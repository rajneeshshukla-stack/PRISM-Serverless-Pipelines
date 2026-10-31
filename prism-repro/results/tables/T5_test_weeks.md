# Test weeks, validation-tuned parameters (mean ± 95% t half-width over traces)

SYNTHETIC simulation (fast simulator). Violating window: 15-min window with record attainment < 99%.

| Scenario   | Policy        | Cost (USD)   | Violating windows (%)   |   Record attainment (%) |   p99 latency (s) | Billing utilisation   | SLO met   |   n |
|:-----------|:--------------|:-------------|:------------------------|------------------------:|------------------:|:----------------------|:----------|----:|
| stationary | OnDemand      | 868 ± 13     | 16.76 ± 1.28            |                   99.36 |             13.79 | 0%                    | 0%        |   5 |
| stationary | Static        | 1,412 ± 18   | 0.48 ± 0.36             |                   99.74 |             13.2  | 24%                   | 100%      |   5 |
| stationary | Scheduled     | 1,287 ± 60   | 1.19 ± 0.51             |                   99.72 |             13.22 | 27%                   | 100%      |   5 |
| stationary | Reactive      | 1,504 ± 49   | 1.52 ± 0.74             |                   99.72 |             13.23 | 21%                   | 80%       |   5 |
| stationary | PredHead      | 928 ± 38     | 1.85 ± 0.89             |                   99.69 |             13.27 | 51%                   | 60%       |   5 |
| stationary | PRISM         | 1,073 ± 77   | 1.28 ± 0.78             |                   99.73 |             13.22 | 38%                   | 80%       |   5 |
| stationary | PredHead+hyst | 1,001 ± 60   | 1.70 ± 0.81             |                   99.7  |             13.26 | 43%                   | 80%       |   5 |
| stationary | QuantProv_q90 | 1,110 ± 161  | 1.28 ± 0.79             |                   99.73 |             13.22 | 36%                   | 80%       |   5 |
| stationary | QuantProv_q99 | 1,150 ± 101  | 0.92 ± 0.58             |                   99.74 |             13.21 | 34%                   | 100%      |   5 |
| growth     | OnDemand      | 1,133 ± 15   | 17.14 ± 1.21            |                   99.37 |             13.78 | 0%                    | 0%        |   5 |
| growth     | Static        | 1,575 ± 17   | 2.14 ± 0.50             |                   99.69 |             13.28 | 30%                   | 20%       |   5 |
| growth     | Scheduled     | 1,452 ± 59   | 3.93 ± 0.87             |                   99.65 |             13.32 | 35%                   | 0%        |   5 |
| growth     | Reactive      | 1,941 ± 64   | 1.64 ± 0.54             |                   99.72 |             13.23 | 22%                   | 80%       |   5 |
| growth     | PredHead      | 1,208 ± 49   | 1.67 ± 0.77             |                   99.7  |             13.26 | 51%                   | 60%       |   5 |
| growth     | PRISM         | 1,396 ± 89   | 1.22 ± 0.72             |                   99.73 |             13.21 | 38%                   | 80%       |   5 |
| growth     | PredHead+hyst | 1,306 ± 78   | 1.49 ± 0.70             |                   99.7  |             13.25 | 44%                   | 60%       |   5 |
| growth     | QuantProv_q90 | 1,457 ± 204  | 1.16 ± 0.79             |                   99.73 |             13.21 | 36%                   | 80%       |   5 |
| growth     | QuantProv_q99 | 1,512 ± 118  | 0.83 ± 0.62             |                   99.74 |             13.2  | 33%                   | 100%      |   5 |
| bursty     | OnDemand      | 896 ± 10     | 17.77 ± 1.52            |                   99.34 |             13.82 | 0%                    | 0%        |   5 |
| bursty     | Static        | 1,430 ± 20   | 0.62 ± 0.56             |                   99.73 |             13.22 | 24%                   | 100%      |   5 |
| bursty     | Scheduled     | 1,306 ± 60   | 1.64 ± 0.83             |                   99.71 |             13.25 | 28%                   | 60%       |   5 |
| bursty     | Reactive      | 1,573 ± 50   | 1.55 ± 0.63             |                   99.72 |             13.23 | 21%                   | 80%       |   5 |
| bursty     | PredHead      | 958 ± 33     | 2.89 ± 0.96             |                   99.66 |             13.32 | 51%                   | 0%        |   5 |
| bursty     | PRISM         | 1,202 ± 66   | 1.40 ± 0.88             |                   99.73 |             13.22 | 33%                   | 80%       |   5 |
| bursty     | PredHead+hyst | 1,034 ± 56   | 2.71 ± 1.05             |                   99.67 |             13.3  | 43%                   | 40%       |   5 |
| bursty     | QuantProv_q90 | 1,252 ± 148  | 1.28 ± 0.96             |                   99.73 |             13.22 | 31%                   | 80%       |   5 |
| bursty     | QuantProv_q99 | 1,301 ± 76   | 0.95 ± 0.88             |                   99.74 |             13.2  | 28%                   | 100%      |   5 |
| new_spike  | OnDemand      | 1,089 ± 15   | 23.21 ± 1.22            |                   99.26 |             13.98 | 0%                    | 0%        |   5 |
| new_spike  | Static        | 1,546 ± 16   | 1.82 ± 0.46             |                   99.69 |             13.28 | 29%                   | 60%       |   5 |
| new_spike  | Scheduled     | 1,423 ± 59   | 3.57 ± 1.43             |                   99.66 |             13.32 | 34%                   | 0%        |   5 |
| new_spike  | Reactive      | 1,881 ± 62   | 1.40 ± 0.48             |                   99.73 |             13.22 | 21%                   | 100%      |   5 |
| new_spike  | PredHead      | 1,160 ± 45   | 6.67 ± 1.66             |                   99.59 |             13.41 | 51%                   | 0%        |   5 |
| new_spike  | PRISM         | 1,395 ± 74   | 1.55 ± 1.15             |                   99.72 |             13.23 | 35%                   | 80%       |   5 |
| new_spike  | PredHead+hyst | 1,241 ± 73   | 3.24 ± 1.80             |                   99.66 |             13.32 | 44%                   | 20%       |   5 |
| new_spike  | QuantProv_q90 | 1,460 ± 187  | 1.25 ± 1.07             |                   99.73 |             13.21 | 33%                   | 80%       |   5 |
| new_spike  | QuantProv_q99 | 1,516 ± 78   | 0.98 ± 0.55             |                   99.74 |             13.2  | 30%                   | 100%      |   5 |
