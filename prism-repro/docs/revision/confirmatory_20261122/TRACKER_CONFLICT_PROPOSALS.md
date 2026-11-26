# Proposed tracker corrections outside the 13 target rows (23 Nov 2026; NOT applied)

**Update (final audit, 23 Nov 2026):** the corrections below were applied, all with statuses unchanged, except the optional
R2.4 note and the R2.19 blocker note, which were not needed. They are in
`PRISM_Tracker_dispositions_final_audit_verified_*.xlsx`; see `FINAL_AUDIT_20261123.md` section 3, which also lists
further rows corrected.

Swept: all 73 rows of `PRISM_Tracker_dispositions_confirmatory_regeneration_verified_20261123-133300.xlsx` for claims
that the C1-C3 runs (`RESULTS.md`) or the regeneration (`../regeneration_20261122/README.md`) make out of date
(`private/drafts/tracker_tools/conflict_sweep.py`). Only the 13 target rows were edited. The rows below are proposals
for the author; no status change is proposed unless stated.

Verified facts the proposals rely on:
- `docs/revision/PRESPECIFICATION.md` has one commit, d16fbea (21 Nov 2026 11:54:54 CST), no working-tree change and no
  addendum file; the first confirmatory week started 22 Nov 2026 22:49:32 UTC (`run/run.log`). The frozen file
  therefore precedes the first run on seeds 106-130.
- C1-C3 ran pre-calibration (assumed constants) on seeds 106-130 and are verified (`checks/verify_run_final.txt`).
- The regeneration rebuilt every stored table at fd8b01a, pre-calibration; it is not the regeneration on measured
  constants.

| Row | Current text (excerpt) | Why it is out of date | Proposed text |
|---|---|---|---|
| R3.5 (Requests, Evidence, Remaining) | "The 25 confirmatory traces (seeds 106-130) have not run"; "no saved output ... uses seeds 106-130"; "Confirmatory output is pending" | C1-C3 ran on seeds 106-130, 22-23 Nov | "C1-C3 ran on seeds 106-130 (pre-calibration, 22 Nov 22:49 UTC to 23 Nov 15:26 UTC); the frozen file d16fbea precedes the first run (verified: one commit, no addendum). Open: primary results from those traces in the manuscript, and the calibrated rerun." Its pass criterion's first half is now met. |
| R2.2 (Requests, Remaining) | "the confirmatory, calibrated evaluation has not run"; "Next: the confirmatory C1-C3 on seeds 106-130"; "run and record the closed-loop test suite; then C1-C3 ..." | The confirmatory evaluation ran, pre-calibration | "The confirmatory evaluation ran pre-calibration (C1-C3, 23 Nov 2026; RESULTS.md); the calibrated rerun has not. (b), every baseline under the same loop, remains open: C1-C3 cover QuantProv-q90, Reactive and MemAdapt-q90 only." |
| R5.M4 (Requests (a), Evidence, Remaining) | "the 25 confirmatory traces have not run"; "Seeds 106-130 ... were not used"; "needs an addendum before the first run on seeds 106-130, or an exploratory run" | The first run on seeds 106-130 happened, so the addendum option has lapsed | "(a) 25 more traces ran in C1-C3 (pre-calibration). Including the shifted-trigger scenario or other families now requires an exploratory run, labelled as such; an addendum to the frozen plan is no longer possible." |
| R4.6 (Remaining) | "checked on unseen seeds 106-130" | Seeds 106-130 have now been used, and their results seen, by C1-C3 | "checked on seeds 106-130 as an exploratory analysis (those traces were used by the confirmatory C1-C3), or on new seeds fixed in advance." |
| R5.M1, R6.3 (Remaining; R6.3 Requests and Response) | "Next: the confirmatory C1-C3 on seeds 106-130"; "The calibrated confirmatory evaluation is open"; "The full closed-loop comparison remains pending" | C1-C3 ran (pre-calibration) | "C1-C3 ran pre-calibration (RESULTS.md); next: the rerun on measured constants." R6.3 Response: "The closed-loop comparison on 25 traces is complete on assumed constants [pending: rerun on measured constants]." |
| R2.3, R2.16, R2.19, R3.4, R4.7, R4.9, R7.3 (Remaining) | "Blocker: regeneration" (R2.3: "regeneration (closed loop, measured constants)") | A regeneration at one commit now exists (pre-calibration); the blocker that remains is the one on measured constants | "Blocker: regeneration on measured constants (the pre-calibration regeneration at fd8b01a, 23 Nov 2026, is in docs/revision/regeneration_20261122/)." For R2.19 add: its fast-grid study was not rerun on the regenerated tree. For R4.7 add: on the regenerated Table XII PRISM is no longer the lowest-violating family (QuantProv-q90 0.18%, PRISM 0.33%). |
| R2.4 (Changed) | "It has not been run on event-level rows" | Event-level E12 rows were regenerated (seeds 101-105), but the R2.4 severity analysis was not rerun on them; the statement stays true | No change; optionally add "E12 regenerated 23 Nov 2026; the severity analysis has not been rerun on it." |
| R2.19 (Evidence, about the 1.0% comparison) | "PRISM against QuantProv-q90 at 1.0% is -2.3 +/- 2.0% (paper method) ... against the submitted -0.4 +/- 3.3%" | Consistent: the regenerated value is -2.27 +/- 2.02% | No change. |

Not affected: the AWS rows (R1.1, R1.2, R2.8, R3.1, R4.3, R5.M2, R6.1, R6.2: their "PRISM's controller did not run"
statements concern AWS, not simulation), R2.7 and R2.9 ("not run" refers to within-run execution changes).
