# E11 regenerated: PRISM with Eq. (5) (occupancy) against PRISM with Erlang-B (the current main configuration)

PRE-CALIBRATION, fast simulator, traces 101-105, both validation-tuned by the common rule; test weeks.

Check: E11's explicit-Erlang-B rows equal E1's default PRISM rows run for run: True (150 rows)

| Scenario   | PRISM, Eq. (5)   | PRISM, Erlang-B   |   max |cost diff| (USD) | viol diff range (pp)   |
|:-----------|:-----------------|:------------------|------------------------:|:-----------------------|
| stationary | 956 / 1.64%      | 981 / 1.55%       |                     137 | -0.74 … +0.45          |
| growth     | 1,241 / 1.28%    | 1,273 / 1.31%     |                     183 | -0.45 … +0.45          |
| bursty     | 1,044 / 2.38%    | 1,076 / 2.14%     |                     168 | -1.34 … +0.30          |
| new_spike  | 1,237 / 2.26%    | 1,270 / 2.11%     |                     195 | -1.79 … +1.04          |

Selected eps per trace: Eq. (5) {101: 0.08, 102: 0.08, 103: 0.08, 104: 0.08, 105: 0.08}; Erlang-B {101: 0.05, 102: 0.03, 103: 0.08, 104: 0.08, 105: 0.08}
