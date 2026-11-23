# Feature-group ablations (mean over traces; PRISM at the full model's validation-chosen ε)

| Scenario         | Variant        |   MAPE (%) |   Pinball τ=0.9 | Coverage q99 raw   |   PRISM cost | PRISM viol   |
|:-----------------|:---------------|-----------:|----------------:|:-------------------|-------------:|:-------------|
| stationary       | gbm            |       12.2 |            44.9 | 97.2%              |          968 | 1.70%        |
| stationary       | gbm_no_trigger |       14.7 |            50.9 | 97.3%              |          968 | 2.17%        |
| stationary       | gbm_no_prevday |       12.3 |            44.5 | 97.5%              |          960 | 1.67%        |
| stationary       | gbm_no_norm    |       12.6 |            47.1 | 97.2%              |          987 | 1.61%        |
| growth           | gbm            |       12.2 |            58.7 | 97.3%              |        1,261 | 1.34%        |
| growth           | gbm_no_trigger |       14.7 |            66.5 | 97.3%              |        1,254 | 2.14%        |
| growth           | gbm_no_prevday |       12.2 |            58   | 97.5%              |        1,254 | 1.40%        |
| growth           | gbm_no_norm    |       15.5 |            80.4 | 95.4%              |        1,251 | 1.43%        |
| bursty           | gbm            |       14   |            62.8 | 96.0%              |        1,053 | 2.35%        |
| bursty           | gbm_no_trigger |       17.3 |            69.5 | 96.0%              |        1,047 | 2.59%        |
| bursty           | gbm_no_prevday |       13.9 |            61.9 | 96.2%              |        1,044 | 2.47%        |
| bursty           | gbm_no_norm    |       14.1 |            64.8 | 95.7%              |        1,062 | 2.14%        |
| new_spike        | gbm            |       16.3 |           108.5 | 93.4%              |        1,241 | 2.62%        |
| new_spike        | gbm_no_trigger |       17.5 |            78.2 | 96.1%              |        1,224 | 2.74%        |
| new_spike        | gbm_no_prevday |       16.4 |           110.9 | 92.2%              |        1,257 | 2.38%        |
| new_spike        | gbm_no_norm    |       17.3 |           122.5 | 91.7%              |        1,263 | 2.77%        |
| shifted_triggers | gbm            |       35.5 |           140.4 | 90.9%              |        1,028 | 3.30%        |
| shifted_triggers | gbm_no_trigger |       17.6 |            63.6 | 96.6%              |          988 | 2.32%        |
| shifted_triggers | gbm_no_prevday |       35.9 |           144.4 | 89.9%              |        1,074 | 2.32%        |
| shifted_triggers | gbm_no_norm    |       33.3 |           134.1 | 92.5%              |        1,016 | 4.29%        |
