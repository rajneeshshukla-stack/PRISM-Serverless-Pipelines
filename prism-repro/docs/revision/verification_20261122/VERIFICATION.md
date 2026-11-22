# Verification of the 21-22 Nov 2026 revision-progress pass

**Scope.** This verifies the saved outputs listed in `../REVISION_PROGRESS_20261122.md` against the reviewer wording in
`review-inputs/detailed review comments.txt`. Verified 22 Nov 2026 from the saved files. The pass was not rerun, no
AWS call was made, and no file in the six output folders was changed.

**Labels.** Every simulation figure is PRE-CALIBRATION: assumed constants (Table S1), superseded at recalibration.
Test-week analyses are POST HOC. The event-level replays are OPEN LOOP. Only seeds 101-105 and the Huawei traces
201-205 were used, so the confirmatory seeds 106-130 stay unused.

**Code.** HEAD 78ba419 on branch `closed-loop`. `src/`, `experiments/`, `results/` and `CHECKSUMS.sha256` are clean.
The four new scripts are uncommitted; each was last modified before its run started.

**Platform.** One Windows 11 laptop with Python 3.12.9, numpy 2.4.4, scipy 1.17.1 and scikit-learn 1.8.0
(`.venv-prism-pilot`), the same versions as the pass recorded.

## Unfavourable and incomplete items first

1. **`event_severity/` did not finish.**
   - The machine entered Modern Standby at 01:44:40 CST, the same second as the last row was written.
   - Windows Update then restarted it twice, at 02:53 and 02:55 CST (System log: Kernel-Power 506, User32 1074).
   - `run.log` has no end line. `summary.txt` was never written, although the README's provenance cites it, and the
     README's Results section is empty.
   - 204 rows were saved:
     - R24 (R2.4): 19 of 20 tasks complete. Trace 105 new spike lacks the 30% and 50% margin replays.
     - R72 (R7.2): 9 of 48 replays; one of the 12 weeks is complete.
   - `event_severity_summary_partial_rows.txt` here is the script's `--analyse` output on a copy of the saved rows.
     It is labelled as a verification copy.
2. **R7.2's fast-to-event decomposition is not usable** (n = 1).
3. **The current code changes a stored statistical reading.** PRISM against QuantProv-q90 at matched compliance at the
   1.0% target:
   - stored submitted rows: -0.4 +/- 3.3%, which includes zero;
   - current code (`grid_studies`): -2.3 +/- 2.0%, which excludes zero, in all three estimates.

   The current code also selects more grid edges than the stored rows: 29 against 23 of 160 post hoc, and 28 against
   25 of 40 on the real traces.
4. **Wording to correct before the outputs are cited:**
   - `grid_studies/README.md` says "range over the five traces", but PRISM's 1.5% and 2.0% cells use four.
   - It says QuantProv-q90 and PredHead+S "remain indistinguishable". The accurate statement is that their intervals
     include zero, which does not establish equivalence.
5. **`notes/decisions_pending.md` checks:**
   - D4's "69-100%" is 68.90-100% in `supplement_tables/pertrace_tables.md`, rounded.
   - D2's reading of reference [3] comes from a public PDF that is not stored in the repository, so it was not
     re-checked.
   - D5's Huawei 2025 Region 2 counts were not re-checked, and that data set states no licence.
6. **Reviewer IDs cited.** The brief says 28 reviewer items, but the outputs and the new decision text cite 27
   distinct IDs, listed under "Reviewer IDs cited" below.

## What was verified, and how

| Folder | Check | Result |
|---|---|---|
| `grid_studies/` | `--analyse` rerun on a copy of the saved rows; every README figure compared with the summaries; logs have start and end lines | `summary_posthoc.txt` and `summary_real.txt` byte-identical; README figures match (edge tallies 29 -> 2 of 160 and 28 -> 14 of 40, item by item) |
| `grid_edges/` | `grid_edge_audit.py` rerun on the stored rows (`results/raw/E1`, `E12`, `R1`) | all four JSON files byte-identical; 0/40, 23/160, 6/30, 25/40 |
| `statistical_meaning/` | script rerun | `summary.md` byte-identical; reproduces the stored T6 tables 4 of 4 scenarios each |
| `supplement_tables/` | script rerun | `pertrace_tables.md` byte-identical; 46 of 46 cells reproduce the stored mean tables |
| `aws_live_followup/` | 18 run files checked against `aws_live_integration/sources.sha256`; script rerun on the run folder | 18 of 18 OK; 4 tables and `build_output.txt` byte-identical |
| `event_severity/` | `--analyse` on a copy of the saved rows; request counts and completeness per task | see item 1; the current code reproduces the stored Table XI violating windows in 60 of 60 replays (costs within USD 0.005) |

`SHA256SUMS` lists every verified file as it stood when checked.

## Reviewer IDs cited (27)

These are the IDs cited by the outputs and by the 21-22 Nov additions to `notes/decisions_pending.md`:

R1.1, R1.3, R2.4, R2.6, R2.7, R2.8, R2.9, R2.14, R2.19, R2.20, R3.1, R3.2, R3.7, R4.3, R4.4, R4.7, R4.10, R5.M4,
R5.M7, R5.m4, R5.m5, R6.1, R6.2, R6.4, R7.2, R7.4, R7.6.

Statuses and tracker cells were updated in `notes/dispositions.md` and in the 22 Nov 2026 tracker workbook.

## Line endings (22 Nov 2026)

Applies to `SHA256SUMS`, with companion `SHA256SUMS.lf`.

Python on Windows wrote the JSON row files with CRLF line endings, and Git (core.autocrlf=true) stores them with LF. The checksum lists named here hash the CRLF working copies. Their `.lf` companions hash the stored LF content; use those on an LF checkout. The companions were written 22 Nov 2026 from the committed blobs, after checking that each blob is the LF form of the listed file.
