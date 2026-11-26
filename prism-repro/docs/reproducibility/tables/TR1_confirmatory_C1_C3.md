# TR1. Prespecified confirmatory comparisons C1-C3 (held-out traces 106-130)

**Source:** `prism-repro/docs/revision/confirmatory_20261122/run/tables/` (C1C2_paired.csv, C3_paired.csv, *_per_trace.csv);
analysis frozen in `prism-repro/docs/revision/PRESPECIFICATION.md` (d16fbea) before the first held-out week.
**Configuration:** closed-loop event-level simulator, commit fd8b01a, `PipelineConfig()`/`PrismConfig()` defaults
(assumed constants: Eq. (2) memory scaling, independent stage spread, Eq. (3) start-up 6 s, lag 2 min), Windows 11, the
REGEN-WIN package set. **PRE-CALIBRATION.** C1/C2: 14.5 s, four scenarios (stationary, growth, bursty, new spike);
C3: 12 s, stationary. **Metric:** PRISM minus comparator; cost in % of the comparator's weekly cost (mean over 25
traces, 95% t interval, df 24); violating windows in percentage points (window = 15 min; violating when fewer than
99% of its records meet the deadline). **Decision rules** (frozen): difference = interval excludes 0; tie = interval
within +/-2%; similar compliance = violating-window interval within +/-0.5 points, otherwise the cost comparison is
confounded.

| Comparison | Pair | Traces | Cost diff (%) | 95% CI | Cost call | Violating windows diff (pts) | 95% CI | Compliance call | Traces PRISM cheaper / costlier |
|---|---|---|---|---|---|---|---|---|---|
| C1 | PRISM vs QuantProv_q90 | 25 | +0.30 | [-1.42, +2.01] | not distinguishable (includes 0, exceeds +/-2%) | -0.106 | [-0.274, +0.062] | similar compliance (within +/-0.5 points) | 11 / 14 |
| C2 | PRISM vs Reactive | 25 | -26.49 | [-28.76, -24.23] | difference: PRISM cheaper | +0.018 | [-0.296, +0.332] | similar compliance (within +/-0.5 points) | 25 / 0 |
| C3 | PRISM vs MemAdapt_q90 | 25 | +13.06 | [+8.50, +17.63] | difference: PRISM costlier | -0.655 | [-0.921, -0.389] | cost comparison confounded by compliance | 4 / 21 |

**Per family (test weeks; scenarios averaged per trace; then mean over traces):**

| Set | Family | Traces | Mean weekly cost (USD) | Mean violating windows (%) | Weeks meeting 2% | Traces above 2% |
|---|---|---|---|---|---|---|
| C1C2 | PRISM | 25 | 1,456.5 | 1.58 | 81 of 100 | 5 of 25 |
| C1C2 | QuantProv_q90 | 25 | 1,454.6 | 1.69 | 72 of 100 | 7 of 25 |
| C1C2 | Reactive | 25 | 1,982.9 | 1.56 | 75 of 100 | 5 of 25 |
| C3 | PRISM | 25 | 1,672.8 | 1.17 | 24 of 25 | 1 of 25 |
| C3 | MemAdapt_q90 | 25 | 1,487.6 | 1.83 | 17 of 25 | 8 of 25 |

Reading: C1 is not distinguishable and not a tie (upper end +2.011% exceeds +2% by 0.011 points; platform-fragile).
C2: PRISM cheaper at similar compliance. C3: PRISM costlier but violates fewer windows, outside the band, so the
cost comparison is confounded and supports no cost ranking. These are frozen-configuration results with assumed
constants; a calibrated held-out run is not part of this revision (TR2, readiness).
