# TR4. AWS Lambda measurements used in the replies (21-22 Nov 2026, us-east-2)

**Sources:** memcal-1 `prism-repro/docs/revision/aws_memcal_20261122/` (RESULTS.md; tables/timings.csv, block = all) and the
live integration run `prism-repro/docs/revision/aws_live_integration/` (tables/arms.csv, overhead.csv, memory_updates.csv).
**Scope:** synthetic four-stage document pipeline; functions do no application start-up work; on demand; at most 8 in
flight; laptop client; memcal-1 = 20,992 calibration invocations (1,312 per stage and size; 4,992 forced cold starts)
plus a 256-invocation smoke run, three blocks on one afternoon (day-to-day variation not measured).

**Warm Lambda Duration, median (ms), and cold-start quantities per stage:**

| Stage | 512 MB | 1024 MB | 2048 MB | 3008 MB | Init Duration median, range over sizes (ms) | Client first-call penalty median, range (ms) |
|---|---|---|---|---|---|---|
| ingest | 1,624.3 | 800.9 | 463.0 | 462.9 | 114.0-115.0 | 226-232 |
| transform | 8,038.9 | 3,993.6 | 2,291.6 | 2,286.8 | 113.7-116.0 | 236-258 |
| aggregate | 5,092.5 | 2,529.5 | 1,451.3 | 1,451.1 | 114.2-115.6 | 309-513 |
| load | 2,453.3 | 1,205.3 | 689.0 | 688.4 | 114.1-115.7 | 229-240 |

Init Duration 5th-95th percentiles across the 16 cells: 94.7-136.6 ms. The client penalty adds
environment creation, the network and first-call execution to the platform's Init Duration.

**Live integration run (21 Nov 2026; 40 records per arm; 14.5 s per-record deadline):**

| Quantity | Value |
|---|---|
| Records meeting 14.5 s: OnDemand at fixed 1024 MB / fixed memory schedule incl. 512 MB | 39 of 40 / 29 of 40 |
| Peak pipelines in flight (client cap 8): OnDemand / schedule arm | 5 / 8 |
| End-to-end p50 / p95, OnDemand arm (s) | 9.08 / 12.33 |
| Shared memory-size change across four functions (s), three changes | 3.27-3.33 |
| Stage transition, warm next stage, median (ms) | 23-27 |
| Stage transition, cold next stage, median (ms) | 250-260 |
| Configuration updates (memcal-1, environment variable only; 1 s polling) | 20 rows of block x memory summaries |
