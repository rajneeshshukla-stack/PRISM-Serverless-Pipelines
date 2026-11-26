# R6.1: the smallest credible live PRISM-versus-baseline check: implemented and verified locally; live run pending (23 Nov 2026, revised 24 Nov 2026)

**Nothing here was executed on AWS.** No AWS call, deployment or charge was made. Live execution needs separate
authorisation (`--execute` and `PRISM_AWS_AUTHORIZED`). Every local check uses the fake AWS clients
(`aws_pipeline/prism_pipeline/fake.py`) with sockets blocked. The offline botocore check validates request shapes and
sends nothing.

The harness and controller are the repository's own (`aws_pipeline/`, `src/prism_repro/closed_loop.py`). The workload
is a proposed synthetic document-ingestion pipeline, not a production application.

## Reviewer request (Reviewer 6)

> "Please validate PRISM on a real FaaS platform using an end-to-end four-stage pipeline. Measure actual cold starts,
> activation lag, concurrency, service times, and billing instead of relying entirely on modeled values."

## 1. Unfavourable findings first

- **At the 14.5 s deadline, PRISM keeps 1024 MB in every epoch.** This holds in the offline preview and in every
  mocked run. So the live check exercises PRISM's provisioned-concurrency (P) decisions, not its memory adaptation.
  Live memory actuation through the same adapter was shown only by the fixed-schedule run of 21 Nov 2026
  (`../aws_live_integration/`), which was not driven by PRISM.
- **The previous plan would not have tested PRISM.** In `pc_mode='record'`, PRISM's P is logged but never applied.
  Since memory stays at 1024 MB, both arms would then run identical applied configurations, so the comparison would
  test the harness, not PRISM. The live check therefore needs `--pc-mode apply`, which this pass implements.
- **Compressed time is unsuitable when P is applied.** AWS says provisioned concurrency "doesn't come online
  immediately after you configure it. Lambda starts allocating provisioned concurrency after a minute or two of
  preparation" (lambda-concurrency.html). With 12-s bins, an epoch is 60 s and the lag is 24 s, so new P could not be
  ready inside its own epoch. The plan therefore uses paper time (`--bin-s 60`: 5-minute epochs and a 2-minute lag),
  which makes each arm 40 minutes long.
- **The baseline is OnDemand, not calibrated q90 with smoothing.** OnDemand (1024 MB, P = 0, the platform's default
  scaling) is the reference for R6.1's measurement request: it shows what PRISM's P changes relative to the platform
  itself. Reviewer 6's separate request to compare against "a simple calibrated-q90 + smoothing controller" (R6.4, answered in simulation) is
  not addressed by this check. A third live arm would need its policy wired through `PolicyController` and roughly 40
  more minutes per run. It is not implemented.
- **Some quantities can be measured only partly or not at all in this run.** See section 5. Burst overflow needs a
  separate step-load test. Actual charges need the AWS bill or Cost Explorer export (R2.14).

## 2. What was implemented (local code, 23 Nov 2026)

| Piece | Where | What it does |
|---|---|---|
| Trace-replay arm | `livetest.py` `mode="prism_replay"`, `replay_records`; CLI `--mode prism_replay` | Thins one trace-week of the paper's synthetic trace (seed 101, stationary, test week, minutes 0-39, thin 1/60). Both arms get the identical record list: IDs, arrival offsets and document sizes, written once to `records_plan.jsonl`. |
| PRISM's own controller live | `livetest.py` → `closed_loop.PolicyController(policies.PRISM eps 0.02, gbm)` → `campaign.run_arm` → `ControllerAdapter` | Runs the same controller code as the simulator. Telemetry comes from finished records only; P is scaled back by thinning (P_live = ceil(P x 1/60)). |
| Provisioned concurrency applied | `adapter.LambdaActuator(pc_mode="apply", alias=...)`, `publish_alias`; `aws.deploy(alias=)`; CLI `--pc-mode apply` | Publishes versions and invokes them through alias `live`, since provisioned concurrency is not allowed on $LATEST. Calls `PutProvisionedConcurrencyConfig` per stage and deletes the config for a stage that goes to 0. On a memory change it deletes the config, republishes, verifies the new MemorySize through the alias, and re-requests P. It never relies on undocumented reallocation when an alias is repointed. |
| Requested vs applied | `actuation` in each `decisions.jsonl` line | Memory: `memory_requested`, and `memory_applied` read back from every stage (through the alias in apply mode). P: `pc_requested` (with `pc_clipped_from` if over the cap), `pc_submitted`, `pc_accepted`, `pc_refused` (reason per stage) and `pc_status_after`. `pc_applied` is never set from a request. |
| Readiness, observed | `adapter.PcMonitor` → `<arm>/pc_status.jsonl`; `pc_readiness` → `<arm>/pc_readiness.json`; bounded wait for epoch 0 (`pc_initial_wait`) | Polls `GetProvisionedConcurrencyConfig` every 10 s and logs status, requested, allocated and available. Activation lag = first READY poll with allocated ≥ requested, minus the request time. A request that never becomes READY is reported as "not ready by arm end". |
| Refusals explicit | `pc_status`: `refused_quota` (pre-check, nothing sent), `refused` / `partially_refused` (API error code), `recorded_not_applied` (record mode), `unchanged`, `none_requested` | A refusal is logged and the arm continues on the previous configuration. Before this pass, a refusal raised and stopped every later decision. |
| Quota gate | `livetest.run` after preflight | Reads `UnreservedConcurrentExecutions`. If unreserved − 100 < 4 x pc_cap, the run stops before anything is created. |
| Cost bound | `pc_cap` (default 4 per stage) | A capped P is recorded with its uncapped value. |
| Initialisation type | handler `init_type` (`AWS_LAMBDA_INITIALIZATION_TYPE`: "provisioned-concurrency" or "on-demand", per provisioned-concurrency.html); `driver.stage_rows`; `arm.json` `served_by_init_type` | Separates executions served by provisioned environments from on-demand ones, including spill-over. |
| Telemetry fix | `LiveTelemetry.view` | `n_od` and `cold` now exclude executions served by a provisioned environment. Previously every execution counted as on demand, which was correct only because P was never applied. |
| Coverage fix | `aws.report_coverage(arms=None)` checks every arm directory | The old fixed list omitted `adapter_prism`. A replay run would then have been marked verified, and its log groups deleted, without checking that arm's request IDs. In the first mocked replay, coverage listed only smoke, baseline_ondemand and adapter_schedule. |
| Teardown | `aws.teardown` | Deletes each alias's provisioned-concurrency config first, because it is billed while set. Then it deletes the functions and the other resources, as before. |
| Offline preview | `livetest.preview_decisions` | Shows PRISM's planned decisions before any AWS use (section 4). |

## 3. Verified locally, 23 Nov 2026 (fakes; no AWS)

- **Unit tests: 80 of 80 pass** with `../venv/Scripts/python -m unittest discover -s tests` from `aws_pipeline/`
  (`local_verification/unittest.txt`). That is the 58 earlier tests (one changed, below) plus 22 new ones in
  `tests/test_r61_replay.py`.
- **Changed test.** `test_provisioned_concurrency_refused_at_quota_10` now expects a recorded `refused_quota`
  instead of `PermissionError`. It also checks that apply mode without an alias is rejected.
- **End-to-end self-test** (schedule mode, unchanged sequence): 26 of 26 checks (`local_verification/selftest_checks.json`).
- **Offline botocore 1.44.9 request validation**, nothing sent:
  - replay with `pc_mode='apply'`: 32 operations, including publish_version, create_alias, update_alias, and
    put/get/delete_provisioned_concurrency_config;
  - schedule mode: 26 operations.

  Both are ok, and teardown is clean (`local_verification/botocore_check_*.json`).

What the new tests establish:

| Requirement | Test (`tests/test_r61_replay.py`) |
|---|---|
| The same records reach both arms (ID, offset, size against `records_plan.jsonl`) | `test_same_records_reach_both_arms` |
| PRISM's decisions reach actuation, with decision timing (`observed_upto_bin` = 5k − 2, `decided_wall_ns` ≤ `applied_wall_ns`, `decision_s`), and memory applied = requested | `test_decisions_reach_actuation_with_timing` |
| Telemetry has no lookahead; provisioned executions are neither on demand nor cold | `test_provisioned_environment_is_neither_on_demand_nor_cold` (plus the earlier `test_no_lookahead_and_counts`) |
| A request is not readiness; READY is observed; provisioned environments serve the alias; spill-over is on demand; versions are published, not $LATEST | `test_request_is_not_readiness_and_readiness_is_observed` |
| P changes reach the API, and 0 deletes the config | `test_changes_reach_the_api_and_zero_deletes` |
| A memory change republishes the alias and re-requests P | `test_memory_change_republishes_the_alias_and_reapplies_pc` |
| Refusals are explicit (quota pre-check, API error per stage, cap) | `test_quota_refusal_is_recorded_and_nothing_is_sent`, `test_api_refusal_is_recorded_per_stage`, `test_cap_is_recorded`, `test_apply_needs_an_alias` |
| The run stops before deployment when the quota is too low | `test_apply_stops_before_deploy_when_quota_is_too_low` |
| Readiness and activation-lag summary | `test_readiness_summary`, `test_readiness_observed_and_pc_served` |
| Deadlines, outcomes and 4 request IDs per completed record | `test_records_carry_deadline_outcome_and_request_ids` |
| REPORT coverage includes the PRISM arm; a missing ID blocks verification and keeps the log groups | `test_coverage_checks_the_prism_arm`, `test_missing_prism_arm_report_blocks_verification_and_keeps_logs` |
| Teardown deletes provisioned concurrency first and leaves nothing | `test_teardown_deletes_pc_first_and_is_clean`, `test_verified_and_clean` |
| The plan's counts, alias steps and arm differences | `test_replay_is_deterministic_and_plan_counts` |
| The planned comparison exercises adaptive P decisions, with memory constant | `test_preview_shows_adaptive_pc_decisions` |

The earlier tests still cover:
- resumable REPORT collection and request-ID matching (`tests/test_report_collection.py`);
- invocation errors and Step Functions failures (`test_deadline_outcomes_failures_and_no_retry`,
  `test_sfn_executor_failure_is_recorded`);
- throttling: with the fake's account limit at 1, `TooManyRequestsException` produces failed records that carry the
  error text, and the fake counts the throttles (new: `test_throttled_invocation_is_a_failed_record_with_its_error`);
- the client cap (`test_cap_sheds_and_bounds_in_flight`).

Timing values on the fakes are the host's and mean nothing for AWS.

**Mocked deterministic replay** (scaled time, thin 1/600, 4 epochs, seasonal-naive forecaster):
- both arms received the same records;
- PRISM requested P = 1 per stage at epoch 0, and all four configs were accepted and observed READY before the first
  record;
- provisioned environments served PRISM-arm executions, and none served the baseline;
- coverage was complete, and includes adapter_prism;
- teardown was clean.

At this thinning P did not change after epoch 0. The change path is covered by the unit tests above, and by the
preview at the planned thinning.

## 4. What the planned run is expected to exercise (offline preview, not a measurement)

`local_verification/preview_decisions.json` gives PRISM's decisions for the planned replay. Its telemetry is
synthesised as if every record ran its stages back to back, on demand, at the warm 1024-MB means. Live decisions
depend on measured completions and can differ.

- **gbm** (the paper's forecaster, used in the run):
  - P_live per stage [ingest, transform, aggregate, load] by epoch: [1,2,2,1], [1,2,1,1], [1,2,1,1], [1,2,1,1],
    [1,1,1,1], [1,2,2,1], [1,2,1,1], [1,2,1,1];
  - 5 P changes after epoch 0;
  - memory 1024 MB in all 8 epochs;
  - about 12,300 configured GB-s of provisioned concurrency.
- **seasonal naive:** 3 changes; memory 1024 MB.

## 5. What this run can and cannot measure

| Reviewer item | In this run | Not in this run |
|---|---|---|
| Cold starts | Per stage execution: cold flag, `init_type`, and the REPORT Init Duration of on-demand starts | — |
| Activation lag | Per accepted P change and for epoch 0: time from request to the first READY poll with allocated ≥ requested (10-s resolution), against the controller's 2-minute lag | Distribution over many changes, other sizes or other regions |
| Concurrency | Records in flight (submit and end times); P requested, allocated and available (polls); executions served by provisioned environments vs spill-over | Concurrency above the client cap of 8 |
| Service times | REPORT Duration per stage, end-to-end time per record against 14.5 s | — |
| Billing | REPORT Billed Duration and memory → GB-s; configured provisioned GB-s from the accepted configs over time; list-price estimate | Actual charges (R2.14: needs a usable billing export; none is available locally) |
| Burst overflow | Incidental spill-over count at this load | A controlled step load above P, which needs a separate test (one alias, fixed P, step from below to above P, count on-demand cold starts) |
| Memory adaptation | — | PRISM chooses 1024 MB throughout at 14.5 s |

## 6. Provisioned-concurrency requirements (AWS documentation, read 23 Nov 2026; public pages, no AWS call)

- "You cannot use provisioned concurrency with the $LATEST version" (provisioned-concurrency.html). The qualifier is
  "The version number or alias name" (API_PutProvisionedConcurrencyConfig.html). The kit publishes versions and
  invokes alias `live`.
- "You can configure up to the Unreserved account concurrency in your account, minus 100" (provisioned-concurrency.html).
  The harness pre-checks this and stops before deployment if it fails.
- Status is "IN_PROGRESS | READY | FAILED". The response fields are RequestedProvisionedConcurrentExecutions,
  AllocatedProvisionedConcurrentExecutions and AvailableProvisionedConcurrentExecutions. StatusReason is given "For
  failed allocations" (API_GetProvisionedConcurrencyConfig.html). A configuration request is therefore not readiness,
  and the harness reports readiness only from these reads.
- Repointing an alias that carries provisioned concurrency: the pages read do not state what happens. The harness
  deletes the config first and re-requests P on the new version.
- "Lambda uses on-demand instances to handle any excess traffic" (provisioned-concurrency.html). This is the
  spill-over that the harness records by `init_type`.
- "Lambda bills you for initialization even if the environment instance never processes a request. Provisioned
  concurrency runs continually and incurs separate billing" (provisioned-concurrency.html). This is the reason for the
  cap and for deleting the configs at teardown.
- Not checked on those pages: that a published version's configuration is immutable. The harness does not rely on
  it; it verifies memory through the alias after each publication.

**Quota checks before deployment** (read only):
1. `preflight --execute`: ConcurrentExecutions, UnreservedConcurrentExecutions and leftover resources in us-east-2.
   The live-test gate needs unreserved ≥ 100 + 16 (cap 4 x 4 stages); the run also needs the client cap of 8 plus
   headroom. D7's reading of 400 is one observation from 22 Nov 2026 and must be repeated.
2. No reserved concurrency on the kit's functions; the kit sets none. With reserved concurrency, provisioned
   concurrency cannot exceed it.

## 7. Commands (Git Bash, from `prism-repro/aws_pipeline/`)

```bash
export AWS_PROFILE=prism-ohio                         # the account's us-east-2 profile; every AWS step below uses it
PY=../venv/Scripts/python
R="--region us-east-2 --mode prism_replay --pc-mode apply --bin-s 60 --epochs 8 --thin 0.016666666666666666 --eps 0.02 --forecaster gbm --pc-cap 4"
OUT=runs/r61_prism_replay_$(date +%Y%m%d-%H%M%S)      # new directory; nothing is overwritten

# 0. local, no AWS
$PY -m unittest discover -s tests                     # expect: Ran 81 tests ... OK
aws sts get-caller-identity --profile prism-ohio --query Account --output text   # login valid; account as expected
                                                      # (on "expired": aws login --profile prism-ohio)
$PY -m prism_pipeline $R plan                         # every call; 323 records per arm; estimate line

# 1. read-only preflight (authorised session only)
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
$PY -m prism_pipeline --region us-east-2 preflight --execute   # no STOP line; read Unreserved
$PY -m prism_pipeline --region us-east-2 verify --execute      # must print CLEAN before deploying

# 2-4. deploy, calibrate, smoke, both arms, collect, coverage, analyse, teardown (one sequence)
$PY -m prism_pipeline $R live-test --out $OUT --execute --host-note "<host>, us-east-2, $(date -u +%FT%TZ)"

# 5. check
$PY -m prism_pipeline coverage --run $OUT             # complete: true; matched = 2596
$PY -m prism_pipeline --bin-s 60 analyse --run $OUT --out $OUT/analysis_check --arms baseline_ondemand,adapter_prism
$PY -m prism_pipeline --region us-east-2 verify --execute      # CLEAN, or only retained log groups
unset PRISM_AWS_AUTHORIZED
```

**Recovery** (each step is scoped to the kit's prefix, tag and manifest):

```bash
export AWS_PROFILE=prism-ohio
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES
# interrupted run: delete provisioned concurrency, then everything else; log groups kept unless coverage is complete
$PY -m prism_pipeline --region us-east-2 teardown --manifest $OUT/manifest.json --execute
# incomplete REPORT coverage: resume collection (state in $OUT/cloudwatch_collect_state.json), then re-check
$PY -m prism_pipeline --region us-east-2 collect --manifest $OUT/manifest.json --execute
$PY -m prism_pipeline --region us-east-2 collect --manifest $OUT/manifest.json --execute --rescan   # late lines
# once coverage is complete: delete the retained log groups (refuses otherwise)
$PY -m prism_pipeline --region us-east-2 cleanup-logs --manifest $OUT/manifest.json --execute
$PY -m prism_pipeline --region us-east-2 verify --execute
unset PRISM_AWS_AUTHORIZED
```

A failed arm is not resumable. Keep the failed run's folder, and start a new `$OUT` for the rerun.

## 7a. Pin before deployment, and preflight requirements (added 24 Nov 2026)

**The profile.** Every AWS command runs with `AWS_PROFILE=prism-ohio`, region us-east-2. `livetest.json` records the
profile name, never the account ID.

**The code.** On 24 Nov 2026 the harness changes since 3edc386 are **uncommitted**. Before deployment:
1. Commit them on `closed-loop`, or at least freeze the working tree.
2. Record the commit in the run's host note.

Each run now writes `code` into `livetest.json`:
- `git_head`;
- `uncommitted_paths` under `aws_pipeline/` and `src/`;
- the SHA-256 of every `prism_pipeline/*.py` and of `handlers/docpipe.py`.

A run with `uncommitted_paths` non-empty is still valid as a check, but it cannot be cited until the hashes are
matched to a commit. The files to pin, with their SHA-256 as of this pass, are listed in `PINNED_FILES.sha256`:
- `aws_pipeline/prism_pipeline/{adapter,aws,campaign,cli,driver,estimate,fake,livetest}.py`;
- `aws_pipeline/handlers/docpipe.py`;
- `src/prism_repro/` at 3edc386, clean.

**The configuration (pinned).** The `R` string above, unchanged:
- us-east-2, `prism_replay`, `pc_mode` apply;
- 60-s bins, 8 epochs, thin 1/60, ε 0.02, gbm, `pc_cap` 4;
- trace 101, stationary, test week;
- seed 20261122;
- 14.5 s deadline, client cap 8, alias `live`.

The run uses boto3/botocore from `../aws_measurement/.venv-aws`; botocore 1.44.9 is what the offline request
validation checked.

**Preflight requirements (read only; all must hold before `live-test`):**
1. **Valid login.** `aws sts get-caller-identity --profile prism-ohio` succeeds, and the account is the expected one.
   On 24 Nov 2026 it failed with an expired login, so nothing was read.
2. **Account settings.** `preflight --execute` prints no STOP line:
   - ConcurrentExecutions ≥ 10;
   - no `prism-pipe-` leftovers.
3. **Unreserved concurrency ≥ 116.** That is 100 plus the cap of 4 per stage x 4 stages. The live test also checks
   this itself and stops before creating anything (`res["pc_quota"]`). D7's reading of 400 is one observation from
   22 Nov.
4. **Clean.** `verify --execute` prints CLEAN.
5. **Host.** A host that will not sleep for about 95 minutes, and a USD 1 budget alarm.
6. **Authorisation.** The author has authorised the run; this plan does not.

## 8. Expected counts, duration and cost (from the implemented harness)

**Records** (`plan`):
- 323 records per arm, arriving over 0-2,391 s;
- 649 Step Functions executions (2 x 323 + 3 smoke);
- 2,596 stage REPORT lines with recorded request IDs, which is the coverage target;
- up to 80 calibration-probe REPORTs (≤ 20 per stage), counted as extras.

**Control-plane calls:**
- P puts: 4 at epoch 0, plus about 5 later changes (preview);
- readiness reads: about 4 stages x 240 polls per arm (10 s over 40 min), plus the epoch-0 wait.

**Duration:** about 95 minutes:
- deploy, calibration and smoke, about 5 min;
- baseline arm, 40 min;
- PRISM arm, epoch-0 readiness wait of up to 5 min, then 40 min;
- log settling, 1 min;
- collection and teardown, a few minutes.

The host must not sleep. This machine has suspended overnight, and a Windows Update restart ended a run on 22 Nov.
Prefer daytime with sleep disabled, CloudShell, or a small EC2 host in us-east-2.

**Cost** (UNVERIFIED list prices, `estimate.PRICES_UNVERIFIED`; check them against us-east-2 before approval):
- expected about USD 0.16, made of:
  - USD 0.105 for Lambda duration and requests, Step Functions and logs, with both arms at 1024 MB;
  - USD 0.051 of provisioned concurrency (12,300 GB-s at USD 0.0000041667, from the preview);
- upper about USD 0.62: the PRISM arm at 3,008 MB (USD 0.151) plus the provisioned-concurrency ceiling of
  4 x 4 x 3,008 MB for 40 min (USD 0.47).

Set a USD 1 budget alarm.

## 9. Criteria: is the check valid, and is it ready to expand

**Valid** (all must hold; these are the live pass criteria):
- `livetest.json` has `code.git_head`, and its `files_sha256` match `PINNED_FILES.sha256`, or the differences are
  listed;
- `pc_quota` shows unreserved ≥ 116;
- `verified: true`, meaning every recorded request ID has a REPORT (2,596 of 2,596);
- every record has an outcome;
- 0 unexplained execution errors, with any throttling listed;
- both arms got the same 323 records;
- for every decision, `memory_applied` = `memory_requested`, and P `pc_submitted` and `pc_accepted` are recorded;
- readiness is reported only from `pc_status.jsonl` polls: `pc_applied` stays null, and `pc_readiness.json` gives
  each accepted change as "ready" with its lag, or "not ready by arm end";
- no `adapter_error` and no `pc_monitor_error`;
- teardown leaves no function, state machine, role or provisioned-concurrency config. Log groups may remain only
  if coverage is incomplete.

**Ready to expand** (more weeks, the q90 + smoothing arm, other deadlines), only if also:
- epoch 0's P was READY before the first record;
- every later accepted change was READY within its epoch, or the lag is reported as the finding;
- provisioned environments served PRISM-arm executions, and spill-over is counted;
- the measured end-to-end times at 1024 MB are within the simulator's calibration range. Otherwise, calibrate first.

**If the quota gate stops the run:** run nothing as R6.1 evidence. A record-mode run would leave the two arms'
applied configurations identical at 14.5 s, so it would establish only the harness mechanics already shown on
21 Nov 2026.

## 10. Status for R6.1

R6.1 is still open. The live comparison has not run. What remains is authorised AWS execution of section 7 and its
evidence. R2.14's reconciliation of actual charges stays pending until a usable billing export exists.
