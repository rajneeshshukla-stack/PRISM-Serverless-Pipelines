# Calibration decisions and the bounded Linux closed-loop check, legacy Eq. (2) against per-size execution (24 Nov 2026)

EXPLORATORY. Development traces 101-105 only; seeds 106-130 were not used. Closed-loop event-level simulator. Every
constant other than execution time is the pre-calibration default, so these results are **PARTIALLY CALIBRATED at
most**. No AWS call. The pinned `src/` (3edc386, R6.1), the frozen prespecification and the submitted outputs are
unchanged.

`DECISIONS.md`, `ADDENDUM_DRAFT.md` and `RUN_PLAN.md` were hashed at 22:20:03Z (`PLAN.sha256`), before the Linux build
and before any run.

## 1. Decisions (`DECISIONS.md`; the author confirms)

| Item | Decision | Status |
|---|---|---|
| P1 | The synchronous four-stage synthetic document pipeline is the calibration scope. Differences from the simulated workload are listed | recommended |
| P2 | Log-normal document length, mean 3,000 words, σ 0.30, declared. The simulator reads it as a mean-one multiplier per stage, drawn **independently** | **unresolved, material:** under P2 one document drives all stages. A common factor raises v_w at 1024 MB, 14.5 s from 0.24% to 3.33% (`p2_correlation_check.txt`) |
| P3 | 6 s kept as a declared application start-up, constant in memory. It already includes platform INIT, so the measured 0.115 s is not added. The client-observed penalty is kept separate | recommended |
| P3, 10 s | **Correction:** AWS's 10 s Init limit is not a cap. An on-demand Init over 10 s is retried at the first invocation, and the limit does not apply to provisioned concurrency. So `init_max_s` must not be enabled as "the limit" | recommendation: declare start-up < 10 s, with untruncated as a sensitivity |
| P9 | Keep the metric: record end-to-end latency from stage-1 arrival to final completion, against 14.5 s; 99% window attainment. Compare live results on `service_s` or report the client overhead; never compare client-observed and simulated SLA directly | decided (unchanged metric) |
| R2.11, D3 | Frozen choices kept: shared conformal offset, no warm-up. The alternatives stay exploratory | decided |
| D-CAL-1 | The per-size table is an explicit change of Eq. (2)'s form. `ADDENDUM_DRAFT.md` drafts the dated note | recommended; applied after the R6.1 run |

## 2. What ran (`RUN_PLAN.md`; `run_linux.sh`, `calib_closed_loop.py`, `analyse_calib.py`)

**Build.**
- A fresh Linux clone of 3edc386 plus the candidate patch (SHA-256 3569ea2a...).
- Driver SHA-256 6f350202...; factors file c60f471a... (`outputs/provenance_*.json`).

**Linux tests in the clone** (`linux_test_suite.txt`):
- 137 of 139 pass, including all 11 `test_exec_measured` tests and the byte-identical rerun gate.
- The 2 failures (`test_stage_demand_guard`, golden hashes recorded on Windows) fail identically in the **unpatched**
  clean clone (`linux_stage_demand_guard_unpatched.txt`). They are a pre-existing platform difference, not caused by
  the patch.

**Runs:** 138 of 138 expected closed-loop weeks, 2 workers, 22:24-23:52Z, no failure, no partial file, no duplicate.
Identical request streams for every model and policy on each trace, week and scenario.

| Set | Weeks |
|---|---|
| E14 (legacy and measured) | 10 |
| F13 | 20 |
| R13 | 108 |

## 3. Results

**E14, legacy equality on Linux.** The patched build's legacy configuration equals set K arm A of
`../closed_loop_kappa_20261124/` exactly, in every reported field, on all 5 traces.

**E14, default deadline (14.5 s, PRISM at K's eps):**
- the measured model changes cost by −3.87%, −3.31%, −0.28%, −0.06% and −0.17%;
- violating windows are unchanged, except trace 101 (1.79% -> 1.93%);
- no weekly verdict changes;
- PRISM spends 0.6-12% of epochs at 2048 MB under both models.

So at the default deadline the change is small but not zero on 2 of 5 traces. That exceeds the plan's 1% reporting
threshold.

**F13, 13 s, fixed settings (PRISM eps 0.01, MemAdapt-q90 a = 0.6), 5 traces:**

| | Legacy | Measured | Measured − legacy |
|---|---|---|---|
| PRISM memory use (share of epochs) | 2048 MB 95-97%, **3008 MB 3-5%** | 2048 MB 100%, 3008 MB 0% | — |
| PRISM cost (USD) / violating windows (%) | 1,789-1,950 / 0.30-1.04 | 1,118-1,169 / 0.15-0.60 | cost −38.5 +/- 1.5%; violating windows −0.30 +/- 0.19 points |
| MemAdapt cost / violating windows | 1,308-1,363 / 1.19-2.23 (trace 104 misses 2%) | 1,006-1,048 / 0.45-1.04 | cost −23.1 +/- 0.04%; violating windows −0.98 +/- 0.53 points |
| PRISM premium over MemAdapt | **+39.3%** (36.0-43.0) | **+11.3%** (11.1-11.7) | — |

By the prespecified rule, the 13 s smoke result **holds beyond trace 101**:
- both costs fall by 10% or more on 5 of 5 traces;
- the premium shrinks on 5 of 5;
- the verdict is unchanged on 4 of 5. On trace 104, MemAdapt moves from missing to meeting the target.

**R13, 13 s, each policy retuned under each model, traces 101-103:**
- **PRISM** selects eps 0.01 under both models on all 3 traces. Test cost (legacy -> measured): 1,789 -> 1,118,
  1,950 -> 1,169, 1,857 -> 1,135. Violating windows 0.30-0.45% -> 0.15-0.30%.
- **MemAdapt-q90** selects 0.6 under legacy and **0.4 under the measured model**. 0.4 is the lowest value of the
  widened grid, so it is **flagged as an edge selection**: a smaller multiplier might be cheaper. Test cost 1,308-1,363
  -> 940-960; violating windows 1.64-1.94% -> 0.74-1.04%.
- **Retuned premium** of PRISM over MemAdapt: +36.8 / +43.0 / +39.9% (legacy) against +19.0 / +21.7 / +19.7%
  (measured). With MemAdapt at an edge, the measured premium is a lower bound. Every week meets 2%, and PRISM has
  fewer violating windows than MemAdapt under both models.

## 4. What this means for the Eq. (2)-dependent claims (development check, not confirmatory)

| Earlier claim | Under the measured model (this check) |
|---|---|
| "At 13 s PRISM used 2048 and 3008 MB" | **Does not hold.** 3008 MB is never used: it is no faster than 2048 MB and costs more |
| "PRISM costs 8-28% more than the warm-feasibility rule" (fast simulator, identical compliance) | **Direction holds, magnitude does not.** PRISM costs more under both models, about +11% (fixed) and +19-22% (retuned, MemAdapt at a grid edge) against +37-43% under legacy. Compliance is not identical in the closed loop (PRISM has fewer violating windows). So "8-28% at equal compliance" is a fast-simulator, Eq. (2) figure |
| "Memory choice changes cost by tens of percent at short slack" | Holds, and is larger: 2048 MB costs about 1.15x the GB-s of 1024 MB, not 1.5x |
| Default-deadline results (14.5 s) | Small changes (<= 3.9% cost) on 2 of 5 traces; no verdict changes |
| Fixed-2048 MB headroom saving 13-27%; R2.7's 3008 MB result | **Not tested here.** They remain flagged (M21) |

**Sensitive to the remaining assumptions:**
- **P2 (common vs independent spread):** decisive for 1024 MB feasibility even at 14.5 s.
- **P3 (6 s start-up):** sets the cold-start misses that dominate violating windows.
- **Activation lag.**

None of the numbers here is calibrated in those inputs.

## 5. Readiness for the final evaluation (section 4 of the task; `DECISIONS.md` sections 2-7)

**Still needed before a full Linux C1-C3 rerun:**
1. **Decisions:** P2's common-vs-independent spread; P3's start-up value and the 10 s handling; D-CAL-1; P1; and the
   lag source.
2. **A frozen calibrated build after the R6.1 run:**
   - the patch, any P2/P3 modes, and the dated addendum;
   - the Linux suite and gate;
   - the legacy-equality check (E14-style).
3. **A development dry run under the frozen build,** including the MemAdapt grid-edge question (widen `GRIDS_WIDE`
   below 0.4 for the exploratory families if needed; this cannot change the frozen confirmatory rules).
4. **Only then** C1-C3 on seeds 106-130.

**What the R6.1 live run can and cannot establish** (`../r61_live_plan_20261123/RUN_SHEET_20261124.md`):
- **It can:** a small-scale readiness lag for provisioned concurrency (about 9 observations at 10-s polling); cold
  starts, service times and initialisation types; spill-over **descriptively** at 323 records per arm; PRISM's
  actuation path on the synthetic workload.
- **It cannot:**
  - burst overflow at scale: the client caps at 8 in flight on a 1/60-thinned replay;
  - the SLA window metric (2 windows per arm);
  - application start-up, since the docpipe has no start-up work unless P3 sets `PRISM_INIT_ROWS`.
- **Retained claims needing a burst test:** any statement about overflow or on-demand scale-out under spikes on AWS
  needs a separate burst test. The spike-scenario results stay simulation-only until then.
- **What stays assumed after the live run:** the application start-up (6 s), unless a start-up campaign with P3's
  work is run.

**How to apply the calibration after the live run:**
- `git apply ../calibration_20261124/candidate_exec_measured.patch` on the post-R6.1 tree;
- add `tests/test_exec_measured.py`;
- set `exec_scaling` = "measured" and `exec_factor_measured` in the calibrated configuration only;
- record the addendum.

## 6. Files

- **Decisions and plan:** `DECISIONS.md`, `ADDENDUM_DRAFT.md`, `RUN_PLAN.md`, `PLAN.sha256`, `PLAN_HASHED_AT.txt`.
- **P2 check:** `p2_correlation_check.py`, `.json`, `.txt`.
- **Run:** `calib_closed_loop.py`, `run_linux.sh`, `run_stdout.txt`.
- **Tests:** `linux_test_suite.txt`, `linux_stage_demand_guard_unpatched.txt`.
- **Analysis:** `analyse_calib.py`, `analysis.json`, `analysis_stdout.txt`.
- **Outputs:** `outputs/` (week JSON and per-epoch `.npz`, groups, run.log, provenance).
- **Checksums:** `SHA256SUMS`.

## Dated note, 25 Nov 2026: scope of these results (P2)

**Every result in this folder uses ρ = 0:** independent per-stage execution spread, the frozen form.
- "Measured" here means the per-size execution factors, not a measured cross-stage dependence.
- The P2 follow-up (`../p2_dependence_20261124/`) measured ρ ≈ 0.998 for the document pipeline from the archived live
  run. It found that at ρ ≈ 1:
  - 1024 MB is not warm-feasible at 14.5 s;
  - PRISM's retuned premium over MemAdapt at 14.5 s is ≥ +17%;
  - the fixed-setting premium at 13 s is +21.2%, against +11.3% here.
- **Do not pair these figures with ρ = 1 results.** These results stand within their stated scope.
