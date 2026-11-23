# Confirmatory closed-loop comparisons C1-C3, 22-23 Nov 2026

Relevant reviewer comments: R2.1, R2.18, R3.3, R4.2, R6.4, R6.5, R7.6.

## Labels

**PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION.** The runs use the `PipelineConfig()` and `PrismConfig()` defaults at
a10efe6. These are assumed, not measured; see `CONSTANTS.md` for each constant's support and for what blocks a
calibrated rerun. The runs follow the frozen `../PRESPECIFICATION.md` (d16fbea, no addendum) exactly:
- event-level simulator in closed loop;
- confirmatory seeds 106-130;
- submitted split: validation week days 14-20 (event draw key 2), test weeks days 21-27 (key 3);
- the common tuning rule with the prespecified edge expansion;
- per-trace paired differences with 95% t intervals (df 24), and the three prespecified criteria.

Development seeds 101-105 appear only in the driver and evaluator checks below, never in a C1-C3 result.

## What ran (`run/`)

| Comparison | Families | Deadline, non-scaling | Scenarios (test weeks) | Traces |
|---|---|---|---|---|
| C1 | PRISM against QuantProv-q90 | 14.5 s, 0.5 (defaults) | stationary, growth, bursty, new_spike | 106-130 |
| C2 | PRISM against Reactive | 14.5 s, 0.5 | the same four | 106-130 |
| C3 | PRISM against MemAdapt-q90 | 12 s, 0.5 | stationary | 106-130 |

**Driver:** `prism-repro/scripts/revision/closed_loop_confirmatory.py`, new and uncommitted. Its SHA-256 is recorded
in `run/environment.json`.
- Each closed-loop week is one task, saved atomically as `run/weeks/...json` when it completes, so a stopped run
  resumes where it stopped.
- **Groups and selection:** a (set, seed, family) group runs its validation grid first. It then applies
  `experiment.select_by_rule` and the prespecified edge expansion over `experiment.GRIDS_WIDE`, with code copied
  verbatim from `scripts/revision/closed_loop_pilot.py`.
- **Test weeks:** a group's test weeks are submitted only after its selection is final, so no test outcome can enter
  a selection.
- **Shared bundles:** each seed's trace bundle, with its trained forecasters, is built once and loaded by every
  worker. The files are pickled under `run/bundles/`, which Git ignores.

## Verification of the driver and the evaluator (before the confirmatory runs)

| Check | Result | File |
|---|---|---|
| Trace provenance, seeds 101-130 | 150 of 150 seed-scenario counts match `data/trace_set_revision.json`; the first 21 days are identical across scenarios; the workload parameters equal the manifest. The manifest (4c43769, 20 Nov) predates the prespecification (d16fbea, 21 Nov) and is unchanged | `trace_verification.json` |
| Closed-loop regression tests at fd8b01a | 30 of 30 pass: no lookahead, closed loop equal to open loop on the same schedule, telemetry conservation, epoch-major guard, Erlang-B oracle | `tests/unittest_closed_loop.txt` |
| Full unit-test suite at fd8b01a (regeneration tree) | 124 of 124 pass | `../regeneration_20261122/` |
| Driver reproduces the saved exploratory pilot (trace 101, all four families) | 41 of 41 rows and 424 of 424 fields identical (wall time excluded). The selections and expansions are the same. One thread per process, against the pilot's multithreaded forecaster training, does not change any value | `pilot101_check/comparison.txt` |
| Shared-bundle path | the reloaded bundle equals a fresh build in 58 of 58 arrays and predictions; a closed-loop week run from it equals the reproduction's row in every field | `pilot101_check/bundle_check.json` |
| End-to-end smoke check, development seed 101 (R2.1, R4.2, R6.4) | see `checks/smoke_check_101.json` | `checks/` |
| R3.3: the evaluator does not use the matched peak draw | see section "R3.3" | `checks/r33_match_check.json` |

## R3.3: how the event-level evaluation removes the Eq. (14) match

- **The match.** The fast simulator draws each minute's peak concurrency as a Poisson quantile at
  `u ~ U(1 - peak_upper_frac, 1)`, with `peak_upper_frac = 0.45` (`src/prism_repro/simulator.py`, `WeekDraws`). That
  construction is the one behind Eq. (14), and its mean is close to the effective load PRISM plans for.
- **The event-level evaluator** (`src/prism_repro/des.py`) never reads `peak_upper_frac`, `u_peak` or the effective
  peak.
  - Every request is an event, placed uniformly at random within its minute.
  - Every request has its own execution, orchestration and initialisation draws.
  - Each request is routed to a free provisioned environment, a warm on-demand one, or a cold start.
  - Concurrency, cold starts and every latency follow from that routing, and window attainment is computed from
    every request.
- **Configuration check** (`checks/r33_match_check.json`, exploratory, development seed 101):
  - One fixed PRISM schedule was evaluated under `peak_upper_frac` 0.45 and 0.90.
  - **Event level:** bit-identical, with cost 1,052.37 USD and 2.68% violating windows under both.
  - **Fast simulator:** the outcome changes, from 1.04% to 0.89% violating windows, with overflow share 0.0126 against
    0.0093.
  - On that same schedule the event level records 2.6 times the fast simulator's violating windows and 3.1 times its
    cold-start ratio, consistent with Table X and `../kappa_gap/`.
- **The one residual: pre-week history.** The closed loop's pre-week history concurrency (`K_hist_default`, the same
  for every policy, prespecification section 1) comes from the fast simulator's draws.
  - Among the confirmatory families only Reactive reads it, and only at decisions k = 0 and k = 1. Its 5-minute window
    then reaches 5 and 1 minutes before the week starts.
  - Those are 2 of 2,016 decisions per week.
  - PRISM, QuantProv-q90 and MemAdapt-q90 do not read it.
- **Consequence.** C1-C3, evaluated at event level, are the requested test without the match. PRISM's own planning
  model still uses its effective load (Eq. (14)) to make decisions, as designed; only the evaluator's dependence on it
  is removed.

## R6.4: shared forecasting and smoothing

- **QuantProv-q90** provisions `a x q_cal[k, q0.9]`: the calibrated q0.9 forecast from the same GBM forecaster and
  conformal offset that PRISM reads (`use_conformal = True`). It applies the scale-in rule
  `P = max(P, floor(0.85 x previous))` (`src/prism_repro/policies.py`).
- **PRISM** applies the same rule with the same factor (`hysteresis = 0.85`, `use_hysteresis = True`), but only while
  its memory size is unchanged. That is the one difference.
- In closed loop, each policy's forecaster runs online from the same observed arrivals, so the forecasts are identical.
  `checks/smoke_check_101.json`, check D, compares them array by array.

## Results

Filled in when the runs complete: `run/summary.txt`, `run/tables/`, and `RESULTS.md`.
