# Calibration decisions for the final evaluation (24 Nov 2026; recorded before the bounded Linux check)

**These are decisions for the author to confirm.** Nothing is applied to the pinned `src/` (3edc386, R6.1) or to
`docs/revision/PRESPECIFICATION.md`. The evaluation they define is **PARTIALLY CALIBRATED**: execution time is
calibrated, while start-up, activation lag, keep-alive, orchestration overhead and the arrival model stay declared
assumptions (section 7).

**Inputs:**
- `../calibration_20261124/` (calibration table, held-out checks, the opt-in mode, tests, smoke test);
- `aws_pipeline/SPEC.md` (P1-P9);
- `../aws_memcal_20261122/`;
- `../aws_live_integration/`;
- the AWS Lambda execution-environment documentation (read 24 Nov 2026);
- `p2_correlation_check.*` (this folder).

## 1. P1, workload: the synchronous four-stage synthetic document-ingestion pipeline (`handlers/docpipe.py`)

**Decision.** It is the scope of the AWS-based calibration. The calibrated factors describe this workload on
python3.12/x86_64 in us-east-2. They are not general Lambda constants.

**Where the simulated workload differs from the measured one:**

| Aspect | Simulator | Measured workload |
|---|---|---|
| Stage means at 1024 MB | Table S1 (0.8, 4.0, 2.5, 1.2 s) | Equal by construction: the work units K were fitted to them |
| Execution spread | independent log-normal per stage, σ 0.30 (D01) | one document's length drives all four stages (section 2) |
| Orchestration | 0.1 s per stage (σ 0.30) | Step Functions Express transitions of 23-30 ms, plus the client's network |
| Start-up | 6 s declared mean (section 3) | no start-up work: platform INIT about 0.115 s |
| Arrivals | synthetic traces at about 600 records/min | thinned, rescaled replays (P5), at most 8 in flight at the client |
| Client | none: arrival at stage 1 | a client that submits synchronously and may shed at its cap |

## 2. P2, input sizes: log-normal document length, mean 3,000 words, σ 0.30 (SPEC.md P2). Declared, not measured

**How the simulator reads it.**
- `exec_shape` = 0.30 is the σ of log of a mean-one multiplier: `lognormal_mult`, exp(σz − σ²/2).
- It is applied to each stage's mean execution time.
- The 3,000-word mean maps to the mean multiplier 1, because K was fitted on a reference document of the mean size,
  so handler time at 3,000 words equals the stage mean.
- The memcal-1 campaign used one document, so its spread (σ_log about 0.01-0.13) is platform jitter only. It neither
  supports nor contradicts 0.30.

**Unresolved: material.** The simulator draws the four multipliers **independently**. Under P2, one document's length
is **common** to all four stages. With the same marginal spread, the warm end-to-end miss probability v_w changes
(`p2_correlation_check.txt`; Monte Carlo, 400,000 draws):

| Model | Deadline | 1024 MB: independent / common | 2048 MB: independent / common |
|---|---|---|---|
| Eq. (2) | 14.5 s | 0.24% / 3.33% | 0.001% / 0.26% |
| Eq. (2) | 13 s | 1.18% / 7.17% | 0.009% / 0.75% |
| measured factors | 14.5 s | 0.24% / 3.33% | 0.000% / 0.010% |
| measured factors | 13 s | 1.18% / 7.17% | 0.000% / 0.044% |

Under the common reading, 1024 MB exceeds the 1% per-record allowance of a window **at the default 14.5 s**, so
memory would matter at the default deadline too.
- The live integration run is consistent with this: its baseline's one miss was a warm record on the run's largest
  document (5,951 words; `../aws_live_integration/RESULTS.md`). That is one observation.

**Alternatives:**
- (a) keep the simulator's independent spread, and state that the docpipe workload is represented only in its
  marginals;
- (b) give the docpipe handler independent per-stage work, which needs a change to the pinned harness after the R6.1
  run;
- (c) add an opt-in common-factor mode to the simulator.

**This pass keeps (a)**, the frozen model, for the bounded check, and does not decide. The choice must be made before
the calibrated C1-C3.

## 3. P3, start-up: keep 6 s as a declared application start-up scenario, memory-independent

**What the 6 s is.** It is the simulator's whole cold-start occupancy before service: one stage-independent
log-normal (SPEC.md row "Initialisation"). It therefore already contains whatever platform INIT a real application
has.

**The measured quantities stay separate and are not added to it:**
- Lambda Init Duration, 0.114-0.116 s, flat in memory;
- the client-observed first-call penalty, 0.23-0.51 s, which includes the network.

The measured 0.115 s is a lower bound on the start-up of an application that does no start-up work. It is not an
estimate of the 6 s.

**Direction:** "constant" in memory is a scenario assumption. The only measured part (platform INIT) is flat. A
CPU-bound start-up would scale like execution. Report Eq. (3) and the CPU-bound variant as sensitivities.

**The 10 s limit: correction.** AWS's documentation (lambda-runtime-environment.html, read 24 Nov 2026) says:
- "The Init phase is limited to 10 seconds. If all three tasks do not complete within 10 seconds, Lambda retries the
  Init phase at the time of the first function invocation with the configured function timeout."
- "The 10-second timeout doesn't apply to functions that are using provisioned concurrency, SnapStart, or Lambda
  Managed Instances."

So the limit is **not a cap on start-up time**:
- an on-demand start-up over 10 s fails once and is retried within the invocation, which makes it longer;
- provisioned environments may initialise for longer.

The R4.8 truncation (`init_max_s`) therefore does not represent AWS's behaviour, and must not be enabled as "the 10 s
limit". **Alternatives:**
- (a) leave start-up untruncated: about 3% of draws exceed 10 s at σ 0.30 and mean 6 s, and these are modelled as
  ordinary long starts;
- (b) model timeout-and-retry: 10 s plus a second Init;
- (c) declare start-up below 10 s as a property of the application.

**Recommendation:** (c) for the scenario, with (a) as a sensitivity. This corrects `../calibration_20261124/` (its
table and decision record said the cap is "supported").

## 4. P9, deadline clock

**Simulator** (`des.py`): a record's latency runs from its arrival at stage 1 to its completion after the last stage's
orchestration delay. It is the sum, over stages, of execution, any cold initialisation, and one orchestration delay
(0.1 s mean) per stage. There is no client, and no concurrency cap at submission.

**Live harness** (`prism_pipeline/driver.py`):
- `e2e_s` runs from the client's StartSyncExecution call to its response, on the client's monotonic clock, and adds
  the client's network and Step Functions' start and finish;
- records above the client cap of 8 are `shed_client_cap`, counted separately;
- `service_s` (AWS clocks) is also recorded.

**Decision:**
- keep the evaluation metric: per-record attainment of 14.5 s, with a 15-minute window violating when attainment is
  below 99%;
- compare live and simulated outcomes on `service_s` from an in-region client (SPEC.md P9's recommendation), or
  report the measured client overhead (memcal-1 median 0.081 s from the laptop) and the shed records alongside;
- client-observed and simulated SLA rates are not compared directly.

## 5. R2.11 and D3: keep the frozen choices for the main comparison

- R2.11: one shared conformal offset (`conformal_per_quantile` = False).
- D3: no warm-up (`conformal_warmup_days` = 0; `forecast_train_days` = 14).

The per-quantile calibration (R2.11 sweep) and the warm-up split (R4.6, R5.M3, PROVISIONAL) stay separate exploratory
analyses. Their outcomes do not feed any decision about the frozen evaluation.

## 6. Execution time against memory: the per-size table replaces Eq. (2)'s form (D-CAL-1)

**What changes.** This is an explicit change to the **form** of Eq. (2): the single `nonscaling` share is replaced by
a per-size, per-stage factor table relative to 1024 MB, fitted on memcal-1 FIT only (`exec_factor_measured.json`).

**Evidence:**
- held-out within the 0.41% block repeatability in 16/16 cells;
- factor errors <= 0.30%;
- Eq. (2) fails 16/16.

**Scope:** docpipe-1, python3.12/x86_64, us-east-2, 512-3008 MB only.

**Other sizes:** no other size is supported. The mode refuses them.

**How it is applied.** `ADDENDUM_DRAFT.md` drafts the dated note. The code change
(`../calibration_20261124/candidate_exec_measured.patch`) is applied only after the R6.1 live run, on a separate
calibrated build.

## 7. What the final evaluation will still assume

| Input | Status |
|---|---|
| Application start-up | 6 s, σ 0.30, memory-independent |
| Activation lag | 2 min, until the R6.1 readiness measurement |
| Keep-alive | 10 min |
| Orchestration overhead | 0.1 s per stage |
| Execution spread | independent per stage (section 2) |
| Arrivals | synthetic traces |
| Prices | list prices |

A run with these inputs is labelled **PARTIALLY CALIBRATED (execution time only)**.
