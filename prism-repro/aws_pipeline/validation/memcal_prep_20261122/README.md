# memcal-1: local preparation and validation, 22 Nov 2026 (no AWS)

**Nothing was deployed, invoked or charged.**
- **Host:** every check ran on one Windows 11 host (Python 3.12.9), at HEAD af9c4ea, with sockets blocked.
- **Data:** the timings in the dry run are host timings under in-process fakes, not AWS measurements. They show only
  that the bookkeeping and the analysis work.
- **Plan:** `../../MEMCAL_PLAN.md`, hashed in `PLAN.sha256`.

## What was checked

| Check | Result | File |
|---|---|---|
| Unit tests, `aws_pipeline` | 58 of 58 pass: 29 pipeline, 15 collector, 14 new memcal | `tests_aws_pipeline.txt` |
| Unit tests, `aws_measurement` (Runner extended) | 33 of 33 pass | `tests_aws_measurement.txt` |
| Earlier pipeline botocore check (`fake.py` extended) | passes, 26 operations | not saved |
| **memcal botocore check**, offline | passes. 519 requests over 19 operations are valid against botocore 1.44.9 for us-east-2. A wrong parameter is rejected. Scenario: one REPORT lost before collection; coverage 255/256 and not complete; teardown deletes the functions and role but **retains all 16 log groups** at 14-day retention; `cleanup-logs` is refused, then forced; verify CLEAN. | `botocore_check.json` |
| **Full-design dry run** on the fakes (real `docpipe.py`, K scaled to 1/1000, 2 min 39 s) | Preflight; deploy of 16 functions; smoke run OK; blocks 0, 1 and 2 (208 visits each). Peak in flight 8 with a cap of 8; no throttle; 640 configuration updates. All 21,248 REPORTs collected and matched by request ID, and every tail copy equals its CloudWatch copy. Runtime version recorded in every block; no orphan REPORTs. Teardown, cleanup and verify CLEAN. | `dry_run_summary/dry_run_log.json`, `cloudwatch_coverage.json`, `run.log` |
| Analysis of the dry run (2,000 bootstrap replicates) | Runs end to end. FIT 15,592 and CHECK 5,400 invocations; 80 held-out check rows written. The values reflect the fake's host timing and its 1024/m scaling, so they are **not results**. | `dry_run_summary/analysis_*` |
| Analysis against **known synthetic truth** (unit test) | Recovers Eq. (2) non-scaling 0.3 per stage (±0.02) and the Eq. (3)-form fit of P_mean (non-scaling 0.43, 0.35 s at 1024 MB). Finds Lambda-reported init flat while P falls ("P and I trends differ"), with the decision "keep the direction". Over 80% of held-out predictions lie inside the CHECK intervals. | `tests/test_memcal.py` |
| Design | 16 cells; per cell 39 visits, 312 cold and 1,000 warm; FIT 29 visits (232 cold), CHECK 10 (80 cold, 4/3/3 by block); 624 visits, 20,992 invocations; smoke 256. Deterministic: design SHA-256 76ab39d7...5fd. | `dry_run_summary/design.json` |
| Workload record | Handler Git blob 23206632...ae2, last commit ea32370; python3.12 x86_64; K frozen; inputs hashed; start-up behaviour. | `dry_run_summary/workload_spec.json` |
| Guards | Plan only without `--execute`. PermissionError without `PRISM_AWS_AUTHORIZED`. A K scale is refused outside the fakes. `run` refuses on drift in memory, environment or K, or on a tampered design or split. | `tests/test_memcal.py` |
| Estimate at current list prices | USD 1.06 in-region, **USD 1.17** from a laptop (free tier not assumed); 2.4-3.7 active hours over 3 days | `estimate.json` |

**Changes to shared code** (backward compatible; all earlier tests pass):
- `aws_measurement/prism_measure/runner.py`: optional `payloads`, `normalise`, `meta` and `tail_hook`.
- `aws_pipeline/prism_pipeline/fake.py`: `get_function_configuration` returns Runtime, Handler, Timeout, Architectures
  and CodeSha256, and a cold start writes an `INIT_START` line.

**Raw dry-run files** (records, REPORTs, the fake manifest; 28 MB) are in
`aws_pipeline/runs/memcal_dryrun_20261122/final/`, outside Git.

**Prices:** from the public AWS Price List files for us-east-2, retrieved 22 Nov 2026 16:23 UTC: AWSLambda version
20261120203647 and AmazonCloudWatch version 20261119171040. The files were not stored.
