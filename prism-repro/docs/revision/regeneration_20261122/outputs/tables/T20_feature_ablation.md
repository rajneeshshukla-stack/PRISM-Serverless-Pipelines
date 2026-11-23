# Feature-group ablations (mean over traces; PRISM at the full model's validation-chosen ε)

| Scenario         | Variant        |   MAPE (%) |   Pinball τ=0.9 | Coverage q99 raw   |   PRISM cost | PRISM viol   |
|:-----------------|:---------------|-----------:|----------------:|:-------------------|-------------:|:-------------|
| stationary       | gbm            |       12.2 |            44.8 | 97.3%              |          981 | 1.55%        |
| stationary       | gbm_no_trigger |       14.7 |            50.7 | 97.3%              |          978 | 1.85%        |
| stationary       | gbm_no_prevday |       12.2 |            44.5 | 97.5%              |          974 | 1.55%        |
| stationary       | gbm_no_norm    |       12.6 |            47   | 97.1%              |          994 | 1.49%        |
| growth           | gbm            |       12.1 |            58.4 | 97.4%              |        1,273 | 1.31%        |
| growth           | gbm_no_trigger |       14.7 |            66.3 | 97.2%              |        1,273 | 1.73%        |
| growth           | gbm_no_prevday |       12.2 |            57.9 | 97.5%              |        1,271 | 1.25%        |
| growth           | gbm_no_norm    |       15.4 |            80.2 | 95.4%              |        1,278 | 1.25%        |
| bursty           | gbm            |       14   |            62.6 | 96.0%              |        1,076 | 2.14%        |
| bursty           | gbm_no_trigger |       17.3 |            69.5 | 96.0%              |        1,070 | 2.29%        |
| bursty           | gbm_no_prevday |       13.9 |            61.7 | 96.2%              |        1,063 | 2.20%        |
| bursty           | gbm_no_norm    |       14.1 |            64.9 | 95.5%              |        1,084 | 1.99%        |
| new_spike        | gbm            |       16.3 |           108.3 | 93.4%              |        1,270 | 2.11%        |
| new_spike        | gbm_no_trigger |       17.5 |            77.8 | 96.1%              |        1,234 | 2.59%        |
| new_spike        | gbm_no_prevday |       16.3 |           111.2 | 92.0%              |        1,285 | 1.64%        |
| new_spike        | gbm_no_norm    |       17.2 |           122.4 | 91.7%              |        1,296 | 2.26%        |
| shifted_triggers | gbm            |       35.5 |           139.9 | 91.0%              |        1,058 | 2.38%        |
| shifted_triggers | gbm_no_trigger |       17.6 |            63.5 | 96.5%              |        1,007 | 2.05%        |
| shifted_triggers | gbm_no_prevday |       35.8 |           144.3 | 90.0%              |        1,095 | 2.26%        |
| shifted_triggers | gbm_no_norm    |       33.4 |           134.3 | 92.5%              |        1,036 | 3.42%        |
