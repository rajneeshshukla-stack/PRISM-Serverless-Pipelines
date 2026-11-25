# P2 decision record: execution-time dependence across stages (24-25 Nov 2026)

The author decides; this records the evidence and the recommendation. Nothing here edits `PRESPECIFICATION.md`, the
manuscript or the submitted results.

## The question

**What the simulator does.** It draws each request's four per-stage execution multipliers independently: log-normal,
mean 1, σ_log 0.30, at four sites:
- the event-level draws;
- the fast-simulator draws;
- PRISM's attainment table;
- PRISM's miss table.

**What the live workload does.** The calibration workload (P1, the synthetic document pipeline) gives each record one
document. Every stage's work is K × document length (`docpipe.py`). The P2 size mix is σ_log 0.30, declared in
`workload.py` as "= PipelineConfig.exec_shape".

**The question:** is the spread shared across stages, independent, or in between?

## Evidence

### 1. The saved warm miss estimates reproduce

The saved values are 0.24% and 3.33% at 1024 MB and 14.5 s.
- **Rerunning** `../calibration_final_20261124/p2_correlation_check.py` reproduces all 24 values bit for bit
  (`repro_p2_correlation_check.*`).
- **Their assumptions:**
  - warm latency only (no start-up);
  - Eq. (2) stage means, which equal the per-size model at 1024 MB, where every factor is 1;
  - mean-one log-normal, σ 0.30;
  - 0.1 s overhead per stage, σ 0.30;
  - 400,000 draws.
- **The build's own miss table** (`vw_by_rho.txt`, ρ = 0 and ρ = 1, other random streams) gives 0.216% and 3.284%. Both
  are within Monte Carlo error of the saved values (1.8 and 1.0 combined standard errors).

### 2. The archive identifies the dependence for this workload (`DATA_AUDIT.md`)

- **Data:** 34 all-warm 1024 MB records of distinct documents (1,560-5,951 words), each with all four stages joined by
  record ID.
- **Size effect:**
  - document size explains 99.3-99.9% of each stage's log-time variance;
  - slopes are 0.93-1.03, i.e. time is proportional to size.
- **Stage-specific remainder:** σ_log 0.009-0.019, nearly uncorrelated across stages (mean 0.04, bootstrap 95%
  [−0.09, 0.14]).
- **Total correlation of log stage times:** 0.996 [0.993, 0.998].
- **Moment-matched ρ** at σ 0.30: 1 − (0.0144/0.30)² = **0.998**.
- **Limits:**
  - the documents in the checks are the same as in the fit;
  - one day of runs, one region;
  - σ 0.30 itself is declared, not measured;
  - the shared mechanism is a design property of the synthetic handler, confirmed on AWS; it is not a property of
    every application.

### 3. Warm miss probability by ρ, per-size model (`vw_by_rho.txt`)

| | 14.5 s, 1024 MB | 14.5 s, 2048 MB | 13 s, 1024 MB | 13 s, 2048 MB |
|---|---|---|---|---|
| ρ = 0 (independent) | 0.216% | 0.000% | 1.18% | 0.000% |
| ρ = 0.998 (measured) | 3.283% | 0.014% | 7.24% | 0.047% |
| ρ = 1 (shared) | 3.284% | 0.015% | 7.25% | 0.046% |

- ρ = 0.998 and ρ = 1 are indistinguishable (0.002 points at 1024 MB, 14.5 s). By the plan's rule, ρ = 1 stands for the
  measured value in the closed loop.
- **What this means for 1024 MB at 14.5 s:**
  - feasible at ρ = 0;
  - infeasible at ρ ≈ 1 for PRISM's default risk budgets (eps 0.01-0.03) and for MemAdapt's 0.005 tolerance.

### 4. Closed-loop consequences (development traces, `README.md`)

The conclusions change at 14.5 s and in magnitude at 13 s.

## Decision P2-DEP (recommended; author to confirm)

**Primary: ρ = 0.998,** i.e. a shared document-size factor plus a small, independent stage-specific remainder, for the
calibration scope P1.

**Reasons:**
- the workload mechanism (one document drives every stage);
- the archived AWS measurement of that mechanism.

**What the choice was not based on:**
- not on the closed-loop outcomes, whose plan was hashed before the mode was implemented (RUN_PLAN.md, 00:43:59Z);
- not on which configuration favours PRISM. In fact ρ ≈ 1 *raises* PRISM's premium over the memory-adaptive baseline.

**Carried forward as a sensitivity: ρ = 0** (the frozen form), because the conclusions depend on the choice. It stands
for an application whose stages respond to unrelated inputs.

**Measured or assumed:**

| Parameter | Status |
|---|---|
| ρ (cross-stage correlation of execution spread) | **Measured** for the document pipeline on AWS (0.996-0.998; 34 records, 1 day) |
| Stage-specific residual σ_log (about 0.014) | **Measured** (same data) |
| Marginal σ_log 0.30 (the document-size mix) | **Declared** (SPEC P2); the 40 planned sizes have sd 0.249 |
| Proportionality of time to size (slopes 0.93-1.03) | **Measured**; the model uses the multiplier form, so proportionality is assumed exactly |
| ρ for any other application | **Unknown;** requires that application's matched stage timings |
| Dependence of start-up and orchestration overhead across stages | **Assumed independent** (not identifiable: cold records excluded, overhead not logged per stage) |

**What would resolve the remaining uncertainty:**
1. **The R6.1 live run, as already pinned, can replicate ρ without any change.**
   - It replays 323 P2-sized documents per arm at 1024 MB, and its records carry `n_words` and the four stage timings
     joined by record ID: about 10 times the archived sample, on new documents.
   - It also observes warm deadline misses at 1024 MB directly. The prediction is about 3.3% at ρ ≈ 1 against 0.2% at
     ρ = 0; the 95% interval for 10 misses in 323 is 1.5-5.6%, so the two are separable.
   - The dependence estimate needs only `audit_dependence.py` pointed at its archive.
2. **For an application other than the document pipeline:** matched per-record stage timings of that application with
   its real input mix (≥100 records, warm and cold flagged, two memory sizes). The P2 size mix (σ) would then be
   measured too.

## Other choices, unchanged

- **P3:**
  - 6 s total start-up occupancy, a declared scenario that already contains the measured ~115 ms platform
    initialisation (nothing added);
  - the 10 s Init limit is an on-demand timeout retried at the first invocation, not a universal cap, and is not
    modelled as a truncation.
- **R2.11, D3:** frozen choices kept (one shared offset; no warm-up).
- **D-CAL-1:** the per-size lookup is a change of Eq. (2)'s form, recorded in `ADDENDUM_DRAFT.md` (v2, this folder).
