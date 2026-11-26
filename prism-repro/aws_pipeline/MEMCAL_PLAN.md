# First multi-memory calibration campaign (memcal-1), us-east-2: plan and runbook

**Prepared and validated locally on 22 Nov 2026. Nothing has been deployed, invoked or charged.**
- **Code:** `prism_pipeline/memcal.py` and `tests/test_memcal.py`.
- **Local results:** `validation/memcal_prep_20261122/`.

The plan below (design, split, analysis and decision rules) is fixed before any data. Its SHA-256 is recorded in
`validation/memcal_prep_20261122/PLAN.sha256`.

**Reviewer comments addressed:** R1.2, R2.8, R3.1, R4.3, R5.M2 and R6.2 (on-demand parts only).

**Separately scoped, and not part of this campaign:**
- provisioned-concurrency activation and overflow;
- the live adaptive-controller comparison;
- the confirmatory simulator runs.

**Unchanged:** the confirmatory seeds 106-130 (no simulator run here), the manuscript, `results/`,
`CHECKSUMS.sha256` and the reviewer statuses.

## 1. Workload (declared, frozen)

| Item | Value |
|---|---|
| Workload | The synthetic four-stage document-ingestion pipeline (`SPEC.md`), declared by the author as the research workload for this campaign (decision P1). It is not the authors' application. |
| Code | `handlers/docpipe.py`, unchanged since commit ea32370: Git blob `23206632b5f65bc94eb449a2d50e826559bc3ae2`, SHA-256 (LF) `f03a4a72e933f1e7...2f73a7eb64f2ac6e`. Repository HEAD at preparation: af9c4ea. `prepare` records both in the run's `workload_spec.json`, and `deploy` refuses if the handler differs. |
| Runtime, architecture | `python3.12`, `x86_64`. Managed runtime: the exact patch level (`Runtime Version: python:3.12.vNN`) is read from each cold invocation's `INIT_START` line and reported per block, because Lambda patches managed runtimes automatically. |
| Package | Zip with `docpipe.py` only (5,052 bytes); standard library only; no layers. Lambda's CodeSha256 is recorded at deploy and re-checked before every block. |
| Functions | 16: `prism-mcal-<stage>-<MB>` for ingest, transform, aggregate and load, each at 512, 1024, 2048 and 3008 MB. Handler `docpipe.<stage>`; timeout 60 s; tag `project=prism-memcal`. |
| Region, account | us-east-2, one account (profile `prism-ohio`). |
| Work units | **Frozen at the 1024 MB reference:** K = 373 / 4908 / 2264 / 1966 (ingest / transform / aggregate / load). They come from the saved AWS calibration of run `livetest_20261122-090236` (us-east-2, 1024 MB, 22 Nov 2026 09:02 CST). Achieved medians were 0.8005 / 4.0451 / 2.5160 / 1.1852 s, against the paper's 0.8 / 4.0 / 2.5 / 1.2 s. The **same K is used at all four sizes**: `PRISM_CALIBRATION=0`, so the handler ignores any per-request override. Nothing is retuned per size. |
| Matched by construction | K was fitted so that each stage's warm handler time at 1024 MB equals the paper's mean, so the 1024 MB warm times reproduce the targets **by construction**. They are a check, not a finding. What is measured is the trend across 512, 2048 and 3008 MB of this fixed work, plus the cold-start terms and billing. |
| Input mix | One reference document per stage, at every size: `doc_seed` 20261121, 3,000 words, the calibration document. The stage request bodies (165 / 10,043 / 9,602 / 9,940 bytes) are computed locally by running the pure stage functions down the chain. The document a stage receives does not depend on K. The bodies are hashed in `workload_spec.json` and re-checked before every block. The P2 log-normal size mix is **not** used: its spread is set by construction, and it would swamp the cold-minus-warm difference. |
| Start-up behaviour | **Module scope, inside Lambda's INIT:** standard-library imports, a 2,000-word synthetic vocabulary, four compiled regular expressions, and one `env_init` log line. `PRISM_INIT_ROWS=0`, so no classifier or lexicon tables are built (P3 default). **First invocation:** no extra work; first-use costs land inside Duration and are measured as X. **Absent:** no network, files or S3 (sink `none`). **Consequence:** the cold penalty is the platform's plus the standard library's. The paper's 6 s mean initialisation has no code counterpart here, so the campaign tests the direction and shape of the memory trend, not the paper's magnitude. |
| Invocation | Synchronous `Invoke` (RequestResponse, `LogType=Tail`) of each stage function directly from the client. No Step Functions. |

## 2. Design (reused from `aws_measurement/prism_measure`)

**Cells:** 4 stages x 4 sizes = 16.

**Per cell:**
- 39 visits, 13 in each of 3 blocks.
- 312 cold invocations: 39 cold batches of 8.
- 1,000 warm invocations: 125 batches of up to 8, spread 3-4 per visit.

**Totals:** 624 visits and 20,992 invocations (4,992 cold, 16,000 warm). A smoke run adds 16 visits and 256
invocations (128 cold, 128 warm), excluded from the analysis.

**Visit:**
1. Change the function's `PRISM_COLD_NONCE` environment variable. This retires every warm environment.
2. Poll until the update is `Successful`.
3. Release one cold batch of 8 together through a barrier, so each call gets a new environment.
4. Run that visit's warm batches on those environments.

**Randomisation:** each cell's visits are split equally over the 3 blocks, and the 208 visits of a block are run in a
shuffled order. Memory size is therefore not confounded with time of day or day.
- Design seed 20261122; split seed 20261123; smoke seed 20261129.
- These are design seeds, not simulator seeds.

**Blocks:** one block per day on three different days, at different times of day.

**Concurrency cap: 8 in flight.** It is enforced twice: no batch exceeds 8, and a bounded semaphore limits calls.
- Preflight requires an account limit of at least 10. The us-east-2 limit read on 21 Nov 2026 was 400; it is re-read
  at preflight.
- Nothing else may run in the account and region during a block.

**Cold and warm are observed, not assumed:**
- **Handler:** each response carries a `cold` flag (the first call in a new environment), an environment ID and the
  nonce.
- **Lambda:** the REPORT line has an `Init Duration` only on a cold start.
- **Flags:** the analysis flags `cold_without_init`, `warm_with_init`, `unexpected_warm_in_cold_batch` and
  `unexpected_cold_in_warm_batch`.
- **Warm baseline:** built only from warm invocations in warm batches.

**Held-out data for checking the calibration:** per cell, 29 FIT visits (232 cold) and 10 CHECK visits (80 cold, and
their warm batches).
- The 10 CHECK visits fall 4/3/3 across the blocks (random block order), and are chosen at random within each block.
- They are assigned by `split_of` before any data and saved in `design.json`.
- `run` refuses if `design.json`, the split or the deployed configuration differ from what was declared.
- CHECK visits are used for nothing but the calibration check.

## 3. What is recorded, per invocation, separately

| Quantity | Source |
|---|---|
| Client latency `e2e_s` | monotonic client clock around the whole synchronous call, including reading the response |
| Lambda Init Duration | REPORT line (cold only) |
| Handler Duration | REPORT line |
| Billed Duration | REPORT line. It includes INIT on cold starts: all 44 REPORTs of run livetest_20261122-090236 showed ceil(Duration [+ Init]). |
| Memory Size, Max Memory Used | REPORT line |
| `handler_s`, `module_init_s`, `env_id`, `nonce`, `k`, `memory_mb` | the stage's own trace entry, normalised so the document is not stored |
| runtime patch level | `INIT_START` line of the cold invocation's log tail (ARN dropped) |
| request ID | response metadata; the join key |

## 4. REPORT collection and cleanup

1. Each invocation's REPORT is parsed from its log tail.
2. `collect` saves every REPORT line of the 16 log groups through the repaired collector (`aws.collect_reports`):
   - page by page;
   - each page flushed before its token is saved;
   - 5 attempts per page;
   - resumable, with duplicates skipped.
   The window is fixed at the first collection, from 10 min before the first recorded invocation to 13 days later.
   Later blocks use `--rescan`.
3. `coverage` matches every recorded request ID (smoke and campaign) against the saved REPORTs. It writes
   `cloudwatch_coverage.json` with:
   - matched, missing and the missing IDs;
   - extras;
   - where the tail and CloudWatch copies differ.
4. Log groups have **14-day retention**.
   - `teardown` deletes the functions and role in every case.
   - It deletes the log groups **only if coverage is complete**. Otherwise it keeps them, re-applies the retention, and
     lists them in the manifest.
   - `cleanup-logs` refuses to delete retained groups until coverage is complete; `--force-delete-incomplete` is
     recorded as forced.
5. **Collect after every block.** REPORTs are then saved before the next day, and well inside the retention.

## 5. How the results test Eq. (3)

Decomposition per cell, fit split only (as in `docs/revision/init_vs_memory/MEASUREMENT_PLAN.md`):

| Quantity | Definition |
|---|---|
| `I` | median Lambda-reported Init Duration |
| `P` | median cold e2e minus median warm e2e: the full first-call penalty |
| `X` | median cold Duration minus median warm Duration |
| `R` | P − I − X: environment creation and the network |
| `P_mean` | mean cold e2e minus mean warm e2e; the simulator uses means |

Uncertainty comes from a bootstrap over batches (2,000 replicates). A trend is the slope of log quantity on log
memory over 512-3008 MB. Eq. (3) as implemented has slope −0.273 over these sizes.

**(a) Decision on P.** The MEASUREMENT_PLAN rule is applied to the fit-split P slope, per stage and pooled. It needs
at least 25 cold and warm batches per cell; there are 29 FIT cold batches.

| P slope interval | Decision |
|---|---|
| contains −0.273 | keep Eq. (3); refit `init_mean_1024` and `init_nonscaling` |
| below 0, excluding −0.273 | keep the direction; refit the non-scaling share |
| contains 0, excluding −0.273 | `constant` or `measured` |
| above 0 | `inverted` or `measured`; narrow the RQ4 memory claims |

**(b) Lambda-reported init against the full first-call penalty.**
- The slopes of I and P are reported side by side, with their intervals.
- The bootstrap interval of (slope P − slope I) is also reported.
- If that interval excludes 0, the two trends differ: Eq. (3) must say which quantity it models, and in the
  simulator initialisation is the occupancy before service, which is P.
- Otherwise no difference is detectable.

**(c) Calibration, checked on held-out data.** Fitted on FIT visits only:
- **Eq. (2) form for warm Duration:** `d1024` and `nonscaling` per stage. The 3008/2048 ratio is reported as a
  single-vCPU plateau check.
- **Eq. (3) form for `P_mean`, and for I:** `init_mean_1024` and `init_nonscaling`; a fit at the boundary is flagged.
- **`measured` mode:** the per-size fit-split means, i.e. the `init_mean_measured` candidate.

Each prediction is compared with the CHECK split's own 95% batch-bootstrap interval (`calibration_check.csv`). A
calibrated form **passes** for a quantity and stage when its prediction lies inside the CHECK interval at all four
sizes. Otherwise the failing sizes are reported, and that form is not used for that stage.

**What this does not do:** replace any simulator constant. Recalibrating the simulator from these values and
regenerating results is a separate step.

## 6. What the campaign can establish

All of this holds for the declared workload, on demand, in us-east-2, with up to 8 concurrent invocations.

| ID | Can establish | Cannot establish |
|---|---|---|
| R1.2 (c) | The measured direction and shape of the cold penalty against memory; the decision rule applied; an `init_mean_measured` candidate for re-centring the sweep | The paper's 6 s magnitude (no start-up code, P3); real application start-up |
| R2.8 | (a1) Warm execution time against memory (1024 MB by construction; spread not measured: one document). (a2) I, P, X, R per size. (a4) Billed GB-s and requests, measured. (b) Eq. (2) and Eq. (3) parameters, checked on held-out data | (a3) Concurrency activation (provisioned concurrency). Actual charges until reconciled with the bill. The simulator recalibration itself (separate step) |
| R3.1 (a) | Eq. (3)'s direction on a real platform, by the stated rule | (b) the 2-minute activation lag |
| R4.3 (a1) | Initialisation per memory size (I and P) | (a2) activation time; (a3) overflow under a burst |
| R5.M2 | A measured initialisation centre for the sweep | the lag centre; RQ3 effects (simulator work) |
| R6.2 | Cold starts, service times, billing fields, and on-demand concurrency up to 8 | Activation lag; provisioned-concurrency behaviour; scale beyond the cap |

**No reviewer status changes until the campaign has run, its coverage is complete, and the results are checked.**

**Caveats to report:**
- A laptop client adds wide-area latency and its variance to P and R, but not to I or X. An in-region host is better
  if available.
- Single-threaded pure-Python work may plateau above about 1,769 MB, which the Eq. (2) check will show.
- The runtime patch level may change between days; it is reported.

## 7. Local validation (no AWS; `validation/memcal_prep_20261122/`)

See the folder's `README.md`:
- unit tests for both harnesses;
- the full-design dry run on the fakes (real handler code, K scaled to 1/1000, sockets blocked);
- the offline botocore request check;
- the estimate.

## 8. Commands (Git Bash, from `prism-repro/aws_pipeline`)

```
cd prism-repro/aws_pipeline                      # from the repository root
PY=../venv/Scripts/python                        # boto3 is taken from ../aws_measurement/.venv-aws
export AWS_PROFILE=prism-ohio
RUN=runs/memcal_$(date +%Y%m%d-%H%M%S)           # new directory, outside Git; never reused

# Local, no AWS
$PY -m prism_pipeline.memcal prepare --run $RUN               # design.json + workload_spec.json
$PY -m prism_pipeline.memcal estimate --out $RUN/estimate.json
$PY -m prism_pipeline.memcal deploy --run $RUN                # PLAN ONLY: prints every call

# Day 1 (once authorised; re-authenticate the profile first, e.g. `aws login --profile prism-ohio`)
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline.memcal preflight --execute              # read only; any STOP line ends the session
$PY -m prism_pipeline.memcal deploy --run $RUN --execute      # role, 16 log groups, 16 functions (resumable)
$PY -m prism_pipeline.memcal smoke --run $RUN --execute --host-note "<host, network, date time>"
$PY -m prism_pipeline.memcal collect --run $RUN --execute     # first collection fixes the window
$PY -m prism_pipeline.memcal coverage --run $RUN              # local; exit 0 = complete
$PY -m prism_pipeline.memcal run --run $RUN --block 0 --execute --host-note "<host, network, date time>"
$PY -m prism_pipeline.memcal collect --run $RUN --execute --rescan
$PY -m prism_pipeline.memcal coverage --run $RUN
unset PRISM_AWS_AUTHORIZED

# Day 2 and Day 3: same four lines with --block 1, then --block 2 (re-authenticate first)
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline.memcal run --run $RUN --block 1 --execute --host-note "..."
$PY -m prism_pipeline.memcal collect --run $RUN --execute --rescan
$PY -m prism_pipeline.memcal coverage --run $RUN
unset PRISM_AWS_AUTHORIZED

# After block 2: analyse, then clean up
$PY -m prism_pipeline.memcal analyse --run $RUN --out $RUN/analysis            # local
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline.memcal teardown --run $RUN --execute    # log groups deleted only if coverage is complete
$PY -m prism_pipeline.memcal verify --execute                 # read only; must print CLEAN
unset PRISM_AWS_AUTHORIZED
```

**If teardown prints `RETAINED`:** within 14 days, run:

```
collect --rescan
coverage
cleanup-logs --run $RUN --execute
verify --execute
```

**Resuming an interrupted block:** rerun the same `run --block N` line. Completed visits are skipped and the broken
visit reruns under a new attempt number. Note any laptop sleep or suspension in the host note of the resumed run.

**Stop conditions:**
- any `STOP` line;
- the smoke check not `SMOKE OK`;
- any throttle or function error;
- a cold batch that is not cold;
- configuration drift (`run` refuses by itself);
- spend above the authorised ceiling.

**Operator permissions:**
- **IAM:** `iam:CreateRole`, `TagRole`, `GetRole`, `AttachRolePolicy`, `DetachRolePolicy`, `DeleteRole`,
  `PassRole`.
- **Lambda:** `lambda:CreateFunction`, `TagResource`, `ListTags`, `GetFunctionConfiguration`,
  `UpdateFunctionConfiguration`, `InvokeFunction`, `ListFunctions`, `DeleteFunction`, `GetAccountSettings`.
- **CloudWatch Logs:** `logs:CreateLogGroup`, `TagResource`, `PutRetentionPolicy`, `DescribeLogGroups`,
  `FilterLogEvents`, `DeleteLogGroup`.
- **STS:** `sts:GetCallerIdentity`.
- No Step Functions permission is needed.

## 9. Duration and cost (`validation/memcal_prep_20261122/estimate.json`)

**Prices** are the current us-east-2 list prices from the public AWS Price List, retrieved 22 Nov 2026 16:23 UTC:

| Item | Price | Publication |
|---|---|---|
| Lambda x86 duration | $0.0000166667 per GB-s (tier 1) | AWSLambda, 2026-11-20 |
| Lambda requests | $0.20 per million | AWSLambda, 2026-11-20 |
| CloudWatch Logs ingestion | $0.50 per GB | AmazonCloudWatch, 2026-11-19 |
| CloudWatch Logs storage | $0.03 per GB-month | AmazonCloudWatch, 2026-11-19 |

The free tier is not assumed.

| Client scenario | Billable GB-s incl. INIT (three duration models) | Lambda USD | Active hours (per block) | Planning upper, USD |
|---|---|---|---|---|
| In-region (0.3 s platform cold, 0.05 s overhead, 5 s update) | 47,018 - 60,610 | 0.79 - 1.01 | 2.4 - 2.6 (0.8 - 0.9) | 1.06 |
| Laptop over WAN (1.0 s, 0.25 s, 10 s) | 52,642 - 66,234 | 0.88 - 1.11 | 3.6 - 3.7 (1.2 - 1.25) | **1.17** |

**Small additions:**
- requests: USD 0.004 (20,992 of them);
- logs: about 0.03 GB, USD 0.014;
- the smoke run: about USD 0.01 and 4 minutes;
- data transfer of the responses (about 0.28 GB): at most USD 0.03, at an **unverified** $0.09/GB.

**Elapsed time:**
- deploy: about 5 min;
- each collection: a few minutes;
- **three calendar days**, attended for about 1.5 h each.

**Kept apart in reporting:**
- **Invocations and billable durations** are measured from the REPORT lines: `analysis/all/billing.csv` gives requests
  and billed GB-s per cell, with Billed Duration including INIT.
- **Actual AWS charges** come only from the bill or the Cost and Usage Report: the Lambda GB-second and request usage
  types, and CloudWatch Logs ingestion, in us-east-2, for the campaign days. Free-tier credits may make them zero.
  They are to be reconciled after the bill settles, as in `aws_measurement/RUNBOOK.md`. No charge is claimed until
  then.

## 10. Cleanup checks

- **verify:** `verify --execute` prints `CLEAN`: no `prism-mcal-` function, no `/aws/lambda/prism-mcal-` log group,
  and no `prism-mcal-lambda-role`.
- **Manifest:** it records any `retained_log_groups`, and whether a log deletion was forced.
- **Before deleting log groups:** `cloudwatch_coverage.json` shows `complete: true`, `missing: 0` and
  `collection_status: complete`.
- **Local files:** the raw run directory (records, REPORTs, manifest with account ID and ARNs) stays outside Git.
  Only sanitised aggregate tables are committed later.
- **Optional:** a CloudTrail export of the campaign days confirms every `DeleteFunction`, `DeleteLogGroup` and
  `DeleteRole`.
