# Calibrated simulator build: regression checks and development verification (plan fixed before any run, 25 Nov 2026)

**Status of this pass:**
- **Development check,** not confirmatory: traces 101-105 only; seeds 106-130 are not used.
- **Event-level closed-loop simulator, Linux.**
- **Code:** isolated calibration build = `92e3e68` + `../p2_dependence_20261124/candidate_exec_p2.patch` (SHA-256
  af456a05…: the per-size lookup + `exec_common_frac`). `src/` at `92e3e68` is identical to 3edc386.
- **Unchanged:** the frozen `src/`, `PRESPECIFICATION.md`, the manuscript, submitted outputs and the R6.1 harness.

## Calibrated configuration (CAL; `ADOPTED_DECISIONS.md`)

`PipelineConfig()` defaults plus:
- `exec_scaling="measured"`;
- `exec_factor_measured=<memcal-1 FIT factors>`;
- `exec_common_frac=0.998`;
- `init_max_s=10.0`.

`PrismConfig()` defaults. The policies, `GRIDS`, `GRIDS_WIDE`, the selection rule and the edge expansion are the
prespecified ones, verbatim (`scripts/revision/closed_loop_confirmatory.py`).

## Regression checks (must all pass before any development result is read)

- **R1: full test suite** on the Linux build. Expected: the 147 tests of the P2 pass, all passing except the 2 known
  Windows-recorded hash anchors (`test_stage_demand_guard`), which also fail in the unpatched Linux clone.
- **R2: legacy equality.** The default configuration reproduces `../calibration_final_20261124/` set E14_legacy
  (PRISM, 14.5 s, eps 0.01/0.01/0.03/0.03/0.03) exactly, in every field, on 5 of 5 traces.
- **R3: per-size, ρ = 0.** Reproduces E14_meas exactly, 5 of 5.
- **R4: per-size, ρ = 1.** Reproduces the P2 set S145 PRISM test weeks exactly, 5 of 5.

Any mismatch stops the pass.

## Development runs (one group at a time, 2 workers, resumable)

| Group | Configuration | Families | Traces | Weeks |
|---|---|---|---|---|
| **A** | CAL, 14.5 s (the C1-C2 deadline) | PRISM, QuantProv_q90, Reactive, MemAdapt_q90; retuned by the prespecified rule; stationary test week | 101-105 | about 245 |
| **B** | CAL, 12 s (the C3 deadline) | PRISM, MemAdapt_q90; retuned likewise; stationary test week | 101-105 | about 110 |
| **D** | Diagnostic, only if a family selects the **lowest value of its wide grid** in A or B | Validation weeks below that bound: MemAdapt or QuantProv a = 0.3 and 0.2; PRISM eps 0.001; Reactive 0.25 and 0.20. **Not used for selection;** it only shows whether the unresolved edge hides a cheaper compliant setting. | affected traces | up to 30 |

## Interpretation rules (fixed now)

**1. The 14.5 s P2 finding is verified** if, under CAL, all of the following hold:
- PRISM and MemAdapt use ≥ 2048 MB in ≥ 95% of epochs on every trace;
- both meet 2% on ≥ 4 of 5 traces;
- PRISM costs more than MemAdapt on ≥ 4 of 5 traces.

Otherwise the finding is revised as observed.

**2. Edge.**
- A selection at the lowest or highest value of `GRIDS_WIDE` after expansion is an **unresolved edge** under the
  prespecified rule.
- Under the rule it is not resolved, only reported, with D as a diagnostic.

**3. Readiness for held-out C1-C3** (all must hold):
- R1-R4 pass;
- A and B complete with no failure or duplicate, and identical request streams per (trace, week, scenario);
- no family has an unresolved edge on ≥ 2 of 5 traces in the set it enters (C1-C2: PRISM, QuantProv_q90 and Reactive
  at 14.5 s; C3: PRISM and MemAdapt at 12 s);
- the calibrated configuration and the adopted addendum are recorded.

If an unresolved edge remains, the build is **not ready**. Widening `GRIDS_WIDE` is a change to the prespecified
protocol, which needs a dated author decision applied to every family alike before C1-C3.

**4. Not covered by this pass:**
- the growth, bursty and new_spike test weeks of C1-C2: selection uses the validation week, so edges are covered,
  but the scenario outcomes are not;
- the ρ = 0 and untruncated-start-up sensitivities: their configurations are fixed here, but the runs belong with
  C1-C3.
