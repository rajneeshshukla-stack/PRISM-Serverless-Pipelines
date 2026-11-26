# R1.1(b): safety-margin rule, out-of-sample check (23 Nov 2026)

- `PLAN.md`: criteria fixed before the analysis.
- `margin_rule.py`: the analysis; no simulation.
- `result.txt`: the output.

Input: `../event_severity_resumed_20261122/rows_R24_*.jsonl`. These are PRISM's E12-selected schedules on development
traces 101-105, replayed at event level with uniform margins of 0-50%. Labels: PRE-CALIBRATION, OPEN LOOP, POST HOC
replay.

**Result.** Leave one trace out, with either criterion (every training week, or 90% of them):
- 16 of 20 held-out weeks meet 2% (95% Clopper-Pearson 56-94%).
- All four failures are trace 103: the 10% margin chosen from the other traces gives 2.08-2.83%, and the trace needs
  20-50%.
- The chosen margins cost +24.9% (strict criterion) and +15.5% (lenient criterion).

**Related claim elsewhere (not changed).** R2.4 reports in-sample counterfactuals on the same 20 weeks: "a uniform 10%
margin meets 2% in 16/20 weeks". They are already labelled "not a policy the controller could run without hindsight",
so the two do not conflict. Proposed clarification for R2.4's reply, for the author to decide: add "(in sample; a margin
chosen on other traces does not transfer to trace 103, see R1.1)".
