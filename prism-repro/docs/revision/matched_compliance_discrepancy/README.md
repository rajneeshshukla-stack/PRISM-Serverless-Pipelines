# PRISM against QuantProv-q90 at the 1.0% matched-compliance target: stored rows against current code (R7.6, R5.M7(d))

**Labels.** PRE-CALIBRATION, POST HOC (matched compliance uses test-week knowledge), fast simulator. The analysis is
read-only: it recomputes from saved records and runs no simulation. It was written 22 Nov 2026.

**Reproduce** (from `prism-repro/`): `python docs/revision/matched_compliance_discrepancy/mc_discrepancy.py .`, whose
output is `output.txt`.

**The two figures:**

| Source | Rows | PRISM minus QuantProv-q90 at 1.0% | Per trace (101-105) |
|---|---|---|---|
| Stored, submitted code | `results/tables/revision/pc_billing_runs.csv`, the input of `scripts/revision/matched_compliance_pertrace.py`; output `results/tables/revision/matched_compliance_pertrace.txt` | -0.4 +/- 3.3%, includes zero | +3.3, +0.3, -4.1, -0.5, -0.7 |
| Current code at HEAD 78ba419 | `docs/revision/grid_studies/rows_posthoc_*.jsonl`, stage `grid_wide`, settings of the paper's grid only | -2.3 +/- 2.0%, excludes zero | -0.4, -3.9, -3.9, -1.0, -2.1 |

## What was checked

- **Method.** Both scripts use the same steps:
  - take the four-scenario mean per setting;
  - form the lower-left envelope;
  - interpolate linearly at the target;
  - pair by trace, as PRISM / comparator - 1;
  - take a 95% t interval with df = 4.

  Both read the modelled cost, not the billing-adjusted cost. An independent implementation (`mc_discrepancy.py`)
  reproduces both figures exactly from their own inputs.
- **Inputs.** Both sets cover the same settings: the paper's grid, all four scenarios and five traces, with 30 PRISM
  and 50 QuantProv-q90 settings complete in each.
- **Swapping inputs:**
  - current PRISM against stored QuantProv-q90 gives -6.1 +/- 5.7%;
  - stored PRISM against current QuantProv-q90 gives +3.8 +/- 6.6%.

  Neither family's change alone gives the current figure.
- **Per setting**, current minus stored, as the four-scenario mean:
  - PRISM costs 0.0-3.7% less at the same eps, mostly about 2%, and has fewer violating windows in most cells.
  - QuantProv-q90's cost moves by only -0.4 to +1.7%, while its violating windows also fall, by up to 2.0 points at
    a = 0.6.

  These shifts move the interpolation brackets. For example, PRISM on trace 101 moves from eps [0.01, 0.02] to
  [0.03, 0.05].

## Disposition

The interpolation, pairing and uncertainty calculation do not cause the difference. It comes from the simulated rows
themselves, which differ between the submitted code and the current code.

Code revisions between `v1-submitted` and HEAD that touch the relevant modules include:
- 33d1000, the m12_m5 corrections;
- 1ab053c, exact attainment;
- 44ef122, which ranks infeasible candidates by violation quantile and affects PRISM only;
- be7a912, 92d304c, 4702440, fb8b360, 38f0d67, bde7d25, a396f40 and 31b8c50, which add options, grids, a policy or
  the lag-dependent horizon, according to their commit messages.

Whether each of these leaves the paper's configuration byte-identical was not checked here.

The platform also differs from the one that produced the submitted rows (`../table6_versions/`).

No change was instrumented, so the cause is not attributed. Both figures are reported with their provenance, and the
conclusion is left open. Which figure the paper reports is settled by the regeneration on one implementation (R2.15,
R3.6).

## Update, 22 Nov 2026: controlled replay

See `FINDINGS_20261122.md`. On this laptop, switching exact attainment (1ab053c) and the Erlang-B risk model
(f119bee) alone reproduces the change from the submitted code to the current code; exact attainment carries most of
it. Every other code change since v1-submitted leaves the rows unchanged.

A further -0.32 points lie between the stored Linux rows and the same submitted tree on this laptop; that part is not
attributed. The paired change between the two estimates is -1.91 +/- 2.42 points, which includes zero. The
"about 2% cheaper" observation above is the Erlang-B switch, and it is not what moves the 1.0% estimate.
