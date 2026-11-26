# Aggregate over all test weeks (traces × scenarios)

| Policy        |   Mean cost (USD) |   Mean violating windows (%) | SLO met (share of test weeks)   |   test weeks |
|:--------------|------------------:|-----------------------------:|:--------------------------------|-------------:|
| OnDemand      |               997 |                        18.91 | 0%                              |           20 |
| Static        |             1,372 |                         2.06 | 70%                             |           20 |
| Scheduled     |             1,263 |                         2.88 | 45%                             |           20 |
| Reactive      |             1,551 |                         1.93 | 45%                             |           20 |
| PredHead      |               990 |                         3.88 | 25%                             |           20 |
| PRISM         |             1,130 |                         2    | 50%                             |           20 |
| PredHead+hyst |             1,066 |                         2.74 | 35%                             |           20 |
| QuantProv_q90 |             1,139 |                         2.03 | 40%                             |           20 |
| QuantProv_q99 |             1,222 |                         1.47 | 75%                             |           20 |
