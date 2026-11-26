# R2.7: within-run shift in execution time, dynamic against one-time memory (24 Nov 2026)

EXPLORATORY. Fast simulator, PRE-CALIBRATION constants, development traces 101-105 (stationary, test week), Windows,
current code at 3edc386; `src/` is unchanged. This is separate from the main study. The narrowed RQ4 and its
fixed-regime result (`../r27_r32_review_20261123/NOTE.md`, `../memadapt/summary.txt`) stand as they were.
`PLAN.md` was fixed before any run (SHA-256 in `PLAN.sha256`).

## 1. Result for the prespecified shift (warm execution time x 1.5 at day 4): no demonstrated benefit

`result.txt` gives the results. Both criteria hold on **0 of 5** traces.

| Policy (same shared estimate 60 min after the shift, except C) | Week violating windows | Post-shift | Week cost (USD) |
|---|---|---|---|
| A: PRISM-online, dynamic memory (exploratory variant) | 57.29-57.74% | 100% | 1,913-1,977 |
| B_1024: one-time 1024 MB (the pre-shift choice) | 57.29-57.59% | 100% | 1,683-1,752 |
| B_2048: one-time 2048 MB | 57.14% | 100% | 2,060-2,103 |
| **B_3008: one-time 3008 MB (best in hindsight)** | **0.00-0.15%** | **0.00-0.26%** | **2,534-2,588** |
| C: published PRISM, no estimate | 57.29-57.74% | 100% | 1,254-1,288 |

**Mechanism, from the model's own tables:**
- After the shift, even an all-warm record is on time only 98.75% of the time at 2048 MB. That is below the 99% window
  target, so 2048 MB cannot meet the target. At 3008 MB the figure is 99.75%.
- PRISM-online re-planned with the shifted times and moved from 1024 to 2048 MB on day 4, not to 3008 MB.
- Its optimiser accepted a warm miss probability of 1.27% under its risk budget ε = 0.02. That budget is looser than
  the 1% per-window miss that the target allows (`optimizer.py`: a size is feasible when (1 − p_c) v_w + p_c ρ ≤ ε).
- So dynamic re-optimisation chose a memory size the target does not allow. A one-time choice of 3008 MB met the
  target, at 30-32% more cost than A.
- Without an estimate (C), the published configuration stays at 1024 MB, as the narrowed RQ4 states: the method does
  not observe execution times online.

## 2. Post hoc sensitivity, a smaller shift (x 1.25): not a verdict

`posthoc_factor_1.25/result.txt` (`R27_FACTOR=1.25`; chosen after seeing section 1). Labelled POST HOC.
- A moved to 2048 MB on day 4 and met 2% on all 5 traces (0.74-1.19%; 0.00% after the estimate). It cost 6.7-8.6%
  less than the best one-time configuration (2048 MB all week, 0.00%).
- One-time 1024 MB failed after the shift (57.3-57.6%).
- Both criteria hold on 5 of 5 traces here.

So dynamic memory pays off when the size the controller picks after the shift is feasible, and fails when its risk
budget lets it pick an infeasible size. This dependence is shown on two shift sizes only.

## 3. Validity checks

- **Splicing.** With no shift, `scripts/revision/r27_shift.py` reproduces `simulator.simulate` on every summary
  field (`check.json`, all identical).
- **The online variant.** With no estimate, `PRISMOnline` reproduces the published PRISM.
- **Same information.** A and B_m receive the same estimate at the same epoch (876). C receives none.
- **Common random numbers.** The draws are identical before and after the shift; only the execution-time scaling
  changes.

## 4. What this answers, and what it does not

**Answered (exploratory, fast simulator, pre-calibration):**
- R2.7's question for one of the listed shift types, a step in CPU intensity or function execution time: whether
  dynamic memory optimisation gives a benefit that a one-time configuration cannot.
- At the prespecified size it did not.
- At a smaller post hoc size it did, by 7-9% at equal compliance.

**Not answered:**
- shifts in memory demand or initialisation latency;
- gradual drifts;
- estimation from telemetry (the estimate here is the true value, given to both controllers alike);
- event-level or closed-loop confirmation;
- calibrated constants;
- AWS.

The variant PRISM-online is exploratory and is not the published configuration.

## Files

- `PLAN.md`, `PLAN.sha256`;
- `check.json`;
- `rows.jsonl`, `run.log`, `result.txt`;
- `posthoc_factor_1.25/`;
- `../../../scripts/revision/r27_shift.py`;
- `SHA256SUMS`.
