# Calibration decisions adopted by the author (25 Nov 2026)

The author approved these in the session of 25 Nov 2026, after the R6.1 live run, choosing among the stated
alternatives. `PRESPECIFICATION.md`, the manuscript, the submitted outputs and the pinned R6.1 harness are unchanged.
The dated note that records them is `ADDENDUM.md` in this folder.

| ID | Decision adopted | Alternatives offered | Evidence |
|---|---|---|---|
| **P1** | The synchronous four-stage synthetic document pipeline (`handlers/docpipe.py`) is the calibration scope. | Approve P1 only; neither | `../calibration_final_20261124/DECISIONS.md` section 1 |
| **P2-DEP** | Cross-stage execution dependence ρ = **0.998** is primary for this document pipeline; **ρ = 0** (independent stages, the frozen form) is reported as a sensitivity. | ρ = 0 primary; defer | `../p2_dependence_20261124/` (34 records); replicated in `../r61_live_run_20261125/` (0.996 on 314 new documents; fully warm misses 2.55% and 2.88% against 0.22% predicted by ρ = 0) |
| **P3** | Start-up: 6 s mean, σ 0.30, memory-independent, a declared scenario that already includes the measured ~0.115 s platform initialisation. **The modelled application is declared to start within 10 s.** The untruncated 6 s model is reported as a sensitivity. | Model timeout and retry; untruncated as primary | `../calibration_final_20261124/DECISIONS.md` section 3 |
| **D-CAL-1** | The per-size, per-stage execution factors from memcal-1 (`../calibration_20261124/exec_factor_measured.json`) replace the form of Eq. (2); recorded as an explicit change of model form. | Approve P1 only (Eq. (2) primary); neither | `../calibration_20261124/` |
| **Lag** | Activation lag stays at the assumed 2 min. R6.1 measured 82.8 s and 20.1 s (2 events, 10 s polling); both are within 2 min, too few to re-centre. | Re-centre on about 1.4 min | `../r61_live_run_20261125/README.md` |

**Unchanged:**
- P9 (compare live results on AWS-side time);
- R2.11 (one shared calibration offset);
- D3 (no warm-up of the conformal offset);
- keep-alive 10 min;
- overhead 0.1 s per stage;
- σ 0.30 (the declared document-size mix);
- list prices;
- the policies, grids, validation rule and edge expansion;
- seeds 106-130 and the test and decision rules.

**How each decision maps to configuration:** existing opt-in fields in the isolated calibration build; the code
defaults stay the frozen model.

| Decision | Configuration |
|---|---|
| D-CAL-1 | `exec_scaling = "measured"`, `exec_factor_measured = <memcal-1 FIT factors>` |
| P2-DEP | `exec_common_frac = 0.998` |
| P3 | `init_max_s = 10.0`: the existing R4.8 mapping onto the log-normal truncated at 10 s (monotone, so common random numbers are preserved). Here it represents the declared start-up bound, not an AWS cap. |
| Lag | `lag_min = 2` (the default) |
