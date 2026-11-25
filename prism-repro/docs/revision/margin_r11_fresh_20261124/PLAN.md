# R1.1(b): diagnosis of the trace-103 failures, a revised margin rule, and its validation on fresh traces (plan fixed before the run, 24 Nov 2026)

EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event-level simulator, Windows. No AWS. Seeds 106-130 (confirmatory, frozen)
are not used, and `../PRESPECIFICATION.md` is unchanged. This file is fixed before any fresh-trace run; its SHA-256
is in `PLAN.sha256`.

## 1. Reproduction (done before this plan)

`../margin_r11_20261123/margin_rule.py`, rerun on `../event_severity_resumed_20261122/rows_R24_*.jsonl`, gives a
result byte-identical to `../margin_r11_20261123/result.txt`:
- leave one trace out, 16 of 20 held-out weeks meet 2%;
- the four failures are all trace 103, at the 10% margin chosen from the other traces.

## 2. Diagnosis: causes supported by the logs, and hypotheses

**Supported by the stored rows:**
- Source of the margin-0 figures: `rows_R24_*.jsonl`.
- Source of the validation figures: `../../../results/raw/E12/E12_seed*.jsonl`, the event-level validation-week
  replays that selected PRISM's risk budget ε.

1. **Trace 103 runs PRISM at the largest risk budget.** E12 selected ε = 0.03 on 103, against 0.005 (101, 102),
   0.01 (104) and 0.02 (105).
2. **Its validation week was the easiest, and the selection had almost no slack.** At ε = 0.03, the validation
   violating-window rate is 1.935% on 103, against 2.08-3.13% on the other traces. 103 is the lowest or
   second-lowest trace at every ε. The selected budget met 2% by 0.07 points on 103, against 0.21-0.51 points on
   the other traces.
3. **The validation-to-test shift is largest on 103.** At the selected ε, the mean test-week rate minus the
   validation rate is:
   - 103: +1.38 points (1.94% → 2.83-4.02%);
   - 104: +0.41;
   - 105: +0.22;
   - 101: −0.15;
   - 102: −0.26.
4. **More overflow follows the larger budget.** Overflow share at margin 0 is 1.10-1.17% on 103, against 0.32-0.86%
   on the other traces.
5. **All violations come from initialisation occupancy.** With instantaneous initialisation (`init_instant`), every
   one of the 20 weeks, trace 103 included, has 0.00% violating windows.

**Hypotheses, not shown by the logs:**
- **(H1)** Trace 103's validation week has fewer random bursts than its test weeks: 249 of 271 violating windows
  contain a random burst (R2.4). Burst counts per week were not tabulated here.
- **(H2)** The selection rule rewards an easy validation week with a riskier ε, which does not transfer to harder
  weeks.
- **(H3)** The ε dependence would persist under calibrated constants (the 6 s modelled start-up, P3).

## 3. Revised rule (fixed now)

The operator knows, at decision time:
- the risk budget ε selected on the validation week;
- PRISM's schedule.

The rule uses nothing else.

**Rule E (primary):** an ε-dependent uniform margin on every stage's provisioned concurrency, P → ceil(P x (1 + m)):
- m = 10% if the selected ε ≤ 0.02;
- m = 50% if the selected ε ≥ 0.03.

These values are the strict criterion (every development week meets 2%) applied separately to the development weeks
with ε ≤ 0.02 (101, 102, 104, 105: 16 of 16 meet 2% at 10%) and with ε ≥ 0.03 (103: 4 of 4 need 50%). Trace 103 is
therefore development evidence. For ε above 0.03 the rule extrapolates; such cases are flagged.

**Rule U (comparator):** the strict criterion on all 20 development weeks, which gives a uniform 50% margin for
every ε.

## 4. Fresh eligible cases (fixed now)

- **Seeds 131-135:** new synthetic traces from the same generator (`prism_repro.workload.generate_trace`), never used
  in development or confirmation.
- **Weeks:** the four main scenarios (stationary, growth, bursty, new spike), test weeks: 20 weeks.
- **Pipeline, the paper's E1 and E12 code paths, for PRISM only:**
  - `TraceBundle(seed, PipelineConfig())`;
  - fast-simulator schedules (`simulator.simulate`) for every ε in `GRIDS["PRISM"]` on the validation week;
  - event-level validation replays (`des.simulate_events`, draw stream 2) and `select_by_rule` (cheapest with ≤ 2%,
    else least violating), as `scripts/revision/e12_event_retune.py` does;
  - the selected ε's fast-simulator test-week schedules, replayed at event level (draw stream 3) with margins 0, 10%
    and 50%.
- **Eligible:** a week counts if every replay completes without error. A failed replay is reported, not dropped.
- **Code-path check, before the fresh run:** recompute trace 103's validation-week schedule at ε = 0.03 and its
  event-level replay, and compare with the stored E1 schedule and E12 row. Any difference (for example from the
  platform: the stored rows reproduce on Linux) is reported and does not stop the run.

## 5. Pass criterion (fixed now)

Rule E passes if at least 18 of the 20 fresh weeks meet 2% (violating-window rate ≤ 2%).

**Reported in every case:**
- weeks meeting 2% under rule E, rule U and margin 0, each with a 95% Clopper-Pearson interval;
- the mean, minimum and maximum relative cost of the margin against the same week's margin-0 replay;
- every failing week, with its seed, scenario, ε and rate;
- the ε selected per seed, and whether any lies above 0.03 (extrapolation).

**Not claimed:**
- an AWS Lambda margin, or the size of violations on AWS (R1.1(a));
- a production margin. The constants are assumed (P3) and the replays are open loop.
