# Corrective patch for three code defects found after the runs

`m12_m5_corrections.patch` corrects the three defects listed in `../KNOWN_ISSUES.md` (paper: Section VI-G and
Supplementary Section S1). **The stored results in `results/` were produced without this patch and were not
regenerated.**

| Defect | File | Change |
|---|---|---|
| (a) reactive tracking reads pre-week minute -1 at the first epoch | `src/prism_repro/policies.py` | The pre-week slice ends at the visible horizon: `K_hist_default[week_start + lo : week_start + min(v + 1, 0)]` |
| (b) expired pre-week on-demand environments counted as warm | `src/prism_repro/simulator.py` | Per-minute pre-week pool with keep-alive expiry; the pre-week pool applies only if the first decision uses the default memory |
| (c) warm pool kept across memory changes | `src/prism_repro/simulator.py`, `src/prism_repro/des.py`, `scripts/revision/pc_billing_bounds.py` | A memory change starts a new on-demand pool (fast simulator); idle environments are reused only by requests of the same memory version (event-level simulator); the billing bound counts the new pool as re-provisioned |
| Tests | `tests/test_stage21_fixes.py` (new) | Four tests. Without the patch all four fail: three by assertion, and the event-level test with an error because the unpatched simulator has no memory-version argument. With the patch all four pass |

## Apply and test

From the repository root, on a copy:

```
patch -p1 --dry-run < patches/m12_m5_corrections.patch
patch -p1 < patches/m12_m5_corrections.patch
python -m unittest discover -s tests -v        # 52 tests (48 without the patch)
```

After the patch, `python scripts/build_manifest.py --verify` reports the changed files, because
`CHECKSUMS.sha256` describes the code that produced the stored results. Re-running the experiments with the
patch gives results that differ from the stored ones by the amounts below; with other library versions than the
pinned ones, forecast-driven runs also change by the library-version effect (Supplementary Section S1).

## Measured effect (paired diagnostic)

The same specifications were run with the unpatched and the patched code in the same software environment
(Python 3.13.18, scikit-learn 1.9.1), so the difference isolates the patch. 435 stored configurations:

| Scope | Runs | Runs with any change | Cost change | Violating-window change | Target met/missed changes |
|---|---|---|---|---|---|
| E1, validation-selected configuration of all 9 families, 20 test weeks | 180 | 8 | at most USD 0.002 per week | none | none |
| E1, validation grids of the policies without a learned forecaster | 140 | 11 | -0.005 to +0.006 USD | none | none; no selection changes |
| E1, PRISM at epsilon = 0.005 and 0.01, 20 test weeks | 40 | 4 | at most +USD 0.04 | none | none |
| E4, PRISM with memory (Table IX) | 14 | 0 | none | none | none |
| E6, PRISM under caps (Suppl. Table S5) | 40 | 17 | at most +USD 0.21 (0.012%) | none | none |
| Event-level replay of stored PRISM-0.005 schedules, traces 101-102 | 8 | 7 | at most +USD 0.005 | none | none |
| Forecast-driven validation runs within one window of the 2% threshold, at or below it (7) and above it but cheaper than the selected configuration (6) | 13 | 0 | none | none | none |

The unpatched runs without a learned forecaster reproduced the stored results exactly, which checks the harness.

`diagnostic/` holds the three scripts, their raw outputs (`*_unfixed.jsonl`, `*_fixed.jsonl`) and the summary
(`m12_m5_diagnostic_summary.json`). Each script takes `<code_root> <stored_results_root> <out.jsonl>` (the first
one also a list of jobs: `E1sel E1valnf E4 E6`); run it once with an unpatched and once with a patched copy of
this repository as `<code_root>` and this repository as `<stored_results_root>`. The scripts write nothing to
`results/`. Their docstrings use the working labels under which they were written ("Stage 2.1", "scratch").
