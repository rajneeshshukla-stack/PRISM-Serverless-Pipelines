# Which paired differences are distinguishable from zero (regenerated rows at fd8b01a; n = 5 traces; 95% t intervals)

Pre-calibration, regenerated at fd8b01a (current code). 'includes 0' = the five traces cannot distinguish the policies at the
95% level; it is not a demonstration of equivalence. Built by scripts/revision/statistical_meaning.py.

## A. Selected configurations (validation rule), PRISM minus comparator, per test scenario

| Comparator | Scenario | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |
|---|---|---|---|---|---|
| QuantProv_q90 | stationary | +1.6 +/- 2.3 | includes 0 | -0.18 +/- 0.30 | includes 0 |
| QuantProv_q90 | growth | +1.3 +/- 2.2 | includes 0 | -0.18 +/- 0.36 | includes 0 |
| QuantProv_q90 | bursty | +0.0 +/- 3.5 | includes 0 | -0.15 +/- 0.29 | includes 0 |
| QuantProv_q90 | new_spike | -0.1 +/- 3.1 | includes 0 | -0.18 +/- 0.58 | includes 0 |
| QuantProv_q90 | all four | +0.7 +/- 2.7 | includes 0 | -0.17 +/- 0.20 | includes 0 |
| QuantProv_q99 | stationary | -6.3 +/- 4.5 | excludes 0 | +0.15 +/- 0.81 | includes 0 |
| QuantProv_q99 | growth | -6.6 +/- 4.6 | excludes 0 | -0.00 +/- 1.07 | includes 0 |
| QuantProv_q99 | bursty | -8.3 +/- 5.1 | excludes 0 | +0.77 +/- 1.07 | includes 0 |
| QuantProv_q99 | new_spike | -8.4 +/- 4.6 | excludes 0 | +0.86 +/- 0.94 | includes 0 |
| QuantProv_q99 | all four | -7.4 +/- 4.6 | excludes 0 | +0.45 +/- 0.88 | includes 0 |
| PredHead+hyst | stationary | +6.1 +/- 5.1 | excludes 0 | -0.39 +/- 0.21 | excludes 0 |
| PredHead+hyst | growth | +5.6 +/- 5.7 | includes 0 | -0.42 +/- 0.40 | excludes 0 |
| PredHead+hyst | bursty | +12.5 +/- 6.2 | excludes 0 | -1.16 +/- 0.36 | excludes 0 |
| PredHead+hyst | new_spike | +10.4 +/- 6.5 | excludes 0 | -1.99 +/- 1.35 | excludes 0 |
| PredHead+hyst | all four | +8.6 +/- 5.6 | excludes 0 | -0.99 +/- 0.35 | excludes 0 |
| PredHead | stationary | +14.1 +/- 5.3 | excludes 0 | -0.65 +/- 0.56 | excludes 0 |
| PredHead | growth | +13.9 +/- 5.0 | excludes 0 | -0.86 +/- 0.40 | excludes 0 |
| PredHead | bursty | +21.0 +/- 6.3 | excludes 0 | -1.55 +/- 0.52 | excludes 0 |
| PredHead | new_spike | +17.8 +/- 4.8 | excludes 0 | -5.80 +/- 1.54 | excludes 0 |
| PredHead | all four | +16.6 +/- 4.9 | excludes 0 | -2.22 +/- 0.43 | excludes 0 |
| Reactive | stationary | -27.4 +/- 7.9 | excludes 0 | -0.30 +/- 1.82 | includes 0 |
| Reactive | growth | -27.0 +/- 8.4 | excludes 0 | -0.68 +/- 1.55 | includes 0 |
| Reactive | bursty | -23.8 +/- 8.5 | excludes 0 | +0.21 +/- 1.85 | includes 0 |
| Reactive | new_spike | -24.8 +/- 9.0 | excludes 0 | +0.18 +/- 1.84 | includes 0 |
| Reactive | all four | -25.7 +/- 8.4 | excludes 0 | -0.15 +/- 1.72 | includes 0 |
| Static | stationary | -23.2 +/- 12.9 | excludes 0 | +0.45 +/- 1.63 | includes 0 |
| Static | growth | -12.0 +/- 12.8 | includes 0 | -1.73 +/- 2.93 | includes 0 |
| Static | bursty | -17.1 +/- 13.0 | excludes 0 | +0.74 +/- 2.15 | includes 0 |
| Static | new_spike | -10.6 +/- 11.5 | includes 0 | -0.60 +/- 3.14 | includes 0 |
| Static | all four | -15.5 +/- 12.5 | excludes 0 | -0.28 +/- 2.40 | includes 0 |
| Scheduled | stationary | -16.8 +/- 9.6 | excludes 0 | +0.21 +/- 1.30 | includes 0 |
| Scheduled | growth | -5.5 +/- 10.7 | includes 0 | -3.54 +/- 2.34 | excludes 0 |
| Scheduled | bursty | -10.2 +/- 11.0 | includes 0 | +0.24 +/- 1.42 | includes 0 |
| Scheduled | new_spike | -3.7 +/- 11.2 | includes 0 | -1.31 +/- 2.48 | includes 0 |
| Scheduled | all four | -8.8 +/- 10.5 | includes 0 | -1.10 +/- 1.84 | includes 0 |

Check: PRISM vs QuantProv_q90 per-scenario cost % reproduces T6_paired_PRISM_vs_QuantProvq90.md in 4 of 4 scenarios.
Check: PRISM vs PredHead+hyst per-scenario cost % reproduces T6_paired_PRISM_vs_PredHeadHyst.md in 4 of 4 scenarios.

## B. Matched compliance (POST HOC, interpolated per trace over its four test weeks), PRISM minus comparator

| Target | Comparator | Cost % (mean +/- hw) | n traces | Cost |
|---|---|---|---|---|
| 1.0% | QuantProv_q90 | -2.3 +/- 2.0 | 5 | excludes 0 |
| 1.0% | PredHead+hyst | -1.3 +/- 2.7 | 5 | includes 0 |
| 1.0% | Static | -13.0 +/- 6.6 | 5 | excludes 0 |
| 1.0% | Reactive | -23.5 +/- 8.2 | 5 | excludes 0 |
| 1.5% | QuantProv_q90 | -1.2 +/- 1.9 | 4 | includes 0 |
| 1.5% | PredHead+hyst | -0.2 +/- 3.4 | 4 | includes 0 |
| 1.5% | Static | -15.2 +/- 6.5 | 4 | excludes 0 |
| 1.5% | Reactive | -24.0 +/- 6.7 | 4 | excludes 0 |
| 2.0% | QuantProv_q90 | -1.1 +/- 1.9 | 4 | includes 0 |
| 2.0% | PredHead+hyst | +0.4 +/- 3.0 | 4 | includes 0 |
| 2.0% | Static | -16.8 +/- 5.9 | 4 | excludes 0 |
| 2.0% | Reactive | -25.5 +/- 4.8 | 4 | excludes 0 |

## C. Real-trace replay (POST HOC), selected configurations, PRISM minus comparator

| Comparator | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |
|---|---|---|---|---|
| QuantProv_q90 | +1.6 +/- 4.0 | includes 0 | +0.15 +/- 0.41 | includes 0 |
| QuantProv_q99 | +1.0 +/- 4.1 | includes 0 | +0.03 +/- 0.08 | includes 0 |
| PredHead+hyst | +2.1 +/- 0.6 | excludes 0 | -0.06 +/- 0.17 | includes 0 |
| PredHead | +8.9 +/- 15.9 | includes 0 | -0.03 +/- 0.08 | includes 0 |
| Reactive | -22.9 +/- 23.4 | includes 0 | -0.65 +/- 1.12 | includes 0 |
| Static | -18.3 +/- 31.2 | includes 0 | -0.42 +/- 1.09 | includes 0 |
| Scheduled | -10.0 +/- 3.9 | excludes 0 | -2.17 +/- 5.44 | includes 0 |

## Summary
- A: cost intervals excluding zero 23 of 35; violating-window intervals 11 of 35.
- B: cost intervals excluding zero 7 of 12.
- C: cost intervals excluding zero 2 of 7; violating-window intervals 0 of 7.
