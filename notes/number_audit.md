# Number audit for the response to reviewers

Branch `phase-e-review`, 21 Nov 2026. Every figure the response material relies on, with the command, commit,
configuration, input, environment and output that support it, or the reason it is not supported. Figures
marked *reported* come from another session's Linux sandbox and are not reproduced here. Paths are relative
to `prism-repro/` unless they start with `notes/`.

**Naming rule.** Two unrelated quantities both round to 1.92%: the *Erlang-B relative error* (R3.4, R4.9) and the
*end-to-end integer-search saving* (R2.13). Never print either without its name, and never next to the other.

## 0. Session record

| Item | Value |
|---|---|
| Branch, start | `phase-e-review` at `8bf6152` (13 local commits over `main` = `2bdeaba`); no upstream; never pushed |
| Worktree at start | clean, no stash, no untracked files |
| Test environment | Windows 11 Pro 10.0.26200, Python 3.12.9 (MSC v.1942), `prism-repro/venv` = `requirements.txt` pins (numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, scikit-learn 1.8.0, matplotlib 3.10.8); Intel i5-10310U (4 cores, 8 threads, AVX2, no AVX-512), 16 GB; Git 2.56.0.windows.4, `core.autocrlf=true` |
| Baseline suite | `python -m unittest discover -s tests -v` → 77 tests, OK, 60 s |
| Frozen items | `results/`, `CHECKSUMS.sha256`, tag `v1-submitted` = `3b4bc33`: unchanged (checked at the end of the pass) |
| Tracker | read only; SHA-256 `337CEC16AC09BDC592A1A26260974776BC001308D6A46273AE1E96126DBCAC4A` at the start and at the end; backup `C:\Users\<user>\PRISM_tracker_backups\PRISM_Tracker_20261121T070431Z.xlsx` (same hash) |

## 1. Unfavourable findings and open discrepancies (read first)

1. **The published level-choice count does not reproduce on Windows.** The documented diagnostic, run unmodified
   from `git archive 3b4bc33`, gives **10 of 40,280** feasible epochs here, not 16 of 40,293 (section 5). The 16 of
   40,293 reproduced exactly in the author's Linux / Python 3.13.18 run (*reported*).
2. **Forecast-driven runs are platform-dependent at identical code and package pins.** From the archived submitted
   tree on Windows, `scripts/check_reproducibility.py` reproduces 3 of 6 stored E1 runs: the three without a
   forecaster bit for bit, PredHead, QuantProv and PRISM not (PRISM-0.05, seed 101, stationary: USD 1,017.03 against
   1,034.95 stored). PRISM's cost differs from E1 by up to 4.1% across 20 runs. Traces are bit-identical; one
   OpenMP thread and disabling numpy's AVX2/FMA3 dispatch change nothing. Root cause not isolated.
3. **The submitted configuration misses the weekly target in 8 of 20 held-out weeks on current code**, although
   its pooled rate is 1.78% (section 6).
4. **The `integer_search_e2e.py` script behind the end-to-end integer-search saving is not on this machine**, so the
   1.92% figure is *reported* only (Linux sandbox; never run on Windows). Its own table shows **two** crossings of
   the 2% target, not one (section 4).
5. **"Binds in 97-99.7% of epochs" is wrong at the low end and mislabelled**: 96.6-99.7% of epochs *in which
   decide() returned a feasible decision* had a cheaper per-stage vector under the same per-epoch rule (section 4).
6. **The response draft states as done much work that is not done** (section 9): platform measurements, the closed
   loop, regenerated tables, the memory-adaptive and hybrid-histogram baselines, the frozen prespecification,
   warm-start retuning, per-quantile retuning, and manuscript rewrites.
7. **Unexplained:** in the lag sweep, Reactive's compliance improves as the lag grows (9, 13, 16 of 20 weeks at
   L = 2, 5, 10 min). Not investigated further; flagged for the closed-loop rerun.
8. **Warm-up does not warm.** A 7-day in-sample warm-up leaves the conformal offset at 0.04 at the start of
   validation, against 0.19-0.34 out of sample (section 7).

## 2. Checksum verification (R2.16, R3.6, R7.7)

Fix: `efcfd12` (`scripts/build_manifest.py --verify`; test `tests/test_manifest_verify.py`, 8 tests). Fresh clone:
`git clone -c core.autocrlf=true --branch phase-e-review <repo> <tmp>`, worktrees at `v1-submitted` and
`origin/main`; every working copy is `i/lf w/crlf` and `git status` clean. Counting harness:
`docs/revision/checksums/checksum_counts.py <checkout> <branch>/prism-repro/scripts`.

| Tree (commit) | Committed blobs (LF, `git cat-file`) | Old verifier: raw working-copy bytes | Fixed verifier |
|---|---|---|---|
| `v1-submitted` (`3b4bc33`) | 0 | 201 of 290 | 0 mismatches (89 byte-identical, 201 CRLF-normalised) |
| `main` (`2bdeaba`) | 13 | 201 | 13 (89 / 188) |
| `phase-e-review` (`efcfd12`) | 20 | 201 | 20 (89 / 181) |

In every tree the fixed verifier flags exactly the files whose committed content differs from the manifest. In the
branch clone, appending one line to `src/prism_repro/workload.py`, deleting
`data/fixtures/example_trace_SYNTHETIC_seed7_day1.csv` and flipping one byte of `results/raw/E2/arrays_seed101.npz`
gave `MISMATCH`, `MISSING`, `MISMATCH` and exit code 1. 52 of the 89 binary files contain CRLF byte pairs and are
never normalised. The earlier "23 mismatches" figure is retracted.

Genuine mismatches are files changed after submission, each by a named commit: on `main` the 13 are `.gitignore`
(`e28ab91`), `KNOWN_ISSUES.md` (`82463a1`), `docs/TEST_REPORT.md`, `patches/README.md` (`012bc3e`, `2bdeaba`),
`scripts/revision/pc_billing_bounds.py`, `src/prism_repro/{config,des,latency,optimizer,policies,simulator}.py`,
`tests/test_controller.py` and `tests/test_des_online.py` (`33d1000` patch, `f119bee` Erlang-B, `44ef122` ranking,
`1ab053c` exact attainment, `e3faa6c`, `e160490`, `8e6f60c`, `c7360fe`). The branch adds `README.md`,
`scripts/build_manifest.py`, `src/prism_repro/{experiment,features,forecast}.py`, `tests/test_analytic.py` and
`tests/test_simulation.py` (branch commits). The manifest is rebuilt only at the regeneration.

## 3. Regression anchors

All pinned by `tests/test_regression_anchors.py` (`bc548e7`) at the printed precision.

| Figure | Cited | Verified here | Command, configuration, input |
|---|---|---|---|
| Event-level overflow share at P = c = 40 | 0.118431 | 0.1184306 (28,567 of 241,213 stage executions on demand) | `tests/test_des_online.py::test_erlangb_accuracy_vs_eq5_gap`: Poisson(600) counts for 400 min (`default_rng(0)`), `EventDraws(cfg, counts, 3, 0)`, stage mean 4.0 s, init 6.0 s, keep-alive 600 s, 40 provisioned |
| Erlang-B B(40, 40) | 0.116156 | 0.1161560 | `risk.erlang_b(40, 40)` |
| **Erlang-B relative error** | 1.92% | 1.9206% from full precision (1.9209% from the six-decimal inputs; both round to 1.92%) | as above |
| Eq. (5) at c_eff | 0.144785 | 0.1447851, c_eff(40) = 46.0056 | `risk.occupancy_overflow(40, c_eff(40))` |
| Eq. (5) relative error | 22.25% | 22.2532% full precision (22.2526% from rounded inputs) | as above |
| Impossible initialisations, 1024 MB | 3.20% | 3.20% analytic; 3.20% in `EventDraws(seed 3)`; 3.21% in 2M draws | P(6.0 s x lognormal(sigma 0.3) > 10 s); `tests/test_analytic.py::TestTruncatedInit` |
| Impossible initialisations, 512 MB | 16.40% | 16.40% analytic (mean 7.8 s) | as above |
| rho at 1024 / 2048 MB | 0.53 / 0.09 | 0.531 / 0.094 | `latency.miss_probabilities`, default config; `tests/test_analytic.py::TestInitScalingDirection` |

## 4. Optimizer evidence: three different percentages

| | **End-to-end integer-search saving** | Static per-epoch gap | Stage-demand common-demand baseline |
|---|---|---|---|
| Value | 1.92% mean, range 1.53-2.66% (*reported*) | 2.71% mean, range 1.52-5.90% | 2.90% mean |
| What | six offline test-week replays: PRISM's feasible vector refined each epoch by integer search under the same per-epoch rule, against unchanged PRISM | integer coordinate descent from PRISM's chosen vector, one static epoch per configuration | same search, demand equal at every stage (the paper's setting) |
| Configurations | seeds 101-103 x {stationary, new_spike}, test weeks, E1-selected eps (101: 0.02, 102: 0.03, 103: 0.05), corrected code | 16: eps {0.005, 0.01, 0.02, 0.05} x memory {1024, 2048} x two demand sets | eps {0.01, 0.02, 0.05} at 1024 MB |
| Command | `scripts/revision/integer_search_e2e.py` (author's script; not on this machine) | `python scripts/revision/integer_search_gap.py . <out.json>` (4 s) | `python scripts/revision/stage_demand_gap.py . <out.json>` (6 s) |
| Environment | one Linux sandbox, Python 3.13.18 | Windows (this pass) | Windows (this pass) |

**End-to-end table (author's run, transcribed from the session record).** PRISM cost / searched cost / saving /
violating windows base -> searched / epochs improved of epochs with a feasible decision:
101 stationary 1113.57 / 1093.51 / 1.80% / 0.74% -> 0.74% / 1947 of 2015 (96.63%);
101 new_spike 1400.87 / 1379.40 / 1.53% / 0.60% -> 0.89% / 1959 of 2015 (97.22%);
102 stationary 1110.51 / 1093.52 / 1.53% / 0.74% -> 0.89% / 1952 of 2015 (96.87%);
102 new_spike 1430.69 / 1406.18 / 1.71% / 0.74% -> 0.74% / 1954 of 2014 (97.02%);
103 stationary 998.31 / 971.79 / 2.66% / 1.93% -> 2.38% / 2010 of 2016 (99.70%);
103 new_spike 1306.70 / 1276.97 / 2.28% / 1.79% -> 2.08% / 1998 of 2016 (99.11%).
Recomputed from these costs: mean saving 1.918%, range 1.53-2.66%. Compliance worse in 4 of 6 runs.
**Crossings verified from this table: two.** 103/stationary 1.93% (13 of 672 windows, meets) -> 2.38% (16,
misses), and also 103/new_spike 1.79% (12) -> 2.08% (14, misses). The response must state both.

**"Binds" correction.** The six "epochs improved" shares are 96.63, 97.22, 96.87, 97.02, 99.70 and 99.11%, i.e.
**96.6-99.7%**, and the denominator is the 2,014-2,016 epochs per run in which `decide()` returned a feasible
decision, not all 2,016. What they measure: a cheaper per-stage vector satisfying the same per-epoch feasibility rule
existed. They do not show a binding constraint, and the end-to-end cost of using those vectors is the 1.92% above.

**Independent check on Windows (different code, not the author's script).**
`python scripts/revision/integer_search_e2e_check.py . <out.json>` (`50ac42f`; output
`docs/revision/integer_search_e2e/e2e_check_windows.json`, 6.5 min): mean saving 1.88% (1.19-2.95%), compliance
worse in 4 of 6, one crossing (103/new_spike 1.79% -> 2.53%; 103/stationary already misses in its base run,
2.08% -> 2.23%). Supports no claim about the author's script on any platform.

**Fan-out (scoped).** Profile `fanout_x3_at_3` (stages 3-4 see three times stage 1's records), eps {0.01, 0.02,
0.05}, 1024 MB, the four-quantile demand set of `stage_demand_gap.py`: no member of the one-parameter family is
feasible at the paper's candidate bound `level_hi` = 1.15 for any eps tested; with `level_hi` = 4.0 and eps 0.02
the family's cheapest feasible member costs 17.40% more than the searched vector. Filter-50%-at-stage-2: 5.06%;
batch-10:1-at-stage-4: 5.78%; common: 2.90%. These are static benchmarks on one profile each.

## 5. Level-choice statistic (R2.17, R5.M6, R4.1, R6.7, R7.1)

Every run set: 20 PRISM test weeks (seeds 101-105 x 4 scenarios, E1-selected eps), 2,016 epochs each, **40,320
epochs**. Command: `python scripts/revision/level_choice_diagnostic.py <code_root> <out.json>`.

| Code | Environment | No feasible candidate | Feasible | Above smallest feasible | Share of feasible | Source |
|---|---|---|---|---|---|---|
| Submitted tree (`3b4bc33`) | Linux, Python 3.13.18 | 27 | 40,293 | **16** | 0.040% | published; stored `results/tables/revision/level_choice_diagnostic.json`; reproduced exactly from an archived tree (*reported*, author's run) |
| Corrected `main` | Linux, Python 3.13.18 | 11 | 40,309 | 22 | 0.055% | *reported*, same run |
| Submitted tree (`git archive 3b4bc33`) | Windows, Python 3.12.9, pinned | 40 | 40,280 | 10 | 0.025% | `docs/revision/level_choice/diagnostic_v1_archive_windows.json` |
| Current code, `risk_model` overridden to Eq. (5) | Windows | 40 | 40,280 | 10 | 0.025% | `docs/revision/level_choice/diagnostic_current_code_eq5_override_windows.json`; identical to the row above run by run, cost bit-identical in all 20 runs |
| Corrected code (`efcfd12`) | Windows | 13 | 40,307 | 26 | 0.065% | `docs/revision/level_choice/margins_branch_windows.json` |

**Instrumented** (`scripts/revision/level_choice_margins.py`, `e95fd8d`; decisions unchanged, both Windows rows
reproduced exactly): every above-smallest choice saves 1.0e-5 to 5.6e-3 of the epoch's expected cost (median
5.4e-4 corrected, 2.1e-3 submitted); no feasible epoch has a best-versus-second-best cost gap below 1e-9; no
decision changes when eps is scaled by 1 +- 1e-9. These are not floating-point near-ties. The archived tree's
per-epoch schedules differ from the stored E1 schedules in 1,469-1,981 of 2,016 epochs per run: the platform
changes the forecast-driven inputs. No dependency version is identified as the cause.

**Cite:** "16 of 40,293 feasible epochs" for the submitted code (Linux, Python 3.13.18). For corrected code, "fewer
than 0.07% of the epochs with a feasible candidate (40,320 epochs per run set), in every environment tested"
(largest observed share 26 of 40,307 = 0.065%).

**Correction (21 Nov 2026).** That bound is for the selections the diagnostic fixes, `SEL = {101: 0.02, 102: 0.03,
103: 0.05, 104: 0.05, 105: 0.05}` (the submitted run's). In `scripts/revision/stage_demand_e2e.py` (common demand,
each eps on all 20 test weeks, current code, Windows) the above-smallest counts are: eps 0.005 and 0.01, none;
0.02, 31 of 40,278 (0.077%); 0.03, 43 of 40,307 (0.107%); 0.05, 28 of 40,317 (0.069%); 0.08, the top of the grid,
9,548 of 40,320 (23.7%). Current code's own validation selects 0.08 for traces 103-105, and at its selections
(0.05, 0.03, 0.08, 0.08, 0.08) 5,908 of 40,316 feasible epochs (14.7%) are above the smallest. So "below 0.07%"
holds for the diagnostic's per-trace eps, not for every eps up to 0.05 (at most 0.11% there), and not at 0.08.
Cite the bound only with its eps values.

## 6. Cold-hit floor and weekly compliance (R2.12, R2.4)

Rows: `docs/revision/kappa_floor/rows_{101..105}.jsonl` (`8d8a816`; `python scripts/revision/kappa_floor_retune.py .
<out_dir>`, 300 runs, 16 min, Windows, current code, fast simulator, pre-calibration).

| Comparison | Floor 0.001 vs 0.1 |
|---|---|
| Validation-selected eps, held-out test weeks | cost +12.3% (paired, +1.3 to +23.0%, 20 weeks); pooled violating windows 0.99% vs 1.78%; weeks meeting 2%: 20/20 vs 12/20 |
| Post hoc matched compliance (frontier over eps) | +2.8% at 1.0% (5/5 traces), +3.6% at 1.5% (4/5), +3.7% at 2.0% (4/5) |
| Earlier fixed-eps diagnostic (13-21% cheaper without the floor) | superseded; do not cite |

**Weekly target.** A window violates when fewer than 99% of its records meet the deadline; a week meets the target
when at most 2% of its 672 windows violate (13.44 windows, so 13 is the allowance). The 1.78% is the mean of 20
weekly rates, equal to the pooled 239 of 13,440 windows. Misses (`docs/revision/kappa_floor/weekly_compliance.txt`,
`python scripts/revision/weekly_compliance.py .`): 103 stationary 17, growth 16, bursty 20, new_spike 23; 104
stationary 15, bursty 21, new_spike 17; 105 new_spike 16 windows. All eight are at eps = 0.08, the top of the grid,
chosen on validation with 9-12 violating windows; all eight weeks at an interior eps met the target; mean kappa
0.101-0.108 in missed and met weeks alike. Association, not cause. Post hoc alternatives on the same weeks (not a
validation): validation margin 1.5% cost +4.6%, 15/20; cap eps at 0.05 +5.3%, 18/20; uniform 0.03 +11.5%, 20/20;
uniform 0.02 +16.1%, 20/20.

## 7. Other figures produced in this branch

| Figure | Value | Source |
|---|---|---|
| eps -> violating-window mapping, stored E1 rows | monotone (Spearman 1.0); 95% PI held-out coverage 98.3% (val -> test, 120 weeks), 97.5% (leave one trace out); only eps 0.005 has upper PI <= 2% | `python scripts/revision/eps_window_mapping.py . results/raw/E1/rows.jsonl` (`637596a`) |
| same, current-code rows | coverage 96.7% / 96.7%; operator rule eps 0.02 | `docs/revision/kappa_floor/eps_mapping_current_code.txt` |
| q0.9 coverage, shared vs independent offsets | held-out test weeks: stationary 98.0% -> 89.9%, new spike 92.4% -> 89.8%; q0.99 unchanged | `4702440`; GBM, seeds 101-105 |
| Conformal offset at validation start, 7-day warm-up | 0.04 (four traces), -0.01 (105); without warm-up 0; out of sample 0.19-0.34 | `92d304c` |
| rho at 2048 MB by init direction | 0.094 Eq. (3), 0.196 constant, 0.350 inverted | `131f024` |
| Truncation at 10 s | rho(1024) 0.531 -> 0.515; rho(2048) 0.094 -> 0.087 | `a0a7916` |
| Lag sweep (pre-calibration) | PRISM USD 1,150 / 1,182 / 1,167 at L = 2 / 5 / 10, -25.8 / -25.0 / -24.5% vs Reactive; offset x1.48 / x1.56 / x1.66 | `docs/revision/sensitivity/summary.txt` (`a4187f7`) |
| Init direction (pre-calibration) | D = 12 s: >= 2048 MB in every epoch under all three directions, violating windows 0.00 / 0.07 / 0.30%, cost +3.4% (constant), +5.4% (inverted) vs Eq. (3); D = 13 s: ~96% violating, memory stays at 1024 MB (eps 0.02 > v_w(1024) = 1.18%) | same |
| Grid edges | E1 validation 0 of 40; E12 6 of 30; R1 25 of 40 (PRISM eps 0.08 and headroom h 1.0 in 4 of 5 traces); E1 test-week post hoc 23 of 160 (PredHead h 2.0 under new spike in 5 of 5) | `python scripts/revision/grid_edge_audit.py . <rows>` (`fb8b360`) |
| Trace set | 30 seeds (101-130); 9 of 10 properties unflagged; new-spike mass ratio flagged at a 0.1% scale | `data/trace_set_revision.json` (`4c43769`) |

## 8. Figures quoted from the paper, traced to stored outputs

Not recomputed in this pass; values read from the stored tables of the submitted code.

| Figure | Stored source |
|---|---|
| PRISM violating windows 1.44% fast -> 3.75% event level, same schedules | `results/tables/T10_fast_vs_event.md` |
| New spike: PRISM 1.55%, PredHead+S 3.24%, PredHead 6.67% | `results/tables/T5_test_weeks.md` |
| Table IX: eps 0.02 -> 0.01 at D = 13 s, memory fixed: USD 1,247 -> 940, 70.01% -> 79.46% | `results/tables/T8_memory_regimes.md` |
| Sampling flips 1.0-9.6% of windows; in-flight maximum 1.48-1.5x the peak draw at the median | `results/tables/E9_inflight_and_sampling.md` |
| Calibrated q0.9 coverage 92.1-98.1% (97-98% in three scenarios) | `results/tables/T4_forecast_coverage.md` |
| Huawei replay: PRISM 0.39% violating windows | `results/tables/R1_real_traces.md` |
| Event-level retuning (E12): PRISM met the target in 13 of 20 weeks, ~2.02% | `results/tables/revision/E12_event_level_retuning_analysis.txt` (per-scenario meet counts) |
| 13-29% saving, 0.2-22% per trace, 11-16% with omitted charges, ~1.6% / ~4% matched-compliance spreads, 14-29% fixed-2048 headroom, 0.74 points under scikit-learn 1.9.1, 32 hours to the kappa floor, 395 replays | located in `results/tables/revision/` and `results/raw/E4b/` analyses but not individually re-read in this pass |

## 9. Response draft: numbers and claims (Claude doc "PRISM — IEEE Access Response to Reviewers", rev 10, read only)

Numbers in the draft are almost all reviewer quotations of the paper (section 8) or plan bookkeeping (task numbers,
hours, the 73 / 66 / 7 counts, which are verified against the tracker and the plan). The draft is written ahead of
the work. Statements it makes as done that are **not supported now**:

| Entries | Statement | Status now |
|---|---|---|
| Letter to the editor; R2.1, R2.2, R3.3, R4.2, R5.M1, R6.3, R6.4 | closed-loop event-level primary evaluation, every family retuned on widened grids | not done; only open-loop telemetry instrumentation exists |
| Letter; R2.15, R3.6 | every table regenerated from one corrected build, registry diff | not done; regeneration waits for the AWS constants |
| R1.2, R1.3, R2.8, R3.1, R4.3, R5.M2, R6.1, R6.2, R2.14, R2.20 | platform deployment, measured init (five sizes, >= 200 cold starts), lag, overflow, bill | not done (AWS) |
| R2.1 | "corrected two defects ... initialization occupied no environments" | exact attainment done (`1ab053c`); initialization occupancy is still absent from the fast simulator |
| R2.4 | failure analysis | partial: per-week analysis of the fast-simulator replay (section 6); event-level analysis pending |
| R2.5, R4.1 | "tested ... utilization above break-even with a wider eps grid" | not done (stage-specific demand and integer search done, static only) |
| R2.6, R3.7, R7.4 | memory-adaptive baseline added | not done |
| R3.2 | hybrid histogram baseline added | not done |
| R2.18, R3.5, R6.6 | prespecification frozen; 30 traces run | 30 seeds recorded (`4c43769`); nothing run on 106-130; prespecification not frozen |
| R4.6, R5.M3 | warm offset, retuning done | option implemented; in-sample warm-up ineffective (section 1); retuning not run |
| R4.7, R5.M4 | grids widened, edge gate | audit and `GRIDS_WIDE` exist; no run uses them |
| R4.8 | "corrected: truncated" | implemented and gated, off by default until the measured fit |
| R2.11 | sweep run; rule renamed | independent offsets implemented and evidenced (section 7); sweep not run; rename is manuscript work |
| R2.16, R5.M6 | Table VI under both scikit-learn versions | not done; also add the platform dependence (section 1, item 2) |
| R2.22, R3.8, R4.10, R4.11, R5.M7, R5.m1-m5, R5.R, R7.6 | manuscript rewritten | manuscript not edited; proposals in `notes/manuscript_proposals.md` |
| R4.1, R7.1 | "16 of 40,293" (reviewer quote) | correct for the submitted code on Linux / Python 3.13.18; see section 5 for how to cite corrected code |

Supported as written: R3.4 and R4.9 (Erlang-B is the main configuration, Eq. (5) behind a flag, gate within 2.5%:
`f119bee`, `e160490`; the **Erlang-B relative error** is 1.92%, Eq. (5) 22.25%); R5.M5 (infeasible candidates ranked
by violation quantile and an eps-monotonicity test: `44ef122`, `8e6f60c`); R4.2 and R5.M1, exact-attainment part
only (`1ab053c`); the draft's rho 0.53 -> 0.09.
