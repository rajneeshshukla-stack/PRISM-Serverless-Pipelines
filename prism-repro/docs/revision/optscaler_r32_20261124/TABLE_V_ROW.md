# Table V-ready row: OptScaler [16] (standalone; NOT inserted; 24 Nov 2026)

EXPLORATORY, PRE-CALIBRATION. Fast simulator, development traces 101-105. These are the regenerated Windows values
(fd8b01a), **not the submitted Table V**: insert only into a table regenerated from the same result set. That needs
the reporting-platform decision, and the values change with the calibrated rerun.

**Recommended row** (author's decision). OptScaler at its published parameters: c* = 0.5, alpha = 0.95, eta by the
published selection rule. Format as Table V: mean +/- 95% half-width over five traces, and in brackets the traces
out of five meeting the 2% target.

| Policy | Stationary: cost (USD) | violating windows (%) | Growth: cost (USD) | violating windows (%) | Bursty: cost (USD) | violating windows (%) | New spike: cost (USD) | violating windows (%) |
|---|---|---|---|---|---|---|---|---|
| OptScaler [16]† | 1,367 ± 20 | 0.12 ± 0.15 [5] | 1,764 ± 24 | 0.15 ± 0.23 [5] | 1,391 ± 18 | 0.27 ± 0.33 [5] | 1,671 ± 22 | 0.18 ± 0.15 [5] |
| PRISM (same result set) | 981 ± 93 | 1.55 ± 0.97 [3] | 1,273 ± 125 | 1.31 ± 0.90 [4] | 1,076 ± 104 | 2.14 ± 1.07 [3] | 1,270 ± 123 | 2.11 ± 1.32 [2] |

† The published utilization target (c* = 0.5, alpha = 0.95), not validation-tuned. Under the common tuning rule the
selected targets (0.90-1.00) made its online estimator diverge; see the supplement.

**Table VI-style paired row**, PRISM minus OptScaler. Cost (%) and violating windows (points); in parentheses, the
traces in which PRISM was cheaper / had fewer violating windows:
- stationary −28.3 ± 6.4 (5), +1.43 ± 1.03 (0);
- growth −27.8 ± 6.7 (5), +1.16 ± 1.04 (0);
- bursty −22.7 ± 7.5 (5), +1.88 ± 1.09 (0);
- new spike −24.0 ± 7.2 (5), +1.93 ± 1.27 (0).

**Wording for the text** (proposal only):

> We add OptScaler [16], a chance-constrained capacity controller evaluated on the Azure Functions trace, implemented
> from its paper with the common forecaster (supplement). At its published utilization target it meets the 2% target
> on every trace and scenario, at 30-40% higher cost than PRISM (PRISM costs 23-28% less), with 1.2-1.9 points
> fewer violating windows. The two
> are not at the same compliance, so this is a trade-off, not a ranking. Tuned by our common rule, its online
> estimator diverged, so we do not report a tuned row.

**Not for Table V:**
- the prespecified validation-tuned row, which is invalid (divergence);
- the POST HOC eta = 0 row, which is not the published controller (supplement only, labelled);
- the hybrid histogram policy [3], which is not reproduced.

**Linux x86-64 values (24 Nov 2026; README section 8), if Linux is the reporting basis:**

| Policy | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| OptScaler [16]†: cost (USD) / violating windows (%) [traces meeting 2%] | 1,368 ± 20 / 0.12 ± 0.15 [5] | 1,765 ± 24 / 0.15 ± 0.23 [5] | 1,392 ± 18 / 0.30 ± 0.29 [5] | 1,671 ± 21 / 0.15 ± 0.13 [5] |
| PRISM (Linux E1) | 968 ± 107 / 1.70 ± 0.96 [3] | 1,261 ± 134 / 1.34 ± 0.91 [4] | 1,053 ± 109 / 2.35 ± 0.99 [2] | 1,241 ± 135 / 2.62 ± 1.50 [1] |

Paired, PRISM minus OptScaler, cost (%) / violating windows (points):
- stationary −29.3 ± 7.4 / +1.58 ± 1.00;
- growth −28.6 ± 7.2 / +1.19 ± 1.03;
- bursty −24.4 ± 7.9 / +2.05 ± 0.94;
- new spike −25.7 ± 7.6 / +2.47 ± 1.43.

In every scenario, PRISM is cheaper on 5 of 5 traces and has fewer violating windows on 0 of 5.

The proposed text's ranges become "33-42% higher cost than PRISM (PRISM 24-29% less)" and "1.2-2.5 points fewer
violating windows".

*[Base corrected 24 Nov 2026: the paired figure is (PRISM − OptScaler) / OptScaler, so PRISM costs 23-28% less than OptScaler; OptScaler costs 30-40% more than PRISM (mean of per-trace ratios). The earlier '23-28% more expensive than PRISM' inverted the base.]*
