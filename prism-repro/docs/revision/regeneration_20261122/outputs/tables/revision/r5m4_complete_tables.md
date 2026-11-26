# Per-trace PRISM ablations, complete (REGENERATED rows at fd8b01a, test weeks; cost USD / violating windows)

PRISM at each trace's validation-chosen eps; the variants use the same eps. Pre-calibration; regenerated at fd8b01a
(R3.6). Built by scripts/revision/supplement_pertrace_tables.py from results/raw/E1 and results/raw/E3.

| Trace | eps | Scenario | PRISM | No conformal | Oracle forecast | No scale-in rule | Quantile feasibility |
|---|---|---|---|---|---|---|---|
| 101 | 0.05 | stationary | 1,001 / 1.19% | 903 / 2.08% | 921 / 0.15% | 917 / 1.64% | 1,001 / 1.19% |
| 101 | 0.05 | growth | 1,281 / 1.19% | 1,176 / 1.49% | 1,199 / 0.15% | 1,171 / 1.49% (new) | 1,281 / 1.19% (new) |
| 101 | 0.05 | bursty | 1,111 / 1.64% | 944 / 3.42% | 963 / 0.15% | 1,007 / 2.53% (new) | 1,111 / 1.64% (new) |
| 101 | 0.05 | new_spike | 1,259 / 1.64% | 1,123 / 5.65% | 1,169 / 0.15% | 1,154 / 5.36% | 1,259 / 1.64% |
| 102 | 0.03 | stationary | 1,104 / 0.74% | 950 / 1.64% | 929 / 0.15% | 996 / 1.19% | 1,104 / 0.74% |
| 102 | 0.03 | growth | 1,446 / 0.74% | 1,231 / 1.79% | 1,210 / 0.00% | 1,298 / 1.49% (new) | 1,446 / 0.74% (new) |
| 102 | 0.03 | bursty | 1,206 / 1.19% | 981 / 3.27% | 961 / 0.15% | 1,077 / 2.23% (new) | 1,206 / 1.19% (new) |
| 102 | 0.03 | new_spike | 1,437 / 0.60% | 1,183 / 2.98% | 1,178 / 0.00% | 1,292 / 1.93% | 1,437 / 0.60% |
| 103 | 0.08 | stationary | 937 / 2.53% | 907 / 2.83% | 922 / 0.00% | 865 / 2.38% | 933 / 2.53% |
| 103 | 0.08 | growth | 1,222 / 2.38% | 1,180 / 2.53% | 1,199 / 0.00% | 1,126 / 2.53% (new) | 1,217 / 2.38% (new) |
| 103 | 0.08 | bursty | 998 / 2.98% | 935 / 3.87% | 956 / 0.00% | 918 / 3.27% (new) | 996 / 2.98% (new) |
| 103 | 0.08 | new_spike | 1,198 / 3.42% | 1,133 / 5.65% | 1,170 / 0.15% | 1,110 / 7.59% | 1,195 / 3.57% |
| 104 | 0.08 | stationary | 925 / 2.23% | 880 / 2.38% | 903 / 0.15% | 851 / 2.38% | 922 / 2.23% |
| 104 | 0.08 | growth | 1,206 / 1.64% | 1,148 / 2.68% | 1,176 / 0.15% | 1,107 / 1.93% (new) | 1,201 / 1.79% (new) |
| 104 | 0.08 | bursty | 1,043 / 3.12% | 916 / 3.87% | 948 / 0.15% | 945 / 3.42% (new) | 1,043 / 3.12% (new) |
| 104 | 0.08 | new_spike | 1,264 / 2.53% | 1,101 / 6.10% | 1,150 / 0.15% | 1,149 / 5.65% | 1,264 / 2.53% |
| 105 | 0.08 | stationary | 938 / 1.04% | 910 / 1.49% | 923 / 0.15% | 866 / 1.49% | 934 / 1.19% |
| 105 | 0.08 | growth | 1,212 / 0.60% | 1,182 / 1.04% | 1,198 / 0.15% | 1,118 / 1.49% (new) | 1,206 / 0.60% (new) |
| 105 | 0.08 | bursty | 1,021 / 1.79% | 940 / 3.27% | 960 / 0.15% | 934 / 2.68% (new) | 1,019 / 1.93% (new) |
| 105 | 0.08 | new_spike | 1,194 / 2.38% | 1,126 / 3.57% | 1,170 / 0.15% | 1,109 / 4.02% | 1,191 / 2.38% |

Mean over the five traces (must equal results/tables/E3_ablation_conformal_oracle.md):

| Scenario | PRISM | No conformal | Oracle | traces where removing conformal raised violations |
|---|---|---|---|---|
| stationary | 981 / 1.55% | 910 / 2.08% | 919 / 0.12% | 5/5 |
| growth | 1,273 / 1.31% | 1,183 / 1.90% | 1,196 / 0.09% | 5/5 |
| bursty | 1,076 / 2.14% | 943 / 3.54% | 958 / 0.12% | 5/5 |
| new_spike | 1,270 / 2.11% | 1,133 / 4.79% | 1,167 / 0.12% | 5/5 |

Filled cells: 20 (marked "(new)"): no scale-in rule and quantile feasibility for the growth and bursty test
weeks, run by docs/revision/regeneration_20261122/r5m4_missing_runs.py at the same validation-selected eps.
Consistency: the stationary and new-spike cells rerun by the same script equal the E3-derived cells in 10 of 10 rows.


# QuantProv memory results on the widened grid (REGENERATED rows at fd8b01a, stationary test week; POST HOC)

Same selection rule as results/tables/R2_quantprov_memory.md (cheapest grid point with at most 2% violating
windows on the test week, else the least violating). Paper grid a = 0.6-1.5 (results/raw/R2); widened grid adds
a = 0.4, 0.5, 1.6, 1.8, 2.0 (experiment.GRIDS_WIDE; results/r5m4_missing/quantprov_memory_widened.jsonl).
"edge" = the selection is at an end of the grid searched.

| Non-scaling | Deadline s | Trace | Rule, memory MB | Paper grid | Widened grid | Selection changed |
|---|---|---|---|---|---|---|
| 0.5 | 14.5 | 101 | QP-q90 1024 | 922 / 1.93% (a 0.7) | 922 / 1.93% (a 0.7) | no |
| 0.5 | 14.5 | 101 | QP-q90 2048 | 1,313 / 0.00% (a 0.6, edge) | 1,222 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 14.5 | 101 | QP-q99 1024 | 993 / 1.79% (a 0.6, edge) | 993 / 1.79% (a 0.6) | no |
| 0.5 | 14.5 | 101 | QP-q99 2048 | 1,489 / 0.00% (a 0.6, edge) | 1,286 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 14.5 | 102 | QP-q90 1024 | 950 / 1.79% (a 0.7) | 950 / 1.79% (a 0.7) | no |
| 0.5 | 14.5 | 102 | QP-q90 2048 | 1,348 / 0.00% (a 0.6, edge) | 1,243 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 14.5 | 102 | QP-q99 1024 | 998 / 1.93% (a 0.6, edge) | 998 / 1.93% (a 0.6) | no |
| 0.5 | 14.5 | 102 | QP-q99 2048 | 1,497 / 0.00% (a 0.6, edge) | 1,295 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 101 | QP-q90 1024 | 876 / 100.00% (a 0.6, edge) | 813 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 101 | QP-q90 2048 | 1,313 / 0.00% (a 0.6, edge) | 1,222 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 101 | QP-q99 1024 | 993 / 100.00% (a 0.6, edge) | 857 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 101 | QP-q99 2048 | 1,489 / 0.00% (a 0.6, edge) | 1,286 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 102 | QP-q90 1024 | 899 / 100.00% (a 0.6, edge) | 828 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 102 | QP-q90 2048 | 1,348 / 0.00% (a 0.6, edge) | 1,243 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 102 | QP-q99 1024 | 998 / 100.00% (a 0.6, edge) | 863 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 13.0 | 102 | QP-q99 2048 | 1,497 / 0.00% (a 0.6, edge) | 1,295 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 101 | QP-q90 1024 | 876 / 100.00% (a 0.6, edge) | 813 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 101 | QP-q90 2048 | 1,313 / 0.00% (a 0.6, edge) | 1,222 / 0.45% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 101 | QP-q99 1024 | 993 / 100.00% (a 0.6, edge) | 857 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 101 | QP-q99 2048 | 1,489 / 0.00% (a 0.6, edge) | 1,286 / 0.15% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 102 | QP-q90 1024 | 899 / 100.00% (a 0.6, edge) | 828 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 102 | QP-q90 2048 | 1,348 / 0.00% (a 0.6, edge) | 1,243 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 102 | QP-q99 1024 | 998 / 100.00% (a 0.6, edge) | 863 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 12.0 | 102 | QP-q99 2048 | 1,497 / 0.00% (a 0.6, edge) | 1,295 / 0.00% (a 0.4, edge) | yes |
| 0.5 | 11.0 | 101 | QP-q90 1024 | 876 / 100.00% (a 0.6, edge) | 813 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 11.0 | 101 | QP-q90 2048 | 1,313 / 1.79% (a 0.6, edge) | 1,313 / 1.79% (a 0.6) | no |
| 0.5 | 11.0 | 101 | QP-q99 1024 | 993 / 100.00% (a 0.6, edge) | 857 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 11.0 | 101 | QP-q99 2048 | 1,489 / 1.19% (a 0.6, edge) | 1,489 / 1.19% (a 0.6) | no |
| 0.5 | 11.0 | 102 | QP-q90 1024 | 899 / 100.00% (a 0.6, edge) | 828 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 11.0 | 102 | QP-q90 2048 | 1,348 / 1.79% (a 0.6, edge) | 1,348 / 1.79% (a 0.6) | no |
| 0.5 | 11.0 | 102 | QP-q99 1024 | 998 / 100.00% (a 0.6, edge) | 863 / 100.00% (a 0.4, edge) | yes |
| 0.5 | 11.0 | 102 | QP-q99 2048 | 1,497 / 1.34% (a 0.6, edge) | 1,497 / 1.34% (a 0.6) | no |
| 0.15 | 14.5 | 101 | QP-q90 1024 | 922 / 1.93% (a 0.7) | 922 / 1.93% (a 0.7) | no |
| 0.15 | 14.5 | 101 | QP-q90 2048 | 1,010 / 0.00% (a 0.6, edge) | 942 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 14.5 | 101 | QP-q99 1024 | 993 / 1.79% (a 0.6, edge) | 993 / 1.79% (a 0.6) | no |
| 0.15 | 14.5 | 101 | QP-q99 2048 | 1,145 / 0.00% (a 0.6, edge) | 990 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 14.5 | 102 | QP-q90 1024 | 950 / 1.79% (a 0.7) | 950 / 1.79% (a 0.7) | no |
| 0.15 | 14.5 | 102 | QP-q90 2048 | 1,037 / 0.00% (a 0.6, edge) | 958 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 14.5 | 102 | QP-q99 1024 | 998 / 1.93% (a 0.6, edge) | 998 / 1.93% (a 0.6) | no |
| 0.15 | 14.5 | 102 | QP-q99 2048 | 1,151 / 0.00% (a 0.6, edge) | 998 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 101 | QP-q90 1024 | 876 / 100.00% (a 0.6, edge) | 813 / 100.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 101 | QP-q90 2048 | 1,010 / 0.00% (a 0.6, edge) | 942 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 101 | QP-q99 1024 | 993 / 100.00% (a 0.6, edge) | 857 / 100.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 101 | QP-q99 2048 | 1,145 / 0.00% (a 0.6, edge) | 990 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 102 | QP-q90 1024 | 899 / 100.00% (a 0.6, edge) | 828 / 100.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 102 | QP-q90 2048 | 1,037 / 0.00% (a 0.6, edge) | 958 / 0.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 102 | QP-q99 1024 | 998 / 100.00% (a 0.6, edge) | 863 / 100.00% (a 0.4, edge) | yes |
| 0.15 | 12.0 | 102 | QP-q99 2048 | 1,151 / 0.00% (a 0.6, edge) | 998 / 0.00% (a 0.4, edge) | yes |

Selections changed by widening: 36 of 48. Edge selections: paper grid 44 of 48; widened grid 36 of 48.
Widened-grid edge selections by kind: infeasible at every a (least violating, then cheapest): 16; meets 2% at the grid end (cost would fall further): 20.
Where the rule still meets 2% at a = 0.4 (all at 2048 MB), the QuantProv cost is an upper bound set by the grid,
so the stored QuantProv-2048 costs (paper grid, a = 0.6) overstate what the rule can reach; this weakens, not
strengthens, the comparison in PRISM's favour. The 1024 MB cells at deadlines of 13 s or less violate 100% of
windows at every a, so their selection is the cheapest infeasible setting and the edge flag carries no meaning.

