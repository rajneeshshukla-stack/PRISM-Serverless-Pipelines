# Prespecification of the revision's comparisons (R3.5, R6.6)

Frozen 21 Nov 2026, on branch `closed-loop` at commit a10efe6 (the commit adding this file is its timestamp). This file
is never edited. A correction is a dated addendum in a separate file (`PRESPECIFICATION_ADDENDUM_<date>.md`), in its
own commit, saying what changed and why. **Pass criterion:** this file's commit precedes the first run on any of
seeds 106-130.

## 1. Simulator and constants

- Event-level simulator in closed loop: `des.simulate_events(cfg, draws, controller=closed_loop.PolicyController(...))`.
  Each epoch the controller sees telemetry up to minute 5k - 2 only, then sets epoch k (tested: no lookahead,
  conservation across boundaries).
- Initialisation protocol (`docs/revision/event_init/`): the week starts with provisioned capacity ready and no warm
  on-demand environment; pre-week information is the trace's arrival history and the fast simulator's history
  concurrency, the same for every policy.
- Constants: `PipelineConfig()` and `PrismConfig()` defaults at a10efe6. These are not measured. **Every result
  produced under this prespecification is pre-calibration and supersedes at recalibration**; the comparisons are
  rerun unchanged, under this same file, when measured constants replace the assumed ones.
- The fast simulator is not used for any confirmatory comparison (it understates event-level cold starts about 3x,
  `docs/revision/kappa_gap/`).

## 2. Policies

Confirmatory set: PRISM (Erlang-B risk model, conformal recalibration, scale-in rule, joint memory search);
QuantProv-q90 (calibrated q0.9 forecast times a, with the scale-in rule); Reactive (target tracking on observed peak
concurrency); MemAdapt-q90 (`policies.MemAdapt`, tau_w = 0.005). All forecast-driven policies use the GBM forecaster,
computed online from observed arrivals. Exploratory only: PredHead, PredHead+S, QuantProv-q99, Static, Scheduled,
OnDemand. The oracle has no closed loop and is not compared.

## 3. Traces, seeds and split

- Traces: `data/trace_set_revision.json` (SYNTHETIC; counts fixed by the SHA-256 there). Development seeds 101-105 may
  be used for pilots and diagnostics and never enter a confirmatory result. **Confirmatory seeds: 106-130** (25
  traces), scenarios stationary, growth, bursty and new_spike.
- Split (submitted): forecasters fitted on days 0-13; conformal offset from zero at day 14; validation week days
  14-20 (scenario-independent), test weeks days 21-27 per scenario. The PROVISIONAL split (fit 0-10, out-of-sample
  warm-up 11-13) is exploratory unless adopted by addendum before the first confirmatory run.
- Event draws: key 2 for the validation week, key 3 for test weeks; every policy sees identical workloads and draws.

## 4. Tuning rule and grids

- Per policy and trace: run every grid value on the closed-loop validation week; select the cheapest setting whose
  violating-window rate is at most 2% (13 of 672 windows); if none qualifies, the least violating, ties to the
  cheaper (`experiment.select_by_rule`).
- Initial grids: `experiment.GRIDS` (PRISM eps 0.005-0.08; QuantProv a 0.6-1.5; Reactive u 0.40-0.90; MemAdapt as
  QuantProv).
- Edge-expansion rule: if the selected value is the first or last value of the grid, add the next value of
  `experiment.GRIDS_WIDE` beyond that end, rerun validation for it, and reselect; repeat until the selection is
  interior or `GRIDS_WIDE` has no further value on that side. Every expansion is recorded. A selection still at an
  edge after that is reported as an edge hit.

## 5. Evaluation and metrics

- The selected setting of each policy runs on the four held-out test weeks of the same trace.
- Per trace (the independent unit; scenarios averaged within a trace): weekly cost (simulator cost model, USD/week),
  pooled violating-window rate over the four test weeks, weeks meeting the 2% target.
- Paired difference per trace, PRISM minus comparator: cost (%) and violating-window rate (points); reported as mean
  with a 95% t interval over the 25 traces, plus counts of traces in each direction.
- A cost difference is called a difference only if its interval excludes zero; a tie is claimed only if the interval
  lies within +/- 2%. Two policies "attain similar compliance" only if the paired violating-window interval lies within
  +/- 0.5 points; otherwise the cost comparison is reported as confounded by compliance.

## 6. Confirmatory comparisons

- C1. PRISM against QuantProv-q90, default deadline (14.5 s), all four scenarios.
- C2. PRISM against Reactive, default deadline, all four scenarios.
- C3. PRISM against MemAdapt-q90 in the short-slack regime (deadline 12 s, non-scaling 0.5), stationary scenario.

Everything else is exploratory and labelled so: per-scenario breakdowns, matched-compliance frontiers (post hoc),
stage-specific demand, above break-even and wider eps grids, the provisional split, cold-hit floor variants,
fast-simulator comparisons, and any pilot on development seeds.

## 7. Pilot (exploratory, before the confirmatory runs)

Development seeds 101-103, stationary scenario, policies PRISM, QuantProv-q90, Reactive and MemAdapt-q90, tuned and
evaluated by sections 4-5. Its purpose is to check the pipeline end to end and the compute budget; it is not a result.
