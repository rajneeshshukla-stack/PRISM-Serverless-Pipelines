# P2: execution-time dependence across stages (24-25 Nov 2026)

EXPLORATORY, development traces 101-105 only (seeds 106-130 not used), closed-loop event-level simulator, PARTIALLY
CALIBRATED: per-size execution factors used; start-up 6 s, activation lag, keep-alive and overhead assumed. No AWS
call, no commit. Manuscript, submitted results, PRESPECIFICATION.md, raw AWS archives and R6.1 pinned files unchanged.

## Findings, unfavourable first

1. **The independence assumption is contradicted for the document pipeline.** On AWS, document size explains
   99.3-99.9% of each stage's warm-time variance. Log stage times correlate at 0.996 across stages. The measured ρ is
   0.998, against the model's 0 (`DATA_AUDIT.md`).
2. **At the default 14.5 s deadline, 1024 MB stops being warm-feasible.** v_w(1024 MB) is 3.28% at ρ ≈ 1 against
   0.22% at ρ = 0.
   - Both PRISM and the memory-adaptive baseline move to 2048 MB in every epoch.
   - The default deadline then behaves like the earlier short-slack regimes.
3. **Retuned at 14.5 s, PRISM costs +17.2 to +17.9% more than MemAdapt under shared spread (3 traces).**
   - Both meet 2% on every trace.
   - This is a lower bound: MemAdapt ends at the widened-grid edge 0.4 on all three traces, so it may be cheaper
     still.
   - Under independent spread, PRISM was −10.2 to +3.5% against MemAdapt, with failures of the 2% target on 1 (PRISM)
     and 2 (MemAdapt) of 3 traces.
   - **The "tie at the default deadline" therefore depends on P2.**
4. **At 13 s with fixed settings, PRISM's premium over MemAdapt rises from +11.3% (ρ = 0) to +21.2% (ρ = 1).**
   - RQ4's direction holds under both.
   - The magnitude depends on P2, and on the per-size model shown earlier.
5. **What P2 does not change:**
   - 3008 MB stays essentially unused (0-0.6% of epochs);
   - no 13 s SLA verdict changes;
   - MemAdapt at 13 s is unchanged (it already used 2048 MB).

## What ran

**Build.**
- **Source:** the isolated calibration build: 3edc386 + `candidate_exec_p2.patch` (the per-size lookup + the opt-in
  `exec_common_frac`), SHA-256 af456a05….
- **Patch scope:**
  - `exec_common_frac` = ρ, with each stage's log multiplier σ(√ρ·z_request + √(1−ρ)·z_stage) − σ²/2;
  - marginals unchanged;
  - default 0, with the common normals from separate random streams, so ρ = 0 is bit-identical to the existing model;
  - applied at all four draw sites, so PRISM's planning tables match the simulated world.
- **Where it is set up:**
  - Windows worktree `prism-repro/private/calib_build_20261124`;
  - Linux clone `~/prism_linux/calib2_3edc386` (WSL, py312).

**Linux suite:** 147 tests; 145 pass (`linux_test_suite.txt`).
- The 8 new `test_exec_common` and 11 `test_exec_measured` tests pass, as does the byte-identical rerun gate.
- **The 2 failures are the same pre-existing Windows-recorded hash anchors:**
  - `test_stage_demand_guard`, `test_default_configuration_matches_pre_feature_code`;
  - `test_stage_demand_guard`, `test_explicit_unit_phi_matches_pre_feature_code`.

  They fail identically in the unpatched Linux clone (`../calibration_final_20261124/linux_stage_demand_guard_unpatched.txt`).
- **No regression:** the last pass had 139 tests and the same 2 failures; this pass adds 8 tests, all passing.

**Plan:** `RUN_PLAN.md`, hashed at 25 Nov 2026 00:43:59Z (`PLAN.sha256`, `PLAN_HASHED_AT.txt`), before the mode was
implemented. MEAS (ρ = 0.998) was not run in the closed loop: its v_w differs from ρ = 1 by 0.002 points, below the
plan's 0.25-point threshold.

**Runs.** One group at a time, 2 workers, resumable (`run_linux.sh`, `p2_closed_loop.py`); outputs in `outputs/`.

| Group | Weeks | Check |
|---|---|---|
| G0: regression, ρ = 0, 14.5 s, PRISM | 5 | **identical in every field** to the per-size run E14_meas of `../calibration_final_20261124/` on 5 of 5 traces |
| G1: fixed settings, 14.5 s | 15 | |
| G2: retuned, 14.5 s, traces 101-103 | 110 new (validation weeks incl. edge expansions, plus tests not already run in G0 or G1) | expected counts by hand: 62 ρ = 0 and 68 ρ = 1 weeks at 14.5 s, all present |
| G3: fixed settings, 13 s | 10 (ρ = 0 is C13_meas of the last pass, reproduced by the same code path, G0) | |

**Coverage checks:**
- no failures or duplicates;
- `counts_sha256` identical per (trace, week, scenario) across every set, so the arrivals match;
- the event draws are matched by construction: the same keys, and the common factor comes from its own stream.

## Results

**Analysis:** `analyse_p2.py` → `analysis.json` and `analysis_stdout.txt`.
- Paired differences are ρ = 1 minus ρ = 0: mean ± 95% t half-width over traces.
- "Violating windows" is the closed-loop share of 15-minute windows violating the per-record target. It is reported
  separately from the warm miss probability v_w (DECISIONS.md section 3).

### G1: 14.5 s, settings fixed (PRISM at eps 0.01/0.01/0.03/0.03/0.03; MemAdapt-q90 at 1.3/1.5/1.1/1.2/1.2)

| | Cost, ρ = 1 vs 0 | Violating windows | Meets 2% (ρ = 0 → 1) | Memory ≥ 2048 MB (ρ = 0 → 1) |
|---|---|---|---|---|
| PRISM | **−8.7 ± 4.9%** | −1.76 ± 0.60 points | 3/5 → 5/5 (flips on 103, 104) | 0.6-10% → 100% of epochs |
| MemAdapt | **+14.7 ± 0.05%** | −1.91 ± 0.85 points | 2/5 → 5/5 (flips on 101, 103, 104) | 0% → 100% |

**Why PRISM's cost falls** (`outputs/`, week fields):
- At 1024 MB under ρ = 0, a cold start misses the deadline 53% of the time, so PRISM holds about 250-300 provisioned
  units.
- At 2048 MB under ρ = 1 (execution about 0.57×, p99 about 10 s), it holds about 100 units and lets about 4% of
  requests overflow to on-demand.

**Untested hypothesis:** PRISM under ρ = 0 might also be cheaper at 2048 MB. G2 trace 101, where PRISM selects eps
0.002 and uses 2048 MB throughout at a lower cost, points that way.

### G2: 14.5 s, each configuration retuned (same validation rule and edge expansion)

| Trace | ρ = 0: PRISM (eps) | ρ = 0: MemAdapt (a) | Premium | ρ = 1: PRISM (eps) | ρ = 1: MemAdapt (a) | Premium |
|---|---|---|---|---|---|---|
| 101 | 1,192.5 (0.002, **edge**), 0.00% | 1,239.4 (1.3), 2.23% ✗ | −3.8% | 1,101.2 (0.01), 0.15% | 939.7 (0.4, **edge**), 0.15% | **+17.2%** |
| 102 | 1,306.0 (0.01), 1.19% | 1,454.0 (1.5), 1.04% | −10.2% | 1,124.7 (0.01), 0.15% | 960.0 (0.4, **edge**), 0.60% | **+17.2%** |
| 103 | 1,194.1 (0.03), 2.53% ✗ | 1,153.6 (1.1), 2.83% ✗ | +3.5% | 1,118.0 (0.01), 0.15% | 948.2 (0.4, **edge**), 0.60% | **+17.9%** |

The table gives cost in USD per week, with the selected setting and the violating windows; ✗ marks a week that does
not meet 2%.

**Selections change:**
- PRISM: 2 of 3 traces;
- MemAdapt: 3 of 3.

**The paired costs** (ρ = 1 minus ρ = 0, retuned) are −6.4 to −13.9% for PRISM and −17.8 to −34.0% for MemAdapt.

**Validation behaviour under ρ = 1:**
- PRISM's eps 0.05 and 0.08 accept 1024 MB and violate 98-100% of windows; eps 0.005-0.03 keep 2048 MB.
- PRISM's selection is therefore interior but close to a cliff.

### G3: 13 s, settings fixed (PRISM eps 0.01; MemAdapt a = 0.6)

| | Cost, ρ = 1 vs 0 | Violating windows | Verdict flips | Premium of PRISM over MemAdapt |
|---|---|---|---|---|
| PRISM | **+8.8 ± 3.0%** | −0.03 ± 0.08 points | none | |
| MemAdapt | −0.01 ± 0.02% | +0.06 ± 0.34 points | none | |
| Premium | | | | **+11.3% (ρ = 0) → +21.2% (ρ = 1)** (18.7-24.7% per trace) |

Memory at 13 s is 2048 MB in both models (ρ = 1: 0.6% of epochs at 3008 MB on trace 103).

**Not run:** retuning at 13 s under ρ = 1. The retuned ρ = 0 result (premium +19 to +22%, MemAdapt at the edge) is in
`../calibration_final_20261124/`.

### By the plan's rules

| Rule | 14.5 s | 13 s |
|---|---|---|
| Verdict flips (≥ 2 of 5) | **changes** (PRISM 2, MemAdapt 3) | no change |
| Cost interval excludes 0 | **changes** (both) | **changes** (PRISM) |
| Selections change (≥ 2 of 3) | **changes** (both) | not tested |

## Claims: carry forward, sensitivity wording, revalidation

The earlier results keep their original scope: Eq. (2), or the per-size model at ρ = 0.

| Claim | Status |
|---|---|
| "At the default deadline PRISM reduces to a q0.9-driven rule and ties with QuantProv-q90 / MemAdapt" (R4.1; R2.6 "+1.6%"; R4.4 "ties at 14.5 s") | **Needs revalidation.** It holds at ρ = 0 (memory 1024 MB). At ρ ≈ 1, 1024 MB is infeasible at 14.5 s, both move to 2048 MB, and retuned PRISM costs ≥ 17% more. |
| "PRISM keeps 1024 MB at 14.5 s" (R6.1 plan, offline preview) | **True of the frozen controller (ρ = 0 tables).** A controller calibrated with ρ ≈ 1 would choose 2048 MB. The R6.1 run tests the frozen controller, so the reply must say so. |
| RQ4: "PRISM costs 8-28% more than the memory-adaptive rule at 12-13 s" | **Direction carried forward; magnitude needs sensitivity wording:** +11% fixed / +19-22% retuned (ρ = 0, per-size) against +21% fixed (ρ = 1, per-size); Eq. (2) gave +27.9%. |
| "A larger size restores compliance when 1024 MB cannot meet the deadline" | **Carried forward;** it now also applies at 14.5 s under ρ ≈ 1. |
| "PRISM uses 3008 MB at 13 s" | **Not carried forward** (the last pass: 0% under the per-size model); unchanged by P2. |
| Fixed-2048 headroom is 13-27% cheaper; R2.7's 3008 MB result | **Untested here;** stay flagged for revalidation. |
| Any submitted compliance or cost figure (fast simulator, Eq. (2), ρ = 0) | **Pre-calibration;** supersedes at the calibrated rerun, which must carry both ρ values if P2 is not settled. |
| Mixing configurations | Comparisons must pair the same ρ and the same scaling model. The earlier "measured" premiums (`../calibration_final_20261124/`) are ρ = 0 only and are now labelled so. |

## What the R6.1 live run can and cannot measure (actual run sheet, `../r61_live_plan_20261123/RUN_SHEET_20261124.md`)

**Can measure:**
- **ρ for this workload, on new documents.** The run has 323 P2-sized records per arm at 1024 MB, with `n_words` and
  four joined stage timings. Run `audit_dependence.py` on its archive.
- **Warm deadline misses at 1024 MB.** About 3.3% is predicted at ρ ≈ 1 and 0.2% at ρ = 0. With 323 records the 95%
  intervals separate them, though the per-arm attainment is imprecise.
- **Provisioned-concurrency readiness lag:** about 9 observations at 10 s resolution.
- **Cold starts, spill-over and actuation, descriptively.**

**Cannot measure:**
- **Burst overflow:** the run is capped at 8 in flight and P ≤ 4 per stage. That needs a separate burst test.
- **Application start-up:** the handler does no start-up work (`PRISM_INIT_ROWS = 0`). That needs a campaign with real
  start-up work.
- **Memory dependence of the dependence:** the run uses 1024 MB only. That needs a variable-size campaign at 2048 MB.
- **The window-level SLA:** 2 windows per arm.

The R6.1 pinned files verify (9/9 OK; `src/prism_repro` clean at 3edc386).

## Remaining before the final evaluation

1. **Author decisions:**
   - P2-DEP: ρ = 0.998 primary (recommended), or ρ = 0, with the other as a sensitivity;
   - P3: start-up value and 10 s handling;
   - D-CAL-1;
   - P1.
2. **The R6.1 live run** (separately authorised), then `audit_dependence.py` on its archive to replicate ρ, and the
   readiness-lag estimate.
3. **A separate burst-overflow test**, if any claim about AWS overflow under spikes is to be made. Optionally, a
   variable-size campaign at 2048 MB and a start-up campaign.
4. **Freeze a calibrated build:**
   - the cumulative patch, with ρ set by configuration;
   - the addendum v2 adopted;
   - the Linux suite, the gate and both regressions (legacy equality and G0);
   - a development dry run that resolves the MemAdapt grid edge (0.4 at both 13 s and 14.5 s under ρ ≈ 1), applied to
     every family alike.
5. **Only then,** Linux C1-C3 on seeds 106-130, with both ρ values if P2 is unsettled. Not started.

## Files

- **Data audit:** `DATA_AUDIT.md`, `audit_dependence.py`, `dependence_audit.json` and its stdout.
- **Reproduction of the saved estimates:** `repro_p2_correlation_check.*`.
- **Decision record and addendum:** `DECISIONS.md`, `ADDENDUM_DRAFT.md` (v2).
- **Plan:** `RUN_PLAN.md`, `PLAN.sha256`, `PLAN_HASHED_AT.txt`.
- **Build:** `candidate_exec_p2.patch`, `test_exec_common.py`, `test_exec_measured.py`, `linux_test_suite.txt`.
- **Miss table:** `vw_by_rho.*`.
- **Runs:** `p2_closed_loop.py`, `run_linux.sh`, `run_stdout.txt`, `outputs/`.
- **Analysis:** `analyse_p2.py`, `analysis.json`, `analysis_stdout.txt`.
- **Checksums:** `SHA256SUMS`.
