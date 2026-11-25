# Calibration table for the final PRISM evaluation (24 Nov 2026)

No AWS call. The constants are `PipelineConfig()` at 3edc386. **Nothing is changed in the pinned `src/`.**

**Sources:**
- memcal-1 (`../aws_memcal_20261122/`): on demand, us-east-2, the declared docpipe-1 four-stage workload, one reference
  document, at most 8 in flight, laptop client, one afternoon, FIT/CHECK split by visit, fixed in advance;
- the live integration run (`../aws_live_integration/`): one run, 40 records per arm, varied documents;
- AWS pricing pages (`../billing_r214_pc_20261124/`).

**Verdicts:**
- **supported** — the measurement supports a replacement, with the held-out check passed;
- **by construction** — the agreement is built in, so it is not evidence;
- **declared** — a workload property set by the author's decision, not measured;
- **assumption** — no measurement;
- **later AWS** — needs the R6.1 run or a separate test.

| Simulator input (current value) | Measured quantity | Value | Units | Memory | Scope | Verdict |
|---|---|---|---|---|---|---|
| `warm_mean_1024` (0.8, 4.0, 2.5, 1.2) | warm Lambda Duration median at 1024 MB | 0.801, 3.994, 2.529, 1.205 | s | 1024 | docpipe-1, reference document | **by construction.** The work units K were frozen so that 1024 MB reproduces Table S1. Keep it as the reference; it is not independent evidence |
| `nonscaling` 0.5 (Eq. (2): x1.5 at 512, x0.75 at 2048, x0.667 at 3008) | warm Duration median relative to the same stage at 1024 MB, FIT split | 512: 2.013-2.034; 2048: 0.572-0.578; 3008: 0.571-0.578 | ratio | 512-3008 | docpipe-1; corroborated by the live run's per-1,000-word ratios (2.01-2.07; 1/1.71-1/1.74) | **supported, as per-size factors.** The Eq. (2) form fails held-out in 16/16 cells (−10.1% to +13.1%). The measured factors pass 14/16 strictly, 16/16 within the 0.41% between-block repeatability, with factor errors <= 0.30% (`heldout_exec_measured.csv`). Opt-in mode built and tested (section 3 of the README); promotion is a model decision |
| `exec_shape` 0.30 (σ of log execution time) | warm Duration spread with one fixed document | σ_log about 0.01-0.13 (p05-p95) | — | all | one document: platform jitter only | **declared.** SPEC.md P2 sets the document length log-normal (mean 3,000 words, σ 0.30). The work is proportional to length, so the spread is 0.30 by construction. Keep 0.30 if P2 is adopted. Not a measurement |
| `overhead_mean` 0.1 s, `overhead_shape` 0.30 | Step Functions stage-to-stage transition, warm next stage | 23-30 ms (median) | s | — | one run | **assumption.** What `overhead` represents depends on P9 (the deadline's reference clock). Orchestrator only: about 0.025 s. With a client: add the client's network. memcal's client overhead, median 0.081 s, includes the wide-area network |
| Platform initialisation (part of `init_mean_1024`) | Lambda Init Duration I (REPORT) | 0.114-0.116; max 0.36 over 4,992 cold starts; slope +0.005 [+0.001, +0.008] against memory | s | 512-3008 | docpipe-1 with no start-up work (`INIT_ROWS` = 0) | **supported for the platform part only:** flat in memory. Held-out: Eq. (3) form 14/16, measured mode 15/16 (misses about 2 ms) |
| (not a simulator input) | client-observed first-call penalty P = cold minus warm end-to-end (median) | 0.23-0.25; aggregate 0.51 -> 0.31 (512 -> 3008 MB); pooled slope −0.116 against Eq. (3)'s −0.273 | s | 512-3008 | includes the client's network; P_mean estimable for ingest only (stalls), 8/8 held-out | Reported, not used. It is not the modelled occupancy of an application with start-up work |
| `init_mean_1024` 6.0 s, `init_shape` 0.30 (application start-up) | none | — | s | — | — | **assumption (P3).** Neither tested nor contradicted. **Do not replace with 0.115 s:** that would model an application with no start-up work |
| `init_scaling` "eq3" (`init_nonscaling` 0.7) | direction of I and P against memory | I flat; P falls only where first-call work is CPU-bound (aggregate) | — | 512-3008 | docpipe-1 | **partly supported.** The platform part is constant. For application start-up the direction depends on what the start-up does. A CPU-bound start-up would follow the measured execution factors |
| `init_max_s` None | Lambda INIT limit (documented) | 10 | s | — | AWS documentation | **supported:** enable at the calibrated rerun (R4.8). Whether it binds depends on P3 |
| `lag_min` 2 (activation lag of provisioned concurrency) | none | — | min | — | — | **later AWS:** the R6.1 run's readiness polling gives about 9 activation observations at 10-s resolution |
| `keepalive_min` 10 | none | — | min | — | — | **assumption.** AWS states no rule; a designed idle-gap test would be needed |
| Burst overflow (on-demand scale-out beyond provisioned concurrency) | none | — | — | — | — | **later AWS, separate test.** The R6.1 run is a thinned replay capped at 8 in flight (client cap; 323 records per arm), so it shows spill-over only descriptively at low load, not burst scale-out |
| Memory change (not a constant; the simulator applies it at an epoch boundary) | UpdateFunctionConfiguration(MemorySize) across 4 functions | 3.27-3.33 | s | 512-2048 | one run | Consistent with the simulator (far below a 5-minute epoch) |
| `Prices` | list prices; billing rules on 21,248 REPORT records | as configured; rounding effect <= 0.031% | USD | — | public pages | **supported** (list prices; the final bill is open, R2.14(b)) |

**Held-out coverage, 37/56** (`heldout_coverage.txt`):
- Eq. (2) warm Duration: 0/16;
- I, Eq. (3) form: 14/16;
- I, measured mode: 15/16;
- P_mean, both forms: 8/8, ingest only.

Every miss of consequence is Eq. (2): it predicts 2048 MB too slow (+12.8% to +13.1%), 3008 MB too fast (−9.7% to
−10.1%), and 512 MB too fast (−6.9% to −7.6%), because execution stops speeding up above 2048 MB (one vCPU). The three
Init misses are about 2 ms on 0.115 s.

*Correction, 24 Nov 2026 (`../calibration_final_20261124/DECISIONS.md` section 3): AWS documents the 10 s Init limit for on-demand functions only, and as a timeout that is retried at the first invocation under the function timeout ("Lambda retries the Init phase at the time of the first function invocation"). It is not a cap on start-up time, and it does not apply to provisioned concurrency. So `init_max_s` = 10 is **not** "supported by Lambda's documented limit", as stated above. Enabling it would misrepresent long start-ups.*
