# Decision record for the final (calibrated) PRISM evaluation (24 Nov 2026; for the author's decision)

**Nothing here is applied.** The pinned `src/` (3edc386, R6.1 run sheet) is unchanged, and the frozen prespecification
is unchanged. No calibration input uses a trace or a seed: every fitted value comes from the memcal-1 FIT split.
Seeds 106-130 play no part in model selection or tuning.

**Numbering correction.** In `aws_pipeline/SPEC.md`:
- **P2** is the input-size distribution;
- **P3** is the start-up work;
- **P4** is the data source and sink.

Earlier notes of 24 Nov 2026 (`../calibration_inputs_20261124/README.md` and the tracker's Remaining work for R1.2,
R2.8, R4.3, R4.8, R5.M2 and R7.5) called input sizes "P4". They mean P2. Corrected below and in the tracker.

## 1. What can be calibrated now (local evidence suffices)

| Input | Proposed value | Evidence |
|---|---|---|
| Execution time against memory | Per-size factors from memcal-1 FIT, replacing Eq. (2): 512 MB 2.013-2.034, 2048 MB 0.572-0.578, 3008 MB 0.571-0.578 x the 1024 MB reference | Held-out: factors within 0.30%. The Eq. (2) form fails 16/16. Corroborated by the live run. Implemented as an opt-in mode with 11 tests; legacy outputs identical (`README.md` section 3) |
| `init_max_s` | 10 s | Lambda's documented INIT limit (R4.8; truncation gate exists) |
| Platform part of initialisation, direction | constant in memory | I flat at 0.115 s across 512-3008 MB |

**Model decision D-CAL-1 (author).** The per-size table changes the model's form, not only a constant. The
prespecification reruns the comparisons "unchanged ... when measured constants replace the assumed ones". The policies,
seeds, tests and decision rules stay the same. Whether a per-size table counts as "measured constants" needs a dated
statement before the rerun.
- **Recommendation:** adopt it, and record it as the measured replacement of `nonscaling`, because no single
  `nonscaling` reproduces the data.

## 2. What remains a modelling assumption (declared, not measured)

| Input | Recommendation | Evidence |
|---|---|---|
| **P3: application start-up** (`init_mean_1024` 6 s, `init_shape` 0.30) | **Keep 6 s as a declared application start-up.** Do not replace it with the measured 0.115 s: that is Lambda's platform INIT for functions with no start-up work, and using it would model a different application. | Reviewer 4 cites reference [8]: cold starts up to about 7 s in one region and 3 s in another, so 6 s is within the published range, at its upper end. The event-level replays attribute every violating window to initialisation occupancy, so the magnitude matters (R1.1(a)). |
| P3 direction (`init_scaling`) | Use **"constant"** in the primary configuration, and report Eq. (3) and a CPU-bound variant (6 s x the measured execution factors, through `init_mean_measured`, truncated at 10 s) as sensitivities. | The measured platform part is flat. Eq. (3) fits I only at `init_nonscaling` = 1 (constant). A CPU-bound start-up would scale like execution (aggregate's first-call work does). |
| Sensitivities for the 6 s | 3 s (the lower cited value) and the measured platform-plus-client penalty (about 0.25 s) as a lower bound | At 3 s, on-demand execution already meets the target (Section S5), so the problem PRISM solves shrinks with start-up time. That belongs in the scope statement. |
| **P2: input sizes** (`exec_shape` 0.30) | **Adopt SPEC.md P2**: log-normal document length, mean 3,000 words, σ 0.30. The handler's work is proportional to length, so the warm-time spread is 0.30 by construction. | memcal-1 used one document, so its 0.01-0.13 spread is platform jitter only, as SPEC.md predicts for a fixed size. The live run's per-1,000-word scaling is consistent across memory. |
| `overhead_mean`, `keepalive_min` | Keep 0.1 s and 10 min as assumptions. Decide P9 (which clock the deadline uses) before changing `overhead`. | Measured orchestration transitions are 23-30 ms. No keep-alive rule is published. |

## 3. What needs later AWS evidence

| Input | Test | Note |
|---|---|---|
| Activation lag (`lag_min` 2) | the R6.1 live run (`../r61_live_plan_20261123/RUN_SHEET_20261124.md`) | About 9 readiness observations at 10-s polling, a small-scale estimate. Sweeps at L = 5 and 10 already exist |
| **Burst overflow** (on-demand scale-out beyond provisioned concurrency) | **a separate burst test** | **Checked: the R6.1 run sheet does not measure it.** The run is a 1/60-thinned trace replay with a client cap of 8 in flight; the sheet records spill-over "descriptively, for this workload and load" only |
| Application start-up, if P3 sets start-up work (`PRISM_INIT_ROWS`) | a short on-demand campaign like memcal-1, with that work | Measures the actual start-up distribution and its direction in memory; would replace the declared 6 s |
| Final charges | the billing records (R2.14(b)) | Not a simulator input |

## 4. Smoke test of the candidate (development trace 101; fast simulator; `smoke_worktree.json`)

| Regime | Legacy (Eq. (2)) | Measured factors | Change |
|---|---|---|---|
| 14.5 s, PRISM | eps 0.05; 1024 MB; stationary USD 1,000.9 / 1.19%; new spike 1,258.5 / 1.64% | identical | none: 1024 MB is the reference |
| 13 s, PRISM | eps 0.01; 2048 and 3008 MB; stationary 1,690.0 / 0.00%; new spike 2,090.7 / 0.00% | eps 0.01; **2048 MB only**; 1,112.5 / 0.00%; 1,390.5 / 0.00% | Same selection and SLA verdict; cost −34%; no 3008 MB, which has no speed-up |
| 13 s, MemAdapt-q90 | 0.6; 2048 MB; 1,313.0 / 0.00%; 1,657.5 / 0.00% | 0.6; 2048 MB; 1,007.9 / 0.00%; 1,272.4 / 0.00% | Same selection and verdict; cost −23% |
| 13 s, PRISM against MemAdapt (stationary) | +28.7% | +10.4% | **The RQ4 cost premium shrinks** |
| Warm miss v_w at 512 MB, 14.5 s | 0.251 | 0.849 | 512 MB becomes far worse, as the measured 2x slowdown implies |
| Cold miss ρ at 2048 MB, 14.5 s / 13 s | 0.094 / 0.254 | 0.023 / 0.081 | Larger memory is more effective |

**Reading.** On this trace, the candidate leaves every selection and every SLA verdict unchanged. It changes the
memory economics: 2048 MB costs about 1.15x 1024 MB per invocation instead of 1.5x, and 3008 MB buys nothing. So the
fast-simulator RQ4 numbers are properties of the assumed Eq. (2): PRISM's 8-28% premium over MemAdapt, its use of 3008
MB at 13 s, and the 13-27% saving of fixed 2048 MB headroom. These are one-trace smoke results, not replacements.

## 5. Checks before a full Linux C1-C3 rerun (not started)

1. **Author decisions:**
   - P1 (adopt the docpipe workload);
   - P2 (as above);
   - P3 (start-up value and direction);
   - D-CAL-1 (per-size execution factors);
   - P9 (deadline clock; affects `overhead`);
   - R2.11 (shared or per-quantile calibration);
   - D3 (R4.6 / R5.M3 warm-up split).

   Each changes the configuration, and must be fixed before the run.
2. **A frozen calibrated build,** separate from the R6.1 pinned files:
   - the candidate patch (`candidate_exec_measured.patch`) plus the chosen constants, on its own commit or tag after
     the R6.1 run, or in a separate worktree;
   - full test suite and byte-identical gate on Linux;
   - a configuration hash recorded.
3. **The legacy-equality check** on Linux (the smoke script's `--legacy-only` mode against the pinned tree). It passed
   on Windows here.
4. **A dated recalibration note** under the prespecification: the constants changed, the comparisons are unchanged.
   Values come only from memcal-1 FIT, never from seeds 106-130.
5. **Development checks on 101-105:**
   - a closed-loop dry run (the `pilot101` set, and the κ and comparator sets if wanted) under the calibrated build:
     runtime, memory at 2-3 workers, no failures;
   - a re-check of the grid edges (PRISM eps, QuantProv a), because the calibrated miss tables move the operating
     points.
6. **Activation lag:** either the R6.1 measurement replaces 2 min, or 2 min stays a declared assumption with the
   L = 5 and 10 sweeps.
7. **Only then:** C1-C3 on seeds 106-130 on Linux, once (about 34 CPU-h, run at 2-3 workers given the memory stops
   observed on 24 Nov 2026).

*Correction, 24 Nov 2026 (`../calibration_final_20261124/DECISIONS.md` section 3): AWS documents the 10 s Init limit for on-demand functions only, and as a timeout that is retried at the first invocation under the function timeout ("Lambda retries the Init phase at the time of the first function invocation"). It is not a cap on start-up time, and it does not apply to provisioned concurrency. So `init_max_s` = 10 is **not** "supported by Lambda's documented limit", as stated above. Enabling it would misrepresent long start-ups.*
