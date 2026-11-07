# Per-stage provisioning caps, PRISM ε = 0.02 (mean over traces)

| Scenario   | Cap   |   Cost | Violating windows   | Infeasible epochs   |   Mean provisioned |   traces |
|:-----------|:------|-------:|:--------------------|:--------------------|-------------------:|---------:|
| stationary | None  |  1,149 | 0.86%               | 0.37%               |                253 |        5 |
| stationary | 250   |  1,145 | 0.86%               | 0.47%               |                250 |        5 |
| stationary | 60    |  1,372 | 0.00%               | 0.11%               |                117 |        5 |
| stationary | 40    |  1,335 | 0.00%               | 0.15%               |                102 |        5 |
| new_spike  | None  |  1,497 | 0.77%               | 0.24%               |                341 |        5 |
| new_spike  | 250   |  1,538 | 0.80%               | 0.46%               |                296 |        5 |
| new_spike  | 60    |  1,704 | 0.00%               | 0.15%               |                138 |        5 |
| new_spike  | 40    |  1,825 | 0.00%               | 0.29%               |                115 |        5 |
