# Quantile-mode vs scenario-mode feasibility (§6.10 analogue)

Decision time is the median per-epoch optimiser call measured inside the simulation loop on the reference sandbox (1 shared CPU core).

| Scenario   | Identical P (share of epochs)   | Identical memory   | Cost diff   |   Viol diff (pp) |   Decision ms scenarios |   Decision ms quantile |
|:-----------|:--------------------------------|:-------------------|:------------|-----------------:|------------------------:|-----------------------:|
| stationary | 92.6%                           | 100.0%             | -0.25%      |             0.03 |                    3.43 |                   1.99 |
| new_spike  | 97.6%                           | 100.0%             | -0.09%      |             0.03 |                    3.55 |                   2.02 |
