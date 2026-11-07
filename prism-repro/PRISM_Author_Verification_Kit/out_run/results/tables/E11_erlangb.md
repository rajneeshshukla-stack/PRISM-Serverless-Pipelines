# PRISM vs PRISM-EB, both validation-tuned under the fast simulator

| Scenario   | PRISM         | PRISM-EB      |   max |cost diff| (USD) | viol diff range (pp)   |
|:-----------|:--------------|:--------------|------------------------:|:-----------------------|
| stationary | 1,073 / 1.28% | 1,069 / 1.43% |                      90 | -0.15 … +0.30          |
| growth     | 1,396 / 1.22% | 1,391 / 1.31% |                     108 | -0.15 … +0.45          |
| bursty     | 1,202 / 1.40% | 1,195 / 1.58% |                      96 | -0.30 … +0.45          |
| new_spike  | 1,395 / 1.55% | 1,389 / 1.64% |                     107 | -0.30 … +0.30          |
