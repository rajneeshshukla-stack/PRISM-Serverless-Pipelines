# Deployable four-stage PRISM pipeline (R6.1, R2.20, R4.5, R2.2, R6.2, R2.8)

**Prepared 21 Nov 2026. It has not been deployed: no AWS resource has been created and nothing has been charged.**
The real-AWS path has never run against AWS.

## Read first: what is not settled

1. **The workload is a proposal, not the paper's application.** The paper specifies the stages' timing and the
   controller interface, not what the stages compute, their data, services or code (`SPEC.md`). The handlers
   implement a **proposed** synchronous document-ingestion pipeline (from E8 / R4.5), pending author decision P1;
   decisions P1-P9 are listed in `SPEC.md`.
2. **Calibration sets how heavy the work is.** The stage times are set by the paper's warm means through K, a
   multiplier with no meaning of its own. Measured warm times at 1024 MB therefore reproduce the targets by
   construction. What is measured is everything else: scaling across memory sizes, cold starts, orchestration
   transitions, and billing.
3. **Start-up work is the platform's own.** With `PRISM_INIT_ROWS = 0` (P3) the cold start is the platform's plus
   the standard library's, which is expected to be far below the paper's assumed 6 s mean (not measured).
4. **Provisioned concurrency cannot be applied** at the account's quota of 10. The adapter records the requested
   levels and applies only memory.
5. **The smallest live test does not run PRISM's own decisions.** It runs a fixed memory schedule through the adapter
   against an OnDemand baseline. PRISM's controller through the adapter is tested locally only (`LIVE_TEST.md`).
6. **Prices are unverified** list prices (`prism_pipeline/estimate.py`).
7. **The manuscript itself was not read** in this pass; it is not in the repository (`SPEC.md`, Sources).
8. **Platform.** All local checks ran on one Windows 11 host with Python 3.12.9. Their timings are host timings
   under fakes, not AWS measurements.

## Layout

| Path | What |
|---|---|
| `SPEC.md` | what the paper specifies, the proposed workload stage by stage, and the author decisions P1-P9 |
| `LIVE_TEST.md` | the smallest live test in us-east-2: design, cost, duration, permissions, commands, stop conditions, scoped cleanup |
| `handlers/docpipe.py` | the four stage handlers (one package, entry points ingest/transform/aggregate/load; standard library) |
| `prism_pipeline/asl.py` | Express state machine (4 Task states, no Retry, logging off) |
| `prism_pipeline/driver.py` | open-loop record driver; Step Functions and client-chain executors; cap 8 in flight; one JSONL line per record |
| `prism_pipeline/adapter.py` | PRISM controller to deployment: live telemetry (no lookahead), epoch timing, memory actuation, provisioned concurrency record-only |
| `prism_pipeline/campaign.py` | calibration, forced-cold reset, one arm (driver plus adapter) |
| `prism_pipeline/aws.py` | preflight, deploy, collect REPORT lines, teardown, verify; plan-only unless authorised; scoped by prefix and tag |
| `prism_pipeline/analyse.py` | request-ID join, deadline outcomes, per-stage and e2e timing, cold starts, transition gaps, decisions, paired arms, billing |
| `prism_pipeline/estimate.py` | cost and duration of the smallest live test, every assumption listed |
| `prism_pipeline/livetest.py` | the whole live test as one sequence, teardown in `finally` |
| `prism_pipeline/fake.py`, `selftest.py` | in-process fakes running the real handler code; end-to-end self-test |
| `tests/test_pipeline.py` | 29 local tests (sockets blocked, no boto3) |
| `tests/check_botocore_shapes.py` | offline check of every AWS request against botocore's service models |
| `validation/prep_20261121/` | saved plan, estimate, state machine, test listing, self-test and botocore-check summaries |

**Reused from the measurement harness (`../aws_measurement`):**
- the authorisation guard (`PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES`);
- the REPORT-line parser and its test-fixture format;
- the 8-in-flight cap;
- the forced-cold nonce;
- the "no silent retry" rule.

**Not changed:**
- `src/`, Eq. (3), the controller and the simulator: the adapter calls them read-only;
- the manuscript, the notes and the workbooks;
- `results/` and `CHECKSUMS.sha256`;
- the harness itself.

## Local validation (no AWS)

```
cd prism-repro/aws_pipeline
../venv/Scripts/python -m unittest discover -s tests -v          # 29 tests, about 20 s
../venv/Scripts/python -m prism_pipeline selftest --out <new dir> # whole live-test sequence on fakes
../venv/Scripts/python tests/check_botocore_shapes.py <new dir>   # request shapes, offline
../venv/Scripts/python -m prism_pipeline plan                     # every AWS call, printed only
../venv/Scripts/python -m prism_pipeline estimate
```

**Results of 21 Nov 2026 (`validation/prep_20261121/`):**

- **Unit tests.** 29 of 29 pass. The suite was run three times, and passed each time. The measurement harness's 33
  tests still pass.
- **Self-test on the fakes.** The whole sequence ran against the fakes: deploy, calibrate, smoke, both arms, collect,
  analyse, teardown. All 25 checks pass:
  - every record was logged;
  - request IDs were complete and unique, and every REPORT was joined;
  - every cold start had an Init Duration;
  - a decision was taken every epoch;
  - memory changed exactly as scheduled (3 changes), with cold starts after each change;
  - the baseline ran at 1024 MB only;
  - both arms ran the same 16 records;
  - nothing was left after teardown.

  Deadline outcomes in the self-test are host timings under scaled targets. They show the bookkeeping works, not any
  timing.
- **Offline botocore check.** All 26 distinct API operations the live test uses passed botocore 1.44.9's request
  validation for us-east-2, with no request sent. A deliberately wrong parameter was rejected. This checks request
  names and types only. It does not check:
  - AWS's responses (those came from the fakes);
  - IAM propagation, permissions or service limits;
  - Lambda's real timings.

## What an author decision would change

- **P1 with real stage code:** replace `handlers/docpipe.py` (same envelope and trace contract) and drop the PROPOSED
  label. The rest stays.
- **P3:** set `PRISM_INIT_ROWS` at deploy.
- **P4:** add an S3 sink. This needs a bucket, IAM rights and teardown support, none of which is built yet.
- **P5 and P6:** a PRISM-controlled live run. Use `PolicyController` with a bundle, `trace_stream` over
  `thinned_counts`, `count_scale = 1/thin`, `pc_scale = thin` and `bin_s = 60`. The run takes hours.
