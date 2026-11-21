# Decisions pending for the author

Prepared 21 Nov 2026 on branch `phase-e-review`. Nothing below is decided; each section gives the options, what each
costs, which comment IDs it releases, what is already built, and a recommendation with its evidence. Numbers are
PRE-CALIBRATION (fast simulator, assumed constants, current code) unless stated. Reviewer wording is paraphrased
from the reviewer file; check each against the current manuscript text.

## D1. Memory: add the memory-adaptive baseline, or narrow the abstract (R2.6, R7.4, R3.7; touches R4.4b)

**Question.** Reviewers 2, 3 and 7 ask whether PRISM's joint online memory sizing adds anything beyond a simple
memory-selection rule. The stored post hoc comparison found fixed-2048 MB headroom 14-29% cheaper than PRISM's best
setting in every short-slack regime (two traces, fixed size and setting chosen with test-week knowledge).

**Options.**
- (a) Add the baseline to the memory comparison (Table IX / S14). Releases R2.6 and R7.4 (both ask for exactly
  this) and R3.7 (its first branch). Cost: one more family at the regeneration, about 30 minutes of fast-simulator
  time per regeneration; text for one paragraph and one table column.
- (b) Narrow the abstract and the graphical-abstract caption to what Table IX supports. Releases R3.7 (second
  branch) and R4.4(b) (caption). R2.6 and R7.4 stay open: they ask for the comparison, not for softer wording.
- (a) and (b) together: releases all four.

**Built.** `policies.MemAdapt` (a396f40): memory = the smallest size whose warm miss probability
v_w(m) is at most 0.005 (the latency model PRISM's optimiser uses; tolerance fixed in advance, not tuned); capacity
= QuantProv-q90 at that size with the scale-in rule; one parameter tuned by the common rule; memory changes logged.
Tests show it adapts across regimes (1024 MB at 14.5 s, 2048 MB at 12 s) and replays byte for byte as QuantProv
whenever the default size qualifies. Comparison: `scripts/revision/memadapt_compare.py`, outputs in
`docs/revision/memadapt/`.

**Evidence** (7980b69, five traces, stationary weeks, pre-calibration). MemAdapt picks 1024 MB at the default
deadline (where it is QuantProv-q90 exactly) and 2048 MB in every short-slack regime, once per replay. Both it and
PRISM meet 2% in 5/5 weeks at 12-13 s, and PRISM costs more at the validation-selected settings: +27.9% (13 s),
+19.8% (12 s), +8.3% (non-scaling 0.15, 12 s), +4.7% at 11 s (PRISM 0.39 points fewer violating windows); at the
default deadline they tie (+1.6%). Fixed-2048 headroom is a further 6.3-6.6% cheaper at 12-13 s. With test-week
knowledge, as the stored analysis, headroom at 2048 MB is 9.8-27.0% cheaper than PRISM's best (stored: 14-29%).

**Recommendation.** (a) and (b) together. The comparison R2.6 and R7.4 ask for now exists, and its answer decides
the wording: in the regimes tested, the memory benefit comes from choosing a larger size when the deadline tightens,
which a one-line rule does at lower cost than PRISM's joint optimisation. Add MemAdapt (and keep the fixed-size
rows) in Table IX / S14, and narrow the abstract and caption to "memory selection is needed when 1024 MB cannot
meet the deadline; a simple warm-feasibility rule achieves it". Claiming more would need D4(c).

## D2. Published baseline: the hybrid histogram policy of [3] (R3.2)

**Question.** Reviewer 3 asks for a published controller in Table V, for example the hybrid histogram policy of
reference 3. That policy (as commonly cited: Shahrad et al., USENIX ATC 2020; check the reference list) sets
per-application keep-alive and pre-warm windows from a histogram of idle times. It decides when one warm instance
should exist for intermittently invoked functions; it does not size provisioned concurrency. At the paper's load
(about 600 records per minute per stage) a function is never idle for a minute, so a faithful implementation
degenerates to "always warm" and its comparison with PRISM would test nothing.

**Options.**
- (a) Faithful implementation on the fast simulator's on-demand path, with a correctness gate against a published
  characteristic of [3] (for example, its cold-start versus wasted-memory trade-off against a fixed keep-alive),
  tuned by the common rule, in Table V. Releases R3.2 fully. Cost: plan #89-92; the author must first state which
  published figure the implementation has to reproduce, and on which trace (it needs intermittent functions, which
  the synthetic pipeline does not have).
- (b) An adapted variant: the histogram idea applied to concurrency (provision from a histogram of recent
  concurrency, with pre-warm on predicted rises). Cheaper (one policy, a test, the grid), but no published
  characteristic to check it against, so it is our baseline, not [3]'s; R3.2 is partially answered.
- (c) Decline with the argument above, and add a sentence in Section II on why keep-alive policies and provisioned
  concurrency address different regimes. Releases nothing new; R3.2 is answered by argument.

**Built.** Nothing.

**Recommendation.** (c) plus a scoped (b) only if the author wants a published-style baseline in Table V. The
decisive point for (a) is whether [3] contains a characteristic that applies at this load; if it does not, (a)
cannot pass its own correctness gate. Evidence: the paper's workload never leaves a function idle for a minute
(mean 600 executions per minute per stage, Table S1).

## D3. Conformal training split (R4.6, R5.M3)

**Question.** Under the submitted split the forecaster is fitted on days 0-13 and the conformal offset starts at
zero on day 14, so validation is replayed with a cold offset while the test week inherits a warm one; a warm-up on
days before validation is in-sample and leaves the offset near 0.04 (NA-7).

**Options.**
- (a) Keep the submitted split; state the cold-start of the offset in validation and its effect. Releases nothing;
  R4.6 and R5.M3(a) stay open.
- (b) PROVISIONAL split (built, 31b8c50): fit on days 0-10, warm the offset on the out-of-sample days 11-13, then
  validate and test as before. Releases R4.6 and R5.M3(a)-(c) once adopted. Cost: every forecast-driven table moves
  (different training data); the change belongs to the regeneration, not to a patch.
- (c) A longer trace (fit 0-13, warm 14-16, validate 17-23, test 24-30). Keeps the training length; changes the
  generator's 28-day horizon and every scenario's timing. More work than (b).

**Built.** `PrismConfig.forecast_train_days` (default 14, byte-identical), with the existing
`conformal_warmup_days`; `scripts/revision/provisional_split.py`, outputs in `docs/revision/provisional_split/`.

**Evidence** (ccd3649, PROVISIONAL, 20 held-out weeks). The warm-up works: the offset enters validation at
0.22-0.37 (submitted 0), close to its test-start level (0.26-0.46). But validation is then no longer conservative,
the rule picks eps 0.08 (grid edge) on all five traces, and test compliance falls: PRISM 9/20 weeks within 2%,
pooled 2.11% (submitted 12/20, 1.78%); QuantProv-q90 8/20 (11/20); cost -3.0% and -1.7%. The calibration sweep
found the same through the initial offset (dc528db: start at 0.4, PRISM 8/20 weeks). The no-recalibration
ablation does not move (2.97-2.98%, 5-6/20).

**Recommendation.** (b), but only together with a selection rule fixed in advance and checked on unseen seeds
(106-130), for example a validation margin below 2% or two validation weeks. The cold start of the submitted split is
an artefact the reviewers are right to question, and part of the submitted test compliance rested on it. Warming
without changing the rule would replace one problem with a visible compliance shortfall. If the regeneration has
no room for a new rule, (a) with the disclosure above is the honest fallback.

## D4. RQ4: per-stage memory and a within-run change, or narrow RQ4 (R2.7, R4.4)

**Question.** RQ4 claims memory adaptation helps meet tighter deadlines. It is tested only in fixed regimes, with
one memory size shared by every stage (AWS sets memory per function). Reviewer 2 asks for changes during a run
(CPU intensity, memory demand, execution time, initialisation latency); Reviewer 4 asks to narrow RQ4 or test it
with per-stage memory and a within-run change.

**Options.**
- (a) Test. Per-stage memory needs the optimiser to search memory per stage (4^4 = 256 combinations per decision,
  or coordinate search), per-stage memory in both simulators, and a latency table per combination. A within-run
  change needs time-varying latency parameters in the simulators and every family rerun. Plan #97-100 (marked P4,
  "cut first"); several days. Releases R2.7 and R4.4(a).
- (b) Narrow RQ4 and the caption to the fixed regimes and shared memory tested; state the within-run question as a
  limitation. Releases R4.4(a)-(b) and answers R2.7 as a stated limitation.
- (c) Narrow now, and run only the within-run change with the memory-adaptive baseline of D1 as comparator.
  MemAdapt picks its size once per regime from the latency model, so a mid-run change in execution time is exactly
  where an online memory decision could beat it; this is the one test that could support a positive RQ4.

**Built.** MemAdapt (D1); init-direction sweep showing PRISM's memory switching holds under all three directions at
12 s (a4187f7). Nothing for per-stage memory or within-run change.

**Recommendation.** (b) now; (c) only if the author wants to keep a positive RQ4. Evidence: in every fixed regime
tested, MemAdapt meets the target as PRISM does at equal or lower cost (D1: PRISM +8.3% to +27.9% at 12-13 s), so
fixed regimes cannot support RQ4 as stated; a mid-run change of execution time is the remaining case where an
online memory decision could beat a once-per-regime choice, and it has not been run.

## D5. Traffic scope: less structured traces (R2.9)

**Question.** The generator's hourly spikes are known to the forecaster as trigger-minute features
(`trigger_minutes_known`, from `spike_minutes` (0, 1, 30)), which can favour predictive provisioning. Reviewer 2
asks for irregular bursts, unexpected periodicity changes and different predictability.

**Options.**
- (a) Generator extension: spike timing random or drifting and not given to the forecaster; heavier-tailed bursts;
  a diurnal phase or period change inside the test week; all families rerun under the common rule. Plan #94-95,
  about seven hours plus runs. Releases R2.9.
- (b) Minimal version: the existing generator with the trigger-minute features removed (forecaster blind to the
  schedule) plus one scenario with an unannounced change of the spike schedule (the generator already has
  `shifted_spike_minutes`). A few hours; answers the "features favour prediction" point directly; R2.9 partly.
- (c) Rely on the stored Huawei replay (no trigger minutes assumed; PRISM cheaper than static, scheduled and
  reactive there) and state the limitation. Costs and SLA outcomes there are simulated. Releases nothing new.

**Built.** Nothing new. The new-spike and shifted-spike scenarios already test unannounced changes of schedule.

**Recommendation.** (b): it isolates the reviewer's specific concern (encoded features) at a fraction of (a)'s
cost, and (a)'s heavier-tailed bursts can follow if (b) shows the advantage depends on the features.

## D6. AWS campaign: four or five memory sizes

**Question.** The model uses `mem_options = (512, 1024, 2048, 3008)`; the campaign plan lists five sizes including
1536 MB (REPRODUCE.md section 6, decision open).

**Options.**
- (a) Four sizes. The campaign matches the model; one fewer size to deploy and measure (about 20% fewer runs).
- (b) Five sizes, 1536 MB added to the campaign and, if it matters, to `mem_options`. About 25% more measurement
  runs; every memory table gains a column.

**Built.** Nothing; the numbers below come from the latency model (Eq. (3) init scaling, which the campaign will
replace).

**Evidence.** Under the current latency model, 1536 MB is warm-feasible (v_w at most 0.005) where 1024 MB is not, in
three of the six memory regimes: (non-scaling 0.5, 13 s) v_w 0.0007, (0.5, 12 s) 0.0027, (0.15, 12 s) 0.0002. There
it needs 16.7% (non-scaling 0.5) or 6.5% (0.15) fewer GB-seconds per execution than 2048 MB, but its cold-start miss
probability is higher (0.44 against 0.25 at (0.5, 13 s); 0.64 against 0.43 at (0.5, 12 s)), so whether it is cheaper
end to end depends on the cold-start rate. At 11 s it is not warm-feasible (v_w 0.0105). The memory-adaptive rule
of D1 would move to 1536 MB in those three regimes.

**Recommendation.** (b), measure five sizes. RQ4 and D1 are decided in exactly the short-slack regimes where the
missing size would be chosen; a fifth size costs one more deployment in the campaign, against a second campaign
if it turns out to matter after the regeneration.
