# Aggregate over all test weeks (traces × scenarios)

| Policy        |   Mean cost (USD) |   Mean violating windows (%) | SLO met (share of test weeks)   |   test weeks |
|:--------------|------------------:|-----------------------------:|:--------------------------------|-------------:|
| OnDemand      |               997 |                        18.91 | 0%                              |           20 |
| Static        |             1,372 |                         2.06 | 70%                             |           20 |
| Scheduled     |             1,263 |                         2.88 | 45%                             |           20 |
| Reactive      |             1,551 |                         1.93 | 45%                             |           20 |
| PredHead      |               985 |                         4    | 20%                             |           20 |
| PRISM         |             1,150 |                         1.78 | 60%                             |           20 |
| PredHead+hyst |             1,058 |                         2.77 | 30%                             |           20 |
| QuantProv_q90 |             1,142 |                         1.95 | 55%                             |           20 |
| QuantProv_q99 |             1,243 |                         1.33 | 85%                             |           20 |
