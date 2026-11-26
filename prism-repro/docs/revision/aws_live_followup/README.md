# Follow-up analysis of the saved live run (R3.1, R2.8, R6.2, R2.14)

**Scope.** This analyses run `livetest_20261121-203051` from the saved records only. It makes no AWS call and reruns
nothing. The committed evidence package for that run is `../aws_live_integration/` (commit 78ba419), and the hashes of
the private run files are in `../aws_live_integration/sources.sha256`.

**What the run was:**
- a live fixed-schedule integration test, in us-east-2;
- on the proposed synthetic document-ingestion workload;
- with handlers that do no start-up work (`aws_pipeline/SPEC.md` decision P3, `PRISM_INIT_ROWS = 0`).

**What it was not:**
- PRISM's adaptive controller was not evaluated live.
- No CloudWatch REPORT entries were saved, so the Lambda Init Duration, Billed Duration and Max Memory Used figures are
  unverified.
- No billing record exists.

Every figure below is a client-visible or in-function measurement, labelled as such.

**Reproduce** (from the repository root; standard library only; the private run folder is needed):

```
python prism-repro/docs/revision/aws_live_followup/analyse_saved_run.py \
  --run "AWS Live Implementation Log/AWS_livetest_20261121-203051" \
  --out prism-repro/docs/revision/aws_live_followup
```

It writes `tables/*.csv` and `build_output.txt`, and scans them for account IDs, ARNs, request or environment IDs and
IP addresses (last run: clean).

## Results

| Quantity | Value | Basis | Comment it bears on |
|---|---|---|---|
| Added latency of a cold stage (median cold gap minus median warm gap) | 0.230 s at 512 MB (9 cold rows), 0.230 s at 1024 MB (19), 0.228 s at 2048 MB (9) | Gap between the previous stage's end and this stage's start, on the clocks of two Lambda hosts; stages 2-4 only | R3.1(a), R2.8 |
| Warm execution-time variability | CV of handler time 0.11-0.34; per 1,000 words 0.005-0.062 (12 stage-size cells, 10-49 rows each) | In-function timer | R2.8 |
| Peak concurrency | at most 5 concurrent executions per function and 7 across all functions; 0 failed records in either arm | Lambda host clocks | R6.2 |
| Lambda GB-s, lower bound | 356.5 (baseline) and 381.5 (schedule arm), about USD 0.012 together at the unverified list price | Handler time x memory; excludes initialisation and billing rounding; **an estimate, not a bill** | R2.14 |
| Step Functions billed GB-s | 22.9 and 27.55 | As returned by AWS with each execution | R2.14 |

## Reading the results

- **Cold-start latency.** With no start-up work, a cold stage adds about 0.23 s, and the amount does not change with
  memory from 512 to 2048 MB.
  - This is only the platform's own start-up for a small Python function. It is not PRISM's assumed 6 s mean
    initialisation, and it is not a Lambda Init Duration.
  - It does not test Eq. (3) for a function with real start-up work, which needs decision P3 and REPORT lines.
  - It agrees in direction with the external SeBS data, where Lambda-reported initialisation is nearly flat with
    memory (`../init_vs_memory/`).
- **Warm-time variability.** Once document size is divided out, the platform adds 0.5-6.2% variation to warm handler
  time. Nearly all of the 11-34% spread in raw handler time comes from the input-size distribution, which the workload
  draws on purpose (P2, log-normal, sigma 0.30). One run cannot separate the platform's noise from anything else.
- **Concurrency.** These are low levels: at most 8 pipelines were ever in flight. They show no throttling or failure
  at these levels and say nothing about bursts or provisioned capacity.
- **Cost.** This is a lower bound from in-function time, not a reconciliation. Billing verification (R2.14(b)) still
  needs the provider's billing record (Cost Explorer or the cost and usage report for 22 Nov 2026 UTC).

**Not available from the saved files:**
- per-request Init Duration, Billed Duration and Max Memory Used, lost when teardown deleted the log groups after the
  failed collection;
- provisioned-concurrency activation lag and overflow, because no provisioned concurrency was requested or applied;
- the bill.
