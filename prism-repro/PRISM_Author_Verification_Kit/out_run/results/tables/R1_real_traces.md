| Family | Selected parameter (per trace) | Cost (USD) | Violating windows (%) | Traces meeting 2% | Billing util. |
|---|---|---|---|---|---|
| On-demand | None, None, None, None, None | 895 ± 143 | 6.85 ± 13.26 | 3/5 | 0.00 |
| Static | 50, 50, 99, 99.9, 50 | 1,389 ± 1,214 | 0.68 ± 0.56 | 5/5 | 0.50 |
| Scheduled | 1.0, 1.0, 1.2, 2.0, 1.0 | 1,027 ± 253 | 2.41 ± 5.47 | 4/5 | 0.47 |
| Reactive | 0.9, 0.9, 0.65, 0.4, 0.9 | 1,353 ± 934 | 1.16 ± 1.39 | 4/5 | 0.40 |
| PredHead | 1.0, 1.0, 1.0, 1.4, 1.0 | 848 ± 149 | 0.71 ± 0.96 | 5/5 | 0.73 |
| PredHead+S | 1.0, 1.0, 1.0, 1.3, 1.0 | 909 ± 265 | 0.68 ± 0.93 | 5/5 | 0.68 |
| QuantProv-q90 | 0.9, 0.8, 0.7, 1.1, 0.8 | 908 ± 274 | 0.65 ± 1.08 | 5/5 | 0.70 |
| QuantProv-q99 | 0.8, 0.7, 0.7, 1.0, 0.6 | 917 ± 278 | 0.71 ± 0.94 | 5/5 | 0.68 |
| PRISM | 0.08, 0.08, 0.08, 0.02, 0.08 | 925 ± 244 | 0.39 ± 0.50 | 5/5 | 0.62 |

Paired PRISM minus comparator (mean ± 95% half-width over traces; cost % per trace; vw in points; counts = traces PRISM cheaper / fewer violating windows)

| Comparator | Cost (%) | Violating windows (pp) |
|---|---|---|
| PredHead | +8.5 ± 12.4 (0) | -0.33 ± 0.48 (3) |
| PredHead+S | +2.1 ± 2.8 (1) | -0.30 ± 0.43 (3) |
| QuantProv-q90 | +2.4 ± 4.0 (1) | -0.27 ± 0.67 (2) |
| QuantProv-q99 | +1.5 ± 4.0 (2) | -0.33 ± 0.58 (3) |
| Static | -20.2 ± 31.1 (5) | -0.30 ± 0.29 (4) |
| Scheduled | -9.9 ± 5.9 (5) | -2.02 ± 5.11 (4) |
| Reactive | -24.0 ± 22.7 (5) | -0.77 ± 1.09 (4) |
| On-demand | +3.7 ± 26.0 (4) | -6.46 ± 12.86 (5) |

Forecast quality on the test week (per trace):

| Trace | MAPE median (%) | cov90 raw | cov99 raw | cov90 cal | cov99 cal |
|---|---|---|---|---|---|
| huawei_fn150 | 4.5 | 0.842 | 0.973 | 0.939 | 0.990 |
| huawei_fn72 | 5.6 | 0.854 | 0.978 | 0.948 | 0.989 |
| huawei_fn60 | 6.3 | 0.825 | 0.964 | 0.944 | 0.991 |
| huawei_fn183 | 9.7 | 0.843 | 0.975 | 0.948 | 0.990 |
| huawei_fn42 | 4.5 | 0.882 | 0.977 | 0.954 | 0.991 |

Per trace, selected configuration on the test week (cost USD / violating windows %):

| Family | huawei_fn150 | huawei_fn72 | huawei_fn60 | huawei_fn183 | huawei_fn42 |
|---|---|---|---|---|---|
| On-demand | 859 / 0.89 | 832 / 1.64 | 813 / 5.65 | 875 / 25.60 | 1,097 / 0.45 |
| Static | 827 / 0.15 | 823 / 0.60 | 1,140 / 0.89 | 3,121 / 1.34 | 1,032 / 0.45 |
| Scheduled | 852 / 0.30 | 844 / 0.45 | 957 / 1.04 | 1,290 / 10.27 | 1,194 / 0.00 |
| Reactive | 904 / 0.60 | 895 / 1.19 | 1,139 / 1.04 | 2,681 / 2.98 | 1,146 / 0.00 |
| PredHead | 771 / 0.15 | 752 / 0.15 | 757 / 1.49 | 976 / 1.64 | 982 / 0.15 |
| PredHead+S | 772 / 0.30 | 757 / 0.00 | 782 / 1.34 | 1,252 / 1.64 | 983 / 0.15 |
| QuantProv-q90 | 773 / 0.15 | 755 / 0.00 | 761 / 1.93 | 1,260 / 1.19 | 991 / 0.00 |
| QuantProv-q99 | 773 / 0.15 | 757 / 0.45 | 769 / 1.79 | 1,266 / 1.19 | 1,020 / 0.00 |
| PRISM | 790 / 0.15 | 778 / 0.00 | 813 / 0.74 | 1,231 / 0.89 | 1,015 / 0.15 |
