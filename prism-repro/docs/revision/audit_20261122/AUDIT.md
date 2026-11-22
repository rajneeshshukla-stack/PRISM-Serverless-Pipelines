# Audit of reviewer-relevant changes, 21 Nov 2026 11:00 AM CST to the end of the resumed pass (22 Nov 2026)

**Scope.** Checked:
- every commit on every local ref in the window;
- the saved local experiments and AWS evidence;
- the verified uncommitted work of the interrupted overnight pass and of the resumed pass.

Each finding was checked against the cumulative baseline workbook,
`PRISM_Tracker_dispositions_overnight_verified_20261122-063949.xlsx` (SHA-256 16a130f6...; totals 0 Fixed, 36
Partially fixed, 36 Not fixed, 1 No change warranted). The final cutoff is recorded in the Evidence and commits entry
of the resumed workbook and in `../REVISION_PROGRESS_20261122.md`.

**Refs.**
- `closed-loop` holds all 13 commits in the window, from d5191dd (11:53:36 AM) to 78ba419 (11:00:37 PM, 21 Nov).
- `main` (2bdeaba, 20 Nov), `phase-e-review` (3bd1f33, 21 Nov 8:53 AM), their remotes and `v1-submitted` have no
  commit in the window.
- There are no stashes.

## Commits in the window and their tracker representation

| Commit (CST, 21 Nov) | Work | In the baseline tracker | Action |
|---|---|---|---|
| d5191dd 11:53 | week-aligned feature history; 232 -> 170 s per PRISM week | yes (R2.2, R6.3, E&C) | none |
| a10efe6 11:54 | kappa gap: event-level cold starts 3.23x fast; init protocol | yes (R2.12, R5.M1, R3.3, R2.2) | none |
| d16fbea 11:54 | prespecification frozen | yes (R3.5, E&C); **contradicted** by the md's R6.6 ("not frozen") and by R2.18's "Next: freeze the prespecification" | corrected |
| 3e6021d 11:55 | pilot driver | yes | none |
| 8786295 11:58 | manuscript drafts, RQ4 options, quota-10 plan | yes (18 IDs) | none |
| c6ebc86 11:59 | B3 on hold; C1 fidelity statement | yes for R2.12 and R5.M1; R3.3 lacked proposal C1 | added to R3.3 |
| b9d84bd 12:01 | REPRODUCE.md section 7 | yes | none |
| 1f1d771 12:12 | dispositions after the pilot | yes | none |
| pilot rerun 12:22-3:20 PM at 1f1d771 | 125 closed-loop weeks; verified | yes (3:42 PM About entry and rows) | the workbook's R2.2, R6.3 and R3.5 still said "Verify the exploratory pilot outputs": corrected |
| 20ea675 3:59 PM | verified pilot evidence committed (`closed_loop_pilot/`) | evidence yes; **commit missing** from Evidence and commits | E&C entry added |
| 58da2ff 5:00 PM | init vs memory from external data; measurement plan | yes | none |
| 6d6b6ef 5:51 PM | AWS measurement harness | evidence yes; the 5:46 PM E&C row says "uncommitted (local)", but it was **committed 5 minutes later** | E&C entry added |
| ea32370 7:56 PM | pipeline kit, local rehearsal on fakes | yes | none |
| live run 8:30-8:55 PM (no commit) | fixed-schedule live integration test, us-east-2 | yes, with the REPORT-collection gap and the not-clean teardown | none |
| 78ba419 11:00 PM | sanitized live evidence package | yes (paths in replies); rows cited only private raw paths in Evidence | repository path added to R2.8, R2.20, R6.1, R6.2 |

## Contradictions corrected (stale after the closed-loop build of 21 Nov)

- **"Closed loop" as a blocker.** R2.1, R2.18, R3.3, R4.2, R6.5, R1.1, R5.M4 and R6.4 called the blocker the closed-loop
  build, Phase E, or the closed loop. The simulator is built and piloted. The remaining blocker is the confirmatory,
  calibrated closed-loop evaluation: C1-C3 on seeds 106-130 after measured constants.
- **R4.2.** Its Evidence said "instrumentation only"; that is superseded.
- **`notes/dispositions.md`, stale rows:**
  - R6.6 said the prespecification is not frozen; it was frozen in d16fbea.
  - R2.12's draft reply relied on proposal B3, which is on hold (c6ebc86).
  - R5.M1 still named the closed-loop build as its blocker.

  The workbook's text replaces all three. The md-only verified facts were carried into the workbook first:
  - the missing closed-loop test run (R2.2, R6.3);
  - the seed and prespecification checks (R3.5);
  - the historical lower-floor comparison (R2.12);
  - the analysis-labelling practice (R6.6).

## Distinctions kept

- Local rehearsal on fakes (ea32370) is not live evidence.
- The live fixed-schedule integration test (21 Nov, 8:30-8:55 PM) ran on the proposed synthetic workload and was not
  driven by PRISM's controller. CloudWatch REPORT collection saved 0 entries, and teardown deleted the log groups.
  Lambda Init Duration, billed duration and Lambda cost are therefore unverified, and no bill exists.
- No live adaptive-controller validation exists. No row claims one; checked by a text scan of the four AWS rows and
  every draft reply.
- No draft reply contains a private Windows path, an AWS identifier or a raw log; checked by a text scan of all 73
  replies.

## Findings whose source or timing cannot be verified (flagged, not used as evidence)

- **Session reports with no saved file:**
  - the 33 harness and 124 project tests "observed passing" (no test log was saved);
  - the live-run audit;
  - the author's later CLI check that the state machine was gone.
- **The first pilot run's output** is unavailable; only the 12:22 PM rerun is verified.
- **The "20-35x" kappa-estimate gap** appears in no saved file, and PRIOR_EVIDENCE.md is absent.
- **The live run's code revision** is not recorded in its files; ea32370 is inferred from file dates.
- **The quota of 400** in us-east-2 is one preflight reading.
- **D2's reading of reference [3]** comes from a public PDF that is not stored.
- **D5's Huawei 2025 Region 2 counts** were not re-checked, and that data set states no licence.

## The 28-ID queue against the 27 cited IDs

The overnight prompt (22 Nov 2026 05:25 UTC) listed 28 IDs:
- 17 technical: R2.1, R2.4, R2.18, R2.19, R3.3, R4.2, R4.7, R4.10, R4.11, R5.M4, R5.M7, R5.m4, R5.m5, R6.4, R6.5,
  R7.2, R7.6;
- 4 decision: R2.7, R4.4, R2.9, R3.2;
- 7 AWS-linked: R1.1, R2.8, R2.14, R3.1, R3.6, R6.1, R6.2.

The overnight outputs cite 27 IDs, of which 21 are in the queue. The other 6 cited IDs were outside it: R1.3, R2.6,
R2.20, R3.7, R4.3 and R7.4.

Seven queue IDs were neither cited nor given a recorded blocker:

| ID | Status | Remaining work and blocker |
|---|---|---|
| R2.1 | Not fixed | event-level primary evaluation; blocker: the calibrated confirmatory closed-loop runs |
| R2.18 | Not fixed | (a) runs on 30 traces, blocked by calibration; (b) labels in the manuscript |
| R3.3 | Not fixed | (a) unmatched primary evaluation, blocked by calibration; (b) move Table X (manuscript); proposal C1 drafted |
| R3.6 | Not fixed | regeneration on measured constants in one environment; the author's release decision |
| R4.2 | Not fixed | closed-loop exact-attainment primary evaluation, blocked by calibration |
| R4.11 | Not fixed | (a) apply proposal E10 (no blocker); (b) waits for the primary evaluation |
| R6.5 | Not fixed | 30-trace primary results, blocked by calibration |

None of the seven can advance locally without calibration, a manuscript edit or the author's decision. Their rows now
record that.
