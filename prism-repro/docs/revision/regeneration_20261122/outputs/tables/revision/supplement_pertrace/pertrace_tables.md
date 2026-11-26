# Per-trace PRISM ablations (REGENERATED rows at fd8b01a, test weeks; cost USD / violating windows)

PRISM at each trace's validation-chosen eps; the variants use the same eps. Pre-calibration; regenerated at fd8b01a
(R3.6). Built by scripts/revision/supplement_pertrace_tables.py from results/raw/E1 and results/raw/E3.

| Trace | eps | Scenario | PRISM | No conformal | Oracle forecast | No scale-in rule | Quantile feasibility |
|---|---|---|---|---|---|---|---|
| 101 | 0.05 | stationary | 1,001 / 1.19% | 903 / 2.08% | 921 / 0.15% | 917 / 1.64% | 1,001 / 1.19% |
| 101 | 0.05 | growth | 1,281 / 1.19% | 1,176 / 1.49% | 1,199 / 0.15% | not run | not run |
| 101 | 0.05 | bursty | 1,111 / 1.64% | 944 / 3.42% | 963 / 0.15% | not run | not run |
| 101 | 0.05 | new_spike | 1,259 / 1.64% | 1,123 / 5.65% | 1,169 / 0.15% | 1,154 / 5.36% | 1,259 / 1.64% |
| 102 | 0.03 | stationary | 1,104 / 0.74% | 950 / 1.64% | 929 / 0.15% | 996 / 1.19% | 1,104 / 0.74% |
| 102 | 0.03 | growth | 1,446 / 0.74% | 1,231 / 1.79% | 1,210 / 0.00% | not run | not run |
| 102 | 0.03 | bursty | 1,206 / 1.19% | 981 / 3.27% | 961 / 0.15% | not run | not run |
| 102 | 0.03 | new_spike | 1,437 / 0.60% | 1,183 / 2.98% | 1,178 / 0.00% | 1,292 / 1.93% | 1,437 / 0.60% |
| 103 | 0.08 | stationary | 937 / 2.53% | 907 / 2.83% | 922 / 0.00% | 865 / 2.38% | 933 / 2.53% |
| 103 | 0.08 | growth | 1,222 / 2.38% | 1,180 / 2.53% | 1,199 / 0.00% | not run | not run |
| 103 | 0.08 | bursty | 998 / 2.98% | 935 / 3.87% | 956 / 0.00% | not run | not run |
| 103 | 0.08 | new_spike | 1,198 / 3.42% | 1,133 / 5.65% | 1,170 / 0.15% | 1,110 / 7.59% | 1,195 / 3.57% |
| 104 | 0.08 | stationary | 925 / 2.23% | 880 / 2.38% | 903 / 0.15% | 851 / 2.38% | 922 / 2.23% |
| 104 | 0.08 | growth | 1,206 / 1.64% | 1,148 / 2.68% | 1,176 / 0.15% | not run | not run |
| 104 | 0.08 | bursty | 1,043 / 3.12% | 916 / 3.87% | 948 / 0.15% | not run | not run |
| 104 | 0.08 | new_spike | 1,264 / 2.53% | 1,101 / 6.10% | 1,150 / 0.15% | 1,149 / 5.65% | 1,264 / 2.53% |
| 105 | 0.08 | stationary | 938 / 1.04% | 910 / 1.49% | 923 / 0.15% | 866 / 1.49% | 934 / 1.19% |
| 105 | 0.08 | growth | 1,212 / 0.60% | 1,182 / 1.04% | 1,198 / 0.15% | not run | not run |
| 105 | 0.08 | bursty | 1,021 / 1.79% | 940 / 3.27% | 960 / 0.15% | not run | not run |
| 105 | 0.08 | new_spike | 1,194 / 2.38% | 1,126 / 3.57% | 1,170 / 0.15% | 1,109 / 4.02% | 1,191 / 2.38% |

Mean over the five traces (must equal results/tables/E3_ablation_conformal_oracle.md):

| Scenario | PRISM | No conformal | Oracle | traces where removing conformal raised violations |
|---|---|---|---|---|
| stationary | 981 / 1.55% | 910 / 2.08% | 919 / 0.12% | 5/5 |
| growth | 1,273 / 1.31% | 1,183 / 1.90% | 1,196 / 0.09% | 5/5 |
| bursty | 1,076 / 2.14% | 943 / 3.54% | 958 / 0.12% | 5/5 |
| new_spike | 1,270 / 2.11% | 1,133 / 4.79% | 1,167 / 0.12% | 5/5 |


# Per-trace QuantProv memory results (REGENERATED rows at fd8b01a, stationary test week; POST HOC selection)

Per trace, the cheapest grid point with at most 2% violating windows on the test week, else the least violating
(test-week knowledge, as results/tables/R2_quantprov_memory.md). Cell: cost USD / violating windows (setting).
Built from results/raw/R2 and results/raw/E4b.

| Non-scaling | Deadline s | Trace | PRISM with memory | QP-q90 1024 | QP-q99 1024 | QP-q90 2048 | QP-q99 2048 | PredHead 1024 | PredHead 2048 |
|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 14.5 | 101 | 932 / 1.79% (eps 0.08) | 922 / 1.93% (a 0.7) | 993 / 1.79% (a 0.6) | 1,313 / 0.00% (a 0.6) | 1,489 / 0.00% (a 0.6) | 880 / 1.79% (h 1.3) | 1,233 / 0.00% (h 1) |
| 0.5 | 14.5 | 102 | 945 / 1.79% (eps 0.08) | 950 / 1.79% (a 0.7) | 998 / 1.93% (a 0.6) | 1,348 / 0.00% (a 0.6) | 1,497 / 0.00% (a 0.6) | 940 / 1.79% (h 1.5) | 1,249 / 0.00% (h 1) |
| 0.5 | 13.0 | 101 | 1,690 / 0.00% (eps 0.01) | 876 / 100.00% (a 0.6) | 993 / 100.00% (a 0.6) | 1,313 / 0.00% (a 0.6) | 1,489 / 0.00% (a 0.6) | 820 / 100.00% (h 1) | 1,233 / 0.00% (h 1) |
| 0.5 | 13.0 | 102 | 1,722 / 0.00% (eps 0.01) | 899 / 100.00% (a 0.6) | 998 / 100.00% (a 0.6) | 1,348 / 0.00% (a 0.6) | 1,497 / 0.00% (a 0.6) | 831 / 100.00% (h 1) | 1,249 / 0.00% (h 1) |
| 0.5 | 12.0 | 101 | 1,576 / 0.00% (eps 0.03) | 876 / 100.00% (a 0.6) | 993 / 100.00% (a 0.6) | 1,313 / 0.00% (a 0.6) | 1,489 / 0.00% (a 0.6) | 820 / 100.00% (h 1) | 1,233 / 0.15% (h 1) |
| 0.5 | 12.0 | 102 | 1,615 / 0.00% (eps 0.03) | 899 / 100.00% (a 0.6) | 998 / 100.00% (a 0.6) | 1,348 / 0.00% (a 0.6) | 1,497 / 0.00% (a 0.6) | 831 / 100.00% (h 1) | 1,249 / 0.00% (h 1) |
| 0.5 | 11.0 | 101 | 1,438 / 1.34% (eps 0.08) | 876 / 100.00% (a 0.6) | 993 / 100.00% (a 0.6) | 1,313 / 1.79% (a 0.6) | 1,489 / 1.19% (a 0.6) | 820 / 100.00% (h 1) | 1,257 / 1.93% (h 1.1) |
| 0.5 | 11.0 | 102 | 1,467 / 1.04% (eps 0.08) | 899 / 100.00% (a 0.6) | 998 / 100.00% (a 0.6) | 1,348 / 1.79% (a 0.6) | 1,497 / 1.34% (a 0.6) | 831 / 100.00% (h 1) | 1,273 / 1.79% (h 1.1) |
| 0.15 | 14.5 | 101 | 932 / 1.79% (eps 0.08) | 922 / 1.93% (a 0.7) | 993 / 1.79% (a 0.6) | 1,010 / 0.00% (a 0.6) | 1,145 / 0.00% (a 0.6) | 880 / 1.79% (h 1.3) | 951 / 0.00% (h 1) |
| 0.15 | 14.5 | 102 | 945 / 1.79% (eps 0.08) | 950 / 1.79% (a 0.7) | 998 / 1.93% (a 0.6) | 1,037 / 0.00% (a 0.6) | 1,151 / 0.00% (a 0.6) | 940 / 1.79% (h 1.5) | 964 / 0.00% (h 1) |
| 0.15 | 12.0 | 101 | 1,098 / 0.00% (eps 0.03) | 876 / 100.00% (a 0.6) | 993 / 100.00% (a 0.6) | 1,010 / 0.00% (a 0.6) | 1,145 / 0.00% (a 0.6) | 820 / 100.00% (h 1) | 951 / 0.00% (h 1) |
| 0.15 | 12.0 | 102 | 1,115 / 0.00% (eps 0.03) | 899 / 100.00% (a 0.6) | 998 / 100.00% (a 0.6) | 1,037 / 0.00% (a 0.6) | 1,151 / 0.00% (a 0.6) | 831 / 100.00% (h 1) | 964 / 0.00% (h 1) |

Reproduction of the stored mean tables from these per-trace values:

- ablation mean stationary: reproduced
- ablation mean growth: reproduced
- ablation mean bursty: reproduced
- ablation mean new_spike: reproduced
- memory mean 0.5/14.5 PRISM: reproduced
- memory mean 0.5/14.5 q901024: reproduced
- memory mean 0.5/14.5 q991024: reproduced
- memory mean 0.5/14.5 q902048: reproduced
- memory mean 0.5/14.5 q992048: reproduced
- memory mean 0.5/14.5 PH1024: reproduced
- memory mean 0.5/14.5 PH2048: reproduced
- memory mean 0.5/13.0 PRISM: reproduced
- memory mean 0.5/13.0 q901024: reproduced
- memory mean 0.5/13.0 q991024: reproduced
- memory mean 0.5/13.0 q902048: reproduced
- memory mean 0.5/13.0 q992048: reproduced
- memory mean 0.5/13.0 PH1024: reproduced
- memory mean 0.5/13.0 PH2048: reproduced
- memory mean 0.5/12.0 PRISM: reproduced
- memory mean 0.5/12.0 q901024: reproduced
- memory mean 0.5/12.0 q991024: reproduced
- memory mean 0.5/12.0 q902048: reproduced
- memory mean 0.5/12.0 q992048: reproduced
- memory mean 0.5/12.0 PH1024: reproduced
- memory mean 0.5/12.0 PH2048: reproduced
- memory mean 0.5/11.0 PRISM: reproduced
- memory mean 0.5/11.0 q901024: reproduced
- memory mean 0.5/11.0 q991024: reproduced
- memory mean 0.5/11.0 q902048: reproduced
- memory mean 0.5/11.0 q992048: reproduced
- memory mean 0.5/11.0 PH1024: reproduced
- memory mean 0.5/11.0 PH2048: reproduced
- memory mean 0.15/14.5 PRISM: reproduced
- memory mean 0.15/14.5 q901024: reproduced
- memory mean 0.15/14.5 q991024: reproduced
- memory mean 0.15/14.5 q902048: reproduced
- memory mean 0.15/14.5 q992048: reproduced
- memory mean 0.15/14.5 PH1024: reproduced
- memory mean 0.15/14.5 PH2048: reproduced
- memory mean 0.15/12.0 PRISM: reproduced
- memory mean 0.15/12.0 q901024: reproduced
- memory mean 0.15/12.0 q991024: reproduced
- memory mean 0.15/12.0 q902048: reproduced
- memory mean 0.15/12.0 q992048: reproduced
- memory mean 0.15/12.0 PH1024: reproduced
- memory mean 0.15/12.0 PH2048: reproduced
