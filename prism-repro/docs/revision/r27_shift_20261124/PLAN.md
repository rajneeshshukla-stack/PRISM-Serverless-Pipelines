# R2.7: a within-run shift in execution time, dynamic against one-time memory (plan fixed before any run, 24 Nov 2026)

EXPLORATORY. Fast simulator, PRE-CALIBRATION constants, development traces only, Windows, current code (3edc386,
`src/` unchanged). The narrowed RQ4 and its fixed-regime result are kept as they are. This is a separate exploratory
experiment, and it does not enter the main study. Its SHA-256 is in `PLAN.sha256`.

## Request (Reviewer 2, comment 7)

> "Please investigate scenarios where the application workload changes during execution, including shifts in CPU
> intensity, memory demand, function execution time, or initialization latency. Such experiments would directly test
> whether dynamic memory optimization provides benefits that cannot be achieved through a one-time configuration
> decision."

This pass tests **one** of the listed shifts: CPU intensity, modelled as a step in warm execution time. Memory
demand and initialisation-latency shifts are not tested.

## Regime shift (fixed)

- **Traces:** development traces 101-105, stationary scenario, test week. These are the paper's synthetic traces and
  draws.
- **The shift:** at the start of test-week day 4 (week minute 4320), every stage's warm execution time steps up by
  a factor of 1.5. That is `warm_mean_1024` x 1.5, and the memory scaling (Eq. (2)) is unchanged. At 1024 MB the
  mean warm end-to-end time rises from about 8.9 s to about 13.2 s, against the 14.5 s deadline.
- **What changes in the simulator:** after the change point, every execution-dependent input uses the shifted
  configuration:
  - peak concurrency K, which scales with the service time;
  - warm-latency samples;
  - billed durations;
  - attainment tables.

  The random draws are the same before and after (common random numbers).
- **Where the simulator lives:** `scripts/revision/r27_shift.py`, a copy of `simulator.simulate` with these splices.
  Check before any result: with no shift, it must reproduce `simulator.simulate` exactly on every summary field.

## Policies and information (fixed)

PRISM uses the main configuration (`PrismConfig` defaults, Erlang-B), ε = 0.02, gbm.
- **Information:** both controllers that adapt receive the same estimate, the true shifted execution times, 60
  minutes after the change (epoch 876). That stands in for an online estimator. Neither sees it earlier.
- **(A) PRISM-online, dynamic memory (EXPLORATORY variant, separate from the published configuration):** at epoch
  876 its optimiser and stage means are rebuilt from the shifted configuration. Memory stays a decision every epoch,
  as in PRISM.
- **(B_m) PRISM-online, one-time memory m:** identical to A, including the same estimate at the same epoch, but its
  memory is fixed at m for the whole week, for m in {1024, 2048, 3008}.
  - B_1024 is the one-time configuration an operator would choose from pre-shift information. PRISM and MemAdapt
    both choose 1024 MB at the 14.5 s deadline.
  - The cheapest B_m that meets 2% is the best one-time configuration in hindsight.
- **(C) Published PRISM, no estimate (reference):** it keeps its pre-shift model all week. This shows what happens
  without online estimation, which the published configuration lacks.

## Success criteria (fixed)

Per trace, with the week's violating-window rate (target ≤ 2%) and the week's cost:

1. **Benefit over the pre-shift one-time configuration:** A meets 2% and B_1024 does not; or both meet it and A
   costs at least 5% less; or neither meets it and A's rate is at least 0.5 points lower.
2. **Benefit that no one-time configuration achieves:** A meets 2%, and A costs at least 5% less than the cheapest
   B_m that meets 2%. If no B_m meets 2% and A does, that also counts.

Dynamic memory is said to provide a benefit on a criterion only if it holds on at least 4 of the 5 traces. Otherwise
the result is reported as no demonstrated benefit on that criterion.

**Also reported:**
- post-shift violating-window rates (windows after minute 4320, and after the estimate at minute 4380);
- A's memory per day;
- C against A.

**Not claimed:** any result for the other shift types, for calibrated constants, at event level, or on AWS.
