# Share of stage executions served on demand: event-level vs analytic estimates (5 provisioned policies; detail trace)

| Scenario   | Event-level   | Erlang-B (mean load)   | Fast simulator   | o(P,c) mean load   | o(P,c_eff) (optimiser)   |
|:-----------|:--------------|:-----------------------|:-----------------|:-------------------|:-------------------------|
| stationary | 3.06%         | 3.11% (+2%)            | 3.04% (-1%)      | 2.17% (-29%)       | 3.71% (+21%)             |
| new_spike  | 4.26%         | 4.30% (+1%)            | 4.45% (+4%)      | 3.39% (-20%)       | 5.00% (+17%)             |
