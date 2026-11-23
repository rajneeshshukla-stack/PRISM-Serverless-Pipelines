# Downstream provisioning by forecaster (validation-tuned; cost USD / violating windows)

| Forecaster + method            | stationary    | growth        | bursty        | new_spike     |
|:-------------------------------|:--------------|:--------------|:--------------|:--------------|
| gbm + PRISM                    | 981 / 1.55%   | 1,273 / 1.31% | 1,076 / 2.14% | 1,270 / 2.11% |
| gbm + QuantProv q99            | 1,048 / 1.40% | 1,364 / 1.31% | 1,173 / 1.37% | 1,386 / 1.25% |
| seasonal_naive + PRISM         | 1,010 / 2.11% | 1,329 / 1.99% | 1,132 / 2.53% | 1,483 / 1.82% |
| seasonal_naive + QuantProv q99 | 1,298 / 0.74% | 1,720 / 0.71% | 1,492 / 0.98% | 1,990 / 0.57% |
| last5max + PRISM               | 1,389 / 1.88% | 1,781 / 1.76% | 1,484 / 1.58% | 1,745 / 1.79% |
| last5max + QuantProv q99       | 1,465 / 1.52% | 1,900 / 1.31% | 1,573 / 1.28% | 1,854 / 1.37% |
| ewma + PRISM                   | 1,133 / 1.93% | 1,454 / 1.93% | 1,200 / 1.85% | 1,389 / 2.14% |
| ewma + QuantProv q99           | 1,167 / 1.70% | 1,519 / 1.43% | 1,243 / 1.64% | 1,448 / 1.70% |
