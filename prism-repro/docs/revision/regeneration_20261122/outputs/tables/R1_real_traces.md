| Family | Selected parameter (per trace) | Cost (USD) | Violating windows (%) | Traces meeting 2% | Billing util. |
|---|---|---|---|---|---|
| On-demand | None, None, None, None, None | 895 ± 143 | 6.82 ± 14.41 | 3/5 | 0.00 |
| Static | 50, 50, 95, 99.9, 50 | 1,349 ± 1,235 | 0.74 ± 0.95 | 5/5 | 0.53 |
| Scheduled | 1.0, 1.0, 1.0, 2.0, 1.0 | 1,012 ± 265 | 2.50 ± 6.14 | 4/5 | 0.49 |
| Reactive | 0.9, 0.9, 0.85, 0.4, 0.9 | 1,322 ± 951 | 0.98 ± 1.67 | 4/5 | 0.41 |
| PredHead | 1.0, 1.0, 1.0, 1.1, 1.0 | 831 ± 127 | 0.36 ± 0.79 | 5/5 | 0.75 |
| PredHead+S | 1.0, 1.0, 1.0, 1.1, 1.0 | 888 ± 214 | 0.39 ± 0.87 | 5/5 | 0.69 |
| QuantProv-q90 | 0.9, 0.8, 0.6, 1.0, 0.7 | 897 ± 249 | 0.18 ± 0.30 | 5/5 | 0.71 |
| QuantProv-q99 | 0.8, 0.7, 0.6, 0.9, 0.6 | 903 ± 250 | 0.30 ± 0.63 | 5/5 | 0.69 |
| PRISM | 0.08, 0.08, 0.08, 0.03, 0.08 | 907 ± 220 | 0.33 ± 0.71 | 5/5 | 0.64 |

Paired PRISM minus comparator (mean ± 95% half-width over traces; cost % per trace; vw in points; counts = traces PRISM cheaper / fewer violating windows)

| Comparator | Cost (%) | Violating windows (pp) |
|---|---|---|
| PredHead | +8.9 ± 15.9 (0) | -0.03 ± 0.08 (1) |
| PredHead+S | +2.1 ± 0.6 (0) | -0.06 ± 0.17 (1) |
| QuantProv-q90 | +1.6 ± 4.0 (1) | +0.15 ± 0.41 (0) |
| QuantProv-q99 | +1.0 ± 4.1 (2) | +0.03 ± 0.08 (0) |
| Static | -18.3 ± 31.2 (5) | -0.42 ± 1.09 (3) |
| Scheduled | -10.0 ± 3.9 (5) | -2.17 ± 5.44 (2) |
| Reactive | -22.9 ± 23.4 (5) | -0.65 ± 1.12 (2) |
| On-demand | +1.7 ± 22.8 (4) | -6.49 ± 13.72 (5) |

Forecast quality on the test week (per trace):

| Trace | MAPE median (%) | cov90 raw | cov99 raw | cov90 cal | cov99 cal |
|---|---|---|---|---|---|
| huawei_fn150 | 4.5 | 0.835 | 0.972 | 0.938 | 0.990 |
| huawei_fn72 | 5.6 | 0.860 | 0.977 | 0.945 | 0.989 |
| huawei_fn60 | 6.2 | 0.826 | 0.964 | 0.947 | 0.990 |
| huawei_fn183 | 9.6 | 0.843 | 0.970 | 0.953 | 0.989 |
| huawei_fn42 | 4.3 | 0.891 | 0.976 | 0.963 | 0.991 |

Per trace, selected configuration on the test week (cost USD / violating windows %):

| Family | huawei_fn150 | huawei_fn72 | huawei_fn60 | huawei_fn183 | huawei_fn42 |
|---|---|---|---|---|---|
| On-demand | 859 / 0.45 | 832 / 1.49 | 813 / 4.32 | 875 / 27.38 | 1,097 / 0.45 |
| Static | 827 / 0.00 | 823 / 0.30 | 943 / 1.93 | 3,121 / 1.04 | 1,032 / 0.45 |
| Scheduled | 852 / 0.00 | 844 / 0.15 | 880 / 1.04 | 1,290 / 11.31 | 1,194 / 0.00 |
| Reactive | 904 / 0.00 | 895 / 0.15 | 987 / 1.49 | 2,681 / 3.12 | 1,146 / 0.15 |
| PredHead | 771 / 0.00 | 752 / 0.15 | 757 / 0.00 | 892 / 1.49 | 981 / 0.15 |
| PredHead+S | 772 / 0.00 | 757 / 0.15 | 782 / 0.00 | 1,149 / 1.64 | 982 / 0.15 |
| QuantProv-q90 | 773 / 0.00 | 756 / 0.15 | 756 / 0.00 | 1,208 / 0.60 | 994 / 0.15 |
| QuantProv-q99 | 773 / 0.00 | 757 / 0.15 | 758 / 0.00 | 1,200 / 1.19 | 1,027 / 0.15 |
| PRISM | 783 / 0.00 | 770 / 0.15 | 803 / 0.00 | 1,174 / 1.34 | 1,007 / 0.15 |
