# The optimiser end to end where its reduction to a quantile rule should fail (R2.5, R4.1, R7.1, R6.7)

PRE-CALIBRATION, EXPLORATORY: fast simulator, assumed constants, current code. Forecast-driven results depend on
the platform (NA-1); these come from one Windows machine (`environment.json`: Windows 11, Python 3.12.9, numpy
2.4.4, scipy 1.17.1, scikit-learn 1.8.0).

**Provenance.** `scripts/revision/stage_demand_e2e.py . <out> both --workers=5`, run 21 Nov 2026 09:09:25Z to
14:50:05Z (`run.log`; the machine was suspended for about three hours inside that interval) in a separate worktree
at commit bde7d25 (stage-specific demand, guarded byte-identical at unit demand by 85d909e). The committed script
differs from the run copy only in its analysis section (a same-allocation-shape comparison was added); the code that
produced the rows is identical (checked). `summary.txt` is `python scripts/revision/stage_demand_e2e.py .
docs/revision/stage_demand_e2e --analyse` on the committed rows (`rows_<part>_<profile or regime>_<seed>.jsonl`).

**Design.** Reviewer 4's two tests. Part P, stage-specific demand phi on the paper's grids: common (1,1,1,1), filter
(1,1,0.5,0.5), fan-out (1,1,3,3), batch (1,1,1,0.1). Part B, the wider eps grid (`GRIDS_WIDE`, eps up to 0.20) on
the paper's workload and prices; on a smoother 6000 records/min workload where utilisation exceeds the 0.6
break-even; and with the provisioned price halved (break-even 0.30). Seeds 101-105, every parameter on the
validation week and on all four test weeks (20 weeks per cell); validation-selected settings, paired over the 20
weeks, and POST HOC matched compliance (per trace, frontier over the parameter, mean of four test weeks).
QuantProv-q90 and PredHead+S scale by phi_s d_s (they know phi, as PRISM's risk model does).
QuantProv_q90-blind scales by d_s, ignoring phi: a REFERENCE with the same per-stage allocation shape as PRISM's
candidate family (15).

## Results, nulls and unfavourable results first

1. **No regime shows a consistent end-to-end optimiser advantage over a calibrated quantile rule with the same
   information and the same per-stage allocation.**
2. **Wider eps grid, the paper's workload: null.** The reduction does fail at large eps: PRISM chooses above the
   smallest feasible level in 23.7% of feasible epochs at eps 0.08 and 72-100% at 0.10-0.20. End to end it makes no
   material difference: PRISM against QuantProv-q90 at the validation-selected settings costs -1.2 +/- 2.2%
   (cheaper in 10/20 weeks) with the same violating-window rate (+0.00 +/- 0.23 points); at matched compliance
   -2.3% to -1.0%. From eps 0.15 the chance constraint no longer binds and the cost model alone sets the level:
   2.55% violating windows, above the target, at the same cost for 0.15 and 0.20.
3. **Above break-even, the smooth 6000/min workload: PRISM is costlier.** +11.1 +/- 0.8% at the validation-selected
   settings (cheaper in 0/20 weeks), with fewer violating windows (0.11% against 1.28%); +9.0% to +9.9% at matched
   compliance. QuantProv-q90 runs at a billing utilisation of 0.80, PRISM at 0.57. PRISM's frontier jumps from
   0.13% violating windows (eps 0.10) to 12.5% (eps 0.15), so it has no setting near the rule's operating point.
4. **Provisioned price halved (break-even 0.30): mixed.** PRISM costs +4.3 +/- 1.5% more at the validation-selected
   settings and is more compliant (1.19% against 1.95% violating windows; 19/20 against 11/20 weeks); at matched
   compliance -1.3% (1.0%), +1.6% (1.5%), +4.5% (2.0%). From eps 0.08 the cost model sets the level in 98.5-100% of
   epochs and the outcome no longer changes with eps.
5. **Stage-specific demand: cheaper than the phi-aware rule, through the allocation shape rather than the
   optimisation.** At the validation-selected settings PRISM (paper's family) against QuantProv-q90: filter
   -3.1 +/- 1.4% (cheaper in 16/20; -0.32 points violating windows), fan-out -4.5 +/- 2.4% (16/20; -0.65 points),
   batch -6.8 +/- 2.0% (20/20; -0.03 points). At matched compliance -4.0 to -7.8%, -2.8 to -7.9% and -4.6 to -8.4%.
   But the phi-blind reference, a quantile rule with PRISM's allocation shape, is itself cheaper than the phi-aware
   rule (selected settings: -10.0 +/- 1.6% fan-out, -3.0 +/- 1.4% batch, +2.6 +/- 1.2% filter). Against that
   same-shape rule PRISM's matched-compliance margin is -1.9 to -4.3% (filter), +3.3 to +5.4% (fan-out: PRISM
   costlier) and -0.6 to -2.0% (batch); at the selected settings -5.5 +/- 1.1% (filter, +0.36 points violating
   windows), +6.0 +/- 1.2% (fan-out, -0.88 points) and -3.7 +/- 2.7% (batch, +0.11 points). The family proportional
   to the per-stage load (PRISM-phi) is closer to the phi-aware rule: -0.5 +/- 1.6%, -2.7 +/- 1.2%, -3.1 +/- 2.4%.
6. **Common demand, the paper's grid** (control): PRISM against QuantProv-q90 +0.7 +/- 1.0% at the selected
   settings, -0.5% to -2.3% at matched compliance; it reproduces the calibration sweep's submitted row exactly
   (1150.1 USD/week, 1.78%, 12/20 weeks).

## Two corrections to recorded claims

- **The level-choice bound depends on eps.** The recorded "below 0.07% for corrected code" is for the per-trace eps
  of the submitted run (0.02-0.05). Here, common demand, every eps on all 20 weeks: at most 0.11% up to eps 0.05
  (43 of 40,307 at 0.03), but 9,548 of 40,320 (23.7%) at eps 0.08; current code's validation selects 0.08 for three
  traces, and at its selections 5,908 of 40,316 feasible epochs (14.7%) are above the smallest. Corrected in
  notes/number_audit.md and notes/manuscript_proposals.md.
- **Fan-out is feasible end to end.** The static probe found the paper's family infeasible under a 3x fan-out on the
  paper's grid at kappa 0.35 (NA-4). End to end, with the cold-hit estimate at its floor, the family is feasible in
  96.7-100% of epochs at every eps and meets 2% in 19/20 weeks at the selected eps 0.08, at 79.3% of epochs above
  the smallest feasible level.

**Caveats.** Fast simulator only; the event-level simulator refuses phi != 1 (fan-out joins, filter exits and
batch formation are not modelled), and a record's latency counts one execution per stage with that stage's
per-execution cold-start probability. Matched compliance is post hoc and interpolates linearly, across a wide gap
where a frontier jumps (finding 3). PRISM's selection sits at eps 0.08, the top of the paper's grid, in most Part P cells.
