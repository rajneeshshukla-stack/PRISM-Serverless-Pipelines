# Frozen (validation-tuned) vs test-retuned parameters (cost USD / violating windows); retuned uses test-week knowledge and is a diagnostic only

| Scenario   | PredHead frozen   | PredHead retuned (diagnostic)   | PRISM frozen   | PRISM retuned (diagnostic)   |
|:-----------|:------------------|:--------------------------------|:---------------|:-----------------------------|
| stationary | 859 / 2.20%       | 925 / 1.79%                     | 981 / 1.55%    | 982 / 1.49%                  |
| growth     | 1,117 / 2.17%     | 1,159 / 1.93%                   | 1,273 / 1.31%  | 1,234 / 1.43%                |
| bursty     | 888 / 3.69%       | 1,059 / 1.96%                   | 1,076 / 2.14%  | 1,125 / 1.61%                |
| new_spike  | 1,077 / 7.92%     | 1,311 / 1.76%                   | 1,270 / 2.11%  | 1,327 / 1.22%                |
