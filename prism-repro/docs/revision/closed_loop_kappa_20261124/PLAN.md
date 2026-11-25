# R2.12(b) and R5.M5: the cold-hit (κ) floor under the closed loop. Plan fixed before the run (24 Nov 2026)

EXPLORATORY. PRE-CALIBRATION (`PipelineConfig()`/`PrismConfig()` defaults). Closed-loop event-level simulator,
development traces 101-105 only. The confirmatory seeds 106-130 and the frozen C1-C3 protocol are not touched. No AWS.

## 1. The requests

- **R2.12 (Reviewer 2, comment 12):** "the online cold-hit estimate reaches its lower clipping bound of 0.1 and remains
  there for most test epochs ... Please investigate alternative estimation approaches or operating conditions in which
  the estimator remains active. The manuscript should clarify whether this component is necessary under the default
  experimental configuration."
  - Tracker (b): "Establish the value of the floor or adaptive estimator under closed loop: open."
- **R5.M5 (Reviewer 5, major comment 5):** "The cold-hit estimate κ sits at its 0.1 floor, and the measured ratio is
  about 0.02 ... In those traces the floor, not the measured ratio, may exclude the 1024 MB no-provisioning option."
  - Tracker: proposal B3 is on hold until the floor comparison is retuned in closed loop.

## 2. Does changing the floor test the mechanism?

The floor matters only in epochs where the unclipped estimate falls below it. The earlier evidence points the other
way:
- the fast simulator's κ sat at the floor in 89.7% of epochs;
- the closed-loop pilot's test-week κ was 0.38-0.44 (`../kappa_gap/`, `../closed_loop_pilot/`);
- event-level cold starts per on-demand request are about 3.2 times the fast simulator's.

So under the closed loop, the floor may never bind. Then 0.1 against 0.001 is a null by construction, and a run that
showed no difference would say nothing about the estimator's value.

The plan therefore measures three things:
1. how often κ is at, or below, 0.1 under the closed loop;
2. whether lowering the floor changes any decision;
3. whether the adaptation itself matters, by freezing κ at the floor value.

The third arm answers R2.12's "whether this component is necessary".

## 3. Arms

Every arm runs PRISM's main configuration (Erlang-B, conformal recalibration, scale-in rule, joint memory search). Only
`kappa_clip` differs:

| Arm | `kappa_clip` | Meaning |
|---|---|---|
| **A** (default) | (0.1, 1.0) | the submitted estimator |
| **B** (low floor) | (0.001, 1.0) | the reviewer's lower floor; the estimator is free down to 0.001 |
| **F** (frozen) | (0.1, 0.1) | no adaptation: κ fixed at 0.1 once it leaves its prior (after `kappa_min_overflow` overflow requests), the fast simulator's effective behaviour |

**Two comparisons, labelled separately:**
- **Sensitivity (other settings fixed):** B and F run the test weeks at A's validation-selected eps.
- **Retuned:** A, B and F are each tuned on the validation week by the common rule (`experiment.select_by_rule` over
  `GRIDS["PRISM"]`, with the prespecified edge expansion over `GRIDS_WIDE`, the C1-C3 driver's code), then run on the
  test weeks.

## 4. Inputs and matching

- **Traces:** 101-105.
- **Weeks:**
  - validation week (stationary, days 14-20, event draw key 2);
  - four test weeks (stationary, growth, bursty, new spike; days 21-27, key 3).
- **Matching:** the event draws depend only on the trace and the week, so every arm sees identical requests,
  execution times and initialisation draws.
- **Other settings:** deadline 14.5 s, the default configuration. Forecasts and conformal state are built from the same
  bundle.
- **Platform:**
  - Linux x86-64 (WSL2), Python 3.12.3, the pinned `py312` environment (scikit-learn 1.8.0);
  - a clean clone of HEAD 3edc386: `src/`, `experiments/` and `tests/` are clean, as the driver requires;
  - 4 worker processes, checkpointed per week.
- **Driver:** `scripts/revision/closed_loop_exploratory.py`. It imports the frozen C1-C3 driver unchanged and adds
  families and sets. Its week task is the C1-C3 week task, plus per-epoch κ, P and memory saved as `.npz`.

## 5. Metrics

**Per test week and arm:**
- weekly cost (USD);
- violating-window rate, with exact per-request attainment at event level;
- weeks meeting 2%.

**κ diagnostics:**
- the share of epochs with κ at the floor (A: κ <= 0.1; B: κ < 0.1, i.e. epochs where A's floor would bind; F: by
  construction);
- the κ mean and its 5th and 95th percentiles.

**Decisions:**
- the share of epochs whose provisioned vector P differs from A's, on the same week at the same eps;
- the share whose memory differs;
- the mean provisioned level.

**Paired differences** (B − A and F − A) per scenario over the 5 traces:
- cost in %;
- violating windows in points;
- mean +/- 95% t half-width (df 4), and the traces with a lower value.

## 6. Interpretation (fixed before the run)

- **If A's κ is at the floor in < 5% of test epochs, and B equals A in at least 95% of epochs:** the floor is
  inactive under the closed loop. The reviewer's premise, κ stuck at 0.1, is a fast-simulator artefact, and the floor
  question is moot there.
- **F against A:** whether adapting κ changes cost or compliance. A difference is called only if its 95% interval
  excludes 0. Otherwise: "not distinguishable with five traces". No superiority or equivalence claim.
- **Retuned comparisons:** cost comparisons count as comparable only when the paired violating-window interval lies
  within +/-0.5 points (the C1-C3 rule). Otherwise they are confounded by compliance, and both are reported together.

## 7. Run size

Per trace and arm: 6 validation weeks (plus any edge expansion), 4 tuned test weeks, and 4 sensitivity test weeks
(B, F). Up to about 5 x (3 x 10 + 2 x 4) = 190 closed-loop weeks.
