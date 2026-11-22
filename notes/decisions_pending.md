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

**Update, 21 Nov 2026 (revision-progress pass): the cited method read, and the scope argument checked.**
Reviewer 3's wording: "2. Published baselines. Section V(C) uses no published controller. Please add, for example,
the hybrid histogram policy of reference 3 to Table V." The manuscript's reference list is not in the repository, so
[3] is still assumed to be Shahrad et al., "Serverless in the Wild", USENIX ATC 2020; the author must confirm it.
What that paper defines (public PDF, read 21 Nov 2026; its text is not stored in the repository):
- Section 4.2: the policy "defines the pre-warming and keep-alive windows for each application", that is, when one
  application image is loaded or unloaded. Idle times (ITs) are tracked in a range-limited histogram with "1-minute
  bins" up to a configurable range ("e.g., 4 hours"); the pre-warming window comes from the 5th percentile of the IT
  distribution (rounded down to a bin) and the keep-alive window from the 99th (rounded up), with a 10% margin.
  When the histogram is not representative (too few ITs, or a coefficient of variation of the bin counts below a
  threshold) it reverts to a standard keep-alive with the window equal to the histogram range; applications with
  many out-of-bound ITs use an ARIMA forecast of the next IT.
- Section 3 and Fig. 5(a): 81% of applications are invoked at most once per minute on average, 45% at most once per
  hour; the policy targets that infrequent tail. Section 5: it is evaluated by simulation on a week of Azure
  Functions invocations, with execution times set to 0, by the cold-start percentage of the 75th-percentile
  application against wasted memory time normalised to a 10-minute fixed keep-alive (for example, the 10-minute
  fixed keep-alive has 2.5x more cold starts at the 75th percentile at the same memory as the 4-hour histogram).
  Nothing in it sizes concurrent instances or provisioned capacity.

Consequence for PRISM's setting. At about 600 executions per minute per stage, every idle time between executions is
far below one minute, so all ITs fall in the first bin; the head and the tail both round to zero, the pre-warming
window is 0 and the keep-alive window is one bin plus the margin, which never elapses: the policy keeps every
stage's image loaded and has no rule for how many instances to keep. A faithful implementation therefore reduces to
"no unloading", which is not a provisioned-capacity controller, and the paper's published characteristic (cold
starts against wasted memory for intermittently invoked applications) cannot be reproduced on PRISM's workload.

Options, revised:
- (c) Scope justification (recommended): viable. The method decides whether an application is loaded, not how many
  concurrent instances to provision; at the loads studied it degenerates to keeping every stage loaded. Text for
  Section II, citing the section numbers above.
- (d) New option: add a published controller that does size concurrency. Reviewer 3 says "for example", so any
  published controller satisfies the wording. Two candidates: (1) the provider's own target-tracking scaling for
  provisioned concurrency. Table V's Reactive already implements a target-tracking rule (policies.Reactive: maximum
  concurrency of the last 5 visible minutes divided by u, immediate scale-out, scale-in after 3 epochs of 5 minutes);
  whether its parameters match AWS's documented target tracking must be checked against the AWS documentation before
  it is presented as the provider's policy (not checked here). (2) An open-source concurrency autoscaler with
  documented defaults (for example Knative's stable and panic windows), implemented from its documentation with a
  test of the documented behaviour; a few hours of work, no published workload characteristic to reproduce.
- (a) and (b) as above. (a) is not viable on this workload for the reason above.

**Recommendation.** (c), plus (d)(1) if the AWS documentation confirms that Reactive matches the provider's target
tracking (then Table V already contains a published, provider-documented controller and the response can say so).
R3.2 would stay open until the text is applied (and, for (d), until the check is made).

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

**Update, 21 Nov 2026 (revision-progress pass): one evidence-backed narrowing, drafted for the author's decision.**
Nothing is decided; the manuscript is not edited. The current RQ4 text is not in the repository, so the locations
below come from the reviewers' citations and must be checked against the manuscript.

*Draft RQ4 (narrowed).* "With one memory size shared by all stages and execution characteristics fixed within a
run, when the default size cannot meet the per-record deadline, does selecting a larger size restore compliance, and
does PRISM's joint online optimisation of capacity and memory do so at lower cost than a rule that selects the
smallest warm-feasible size?"

*Answer the evidence supports* (pre-calibration, fast simulator, assumed constants, five traces, stationary weeks;
`prism-repro/docs/revision/memadapt/`, 7980b69): yes to the first part (PRISM and the warm-feasibility rule MemAdapt
meet the 2% target in 5/5 weeks at 12 and 13 s, where the calibrated-quantile and headroom rules at 1024 MB violate
69-100% of windows in the stored memory regimes, `prism-repro/docs/revision/supplement_tables/pertrace_tables.md`);
no to the second (PRISM costs 8.3% to
27.9% more than MemAdapt at 12-13 s, 4.7% more at 11 s with 0.39 points fewer violating windows, and ties at
14.5 s; fixed-2048 MB headroom is a further 6.3-6.6% cheaper at 12-13 s). Under all three initialisation directions
PRISM still moves to 2048 MB at 12 s (a4187f7).

*What each reviewer allows.*
- Reviewer 4 (R4.4): "Please narrow RQ4 or test it." Narrowing is explicitly accepted. The caption criticism ("goes
  beyond this evidence") needs narrowing either way.
- Reviewer 3 (R3.7): "add a simple memory adaptive baseline or soften the abstract." Both available (MemAdapt built).
- Reviewer 5 (R5.m5(c)): the caption "needs narrowing to the third conclusion"; notes "within-run adaptation was
  untested".
- Reviewer 2 (R2.7): asks to "investigate scenarios where the application workload changes during execution" and
  offers no narrowing alternative. The narrowing answers R2.7 only as a stated limitation, which the reviewer may not
  accept; R2.7 stays open unless D4(c) is run.
- Reviewers 2 and 7 (R2.6, R7.4): ask for the memory-adaptive baseline, which the narrowing presupposes is reported.

*Claims that would change* (locations as the reviewers cite them): RQ4 in Section I; the abstract's memory sentence;
the graphical-abstract caption ("memory adaptation helping satisfy tighter latency targets"); the third conclusion
(p. 17, lines 89-95); Section VI-G and Table IX / S14 (add MemAdapt, keep the fixed-size rows); Table XIII's RQ4 scope
row; and any contribution statement that credits joint online memory optimisation (Reviewer 2 notes the title
emphasises joint concurrency and memory).

*What would remain untested:* per-stage memory sizes (AWS sets memory per function; PRISM shares one size); changes of
CPU intensity, memory demand, execution time or initialisation latency within a run; the memory comparison under the
closed-loop event-level simulator (MemAdapt was run in the fast simulator only, which understates event-level cold
starts about 3x, `prism-repro/docs/revision/kappa_gap/`); the measured initialisation-versus-memory direction (it
moves the 2048 MB advantage; the live run measured only platform start-up, flat at about 0.23 s added latency across
512-2048 MB for a function with no start-up work, `prism-repro/docs/revision/aws_live_followup/`); and a 1536 MB size
(D6).

*Consequence for the tracker if adopted:* R4.4 could close once the narrowed RQ4 and caption are in the manuscript;
R5.m5(c) and R4.10 follow the caption; R3.7 already has its baseline; R2.7 stays Not fixed (limitation only).

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

**Update, 21 Nov 2026 (revision-progress pass): which less-structured traces already exist, and the smallest
defensible comparison.** Reviewer 2's wording: "Please evaluate less structured traffic patterns, irregular bursts,
unexpected periodicity changes, and workloads with different levels of temporal predictability."

*Traces already available (checked read-only; nothing analysed beyond counts):*
- `prism-repro/data/real/huawei_fn*.csv`: five Huawei Private 2023 functions, CC BY 4.0, already replayed post hoc
  (R1, no trigger minutes assumed known). The replay cannot separate the families (on-demand met the target in
  three of five traces), so more of the same traces adds little.
- `additional data/huawei_public_2025/R2_minute_metrics/R2/requests/`: Huawei public 2025 data, Region 2, requests
  per function per minute for 31 days (44,640 minutes, 2,148 functions). 31 functions average at least 60 requests
  per minute and are active in at least 95% of minutes; 11 average at least 600 per minute. These are real,
  unstructured arrival series with no designed spikes. **No licence is stated** in the downloaded README
  (`additional data/README.md`), so derived traces should not be redistributed until the sir-lab terms are checked;
  local analysis is unaffected.
- The generator: the `shifted_triggers` scenario (an unannounced change of the spike schedule in the test week) and
  the forecaster variant `gbm_no_trigger` (trigger-minute features removed) both exist in the code
  (`workload.SCENARIOS`, `experiment.FORECASTERS`); neither has been run for all families. `shifted_triggers` for
  all families is also R5.M4(b).
- SeBS (2020) has no arrival traces.

*Smallest defensible comparison (proposal; not run):*
- Inputs: (i) seeds 101-105, forecaster `gbm_no_trigger`, validation on the stationary week, test on the
  `shifted_triggers` and `stationary` weeks; (ii) ten Huawei Region 2 functions chosen by a rule fixed in advance
  (mean at least 600 requests per minute, active in at least 95% of minutes, 28 consecutive days), thinned
  binomially to a mean of 600 per minute as `data/real/make_csvs.py` does, replayed with the R1 protocol.
- Policies: PRISM, QuantProv-q90, PredHead+S, Reactive, Static, on-demand, tuned by the common rule on
  `experiment.GRIDS_WIDE` (so selections do not sit at the paper's grid edges).
- Metrics: test-week cost, violating windows and weeks within 2%; paired PRISM minus QuantProv-q90 and minus
  Reactive with 95% t intervals (n = 5 synthetic traces; n = 10 real); the forecaster's test-week error per trace as
  the predictability measure, and its rank correlation with PRISM's paired advantage over Reactive (exploratory).
  Labelled post hoc unless prespecified before the run.
- Runtime on this laptop (4 cores): about 75 s of simulation per trace-week for all families on the paper's grid
  (PRISM about 7 s per run, the others under 1 s), so (i) about 20 minutes and (ii) about 30 minutes of compute, plus
  one to two hours to write and test the trace-selection and thinning step. No AWS use.
- What it answers: "less structured traffic" and "different levels of temporal predictability" (the real series),
  and "unexpected periodicity changes" in a limited form (the shifted schedule). Heavier-tailed or clustered
  irregular bursts in the synthetic generator would still need option (a).

**Recommendation (unchanged in substance):** (b), extended with the ten Region 2 traces, which the earlier
recommendation did not have; check the data licence first.

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

## D7. Provisioned-concurrency measurements in us-east-2 (R1.3, R2.8, R2.20, R3.1(b), R4.3, R6.1, R6.2)

Added 21 Nov 2026 (revision-progress pass). **Question.** The earlier plan (manuscript proposal G, D6) assumed a
concurrency quota of 10, under which provisioned concurrency cannot be configured. The live run's preflight recorded
`ConcurrentExecutions = 400` in us-east-2 on 21 Nov 2026 (one reading; the author treats it as the verified quota).
AWS keeps 100 unreserved, so up to 300 can be provisioned there. Activation lag, overflow beyond provisioned
capacity under a burst, and provisioned-concurrency billing become measurable.

**Options.**
- (a) Authorise a provisioned-concurrency campaign in us-east-2. Code first, no AWS: the pipeline kit records P but
  cannot apply it (`aws_pipeline/prism_pipeline/adapter.py` raises NotImplementedError for `pc_mode="apply"`;
  published versions and aliases are not built; its error message cites SPEC.md P7, which is the orchestrator
  decision, not this one). Then measure: time from `PutProvisionedConcurrencyConfig` to READY and to the first warm
  invocation (activation lag, R3.1(b), R4.3, R1.3); a burst above P with the overflow routed on demand (R6.2, R4.3);
  PC charges on the bill (R2.14). Order of magnitude at the manuscript's (non-current) PC price, 4.1667e-6 USD per
  GB-s provisioned: 4 functions x 10 instances x 1 GB for 30 minutes is about USD 0.30 per trial, so a few dollars
  for repeated trials; current prices must be checked before approval.
- (b) Keep the lag simulated (the L = 2, 5, 10 sweep exists) and state that activation lag and overflow are
  unmeasured. Releases nothing.

**Built.** The adapter's record mode, the live harness (`aws_pipeline/`), the measurement harness
(`aws_measurement/`). Nothing that applies provisioned concurrency.

**Recommendation.** (a), because the reason it was ruled out (the quota) no longer holds in us-east-2, and the
activation lag is a parameter Reviewers 1, 3, 4 and 5 all raise (Reviewer 5: "Two platform parameters the
conclusions may depend on are never varied"; the simulated lag sweep now exists, a measured value does not). Confirm
the quota with
a fresh read-only `GetAccountSettings` before planning, and run it only with separate authorisation.

## Decisions recorded 22 Nov 2026 (D2, D4, D5)

These are the author's decisions, recorded as given. The sections above stay as written. All new simulation results
are EXPLORATORY and PRE-CALIBRATION (fast simulator). The confirmatory seeds 106-130 were not used, and
`prism-repro/docs/revision/PRESPECIFICATION.md` is unchanged.

### D4 (R4.4, R2.7): narrow RQ4

**Decision.** RQ4 becomes: "When default memory is insufficient in the fixed workload regimes studied, can increasing
memory restore deadline compliance, and at what cost?"

**Evidence** (`prism-repro/docs/revision/memadapt/summary.txt`, 7980b69; five development traces, stationary weeks,
validation-selected). MemAdapt is the warm-feasibility baseline.

| Regime | Outcome |
|---|---|
| 1024 MB insufficient (12-13 s; non-scaling 0.5 and 0.15) | All 100 settings of the quantile rule at a fixed 1024 MB violate 100% of windows. Moving to 2048 MB restores compliance: PRISM and MemAdapt both meet 2% in 5 of 5 weeks, at 0.00-0.03% violating windows. |
| 13 s, non-scaling 0.5 | MemAdapt matches PRISM's compliance; PRISM costs 27.9% more. |
| 12 s, non-scaling 0.5 | MemAdapt matches PRISM's compliance; PRISM costs 19.8% more. |
| 12 s, non-scaling 0.15 | MemAdapt matches PRISM's compliance; PRISM costs 8.3% more. |
| 11 s | PRISM meets the target in more weeks (5 of 5 against 3 of 5; 1.22% against 1.61%) at 4.7% higher cost. |
| 14.5 s (default deadline) | 1024 MB suffices, and both stay there (PRISM +1.6%, -0.18 points). |

**Denominators** (rechecked 22 Nov 2026 from the saved rows, with the source's aggregation: the mean over five traces of
the per-trace percentage; `prism-repro/docs/revision/memadapt/recheck_denominators_20261122.txt`). "PRISM costs X% more
than MemAdapt" and "MemAdapt costs Y% less than PRISM" differ:

| Regime | PRISM relative to MemAdapt | MemAdapt relative to PRISM |
|---|---|---|
| 13 s, non-scaling 0.5 | +27.9% | -21.8% |
| 12 s, non-scaling 0.5 | +19.8% | -16.5% |
| 12 s, non-scaling 0.15 | +8.3% | -7.7% |
| 11 s, non-scaling 0.5 | +4.7% | -4.3% |

Earlier drafts that said the baseline was "8-28% lower cost than PRISM" used the wrong denominator. Corrected: PRISM
costs 8-28% more, or the baseline costs 8-22% less.

**Cost of the remedy.** MemAdapt at 12-13 s (2048 MB) against MemAdapt at the default deadline (1024 MB, which meets 2%
in only 3 of 5 weeks):
- non-scaling 0.5: +37.6% (USD 1,325 against 965; ratio of the mean costs +37.3%);
- non-scaling 0.15, 12 s: +5.8% (USD 1,019 against 965).

**Untested.**
- Changes in execution characteristics within a run.
- Per-stage memory sizes: PRISM shares one size across the four stages.

**What it settles.**
- R4.4 offers "narrow RQ4 or test it". The decision takes the narrowing option, and the drafts are in
  `notes/manuscript_proposals.md` section I.
- R4.4 stays open until the RQ4, limitation and caption text are in the manuscript, together with R4.4(b), the
  caption.
- R2.7 explicitly asks to "investigate scenarios where the application workload changes during execution". That is an
  experiment, not a scope option, so R2.7 stays open, and its reply states the limitation.

### D5 (R2.9): test less-structured workloads

**Decision.** Run the smallest real-trace comparison now. Plan fixed in advance:
`prism-repro/docs/revision/less_structured_r29_20261122/PLAN.md`.

**What ran.** All nine families, under the R1 protocol, on 10 Huawei Public 2025 Region 2 functions selected by the
fixed rule:
- forecast median APE 4.8-55.8%;
- 99.9th-percentile-to-median ratio 2.3-39.4;
- one trace with 6,512 empty minutes.

**Results** (`prism-repro/docs/revision/less_structured_r29_20261122/README.md`):
- PRISM meets 2% on 7 of 10 traces, the same as QuantProv-q90. Static meets it on 10 of 10.
- No paired cost difference of PRISM against QuantProv-q90, Reactive, Static or PredHead+S excludes zero.
- PRISM's cost relative to Reactive is not associated with forecast error: Spearman -0.03.
- Unexpected periodicity changes: the all-family shifted-trigger check of
  `prism-repro/docs/revision/technical_pass_20261122/shifted_triggers/`.

**Still open.**
- The closed-loop, calibrated version.
- Heavier-tailed synthetic bursts (option a).
- Checking the data licence before any derived trace is redistributed. The derived traces stay local.

### D2 (R3.2): the cited hybrid histogram policy

**Decision.** Verify the method against its source and evaluate it only if a faithful reproduction is feasible.

**Verified** (`prism-repro/docs/revision/hybrid_histogram_r32_20261122/README.md`; source PDF SHA-256 d6f71e84...,
not stored):
- The policy sets per-application pre-warm and keep-alive windows: 1-minute bins, 4-hour range, 5th and 99th
  percentiles, 10% margin, CV threshold 2, ARIMA beyond the range.
- It excludes load-spike cold starts that need new instances ("we do not consider it in this paper").
- It reduces the provider's wasted memory.

**On all 40 workloads studied**, from the check `prism-repro/scripts/revision/hybrid_histogram_check.py`, the policy
gives pre-warm 0 and keep-alive 1.1 minutes, and never unloads the application. It decides nothing about concurrent
instances.

**Blocked.**
- There is no instance-level or concurrency rule to reproduce.
- The customer-bill cost model has no term for the provider's wasted memory.
- The Azure Functions 2019 trace behind the published result is not in the repository.

**Next.** The comparison stays open. Recommended:
- (c), the scope statement in Section II;
- (d)(1), checking Reactive against AWS target tracking, not yet done.

The author must confirm that [3] is this paper. Checked 22 Nov 2026: the submitted manuscript and its bibliography are not in the working tree, in `review-inputs/` or in any Git ref (`v1-submitted`, `main`, `closed-loop`), so the identity of [3] is **unverified**. Nothing here reproduces the published baseline.
