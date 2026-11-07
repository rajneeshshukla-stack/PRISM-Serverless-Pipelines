# Quantile-mode vs scenario-mode feasibility (§6.10 analogue)

Decision time is the median per-epoch optimiser call measured inside the simulation loop on the reference sandbox (1 shared CPU core).

| Scenario   | Identical P (share of epochs)   | Identical memory   | Cost diff   |   Viol diff (pp) |   Decision ms scenarios |   Decision ms quantile |
|:-----------|:--------------------------------|:-------------------|:------------|-----------------:|------------------------:|-----------------------:|
| stationary | 98.9%                           | 100.0%             | -0.04%      |                0 |                     1.8 |                   1.62 |
| new_spike  | 99.5%                           | 100.0%             | -0.02%      |                0 |                     1.8 |                   1.66 |
