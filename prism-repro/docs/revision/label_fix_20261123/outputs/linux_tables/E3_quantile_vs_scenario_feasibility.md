# Quantile-mode vs scenario-mode feasibility (§6.10 analogue)

Decision time is the median per-epoch optimiser call measured inside the simulation loop on the reference sandbox (1 shared CPU core).

| Scenario   | Identical P (share of epochs)   | Identical memory   | Cost diff   |   Viol diff (pp) |   Decision ms scenarios |   Decision ms quantile |
|:-----------|:--------------------------------|:-------------------|:------------|-----------------:|------------------------:|-----------------------:|
| stationary | 91.2%                           | 100.0%             | -0.29%      |            -0    |                    3.66 |                   3.52 |
| new_spike  | 94.3%                           | 100.0%             | -0.19%      |             0.15 |                    3.66 |                   3.53 |
