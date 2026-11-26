# TR2. Calibrated development evidence (corrected start-up), traces 101-105

**CALIBRATED DEVELOPMENT EVIDENCE, not confirmatory; development traces 101-105 only; held-out seeds 106-130 untouched.**
**Source:** `prism-repro/docs/revision/calibrated_build_20261125/p3_results.json` (PRISM, MemAdapt-q90) and
`group_A_results.json` (fixed-1024 MB QuantProv-q90 and Reactive, reused after `equivalence_p3.txt`: 20 of 20 weeks
bit-identical under both start-up forms). **Configuration:** event-level closed loop, Linux, isolated build 92e3e68 +
`candidate_exec_p2.patch`; per-size execution factors (memcal-1 FIT), cross-stage dependence rho 0.998, start-up 6 s
memory-independent (adopted P3, `init_scaling` constant) truncated at 10 s (mean 5.82 s at every size), lag 2 min;
prespecified tuning with edge expansion; stationary test week. **Metric:** weekly cost (simulated USD); violating
windows (% of 15-min windows; window violates below 99% record attainment); record attainment (% of records within
the deadline); premium = PRISM / MemAdapt-q90 - 1. **Denominator:** one test week per trace and policy (672 windows).

| Deadline (s) | Trace | PRISM eps | MemAdapt a | PRISM cost | MemAdapt cost | PRISM premium (%) | PRISM viol. (%) | MemAdapt viol. (%) | PRISM attain. (%) | MemAdapt attain. (%) | PRISM meets 2% | MemAdapt meets 2% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14.5 | 101 | 0.02 | 0.4 (edge) | 1,115.9 | 940.9 | +18.6 | 0.60 | 0.89 | 99.95 | 99.90 | yes | yes |
| 14.5 | 102 | 0.02 | 0.4 (edge) | 1,144.1 | 961.3 | +19.0 | 0.15 | 1.04 | 99.94 | 99.90 | yes | yes |
| 14.5 | 103 | 0.02 | 0.4 (edge) | 1,132.3 | 949.6 | +19.2 | 0.15 | 0.89 | 99.94 | 99.90 | yes | yes |
| 14.5 | 104 | 0.02 | 0.4 (edge) | 1,104.4 | 929.7 | +18.8 | 0.74 | 0.89 | 99.93 | 99.90 | yes | yes |
| 14.5 | 105 | 0.02 | 0.4 (edge) | 1,125.4 | 948.8 | +18.6 | 0.30 | 0.45 | 99.95 | 99.91 | yes | yes |
| 12 | 101 | 0.08 | 0.5 | 1,115.9 | 967.5 | +15.3 | 1.64 | 2.68 | 99.76 | 99.68 | yes | no |
| 12 | 102 | 0.03 | 0.7 | 1,282.0 | 1,108.7 | +15.6 | 1.34 | 1.79 | 99.80 | 99.74 | yes | yes |
| 12 | 103 | 0.08 | 0.6 | 1,132.3 | 1,022.4 | +10.7 | 1.79 | 1.93 | 99.76 | 99.70 | yes | yes |
| 12 | 104 | 0.08 | 0.5 | 1,104.4 | 961.9 | +14.8 | 2.38 | 2.38 | 99.74 | 99.68 | no | no |
| 12 | 105 | 0.08 | 0.4 (edge) | 1,125.4 | 948.8 | +18.6 | 1.34 | 2.08 | 99.77 | 99.67 | yes | no |

Both policies use >= 2048 MB in 100% of epochs on every trace and deadline. At 12 s compliance differs (PRISM meets
2% in 4 of 5 test weeks, MemAdapt-q90 in 2 of 5), so the 10.7-18.6% cost difference is not a matched-compliance premium.
PRISM at eps 0.05-0.08 stays at 1024 MB at 14.5 s and violates 97-100% of windows (validation grid; `p3_results.txt`).

**Fixed-1024 MB comparators at 14.5 s (Group A, reused):** every validation setting violated 100% of windows; the
prespecified rule (least violating, ties to the cheaper) therefore selected the cheapest end of the wide grid.

| Trace | Family | Selected | Unresolved edge | Compliant validation setting | Test cost | Viol. (%) | Attain. (%) | >= 2048 MB (% epochs) |
|---|---|---|---|---|---|---|---|---|
| 101 | QuantProv_q90 | 0.4 | yes | none | 810.3 | 100.00 | 96.24 | 0.0 |
| 101 | Reactive | 1.0 | yes | none | 1,458.9 | 100.00 | 96.33 | 0.0 |
| 102 | QuantProv_q90 | 0.4 | yes | none | 828.4 | 100.00 | 96.25 | 0.0 |
| 102 | Reactive | 1.0 | yes | none | 1,404.0 | 100.00 | 96.35 | 0.0 |
| 103 | QuantProv_q90 | 0.4 | yes | none | 817.7 | 100.00 | 96.23 | 0.0 |
| 103 | Reactive | 1.0 | yes | none | 1,412.0 | 100.00 | 96.36 | 0.0 |
| 104 | QuantProv_q90 | 0.4 | yes | none | 800.6 | 100.00 | 96.25 | 0.0 |
| 104 | Reactive | 1.0 | yes | none | 1,388.5 | 100.00 | 96.35 | 0.0 |
| 105 | QuantProv_q90 | 0.4 | yes | none | 817.1 | 100.00 | 96.26 | 0.0 |
| 105 | Reactive | 1.0 | yes | none | 1,429.5 | 100.00 | 96.34 | 0.0 |

**Week counts:** 14.5 s 100 of 100 planned; 12 s 101 of 101; 0 failed, duplicate or orphaned; identical request streams.
**Readiness (run-plan rule 3):** C1-C2 NOT READY (QuantProv-q90 and Reactive at unresolved edges on 5 of 5 traces);
C3 edge condition met (MemAdapt-q90 at the edge on 1 of 5 traces); the combined calibrated
held-out run is therefore not launched for this revision (rule 3 needs every condition).
