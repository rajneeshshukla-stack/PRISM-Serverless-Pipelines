# Test report (software verification)

**Latest full run:** 2026-10-29, `python -m unittest discover -s tests -v` → **48 tests, all passed** (45 s, reference sandbox, Python 3.12.3). Raw output: `results/test_report_full.txt`.

This is software verification only: it shows that the code implements the stated formulas and behaves as specified. It does **not** validate the scientific conclusions.

| Module | What is checked | Oracle |
|---|---|---|
| `test_analytic.py` | Occupancy o(P,c) and Erlang-B vs brute-force sums and the standard recursion; manuscript §3.2 values (C01); monotonicity; zero load; c_eff vs the simulator's own upper-45 % sampling (C05); Eq. 4 limits; Eq. 2 scaling (C03); log-normal mean; Table 3 miss probabilities (C06, Monte Carlo with independent seeds); break-even 60 % and cost indifference at break-even (C02); hand-computed stage cost; exponential-tail exactness (C04); 0.149 pp per window (C39) | independent closed forms, brute force, hand calculation |
| `test_controller.py` | Quantile ordering for every offset in [−0.3, 0.8] and for upper quantiles far below the median (C08); conformal long-run miss rate ≈1 %, two-epoch delay, clipping; vectorised optimiser = scalar loop reference on random cases; zero demand → no provisioning; infeasibility flag and cap; quantile-mode feasibility ≡ scenario-mode (monotone risk); non-monotone cost in P; hysteresis drain ≤ 8 epochs (C07); window-peak target; no look-ahead in features; zero-demand floor | scalar re-implementation, constructed cases |
| `test_simulation.py` | Workload determinism, synthetic label, identical first 21 days, mean rate, growth and spike multipliers, extra burst mass; fast-simulator keep-alive/cold-start hand trace; full provisioning → no on-demand cost; total cost vs independent Eq. 5 computation; invariants (cold ≤ overflow ≤ arrivals, utilisation ∈ [0,1]); determinism and common random numbers; window attainment, run lengths, weighted quantile vs sort; §5.3 selection rule | hand traces, independent formula |
| `test_des_online.py` | Event-level routing hand traces (cold occupancy, keep-alive expiry, LIFO reuse, provisioned loss routing); overflow share of a Poisson stream into P = c = 40 servers vs Erlang-B; in-flight sweep vs brute force; pipeline determinism and bounds; online single-step features = batch features (C31) | Erlang-B theory, brute force |

## Failures found during development (preserved)

| Date | Test | Cause | Resolution |
|---|---|---|---|
| 2026-10-29 | `test_delay_two_epochs` | Test was wrong: it ignored that hits also move the offset (−γ·0.01) | Test rewritten to compare runs with and without the miss |
| 2026-10-29 | `test_cost_not_monotone_in_P` | Test was wrong: its demand grid never passed the break-even utilisation | Wider demand grid |
| 2026-10-29 | `test_provisioned_covers_all` | Test fixture inconsistent (K=10 with 1,000 arrivals/min gives utilisation > 1) | Consistent fixture (100 arrivals/min) |
| 2026-10-30 | (analysis) `scripts/analyze.py` row de-duplication | Real defect found by inspecting the E7 table: rows without a `run_id` (forecast-only rows in E7/E8) were all treated as duplicates, so only one forecaster row per trace survived. E1–E4, E6, E9 and E10 tables unaffected; E2 unaffected (no `run_id` column). The archive delivered before the fix contained an incorrect `T20_feature_ablation` table (then based on 1 of 5 traces). | Fixed; rows without `run_id` are keyed by (seed, scenario, forecaster, label, tag) |
| 2026-10-30 | (analysis) `scripts/build_claim_matrix.py` | Crashed (helper used before definition), leaving a stale matrix; separately, the C35 rule could emit a verdict from NaN values of an incomplete experiment | Fixed; verdicts on experiments with fewer traces than planned are now reported as NOT-EXECUTED (k/n traces) |
| 2026-10-29 | `test_inflight_sweep` | Expected value in the test was wrong, **and** the implementation ignored the in-flight level carried into a minute with only departures (real defect) | Implementation fixed before any E9 run; brute-force oracle added |

## Reproducibility checks

`scripts/check_reproducibility.py --seed 101` re-simulated six stored E1 runs (one per policy family, trace 101, stationary test week) that were produced before later code edits; all six were **bit-identical** (`results/verification/`).

## Not tested

GitHub Actions workflow and Dockerfile (no runner/Docker available); installation from `requirements.txt` in a fresh virtual environment (no network; packages were preinstalled); platforms other than Linux x86-64; Python versions other than 3.12.3; the CSV trace loader on any real trace.
