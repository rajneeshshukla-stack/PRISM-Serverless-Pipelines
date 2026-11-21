# Quota-10 on-demand measurement harness (R1.2, R2.8, R3.1, R4.3, R5.M2, R6.2)

**Prepared 21 Nov 2026. It has not been run on AWS: no resource has been created and nothing has been charged.**
It implements `docs/revision/init_vs_memory/MEASUREMENT_PLAN.md`. The simulator, Eq. (3), the manuscript and the
tracker workbooks are unchanged; nothing here imports from them except a read-only use of
`prism_repro.latency.init_factor` (for Eq. (3)'s slope) and `prism_repro.config.Prices`.

## The stage workloads are PROXIES

The plan asks for PRISM's own four stages. The repository defines them only statistically:

| Specified (`prism_repro/config.py`) | Value |
|---|---|
| Names | ingest, transform, aggregate, load (`STAGES`) |
| Warm execution time | log-normal, mean 0.8 / 4.0 / 2.5 / 1.2 s at 1024 MB (`warm_mean_1024`), shape 0.30 (`exec_shape`) |
| Memory scaling of warm time | Eq. (2), non-scaling share 0.5 (`nonscaling`) |
| Per-stage overhead | 0.1 s, shape 0.30 |
| Initialisation | one stage-independent log-normal, mean 6 s at 1024 MB, Eq. (3) scaling (decision D03: "initialisation time does not depend on the stage") |
| Memory sizes | 512, 1024, 2048, 3008 MB |

**Missing for every stage**, so no real handler can be written:

- what the stage computes;
- its input and output records and payload sizes;
- the services it reads or writes (storage, queues, databases);
- its dependencies and deployment package size;
- runtime and language;
- what runs at module scope versus per invocation (the start-up work that decides what Eq. (3) represents);
- whether the work is single- or multi-threaded, CPU- or I/O-bound.

Even the application is unnamed (R4.5 asks the paper to name one). The real stages are therefore **underspecified**,
and the harness uses labelled proxies instead (`handlers/stage_proxy.py`; every response carries
`"label": "PROXY WORKLOAD ..."`):

- **Stage proxies (main cells):** deterministic single-threaded CPU work (a SHA-256 chain). It is calibrated on AWS
  so that each proxy's warm time at 1024 MB equals the stage's specified mean. The work is fixed across memory sizes,
  so the measured durations show Lambda's own CPU scaling. The proxies do no start-up work, so their cold penalty is
  the platform's: an empty handler's reported init plus environment creation.
- **Init-placement proxies (init cells):**
  - `init_module` puts 2 s (at 1024 MB) of CPU start-up work at module scope, inside Lambda's reported INIT phase.
  - `init_first_call` puts the same work in the first invocation, inside `Duration`.
  - Since the real placement is unknown, the two bracket it and show which Lambda field each lands in.

**What the proxies can and cannot establish:**

- **Can:** Lambda's reported init versus memory, environment-creation time, how CPU-bound start-up work is accounted
  for and scales, CPU-bound warm scaling, and billing fields, all at the quota.
- **Cannot:**
  - the warm-time *distribution* of PRISM's stages (a deterministic proxy has none of its own);
  - the I/O share of the stages;
  - PRISM's real start-up placement.

So Eq. (3) can be grounded for each placement, but choosing the placement that represents PRISM is an author decision,
unless real stage code is supplied. If it is, replace the handler, keep the harness, and drop the proxy labels.

## What it measures (per cell: group x variant x memory)

From the client (synchronous invoke, `LogType=Tail`) and Lambda's REPORT line, joined by request ID:

- `I` = median Init Duration (Lambda-reported initialisation).
- `P` = median cold end-to-end time minus median warm end-to-end time (the full first-call penalty).
- `X` = median cold Duration minus median warm Duration (first-invocation excess inside the handler).
- `R = P - I - X` (environment creation and anything Lambda does not report).
- `P_mean`, the candidate for `init_mean_measured`.
- Billed Duration, Memory Size and Max Memory Used, giving GB-seconds and requests.

**How cold/warm is decided:** it is observed, not assumed. The handler reports a new environment on its first call,
and the presence of `Init Duration` cross-checks it.

**Uncertainty and trends:** a bootstrap over batches gives the uncertainty. Each trend is the slope of log quantity on
log memory, compared with Eq. (3)'s slope over the same sizes (-0.273 over 512-3008 MB).

**The decision rule** is the plan's, applied to `P`. It refuses to decide when any cell has fewer than 25 cold or warm
batches, and it flags cells with fewer than 200 cold invocations carrying an Init Duration.

## Layout

| Path | What |
|---|---|
| `handlers/stage_proxy.py` | Lambda handler (standard library only; prints nothing so the log tail is REPORT-only) |
| `prism_measure/design.py` | cells, randomised blocks and visits, batches; cap `CAP_MAX = 8` (quota 10, headroom 2) |
| `prism_measure/runner.py` | executes a design: retire warm environments, cold batch released by a barrier, warm batches; semaphore cap; resumable JSONL |
| `prism_measure/report.py` | REPORT line and log-tail parser |
| `prism_measure/analyse.py` | request-ID join, missing-field accounting, I/P/X/R, trends, decision rule, billing |
| `prism_measure/fake.py`, `dryrun.py` | in-process fake Lambda/CloudWatch with known ground truth; dry runs with sockets blocked |
| `prism_measure/estimate.py` | runtime and cost estimate with every assumption listed |
| `prism_measure/aws.py` | deploy / calibrate / collect / teardown, plan-only unless authorised (see `RUNBOOK.md`) |
| `tests/test_harness.py`, `tests/fixtures/` | 33 local tests; the fixture has hand-computed answers |
| `validation/dry_run_20261121-172542/` | saved dry-run checks, design and estimate |

## Local validation (no AWS)

```
cd prism-repro/aws_measurement
../venv/Scripts/python -m unittest discover -s tests -v     # 33 tests, about 12 s, sockets blocked
../venv/Scripts/python -m prism_measure dry-run --mode full  --out <new dir>
../venv/Scripts/python -m prism_measure dry-run --mode timed --out <new dir>
```

Results of 21 Nov 2026 are in `validation/dry_run_20261121-172542/`.

**Full plan** (23,168 invocations, 696 visits):
- Every planned invocation was recorded.
- No throttling.
- 416 REPORT lines removed from log tails on purpose were all recovered through the CloudWatch fallback.
- 11 cold REPORTs missing Init Duration were flagged.

**Timed** (reduced design, real overlapping threads):
- Peak in flight was 8 with a cap of 8.
- No unexpected warm in a cold batch.
- I and X were recovered to the REPORT precision (1e-5 s); P and R within thread jitter.

The full mode's instant fake produces many reused environments inside cold batches (its calls do not overlap). The
join flags and excludes them correctly, which is the behaviour a real run needs if a cold batch fails to overlap.
