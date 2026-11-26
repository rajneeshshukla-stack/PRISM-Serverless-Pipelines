# Event-level max in-flight / fast-simulator peak draw (quantiles) and latency-sampling window flips (detail trace)

| scenario   | policy    |   sampling_flip_mean |   inflight_ratio_q10 |   inflight_ratio_q50 |   inflight_ratio_q90 |   inflight_ratio_q99 |
|:-----------|:----------|---------------------:|---------------------:|---------------------:|---------------------:|---------------------:|
| stationary | OnDemand  |                0.061 |                1.1   |                1.5   |                2.25  |                3.649 |
| stationary | Static    |                0.037 |                1.1   |                1.5   |                2.222 |                3.5   |
| stationary | Scheduled |                0.045 |                1.098 |                1.5   |                2.222 |                3.466 |
| stationary | Reactive  |                0.046 |                1.1   |                1.5   |                2.222 |                3.469 |
| stationary | PredHead  |                0.02  |                1.095 |                1.5   |                2.2   |                3.47  |
| stationary | PRISM     |                0.031 |                1.095 |                1.5   |                2.208 |                3.467 |
| new_spike  | OnDemand  |                0.096 |                1.092 |                1.478 |                2.222 |                3.75  |
| new_spike  | Static    |                0.072 |                1.088 |                1.468 |                2.189 |                3.529 |
| new_spike  | Scheduled |                0.087 |                1.087 |                1.467 |                2.175 |                3.471 |
| new_spike  | Reactive  |                0.04  |                1.085 |                1.462 |                2.167 |                3.426 |
| new_spike  | PredHead  |                0.057 |                1.086 |                1.467 |                2.182 |                3.528 |
| new_spike  | PRISM     |                0.066 |                1.085 |                1.463 |                2.167 |                3.455 |
