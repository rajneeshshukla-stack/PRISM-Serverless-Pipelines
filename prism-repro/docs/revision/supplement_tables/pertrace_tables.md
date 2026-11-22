# Per-trace PRISM ablations (SUBMITTED rows, test weeks; cost USD / violating windows)

PRISM at each trace's validation-chosen eps; the variants use the same eps. Pre-calibration; values change at
the regeneration. Built by scripts/revision/supplement_pertrace_tables.py from results/raw/E1 and results/raw/E3.

| Trace | eps | Scenario | PRISM | No conformal | Oracle forecast | No scale-in rule | Quantile feasibility |
|---|---|---|---|---|---|---|---|
| 101 | 0.02 | stationary | 1,132 / 0.89% | 983 / 1.93% | 952 / 0.45% | 1,025 / 1.04% | 1,132 / 0.89% |
| 101 | 0.02 | growth | 1,461 / 0.89% | 1,267 / 1.64% | 1,228 / 0.45% | not run | not run |
| 101 | 0.02 | bursty | 1,268 / 1.04% | 1,027 / 2.38% | 995 / 0.45% | not run | not run |
| 101 | 0.02 | new_spike | 1,427 / 1.49% | 1,214 / 4.76% | 1,203 / 0.74% | 1,292 / 2.53% | 1,427 / 1.49% |
| 102 | 0.03 | stationary | 1,148 / 0.60% | 967 / 2.38% | 945 / 0.15% | 1,031 / 1.04% | 1,148 / 0.60% |
| 102 | 0.03 | growth | 1,485 / 0.60% | 1,251 / 1.93% | 1,229 / 0.45% | not run | not run |
| 102 | 0.03 | bursty | 1,238 / 1.04% | 998 / 3.27% | 978 / 0.15% | not run | not run |
| 102 | 0.03 | new_spike | 1,464 / 0.74% | 1,200 / 4.91% | 1,195 / 0.74% | 1,317 / 3.27% | 1,463 / 0.74% |
| 103 | 0.05 | stationary | 1,036 / 2.23% | 932 / 3.42% | 935 / 0.45% | 945 / 2.68% | 1,035 / 2.23% |
| 103 | 0.05 | growth | 1,348 / 2.08% | 1,210 / 3.27% | 1,216 / 0.45% | not run | not run |
| 103 | 0.05 | bursty | 1,133 / 2.53% | 962 / 4.17% | 970 / 0.30% | not run | not run |
| 103 | 0.05 | new_spike | 1,343 / 3.12% | 1,161 / 7.29% | 1,187 / 0.60% | 1,227 / 5.65% | 1,343 / 3.12% |
| 104 | 0.05 | stationary | 1,026 / 1.49% | 903 / 2.38% | 916 / 0.30% | 931 / 1.64% | 1,026 / 1.49% |
| 104 | 0.05 | growth | 1,365 / 1.49% | 1,176 / 2.68% | 1,193 / 0.30% | not run | not run |
| 104 | 0.05 | bursty | 1,200 / 1.64% | 942 / 3.87% | 962 / 0.30% | not run | not run |
| 104 | 0.05 | new_spike | 1,420 / 1.34% | 1,132 / 6.25% | 1,166 / 0.45% | 1,271 / 4.17% | 1,420 / 1.34% |
| 105 | 0.05 | stationary | 1,021 / 1.19% | 933 / 2.98% | 937 / 0.30% | 932 / 1.34% | 1,021 / 1.19% |
| 105 | 0.05 | growth | 1,323 / 1.04% | 1,210 / 2.53% | 1,215 / 0.45% | not run | not run |
| 105 | 0.05 | bursty | 1,170 / 0.74% | 967 / 3.87% | 975 / 0.45% | not run | not run |
| 105 | 0.05 | new_spike | 1,322 / 1.04% | 1,151 / 5.51% | 1,187 / 0.74% | 1,215 / 3.87% | 1,322 / 1.04% |

Mean over the five traces (must equal results/tables/E3_ablation_conformal_oracle.md):

| Scenario | PRISM | No conformal | Oracle | traces where removing conformal raised violations |
|---|---|---|---|---|
| stationary | 1,073 / 1.28% | 943 / 2.62% | 937 / 0.33% | 5/5 |
| growth | 1,396 / 1.22% | 1,223 / 2.41% | 1,216 / 0.42% | 5/5 |
| bursty | 1,202 / 1.40% | 979 / 3.51% | 976 / 0.33% | 5/5 |
| new_spike | 1,395 / 1.55% | 1,172 / 5.74% | 1,188 / 0.65% | 5/5 |


# Per-trace QuantProv memory results (SUBMITTED rows, stationary test week; POST HOC selection)

Per trace, the cheapest grid point with at most 2% violating windows on the test week, else the least violating
(test-week knowledge, as results/tables/R2_quantprov_memory.md). Cell: cost USD / violating windows (setting).
Built from results/raw/R2 and results/raw/E4b.

| Non-scaling | Deadline s | Trace | PRISM with memory | QP-q90 1024 | QP-q99 1024 | QP-q90 2048 | QP-q99 2048 | PredHead 1024 | PredHead 2048 |
|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 14.5 | 101 | 1,021 / 1.34% (eps 0.05) | 966 / 1.93% (a 0.8) | 1,135 / 1.04% (a 0.8) | 1,306 / 0.00% (a 0.6) | 1,478 / 0.00% (a 0.6) | 880 / 1.93% (h 1.3) | 1,233 / 0.00% (h 1) |
| 0.5 | 14.5 | 102 | 970 / 1.79% (eps 0.08) | 1,011 / 1.64% (a 0.8) | 1,078 / 1.34% (a 0.7) | 1,354 / 0.00% (a 0.6) | 1,502 / 0.00% (a 0.6) | 914 / 1.64% (h 1.4) | 1,249 / 0.00% (h 1) |
| 0.5 | 13.0 | 101 | 1,710 / 0.00% (eps 0.01) | 1,299 / 69.94% (a 1.4) | 1,599 / 69.79% (a 1.4) | 1,306 / 0.15% (a 0.6) | 1,478 / 0.00% (a 0.6) | 1,036 / 70.68% (h 1.9) | 1,233 / 0.00% (h 1) |
| 0.5 | 13.0 | 102 | 1,773 / 0.00% (eps 0.01) | 1,437 / 69.49% (a 1.5) | 1,632 / 68.90% (a 1.4) | 1,354 / 0.00% (a 0.6) | 1,502 / 0.00% (a 0.6) | 1,073 / 70.39% (h 2) | 1,249 / 0.00% (h 1) |
| 0.5 | 12.0 | 101 | 1,608 / 0.30% (eps 0.03) | 871 / 100.00% (a 0.6) | 985 / 100.00% (a 0.6) | 1,306 / 0.74% (a 0.6) | 1,478 / 0.89% (a 0.6) | 820 / 100.00% (h 1) | 1,233 / 0.89% (h 1) |
| 0.5 | 12.0 | 102 | 1,669 / 0.15% (eps 0.03) | 903 / 100.00% (a 0.6) | 1,002 / 100.00% (a 0.6) | 1,354 / 0.45% (a 0.6) | 1,502 / 0.30% (a 0.6) | 831 / 100.00% (h 1) | 1,249 / 0.45% (h 1) |
| 0.5 | 11.0 | 101 | 1,468 / 1.19% (eps 0.08) | 871 / 100.00% (a 0.6) | 985 / 100.00% (a 0.6) | 1,372 / 1.93% (a 0.7) | 1,588 / 1.34% (a 0.7) | 820 / 100.00% (h 1) | 1,258 / 1.93% (h 1.1) |
| 0.5 | 11.0 | 102 | 1,519 / 1.04% (eps 0.08) | 903 / 100.00% (a 0.6) | 1,002 / 100.00% (a 0.6) | 1,514 / 1.19% (a 0.8) | 1,616 / 1.04% (a 0.7) | 831 / 100.00% (h 1) | 1,303 / 1.93% (h 1.2) |
| 0.15 | 14.5 | 101 | 1,021 / 1.34% (eps 0.05) | 966 / 1.93% (a 0.8) | 1,135 / 1.04% (a 0.8) | 1,005 / 0.00% (a 0.6) | 1,136 / 0.00% (a 0.6) | 880 / 1.93% (h 1.3) | 951 / 0.00% (h 1) |
| 0.15 | 14.5 | 102 | 970 / 1.79% (eps 0.08) | 1,011 / 1.64% (a 0.8) | 1,078 / 1.34% (a 0.7) | 1,041 / 0.00% (a 0.6) | 1,155 / 0.00% (a 0.6) | 914 / 1.64% (h 1.4) | 964 / 0.00% (h 1) |
| 0.15 | 12.0 | 101 | 1,118 / 0.00% (eps 0.03) | 871 / 100.00% (a 0.6) | 985 / 100.00% (a 0.6) | 1,005 / 0.00% (a 0.6) | 1,136 / 0.00% (a 0.6) | 820 / 100.00% (h 1) | 951 / 0.00% (h 1) |
| 0.15 | 12.0 | 102 | 1,143 / 0.00% (eps 0.03) | 903 / 100.00% (a 0.6) | 1,002 / 100.00% (a 0.6) | 1,041 / 0.00% (a 0.6) | 1,155 / 0.00% (a 0.6) | 831 / 100.00% (h 1) | 964 / 0.00% (h 1) |

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
