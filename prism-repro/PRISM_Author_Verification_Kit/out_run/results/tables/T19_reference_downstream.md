# Downstream provisioning by forecaster (validation-tuned; cost USD / violating windows)

| Forecaster + method            | stationary    | growth        | bursty        | new_spike     |
|:-------------------------------|:--------------|:--------------|:--------------|:--------------|
| gbm + PRISM                    | 1,073 / 1.28% | 1,396 / 1.22% | 1,202 / 1.40% | 1,395 / 1.55% |
| gbm + QuantProv q99            | 1,150 / 0.92% | 1,512 / 0.83% | 1,301 / 0.95% | 1,516 / 0.98% |
| seasonal_naive + PRISM         | 1,089 / 2.11% | 1,430 / 2.11% | 1,229 / 2.62% | 1,600 / 1.76% |
| seasonal_naive + QuantProv q99 | 1,298 / 1.04% | 1,720 / 0.95% | 1,492 / 1.34% | 1,990 / 0.68% |
| last5max + PRISM               | 1,514 / 1.55% | 1,940 / 1.49% | 1,619 / 1.25% | 1,900 / 1.43% |
| last5max + QuantProv q99       | 1,631 / 1.28% | 2,114 / 1.31% | 1,756 / 1.04% | 2,065 / 1.22% |
| ewma + PRISM                   | 1,230 / 1.85% | 1,572 / 1.67% | 1,303 / 1.55% | 1,503 / 1.79% |
| ewma + QuantProv q99           | 1,268 / 1.46% | 1,651 / 1.37% | 1,355 / 1.43% | 1,572 / 1.52% |
