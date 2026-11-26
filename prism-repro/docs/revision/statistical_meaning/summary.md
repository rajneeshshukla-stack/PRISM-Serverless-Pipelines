# Which paired differences are distinguishable from zero (submitted rows; n = 5 traces; 95% t intervals)

Pre-calibration, submitted code and values. 'includes 0' = the five traces cannot distinguish the policies at the
95% level; it is not a demonstration of equivalence. Built by scripts/revision/statistical_meaning.py.

## A. Selected configurations (validation rule), PRISM minus comparator, per test scenario

| Comparator | Scenario | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |
|---|---|---|---|---|---|
| QuantProv_q90 | stationary | -2.8 +/- 7.5 | includes 0 | +0.00 +/- 0.18 | includes 0 |
| QuantProv_q90 | growth | -3.6 +/- 7.5 | includes 0 | +0.06 +/- 0.10 | includes 0 |
| QuantProv_q90 | bursty | -3.6 +/- 7.5 | includes 0 | +0.12 +/- 0.27 | includes 0 |
| QuantProv_q90 | new_spike | -3.9 +/- 7.4 | includes 0 | +0.30 +/- 0.35 | includes 0 |
| QuantProv_q90 | all four | -3.5 +/- 7.5 | includes 0 | +0.12 +/- 0.18 | includes 0 |
| QuantProv_q99 | stationary | -6.6 +/- 3.5 | excludes 0 | +0.36 +/- 0.36 | includes 0 |
| QuantProv_q99 | growth | -7.5 +/- 3.6 | excludes 0 | +0.39 +/- 0.34 | excludes 0 |
| QuantProv_q99 | bursty | -7.6 +/- 3.7 | excludes 0 | +0.45 +/- 0.61 | includes 0 |
| QuantProv_q99 | new_spike | -8.0 +/- 4.1 | excludes 0 | +0.57 +/- 1.01 | includes 0 |
| QuantProv_q99 | all four | -7.5 +/- 3.7 | excludes 0 | +0.44 +/- 0.51 | includes 0 |
| PredHead+hyst | stationary | +7.1 +/- 4.2 | excludes 0 | -0.42 +/- 0.24 | excludes 0 |
| PredHead+hyst | growth | +7.0 +/- 4.2 | excludes 0 | -0.27 +/- 0.27 | includes 0 |
| PredHead+hyst | bursty | +16.3 +/- 5.9 | excludes 0 | -1.31 +/- 1.06 | excludes 0 |
| PredHead+hyst | new_spike | +12.5 +/- 5.6 | excludes 0 | -1.70 +/- 1.10 | excludes 0 |
| PredHead+hyst | all four | +10.6 +/- 4.6 | excludes 0 | -0.92 +/- 0.58 | excludes 0 |
| PredHead | stationary | +15.6 +/- 8.3 | excludes 0 | -0.57 +/- 0.40 | excludes 0 |
| PredHead | growth | +15.7 +/- 8.0 | excludes 0 | -0.45 +/- 0.35 | excludes 0 |
| PredHead | bursty | +25.5 +/- 8.8 | excludes 0 | -1.49 +/- 0.32 | excludes 0 |
| PredHead | new_spike | +20.4 +/- 8.2 | excludes 0 | -5.12 +/- 1.09 | excludes 0 |
| PredHead | all four | +19.2 +/- 8.0 | excludes 0 | -1.90 +/- 0.46 | excludes 0 |
| Reactive | stationary | -28.7 +/- 3.8 | excludes 0 | -0.24 +/- 0.87 | includes 0 |
| Reactive | growth | -28.1 +/- 3.4 | excludes 0 | -0.42 +/- 0.92 | includes 0 |
| Reactive | bursty | -23.6 +/- 2.6 | excludes 0 | -0.15 +/- 1.00 | includes 0 |
| Reactive | new_spike | -25.8 +/- 3.8 | excludes 0 | +0.15 +/- 1.29 | includes 0 |
| Reactive | all four | -26.6 +/- 3.1 | excludes 0 | -0.16 +/- 0.93 | includes 0 |
| Static | stationary | -24.0 +/- 5.5 | excludes 0 | +0.80 +/- 0.96 | includes 0 |
| Static | growth | -11.3 +/- 5.7 | excludes 0 | -0.92 +/- 1.19 | includes 0 |
| Static | bursty | -16.0 +/- 4.5 | excludes 0 | +0.77 +/- 1.24 | includes 0 |
| Static | new_spike | -9.8 +/- 4.9 | excludes 0 | -0.27 +/- 1.58 | includes 0 |
| Static | all four | -15.0 +/- 4.9 | excludes 0 | +0.10 +/- 1.20 | includes 0 |
| Scheduled | stationary | -16.7 +/- 2.2 | excludes 0 | +0.09 +/- 0.70 | includes 0 |
| Scheduled | growth | -3.9 +/- 2.7 | excludes 0 | -2.71 +/- 0.62 | excludes 0 |
| Scheduled | bursty | -8.0 +/- 2.4 | excludes 0 | -0.24 +/- 1.03 | includes 0 |
| Scheduled | new_spike | -2.0 +/- 3.8 | includes 0 | -2.02 +/- 1.17 | excludes 0 |
| Scheduled | all four | -7.4 +/- 2.2 | excludes 0 | -1.22 +/- 0.78 | excludes 0 |

Check: PRISM vs QuantProv_q90 per-scenario cost % reproduces T6_paired_PRISM_vs_QuantProvq90.md in 4 of 4 scenarios.
Check: PRISM vs PredHead+hyst per-scenario cost % reproduces T6_paired_PRISM_vs_PredHeadHyst.md in 4 of 4 scenarios.

## B. Matched compliance (POST HOC, interpolated per trace over its four test weeks), PRISM minus comparator

| Target | Comparator | Cost % (mean +/- hw) | n traces | Cost |
|---|---|---|---|---|
| 1.0% | QuantProv_q90 | -0.4 +/- 3.3 | 5 | includes 0 |
| 1.0% | PredHead+hyst | -0.2 +/- 7.4 | 3 | includes 0 |
| 1.0% | Static | -12.9 +/- 10.1 | 5 | excludes 0 |
| 1.0% | Reactive | -25.9 +/- 7.8 | 5 | excludes 0 |
| 1.5% | QuantProv_q90 | -0.4 +/- 2.1 | 5 | includes 0 |
| 1.5% | PredHead+hyst | +0.6 +/- 1.8 | 5 | includes 0 |
| 1.5% | Static | -15.3 +/- 7.5 | 5 | excludes 0 |
| 1.5% | Reactive | -27.5 +/- 7.0 | 5 | excludes 0 |
| 2.0% | QuantProv_q90 | +0.2 +/- 1.2 | 5 | includes 0 |
| 2.0% | PredHead+hyst | +1.6 +/- 1.8 | 5 | includes 0 |
| 2.0% | Static | -17.3 +/- 6.0 | 5 | excludes 0 |
| 2.0% | Reactive | -28.4 +/- 6.3 | 5 | excludes 0 |

## C. Real-trace replay (POST HOC), selected configurations, PRISM minus comparator

| Comparator | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |
|---|---|---|---|---|
| QuantProv_q90 | +2.4 +/- 4.0 | includes 0 | -0.27 +/- 0.67 | includes 0 |
| QuantProv_q99 | +1.5 +/- 4.0 | includes 0 | -0.33 +/- 0.58 | includes 0 |
| PredHead+hyst | +2.1 +/- 2.8 | includes 0 | -0.30 +/- 0.43 | includes 0 |
| PredHead | +8.5 +/- 12.4 | includes 0 | -0.33 +/- 0.48 | includes 0 |
| Reactive | -24.0 +/- 22.7 | excludes 0 | -0.77 +/- 1.09 | includes 0 |
| Static | -20.2 +/- 31.1 | includes 0 | -0.30 +/- 0.29 | excludes 0 |
| Scheduled | -9.9 +/- 5.9 | excludes 0 | -2.02 +/- 5.11 | includes 0 |

## Summary
- A: cost intervals excluding zero 29 of 35; violating-window intervals 13 of 35.
- B: cost intervals excluding zero 6 of 12.
- C: cost intervals excluding zero 2 of 7; violating-window intervals 1 of 7.
