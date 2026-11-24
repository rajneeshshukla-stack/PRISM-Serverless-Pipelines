# E3/E7/E9 label-lookup fix, rebuild on Windows and Linux, and the reporting platform (R3.6; 23 Nov 2026)

PRE-CALIBRATION throughout (assumed constants). The manuscript, the submitted `results/`, `CHECKSUMS.sha256` and the frozen
prespecification are unchanged. The fix, its tests and this folder are committed together (not pushed).

**Related evidence.** `../regeneration_20261122/` (Windows regeneration) and `../confirmatory_20261122/` (C1-C3, Windows,
pre-calibration) are committed separately. The rebuild trees under `private/regen_labelfix_20261123/` stay local
(Git-ignored); their inputs are published as the archive described in section 7.

## 1. Unfavourable and null findings first

1. **The reported values depend on the platform, even with identical code and packages.**
   - On the same code (fd8b01a plus this fix) and the same 18 pinned packages, every forecast-driven run (PredHead,
     PredHead+hyst, QuantProv-q90/q99, PRISM) differs between Windows and Linux: 1,200 of 1,200 E1 rows, and E7's
     forecast-accuracy metrics.
   - Runs without a forecast (OnDemand, Static, Scheduled, Reactive) are identical: 700 of 700 E1 rows.
   - Headline values move as a result (section 4). The Suppl. S4 ordering of PRISM against QuantProv-q90 reverses:
     PRISM is costlier on Windows and cheaper on Linux.
2. **The R7.6 matched-compliance result is not robust to the platform.** On Linux:
   - At 1.0% the interval includes zero: −1.98 ± 2.09%.
   - At 1.5% it narrowly excludes zero: −1.78 ± 1.51%.

   On Windows the 1.0% interval was the one that narrowly excluded zero. Neither platform supports established
   superiority.
3. **The confirmatory C1-C3 ran on Windows.** Its forecast-driven values (PRISM, QuantProv-q90, MemAdapt-q90) may
   differ on the reference platform. That has not been measured: C1-C3 was not rerun, per the instruction to reuse the
   completed runs.
4. **A test command wrote into `results/`.**
   - A mistyped Windows check ran `scripts/check_reproducibility.py` in the working repository. That script writes
     `results/verification/reproducibility_seed101_<scenario>.json`. It overwrote the tracked `..._stationary.json` and
     created `..._new_spike.json`.
   - Both were restored at once: the tracked file from HEAD and the new file deleted. `results/` again has no diff against
     HEAD or `v1-submitted`.
   - The accidental outputs were kept outside the repository. They record the current code on Windows, not the
     submitted tree.

## 2. Why E3, E7 and E9 needed the workaround

`policies.PRISM.variant` names a run after its risk model: `'PRISM_EB'` for Erlang-B and `'PRISM'` for Eq. (5)
(`src/prism_repro/policies.py`, line 229, unchanged since the initial commit). That naming was designed when Eq. (5) was
the default, so `'PRISM'` meant the main configuration and `'PRISM_EB'` meant E11's alternative arm.

f119bee (20 Nov 2026) switched `PrismConfig.risk_model` to `"erlangb"` without changing any consumer. Since then:
- the main configuration's E1 rows, labels, run ids and array keys read `PRISM_EB`;
- `experiments/run_experiments.py: selections()` keys rows by `row["policy"]`. E3 (line 212), E7 (302) and E9 (398)
  look the main configuration up as `sel["PRISM"]`, which raises `KeyError: 'PRISM'`;
- `scripts/analyze.py` selects the main configuration by the literal `"PRISM"` (policy, labels, run-id prefixes, `SEL[s]["PRISM"]`),
  so it could not build the tables from current-code rows. The regeneration therefore used two workarounds:
  `run_exp_selection_shim.py` and `normalize_labels.py`.

The submitted rows predate f119bee and never met this.

## 3. The fix (release code path; `src/` unchanged, so policy behaviour and every simulation are unchanged)

| File | Change |
|---|---|
| `experiments/run_experiments.py` | `MAIN_PRISM_VARIANT` is the main configuration's variant name, derived from `PrismConfig()` defaults. `variant_of()` keys those rows as `"PRISM"`, and `selections()` refuses E1 rows of both names, which would be two risk models. Labels, run ids, specs and stored rows are unchanged. |
| `scripts/analyze.py` | `rows()` and `arrays()` read the main configuration's rows and array keys under `"PRISM"`, the same mapping as `normalize_labels.py`, but in memory and on load. E11 and E11occ are read as stored. Mixed names are refused. Stored files are never changed. |
| `tests/test_main_prism_variant.py` (new) | 4 tests: the naming, the `"PRISM"` lookup for the main configuration, submitted-style rows unchanged, and mixed risk models refused. |

The revision scripts under `scripts/revision/` still select by the literal `"PRISM"`; the label normalisation step
remains needed for them. Not fixed here: the stock E11 table compares the explicit Erlang-B arm with E1's default,
which is now also Erlang-B (documented in `../regeneration_20261122/README.md`).

## 4. Checks and rebuilds

**Tests.** 128 of 128 pass on Windows: the earlier 124 plus the 4 new ones. The 4 new tests also pass on Linux.

**Windows rebuild with the normal commands** (`private/regen_labelfix_20261123/prism-repro`, Git-ignored):
- The tree is a `git archive` of fd8b01a plus the three files above. Its inputs are the regenerated raw rows with
  their original `PRISM_EB` labels, without E3, E7 and E9.
- Commands, from that tree:

  ```
  python experiments/run_experiments.py --exp E3 --seeds 101 102 103 104 105
  python experiments/run_experiments.py --exp E7 --seeds 101 102 103 104 105
  python experiments/run_experiments.py --exp E9 --seeds 101 102 103
  python scripts/analyze.py
  ```
- Environment: `PYTHONUTF8=1` (Windows text I/O), one BLAS/OpenMP thread, and `venv/` (Python 3.12.9, `env/windows_venv_freeze.txt`).
- Every lookup resolved without the shim: E3 5 of 5, E7 5 of 5, E9 18 of 18.
- Result against the verified workaround outputs (`windows_fixed_vs_workaround.json`, `compare_trees.py`):
  - E3, E7 and E9 rows are identical in every result field. Only provenance and wall-clock fields differ (source hash,
    start time, runtime, decision time).
  - All 1,688 array keys are identical.
  - 51 of 53 `analyze.py` tables are byte-identical. The other 2 (`E3_quantile_vs_scenario_feasibility`) differ only in
    the measured decision-time column (4.26 against 1.99 ms), because this run shared the CPU with two other experiments
    and the test suite.

**Linux x86-64** (WSL2, Ubuntu 26.04, kernel 6.18 x86_64, i5-10310U; Python 3.12.3 installed by uv; the same 18
packages as the Windows venv, `env/linux_py312_freeze.txt`):
1. **`check_reproducibility.py`** on the `v1-submitted` tree, seed 101, stationary and new spike: 12 of 12 runs are
   identical to the stored rows (`check_reproducibility/linux_v1-submitted_seed101.txt`). `KNOWN_ISSUES.md` records that
   the forecast-driven runs differ on Windows.
2. **Full E1 from the `v1-submitted` tree** (`linux_tag_e1.sh`; one process per seed, separate result directories):
   - All 1,900 rows and all 9,950 arrays are identical to the stored `results/raw/E1`, in every cost, violating-window,
     attainment and selection field (`linux_v1submitted_E1_vs_stored.json`).
   - The only differences are last-bit floating-point noise (at most 2.4e-16) in two diagnostic means of 34 PRISM rows:
     `mean_excess_infeasible` and `max_excess`. No table or selection reads those fields; Table S13 uses the arrays.
   - This covers traces 101-103, whose recorded source af08337 is unavailable, and 104-105 (8c1710f).
   - So the stored E1 is a Linux result that this pinned Linux environment reproduces. The difference on Windows is a
     platform effect. Its mechanism (compiler, libm or similar) is not isolated.
3. **Rebuild with the fixed code** (`linux_rebuild.sh`):
   - E1 ran as one process per seed, concatenated in seed order. E3, E7 and E9 and `analyze.py` then ran with the commands
     above. Every step exited 0.
   - 37 tables were built. Tables for experiments not rerun on Linux (E2, E4-E6, E8, E10-E12, R1, R2) were not rebuilt.
   - Linux against Windows (`linux_vs_windows.json`) is reported below. The Linux tables are in `outputs/linux_tables/`.
     The 1.0% matched comparison from the Linux E1 rows (label normalisation, `pc_billing_bounds.py`, then
     `r76_matched_1pct.py`) is in `outputs/linux_revision/`.

| Quantity (current code, pre-calibration) | Stored (submitted code, Linux) | Windows | Linux |
|---|---|---|---|
| E1 PRISM selections, traces 101-105 | 0.02, 0.03, 0.05, 0.05, 0.05 | 0.05, 0.03, 0.08, 0.08, 0.08 | 0.08, 0.03, 0.08, 0.08, 0.08 |
| Table V new spike, PRISM: violating windows (SLO met) | 1.55% (80%) | 2.11% (40%) | 2.62% (20%) |
| Table V new spike, smoothed / unsmoothed headroom | 3.24% / 6.67% | 4.11% / 7.92% | 4.02% / 7.62% |
| Suppl. S4: PRISM / QuantProv-q90 cost (USD) | 1,267 / 1,320 | 1,150 / 1,142 | 1,130 / 1,139 |
| Suppl. S4: PRISM / QuantProv-q90 violating windows | 1.36% / 1.24% | 1.78% / 1.95% | 2.00% / 2.03% |
| Table VI, PRISM minus QuantProv-q90 cost (4 scenarios) | -2.8 to -3.9% (+/-7.4-7.5) | +1.6, +1.3, 0.0, -0.1% | +0.4, -0.2, -2.0, -1.5%; all intervals include 0 |
| Table X, PRISM fast / event | 1.44% / 3.75% | 1.69% / 6.14% | 1.98% / 6.99% |
| Table VIII new spike, PRISM | 1,395 / 1.55% | 1,270 / 2.11% | 1,241 / 2.62% |
| 1.0% matched (post hoc), PRISM minus QuantProv-q90 | -0.36 +/- 3.30% | -2.27 +/- 2.02% (excludes 0) | -1.98 +/- 2.09% (includes 0) |
| 1.5% matched | -0.44 +/- 2.13% | -1.19 +/- 1.95% | -1.78 +/- 1.51% (excludes 0) |
| 2.0% matched | +0.17 +/- 1.18% (tie) | -1.07 +/- 1.87% | -1.26 +/- 1.69% (n 4) |

Static and Reactive rows are identical on both platforms. In Table X, for example, Static is 2.94% / 13.29% and
Reactive 1.76% / 12.25% on both.

## 5. What this resolves for R3.6, and what depends on the reporting values

- **R3.6(a), rerun all tables in one library version.** Met on Windows, as before. The fix now lets the released
  commands rebuild Tables VIII and X, T14, T20 and the E9 tables without any workaround. The Linux rebuild also covers
  the E1-, E3-, E7- and E9-derived tables on the reference platform type.
- **R3.6(b), share the code.** The blocking defect is fixed locally. Commit and release are the author's actions.
- **Reporting platform** (decision). Linux reproduces the stored results exactly; Windows does not. If the paper keeps
  "Linux x86-64 reference platform" (`REPRODUCE.md`), the values to report are the Linux ones. That needs the remaining
  experiments regenerated on Linux (E2, E4-E6, E8, E10-E12, R1, R2, E4b, E11occ and the revision analyses). It may also
  need C1-C3 rerun there, since C1-C3 ran on Windows.
- **Depend on the chosen values:**
  - Tables V, VI, VII (matched), VIII, X, XI and S4, and the per-trace supplement tables;
  - the graphical abstract (R4.10, R5.m5);
  - the R5.M7 orderings (the S4 ordering flips) and the R7.6 matched-compliance wording;
  - Table X in R3.3, R7.2 and R2.1;
  - the C1-C3 values in R2.1, R2.18, R4.2, R6.4, R6.5 and R7.6;
  - K2 and K6 in `notes/manuscript_proposals.md`.
- **Do not depend on the platform:** the families without a forecast (OnDemand, Static, Scheduled, Reactive), the
  event-level and fast-simulator mechanics, and every AWS measurement.

## 6. Files

- `compare_trees.py`: the comparison tool.
- `windows_fixed_vs_workaround.json`, `linux_vs_windows.json` and `linux_v1submitted_E1_vs_stored.json`: the
  comparisons.
- `check_reproducibility/`, `env/`, `logs/` and `outputs/`: the check outputs, environments, logs and tables.
- `linux_check_repro.sh`, `linux_tag_e1.sh` and `linux_rebuild.sh`: the Linux commands, run from the user's WSL home.
- `SHA256SUMS` (LF).
- `reproduce_analysis.py`, `tools/` and `release_inputs.sha256`: the reproduction package (section 7).

## 7. Reproduction package (prepared 23 Nov 2026 after 6e0f05c)

**What failed in a clean checkout of 6e0f05c.** `r76_endpoints.py` raised `FileNotFoundError`. It executes
`../regeneration_20261122/r76_matched_1pct.py`, which is not committed. The analysis chain for R7.6 also needs
`normalize_labels.py`, and the E11 table needs `e11_occupancy.py`; both are only in the uncommitted regeneration folder.
The completed experiment rows are only in Git-ignored local trees.

**Added:**
- `tools/normalize_labels.py` and `tools/r76_matched_1pct.py`: byte-identical copies of the regeneration scripts.
- `tools/e11_occupancy.py`: a copy with an optional raw-directory argument and with assertions on the arms. E11occ must be
  Eq. (5) (`occupancy`), E11 must be Erlang-B, and E1's main configuration must be labelled `PRISM_EB` with no override.
  The table and its method are unchanged.
- `r76_endpoints.py` now looks in `tools/` first.
- `reproduce_analysis.py`, which runs the whole analysis workflow from a checkout and completed rows into a fresh
  directory. It runs no simulation.
- `release_inputs.sha256`: the 74 input files the workflow needs, as `windows/<EXP>/...` and `linux/<EXP>/...`, about
  35 MB and 30 MB.

**Command:**

```
python docs/revision/label_fix_20261123/reproduce_analysis.py --code <checkout>/prism-repro --out <new dir> \
    --input E1=<rows> --input E3=<rows> --input E7=<rows> --input E9=<rows> [--input E11=<rows> --input E11occ=<rows>]
```

Here `<rows>` is a directory holding `<EXP>/rows.jsonl` and `arrays_*.npz` as the current code wrote them.

**Checks (23 Nov 2026).** The package was run from a clean checkout of 6e0f05c plus the files above, into fresh
directories, on the completed rows. Both platforms' analyses ran on Windows with the pinned `venv/`.
- Windows rows (E1, E11 and E11occ from the regeneration; E3, E7 and E9 from the normal-path rebuild):
  - Input checks: E1 holds 1,900 rows, with the main configuration as 150 `PRISM_EB` rows and no `PRISM` rows.
    `selections()["PRISM"]` returns them (eps 0.05, 0.03, 0.08, 0.08, 0.08).
  - Table V has PRISM in all four scenarios with n = 5, and `E1_selected_parameters` agrees with `selections()`.
  - All 39 `analyze.py` tables are byte-identical to the verified normal-path tables.
  - `pc_billing_runs.csv`, `pc_billing_bounds.txt`, `r76_matched_1pct.txt` and `E11_erlangb_regenerated.md` are
    byte-identical to the verified regeneration outputs.
  - The E11 table compares Eq. (5) with Erlang-B, and E11's explicit Erlang-B rows equal E1's main configuration run for
    run.
  - The R7.6 endpoints equal `outputs/r76_endpoints_full_precision.json` exactly (difference 0.0).
- Linux rows (E1, E3, E7 and E9 from the Linux rebuild):
  - The same input checks hold (eps 0.08, 0.03, 0.08, 0.08, 0.08).
  - All 37 tables are byte-identical to `outputs/linux_tables/`.
  - `pc_billing_bounds.txt` and `r76_matched_1pct.txt` are identical to `outputs/linux_revision/`.
  - The endpoints, trace counts and unbracketed trace are identical.
- Negative checks of `tools/e11_occupancy.py` both fail with an AssertionError, as intended: E11 rows supplied as E11occ,
  and normalised E1 labels.

**Limits that remain, unchanged by the package:**
- The `scripts/revision/` analyses select PRISM by the literal `'PRISM'`, so the package runs `normalize_labels.py` on a
  copy first. The stock E11 table in `scripts/analyze.py` remains degenerate on the current code, and the E11
  comparison comes from `tools/e11_occupancy.py`.
- `linux_*.sh` assume a WSL home layout (`~/prism_linux`). The experiment rebuild commands in section 4 are full
  simulations, outside this analysis workflow.
- `scripts/check_reproducibility.py` writes into `results/verification/`, so run it in a separate checkout only.

**Release inputs.** The 74 input files listed in `release_inputs.sha256` are packed as
`prism_r36_reproduction_inputs_20261123.tar.gz`. It holds the `windows/` and `linux/` folders under `prism_r36_inputs/`,
plus the manifest, about 42.5 MB. Its SHA-256 is
`52c1c701655a08f17516bae56ae4f92be79b139a19e0b3e18128d05d62f27dd2`. After extraction, 74 of 74 files match the
manifest. It is not in Git and not yet published.

**Still needed for a self-contained release:**
1. Publish that archive with the code. Without it, only the code path is reproducible, not the numbers.
2. Push the branch and give the reviewers access through the editor (author's action).
