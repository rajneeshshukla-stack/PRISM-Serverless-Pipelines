# Small live collector verification, 22 Nov 2026 (R2.8, R3.1, R6.2)

**What this was.**
- Run `AWS_livetest_20261122-090236`, in us-east-2, from 09:02:43 to 09:08:04 CST (Lambda, CloudWatch Logs and Step
  Functions Express).
- It used the collector of commit d2001a8.
- Memory was fixed at 1024 MB.
- The workload is the proposed synthetic document-ingestion workload, with handlers that do no start-up work
  (decision P3, `PRISM_INIT_ROWS = 0`).
- There were 3 smoke records and 4 records in each of two arms.
- The schedule was fixed (`--schedule 1024`). PRISM's adaptive controller did not run, and no provisioned concurrency
  was configured.
- The author ran it outside this session. Here it is analysed from the saved files only, with no AWS call.

**Not tested:** memory scaling, provisioned-concurrency activation, simulator calibration, or reconciliation of cost
against an invoice.

**Files here.** Only sanitized aggregates: no request ID, account number or ARN.
- `summary.txt`: the recomputed coverage, the per-stage REPORT statistics, the billed-duration check and the cleanup
  evidence.
- `tables/stage_reports.csv`: the per-stage statistics of the 44 matched REPORT records.
- `analyse_collector_run.py`: the analysis. Run it from the repository root with the private folders:

  ```
  python prism-repro/docs/revision/aws_live_collector_20261122/analyse_collector_run.py --run "AWS Live Implementation Log/AWS_livetest_20261122-090236" --cloudtrail "AWS Live Implementation Log/AWS_livetest_20261122-090236_cloudtrail" --out prism-repro/docs/revision/aws_live_collector_20261122
  ```

- `sources.sha256`: SHA-256 of the 20 private source files (the 17 run files and the 3 CloudTrail exports). Those
  files stay outside Git.

## Results (`summary.txt`)

**Coverage**, recomputed from the arms' records and the saved REPORT file:
- 44 expected stage request IDs (smoke 12, baseline 16, adapter 16): 44 matched, 0 missing.
- 100 REPORT records, all with distinct request IDs and no duplicates.
- 56 extras, 14 per function. They are not recorded stage invocations, which is consistent with the calibration
  probes; this is not verified per request ID. They are excluded from the analysis.
- The saved `cloudwatch_coverage.json` agrees, and `livetest.json` has `verified: true`.
- Collection ran in one call, 2 pages per log group, with no retry.

**Matched reports, 1024 MB:**

| Stage | n | cold / warm | Duration, warm median (ms) | Duration, cold median (ms) | Init Duration (ms) | Billed, warm median (ms) | Max Memory Used (MB) |
|---|---|---|---|---|---|---|---|
| ingest | 11 | 5 / 6 | 846 | 939 | 116-149 (median 125) | 847 | 41-42 |
| transform | 11 | 7 / 4 | 4,654 | 4,809 | 93-127 (median 111) | 4,655 | 41-42 |
| aggregate | 11 | 7 / 4 | 2,769 | 3,021 | 89-133 (median 111) | 2,770 | 112 |
| load | 11 | 5 / 6 | 1,276 | 1,401 | 114-120 (median 117) | 1,277 | 42 |

**Field and billing checks:**
- No required field (Duration, Billed Duration, Memory Size, Max Memory Used) is missing.
- Init Duration appears on all 24 cold invocations and on none of the 20 warm ones.
- Billed Duration equals ceil(Duration) on all 20 warm invocations, and ceil(Duration + Init Duration) on all 24 cold
  ones.
- The stage work is calibrated to the simulator's warm means at 1024 MB, so agreement at that size holds by
  construction.
- Smoke 3/3, baseline 4/4 and adapter 4/4 records met the 14.5 s deadline, with no failure and at most 4 pipelines in
  flight (cap 8).

**Cleanup evidence:**
- **Saved teardown listing:** no function, log group or role remained. The state machine was still listed, because
  Express deletion is asynchronous, so the saved last line is `NOT CLEAN`.
- **CloudTrail export** (Lambda, Logs and Step Functions; no IAM file):
  - `DeleteFunction` 4, no error;
  - `DeleteLogGroup` 8: 4 deletions, then 4 `ResourceNotFound` from the manifest pass after the per-function pass;
  - `DeleteStateMachine` 1, no error.
- **Not evidenced in the saved files:**
  - A later `verify` CLEAN result. If reported, it is terminal-reported.
  - IAM role deletion. It rests on the saved teardown listing alone.
