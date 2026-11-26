# Share of stage executions served on demand: event-level vs analytic estimates (5 provisioned policies; detail trace)

| Scenario   | Event-level   | Erlang-B (mean load)   | Fast simulator   | o(P,c) mean load   | o(P,c_eff) (optimiser)   |
|:-----------|:--------------|:-----------------------|:-----------------|:-------------------|:-------------------------|
| stationary | 2.98%         | 3.03% (+2%)            | 2.95% (-1%)      | 2.11% (-29%)       | 3.62% (+22%)             |
| new_spike  | 4.23%         | 4.28% (+1%)            | 4.42% (+5%)      | 3.38% (-20%)       | 4.99% (+18%)             |
