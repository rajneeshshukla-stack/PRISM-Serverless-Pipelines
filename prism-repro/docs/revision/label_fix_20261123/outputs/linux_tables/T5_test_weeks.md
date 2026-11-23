# Test weeks, validation-tuned parameters (mean ± 95% t half-width over traces)

SYNTHETIC simulation (fast simulator). Violating window: 15-min window with record attainment < 99%.

| Scenario   | Policy        | Cost (USD)   | Violating windows (%)   |   Record attainment (%) |   p99 latency (s) | Billing utilisation   | SLO met   |   n |
|:-----------|:--------------|:-------------|:------------------------|------------------------:|------------------:|:----------------------|:----------|----:|
| stationary | OnDemand      | 868 ± 13     | 16.93 ± 0.71            |                   99.35 |             13.79 | 0%                    | 0%        |   5 |
| stationary | Static        | 1,291 ± 192  | 1.10 ± 1.39             |                   99.68 |             13.26 | 28%                   | 80%       |   5 |
| stationary | Scheduled     | 1,181 ± 50   | 1.34 ± 0.58             |                   99.67 |             13.28 | 32%                   | 100%      |   5 |
| stationary | Reactive      | 1,352 ± 43   | 1.85 ± 1.01             |                   99.65 |             13.29 | 25%                   | 40%       |   5 |
| stationary | PredHead      | 863 ± 55     | 2.17 ± 0.52             |                   99.6  |             13.38 | 61%                   | 40%       |   5 |
| stationary | PRISM         | 968 ± 107    | 1.70 ± 0.96             |                   99.64 |             13.32 | 47%                   | 60%       |   5 |
| stationary | PredHead+hyst | 931 ± 62     | 1.90 ± 0.86             |                   99.62 |             13.35 | 51%                   | 60%       |   5 |
| stationary | QuantProv_q90 | 963 ± 84     | 1.79 ± 0.84             |                   99.64 |             13.32 | 47%                   | 60%       |   5 |
| stationary | QuantProv_q99 | 1,030 ± 72   | 1.49 ± 0.65             |                   99.67 |             13.27 | 41%                   | 80%       |   5 |
| growth     | OnDemand      | 1,133 ± 15   | 16.96 ± 1.03            |                   99.35 |             13.78 | 0%                    | 0%        |   5 |
| growth     | Static        | 1,457 ± 186  | 3.04 ± 3.24             |                   99.61 |             13.36 | 36%                   | 60%       |   5 |
| growth     | Scheduled     | 1,349 ± 50   | 4.85 ± 1.48             |                   99.58 |             13.39 | 40%                   | 0%        |   5 |
| growth     | Reactive      | 1,746 ± 56   | 1.99 ± 0.80             |                   99.65 |             13.3  | 26%                   | 40%       |   5 |
| growth     | PredHead      | 1,123 ± 71   | 2.14 ± 0.55             |                   99.61 |             13.36 | 62%                   | 60%       |   5 |
| growth     | PRISM         | 1,261 ± 134  | 1.34 ± 0.91             |                   99.65 |             13.3  | 47%                   | 80%       |   5 |
| growth     | PredHead+hyst | 1,213 ± 81   | 1.79 ± 0.95             |                   99.63 |             13.33 | 51%                   | 60%       |   5 |
| growth     | QuantProv_q90 | 1,263 ± 106  | 1.55 ± 0.87             |                   99.65 |             13.3  | 47%                   | 60%       |   5 |
| growth     | QuantProv_q99 | 1,353 ± 86   | 1.31 ± 0.60             |                   99.68 |             13.26 | 41%                   | 80%       |   5 |
| bursty     | OnDemand      | 896 ± 10     | 18.24 ± 1.31            |                   99.33 |             13.82 | 0%                    | 0%        |   5 |
| bursty     | Static        | 1,311 ± 188  | 1.40 ± 1.76             |                   99.66 |             13.28 | 29%                   | 80%       |   5 |
| bursty     | Scheduled     | 1,200 ± 49   | 1.90 ± 0.77             |                   99.65 |             13.31 | 32%                   | 60%       |   5 |
| bursty     | Reactive      | 1,414 ± 48   | 1.93 ± 1.08             |                   99.65 |             13.3  | 25%                   | 40%       |   5 |
| bursty     | PredHead      | 893 ± 52     | 3.57 ± 0.54             |                   99.57 |             13.43 | 61%                   | 0%        |   5 |
| bursty     | PRISM         | 1,053 ± 109  | 2.35 ± 0.99             |                   99.65 |             13.31 | 42%                   | 40%       |   5 |
| bursty     | PredHead+hyst | 962 ± 60     | 3.24 ± 0.94             |                   99.59 |             13.39 | 51%                   | 0%        |   5 |
| bursty     | QuantProv_q90 | 1,073 ± 72   | 2.38 ± 0.79             |                   99.66 |             13.29 | 40%                   | 20%       |   5 |
| bursty     | QuantProv_q99 | 1,154 ± 47   | 1.61 ± 1.07             |                   99.69 |             13.25 | 35%                   | 60%       |   5 |
| new_spike  | OnDemand      | 1,089 ± 15   | 23.48 ± 1.02            |                   99.24 |             13.98 | 0%                    | 0%        |   5 |
| new_spike  | Static        | 1,430 ± 185  | 2.71 ± 3.08             |                   99.6  |             13.38 | 34%                   | 60%       |   5 |
| new_spike  | Scheduled     | 1,320 ± 49   | 3.42 ± 1.27             |                   99.57 |             13.42 | 39%                   | 20%       |   5 |
| new_spike  | Reactive      | 1,691 ± 58   | 1.93 ± 0.68             |                   99.66 |             13.29 | 25%                   | 60%       |   5 |
| new_spike  | PredHead      | 1,082 ± 66   | 7.62 ± 2.31             |                   99.49 |             13.53 | 61%                   | 0%        |   5 |
| new_spike  | PRISM         | 1,241 ± 135  | 2.62 ± 1.50             |                   99.61 |             13.36 | 45%                   | 20%       |   5 |
| new_spike  | PredHead+hyst | 1,157 ± 74   | 4.02 ± 2.67             |                   99.55 |             13.44 | 52%                   | 20%       |   5 |
| new_spike  | QuantProv_q90 | 1,259 ± 97   | 2.41 ± 1.15             |                   99.63 |             13.33 | 43%                   | 20%       |   5 |
| new_spike  | QuantProv_q99 | 1,352 ± 67   | 1.49 ± 0.45             |                   99.67 |             13.28 | 37%                   | 80%       |   5 |
