# Validation week: cheapest grid point whose mean (over traces) violating-window rate is under a threshold

| Policy        | min mean cost with ≤1% viol   |   min mean cost with ≤2% viol |
|:--------------|:------------------------------|------------------------------:|
| Static        | 1,418                         |                         1,418 |
| Scheduled     | 1,329                         |                         1,329 |
| Reactive      | 1,666                         |                         1,478 |
| PredHead      | none                          |                           934 |
| PredHead+hyst | 1,147                         |                           975 |
| QuantProv_q90 | 1,190                         |                         1,035 |
| QuantProv_q99 | 1,207                         |                         1,070 |
| PRISM         | 1,148                         |                           985 |
