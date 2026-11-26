# Which simulator inputs the saved AWS measurements support (24 Nov 2026; R1.1, R1.2, R2.8(b), R4.3, R4.8, R5.M2, R7.5)

No AWS call and no simulation. This audit maps each `PipelineConfig()` constant to the saved measurements:
- `../aws_memcal_20261122/RESULTS.md` and `tables/` (memcal-1: on demand, us-east-2, the declared synthetic docpipe-1
  workload, at most 8 in flight, one reference document, one afternoon);
- `../aws_live_integration/RESULTS.md` (one fixed-schedule run, 40 records per arm).

It states what a calibrated run still needs. **No constant was changed.**

## 1. Two different "initialisation" quantities

| Quantity | What it is | Measured? |
|---|---|---|
| **Lambda Init Duration (I)** | The platform INIT phase: runtime start and module import. Reported in REPORT lines | Yes: 0.114-0.116 s at every size. Flat in memory (slope +0.005 [+0.001, +0.008], pooled) |
| **First-call penalty (P)** | Cold minus warm end-to-end at the client: I, plus first-call work inside Duration (X), plus environment creation and the network (R) | Yes: 0.23-0.25 s, and 0.31-0.51 s for aggregate, whose X is CPU-bound. Pooled slope −0.116, against Eq. (3)'s −0.273 |
| **Application start-up** | The application's own initialisation work (loading models or indexes, opening connections). The simulator's `init_mean_1024` = 6 s and its log-normal stand for this, as occupancy before service | **No.** The workload did no start-up work (`INIT_ROWS = 0`, decision P3), so the 6 s is neither tested nor contradicted |

Lambda's INIT phase (I) is part of what an application's start-up costs, not the whole of it. The measured 115 ms
supports the platform part only. Setting `init_mean_1024` to 0.115 s would model an application with no start-up
work. That is a different study, not a calibration of the submitted one.

## 2. Constant by constant

| Constant (default) | Saved evidence | Status | Needed for a calibrated run |
|---|---|---|---|
| `warm_mean_1024` (0.8, 4.0, 2.5, 1.2 s) | Warm Duration at 1024 MB: 0.801, 3.994, 2.530, 1.205 s | **Matched by construction.** The work units K were frozen so that 1024 MB reproduces Table S1, so this agreement is not independent evidence | None for the declared workload. It is the definition of that workload |
| `nonscaling` 0.5 (Eq. (2), memory scaling of execution time) | Duration halves from 512 to 1024 MB, is 1.73-1.75x faster at 2048 MB, and is no faster at 3008 MB (one-vCPU plateau). The Eq. (2) fit gives a share of 0.22-0.23 and **fails held-out at all 16 cells** | **Contradicted in form.** Eq. (2) cannot represent the plateau | A per-size table, not a share. `stage_means` needs a "measured" mode for execution time, analogous to `init_mean_measured`. That is a code change, not yet made |
| `exec_shape` 0.30 (σ of log execution time) | With one fixed document, warm σ_log is about 0.01-0.13 (from p05/p95). That is run-to-run noise only | **Not testable** with these data. The 0.30 stands for input-size variation, and the campaign used one document | An input-size distribution for the declared workload (author decision P4), or a measurement with varied documents |
| `overhead_mean` 0.1 s per stage | Step Functions stage-to-stage transition 23-27 ms (live integration, warm next stage) | **Partly supported.** The measured transition is a quarter of the assumption; the client's network is excluded | A choice of whether `overhead` models the orchestrator only (then about 0.025 s) or orchestrator plus client |
| `init_mean_1024` 6.0 s, `init_shape` 0.30, Eq. (3) (`init_scaling` "eq3", `init_nonscaling` 0.7) | I flat at 0.115 s; P 0.23-0.51 s; Eq. (3)'s shape holds only where first-call work is CPU-bound (aggregate) | **Direction supported for I (constant), magnitude untested** (section 1) | **Decision P3:** what start-up work the declared application does. Then either measure it on AWS, or declare a value and its scaling (`init_scaling` "constant" or "measured") |
| `init_max_s` None (R4.8 truncation at 10 s) | Lambda's INIT limit is documented. I is far below it | **Ready to enable** (code and gate exist). Its effect depends on the P3 start-up distribution | Enable together with the P3 decision, because it moves every risk table |
| `lag_min` 2 (provisioned-concurrency activation) | Not measured. AWS documents "a minute or two of preparation". Configuration-update API calls complete in 1.53-2.20 s, but that is not activation | **Untested** | The R6.1 live run's readiness polling (activation lags, about 9 observations at 10-s resolution) |
| `keepalive_min` 10 (on-demand environment retention) | Not measured. AWS states no rule | **Untested** | A designed idle-gap measurement on AWS, or keep it as a stated assumption |
| `peak_upper_frac`, `intensity_sigma` (arrival model) | Not AWS quantities: workload-model parameters | Not applicable | None |
| Overflow and burst behaviour (on-demand scaling beyond 8 in flight) | Not measured: the campaign capped at 8 | **Untested** | The R6.1 run, or a separate burst test |
| Prices (`Prices`) | Verified against the public pricing pages; the billing rules were checked on 21,248 REPORT records (R2.14) | **Supported** (list prices; the actual bill is still open) | None for list-price modelling |

## 3. What a calibrated rerun needs, in order

1. **P3:** the declared application's start-up work. It sets `init_mean_1024`, `init_shape` and `init_scaling`, and
   with them whether `init_max_s` = 10 binds.
2. **A per-size execution-time mode,** replacing the Eq. (2) share. This is a small code change with a test; the
   measured table is in `../aws_memcal_20261122/tables/timings.csv`.
3. **P4:** the input-size distribution, which gives `exec_shape`.
4. **The activation lag and overflow** from the R6.1 live run (AWS pass).
5. Only then a full rerun. Before 1-4 are settled, a "calibrated" rerun would have to be repeated.

## 4. R1.1: the safety margin

**Kept.** The verified finding stays within its tested scope (`../margin_r11_fresh_20261124/`): a 10% margin on every
stage's provisioned concurrency, for PRISM configurations whose validation-selected eps is at most 0.02. It met 2% in
20 of 20 fresh weeks at +6.1% cost (event level, open loop, pre-calibration).

**Not pursued:** the 50% branch (eps >= 0.03). Reviewer 1 asks to "recommend an operator safety margin"; the
recommendation can be stated with its scope (eps <= 0.02), and the branch is rare under the tuning (1 of 5
development and 2 of 30 fresh traces). Pursue it only if the paper keeps a general margin claim. That would need a new
validation-only selection plan fixed before any test outcome is seen, on traces not yet used.

**A production margin** still depends on items 1-4 above and on the live run.

*Correction, 24 Nov 2026 (calibration pass, `../calibration_20261124/DECISION_RECORD.md`): in `aws_pipeline/SPEC.md` the input-size distribution is decision **P2**, not P4; P4 is the data source and sink. Every "P4 (input sizes)" above means P2.*
