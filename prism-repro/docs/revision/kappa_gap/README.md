# The kappa gap: fast simulator against event level (R2.12, R5.M1, R2.2)

DIAGNOSTIC, PRE-CALIBRATION: assumed constants, current code (b3f191f), one Windows machine (`environment.json`).
Supersedes at recalibration. `scripts/revision/kappa_gap.py`, run 21 Nov 2026 17:01:40Z-17:38:45Z (`run.log`);
`summary.txt` is its `--analyse` output on the committed rows. Ten traces: seeds 101-105 x {stationary, new_spike},
held-out test weeks, PRISM eps = 0.02, GBM forecaster. Per trace, three runs: F the fast simulator; O the event-level
simulator replaying F's own schedule (open loop: every decision shared, so differences are the simulators'); C the
event-level closed loop.

## Conclusion: (c), a simulator difference. The fast simulator understates cold starts.

On identical schedules the event-level model produces **3.23x the fast simulator's cold starts per on-demand
request** (range 2.97-3.59 over the ten traces; 0.0686 against 0.0213) and **2.88x its cold starts** (2.41-3.19;
15,710 against 5,462 per trace-week), with 0.89x its on-demand requests. The cold-start ratio over all stage
executions is 0.00057 against 0.00020. On the same decisions the violating-window rate is **2.89% at event level
against 0.70% in the fast simulator**. The understatement is largest for the short stages (stage 1 x4.8, stage 4
x4.8; stage 2 x2.2, stage 3 x3.2). Every fast-simulator number in the paper that depends on cold starts (violating
windows, attainment, cold-start ratios, the init cost term) is affected in this direction; the event-level E9 replay
already showed 2.1-4.2x the violating windows, and this is the mechanism.

The two other explanations are excluded:

- **(a) Implementation error in the closed-loop update: no.** In every trace PRISM's recorded closed-loop kappa
  equals its own update recomputed from the final event-level telemetry (`summary.txt`, check (a)); unit test
  `tests/test_des_closed_loop.py::TestObservedOutcomes::test_cold_hit_estimate_follows_event_level_telemetry`.
- **(b) The floor suppressing a signal: no, the reverse.** In the fast simulator kappa sits at the 0.1 floor in
  89.7% of epochs (stored E1 runs of the submitted code: 82-97% by eps, 89.4% overall), but the same estimator
  without the floor averages 0.050: the floor raises the fast simulator's estimate, it does not hide a larger one.
  At event level the estimator averages 0.33 on F's schedule and 0.44 in closed loop and touches the floor in under
  0.5% of epochs; clipped and unclipped values agree.

## Cause, demonstrated on one day (seed 101, stationary, F's schedule)

| Variant | On-demand requests | Cold starts | Cold per on-demand request |
|---|---|---|---|
| Event model | 6,555 | 991 | 0.151 |
| The fast simulator's cold-start formula (D12-D13) applied to event-level concurrency | 6,555 | 991 | 0.151 |
| Event model, keep-alive unlimited | 6,529 | 352 | 0.054 |
| Event model, initialisation instantaneous | 6,487 | 592 | 0.091 |
| Fast simulator | 7,220 | 221 | 0.031 |

The fast simulator's accounting of new environments (on-demand concurrency above the previous ten minutes' maximum)
reproduces the event-level cold starts when it is fed event-level concurrency (991 and 991 here; 984 against 989 on
the stored E1 schedule for the same day, checked separately). The difference therefore lies in the concurrency the
fast simulator feeds it: its per-minute peak-concurrency draw is computed from warm service time only, so the
occupancy added by initialisation (cold requests hold their environment for init plus execution) is missing (removing
initialisation removes 40% of event-level cold starts), and environments that expire after the keep-alive and are
re-created later account for most of the rest (an unlimited keep-alive removes 64%).

## Consequences

- **Closed loop:** kappa 0.44 against 0.11; PRISM provisions more than the open-loop replay of the fast schedule,
  cost +8.9% (range +7.7 to +10.2%), violating windows -1.15 points (-2.38 to -0.60). Closed-loop numbers are
  therefore not comparable with fast-simulator numbers, and the gap is explained rather than unexplained.
- **R2.12:** the retuned cold-hit-floor comparison (`docs/revision/kappa_floor/`) was measured in the fast
  simulator, where kappa never escapes the floor and the unfloored estimate (0.05-0.06) is a sixth of the event-level
  one. Its conclusion (keep the 0.1 floor; the lower floor costs 2.8-3.7% more at matched compliance) must be rerun
  under the closed loop before it goes in the response letter. Not rerun here.
- **Not a bug to fix:** the fast simulator's concurrency model is a documented modelling approximation (D12-D13);
  changing it would move every published fast-simulator number. Recorded in KNOWN_ISSUES for the author's decision.
