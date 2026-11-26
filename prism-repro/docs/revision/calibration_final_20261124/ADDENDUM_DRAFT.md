# DRAFT: calibration addendum to docs/revision/PRESPECIFICATION.md (not applied; for the author)

*This is a separate, dated note. `PRESPECIFICATION.md` itself is not edited. It takes effect only when the author
adopts it, before any calibrated confirmatory run.*

**Date:** [to be set when adopted]. **Prepared:** 24 Nov 2026.

**What the prespecification already says.** It defines C1-C3 on seeds 106-130 with the `PipelineConfig()` and
`PrismConfig()` defaults at a10efe6. It states that "every result produced under this prespecification is
pre-calibration and supersedes at recalibration; the comparisons are rerun unchanged, under this same file, when
measured constants replace the assumed ones."

**What this addendum changes:**
1. **Execution-time scaling.**
   - The single-share form of Eq. (2) (`nonscaling` = 0.5) is replaced by per-size, per-stage factors relative to 1024
     MB: `exec_scaling` = "measured" with `exec_factor_measured` from `docs/revision/calibration_20261124/exec_factor_measured.json`.
   - The factors were fitted on the memcal-1 FIT split only, and checked on its prespecified CHECK split.
   - **This is a change of model form,** recorded as such. No single `nonscaling` value reproduces the measurements:
     Eq. (2) fails held-out in 16 of 16 cells, while the per-size factors pass within block repeatability in 16 of 16.
2. **Unchanged:**
   - the policies;
   - seeds 106-130;
   - the scenarios;
   - the validation rule and edge expansion;
   - the tests and decision rules (tie margin +/-2%, comparability band +/-0.5 points);
   - every other constant.

**Inputs still assumed,** so the rerun is labelled PARTIALLY CALIBRATED:
- application start-up, 6 s, σ 0.30, memory-independent (P3);
- activation lag, 2 min;
- keep-alive, 10 min;
- orchestration overhead, 0.1 s per stage;
- independent per-stage execution spread, σ 0.30 (P2; see DECISIONS.md section 2);
- list prices.

**Selection safeguard.**
- No value in this addendum was chosen using seeds 106-130 or any test-week outcome.
- The development checks that informed it used traces 101-105 only (`docs/revision/calibration_final_20261124/`).

**Open items to settle before adoption:**
- P2's common-versus-independent execution spread;
- P3's start-up value and the 10 s handling (DECISIONS.md section 3);
- the activation lag, if measured by the R6.1 run.

*Dated note, 25 Nov 2026: superseded by `../p2_dependence_20261124/ADDENDUM_DRAFT.md` (v2), which adds the proposed P2
dependence parameter (ρ = 0.998 for the document pipeline, ρ = 0 as a sensitivity). This v1 text is kept as written.*
