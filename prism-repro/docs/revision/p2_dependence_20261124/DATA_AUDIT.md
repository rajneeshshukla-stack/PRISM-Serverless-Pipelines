# P2 data audit: can the archived AWS runs identify cross-stage dependence? (24 Nov 2026)

Script `audit_dependence.py` (read-only on the raw archive); result `dependence_audit.json`. No AWS call was made.
Only aggregates are saved: no request IDs, ARNs or account data.

## Sources

| Run | What it holds | Useful for P2? |
|---|---|---|
| **Live integration run, 21 Nov 2026** (`AWS_livetest_20261121-203051`) | **Records:** 40 planned pipeline records, each with a record ID, `n_words`, and all four stage rows (`handler_s`, `cold`, `memory_mb`, `k`, env ID, wall times), run through Step Functions Express. **Arms:** on-demand at 1024 MB, and an adapter schedule (512, 1024 and 2048 MB). The **same 40 documents** run in both arms. | **Yes:** the only source that joins document size to all four stage timings within one record. |
| **Live integration run, 22 Nov 2026** (`AWS_livetest_20261122-090236`) | The work-unit calibration run: 4 records per arm, 1024 MB only, 3,159–3,565 words, and work units within 2.5% of the 21 Nov run. | **Level check only:** 2 all-warm records, one document. |
| **memcal-1** (`AWS_memcal_20261122-110627`) | 20,992 **direct** per-stage invocations of one 3,000-word reference document at 512, 1024, 2048 and 3008 MB. There are no pipeline records, and the stages are not joined per record. | **No:** no size variation and no cross-stage pairing. It is kept separate: it is the source of the per-size factors. |

## Coverage (21 Nov run)

| | On-demand arm | Schedule arm |
|---|---|---|
| Complete 4-stage records | 40 of 40 | 40 of 40 |
| Distinct document sizes | 40 (1,560–5,951 words, mean 3,130, sd of log 0.249) | 40 (same documents) |
| All stages at one size | 40 at 1024 MB | 11 at 512, 11 at 1024, 11 at 2048, 7 mixed |
| Cold stages per record (0 / 1 / 2 / 3 / 4) | 34 / 3 / 1 / 0 / 2 | 24 / 9 / 2 / 2 / 3 |
| **All stages warm, one size** (used) | **34 at 1024 MB** | 8 at 1024, 5 at 512, 10 at 2048 |

- **Missing fields:** none in the complete records.
- **Warm or cold:** taken from the handler's own `cold` flag, set at the first invocation in each execution environment.
- **Records with any cold stage are excluded**, so start-up does not enter the fit.
- **Memory:** fixed within each fitted group, and fitted separately per size.

## Estimates

**Fit set:** on-demand arm, 1024 MB, 34 all-warm records. Model: log handler time = a + b·log(words), per stage.
Bootstrap 95% intervals resample whole records (2,000 resamples), so the four stages of a record move together.

| | Ingest | Transform | Aggregate | Load |
|---|---|---|---|---|
| Slope b (1 = proportional to size) | 0.995 [0.975, 1.011] | 1.026 [0.991, 1.053] | 0.930 [0.917, 0.942] | 0.964 [0.938, 0.991] |
| Share of log-time variance explained by size | 99.76% | 99.41% | 99.85% | 99.33% |
| Residual σ of log time | 0.012 | 0.019 | 0.009 | 0.019 |
| Total σ of log time | 0.233 | 0.240 | 0.217 | 0.226 |

| Correlation across stages | Mean of the 6 pairs | 95% bootstrap |
|---|---|---|
| Residuals (after size) | 0.036 (pairs −0.19 to 0.35) | [−0.09, 0.14] |
| **Total log stage time** (what the simulator's multipliers represent) | **0.996** | **[0.993, 0.998]** |

**Checks:**
- **Schedule arm, 8 all-warm 1024 MB records** (other executions of the same documents, so the documents are **not** independent): mean absolute log error 0.013, per-stage bias −1.3% to +1.6%.
- **22 Nov run, 2 all-warm records of one document** (another day and deployment; the prediction assumes time proportional to the work units): per-stage level error −0.7% to +6.8%, mean absolute 2.9%. This checks the level only, not the slope or the correlation.
- **Other sizes, small samples:**
  - 512 MB (n = 5): total correlation 0.995, residual 0.44;
  - 2048 MB (n = 10): total correlation 0.990, residual 0.10.

  The size effect dominates at every size; the 512 MB residual figure rests on 5 records.

## What this establishes, and what it does not

**Established for this workload:**
- The record-to-record spread in warm stage time is almost entirely document size. It is proportional, or nearly so, at every stage.
- That spread is therefore **shared across the four stages**: total ρ ≈ 0.996, and the moment-matched ρ = 1 − (σ_r/σ)² = 0.998 at σ = 0.30.
- The stage-specific remainder is small (σ_log 0.01–0.02) and nearly independent across stages.
- This holds on AWS, not just in the handler's design. The handler scales work by K × document length at every stage (`docpipe.py`), and the archive confirms that the platform preserves this.

**Not established:**
- **The marginal spread σ = 0.30.** It is the declared P2 document-size mix (SPEC P2), not a measurement of any production workload. The 40 planned sizes have sd of log 0.249.
- **Whether a real application's stages scale with one common size variable.** The synthetic handler does by construction. An application whose stages depend on different input features would have lower ρ. Only measurements of that application can tell.
- **Dependence of start-up and orchestration overhead.** Cold records are excluded, and overhead is not in `handler_s`.

**Uncertainty:**
- 34 documents in the fit; the checks reuse the same documents.
- One day of runs, one region, one function version.
- The closed-loop sensitivity therefore uses ρ = 1 (SHR) and ρ = 0 (IND) as the bounding cases. The measured ρ = 0.998 is evaluated in the warm miss table, where it is indistinguishable from ρ = 1: v_w at 1024 MB and 14.5 s is 3.283% against 3.284% (`vw_by_rho.txt`).

## Earlier statement now superseded

- **Superseded:** R7.5's evidence line "exec_shape 0.30 is untestable (one document; measured run-to-run σ_log about 0.01–0.13)". That holds for memcal-1.
- **What the 21 Nov live run adds:**
  - For this workload, the spread *mechanism* is document size, and it is shared across stages.
  - The *magnitude* stays the declared P2 input.
