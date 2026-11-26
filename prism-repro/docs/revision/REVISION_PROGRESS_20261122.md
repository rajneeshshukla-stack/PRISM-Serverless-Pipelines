# Revision-progress pass, 21-22 Nov 2026: new evidence and how to reproduce it

**Code and platform.**
- Branch `closed-loop`, HEAD 78ba419. The new scripts and outputs below are uncommitted.
- `src/` and `experiments/` were clean for every run (each folder's `environment*.json`).
- One Windows 11 laptop (4 cores; Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0). No result is claimed
  for another platform.

**Labels.**
- Every simulation result here is PRE-CALIBRATION (assumed constants, Table S1) and supersedes at recalibration.
- Test-week analyses are POST HOC.
- Seeds 101-105 and the five Huawei traces (201-205) only. The confirmatory seeds 106-130 were not used, and
  `PRESPECIFICATION.md` is unchanged.

**Not done in this pass:**
- no AWS call, no production-scale run;
- no edit to the manuscript, `results/`, `CHECKSUMS.sha256` or any workbook.

| Folder | What | Reproduce (from `prism-repro/`) | Serves |
|---|---|---|---|
| `event_severity/` | Event-level replays of the stored E1 schedules: severity and persistence of the E12 selections, workload conditions, modelling-factor counterfactuals, capacity margins; PRISM's fast-to-event gap decomposed | `python scripts/revision/event_severity_factors.py . docs/revision/event_severity --workers=4`, then `... --analyse` | R2.4, R7.2; evidence for R1.1 |
| `grid_studies/` | Fast-simulator reruns on the current code: refined near-target evaluation; post hoc and real-trace selections on the widened grids | `python scripts/revision/fast_grid_studies.py . docs/revision/grid_studies --suite=posthoc` (and `--suite=real`), then `--analyse` | R2.19, R4.7, R5.M4(c) |
| `grid_edges/` | The stored grid-edge audit reproduced and listed in full (original boundaries, selections, sides) | `python scripts/revision/grid_edge_audit.py . <rows> --week val\|test --out <file>` | R4.7, R5.M4 |
| `supplement_tables/` | Per-trace ablation and QuantProv memory tables from stored rows; means reproduce the stored tables (46 of 46) | `python scripts/revision/supplement_pertrace_tables.py . docs/revision/supplement_tables` | R5.m4 |
| `statistical_meaning/` | Which paired differences exclude zero (stored rows; reproduces the stored T6 tables) | `python scripts/revision/statistical_meaning.py . docs/revision/statistical_meaning/summary.md` | R7.6, R5.M7(d), R6.4 |
| `aws_live_followup/` | Further analysis of the saved live run (no AWS call): cold-start latency by memory, warm variability, concurrency, Lambda GB-s lower bound | `python docs/revision/aws_live_followup/analyse_saved_run.py --run <private run folder> --out docs/revision/aws_live_followup` (from the repository root) | R3.1, R2.8, R6.2, R2.14, R6.1 |

**Author decisions prepared.** These are in `../../../notes/decisions_pending.md`; each is a dated update that leaves
the earlier text intact:
- D2 (R3.2): the cited method read;
- D4 (R2.7, R4.4): a narrowed RQ4 drafted;
- D5 (R2.9): the available traces and the smallest comparison;
- D7, new: provisioned-concurrency measurements in us-east-2 at the recorded quota of 400.

## Update, 22 Nov 2026: verification and resumed pass (cutoff 7:06 AM CST)

**Verification of the outputs above.** See `verification_20261122/VERIFICATION.md`.
- Every output except `event_severity/` rebuilds byte-identically from its saved rows or run files.
- `event_severity/` stopped at 01:44 CST. The laptop entered Modern Standby, and a Windows Update restart followed.
  It wrote no summary. Its partial analysis is in `verification_20261122/event_severity_summary_partial_rows.txt`.

**Resumed replays.** See `event_severity_resumed_20261122/` (README.md, summary.txt, run_resumed.log).
- 187 saved design rows were reused unchanged; three of them were recomputed exactly.
- The 41 missing replays ran in a separate folder.
- The result is 228 of 228 design rows, each present once. `event_severity/` is untouched.
- Labels: PRE-CALIBRATION, POST HOC, OPEN LOOP.

**Discrepancy, R7.6 and R5.M7(d).** See `matched_compliance_discrepancy/`.
- PRISM against QuantProv-q90 at the 1.0% matched-compliance target is -0.4 +/- 3.3% on the stored rows and
  -2.3 +/- 2.0% on the current code.
- The difference comes from the simulated rows, not from the method.
- Its cause is not attributed; the conclusion is open.

**Audit, 21 Nov 2026 11:00 AM CST to the cutoff.** See `audit_20261122/AUDIT.md`.
- Commits 20ea675 and 6d6b6ef were missing from the tracker's Evidence and commits sheet and were added.
- Stale closed-loop-build and prespecification text was corrected.
- Seven IDs of the 28-ID queue were not advanced, and their blockers are now recorded: R2.1, R2.18, R3.3, R3.6,
  R4.2, R4.11, R6.5.

**Tracker.** `review-inputs/PRISM_Tracker_dispositions_resumed_verified_20261122-070634.xlsx`, with an identical
copy in `PRISM_tracker_backups`.
- R7.2 moved from Not fixed to Partially fixed. Its subrequest (a), which simulation assumptions contribute most, is
  answered in simulation; (b), the real-world effect, is open.
- Totals: 0 Fixed, 37 Partially fixed, 35 Not fixed, 1 No change warranted.
- `notes/dispositions.md` equals the workbook in all 73 rows.
