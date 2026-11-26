# Calibration addendum to docs/revision/PRESPECIFICATION.md (ADOPTED 25 Nov 2026)

*Adopted text of `../p2_dependence_20261124/ADDENDUM_DRAFT.md` (v2), with the author's decisions of 25 Nov 2026
(`ADOPTED_DECISIONS.md`) filled in. It is a separate, dated note; `PRESPECIFICATION.md` is not edited. The drafts v1
and v2 stay as written.*

**Date adopted:** 25 Nov 2026. **Prepared:** 24-25 Nov 2026.

**What the prespecification already says.**
- It defines C1-C3 on seeds 106-130 with the `PipelineConfig()` and `PrismConfig()` defaults at a10efe6.
- It states that "every result produced under this prespecification is pre-calibration and supersedes at recalibration;
  the comparisons are rerun unchanged, under this same file, when measured constants replace the assumed ones."

## Changes

### 1. Execution-time scaling with memory: a per-size lookup (as v1)

- The single-share form of Eq. (2) (`nonscaling` = 0.5) is replaced by per-size, per-stage factors relative to 1024 MB:
  `exec_scaling` = "measured" with `exec_factor_measured` from `docs/revision/calibration_20261124/exec_factor_measured.json`.
- **Where the factors come from:**
  - fitted on the memcal-1 FIT split only;
  - checked on its prespecified CHECK split.
- **This is a change of model form, recorded as such.** No single `nonscaling` value reproduces the measurements:
  Eq. (2) fails held-out in 16 of 16 cells, while the per-size factors pass within block repeatability in 16 of 16.

### 2. Execution-time dependence across stages (P2): adopted

**The change.**
- The four per-stage execution multipliers of a request stop being independent.
- Each stage's log multiplier becomes σ(√ρ·z_request + √(1−ρ)·z_stage) − σ²/2, with σ = 0.30 unchanged.
- `exec_common_frac` = ρ.
- Every marginal is unchanged (mean one, σ_log 0.30).
- It applies wherever execution multipliers are drawn: the event-level world, the fast-simulator draws, and PRISM's
  attainment and miss tables. So the controller's planning model and the simulated world agree.

**Adopted value for the calibration scope (P1, the document pipeline):** ρ = 0.998 (primary).
- Measured on AWS: in the live integration run of 21 Nov 2026, document size explains 99.3-99.9% of each stage's
  warm-time variance at 1024 MB (34 records).
- The stage-specific remainder (σ_log about 0.014) is nearly uncorrelated across stages.
- Source: `docs/revision/p2_dependence_20261124/DATA_AUDIT.md`.
- **Measured:** ρ, and the stage-specific residual.
- **Declared:** σ = 0.30 (the P2 size mix, SPEC P2).

**Sensitivity reported alongside:** ρ = 0 (the frozen form). It stands for an application whose stages respond to
unrelated inputs.

**Why the choice matters.** It changes the warm per-record miss probability, and hence feasibility, at the default
deadline: v_w(1024 MB, 14.5 s) is 0.22% at ρ = 0 and 3.28% at ρ = 0.998.

**What does not change:** the code default stays ρ = 0, so the submitted results and the frozen C1-C3 code path are
bit-identical. ρ is set by configuration, as `exec_scaling` is.

### 3. Unchanged

- the policies;
- seeds 106-130;
- the scenarios;
- the validation rule and edge expansion;
- the tests and decision rules (tie margin +/-2%, comparability band +/-0.5 points);
- every other constant.

## Inputs still assumed (the rerun is labelled PARTIALLY CALIBRATED)

- **Application start-up: 6 s, σ 0.30, memory-independent (P3).**
  - This is the *total* cold-start occupancy and already includes the platform initialisation measured at about 115 ms
    (flat in memory). Nothing is added for it.
  - Lambda's documented 10 s Init limit applies to on-demand initialisation. When it is exceeded, the Init phase is
    retried at the first invocation under the function timeout.
  - It is not a universal cap and does not apply to provisioned concurrency.
  - Adopted (25 Nov 2026): the modelled application is declared to start within 10 s, so start-up is drawn from the
    log-normal truncated at 10 s (`init_max_s` = 10). The bound is a property of the declared application, not an
    AWS limit. The untruncated model is reported as a sensitivity.
- activation lag, 2 min;
- keep-alive, 10 min;
- orchestration overhead, 0.1 s per stage;
- the marginal execution spread, σ 0.30 (declared document-size mix);
- list prices.

**Frozen choices kept:**
- R2.11: one shared calibration offset;
- D3: no warm-up of the conformal offset.

## Selection safeguard

- No value in this addendum was chosen using seeds 106-130 or any test-week outcome.
- The development checks that informed it used traces 101-105 only:
  - `docs/revision/calibration_final_20261124/`;
  - `docs/revision/p2_dependence_20261124/`.
- **ρ was chosen from the archived AWS measurements and the workload mechanism, before the closed-loop P2 outcomes were
  inspected** (RUN_PLAN.md, hashed 25 Nov 2026 00:43:59Z).

## Decisions settled at adoption (25 Nov 2026)

- **P2:** ρ = 0.998 primary for the document-pipeline scope; ρ = 0 reported as a sensitivity. Replicated by the R6.1
  live run (0.996 on 314 new documents; `docs/revision/r61_live_run_20261125/`).
- **P3:** the modelled application is declared to start within 10 s: `init_max_s` = 10 (the log-normal truncated at
  10 s), as a property of the declared application, not an AWS cap. The untruncated 6 s model is reported as a
  sensitivity.
- **D-CAL-1 and P1:** approved as stated in section 1 and in the scope above.
- **Activation lag:** stays at 2 min. The R6.1 run measured 82.8 s and 20.1 s (2 events), both within it.
