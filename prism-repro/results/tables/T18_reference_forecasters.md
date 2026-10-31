# Probabilistic accuracy of the window-peak forecast (raw quantiles; mean over traces and scenarios)

| Forecaster     |   MAPE median (%) |   Pinball 0.5 |   Pinball 0.9 |   Pinball 0.99 | Cov q90   | Cov q99   |
|:---------------|------------------:|--------------:|--------------:|---------------:|:----------|:----------|
| gbm            |              13.7 |          78.2 |          68.7 |           29.8 | 85.1%     | 96.0%     |
| seasonal_naive |              34.2 |         158.6 |         120.8 |           34.2 | 82.9%     | 97.9%     |
| last5max       |              44.1 |         216.1 |         162.5 |           29.1 | 89.4%     | 98.8%     |
| ewma           |              23.8 |         147.5 |         132.9 |           22.9 | 89.8%     | 98.8%     |
