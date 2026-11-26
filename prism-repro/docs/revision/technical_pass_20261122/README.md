# Technical pass, 22 Nov 2026: R2.1, R2.18, R3.3, R4.2, R4.10, R4.11, R5.M4, R5.M7, R5.m4, R5.m5, R6.4, R6.5, R7.6

**Scope.**
- Branch `closed-loop`, HEAD 0316789. `src/`, `experiments/` and `tests/` are clean.
- One Windows 11 laptop: Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0 (`.venv-prism-pilot`).
- Baseline tracker: `PRISM_Tracker_dispositions_mc_discrepancy_verified_20261122-074745.xlsx` (0 Fixed, 37 Partially
  fixed, 35 Not fixed, 1 No change warranted). `notes/dispositions.md` matched it in all 73 rows.
- Seeds and simulations: development seeds 101-105 only, and the confirmatory seeds 106-130 were not run. No AWS call,
  no manuscript edit, no closed-loop or production-scale run.
- Labels: every simulation figure is PRE-CALIBRATION; the shifted-trigger check is EXPLORATORY (not prespecified).

**Files in this folder.**

| File | What | Reproduce (from `prism-repro/`) |
|---|---|---|
| `tests/unittest_closed_loop.txt` | 30 closed-loop, epoch-major and event-level tests: all pass, 128 s, 14:10-14:13 UTC. This is the first saved run of the closed-loop tests; the last full-suite record, `docs/TEST_REPORT.md` at 95163b2, predates them. | `python -m unittest tests.test_des_closed_loop tests.test_des_epoch_major_guard tests.test_des_online -v` |
| `trace_inventory.txt`, `verify_trace_inventory.py` | Development trace counts, 101-105 in all 5 scenarios, against `data/trace_set_revision.json`: 25 of 25 match; the manifest is unchanged since 4c43769. Seeds 106-130 are not generated. | `python docs/revision/technical_pass_20261122/verify_trace_inventory.py .` |
| `shifted_triggers/` | All nine families under the shifted-trigger scenario (R5.M4(b)) with the E1 tuning rule; 470 rows; `summary.txt` | `python scripts/revision/shifted_trigger_all_families.py . docs/revision/technical_pass_20261122/shifted_triggers --workers=3`, then `--analyse` |
| `RUN_PLAN.md` | The smallest calibrated run set for the overlapping requests, the R7.6 checks, and the requests outside the prespecification | — |
| `FINAL_PASS_CHECKLIST.md` | Manuscript locations and the artifacts that supply final values for R4.10, R4.11, R5.M7, R5.m4, R5.m5, R7.6 | — |

## Shifted-trigger check (`shifted_triggers/summary.txt`)

**Method.** Each family was tuned on the stationary validation week and tested on the held-out week in which the spike
schedule changes without notice to the forecaster. Five traces, fast simulator, current code.

**Unfavourable first:**
- PRISM meets 2% in 3 of 5 traces (pooled 2.38%), against 1.55% on the stationary test week at the same settings; its
  cost rises by about 8%.
- Unsmoothed headroom (PredHead) violates 19.0% of windows and smoothed headroom (PredHead+S) 6.5%. Neither meets 2% in
  any trace.
- Reactive (2.38%) and QuantProv-q90 (2.32%) also exceed 2% pooled.
- 7 of 40 selections sit at a grid edge, including PRISM at eps 0.08 on traces 103-105.

**Paired PRISM minus comparator (n = 5, 95% t):**
- QuantProv-q90: cost -0.3 +/- 3.8%, violating windows +0.06 +/- 0.56 points. Both intervals include zero: not
  distinguishable, and not a tie by the prespecified +/- 2% criterion.
- Reactive: cost -21.8 +/- 9.3%, violating windows +0.00 +/- 2.49 points.
- Static: cost -17.3 +/- 11.9%, violating windows +1.19 +/- 2.14 points.

**Consistency check.** The stationary reference reproduces, at HEAD, the selections and the Table VI analogue of
`../table6_versions/comparison.txt` (f77c00c) to printed precision: against PredHead +14.1 +/- 5.3%, against
PredHead+S +6.1 +/- 5.1%, against QuantProv-q90 +1.6 +/- 2.3%.

## The 13 IDs

| ID | Subrequest (key wording) | Verified or completed in this pass | Status | Smallest remaining step |
|---|---|---|---|---|
| R2.1 | event-level simulation as the primary evaluation, or a calibrated approximation | closed-loop event-level controller and telemetry tests pass (30/30); pilot verified 21 Nov (exploratory); mapped to C1-C3 (`RUN_PLAN.md`) | Not fixed | extend the pilot driver; C1-C3 after calibration |
| R2.18 | more independent realisations, repeated experiments; distinguish post hoc from confirmatory | trace inventory checked (25/25 development counts; manifest unchanged); prespecification unchanged; no confirmatory seed used | Not fixed | C1-C3 on 25 traces; caption labels (E11) |
| R3.3 | a test without the Eq. (14) match; move Table X next to Table V | mechanisms on matched schedules (open loop) restated with sources; closed-loop pilot is exploratory; live AWS evidence does not bear on the match | Not fixed | C1-C3 as the unmatched primary test; move the table (manuscript) |
| R4.2 | closed-loop event-level simulation with exact attainment as the primary evaluation | implementation and tests verified; attainment is per request at event level | Not fixed | as R2.1 |
| R4.10 | graphical abstract shows smoothed headroom 3.24% beside 6.67% | drafting (E9) checked; PredHead+S is exploratory in the prespecification | Not fixed | author decision: run PredHead+S or change the comparator; redraw |
| R4.11 | provenance prose to the repository; one primary evaluation and main table | (a) text E10 ready; (b) waits for C1-C3 | Not fixed | apply E10; restructure after C1-C3 |
| R5.M4 | more traces; all families under shifted triggers; widen every edge grid; or state the limits | **(b) done**: all nine families under shifted triggers (fast simulator, exploratory, pre-calibration) | **Partially fixed** | (a) C1-C3 on 25 traces; (c) the prespecified edge expansion, plus the exploratory families; (d) abstract text |
| R5.M7 | label pooled figures; say which orderings held; (d) Tables VI and XII intervals include zero | stationary Table VI analogue reproduced at HEAD; (d) correction retained (VI and XII, not the Table VII 1.0% case); checklist | Not fixed | regenerate (a)-(e); (f) renaming is text only |
| R5.m4 | supplement tables for the per-trace ablation and QuantProv memory results | verified pre-calibration tables exist (46/46); the experiments are outside the prespecified set | Not fixed | author decision: regenerate exploratory, or publish labelled pre-calibration tables |
| R5.m5 | graphical abstract: smoothed headroom; title; caption narrowed | as R4.10; (b) title is text only | Not fixed | (b) now; (a) and (c) after the regeneration and D4 |
| R6.4 | PRISM against a calibrated-q90 + smoothing controller as the primary baseline | C1 is exactly this comparison; exploratory intervals against QuantProv-q90 include zero on both stationary and shifted-trigger weeks | Not fixed | C1 as the main table |
| R6.5 | beyond five traces; stronger statistical evidence | 25 confirmatory traces and the prespecified criteria are ready; none run | Not fixed | C1-C3 |
| R7.6 | which differences are statistically meaningful; no superiority from small differences | checks specified (`RUN_PLAN.md` section 3): difference only if the interval excludes 0; tie only within +/- 2%; similar compliance only within +/- 0.5 points | Not fixed | apply the criteria to C1-C3 and to the exploratory Table VII |

**Also relevant, outside the 13.** The saved test run partly closes the gap recorded for R2.2 and R6.3 ("no saved run
of the closed-loop tests"). It covers three test modules, not the full suite.

**Checksums.** `SHA256SUMS` hashes the files as written on this Windows laptop. Three of them, `shifted_triggers/run.log`,
`tests/unittest_closed_loop.txt` and `trace_inventory.txt`, have CRLF line endings, so `SHA256SUMS.lf` hashes the LF
content that Git stores (core.autocrlf=true). Use the `.lf` list on an LF checkout.
