# Smallest live test in us-east-2 (for a separately authorised run)

**Nothing in this file has been executed.** Every AWS command prints a plan and touches nothing unless it gets
`--execute` **and** the shell has `PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES` (the measurement harness's guard).

## What it verifies, and what it does not

**Verifies, on real AWS:**
- the deployment (two roles, four functions, an Express state machine);
- calibration of each stage to the paper's warm means at 1024 MB;
- that records flow through all four stages under Step Functions;
- that the request IDs join: client, Lambda context, header and REPORT line;
- per-stage and end-to-end timing, cold-start logging, and deadline outcomes against 14.5 s;
- the adapter changing memory at epoch boundaries, and how long each change takes (an R2.20 overhead);
- a baseline arm (OnDemand, 1024 MB) on the **same** 40 records as the adapter arm;
- the analysis on real data;
- a clean teardown.

**Does not verify:**
- **Any PRISM result.** Neither cost nor compliance is measured.
- **Provisioned concurrency.** It is impossible at the quota of 10; the requested P is only recorded.
- **PRISM's own decisions.** The adapter arm runs a fixed memory schedule, 1024 → 512 → 2048 → 1024. PRISM's
  controller through the adapter is tested locally only, because a PRISM-controlled run in paper time takes hours
  (SPEC.md, P5 and P6).
- **Paper time.** Time is compressed: 12-s bins, 60-s epochs.
- **Window-level SLO statistics.** 40 records are too few.
- **The authors' application.** The workload is the proposed one (SPEC.md, P1).

## Design

| Step | What | Invocations |
|---|---|---|
| preflight | read-only: account limits, leftovers | 0 |
| deploy | roles; 4 log groups (7-day retention); 4 functions (1024 MB, 60 s timeout); state machine | 0 |
| calibrate | chain mode, 1024 MB, reference document of 3,000 words; linear fit per stage; then `PRISM_K` set and calibration mode off | at most about 80 |
| smoke | 3 records through the state machine, 30 s apart, cap 1 (the first is cold at every stage) | 12 |
| arm `baseline_ondemand` | force cold; OnDemand (P = 0, 1024 MB); 40 records, Poisson 12/min, seed 20261122, at most 8 in flight | 160 |
| arm `adapter_schedule` | force cold; memory 1024 / 512 / 2048 / 1024 / 1024 per 60-s epoch; **the same 40 records** | 160 |
| collect | wait 60 s; REPORT lines from the four log groups (paginated filter) | 0 |
| analyse | local | 0 |
| teardown | always, in `finally` (unless `--keep`), then a leftover listing | 0 |

**Concurrency:**
- At most 8 records are in flight. Stages run one after another, so that is at most 8 Lambda executions, leaving 2 of
  the quota of 10 spare.
- At 12/min, with records taking about 9 s at 1024 MB (17.5 s at 512 MB if CPU-bound), the mean in flight is 2 to 4.
- A record that arrives when 8 are in flight is logged as `shed_client_cap`, not run and not retried. Under Poisson
  arrivals this is expected for well under one record per arm (an estimate, not measured).

**Expectations, not results:**
- At 1024 MB, e2e should be about 9 s, which meets the deadline.
- At 512 MB, CPU-proportional scaling predicts about 17.5 s (missed), while the simulator's Eq. (2) predicts about
  13.3 s (met). The eight or so records in that epoch therefore show which applies, for this workload.
- At 2048 MB, the prediction is 4.8-6.9 s.

## Expected cost (`validation/prep_20261121/estimate.json`)

**Prices are UNVERIFIED** list prices (x86 Lambda $0.0000166667/GB-s and $0.20/M requests; Step Functions Express
$1.00/M requests and $0.00001667/GB-s; CloudWatch Logs $0.50/GB ingested). Check them for us-east-2 before approval;
`python -m prism_pipeline estimate --price-lambda-gb-s ...` recomputes. No free tier is assumed.

| Duration model | Lambda GB-s | Invocations | Executions | Total |
|---|---|---|---|---|
| CPU share proportional to memory | 1,212 | 412 | 83 | $0.022 |
| Single vCPU plateau above 1,769 MB | 1,222 | 412 | 83 | $0.022 |
| Eq. (2) | 1,229 | 412 | 83 | $0.022 |

**How the figure is built:**
- Lambda duration is about 94% of it. The estimate includes INIT billed as duration, and calibration at its upper
  bound.
- Step Functions adds about $0.001, and logs about $0.0003.
- There is no S3, provisioned concurrency, NAT or data-transfer charge: the client calls public endpoints in the same
  region.

**Approval figures:**
- Suggested ceiling: $0.25.
- Budget alarm: $1.
- The client host is extra if it is EC2; CloudShell is free.

## Duration

**About 20-25 minutes in total:**
- deploy, 2-3 min (IAM propagation retries);
- calibration, about 2 min;
- smoke, about 1.5 min;
- each arm, about 5.5 min (forced-cold reset, then 5 epochs of 60 s);
- log settling, 1 min;
- teardown, about 1 min.

**Machine sleep.** A laptop that sleeps mid-arm spoils that arm's timing; the arm is not resumable. Prefer
CloudShell or a small EC2 host in us-east-2.

## Before the run

1. **Authorisation.** The author approves the run, the region (us-east-2) and the ceiling, and sets a budget alarm.
   Decisions P1-P3 are not needed for this test.
2. **Nothing else running in the account and region.** The quota of 10 is shared, so the measurement harness's
   `prism-meas-` functions must not run at the same time.
3. **Python.** Run with the project venv (`../venv`, which has numpy and scikit-learn; the live test imports
   `prism_repro`). boto3 is not installed into it. When boto3 is missing, `aws.clients` appends
   `aws_measurement/.venv-aws`'s site-packages (boto3 1.44.9, already present) to the path, as the local check
   `tests/check_botocore_shapes.py` does. On another host (CloudShell or EC2):
   `pip install -r ../requirements.txt boto3`.
4. **Operator IAM permissions:**
   - `iam:CreateRole`, `iam:GetRole`, `iam:TagRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`,
     `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:DeleteRole`, `iam:PassRole` (both roles);
   - `lambda:CreateFunction`, `lambda:TagResource`, `lambda:ListTags`, `lambda:GetFunctionConfiguration`,
     `lambda:UpdateFunctionConfiguration`, `lambda:InvokeFunction`, `lambda:ListFunctions`,
     `lambda:DeleteFunction`, `lambda:GetAccountSettings`;
   - `logs:CreateLogGroup`, `logs:TagResource` (or `logs:TagLogGroup`), `logs:PutRetentionPolicy`,
     `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:DeleteLogGroup`;
   - `states:CreateStateMachine`, `states:TagResource`, `states:ListStateMachines`, `states:ListTagsForResource`,
     `states:StartSyncExecution`, `states:DeleteStateMachine`;
   - `sts:GetCallerIdentity`.

## Commands (from `prism-repro/aws_pipeline`, Git Bash)

```
PY=../venv/Scripts/python                             # boto3 from ../aws_measurement/.venv-aws (step 3)
OUT=runs/livetest_$(date +%Y%m%d-%H%M%S)              # new directory; nothing is overwritten
$PY -m prism_pipeline plan                            # prints every call (no AWS)
$PY -m prism_pipeline estimate                        # with --price-* once current prices are checked

export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES          # only once the run is authorised
$PY -m prism_pipeline preflight --execute             # read only; STOP lines end the run
$PY -m prism_pipeline live-test --out $OUT --execute --host-note "<host, region, date>"
$PY -m prism_pipeline verify --execute                # read only: must print CLEAN
unset PRISM_AWS_AUTHORIZED
```

**If the run is interrupted** (Ctrl-C, a crash, a closed session), run:

```
$PY -m prism_pipeline teardown --manifest $OUT/manifest.json --execute
```

Then run `verify --execute`. The manifest is written after every created resource, so a partial deploy is still
torn down; this is tested. Teardown keeps the run's log groups unless REPORT coverage is complete; see "REPORT
collection" below.

## REPORT collection: resume, check, then delete the log groups (fix of 22 Nov 2026)

**Why.** Run `livetest_20261121-203051` lost every REPORT line, in three steps:
1. The first `filter_log_events` call failed on a credential refresh (`EndpointConnectionError` on
   `https://us-east-2.signin.aws.amazon.com/v1/token`), after a stall of about 12 minutes.
2. Nothing had been saved by then.
3. Teardown in `finally` then deleted the log groups.

**What the kit does now** (tests: `tests/test_report_collection.py`):
- `collect_reports` fetches page by page. Each page's REPORT records go to `cloudwatch_reports.jsonl` and are flushed
  to disk **before** the page token is saved in `cloudwatch_collect_state.json`.
- A failed page is retried 5 times, with 1, 2, 4 and 8 s between attempts. If it still fails, collection stops
  without raising and is marked `incomplete`.
- A resumed collection never writes a request ID twice, even when a page is re-fetched after a crash.
- An expired page token restarts that log group; repeated entries are still skipped.
- `coverage` compares every Lambda request ID recorded in `smoke/`, `baseline_ondemand/` and `adapter_schedule/`
  `records.jsonl` with the saved REPORT records. It writes `cloudwatch_coverage.json` (matched, missing, the missing
  IDs with arm, record and stage, and extras such as calibration probes). `complete` means collection finished and
  nothing is missing.
- The run's `livetest.json` has `verified: true` only if coverage is complete and no error occurred. `live-test`
  exits 1 otherwise.
- Teardown (default `--delete-log-groups auto`) deletes the functions, state machine and roles in every case. It
  deletes **this run's** log groups (those listed in the manifest) only if coverage is complete. Otherwise it keeps
  them:
  - it re-applies their 7-day retention;
  - it records them under `retained_log_groups` in the manifest;
  - it prints `RETAINED ...` with the resume commands.

  Nothing outside `/aws/lambda/prism-pipe-` is touched.

**Resume after a failure.** Re-authenticate first (for example `aws login` or `aws sso login`). Then, within 7 days,
before the retention expires:

```
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline collect --manifest $OUT/manifest.json --execute     # resumes from the saved tokens; exit 0 = complete
$PY -m prism_pipeline coverage --run $OUT                                 # local; lists any missing request IDs
$PY -m prism_pipeline collect --manifest $OUT/manifest.json --execute --rescan   # only if IDs are missing: re-reads for late delivery
$PY -m prism_pipeline analyse --run $OUT --out $OUT/analysis              # local
$PY -m prism_pipeline cleanup-logs --manifest $OUT/manifest.json --execute   # deletes the retained groups; refuses unless coverage is complete
$PY -m prism_pipeline verify --execute                                    # must print CLEAN
unset PRISM_AWS_AUTHORIZED
```

No Lambda function is invoked again, and the functions themselves are already deleted. If IDs stay missing after a
rescan, the run is not verified. Deleting the evidence anyway needs `cleanup-logs --force-delete-incomplete`, which
the manifest records as forced.

## Smallest live verification of the fix (us-east-2; separately authorised; not yet run)

**Purpose:** a few cold and warm invocations, with every REPORT line saved and matched before any log group is
deleted.

```
$PY -m prism_pipeline --records 4 --rate 12 --schedule 1024 plan       # no AWS; check the calls
$PY -m prism_pipeline --records 4 --rate 12 --schedule 1024 estimate
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline preflight --execute
$PY -m prism_pipeline --records 4 --rate 12 --schedule 1024 live-test --out $OUT --execute --host-note "<host, date>"
$PY -m prism_pipeline coverage --run $OUT
$PY -m prism_pipeline verify --execute
unset PRISM_AWS_AUTHORIZED
```

**What runs:**
- calibration probes;
- 3 smoke records one at a time: the first is cold at every stage, the rest warm;
- 4 records per arm at 1024 MB, each arm starting cold.

That is 44 stage invocations that must each have a REPORT: 4 stages x (3 + 4 + 4).

**Pass:**
- `livetest.json` shows `verified: true`;
- `cloudwatch_coverage.json` shows `expected_request_ids: 44`, `missing: 0`, `collection_status: complete`;
- in `analysis/analysis.json`, `report_missing: 0` and `cold_without_init_duration: 0`, with at least one cold and
  one warm row per stage;
- teardown deleted the log groups itself (no `RETAINED` line);
- `verify` prints CLEAN.

**Expected cost:** about USD 0.006 at the UNVERIFIED list prices (`validation/report_fix_20261122/
estimate_min_verification.json`). That is 124 Lambda invocations, 80 of them calibration probes; about 336 GB-s
upper bound; and 11 Step Functions executions. Check current us-east-2 prices before approval. The suggested budget
alarm stays at USD 1.

**What can remain after a failure:**
- **Log groups kept on purpose.** If collection is incomplete, the four `/aws/lambda/prism-pipe-<stage>` log groups
  stay, with 7-day retention, until `cleanup-logs` (or the retention) removes them. They bill only storage, a few kB.
- **State machine still listed.** Express deletion is asynchronous: the 21 Nov run's state machine was still listed
  right after `DeleteStateMachine` succeeded. Rerun `verify` after a minute.
- **Teardown itself fails** (for example, credentials expire again). The manifest's functions, state machine, roles
  and log groups remain. None of them bills while idle except log storage, since no provisioned concurrency is
  created. Re-authenticate and rerun `teardown --manifest $OUT/manifest.json --execute`.

## Stop conditions

`live-test` stops by itself on:
- any error;
- preflight `STOP` lines (leftovers, or an account limit below 10).

Inspect `$OUT/livetest.log`. After the run, treat any of these as a failed verification:
- `verified: false` in `$OUT/livetest.json`, or `complete: false` in `$OUT/cloudwatch_coverage.json` (missing REPORT
  records, or collection incomplete); resume as in "REPORT collection";
- `failed` records, `report_missing`, `duplicate_request_ids` or `cold_without_init_duration` in
  `$OUT/analysis/analysis.json`;
- throttling errors in any record;
- a memory change that is not applied before the next epoch (`applied_late_s` and `memory_update_s` in the decision
  logs);
- `client_clock_ahead: true` in `clock_check`: the client clock is ahead of AWS, so telemetry binning is off. Sync the
  clock and rerun.

## Cleanup: scoped to this test's resources

**Teardown deletes:**
- **From the manifest:** the state machine, the four functions, the inline policy and the two roles, plus their log
  groups **only if REPORT coverage is complete**. Otherwise the log groups are kept, with 7-day retention, and
  `cleanup-logs` deletes them later. `--delete-log-groups always` restores the old behaviour.
- **Beyond the manifest:** only resources that carry **both** the `prism-pipe-` prefix **and** the tag
  `project=prism-pipeline`.

**Never touched:**
- the measurement harness's `prism-meas-` resources;
- untagged resources, even with the prefix. Such a resource is listed as NOT CLEAN rather than deleted.

Both behaviours are tested (`tests/test_pipeline.py::TestAWSGuardAndCleanup`).

**After a verified teardown, nothing billable is left:**
- no versions, aliases, provisioned concurrency, buckets or Step Functions log groups were created;
- the log groups' already-ingested bytes have been billed, and deleting the groups stops storage.

After an unverified run, the retained log groups bill storage, a few kB, until `cleanup-logs` deletes them or the
7-day retention removes their events.

**Independent read-only check:**

```
aws lambda list-functions --region us-east-2 --query "Functions[?starts_with(FunctionName,'prism-pipe-')].FunctionName"
aws stepfunctions list-state-machines --region us-east-2 --query "stateMachines[?starts_with(name,'prism-pipe-')].name"
aws logs describe-log-groups --region us-east-2 --log-group-name-prefix /aws/lambda/prism-pipe-
aws iam get-role --role-name prism-pipe-lambda-role     # expect NoSuchEntity; likewise prism-pipe-sfn-role
```

## After the run

1. **Keep `$OUT` outside Git.** It holds records, decisions, manifest, CloudWatch reports and analysis. Commit only
   `$OUT/analysis/*.csv` and `analysis.json`, as for the other raw datasets.
2. **Billing reconciliation.** Once the bill settles, compare the analysis cost (`cost_usd_arms_only`) and the
   estimate with the bill (R2.14).
3. **Report in this order:** failures and unfavourable items first, then whatever was verified. Label every number as
   a smoke-test measurement of the proposed workload, not of PRISM.
