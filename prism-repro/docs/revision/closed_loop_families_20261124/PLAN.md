# R5.M1(e) and R2.2(b): the missing closed-loop comparator runs. Plan fixed before the run (24 Nov 2026)

EXPLORATORY. PRE-CALIBRATION. Closed-loop event-level simulator. Development traces 101-105 only; the confirmatory seeds
106-130 and the frozen C1-C3 are untouched and remain separate. No AWS.

## 1. The requests

- **R5.M1, Reviewer 5, major comment 1:** "Please run the event-level simulator in closed loop as the main evaluator,
  retune every family under it on full grids, and use exact attainment in the fast simulator. ... Instead of the
  first two requests, a narrower option is closed-loop runs for reactive provisioning, PRISM, QuantProv-q90 and
  PredHead+S under the new spike."
- **R2.2, Reviewer 2, comment 2:** "All comparative baselines should be evaluated under the same closed-loop
  conditions."
- **Tracker:** R5.M1(e) is open (the pilot was stationary only, and C1-C3 has no PredHead+S). R2.2(b) is open (C1-C3
  covers QuantProv-q90, Reactive and MemAdapt-q90 only).

## 2. Families

| Family | Grid | Run in |
|---|---|---|
| PRISM | `GRIDS["PRISM"]` | set K of `../closed_loop_kappa_20261124/`, arm A (the same code, bundles, draws and tuning). Reused, not rerun |
| QuantProv-q90, Reactive, PredHead+S (`PredHead+hyst`) | paper grids | set CMPe: R5.M1(e)'s narrower option |
| PredHead, QuantProv-q99, Static, Scheduled | paper grids | set CMPb: the rest of R2.2(b) |
| OnDemand | no parameter | `ondemand`: one week per trace and scenario |
| MemAdapt-q90 | — | **Not run.** At 14.5 s it never leaves 1024 MB, and its closed-loop outcomes equal QuantProv-q90's in every field (pilot; C1-C3 driver). It is covered at 12 s by C3 |

## 3. Design

**Shared with the κ study:**
- traces 101-105;
- validation week (stationary, days 14-20, event draw key 2) and four test weeks (stationary, growth, bursty, new
  spike; key 3);
- deadline 14.5 s;
- the same bundles in one output directory.

Every family therefore sees identical requests and draws.

**Tuning:**
- the common rule (`experiment.select_by_rule`), with the prespecified edge expansion over `GRIDS_WIDE` (the C1-C3
  driver's code);
- test outcomes never enter a selection.

**Information:** each controller sees telemetry up to the decision minute minus the activation lag, and forecasts from
the bundle's online forecaster, as in C1-C3.

**Attainment:** exact per request (event level).

**Platform:** Linux x86-64, a clean clone of 3edc386, pinned `py312`, 4 workers, checkpointed per week.

## 4. Metrics and reporting

**Per family and scenario:**
- weekly cost;
- violating-window rate;
- weeks meeting 2%;
- mean +/- 95% t half-width over 5 traces.

**Paired, PRISM minus comparator, per scenario** (5 traces, df 4):
- cost %;
- violating windows in points;
- direction counts.

Cost comparisons are called comparable only when the paired violating-window interval lies within +/-0.5 points.
Otherwise they are confounded by compliance, and both quantities are reported together. No superiority or
equivalence claim is made.

**The new-spike rows (R5.M1(e)) come first.**

**Checks:**
- run counts against the expected groups;
- no duplicate week files;
- failures.json empty;
- identical `counts_sha256` per trace and week across families.

## 5. Not covered

- calibrated constants;
- the 25 confirmatory traces;
- a closed-loop matched-compliance frontier.
