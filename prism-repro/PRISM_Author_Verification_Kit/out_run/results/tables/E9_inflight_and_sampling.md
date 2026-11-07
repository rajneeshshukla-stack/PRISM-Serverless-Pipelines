# Event-level max in-flight / fast-simulator peak draw (quantiles) and latency-sampling window flips (detail trace)

| scenario   | policy    |   sampling_flip_mean |   inflight_ratio_q10 |   inflight_ratio_q50 |   inflight_ratio_q90 |   inflight_ratio_q99 |
|:-----------|:----------|---------------------:|---------------------:|---------------------:|---------------------:|---------------------:|
| stationary | OnDemand  |                0.061 |                1.1   |                1.5   |                2.25  |                3.649 |
| stationary | Static    |                0.012 |                1.097 |                1.5   |                2.2   |                3.41  |
| stationary | Scheduled |                0.023 |                1.097 |                1.5   |                2.2   |                3.41  |
| stationary | Reactive  |                0.03  |                1.097 |                1.5   |                2.206 |                3.429 |
| stationary | PredHead  |                0.013 |                1.095 |                1.5   |                2.2   |                3.469 |
| stationary | PRISM     |                0.01  |                1.094 |                1.5   |                2.2   |                3.429 |
| new_spike  | OnDemand  |                0.096 |                1.092 |                1.478 |                2.222 |                3.75  |
| new_spike  | Static    |                0.034 |                1.083 |                1.462 |                2.167 |                3.4   |
| new_spike  | Scheduled |                0.049 |                1.084 |                1.462 |                2.167 |                3.394 |
| new_spike  | Reactive  |                0.027 |                1.083 |                1.459 |                2.158 |                3.399 |
| new_spike  | PredHead  |                0.054 |                1.086 |                1.466 |                2.177 |                3.5   |
| new_spike  | PRISM     |                0.021 |                1.083 |                1.458 |                2.167 |                3.394 |
