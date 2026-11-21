# Closed-loop pilot (R2.2, R6.3, R5.M1)

**Exploratory, pre-calibration, supersedes at recalibration.** Not a result: PRESPECIFICATION.md section 7 runs this
pilot only to check the pipeline end to end and the compute budget. It uses development seeds 101-103, which never
enter a confirmatory result. The constants are assumed (`PipelineConfig()`/`PrismConfig()` defaults), not measured.
It ran on one Windows machine only, so it supports no cross-platform claim.

## Provenance

- `run_20261121-122241/` is a byte-for-byte copy of `docs/revision/closed_loop_pilot_rerun_20261121-122241/` at the
  repository root (untracked): `environment.json`, 12 group files and `summary.txt` (UTF-16). The SHA-256 of every
  copied file is in `run_20261121-122241.sha256` and equals the source's.
- There are two checksum lists, because the run wrote its JSON with CRLF line endings on Windows and Git commits
  text with LF (`core.autocrlf=true`, as for the rest of the repository; see KNOWN_ISSUES "Windows checkout reported
  as corrupt").
  - `run_20261121-122241.sha256` hashes the original CRLF bytes as written by the run. A Windows checkout with
    `core.autocrlf=true` verifies against it.
  - `run_20261121-122241.lf.sha256` hashes the committed LF content. A clone on any platform without CRLF
    conversion verifies against it.
  - The two lists differ only in the 13 JSON files, and only by line endings: each committed JSON equals its
    original after CRLF->LF. `summary.txt` is UTF-16, which Git treats as binary, so it is byte-identical in both
    lists.
  - Verify with `cd run_20261121-122241 && sha256sum -c ../run_20261121-122241.lf.sha256`, or use the `.sha256`
    list on a CRLF checkout.
- Script: `scripts/revision/closed_loop_pilot.py` (committed in 3e6021d), run at commit **1f1d771**
  (`environment.json`). The run directory's timestamp is 21 Nov 2026 12:22:41 CST, 10 minutes after 1f1d771
  (12:12:53 CST). The group files were written between 12:33 and 15:13 CST and `summary.txt` at 15:20 CST. Recorded
  week time is 2.74 h over 125 closed-loop weeks (median 78 s). No run.log was saved, so whether the machine
  suspended during the run is not recorded.
- Environment: Windows-11-10.0.26200-SP0, Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0.
- `analyse_reproduced.txt` is `closed_loop_pilot.py prism-repro <copy> --analyse` run again on the saved JSON (no
  simulation). It equals `summary.txt` line for line.
- `verify_evidence.py` and its output `verification.txt` are an independent read-only check (44 checks, all
  passed). It replays the selection rule and the prespecified edge expansion from the saved validation rows,
  checks that every policy saw identical request counts per trace and week, checks that the test-week counts equal
  the `kappa_gap/` stationary test weeks, recomputes the paired intervals, and checks the saved kappa diagnostic
  in `../kappa_gap/`.

## Design (PRESPECIFICATION.md sections 4, 5 and 7)

Stationary scenario, default deadline 14.5 s, kappa floor 0.1, GBM forecasts computed online. Each policy was tuned
on the closed-loop validation week by the common rule: the cheapest setting with at most 13 of 672 violating
windows (2%). Edges were expanded by `GRIDS_WIDE`. The selected setting then ran on one held-out test week per
trace. Every policy saw identical workloads and draws: key 2 for validation, key 3 for test.

## Results, with unfavourable items first

| Policy | Test weeks meeting 2% | Test violating windows (101 / 102 / 103) | Mean test rate | Test cost USD/week (101 / 102 / 103) |
|---|---|---|---|---|
| PRISM | 2 of 3 | 12 / 11 / **16** of 672 | 1.93% | 1298.6 / 1340.1 / 1239.5 |
| QuantProv-q90 | 1 of 3 | **15** / 8 / **19** | 2.08% | 1256.8 / 1425.7 / 1154.7 |
| MemAdapt-q90 | 1 of 3 | **15** / 8 / **19** | 2.08% | identical to QuantProv-q90 |
| Reactive | 3 of 3 | 8 / 7 / 8 | 1.14% | 1786.5 / 1783.0 / 1767.4 |

Paired results, PRISM minus comparator, over 3 traces (95% t interval, df 2):

- **No comparison reaches similar compliance.** The prespecified criterion requires the paired violating-window
  interval to lie within +/-0.5 points, and it fails in all three. Every cost comparison below is therefore
  confounded by compliance.
- **vs Reactive:** PRISM costs 27.3% less, +/- 6.2% (interval -33.6 to -21.1; per trace -27.3, -24.8, -29.9), but
  it has more violating windows in every trace: +0.79 +/- 0.85 points (-0.06 to +1.65; per trace +0.60, +0.60,
  +1.19). Reactive met the target in all three test weeks and PRISM in two.
- **vs QuantProv-q90:** cost +1.6 +/- 17.0% (-15.5 to +18.6; per trace +3.3, -6.0, +7.3). This is neither a
  difference nor a tie under section 5. Violating windows -0.15 +/- 1.28 points (-1.43 to +1.13).
- **vs MemAdapt-q90:** the same numbers as QuantProv-q90. MemAdapt never left 1024 MB (0 epochs at 2048 MB or more),
  so at the default deadline its records equal QuantProv-q90's in every field except runtime. The pilot does not
  test the short-slack comparison C3 (deadline 12 s), which is where MemAdapt differs.
- PRISM's selections were interior (eps 0.01, 0.01, 0.02). Each sat at exactly 13 of 672 validation windows, the
  allowance. QuantProv-q90 on trace 102 selected the top of its grid (1.5) and was expanded once to 1.6, after
  which 1.5 was interior. There were no edge hits after expansion.
- Closed-loop kappa on the test weeks was 0.442, 0.384 and 0.434. This is consistent with `../kappa_gap/` (closed
  loop 0.397-0.473 at eps 0.02) and well above the fast simulator's floor-bound 0.110.

## Limitations

Three development traces give df = 2, so the intervals are wide. The pilot covers one scenario, one deadline and one
test week per trace, with one run per setting and no matched-compliance frontier. It omits PredHead+S and the new
spike scenario (R5.M1(e)). The constants are assumed. It does not rerun the R2.12 cold-hit-floor comparison in
closed loop. The confirmatory comparisons C1-C3 on seeds 106-130 have not been run.
