# TR6. Platform and code-version sensitivity of the headline values (fast simulator, assumed constants)

Same seeds and protocol. Forecast-driven policies (PredHead, PredHead+hyst, QuantProv, PRISM) differ between Windows and
Linux even with identical code and packages; policies without a forecast are identical. Sources: `prism-repro/results/tables/`
(submitted v1), `regeneration_20261122/outputs/tables/` (REGEN-WIN), `label_fix_20261123/outputs/linux_tables/` (REGEN-LINUX).

| Set | PRISM eps selected, traces 101-105 | Table V new spike: PRISM viol. % (SLO met) | smoothed headroom viol. % | unsmoothed headroom viol. % | Table S4 cost PRISM / QuantProv-q90 (USD) | Table S4 viol. PRISM / QuantProv-q90 (%) | Table X PRISM viol. fast / event |
|---|---|---|---|---|---|---|---|
| Submitted v1 (submitted code, Linux) | 0.02, 0.03, 0.05, 0.05, 0.05 | 1.55 (80%) | 3.24 | 6.67 | 1,267 / 1,320 | 1.36 / 1.24 | 1.44% / 3.75% |
| REGEN-WIN (reporting set) | 0.05, 0.03, 0.08, 0.08, 0.08 | 2.11 (40%) | 4.11 | 7.92 | 1,150 / 1,142 | 1.78 / 1.95 | 1.69% / 6.14% |
| REGEN-LINUX (current code, Linux) | 0.08, 0.03, 0.08, 0.08, 0.08 | 2.62 (20%) | 4.02 | 7.62 | 1,130 / 1,139 | 2.00 / 2.03 | 1.98% / 6.99% |

Reading: the ordering 'both headroom rules cheaper, PRISM least violating under the new spike' holds in all three
sets, but PRISM is above the 2% target on average in both regenerations (it was below in v1), and the Table S4
ordering of PRISM against QuantProv-q90 reverses between Windows and Linux.
