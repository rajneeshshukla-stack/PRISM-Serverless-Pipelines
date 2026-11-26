# C1-C3 confirmatory results (seeds 106-130), PRE-CALIBRATION

**PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION.** Every job uses the `PipelineConfig()`/`PrismConfig()` defaults at
a10efe6, which are assumed, not measured (see `CONSTANTS.md`; in particular the modelled 6 s application start-up is
not the measured Lambda Init Duration of about 115 ms, and P3 is open). The analysis is the one frozen in
`docs/revision/PRESPECIFICATION.md` (d16fbea, 21 Nov 2026 11:54 CST), which predates the first week on seeds 106-130
(22 Nov 2026 22:49:32 UTC). Sources: `run/summary.txt`, `run/tables/*.csv`, `run/analysis_checks.json`,
`checks/verify_run_final.txt`.

Reading the calls (prespecification section 5): *difference* = 95% t interval over 25 traces excludes 0;
*tie* = interval within +/-2%; *similar compliance* = violating-window interval within +/-0.5 points, otherwise the
cost comparison is confounded. Differences are PRISM minus comparator.

## Unfavourable and null results first

1. **C3 (PRISM vs MemAdapt-q90, 12 s deadline, stationary): PRISM is costlier, and the cost comparison is confounded.**
   Cost +13.06% [+8.50, +17.63] (difference: PRISM costlier; 21 of 25 traces costlier). Violating windows
   -0.655 points [-0.921, -0.389]: PRISM violates fewer windows, outside the +/-0.5-point band, so by the frozen rule
   the cost comparison is confounded by compliance. These runs do not show whether PRISM is costlier at equal
   compliance. No claim of a cost advantage over MemAdapt-q90 can be made from C3.
2. **C1 (PRISM vs QuantProv-q90, 14.5 s, four scenarios): not distinguishable, and not a tie.** Cost +0.30%
   [-1.42, +2.01]. The interval includes 0, so there is no difference; its upper end (+2.011%) exceeds +2% by
   0.011 points, so the tie criterion is **not** met and equivalence cannot be claimed. Compliance is similar:
   -0.106 points [-0.274, +0.062]. Traces: PRISM cheaper 11, costlier 14.
   - EXPLORATORY per scenario (not part of C1): stationary +2.23% [+0.40, +4.06] (PRISM costlier, 20 of 25 traces);
     growth +0.08%; bursty +0.21%; new_spike -0.81%; only stationary excludes 0.
3. **Held-out misses of the 2% target (test weeks, pooled per trace):**

   | Set | Family | Weeks meeting 2% | Traces with pooled violating rate above 2% |
   |---|---|---|---|
   | C1/C2 | PRISM | 81 of 100 | 5 of 25 (106: 2.01%, 114: 2.79%, 115: 2.01%, 126: 2.64%, 127: 2.42%) |
   | C1/C2 | QuantProv-q90 | 72 of 100 | 7 of 25 |
   | C1/C2 | Reactive | 75 of 100 | 5 of 25 |
   | C3 | PRISM | 24 of 25 | 1 of 25 (106: 2.23%) |
   | C3 | MemAdapt-q90 | 17 of 25 | 8 of 25 |

   Every family, PRISM included, misses the target on held-out weeks it met on validation.

## Favourable result

4. **C2 (PRISM vs Reactive): PRISM cheaper at similar compliance.** Cost -26.49% [-28.76, -24.23] (difference:
   PRISM cheaper on all 25 traces); violating windows +0.018 points [-0.296, +0.332] (similar compliance).

## Pooled means (test weeks, scenarios averaged)

| Set | Family | Mean weekly cost (USD) | Pooled violating windows |
|---|---|---|---|
| C1/C2 | PRISM | 1456.5 | 1.58% |
| C1/C2 | QuantProv-q90 | 1454.6 | 1.69% |
| C1/C2 | Reactive | 1982.9 | 1.56% |
| C3 | PRISM | 1672.8 | 1.17% |
| C3 | MemAdapt-q90 | 1487.6 | 1.83% |

## Tuning

Selections by `select_by_rule` on validation weeks only, with edge expansion over `GRIDS_WIDE`:
- C1/C2: PRISM eps in {0.005, 0.01, 0.02, 0.03, 0.05}, expanded on traces 122 and 128 (0.003, not selected);
  QuantProv-q90 in 1.0-1.5, expanded on 113 and 122 (1.6); Reactive in {0.55, 0.6}, no expansions.
- C3: PRISM eps in {0.02, 0.03}, no expansions; MemAdapt-q90 in 0.6-1.2, expanded on 118, 121, 126 (0.5).
- No edge hits remain after expansion. `verify_run.py` replays every selection and expansion from validation rows
  alone: 0 problems, so no test outcome entered a selection.

## Verification (`checks/verify_run_final.txt`, ok)

- Coverage: 125 of 125 groups (75 C1/C2, 50 C3); 1,432 week files, all inside groups; no temporary files.
- Failures: 10 weeks logged FAILED (all at the first interruption, 22 Nov 23:11:56 UTC) were retried and saved;
  `failures.json` empty; no gaps.
- Duplicates: one file per task and one row per parameter per group.
- Provenance: 1,432 rows checked against the manifest-verified trace hashes, 0 mismatches; every row carries its
  set's configuration hash; identical request counts across families per seed, week and scenario; all 5 run segments
  record commit fd8b01a, clean src/experiments/tests and driver SHA-256 3f909dc9780d7213...
- Determinism: 2 randomly chosen weeks recomputed, identical in every field but wall time, process id and finish time.
- Runtime: 979 C1/C2 weeks (median 73 s, 24.6 CPU-h) and 453 C3 weeks (median 68 s, 9.9 CPU-h).

## Run history (interruptions; none affected results, per the checks above)

| Segment | Start (UTC) | Workers | Ended by |
|---|---|---|---|
| 1 | 22 Nov 22:49:32 | 6 | Claude Code low-memory reaper, 23:11:56 |
| 2 | 22 Nov 23:55:27 | 4 | reaper, about 03:28 |
| 3 | 23 Nov 03:36:37 | 3 | reaper, about 04:25 |
| 4 | 23 Nov 04:27:15 | 2 | battery exhausted, about 08:14 |
| 5 | 23 Nov 10:09:36 | 2 | completed 15:25:55 (582 weeks run, 850 reused, 0 failures) |

During segment 2 an orphaned regeneration step (E12, seeds 101-103, a different tree and seeds) ran alongside the
run; it shared only CPU and memory. Each restart was preceded by `checkpoint_check.py`
(`checks/checkpoint_before_resume*.json`).

**Cost definition.** "Mean weekly cost (USD)" is the simulator's modelled cost at the assumed prices (`pc`/`pcd` are
among the open constants in `CONSTANTS.md`), not an AWS charge or a list-price estimate. PRISM's risk model is Erlang-B
(`risk_model = 'erlangb'`) in every run segment (`run/environment.json`). Audit: `FINAL_AUDIT_20261123.md`.
