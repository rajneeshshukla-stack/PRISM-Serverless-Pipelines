# Constants used by the C1-C3 runs, what supports them, and what blocks a calibrated rerun

Written 22 Nov 2026, before the confirmatory runs started.

## Label

Every C1-C3 result in this folder is **PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION**.
- The runs use the `PipelineConfig()` and `PrismConfig()` defaults at a10efe6, as `../PRESPECIFICATION.md` section 1
  requires. `src/`, `experiments/` and `tests/` are unchanged since a10efe6: `git diff --stat a10efe6 HEAD` over those
  paths is empty, and each run's `environment.json` records the check.
- The prespecification reruns the same comparisons "unchanged, under this same file, when measured constants replace
  the assumed ones". No constant below was changed for these runs.
- C3 changes the deadline only: `deadline = 12.0`. Its `nonscaling = 0.5` equals the default.

## The constants and their support

**Abbreviations:** S1 is Supplementary Table S1 of the submitted manuscript. memcal-1 is
`../aws_memcal_20261122/RESULTS.md` (commit fd8b01a, plus the uncommitted `config_updates.csv` addition).

| Constant | Value in the runs | Support | What the AWS evidence says (pre-calibration labels kept) |
|---|---|---|---|
| `warm_mean_1024` (s, per stage) | 0.8, 4.0, 2.5, 1.2 | S1, assumed | memcal-1 sets its work units K so the 1024 MB warm times equal these, by construction. It therefore cannot validate them; it measures their scaling with memory. |
| `nonscaling` (Eq. (2)) | 0.5 | S1, assumed | **Missed its held-out check**: the Eq. (2) form fails in all 16 stage-memory cells, with errors from −10.1% to +13.1%. The fitted share, 0.22-0.23, cannot follow the plateau from 2048 to 3008 MB. No single value of `nonscaling` reproduces the measured scaling. |
| `exec_shape` (σ of log) | 0.30 | S1, ASSUMPTION D01 | Not measurable from memcal-1. It used one reference document, so warm CV was 0.013-0.092 by construction, not a workload spread. |
| `init_mean_1024` (s) | 6.0 | S1, assumed: application start-up | **Not comparable** with the measurement. Lambda-reported Init Duration for the synthetic deployment was 113.7-116.0 ms (median), with no application start-up work (`INIT_ROWS = 0`). The client-observed first-call penalty P was 0.23-0.51 s. Neither measures the modelled 6 s of application start-up. |
| `init_scaling`, `init_nonscaling` (Eq. (3)) | "eq3", 0.7 | §III-A, assumed | Lambda Init Duration is flat in memory: slope +0.001 to +0.008 against Eq. (3)'s −0.273. The Eq. (3) form fitted to I lands at the boundary `init_nonscaling = 1.0`. By the prespecified rule, the P trend is: pooled, "keep the direction, refit the non-scaling share"; ingest and transform, "constant"; aggregate, "keep Eq. (3)". |
| `init_shape`, `init_max_s` | 0.30, none | S1; R4.8 truncation built, not enabled | Platform Init never exceeded 0.36 s in 4,992 cold starts. The distribution of application start-up is unmeasured. |
| `overhead_mean`, `overhead_shape` | 0.1 s, 0.30 | S1, assumed | The live integration run measured Step Functions stage-to-stage gaps of 23-30 ms (median). memcal-1's client overhead, median 0.081 s, includes the wide-area network. Neither is the modelled per-stage overhead as such. |
| `lag_min` (activation lag) | 2 min | §III-B, assumed | **Not measured**: no provisioned concurrency was configured in any AWS run (D7). |
| `keepalive_min` | 10 | assumed | Not measured. |
| `mem_options` | 512, 1024, 2048, 3008 | design | The memory sizes memcal-1 measured. |
| `prices.od`, `prices.req` | 1.66667e-5 USD/GB-s, 2e-7 USD | §III-D | Equal to the public us-east-2 list prices retrieved 22 Nov 2026 (Lambda x86 duration and requests). |
| `prices.pc`, `prices.pcd` | 4.1667e-6, 9.7222e-6 | §III-D | **Not verified**: the provisioned-concurrency prices were not part of the verified price list. |
| `deadline`, `window_min`, `sla_eps`, `slo_violating_window_target` | 14.5 s (C3: 12 s), 15, 0.01, 0.02 | design (§III-C, §V) | Not platform constants. |
| `epoch_min`, `peak_upper_frac`, `intensity_sigma` | 5, 0.45, 0.148 | design; Eq. (14) | `peak_upper_frac` is the fast simulator's matched peak draw. The event-level simulator does not use it (R3.3; `README.md`). |
| `PrismConfig` | eps grid, gamma 0.05, kappa floor 0.1, hysteresis 0.85, Erlang-B risk model, ... | §IV, frozen defaults | Controller settings, not platform constants. |

## Held-out calibration misses and their effect

These come from memcal-1, `tables/heldout_check.csv`: 37 of 56 predictions fall inside the CHECK split's 95%
batch-bootstrap interval.

| Quantity and form | Result on the held-out visits | Effect on the proposed calibration |
|---|---|---|
| Warm Duration, Eq. (2) form | fails in all 16 cells | The single-term Eq. (2) cannot be calibrated to these data. A calibrated simulator needs either a different execution-scaling form (for example per-size measured means, as `init_mean_measured` already allows for initialisation) or a statement that Eq. (2) is kept as an assumption. **That is a model decision.** |
| Lambda Init I, Eq. (3) form | passes for ingest and aggregate; fails at one size each for transform (3008 MB) and load (1024 MB) | The form only fits as a constant, so `init_scaling = "constant"` is the candidate for the platform's part. The misses are about 1-2% of a 115 ms value, so they are small in absolute terms. |
| Lambda Init I, "measured" mode | passes for ingest, transform and load; fails at one size for aggregate (3008 MB) | As above. |
| P_mean (mean first-call penalty) | ingest passes (constant); not estimable for transform, aggregate, load and pooled (laptop stalls) | The mean-based quantity the simulator uses cannot be calibrated from these data for three stages. An in-region client or a rerun without stalls is needed. |

## What a calibrated rerun needs, and which jobs each item blocks

| Unresolved item | Decision or measurement needed | Calibrated jobs it blocks |
|---|---|---|
| **P3: how the simulator represents application start-up** (`init_mean_1024`, `init_shape`, `init_max_s`, whether Eq. (3) models I or P) | author decision, or a measurement of real stage start-up code | **every calibrated C1-C3 job**: initialisation enters every cold start of every family in every scenario |
| Execution scaling with memory (Eq. (2) fails its held-out check) | model decision: a plateau or per-size form (a code change, made under an addendum) or keep Eq. (2) as an assumption | **calibrated C3** (12 s deadline, where memory choice decides compliance), and PRISM's memory search in calibrated C1 and C2 |
| Activation lag (`lag_min`) | measurement with provisioned concurrency (D7; the adapter's `pc_mode = apply` is not built) | every calibrated C1-C3 job: the lag sets the forecast horizon and the conformal delay of every forecast-driven family and Reactive's response |
| Execution spread (`exec_shape`) | a workload with input-size spread (one reference document was measured) | every calibrated job |
| Provisioned-concurrency prices (`pc`, `pcd`) | price verification | every calibrated cost comparison involving provisioned capacity (all families except OnDemand) |

**What can run now:** the frozen-default (pre-calibration) C1-C3, which the prespecification explicitly allows and
labels. They run here.
