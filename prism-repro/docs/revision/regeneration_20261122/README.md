# Regeneration of every stored table at one commit (R3.6, with R5.M7, R5.m4, R7.6, R4.10/R5.m5 inputs)

**PRE-CALIBRATION. Fast simulator, development traces 101-105 (R1: Huawei traces 201-205).** Every number here uses
the assumed `PipelineConfig()`/`PrismConfig()` constants (see `../confirmatory_20261122/CONSTANTS.md`). Submitted
results in `prism-repro/results/` are unchanged (no diff against `v1-submitted`).

- Tree: `private/regen_20261122/prism-repro` (Git-ignored), a `git archive` of fd8b01a with its copy of
  `results/raw`, `results/tables` and `results/figures` removed first, so no step can read a submitted row.
- Environment: one laptop, Windows 11 (10.0.26200), Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0,
  one thread per BLAS library, `PYTHONUTF8=1`. Unit tests in the tree: 124 of 124 pass (`outputs/logs/tests_full.err`).
- Driver: `run_regeneration.sh` (lanes `lane1`, `lane2`, `rest`, `post`); step logs with start, end and exit code in
  `outputs/logs/` (private paths replaced by `<prism-repro>`).
- Outputs: `outputs/tables/` (every regenerated table), `outputs/table_comparison/` (stored vs regenerated, line by
  line), `outputs/r5m4_missing/` (the runs added for R5.m4).

## 1. Unfavourable and null findings first

1. **Released code defect (R3.6(b)).** At fd8b01a, `experiments/run_experiments.py` E3, E7 and E9 crash with
   `KeyError: 'PRISM'` (`outputs/logs/E9_unshimmed_failure.err`): since f119bee PRISM's runs are labelled `PRISM_EB`,
   and `selections()` keys by that label, while E3 (line 212), E7 (302) and E9 (398) look up `sel["PRISM"]`. The
   released code therefore cannot rebuild Tables VIII and X as shipped. Here they ran through
   `run_exp_selection_shim.py`, which changes only that lookup (section 3). A fix in the code release is needed.
2. **E11 table degenerate on the current code.** `E11_erlangb.md` compares PRISM with Eq. (5) against PRISM with
   Erlang-B, but on the current code both arms run Erlang-B (the default since f119bee), so the regenerated table shows
   identical columns (0 differing runs). The genuine comparison is `outputs/tables/revision/E11_erlangb_regenerated.md`
   (Eq. (5) set explicitly; `e11_occupancy.py`): Eq. (5) is 2.5-3.0% cheaper in every scenario, with higher violating
   rates in three of four (stationary 956 / 1.64% vs 981 / 1.55%; new spike 1,237 / 2.26% vs 1,270 / 2.11%), and its
   validation selection sits at the top of the eps grid (0.08) on all five traces.
3. **Headline values change.** 65 of 71 stored table files differ (6 are new). Selected:
   - E1 selections change: PRISM eps 101: 0.02 -> 0.05, 103-105: 0.05 -> 0.08 (102 unchanged at 0.03).
   - Suppl. Table S4 (all test weeks): PRISM 1,267 USD / 1.36% / SLO met 80% -> **1,150 / 1.78% / 60%**. PRISM now costs
     more than QuantProv-q90 (1,142 / 1.95% / 55%), where it cost less before (1,267 vs 1,320).
   - Table V, new spike: PRISM violating windows 1.55 -> **2.11%** (above the 2% target), SLO met 4/5 -> 2/5.
   - Table VI, PRISM minus QuantProv-q90 cost: stored -2.8 to -3.9% (+/-7.5) -> regenerated +1.6, +1.3, 0.0, -0.1%
     (+/-2.2 to 3.5); every interval still includes 0. PRISM minus PredHead+S: +6.1 +/- 5.1% (stationary) to
     +12.5 +/- 6.2% (bursty), PRISM costlier with fewer violating windows, as before.
   - Table XII (Huawei, POST HOC replay): PRISM is no longer the lowest-violating family (PRISM 0.33%, QuantProv-q90
     0.18%); PRISM minus PredHead+S cost +2.1 +/- 0.6% now excludes 0 (PRISM costlier); PRISM minus Reactive
     -22.9 +/- 23.4% now includes 0.
   - T11 overflow estimates, new spike: 1.80% -> 4.26%.
4. **R5.m4 QuantProv memory table is grid-limited.** On the widened grid 36 of 48 POST HOC selections change; 20 of
   48 still sit at a = 0.4 while meeting 2% (all at 2048 MB), so the QuantProv-2048 costs are upper bounds and the stored
   ones overstate what the rule can reach. At non-scaling 0.15 and 14.5 s PRISM (932) and QuantProv-q90 at 2048 MB
   (942, still at the grid edge) are within 1%. This weakens the stored comparison in PRISM's favour.
5. **R7.6 (POST HOC, n = 5): the 1.0% matched-compliance result changes sign of interpretation.** Stored
   -0.36 +/- 3.30% ("not distinguishable"); regenerated **-2.27 +/- 2.02%** (PRISM cheaper; interval -4.29 to -0.25,
   excludes 0; all 5 traces bracketed for both families). Not equivalence: the interval extends below -2%. At 1.5% and
   2.0% the regenerated intervals include 0 (-1.19 +/- 1.95%, -1.07 +/- 1.87%; 4 of 5 traces bracketed, trace 105 not
   bracketed for PRISM). The stored 2.0% "tie" (+0.17 +/- 1.18%) is not reproduced as a tie. The regenerated 1.0%
   value equals the controlled replay at HEAD defaults recorded in
   `docs/revision/matched_compliance_discrepancy/FINDINGS_20261122.md` (-2.27 +/- 2.02%).
6. **First `post` attempt failed** (23 Nov 18:53 UTC; 7 of 18 steps; `outputs/logs/regeneration_post_attempt1_failed.log`):
   label normalisation refused E9's new object array (section 3), and Windows cp1252 text I/O broke `analyze.py` and
   `statistical_meaning.py`. Its outputs are kept, unused, in the tree under
   `results/post_attempt1_failed_20261123T1853Z/`. The second attempt (19:06-19:21 UTC) ran all 18 steps with exit 0.

## 2. What ran

| Step | Script | Rows (regenerated = submitted count) | Wall time |
|---|---|---|---|
| tests | `python -m unittest discover -s tests` | 124 tests OK | 413 s |
| E1, E8 | `run_experiments.py --exp E1/E8 --seeds 101-105` | E1, E8 complete (lane runs, 22 Nov) | |
| E9 | shim, seeds 101-103 | 72 | 2,101 s |
| E12 | `e12_event_retune.py`, seeds 101-105 (101-103 from 22 Nov, resumed per seed) | 395 (5 x 79) | 3,533 s |
| E2, E3 (shim), E10, E4, E6, E7 (shim), E5, E11 | `run_experiments.py` | 20, 110, 1, 172, 40, 180, 540, 150 | 42-1,021 s each |
| E11occ | `e11_occupancy.py run` (new, no submitted counterpart) | 150 | 1,043 s |
| E4b, R2 | `e4b_fixed_memory.py`, `e4b_ondemand.py`, `e4b_prism_eps.py`, `r2_quantprov_memory.py`, seeds 101-102 | 232, 12, 36, 246 per seed | 24-250 s each |
| R1 | `run_real_traces.py` | 765 | 628 s |
| post | normalise labels, `analyze.py` and every revision analysis, level choice, E11 table, R5.m4 runs, supplement, statistical meaning, relabel, R7.6, comparison | 18 steps, exit 0 | 19:06-19:21 UTC |

E1 (1,900 rows) and E8 (1,280 rows) equal the submitted counts. The submitted folders also hold files the scripts
do not write, with no regenerated counterpart: `R1/PROVENANCE_R1.json`, and in E8 a 16-row
`rows_partial_seed101_original_env.jsonl` with a placeholder `arrays_seed101_forecast_original_env.npz`.

## 3. Disclosures: every deviation from running the released scripts unchanged

| Item | Why | Effect on numbers |
|---|---|---|
| `run_exp_selection_shim.py` (E3, E7, E9) | the `KeyError` defect above; reads `PRISM_EB` as `PRISM` in `variant_of` only, refuses if E1 holds both names; `--check` verified every lookup | none beyond making the lookup succeed |
| `normalize_labels.py` | analyses select PRISM by the literal `PRISM`; the analysis copy `results/raw` relabels `PRISM_EB` -> `PRISM` (111 files, 10,958 strings; E11 and E11occ copied byte for byte); originals kept in `results/raw_regenerated`, manifest with SHA-256 before and after | none: labels only (E9 arrays checked identical apart from labels) |
| `normalize_labels.py`, object arrays | E9 at fd8b01a also saves `::sampling_flip_direction` as a 0-d object array (a dict of three floats), absent from the submitted E9; loaded with `allow_pickle=True` (this run's own output) and relabelled element-wise | none |
| `PYTHONUTF8=1` in `run_regeneration.sh` | Windows defaults redirected stdout and `open()` to cp1252; captured tables with "±" and "≤" were then unreadable as UTF-8 | none: text encoding only |
| `level_choice_regenerated.py` | `level_choice_diagnostic.py` hard-codes the submitted selections (`SEL = {101: 0.02, ...}`); the wrapper replaces that one line with the regenerated selections {101: 0.05, 102: 0.03, 103: 0.08, 104: 0.08, 105: 0.08} | the diagnostic re-runs the selected settings: max deviation from the E1 rows 0.0% cost, 0.0 points (determinism check) |
| `relabel_regenerated.py` | `supplement_pertrace_tables.py` and `statistical_meaning.py` print "SUBMITTED"; 6 exact, all-or-nothing replacements to "REGENERATED at fd8b01a" (`outputs/tables/revision/relabel_manifest.json`) | labels only |
| E12 logs | the `rest` step overwrites `E12.out/.err`; the seed 101-103 logs were copied first (`E12_seeds101-103.*` in the tree) | none |
| Process history | lane 1 ran beside C1-C3 for 3.5 h on 22-23 Nov (an orphaned script after a memory reap; E9 failed there and E12 seeds 101-103 completed); every later step ran alone, one at a time | none: CPU and memory only |

## 4. R5.m4: the missing per-trace combinations

`outputs/tables/revision/r5m4_complete_tables.md` (built by `r5m4_tables.py`; EXPLORATORY):
- Ablation table complete: the 20 "not run" cells (no scale-in rule and quantile feasibility, growth and bursty) are
  filled from 20 new runs at each trace's validation-selected eps (`r5m4_missing_runs.py`); the 20 stationary and
  new-spike cells rerun by the same script equal the E3-derived cells in 10 of 10 rows.
- QuantProv memory table: paper-grid and widened-grid selections side by side for 48 cells; finding 4 above.

## 5. R5.M7: claims against the cited tables, stored and regenerated

`r5m7_extract.py` on the stored tables and on `outputs/tables` (POST HOC where marked):

| Claim area | Stored | Regenerated |
|---|---|---|
| Pooled saving vs Static at 1.0/1.5/2.0% (cost) | -13.4 / -16.1 / -17.9% | -12.6 / -16.7 / -18.3% |
| same, with omitted charges (cost_adj) | -10.6 / -13.6 / -15.5% | -10.0 / -14.4 / -16.1% |
| vs Reactive (cost) | -26.9 / -28.5 / -28.9% | -23.5 / -25.7 / -26.9% |
| Per trace vs Static at 1.0% | -11.5, -17.2, -0.2, -13.3, -22.1 | -16.2, -13.5, -5.6, -10.3, -19.4 |
| "Within 1.6%": vs QuantProv-q90 | -1.4 / -0.0 / +1.2% | -1.5 / -1.6 / -1.1% |
| "Within 1.6%": vs PredHead+hyst | -1.3 / +0.1 / +1.5% | -2.3 / -1.2 / +1.6% |
| Table VII at 1.5%, largest per-scenario gaps | +3.56 (new spike, vs PredHead+hyst), -2.92 (bursty, vs QuantProv-q90) | +1.65 (stationary, vs PredHead+hyst), -2.17 (new spike, vs QuantProv-q90) |
| Table VI vs QuantProv-q90: every interval includes 0 | yes | yes |
| Table XII vs QuantProv-q90 | +2.4 +/- 4.0%, includes 0 | +1.6 +/- 4.0%, includes 0 |
| Huawei lowest-violating family | PRISM | **QuantProv-q90** |
| Huawei: PRISM cost vs both QuantProv rules | above both | above both |
| Synthetic S4: PRISM cost vs QuantProv-q90 / q99 | below / below | **above** / below |

The confirmatory C1 (`../confirmatory_20261122/RESULTS.md`) adds: PRISM minus QuantProv-q90 +0.30% [-1.42, +2.01] on
25 traces, not distinguishable and not a tie. Wording that implies a cost advantage over QuantProv-q90, or that PRISM
is the lowest-violating family on the Huawei traces, is not supported by the regenerated or confirmatory values.

## 6. R4.10 and R5.m5

`../graphical_abstract_20261122/caption.md` section 4 and `inputs_regenerated.csv`: new-spike violating windows
PRISM 2.11%, smoothed headroom 4.11%, unsmoothed headroom 7.92% (submitted 1.55 / 3.24 / 6.67%); caption range
13-27% (submitted 14-29%).

## 7. Commands

```
# from prism-repro/, with absolute paths
bash docs/revision/regeneration_20261122/run_regeneration.sh <tree>/prism-repro <prism-repro>/venv/Scripts/python rest
REPO_ROOT=<prism-repro> bash docs/revision/regeneration_20261122/run_regeneration.sh <tree>/prism-repro <python> post
python docs/revision/regeneration_20261122/r5m4_tables.py <tree>/prism-repro <tree>/prism-repro/results/tables/revision/r5m4_complete_tables.md
python docs/revision/regeneration_20261122/r5m7_extract.py <root> <out.json>      # stored root and regenerated tree
```

Checksums: `SHA256SUMS` (LF) in this folder covers the scripts and `outputs/`.

## 8. Final audit additions (23 Nov 2026; `../confirmatory_20261122/FINAL_AUDIT_20261123.md`)

- **Platform.** This regeneration ran on Windows 11. `REPRODUCE.md` and `KNOWN_ISSUES.md` name Linux x86-64 as the
  reference platform for forecast-driven results, which are not bit-reproducible across platforms. Which platform the
  reported tables come from is an open decision. Where they overlap, the values here equal the earlier current-code
  analyses on the same laptop (Table VI, Table XII, 1.0% matched).
- **Causes of the shifts.** Only the 1.0% matched comparison is decomposed
  (`../matched_compliance_discrepancy/FINDINGS_20261122.md`): exact attainment (1ab053c) and the Erlang-B default
  (f119bee), with a residual -0.32 points between the Linux stored rows and the same code here, not attributed. The
  other tables were not decomposed.
- **Tables built from the shimmed drivers.** These values are verified, but the released scripts cannot rebuild them
  until the lookup is fixed.
  - E3: Table VIII, `E3_quantile_vs_scenario_feasibility`, `T14_hysteresis`.
  - E7: `T20_feature_ablation`.
  - E9: Table X (`T10_fast_vs_event`, `T10b`, `T11`) and the `E9_*` tables.
  - From E3: the ablation half of the per-trace supplement and of `r5m4_complete_tables.md`.
- **Other material changes.**
  - Table X, PRISM violating windows: 1.44% in the fast simulator and 3.75% at event level (submitted) become 1.69%
    and 6.14% (regenerated).
  - E1: PRISM is selected at eps 0.08, the top of its grid, on traces 103-105.
  - Table XII: PRISM is at eps 0.08 on 4 of 5 traces.
- **E11 rows.**
  - The stock E11 runs only the explicit Erlang-B arm (150 rows), which equals E1's default PRISM run for run.
  - E11occ supplies the Eq. (5) arm (150 rows, `risk_model: occupancy`).

## 9. Superseded workarounds (23 Nov 2026)

The E3/E7/E9 lookup defect is fixed in the release path (`experiments/run_experiments.py`, `scripts/analyze.py`;
uncommitted), so `run_exp_selection_shim.py` and, for `scripts/analyze.py`, `normalize_labels.py` are no longer needed.
The fixed code reproduces this regeneration's E3, E7 and E9 rows and arrays, and 51 of 53 tables byte for byte (2 differ
only in measured decision time). The stored results reproduce exactly on Linux x86-64; this Windows regeneration differs
from a Linux one for every forecast-driven run. See `../label_fix_20261123/README.md`.
