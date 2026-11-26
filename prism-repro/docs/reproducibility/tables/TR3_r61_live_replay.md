# TR3. R6.1 paired live replay on AWS (25 Nov 2026, us-east-2): record-level outcomes and actuation

**Source:** `prism-repro/docs/revision/r61_live_run_20261125/r61_results.json` (aggregates; raw run folder private, hashes in
`raw_sources.sha256`); final cleanup `final_verify_CLEAN_20261125T050534Z.txt`. **Configuration:** PRISM's frozen
controller (checkout 92e3e68, eps 0.02, gbm forecaster) against OnDemand, one thinned trace-week (trace 101, stationary,
test week; 323 records per arm; 8 five-minute epochs); synthetic four-stage document pipeline on AWS Lambda and Step
Functions Express. **Metric:** RECORD-LEVEL deadline outcomes at 14.5 s (not the simulator's window-level SLA: 2
fifteen-minute windows per arm, too few to estimate it).

| Quantity | PRISM arm | OnDemand arm | Unit / denominator |
|---|---|---|---|
| Records per arm (identical inputs) | 323 | 323 | records |
| Met the 14.5 s per-record deadline | 313 of 323 | 314 of 323 | records (end to end, client clock) |
| Paired: met in both / missed only under PRISM / missed in both | 313 / 1 / 9 | (same) | records |
| Fully warm 1024 MB records missing the deadline | 9 of 313 (2.88%, 95% CI 1.32-5.39) | 8 of 314 (2.55%, 95% CI 1.11-4.96) | records with 4 warm stages at 1024 MB (denominator) |
| End-to-end p50 / p95 / p99 / max | 8.529 / 13.471 / 16.739 / 19.906 | 8.551 / 13.587 / 16.718 / 20.019 | s |
| Records with >= 1 cold stage | 10 | 9 | records |
| Stage executions served by provisioned concurrency (ingest/transform/aggregate/load) | 291 / 288 / 259 / 274 | 0 (on demand) | of 323 per stage |
| Memory applied = requested | 1024 MB in 8 of 8 decisions | 1024 MB (fixed) | decision epochs (5 min) |
| Provisioned-concurrency READY first observed (polling every 10 s) | 82.8 s after the initial allocation (1/2/2/1 units); 20.1 s after a later change | n/a | two observations from one replay |
| Lambda REPORT records matched to stage executions | 2596 of 2596 (2,584 replay + 12 smoke), 0 missing | (shared) | REPORT records |
| Harness cost estimate (UNVERIFIED list prices; excludes provisioned concurrency) | USD 0.100 for both arms | (shared) | USD, not a bill |

Not measured: burst overflow, application start-up, memory sizes other than 1024 MB, the window-level SLA, actual
charges (TR5). The fully warm miss rates contradict the frozen model's 0.22% prediction and fit the shared-stage model
(about 3.3%); cross-stage dependence re-estimated on 314 new documents: total correlation 0.996 [0.995, 0.997].
