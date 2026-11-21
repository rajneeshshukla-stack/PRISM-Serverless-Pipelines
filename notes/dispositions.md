# Dispositions of the 73 reviewer comments

Branch `phase-e-review`, 21 Nov 2026. One entry per tracker ID, matched to the full wording in
`detailed review comments.txt`. Statuses:

- **Fixed**: all required changes complete and verified; any other request in the row has an evidence-backed rationale.
- **Partially fixed**: at least one substantive request resolved, another open.
- **Not fixed**: substantive work or verification remains and no substantive request is resolved.
- **No change warranted**: fully addressed by a documented rationale, a clarification-only answer or a verified guardrail.

The manuscript was not edited in this pass, so a request whose remedy is manuscript text stays open until the text
is applied (proposals in `notes/manuscript_proposals.md`, cited as P-A1 and so on). Shared work carries the same
status to every ID it serves. Figures and provenance: `notes/number_audit.md` (cited as NA-section). Commits are on
`phase-e-review` unless marked `main`. Pre-calibration means fast simulator, assumed constants, results to be
regenerated. The *Erlang-B relative error* and the *end-to-end integer-search saving* are both 1.92% and unrelated.

<!-- Format, parsed by notes/build_dispositions_xlsx.py: "## <ID> | <status>" then five "- <Field>: <text>" lines. -->

## R1.1 | Not fixed
- Requests: (a) Elaborate on the likely size of SLA violations on AWS Lambda: open. (b) Recommend an operator safety margin: open.
- Changed / rationale: Nothing yet. The margin has to come from closed-loop event-level runs on measured constants, neither of which exists; a margin derived from the open-loop 2.1-4.2x factor would be quoted with false precision.
- Evidence: Open-loop event-level replay gives 2.1-4.2x the fast simulator's violating windows (results/tables/T10_fast_vs_event.md). On current code the submitted configuration misses the weekly target in 8 of 20 held-out fast-simulator weeks (NA-6), so a margin is needed. The eps mapping (637596a) gives an operator rule within the simulator.
- Remaining: Blocker: closed loop (R2.2) and AWS constants. Next: derive the margin from the closed-loop versus fast gap on measured constants (the Phase S safety-margin task; deployment guidance #114-115) and add the guidance subsection (P-D). Pass: a stated margin with its source run, and the eps operator rule from the regenerated rows.
- Suggested response: We agree an operator needs a margin. We now derive it from the closed-loop event-level evaluation run on constants measured on AWS Lambda [margin pending], and we give operators the empirical mapping from the risk budget to weekly compliance so they can choose eps for their target.

## R1.2 | Partially fixed
- Requests: (a) How sensitive are the results to the assumption that initialisation shortens with memory: resolved in simulation, pre-calibration. (b) Would memory co-optimisation still help if initialisation were constant or grew with memory: resolved in simulation, pre-calibration. (c) Ground the direction on measurements: open.
- Changed / rationale: init_scaling option eq3 / constant / inverted / measured (131f024); sweep in the regime where memory matters (a4187f7).
- Evidence: rho at 2048 MB is 0.094 under Eq. (3), 0.196 constant, 0.350 inverted (tests/test_analytic.py::TestInitScalingDirection). At a 12 s deadline PRISM moves to >= 2048 MB in every epoch under all three directions and stays compliant (0.00 / 0.07 / 0.30% violating windows), at 3.4% (constant) and 5.4% (inverted) higher cost; at 13 s eps = 0.02 lets PRISM stay at 1024 MB and ~96% of windows violate under every direction (docs/revision/sensitivity/summary.txt; two traces). External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): three different quantities. (1) Lambda-reported initialisation (SeBS, AWS Lambda us-east-1, November 2020, six benchmarks, 8,165 cold invocations with a reported init duration) is nearly flat with memory: medians 0.01-0.19 s; log-log slopes -0.105 to +0.029 over 512-3008 MB against Eq. (3)'s -0.273. The large-package benchmark 411 is flat (+0.009, interval -0.009 to +0.023). Eq. (3)'s ratio lies inside the interval in 2 of 31 benchmark-memory cells, both day-confounded. The 503 decrease and the Node.js thumbnailer increase do not survive the same-day check. (2) The cold-minus-warm client-time penalty falls with memory in 5 of 6 benchmarks (slopes -0.29 to -0.68, at least as steep as Eq. (3)) and is inconclusive for the Node.js thumbnailer. (3) The {HUAWEI} decreases within the same function in Region 1 (15 functions, median slope -0.45, sign test p = 0.035). It is inconclusive in Region 2 (9 functions) and gives no within-function evidence in Regions 3-5. No AWS source shows initialisation growing with memory, including for the large-package benchmark.
- Remaining: Blocker: AWS init-duration campaign (plan #4, decisive gate #25). Next: fill init_mean_measured, rerun the sweep centred on the measured curve with more traces, report RQ1/RQ3/RQ4. Pass: measured direction stated; sweep table from the regenerated rows. 21 Nov 2026: the external data do not fix a single direction for PRISM. Lambda's reported init phase is close to the 'constant' case, while the whole cold penalty falls with memory at least as steeply as Eq. (3). Which of the two Eq. (3) represents depends on where PRISM's stages do their start-up work. Still to measure on PRISM's own four stages at 512/1024/2048/3008 MB: Init Duration, warm and cold end-to-end times, the cold-minus-warm penalty, and its split into first-invocation execution and environment creation (not separated in the saved analysis). The design and the decision rule for Eq. (3) are in prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md.
- Suggested response: In our simulations, memory co-optimisation still moves to larger memory and keeps compliance when initialisation is constant or grows with memory; the cost of doing so rises by 3-5%. We measured the direction on AWS Lambda [pending] and centre the sweep on it.

## R1.3 | Partially fixed
- Requests: (a) Effect of a longer lag (e.g. 5 minutes) on the predictive component: resolved in simulation, pre-calibration. (b) Would a longer lag need a more conservative calibration offset: resolved in simulation. (c) Grounding on a measured lag: open.
- Changed / rationale: Forecast horizon and conformal delay now follow the lag (be7a912; at L = 10 the old fixed delay would have read the future). Lag sweep L = 2, 5, 10 with every family retuned (a4187f7).
- Evidence: PRISM USD 1,150 / 1,182 / 1,167 per week at L = 2 / 5 / 10, still 24.5-25.8% below Reactive; weeks meeting the target 12 / 11 / 14 of 20. The offset grows on its own: raw upper quantiles scaled by 1.48 / 1.56 / 1.66 (docs/revision/sensitivity/summary.txt). Unexplained: Reactive's compliance improves with longer lag (9 / 13 / 16 weeks).
- Remaining: Blocker: AWS activation-lag campaign. Next: centre the sweep on the measured lag; explain the Reactive trend before citing it. Pass: sweep table on measured constants.
- Suggested response: Yes. With every policy retuned, PRISM's cost at 5 and 10 minutes stayed within 3% of its cost at 2 minutes and about 25% below reactive provisioning in our simulations, and the online recalibration became more conservative by itself (upper quantiles scaled by 1.66 instead of 1.48 at 10 minutes). The measured lag [pending] is the centre of the reported sweep.

## R1.4 | Not fixed
- Requests: (a) Brief discussion of porting the formulation to Azure Functions and Cloud Run: open (manuscript).
- Changed / rationale: Proposal drafted (P-D, R1.4 row). No evidence needed.
- Evidence: The chance constraint, forecaster and recalibration are provider-independent in the code; provider-specific terms are confined to pricing.py and the concurrency semantics of the simulators.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E1, 21 Nov 2026). Blocker: none. Next: add the paragraph in Phase N (plan #113). Pass: paragraph present; consistency gate.
- Suggested response: We added a portability paragraph. The chance constraint, quantile forecast and recalibration carry over unchanged; the cost model and the concurrency semantics (billing granularity, minimum-instance pricing, cold-start behaviour) are what change.

## R2.1 | Not fixed
- Requests: (a) Make the event-level simulation the primary evaluation, or (b) provide a calibrated approximation shown to reproduce its compliance: both open.
- Changed / rationale: Not started; depends on the closed-loop build (R2.2), which converts simulate_events from stage-major to epoch-major and is more than two hours of restructuring, so it was deferred. Exact attainment in the fast simulator (main 1ab053c) removes one fidelity gap but is not the requested remedy.
- Evidence: Fast versus event level, same schedules: PRISM 1.44% -> 3.75% violating windows (T10_fast_vs_event.md). Open-loop telemetry instrumentation and data contract exist (ea84f09).
- Remaining: Blocker: closed-loop build (Phase E). Next: epoch-major simulate_events, wire forecaster, recalibration, cold-hit estimate and decisions; retune all families. Pass: closed-loop smoke and conservation gates, primary table from closed-loop runs.
- Suggested response: We take the first option: the closed-loop event-level simulator becomes the primary evaluation [pending]; the fast simulator remains only as a labelled screening tool.

## R2.2 | Partially fixed
- Requests: (a) Implement the complete PRISM loop in the event-level simulator (forecasts, cold-hit estimates, decisions and calibration respond to telemetry): implemented in simulation, pre-calibration (a2f04b2, b3f191f, d5191dd), and used in the verified exploratory pilot. (b) Evaluate all baselines under the same closed loop: open. The pilot covered four families on three development traces; the confirmatory, calibrated evaluation has not run.
- Changed / rationale: The closed-loop event-level simulator is implemented. simulate_events now runs epoch by epoch with explicit carried state, and its output is unchanged from the stage-by-stage code (a2f04b2; tests/test_des_epoch_major_guard.py). closed_loop.PolicyController (b3f191f) has each policy set epoch k from event-level telemetry up to minute 5k - 2 only, using the per-minute telemetry contract of ea84f09. Forecasts are computed online from observed arrivals, the conformal offset is stepped from observed window peaks, and the cold-hit estimate reads event-level on-demand requests and cold starts. The tests in tests/test_des_closed_loop.py cover no lookahead, conservation across epoch boundaries, a replayed schedule equalling the open loop, and the cold-hit estimate following event-level telemetry. The closed-loop tests were added after the last recorded suite run (prism-repro/docs/TEST_REPORT.md, 95163b2), and no saved run of them exists. Trimming the feature history to whole weeks gives identical outputs and cuts a PRISM week from 232 s to 170 s (d5191dd). The exploratory pilot (script 3e6021d, run at 1f1d771) tuned and evaluated PRISM, QuantProv-q90, Reactive and MemAdapt-q90 under this loop and was verified from its saved output (see Evidence). That resolves (a) in simulation, pre-calibration; (b), every baseline under the same loop in a confirmatory evaluation, remains open.
- Evidence: tests/test_des_online.py::TestEventTelemetry (hand trace with boundary cases; conservation per minute and per window on a boundary-snapped fixture; emitting telemetry leaves results unchanged). Closed-loop pilot verified 21 Nov 2026 from its saved output (Exploratory, pre-calibration, supersedes at recalibration. PRESPECIFICATION.md section 7; development seeds, not a result). Run at commit 1f1d771 on one Windows machine. Design: seeds 101-103, stationary scenario, 14.5 s deadline, one held-out test week per trace. PRISM, QuantProv-q90, Reactive and MemAdapt-q90 were each tuned on the closed-loop validation week by the common rule with the prespecified edge expansion. 125 closed-loop weeks. environment.json, all 12 group files and summary.txt were checked; the selection and edge expansion were replayed from the saved rows, and every policy saw identical request counts per trace and week. Unfavourable first: no comparison attains similar compliance (paired violating-window interval within +/-0.5 points), so every cost comparison is confounded by compliance. Test weeks meeting the 2% target: Reactive 3/3, PRISM 2/3 (trace 103 missed with 16/672 = 2.38%), QuantProv-q90 1/3, MemAdapt-q90 1/3. Paired PRISM minus comparator (95% t interval, df 2): against Reactive, cost -27.3 +/- 6.2% but violating windows +0.79 +/- 0.85 points (more in all three traces); against QuantProv-q90, cost +1.6 +/- 17.0% (neither a difference nor a tie) and violating windows -0.15 +/- 1.28 points. MemAdapt-q90 never left 1024 MB at this deadline, and its outcomes equal QuantProv-q90's in every field. prism-repro/docs/revision/closed_loop_pilot/ (byte copy with SHA-256 list, README, verification.txt).
- Remaining: The closed-loop build is complete; the calibrated evaluation stays open. Blocker: measured constants (calibration) before the confirmatory runs. Pass: every family is retuned and evaluated under the closed loop on seeds 106-130 per PRESPECIFICATION.md (C1-C3) on measured constants, and the closed-loop test suite is run and recorded. The confirmatory runs are estimated at 15-19 h wall clock for the validation-selected design (prism-repro/docs/revision/closed_loop/README.md). Pilot limitations (21 Nov 2026): 3 development traces (df 2, wide intervals); one scenario, one deadline and one test week per trace; assumed constants; one Windows machine. Not covered: the short-slack MemAdapt comparison (C3), the new spike, PredHead+S, and matched-compliance frontiers. Next: the confirmatory C1-C3 on seeds 106-130 under PRESPECIFICATION.md after calibration.
- Suggested response: Implemented as requested [pending]. The event-level simulator now runs epoch by epoch, every policy reads its telemetry, and every baseline is tuned and evaluated under the same loop.

## R2.3 | Partially fixed
- Requests: (a) A window-level risk formulation, or (b) a statistically validated mapping from the per-record budget to the operational target: (b) resolved as a method and validated on stored and current-code rows; final figures open.
- Changed / rationale: scripts/revision/eps_window_mapping.py (637596a): per-eps violating-window rate on validation weeks with the trace as the unit, 95% t-interval and prediction interval, scored on held-out weeks (validation -> test and leave one trace out). (a) is not attempted; (b) is the option the reviewer offers.
- Evidence: Stored E1 rows: monotone (Spearman 1.0), held-out PI coverage 98.3% and 97.5%. Current-code rows: 96.7% and 96.7%, operator rule eps 0.02 (NA-7). Mechanism: at 13 s with eps 0.02, PRISM meets the per-record constraint at 1024 MB (warm miss 1.18%) while ~96% of windows violate, because eps exceeds the 1% per-window allowance (NA-7).
- Remaining: Blocker: regeneration (closed loop, measured constants). Next: rerun the mapping on the regenerated rows; add P-B1. Pass: curve, CI and hold-out coverage from the final rows in the paper.
- Suggested response: We provide the validated mapping. Fitted on validation weeks with the trace as the unit, the violating-window rate rises monotonically with eps, and a 95% prediction interval covered [pending; 96.7-98.3% on pre-regeneration rows] of held-out test weeks. We also state that eps is a tuned parameter: if it exceeds the 1% per-window allowance, the constraint can hold while windows fail.

## R2.4 | Not fixed
- Requests: (a) Which workload conditions and modelling factors make PRISM miss after event-level retuning (Table XI): open. (b) Severity, persistence and the extra provisioning needed: open.
- Changed / rationale: The method exists for the fast simulator: scripts/revision/weekly_compliance.py (5e44a21) lists every held-out week, its windows over the allowance, the selected eps and its validation margin. It has not been run on event-level rows, which is what the comment asks.
- Evidence: Current code, fast simulator: 8 of 20 weeks miss (2.23-3.42%, +2 to +10 windows over 13); all on traces 103-105 where validation chose eps = 0.08, the top of the grid; all interior-eps weeks met the target (NA-6). Association, not cause.
- Remaining: Blocker: closed-loop event-level runs. Next: run weekly_compliance on them, add severity (results/tables/T15_severity.md method), persistence and extra-capacity analysis (plan #66). Pass: per-week table with causes tested, not only associations.
- Suggested response: [pending] We separate weeks that miss narrowly from sustained breaches, report which traces, scenarios and settings they come from, and the extra capacity that would close them. A preliminary fast-simulator analysis already shows the misses cluster where validation selected the largest eps in the grid.

## R2.5 | Partially fixed
- Requests: (a) State the measurable benefit of the optimizer beyond a calibrated upper-quantile rule with the same smoothing: resolved as a narrow, evidenced answer (manuscript text open). (b) Experiments in realistic regimes where the optimizer gives a substantial advantage: resolved as an end-to-end stated null, pre-calibration (no regime tested shows a consistent advantage).
- Changed / rationale: Static benchmarks of the candidate family (main c7360fe, 6cb3eef, 2bdeaba; pinned by bc548e7); level-choice provenance (e95fd8d); stage-specific demand in the fast simulator and the optimiser, guarded byte-identical at unit demand (85d909e, bde7d25); end-to-end runs (066f69c, docs/revision/stage_demand_e2e/).
- Evidence: End to end, 20 held-out weeks per cell, PRISM against QuantProv-q90 at the validation-selected settings: wider eps grid on the paper's workload -1.2 +/- 2.2% (matched compliance -1.0 to -2.3%); above break-even (smooth 6000/min) +11.1 +/- 0.8% (matched +9.0 to +9.9%); break-even 0.30 +4.3 +/- 1.5%, more compliant. Stage-specific demand: 3.1-6.8% cheaper than the phi-aware rule, but against a quantile rule with the same allocation shape -1.9 to -4.3% (filter), +3.3 to +5.4% (fan-out), -0.6 to -2.0% (batch) at matched compliance. Level choice: at most 0.11% of feasible epochs above the smallest for eps up to 0.05, 23.7% at 0.08 (common demand). Static restriction cost 2.71% (16 configurations); end-to-end integer-search saving 1.92% (Linux) with worse compliance in 4 of 6 runs (NA-4).
- Remaining: Blocker: author's framing decision (R4.1). Next: P-A1 to P-A4 with the corrected level-choice wording and the end-to-end null. Pass: text states the null and the conditions tested.
- Suggested response: We tested the optimizer end to end where its reduction to a quantile rule should fail. The reduction does fail there (above the smallest feasible level in most epochs at larger eps, under fan-out and above break-even), but no regime shows a consistent cost advantage over a calibrated quantile rule with the same information: with a wider eps grid the difference is -1.2 +/- 2.2%, above break-even PRISM costs 9-11% more, and under stage-specific demand its 3-7% advantage over the phi-aware rule comes from its candidate family's per-stage allocation, which a quantile rule with the same allocation also captures. We state the benefit accordingly [pending the framing decision, R4.1].

## R2.6 | Partially fixed
- Requests: (a) A competitive baseline that adjusts memory from observed latency or estimated warm-service feasibility: resolved (estimated warm-service feasibility), pre-calibration; its place in the manuscript is the author's decision D1.
- Changed / rationale: policies.MemAdapt, tests and scripts/revision/memadapt_compare.py (a396f40); results (7980b69, docs/revision/memadapt/). Memory: the smallest size whose warm miss probability is at most 0.005, from the latency model PRISM uses, tolerance fixed in advance; capacity: QuantProv-q90 at that size; one parameter tuned by the common rule; memory changes logged. Tests show it adapts across deadlines and is QuantProv byte for byte where 1024 MB qualifies.
- Evidence: Six E4 regimes, seeds 101-105, stationary weeks. MemAdapt picks 2048 MB in every short-slack regime and meets 2% as PRISM does; PRISM costs more at the validation-selected settings: +27.9% (13 s), +19.8% (12 s), +4.7% (11 s, PRISM 0.39 points fewer violating windows), +8.3% (non-scaling 0.15, 12 s); tie at the default deadline (+1.6%). Matched compliance (post hoc): +27.2-27.6%, +19.1-19.5%, -0.6 to +6.8%, +8.3%. Fixed-2048 headroom is a further 6.3-6.6% cheaper at 12-13 s; with test-week knowledge it is 9.8-27.0% cheaper than PRISM's best (stored E4b: 14-29%, two traces).
- Remaining: Blocker: author decision D1 (notes/decisions_pending.md). Next: MemAdapt in Table IX / S14 at the regeneration; narrow the memory claim. Pass: baseline in the comparison and the claim matching it.
- Suggested response: [pending D1] We added a memory-adaptive calibrated-quantile controller: it chooses the smallest memory size at which warm requests meet the deadline, from the same latency model PRISM uses, and provisions by the calibrated q0.9 rule. It adapts as intended (1024 MB at the default deadline, 2048 MB in every short-slack regime). In the regimes we tested it meets the target as PRISM does at 8-28% lower cost at 12-13 s, so we narrowed the memory claim: memory selection is needed when the default size cannot meet the deadline, and a simple warm-feasibility rule achieves it.

## R2.7 | Not fixed
- Requests: (a) Scenarios where execution characteristics change during a run (CPU intensity, memory demand, execution time, initialisation latency): open.
- Changed / rationale: Not run. Options, costs and a recommendation are in notes/decisions_pending.md D4 (5d934d4).
- Evidence: New context from the memory-adaptive baseline (7980b69): in every fixed regime a once-per-regime memory choice meets the target as PRISM does at equal or lower cost, so a mid-run change of execution characteristics is the remaining case in which an online memory decision could show value.
- Remaining: Blocker: author decision D4 (run or narrow). Next: plan #99-100 with MemAdapt as comparator, or narrow RQ4 (R4.4). Pass: results for all families, or a scoped limitation.
- Suggested response: [run: report] or: We did not run mid-run changes of execution characteristics; RQ4 is narrowed to the fixed regimes tested, where a simple memory-selection rule matches PRISM, and we state the limitation.

## R2.8 | Not fixed
- Requests: (a) Measure warm execution times, initialisation delays, activation behaviour and cost on AWS Lambda or a similar platform: open. (b) Calibrate the simulators on them: open.
- Changed / rationale: The parameters are ready to take measured values (init_scaling = measured, init_max_s, lag_min; 131f024, a0a7916, be7a912). No cloud API is called from this repository.
- Evidence: REPRODUCE.md section 6 lists each input and the campaign it waits for. External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): not PRISM's pipeline and not a calibration. Initialisation delays: Lambda-reported init in six 2020 SeBS benchmarks is 0.01-0.18 s at 1024 MB and nearly flat with memory. The cold-minus-warm client-time penalty at 1024 MB is 0.59-1.03 s for five benchmarks and 9.67 s for the large-package one, and falls with memory in 5 of 6. PRISM assumes a 6 s mean initialisation at 1024 MB. The Huawei production provisioning delay (a different process) has function-weighted medians of 0.26-4.61 s at 1024 MB across five regions. Warm execution times, activation behaviour and cost are not in the saved analysis.
- Remaining: Blocker: AWS deployment and campaigns. Next: plan #1-8, #24, #31. Pass: fitted distributions, recalibrated constants, the decisive direction gate. 21 Nov 2026: the external data bound the plausible initialisation range but calibrate nothing. The on-demand campaign at quota 10 (warm and cold timings, Init Duration and the cold-minus-warm penalty per stage and size) is drafted in prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md. Activation behaviour stays blocked under the quota.
- Suggested response: [pending] We deployed the four-stage pipeline on AWS Lambda, measured each quantity and recalibrated the simulators on the measured values.

## R2.9 | Not fixed
- Requests: (a) Evaluate less structured traffic (irregular bursts, unexpected periodicity changes, different predictability): open.
- Changed / rationale: Not run. Options, costs and a recommendation (remove the trigger-minute features and add an unannounced schedule change first) are in notes/decisions_pending.md D5 (5d934d4).
- Evidence: The stored Huawei replay has no trigger minutes assumed known; PRISM was still cheaper than static, scheduled and reactive there (results/tables/R1_real_traces.md), but costs and SLA outcomes are simulated. The generator's spike schedule (minutes 0, 1, 30) is given to the forecaster as features.
- Remaining: Blocker: author decision D5; scope. Next: plan #94-95 or the minimal version. Pass: all families on the new traces.
- Suggested response: [pending] We remove the scheduled-spike features from the forecaster and add traces with unannounced schedule changes and irregular bursts, and report whether the predictive advantage survives.

## R2.10 | Not fixed
- Requests: (a) Keep the distinction that only arrivals are real in the Huawei replay: guardrail. (b) Avoid presenting it as end-to-end validation: open (wording not checked; manuscript not opened).
- Changed / rationale: Proposal drafted (P-D, R2.10 row). No plan task existed; the tracker flags it.
- Evidence: Reviewer 2's own reading: only arrival patterns are real; execution, cold starts, billing and SLA outcomes are simulated.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E2, 21 Nov 2026). Blocker: none. Next: check the abstract, §VI-J and Table XIII wording and apply the proposal. Pass: no sentence calls the replay validation on production workloads.
- Suggested response: We agree and keep the distinction throughout: the Huawei replay uses real arrivals with simulated execution, cold starts, billing and SLA outcomes, and is not presented as end-to-end validation.

## R2.11 | Partially fixed
- Requests: (a) Effect of update rate, clipping bounds, feedback delay and initialisation: resolved (sweep, pre-calibration). (b) Independent calibration per quantile level: resolved, including its cost-compliance effect. Manuscript text open.
- Changed / rationale: PrismConfig.conformal_per_quantile (4702440, default off); feedback delay floored by the lag (be7a912); PrismConfig.conformal_s0 and scripts/revision/calibration_sweep.py (38f0d67); sweep outputs (dc528db, docs/revision/calibration/).
- Evidence: Validation-selected, 20 held-out weeks: clipping never binds (wider bounds give identical runs); update rate and delay move cost -4.2% to +1.4% (weeks meeting 2%: 8-14 of 20); an initial offset of 0.4 makes selection less conservative (PRISM -4.9%, 8/20 weeks; QuantProv-q90 -5.8%, 7/20). Independent offsets: q0.9 coverage 98.0% -> 89.9% (stationary, NA-7); 6.8% / 5.7% cheaper at the selected settings but 6/20 weeks meet 2% (shared: 12/20, 11/20); at matched compliance -1.18% to +0.12% (post hoc). PRISM's selection is at eps 0.08, the grid edge, in 3-5 of 5 traces in every setting.
- Remaining: Blocker: none external. Next: prespecify the calibration (shared or per quantile) before the regeneration; rerun on the reference platform. Pass: text states the sweep and the matched-compliance result.
- Suggested response: The reviewer is right about the shared factor: with it the calibrated q0.9 covered 98% of outcomes in the stationary test weeks; with independent offsets it covers 90% and q0.99 is unchanged. Independent offsets do not improve the cost-compliance trade-off (-1.2% to +0.1% at matched compliance); at the selected settings they are cheaper but meet the target in fewer weeks. Clipping never binds, update rate and feedback delay move cost by -4.2% to +1.4%, and the initial offset matters through validation, where the submitted zero start makes selection conservative (see R4.6).

## R2.12 | Partially fixed
- Requests: (a) Alternative estimators or conditions in which the estimate stays active: resolved (lowering the floor keeps it active). (b) Whether the component is needed under the default configuration: answered by evidence; manuscript text open.
- Changed / rationale: Retuned comparison of floor 0.1 and 0.001 (8d8a816). Retain the 0.1 floor: with eps retuned, the lower floor makes the estimate active but costs more at equal compliance.
- Evidence: Lower floor: mean kappa 0.06 instead of 0.10; cost +2.8 to +3.7% at matched compliance (post hoc), +12.3% with eps selected on validation, target met 20/20 vs 12/20 held-out weeks. The earlier fixed-eps 13-21% saving is superseded (NA-6). Kappa evidence verified 21 Nov 2026 against prism-repro/docs/revision/kappa_gap/ rows. Design: 10 traces (seeds 101-105 x stationary/new_spike), held-out test week, key-3 event draws, 2016 epochs each, PRISM eps 0.02 fixed. The event level replays the fast simulator's own schedule, so every decision is shared. Two quantities, reported separately. (1) Cold-start rate ratio: event-level over fast cold starts per on-demand request (whole week, four stages summed) is 3.23x, the mean of the per-trace ratios (range 2.97-3.59x; 0.0686 against 0.0213). Over stage executions the cold-start ratio is 0.00057 against 0.00020. (2) Kappa-estimate gap (the EWMA of per-epoch cold starts per on-demand request that the 0.1 floor clips): clipped 0.330 against 0.110 on the same schedule (3.00x, 2.40-3.72x) and 0.439 in closed loop (3.99x); unclipped 0.330 against 0.050 (6.98x, 4.34-9.59x) and 9.34x in closed loop (6.05-12.72x). The ratios were derived in prism-repro/docs/revision/closed_loop_pilot/verification.txt. The earlier 20-35x kappa-estimate gap appears in no saved file (PRIOR_EVIDENCE.md was not found). It is unverified and not used here. In the closed-loop pilot (floor 0.1) PRISM's test-week kappa was 0.384-0.442.
- Remaining: Blocker: closed loop (rerun). Next: apply P-B3; rerun in the closed loop. Pass: closed-loop retuned comparison. 21 Nov 2026: the R2.12 floor comparison stays open. The pilot ran only the 0.1 floor, so floor 0.1 against 0.001 has not been retuned in closed loop. Proposal B3 stays on hold until that comparison exists.
- Suggested response: With eps retuned by the common rule, lowering the floor lets the estimate follow the measured ratio but costs 2.8-3.7% more at matched compliance. Under the default configuration the floor acts as a conservative constant that eps tuning compensates for; we say so instead of crediting the adaptive estimate.

## R2.13 | Partially fixed
- Requests: (a) Quantify the solution-quality loss of the one-parameter restriction: resolved (static and end-to-end, distinguished). (b) Compare with a broader integer search: resolved. Manuscript text and in-repository provenance of the end-to-end script: open.
- Changed / rationale: scripts/revision/integer_search_gap.py (main c7360fe, 6cb3eef); end-to-end figures from the author's integer_search_e2e.py (Linux); independent Windows check integer_search_e2e_check.py (50ac42f); anchors pinned (bc548e7).
- Evidence: Static per-epoch gap 2.71% mean over 16 configurations (1.52-5.90%). End-to-end integer-search saving 1.92% mean (1.53-2.66%), Linux only; compliance worse in 4 of 6 runs; two runs cross the 2% target (103 stationary 1.93% -> 2.38%, 103 new spike 1.79% -> 2.08%). A cheaper vector existed in 96.6-99.7% of the epochs with a feasible decision (NA-4).
- Remaining: Blocker: the author's script is not on this machine (checked again 21 Nov 2026: scripts/revision/integer_search_e2e.py absent; not reconstructed). Next: cp ~/Downloads/integer_search_e2e.py prism-repro/scripts/revision/, run it on Windows and Linux, commit outputs; apply P-A3. Pass: committed outputs for both platforms; text as P-A3.
- Suggested response: We ran a broader integer search. As a static benchmark the restriction costs 2.71% per epoch (16 configurations); end to end, refining PRISM's vectors saved 1.92% over six test weeks but raised violating windows in four of them and crossed the 2% target in two, so the per-epoch rule that licenses the cheaper vectors does not carry over fully to window compliance.

## R2.14 | Not fixed
- Requests: (a) A more complete billing implementation (provisioning initialisation, activation timing, recycling, granularity): open. (b) Verify against provider billing records: open.
- Changed / rationale: Not started; the plan orders it after the bill reconciliation.
- Evidence: Stored sensitivity bounds (results/tables/revision/pc_billing_bounds.txt): added-environment charges up to 3.73% for PredHead, 2.15% QuantProv-q99.
- Remaining: Blocker: AWS bill. Next: plan #28-30. Pass: cost model within a stated tolerance of the bill.
- Suggested response: [pending] We implemented the omitted charges and reconciled the model line by line against the AWS bill for the measurement campaign.

## R2.15 | Partially fixed
- Requests: (a) Consolidate the code corrections in one version-controlled implementation: resolved. (b) Rerun the principal comparisons on it: open.
- Changed / rationale: Patch applied on main (33d1000) with four tests; further corrections on main and this branch, each a commit; every new option defaults to the submitted behaviour except the corrections themselves.
- Evidence: git diff v1-submitted -- src/ tests/; KNOWN_ISSUES.md; 89 tests pass in the final run of this pass (Windows 11, Python 3.12.9, pinned; docs/TEST_REPORT.md).
- Remaining: Blocker: AWS constants (one regeneration). Next: plan #38-39 on the reference platform. Pass: every table regenerated from one commit; registry diff against v1-submitted.
- Suggested response: The corrections are consolidated in one version-controlled build. Every table is regenerated from it [pending], with a diff against the submitted numbers that classifies every value that moved.

## R2.16 | Partially fixed
- Requests: (a) Pinned environment, dependency versions, seeds, configuration files and deterministic reproduction instructions: resolved. (b) State which results came from which software version: resolved in the repository; manuscript open. (c) Consistent conditions for all primary experiments: open (regeneration).
- Changed / rationale: requirements.txt pins; byte-identical rerun gate through GBM training (24bb075); REPRODUCE.md (8bf6152, 69d5049, 95163b2); checksum verification fixed for Windows checkouts (efcfd12); Table VI measured under both scikit-learn versions (91a4d8b, R5.M6).
- Evidence: Same machine: two independent runs byte-identical. Across platforms at identical pins, forecast-driven runs differ (PRISM cost up to 4.1%; NA-1 item 2); traces bit-identical. Checksums: fixed verifier flags exactly the changed files on v1-submitted, main and the branch (NA-2).
- Remaining: Blocker: regeneration. Next: regenerate on the reference platform; state the platform with every figure (P-C3). Pass: check_reproducibility 6/6 on the reference platform.
- Suggested response: The environment is pinned, seeds are deterministic and a gate checks byte-identical reruns. We also found that forecast-driven results depend on the platform at identical versions, so every figure is now produced on one reference platform, which we state.

## R2.17 | Partially fixed
- Requests: (a) Discuss what the prototype discrepancy implies for the stability of the conclusions: open (manuscript). (b) Additional independent verification: resolved for the submitted code's level-choice statistic and E1 runs; the outcome is mixed.
- Changed / rationale: Archived-tree reruns and the tie probe (e95fd8d); platform finding (69d5049); Table VI under scikit-learn 1.8.0 and 1.9.1 (91a4d8b): its conclusions hold under both (R5.M6).
- Evidence: Submitted tree: 16 of 40,293 reproduced exactly on Linux / Python 3.13.18 (author's run); 10 of 40,280 on Windows. Not floating-point ties. Non-forecast policies reproduce bit for bit across platforms; forecast-driven ones do not (NA-5, NA-1).
- Remaining: Blocker: none. Next: one paragraph (P-C3); cite the bound for corrected code (P-A2). Pass: paragraph present.
- Suggested response: The prototype cannot be reconstructed and we do not explain the discrepancy away. We verified the present results independently: the published level-choice count reproduces exactly on the reference platform, non-forecast results reproduce on every platform, and forecast-driven results reproduce only on the reference platform, which is why all reported figures come from it.

## R2.18 | Not fixed
- Requests: (a) More independent workload realisations and repeated experiments: open (prepared, not run). (b) Distinguish post hoc from confirmatory findings: open (manuscript and prespecification).
- Changed / rationale: 30 traces fixed a priori (seeds 101-130) with count checksums and a property screen (4c43769); no policy has been run on 106-130.
- Evidence: 9 of 10 trace properties match the original five; one flagged at a 0.1% scale (NA-7).
- Remaining: Blocker: closed loop (the runs should be closed-loop). Next: freeze the prespecification (plan #40) before running; run all families on 30 traces. Pass: primary table on 30 traces with bootstrap CIs; labels on every analysis.
- Suggested response: [pending] We increased to 30 independent traces with recorded seeds and froze the confirmatory comparisons before running them; every analysis is labelled prespecified or post hoc.

## R2.19 | Not fixed
- Requests: (a) Evaluate actual configurations near the SLA targets to validate the interpolated cost differences, especially for Static: open.
- Changed / rationale: Not started; should run on the regenerated code and platform. GRIDS_WIDE (fb8b360) adds points but not near-target refinement.
- Evidence: None new.
- Remaining: Blocker: regeneration. Next: plan #96 (finer grids near the targets, e.g. Static percentiles between 97 and 99.9). Pass: interpolated versus evaluated differences reported.
- Suggested response: [pending] We evaluated real configurations near the targets and report them beside the interpolated values.

## R2.20 | Not fixed
- Requests: (a) Evaluate or estimate telemetry, forecasting integration, API calls, activation delays and memory reconfiguration: open. (b) A small cloud or hardware-in-the-loop test: open.
- Changed / rationale: Not started.
- Evidence: Decision latency 7.4 ms (paper).
- Remaining: Blocker: AWS deployment. Next: plan #114-115. Pass: measured overheads against the 5-minute interval.
- Suggested response: [pending] From the AWS deployment we report telemetry, API-call, activation and reconfiguration overheads against the five-minute decision interval.

## R2.21 | Not fixed
- Requests: (a) Abstract, introduction and conclusion distinguish the formulation from the benefits of calibration and smoothing: open (manuscript). (b) Present PRISM as a simulation-evaluated framework: open (manuscript).
- Changed / rationale: Proposals P-A5, P-A6.
- Evidence: NA-4 and NA-5 support the narrow claim.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md A5, A6 and F, 21 Nov 2026). Blocker: none. Next: apply in Phase N; consistency gate. Pass: claims table matches the text.
- Suggested response: We accept both points. The contribution list separates the formulation, the evaluation protocol and the attribution of robustness to calibration and smoothing, and PRISM is described as a simulation-evaluated framework.

## R2.22 | Not fixed
- Requests: (a) Fix date placeholders, DOI, volume/year and notation formatting: open. (b) Label experiments prespecified, post hoc, corrected or version-specific in text and supplement: open.
- Changed / rationale: Proposal P-D (R2.22 row); KNOWN_ISSUES and REPRODUCE.md label each repository result by code state and platform.
- Evidence: n/a.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E6 and E11, 21 Nov 2026). Blocker: none. Next: editorial pass (plan #124, #110). Pass: checklist complete.
- Suggested response: Corrected, and every analysis now carries one label: prespecified, post hoc, corrected, or version- or platform-specific.

## R3.1 | Not fixed
- Requests: (a) A small real run checking Eq. (3)'s direction against reference [8]: open. (b) Check the 2-minute activation lag: open.
- Changed / rationale: Parameters ready for measured values (init_scaling = measured, lag_min with horizon and delay following it); pre-calibration sensitivity in R1.2 and R1.3.
- Evidence: rho at 2048 MB 0.094 / 0.196 / 0.350 under Eq. (3) / constant / inverted; lag sweep (NA-7). (a) External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): on AWS Lambda (SeBS, 2020) the reported init phase does not follow Eq. (3)'s size of effect: slopes -0.105 to +0.029 against -0.273, with Eq. (3) inside the interval in 2 of 31 cells, both day-confounded. The cold-minus-warm penalty falls with memory in 5 of 6 benchmarks. The Huawei production provisioning delay measures a different process and is mixed across regions: Region 1 decreases within functions, Region 2 is inconclusive, and Regions 3-5 give no within-function evidence. (b) None of these data cover the activation lag.
- Remaining: Blocker: AWS campaigns (plan #4, #6, gate #25). Next: measure, then rerun the sweeps centred on the measurements. Pass: direction gate result stated. 21 Nov 2026: (a) needs PRISM's own stages measured, because the two AWS measures point in different directions (prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md). (b) The lag is blocked: provisioned concurrency cannot be configured under the quota of 10.
- Suggested response: [pending] We measured initialisation per memory size and the activation lag on AWS Lambda; Eq. (3) [stands / is replaced], and the results are reported at the measured values.

## R3.2 | Not fixed
- Requests: (a) Add a published controller, e.g. the hybrid histogram policy of [3], to Table V: open.
- Changed / rationale: Not built. notes/decisions_pending.md D2 (5d934d4) sets out the scope problem: the hybrid histogram policy sets keep-alive and pre-warm windows for intermittently invoked functions, and at the paper's load no function is idle for a minute, so a faithful version has no published characteristic to reproduce here. Options and costs there.
- Evidence: Mean 600 executions per minute per stage (Table S1); none of the synthetic traces leaves a stage idle for a minute.
- Remaining: Blocker: author decision D2 and the author's reading of [3]. Next: plan #89-92 if (a) is chosen. Pass: implementation reproduces a published characteristic, tuned under the common rule, in the main table; or the scope argument in Section II.
- Suggested response: [pending D2] Either: we implemented the hybrid histogram policy of [3], checked it against a published characteristic and added it to Table V. Or: the hybrid histogram policy manages keep-alive for intermittently invoked functions; at the loads we study no function is ever idle, so it reduces to keeping every instance warm, and we explain in Section II why keep-alive policies and provisioned concurrency address different regimes.

## R3.3 | Not fixed
- Requests: (a) A test without the simulator matched to Eq. (14): open (closed-loop event level). (b) Move Table X next to Table V: open (manuscript).
- Changed / rationale: Shares R2.1 and R2.2.
- Evidence: T10_fast_vs_event.md.
- Remaining: Blocker: closed loop. Next: Phase E; move the table (plan #122). Pass: primary evaluation not matched to the controller's load model.
- Suggested response: [pending] The closed-loop event-level simulator, which is not matched to the controller's load model, is the primary evaluation, and the fast-versus-event table sits next to the main results.

## R3.4 | Partially fixed
- Requests: (a) Explain the risk-model choice (Eq. (5) 20-28% off at mean load, Erlang-B within 2.5%): resolved in code (main configuration switched; Eq. (5) kept behind a flag; accuracy gate); explanation text open. (b) Say in the abstract that eps is a tuned knob, not a guarantee: open (manuscript).
- Changed / rationale: main f119bee (switch), e160490 (gate), 012bc3e (guard); values pinned at printed precision (bc548e7).
- Evidence: Event-level overflow 0.118431 at P = c = 40; Erlang-B 0.116156 (Erlang-B relative error 1.92%); Eq. (5) at c_eff 0.144785 (relative error 22.25%) (NA-3).
- Remaining: Blocker: regeneration for the reported results. Next: abstract and §III-C text (P-B1). Pass: abstract states eps is tuned; results from the Erlang-B configuration.
- Suggested response: We now use Erlang-B in the main configuration, keep Eq. (5) behind a flag, and gate the agreement: at the mean load the Erlang-B relative error against the event-level overflow share is 1.92%, while Eq. (5) is 22.25% off. The abstract states that eps is a tuned risk parameter, not a compliance guarantee.

## R3.5 | Partially fixed
- Requests: (a) Use many more traces: open. 30 seeds were fixed a priori (seeds 101-130). The 25 confirmatory traces (seeds 106-130) have not run, and the verified pilot used development seeds 101-103 only. (b) Fix the main comparisons in advance: resolved. PRESPECIFICATION.md was frozen in its own commit (d16fbea, 21 Nov 2026 11:54:54 CST) before the pilot driver (3e6021d) and the pilot run (at 1f1d771).
- Changed / rationale: The trace set is shared with R2.18 (4c43769). The frozen prespecification fixes the following: confirmatory comparisons C1-C3; the tuning rule, grids and edge expansion; the metrics; the difference, tie and similar-compliance criteria; seeds 106-130 as confirmatory and 101-105 as development only. Corrections are allowed only as a dated addendum in a separate commit.
- Evidence: data/trace_set_revision.json: 30 seeds, 101-130, with counts SHA-256. prism-repro/docs/revision/PRESPECIFICATION.md (d16fbea), unchanged through 1f1d771, with no addendum file. The pilot's environment.json records seeds [101, 102, 103] (prism-repro/docs/revision/closed_loop_pilot/). No saved output uses seeds 106-130.
- Remaining: The prespecification is frozen; the calibrated evaluation stays open. Blocker: measured constants (calibration) before the confirmatory runs. Next: run C1-C3 on seeds 106-130 under the frozen file; change it only by a dated addendum. Pass: the prespecification commit precedes the first run on seeds 106-130 (true so far), and primary results are reported on the 25 confirmatory traces.
- Suggested response: [pending] Thirty traces with seeds recorded before any run; the confirmatory comparisons were fixed and timestamped before the production runs.

## R3.6 | Not fixed
- Requests: (a) Rerun all tables with the patched code in one library version: open. (b) Share the code now: open (an outward action for the author).
- Changed / rationale: Repository prepared locally: one corrected build, REPRODUCE.md, a checksum verifier that works on Windows checkouts. Not pushed or released (out of scope).
- Evidence: NA-2; REPRODUCE.md.
- Remaining: Blocker: AWS constants (regeneration); author's release decision. Next: regenerate on the reference platform; release to the editor. Pass: tables regenerated from one commit; repository reachable.
- Suggested response: [pending] Every table is regenerated from one corrected build in one pinned environment on one reference platform, and the repository is available to the reviewers through the editor.

## R3.7 | Partially fixed
- Requests: (a) Add a simple memory-adaptive baseline: resolved (built and compared, pre-calibration). (b) Soften the abstract: open (manuscript; author decision D1).
- Changed / rationale: Shares R2.6 (a396f40, 7980b69) and P-A6 (softening).
- Evidence: As R2.6: the baseline meets the target as PRISM does at 8-28% lower cost at 12-13 s, and ties at the default deadline.
- Remaining: Blocker: author decision D1. Next: P-A6 with the R2.6 evidence. Pass: the baseline in the comparison and the abstract matching it.
- Suggested response: We added a simple memory-adaptive baseline (see R2.6). Because it matches PRISM's compliance at lower cost in the short-slack regimes, we also narrowed the abstract's memory claim to what Table IX supports [pending D1].

## R3.8 | Not fixed
- Requests: (a) Shorten the abstract: open. (b) Align §I with §VII-B: open. (c) Consistent AI disclosure: open. (d) Funding statement: open.
- Changed / rationale: Proposal P-D (R3.8 rows). Conflict with R5.M7, which adds qualifiers: keep only figures that survive.
- Evidence: Reviewer 4 counts ten numbers and three post hoc labels in the abstract.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E6, 21 Nov 2026). Blocker: none. Next: Phase N (plan #106, #111, #124). Pass: all four done.
- Suggested response: All four done: the abstract is rewritten against the claims table and shortened, §I matches §VII-B, the AI-use disclosure is consistent and a funding statement is added.

## R4.1 | Partially fixed
- Requests: (a) State what PRISM reduces to at the default deadline: answer established by evidence, with its eps range (corrected); manuscript text open (P-A1). (b) Test the optimizer where the reduction fails (stage-specific demand; utilisation above break-even with a wider eps grid), or present PRISM as one rule among the families and adjust title and contributions: both tests run end to end (stated null); framing decision open.
- Changed / rationale: Stage-demand probe (main 2bdeaba), integer search (main c7360fe), anchors (bc548e7); stage-specific demand end to end and the above-break-even regimes (85d909e, bde7d25, 066f69c).
- Evidence: Reduction at the submitted run's eps (0.02-0.05): 16 of 40,293 above smallest (submitted, Linux), at most 0.11% for current code. It fails at eps 0.08 (23.7%) and above (72-100% at 0.10-0.20); current code's validation selects 0.08 for three traces (14.7% of feasible epochs at its selections). End to end: no consistent advantage (R2.5); above break-even PRISM is 9-11% costlier. The static fan-out infeasibility (kappa 0.35, NA-4) does not carry over end to end: feasible in 96.7-100% of epochs, 19/20 weeks within 2%.
- Remaining: Blocker: author's framing decision. Next: decide with this evidence, which no longer supports the first branch (a regime where the optimizer pays); title and contributions follow; P-A1 and P-A2 with the corrected wording. Pass: decision written; title and contributions follow it.
- Suggested response: The reduction is correct at the risk budgets the paper selected, and we now state it in Section IV with its range: at larger eps the optimizer does choose above the smallest feasible level. We ran both suggested tests end to end. Neither shows a consistent advantage over a calibrated quantile rule with the same information and allocation: with a wider eps grid the difference is within +/- 2.2%, above break-even PRISM costs 9-11% more, and under stage-specific demand its 3-7% advantage over the phi-aware rule comes from its candidate family's allocation. We therefore [present PRISM as one calibrated rule among the families and adjust the title and contributions: author decision].

## R4.2 | Not fixed
- Requests: (a) A closed-loop event-level simulation with exact attainment as the primary evaluation: open.
- Changed / rationale: Shares R2.2. Exact attainment exists in the fast simulator (main 1ab053c) and is inherent in the event-level simulator; the closed loop is the open part.
- Evidence: ea84f09 (instrumentation only).
- Remaining: Blocker: closed-loop build. Next: Phase E. Pass: as R2.2.
- Suggested response: [pending] Done as asked: the closed-loop event-level simulator, which computes every request's latency and so attainment exactly, is the primary evaluation.

## R4.3 | Partially fixed
- Requests: (a) Ground the constants on the platform (initialisation per memory size, activation time, overflow under a burst): open. (b) Run L = 5 and 10 minutes: resolved, pre-calibration.
- Changed / rationale: be7a912 (horizon and delay follow the lag), a4187f7 (sweep).
- Evidence: PRISM cost +2.8% (L = 5) and +1.5% (L = 10) against L = 2, 24.5-25.8% below Reactive; 11 and 14 of 20 weeks met (NA-7). The 6 s mean initialisation is an assumption; with init at 3 s on-demand already meets the target (paper, Section S5). (a) External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): initialisation per memory size from six 2020 AWS benchmarks. Lambda-reported init is 0.01-0.19 s at every size. The cold-minus-warm penalty at 1024 MB is 0.59-1.03 s for five benchmarks and 9.67 s for the large-package one. The assumed 6 s mean is far above the reported init phase and within the cold penalty only for the large-package benchmark. The Huawei provisioning delay (a different process, different platform) has function-weighted medians of 0.26-4.61 s at 1024 MB by region. Activation time and overflow under a burst are not covered.
- Remaining: Blocker: AWS campaigns. Next: measure; recentre. Pass: constants from measurements; sweep around the measured lag. 21 Nov 2026: initialisation per size for PRISM's own stages, per prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md (on demand, quota 10). Activation time and burst overflow are separate measurements, both blocked under the quota.
- Suggested response: We ran L = 5 and 10 minutes with every family retuned: PRISM's cost moved by under 3% and stayed about 25% below reactive provisioning in our simulations. The constants are now measured on AWS Lambda [pending], and the sweep is centred on the measured lag.

## R4.4 | Not fixed
- Requests: (a) Narrow RQ4, or test it with per-stage memory and a within-run change: open (author decision D4). (b) Narrow the graphical-abstract caption: open (manuscript).
- Changed / rationale: P-A6 (caption), P-D (RQ4); options and costs in notes/decisions_pending.md D4 (5d934d4). Per-stage memory and mid-run change are P4, not built.
- Evidence: Memory-adaptive baseline (7980b69): in every short-slack regime a once-per-regime memory choice meets the target as PRISM does at equal or lower cost (PRISM +8.3% to +27.9% at 12-13 s); fixed-2048 headroom cheaper still. PRISM's memory switching holds under all three init directions at 12 s (a4187f7).
- Remaining: Blocker: author decision D4 (test or narrow). Next: P-A6 and narrow RQ4, or plan #97-100. Pass: RQ4 matches the evidence.
- Suggested response: We accept the caption criticism and narrowed it. RQ4 is narrowed to the fixed regimes tested, where a simple memory-selection rule meets the target at lower cost than PRISM [or: per-stage memory and within-run change are tested, pending D4].

## R4.5 | Not fixed
- Requests: (a) Name a pipeline with per-record deadlines: open (manuscript).
- Changed / rationale: P-D (R4.5 row).
- Evidence: AWS guidance that asynchronous pipelines rarely need provisioned concurrency (reviewer's point).
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E8, 21 Nov 2026). Blocker: none. Next: plan #117. Pass: named use case in §I.
- Suggested response: Added to the motivation: [named synchronous or interactive pipeline in which each record carries its own deadline].

## R4.6 | Partially fixed
- Requests: (a) Warm the conformal offset before validation: resolved as a PROVISIONAL split (built and evaluated); adoption is the author's decision D3.
- Changed / rationale: PrismConfig.conformal_warmup_days (92d304c) and PrismConfig.forecast_train_days (31b8c50, default 14 byte-identical); scripts/revision/provisional_split.py and results (ccd3649, docs/revision/provisional_split/).
- Evidence: Fit on days 0-10, warm on the out-of-sample days 11-13: the offset enters validation at 0.22-0.37 (submitted: 0), close to its level at the start of the test week (0.26-0.46). Side effect: validation is no longer conservative, the rule selects eps 0.08 (grid edge) on all five traces, and PRISM meets 2% in 9/20 test weeks with a pooled 2.11% (submitted: 12/20, 1.78%). The in-sample warm-up of the submitted split leaves the offset near 0.04 (NA-7).
- Remaining: Blocker: author decision D3. Next: adopt the warm-up at the regeneration together with a selection rule fixed in advance and checked on unseen seeds 106-130. Pass: offset warm at validation start; retuned selections and their test compliance reported.
- Suggested response: [pending D3] We now warm the offset on held-out days before the validation week, so validation starts from the offset level the test week sees. This removed a conservatism in the submitted selection, and with the same selection rule test compliance fell; we therefore [adopted a prespecified selection rule, validated on unseen traces / report the effect].

## R4.7 | Not fixed
- Requests: (a) Acknowledge that the real-trace replay cannot separate the families: open (manuscript). (b) Widen the grids whose edges were selected (PRISM and headroom at edges in four of five traces): the observation is verified and widened grids are defined, but no run uses them, so open.
- Changed / rationale: Grid-edge audit and GRIDS_WIDE (fb8b360); existing GRIDS unchanged so stored and existing runs are unaffected.
- Evidence: R1 replay: 25 of 40 selections at an edge, including PRISM at eps 0.08 and headroom at h 1.0 in four of five traces, as stated (NA-7).
- Remaining: Blocker: regeneration. Next: rerun the replay on GRIDS_WIDE and re-audit. Pass: no selection at an edge, or the limit stated.
- Suggested response: We confirm the observation with an audit of every selection, widen every grid whose edge was selected [results pending], and describe the replay as unable to separate the families.

## R4.8 | Partially fixed
- Requests: (a) Remove the about 3% of 1024 MB initialisations above the 10 s limit: resolved in code (truncation with a gate), not yet enabled in the main configuration.
- Changed / rationale: PipelineConfig.init_max_s truncates the log-normal at the cap with common random numbers kept (a0a7916). Default None until the measured init distribution is fitted, since the fit may replace the log-normal and the switch moves every risk table; enabling it earlier would mean regenerating twice.
- Evidence: Gate: no draw above 10 s at 512-3008 MB; closed-form truncated mean and CDF; cited shares 3.20% (1024 MB) and 16.40% (512 MB) under the submitted model (tests/test_analytic.py::TestTruncatedInit; NA-3). With the cap rho(1024) 0.531 -> 0.515.
- Remaining: Blocker: AWS init fit. Next: set init_max_s = 10.0 (or the measured form) at the regeneration. Pass: P(init > 10 s) = 0 in the configuration that produces the reported results.
- Suggested response: Corrected: initialisation times are truncated at the 10 s limit at every memory size (the submitted model also put 16.4% of 512 MB draws above it). The reported results use the truncated, measured distribution [pending].

## R4.9 | Partially fixed
- Requests: (a) Make the main configuration consistent with §S6's recommendation of Erlang-B: resolved in code; regenerated results and text open.
- Changed / rationale: Shares R3.4 (main f119bee, e160490).
- Evidence: Erlang-B relative error 1.92% against the event-level overflow share; Eq. (5) 22.25% (NA-3).
- Remaining: Blocker: regeneration. Next: report the Erlang-B configuration's results. Pass: every reported table from the Erlang-B configuration.
- Suggested response: The main configuration now uses Erlang-B, as §S6 recommends, with Eq. (5) behind a flag and its 22.25% gap at mean load recorded.

## R4.10 | Not fixed
- Requests: (a) Show smoothed headroom (3.24%) next to the 6.67% in the graphical abstract: open.
- Changed / rationale: P-D (R5.m5, R4.10 row).
- Evidence: New spike: PRISM 1.55%, PredHead+S 3.24%, PredHead 6.67% (results/tables/T5_test_weeks.md).
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E9, 21 Nov 2026). Blocker: none (values refresh after the regeneration). Next: plan #116. Pass: redrawn figure.
- Suggested response: Redrawn with smoothed headroom shown beside the unsmoothed comparator.

## R4.11 | Not fixed
- Requests: (a) Move prototype, commit and library-version prose from §V-E and §S1 to the repository: open (the repository already held PROVENANCE.md and KNOWN_ISSUES.md before this revision; REPRODUCE.md now adds which code and platform produced what; the prose is still in the paper). (b) One primary evaluation, one main results table and a separate exploratory section (Reviewer 4, Q3; tracked with R2.22): open.
- Changed / rationale: REPRODUCE.md (8bf6152, 69d5049, 95163b2) records which code and platform produced what; KNOWN_ISSUES.md holds the defect audit.
- Evidence: n/a.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E10 (part a), 21 Nov 2026). Blocker: none for (a); closed loop for (b). Next: plan #125 and #102. Pass: §V-E and §S1 keep only validity-relevant provenance; structure fixed.
- Suggested response: Moved: the paper keeps only what bears on validity, and the commit, version and defect history is in the repository. The evaluation is restructured into one primary evaluation, one main table and an exploratory section [pending].

## R5.M1 | Partially fixed
- Requests: (a) Closed-loop event-level simulator as the main evaluator: open. (b) Retune every family under it on full grids: open. (c) Exact attainment in the fast simulator: resolved. (d) Report the net direction of the sampling misclassification: resolved. (e) Narrower option, closed-loop runs for Reactive, PRISM, QuantProv-q90 and PredHead+S under the new spike: open. (f) Abstract and conclusions say the fast simulator matches the controller's load model by design: open (P-C1).
- Changed / rationale: Exact attainment by cold-start-pattern weighting (main 1ab053c); flip direction (main e3faa6c); closed-loop instrumentation only (ea84f09).
- Evidence: The direction depends on the simulator, as reported in the author's session record and not re-verified here: at event level the 100-request sample understated violations (computed by des.sampling_flip_direction, main e3faa6c); in the fast simulator exact attainment found fewer violations in 8 of 10 runs (main 1ab053c). Fast versus event: PRISM 1.44% -> 3.75% on the same schedules (T10_fast_vs_event.md). Closed-loop pilot verified 21 Nov 2026 from its saved output (Exploratory, pre-calibration, supersedes at recalibration. PRESPECIFICATION.md section 7; development seeds, not a result). Run at commit 1f1d771 on one Windows machine. Design: seeds 101-103, stationary scenario, 14.5 s deadline, one held-out test week per trace. PRISM, QuantProv-q90, Reactive and MemAdapt-q90 were each tuned on the closed-loop validation week by the common rule with the prespecified edge expansion. 125 closed-loop weeks. environment.json, all 12 group files and summary.txt were checked; the selection and edge expansion were replayed from the saved rows, and every policy saw identical request counts per trace and week. Unfavourable first: no comparison attains similar compliance (paired violating-window interval within +/-0.5 points), so every cost comparison is confounded by compliance. Test weeks meeting the 2% target: Reactive 3/3, PRISM 2/3 (trace 103 missed with 16/672 = 2.38%), QuantProv-q90 1/3, MemAdapt-q90 1/3. Paired PRISM minus comparator (95% t interval, df 2): against Reactive, cost -27.3 +/- 6.2% but violating windows +0.79 +/- 0.85 points (more in all three traces); against QuantProv-q90, cost +1.6 +/- 17.0% (neither a difference nor a tie) and violating windows -0.15 +/- 1.28 points. MemAdapt-q90 never left 1024 MB at this deadline, and its outcomes equal QuantProv-q90's in every field. prism-repro/docs/revision/closed_loop_pilot/ (byte copy with SHA-256 list, README, verification.txt). For (b), four families were retuned on the paper grids under the closed loop (exploratory, three traces). For (e), the pilot is stationary only.
- Remaining: Blocker: closed-loop build. Next: Phase E, or the narrower option first. Pass: closed-loop runs; text per P-C1. Pilot limitations (21 Nov 2026): 3 development traces (df 2, wide intervals); one scenario, one deadline and one test week per trace; assumed constants; one Windows machine. Not covered: the short-slack MemAdapt comparison (C3), the new spike, PredHead+S, and matched-compliance frontiers. Next: the confirmatory C1-C3 on seeds 106-130 under PRESPECIFICATION.md after calibration. (e) still needs the new-spike closed-loop runs, including PredHead+S.
- Suggested response: Exact attainment replaces the 100-request sample, and we report the direction of the old error: it depends on the simulator. [pending] The closed-loop event-level simulator is the main evaluator, with every family retuned under it, and the abstract states that the fast simulator matches the controller's load model by design.

## R5.M2 | Partially fixed
- Requests: (a) Runs with longer lags (5 and 10 minutes): resolved, pre-calibration. (b) Runs with initialisation constant or growing with memory: resolved, pre-calibration (two traces). (c) Effect on RQ1, RQ3 and RQ4: partly (cost and weekly compliance per lag; memory choice and cost per init direction; RQ3's matched-compliance comparison not rerun). (d) Otherwise limit the conclusions: not needed if (a)-(c) are reported.
- Changed / rationale: be7a912, 131f024, a4187f7.
- Evidence: Lag: PRISM cost within 3% of L = 2 and 24.5-25.8% below Reactive at all three lags; offset scale 1.48 -> 1.66. Init: at 12 s PRISM switches to >= 2048 MB and stays compliant under every direction, +3.4% / +5.4% cost (NA-7). (b) External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): no AWS source shows initialisation growing with memory. Lambda-reported init is nearly flat (closest to the 'constant' case), and the cold-minus-warm penalty falls with memory in 5 of 6 benchmarks, at least as steeply as Eq. (3). The Huawei production provisioning delay is mixed across regions. This bears on which of the init directions already run is realistic; the dispositions of (a)-(d) are unchanged.
- Remaining: Blocker: AWS (measured centre). Next: RQ3 matched-compliance per lag and direction; more traces for the init runs; centre on measured values. Pass: sweep tables on measured constants. 21 Nov 2026: centre the init sweep on PRISM's measured stages (prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md). Until then, report the 'constant' and Eq. (3) cases side by side. The lag centre stays unmeasured, blocked under the quota.
- Suggested response: We added both. [pre-calibration figures above; final values pending] The predictive advantage survives longer lags in our simulations, the recalibration grows more conservative on its own, and memory co-optimisation still switches to larger memory when initialisation does not shorten with memory, at 3-5% higher cost.

## R5.M3 | Partially fixed
- Requests: (a) Warm the offset before validation: resolved as a PROVISIONAL split (shares R4.6). (b) Retune the no-recalibration ablation: resolved under both splits. (c) Report each selected setting's validation-week results beside its test results: resolved (one table, both splits). Adoption of the split is the author's decision D3.
- Changed / rationale: As R4.6 (31b8c50, ccd3649).
- Evidence: Validation beside test, mean over traces (docs/revision/provisional_split/summary.txt has every trace and setting). Submitted: PRISM validation 1.58% / test 1.78% (12/20 weeks), QuantProv-q90 1.79% / 1.95% (11/20), no recalibration 1.88% / 2.98% (5/20). PROVISIONAL: PRISM 1.55% / 2.11% (9/20), QuantProv-q90 1.64% / 2.23% (8/20), no recalibration 1.85% / 2.97% (6/20).
- Remaining: Blocker: author decision D3. Next: as R4.6; then the same table from the regeneration. Pass: the three items in one table from the adopted split.
- Suggested response: [pending D3] The offset is warmed before validation; PRISM, QuantProv-q90 and the no-recalibration ablation are retuned under the warm start; and each selected setting's validation-week result is reported beside its test-week results. The ablation's test compliance is the same under both splits (about 3% of windows), so recalibration, not the split, is what keeps PRISM near target.

## R5.M4 | Not fixed
- Requests: (a) Run more traces: open (30 prepared). (b) All families under the shifted-trigger scenario: open. (c) Widen every grid whose edge is selected: open (audit done, GRIDS_WIDE defined, no run). (d) Narrower option, state the limits in the abstract: open.
- Changed / rationale: Grid-edge audit (fb8b360); trace set (4c43769). Caution from the weekly-compliance analysis: all eight held-out misses of the submitted configuration on current code occur where validation chose eps = 0.08, the top of the grid; widening the grid lets validation choose larger eps there, which may raise weekly misses. A prespecified selection rule validated on unseen seeds should accompany the widening.
- Evidence: Edges: E12 6 of 30, R1 25 of 40, E1 test-week post hoc 23 of 160 (PredHead at h 2.0 under the new spike in all five traces, as stated); weekly misses NA-6.
- Remaining: Blocker: closed loop. Next: prespecify the rule, run 30 traces, shifted trigger for all families, GRIDS_WIDE; re-audit. Pass: interior selections and weekly compliance reported on unseen seeds.
- Suggested response: [pending] We ran 30 traces, evaluated every family under shifted triggers and widened every grid whose edge was selected; no selected configuration sits at an edge, and weekly compliance is reported for each.

## R5.M5 | Partially fixed
- Requests: (a) Rank infeasible candidates by their violation quantile: resolved. (b) State in the conclusions that the chance constraint acted on capacity as a tuned quantile rule: open (P-A1, P-B1).
- Changed / rationale: main 44ef122 (ranking), 8e6f60c (eps-monotonicity evidence test). Retain the kappa floor of 0.1: the reviewer suggests the floor, not the measured ratio, may exclude the 1024 MB no-provisioning option; with eps retuned, lowering the floor costs 2.8-3.7% more at matched compliance (R2.12), so the floor is kept and described as a conservative constant.
- Evidence: Retuned floor comparison NA-6. The eps-above-warm-miss condition: at 13 s, eps 0.02 lets PRISM keep 1024 MB with a 1.18% warm miss rate and ~96% of windows violate (NA-7).
- Remaining: Blocker: none. Next: text per P-A1 and P-B1. Pass: conclusions state it.
- Suggested response: We accept the analysis. Infeasible candidates are now ranked by their violation quantile, and the conclusions state that the chance constraint acted on capacity as a tuned quantile rule. On the floor: with eps retuned, lowering it made the estimate active but raised cost at equal compliance, so we keep it and describe it as a conservative constant.

## R5.M6 | Partially fixed
- Requests: (a) Make the code available to the reviewers through the editor: open (author's outward action). (b) Report the Table VI differences under both scikit-learn versions: resolved on one Windows machine; the reference-platform rerun is open.
- Changed / rationale: scripts/revision/table6_versions.py and its outputs (91a4d8b): Table VI in two environments identical except scikit-learn (1.8.0, 1.9.1), side by side. Earlier finding stands: forecast-driven results also depend on the platform at identical versions (PRISM cost up to 4.1%), while non-forecast results reproduce bit for bit.
- Evidence: 3 of 20 validation selections change; single-run violating-window rates move by at most 0.74 points and cost by at most 8.4%. PRISM vs QuantProv-q90 cost, 1.8.0 -> 1.9.1: stationary +1.6 +/- 2.3 -> +0.2 +/- 2.9%, growth +1.3 +/- 2.2 -> -0.2 +/- 2.9%, bursty +0.0 +/- 3.5 -> -1.5 +/- 3.0%, new spike -0.1 +/- 3.1 -> -1.3 +/- 2.9%; every interval includes zero in both. PRISM stays 2.9-21.0% costlier than PredHead and PredHead+S with fewer violating windows in both (docs/revision/table6_versions/comparison.txt; Windows, Python 3.12.9, current code). NA-1 item 2 for the platform effect.
- Remaining: Blocker: release decision (author). Next: rerun table6_versions.py on the reference platform at the regeneration; release the repository through the editor. Pass: both columns from the reference platform; repository reachable.
- Suggested response: The repository is available through the editor [pending release]. Under scikit-learn 1.8.0 and 1.9.1, three of twenty validation selections change and single-run violating-window rates move by at most 0.74 points; every conclusion of Table VI holds under both (the PRISM-QuantProv-q90 cost differences shift by 1.3-1.5 points and all intervals include zero). We also report that forecast-driven results reproduce exactly only on the reference platform, which is where every reported figure comes from.

## R5.M7 | Not fixed
- Requests: (a) Label the 13-29% saving as pooled with per-trace ranges: open. (b) Label "within 1.6%" as pooled, with per-scenario spreads: open. (c) Report the Huawei and synthetic orderings separately: open. (d) Say all paired cost intervals against QuantProv-q90 include zero: open. (e) Say which orderings held: open. (f) Rename the "calibrated-90%-quantile rule": open.
- Changed / rationale: Proposals P-A6 (all six) and P-B2.
- Evidence: Figures as quoted by the reviewer; to be re-derived after the regeneration.
- Remaining: Blocker: regeneration for the final values. Next: Phase N with the claims-to-evidence map. Pass: every pooled figure labelled.
- Suggested response: Every point accepted: pooled figures are labelled pooled with their per-trace and per-scenario ranges, the orderings that did not hold are named, intervals that include zero are reported as such, and the rule is renamed.

## R5.m1 | Not fixed
- Requests: (a) Limit "Much of the benefit credited to uncertainty-aware controllers can thus come from two inexpensive ingredients" (p. 2, l. 91-93) to the setting studied: open.
- Changed / rationale: P-A6 row.
- Evidence: n/a.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E7, 21 Nov 2026). Blocker: none. Next: plan #111. Pass: sentence scoped.
- Suggested response: Limited to the simulated pipeline studied.

## R5.m2 | Not fixed
- Requests: (a) New symbols for one meaning each of tau and s (Table II): open.
- Changed / rationale: P-D row.
- Evidence: n/a.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E3, 21 Nov 2026). Blocker: none. Next: plan #118, paper and supplement. Pass: no symbol with two meanings.
- Suggested response: Resolved, with the new symbols used consistently in the paper and the supplement.

## R5.m3 | Not fixed
- Requests: (a) Cite Table IV, not Fig. S2b, for the five-trace means (p. 10, l. 61-63): open.
- Changed / rationale: P-D row.
- Evidence: The reviewer notes Fig. S2b's trace-101 caption gives the reverse ordering.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E4, 21 Nov 2026). Blocker: none. Next: plan #119. Pass: citation corrected.
- Suggested response: Corrected to Table IV.

## R5.m4 | Not fixed
- Requests: (a) Supplementary tables for the per-trace ablation (p. 12, l. 40-43) and the QuantProv memory results (p. 16, l. 33-48): open.
- Changed / rationale: P-D row. The stored outputs exist (results/raw/E3, results/raw/R2), and the values change at the regeneration.
- Evidence: n/a.
- Remaining: Blocker: regeneration for final values. Next: plan #120. Pass: both tables in the supplement.
- Suggested response: Both tables are added to the supplement.

## R5.m5 | Not fixed
- Requests: (a) Show smoothed headroom (3.24%) in the graphical abstract: open. (b) Match the image title to the article title: open. (c) Narrow the caption's memory claim to the third conclusion: open.
- Changed / rationale: P-A6 and P-D rows (shared with R4.10 and R4.4).
- Evidence: T5_test_weeks.md (1.55%, 3.24%, 6.67%); stored E4b (14-29%).
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E9, 21 Nov 2026). Blocker: none. Next: plan #116, #109. Pass: redrawn figure and caption.
- Suggested response: Redrawn with smoothed headroom shown, the image title matched to the article title, and the caption narrowed to the demonstrated claim.

## R5.R | Not fixed
- Requests: (a) Add pages to [5] (1281-1297) and [19] (1-8): open. (b) Update the dead URL of [41]: open.
- Changed / rationale: P-D row; full reference audit planned.
- Evidence: n/a.
- Remaining: Text prepared, not applied (notes/manuscript_proposals.md E5, 21 Nov 2026). Blocker: none. Next: plan #121. Pass: three entries corrected; list audited.
- Suggested response: All three corrected, and the full reference list audited against IEEE style.

## R6.1 | Not fixed
- Requests: (a) Validate PRISM on a real FaaS platform with an end-to-end four-stage pipeline: open.
- Changed / rationale: Shares R2.8. No cloud API is called from this repository.
- Evidence: REPRODUCE.md section 6.
- Remaining: Blocker: AWS. Next: plan #1-2. Pass: deployed pipeline and measurements.
- Suggested response: [pending] We deployed the four-stage pipeline on AWS Lambda. The deployment grounds the constants; the evaluation itself remains simulation-based, and we say so.

## R6.2 | Not fixed
- Requests: (a) Measure cold starts, activation lag, concurrency, service times and billing: open.
- Changed / rationale: Shares R2.8, R2.14, R4.3.
- Evidence: Parameters ready for measured values (R2.8). External data, 21 Nov 2026 (exploratory, post hoc, historical external data; not a PRISM measurement; prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/RESULTS.md): cold starts only. Lambda-reported initialisation and the cold-minus-warm penalty for six 2020 AWS benchmarks are in R1.2. Production provisioning delays come from Huawei (five regions, 31 days): the field is the sum of pod allocation, code deploy, dependency deploy and scheduling, with scheduling 42-77% of it by region. Activation lag, concurrency on AWS, service times of PRISM's stages and billing are not measured by these data.
- Remaining: Blocker: AWS. Next: plan #4-7, #24, #28-31. Pass: fitted distributions and bill reconciliation. 21 Nov 2026: cold starts and service times for PRISM's stages, per prism-repro/docs/revision/init_vs_memory/MEASUREMENT_PLAN.md (on demand, quota 10). Activation lag and burst overflow are blocked under the quota. Billing reconciliation follows proposal G.
- Suggested response: [pending] All five are measured on AWS Lambda and replace the modelled values.

## R6.3 | Partially fixed
- Requests: (a) Run the event-level simulator in closed loop so that telemetry drives later decisions: implemented in simulation, pre-calibration (shared with R2.2), and used in the verified exploratory pilot. The calibrated confirmatory evaluation is open.
- Changed / rationale: Shared with R2.2. The event-level simulator runs epoch by epoch (a2f04b2), and closed_loop.PolicyController (b3f191f) has each policy set epoch k from event-level telemetry up to minute 5k - 2 only. That telemetry follows the per-minute contract of ea84f09. Forecasts, the conformal offset and the cold-hit estimate are all updated from observed outcomes (tests/test_des_closed_loop.py). The closed-loop tests were added after the last recorded suite run (prism-repro/docs/TEST_REPORT.md, 95163b2), and no saved run of them exists.
- Evidence: tests/test_des_online.py::TestEventTelemetry. Closed-loop pilot verified 21 Nov 2026 from its saved output (Exploratory, pre-calibration, supersedes at recalibration. PRESPECIFICATION.md section 7; development seeds, not a result). Run at commit 1f1d771 on one Windows machine. Design: seeds 101-103, stationary scenario, 14.5 s deadline, one held-out test week per trace. PRISM, QuantProv-q90, Reactive and MemAdapt-q90 were each tuned on the closed-loop validation week by the common rule with the prespecified edge expansion. 125 closed-loop weeks. environment.json, all 12 group files and summary.txt were checked; the selection and edge expansion were replayed from the saved rows, and every policy saw identical request counts per trace and week. Unfavourable first: no comparison attains similar compliance (paired violating-window interval within +/-0.5 points), so every cost comparison is confounded by compliance. Test weeks meeting the 2% target: Reactive 3/3, PRISM 2/3 (trace 103 missed with 16/672 = 2.38%), QuantProv-q90 1/3, MemAdapt-q90 1/3. Paired PRISM minus comparator (95% t interval, df 2): against Reactive, cost -27.3 +/- 6.2% but violating windows +0.79 +/- 0.85 points (more in all three traces); against QuantProv-q90, cost +1.6 +/- 17.0% (neither a difference nor a tie) and violating windows -0.15 +/- 1.28 points. MemAdapt-q90 never left 1024 MB at this deadline, and its outcomes equal QuantProv-q90's in every field. prism-repro/docs/revision/closed_loop_pilot/ (byte copy with SHA-256 list, README, verification.txt). Closed-loop PRISM kappa on the test weeks was 0.384-0.442, read from event telemetry (fast-simulator mean 0.110 in kappa_gap/).
- Remaining: The closed-loop build is complete; the calibrated evaluation stays open. Blocker: measured constants (calibration) before the confirmatory runs. Pass: as R2.2. Pilot limitations (21 Nov 2026): 3 development traces (df 2, wide intervals); one scenario, one deadline and one test week per trace; assumed constants; one Windows machine. Not covered: the short-slack MemAdapt comparison (C3), the new spike, PredHead+S, and matched-compliance frontiers. Next: the confirmatory C1-C3 on seeds 106-130 under PRESPECIFICATION.md after calibration.
- Suggested response: [pending] Implemented: forecasts, cold-hit estimates, decisions and calibration respond to event-level telemetry, and every baseline runs under the same loop.

## R6.4 | Not fixed
- Requests: (a) Compare PRISM directly with a calibrated-q90 + smoothing controller as the primary baseline: open.
- Changed / rationale: Needs the restructured evaluation (closed loop, one main table). The tracker records this comment's work under R2.1, R7.6 and R4.11.
- Evidence: QuantProv-q90 shares PRISM's forecaster and smoothing in the stored runs; paired intervals against it include zero (paper, Tables VI and XII).
- Remaining: Blocker: closed loop. Next: plan #64, #102 with R6.4 named. Pass: main table leads with PRISM against QuantProv-q90 with smoothing at matched compliance.
- Suggested response: [pending] The main results table reports PRISM against the calibrated-q90 controller with the same smoothing, at matched compliance, with paired differences and bootstrap intervals.

## R6.5 | Not fixed
- Requests: (a) Expand beyond five traces with stronger statistical evidence: open (30 traces prepared, not run).
- Changed / rationale: Shares R2.18 (4c43769).
- Evidence: data/trace_set_revision.json.
- Remaining: Blocker: closed loop. Next: plan #58, #62. Pass: primary results on 30 traces with CIs.
- Suggested response: [pending] Thirty traces with recorded seeds, bootstrap CIs and paired differences throughout.

## R6.6 | Not fixed
- Requests: (a) Say which analyses were planned and which post hoc: open.
- Changed / rationale: Labels are manuscript work; the prespecification is not frozen. Every analysis added in this revision is labelled post hoc or pre-calibration in its script and output.
- Evidence: EVALUATION_PROTOCOL.md change log; script headers in scripts/revision/.
- Remaining: Blocker: author's prespecification. Next: plan #40, #110. Pass: every analysis labelled.
- Suggested response: [pending] A prespecification was frozen before the production runs, and every analysis in the paper and supplement is labelled prespecified, post hoc, corrected or version-specific.

## R6.7 | Partially fixed
- Requests: (a) Explain the optimizer's practical value when it rarely chose above the smallest feasible capacity: resolved as an evidenced answer, now with its eps range and end-to-end evidence; manuscript text open.
- Changed / rationale: Shares R2.5, R4.1, R7.1 (066f69c).
- Evidence: Above the smallest feasible level in 16 of 40,293 feasible epochs (submitted code) and at most 0.11% for current code at eps up to 0.05; not ties (each such choice saves 1e-5 to 6e-3 of the epoch cost). At eps 0.08 23.7%, at 0.10-0.20 72-100%; end to end the cost against QuantProv-q90 then stays within -1.2 +/- 2.2% (wider grid) or turns against PRISM (+11.1 +/- 0.8% above break-even). Static restriction cost 2.71%; end-to-end integer-search saving 1.92% with worse compliance in 4 of 6 runs (NA-4, NA-5).
- Remaining: Blocker: none. Next: P-A1 to P-A4 with the corrected wording. Pass: text applied.
- Suggested response: Under the evaluated conditions the optimizer's practical value is small. Where it does choose above the smallest feasible level, at larger risk budgets, under stage-specific demand and above break-even, the end-to-end cost is no better than a calibrated quantile rule with the same information, and above break-even it is worse. We state this, with the conditions tested.

## R6.8 | No change warranted
- Requests: (a) Preserve the negative-result reporting and limitation discussion: guardrail, verified for this revision.
- Changed / rationale: No negative finding has been removed or softened in the repository; this pass added several (weekly misses, platform dependence, the floor result reversal, the non-reproducing level-choice count on Windows) and KNOWN_ISSUES.md stays append-only. The manuscript restructuring (Phase N) must keep every negative finding of v1.
- Evidence: KNOWN_ISSUES.md history (only additions on this branch); NA-1.
- Remaining: Blocker: none. Next: add the check to the Phase N gate. Pass: every negative finding in v1 still present and plainly stated.
- Suggested response: Preserved. The revision reorganises where the negative findings sit but removes or softens none, and it adds several found during the revision.

## R7.1 | Partially fixed
- Requests: (a) Explain when the optimizer gives a clear advantage over simpler calibrated provisioning, and under which operating conditions the complexity is justified: resolved as an evidenced, narrow answer with end-to-end results (pre-calibration); manuscript text open.
- Changed / rationale: Shares R2.5, R4.1, R6.7 (066f69c).
- Evidence: As R2.5: no regime tested gives a consistent end-to-end advantage; the stage-specific advantage over the phi-aware rule (3.1-6.8%) comes from the allocation shape, and above break-even PRISM is 9-11% costlier.
- Remaining: Blocker: none (framing decision R4.1). Next: P-A4 with the end-to-end result. Pass: stated conditions backed by end-to-end results.
- Suggested response: In the regimes we tested end to end, none: with a wider eps grid, above break-even and under stage-specific demand, a calibrated quantile rule with the same information and per-stage allocation matches PRISM or does better. We say so, and describe where the complexity would have to pay for itself [pending the framing decision, R4.1].

## R7.2 | Not fixed
- Requests: (a) Which simulation assumptions contribute most to the higher event-level violation rates: open. (b) How they affect PRISM in a real environment: open.
- Changed / rationale: Not started; the decomposition by mechanism (initialisation occupancy, downstream dependency, attainment metric) is the Phase E decomposition task. Only the attainment-metric component is now handled (exact attainment, main 1ab053c).
- Evidence: Fast versus event, same schedules: 1.44% -> 3.75% (T10_fast_vs_event.md).
- Remaining: Blocker: closed loop for the real-environment part. Next: the Phase E decomposition task. Pass: per-mechanism contributions reported.
- Suggested response: [pending] We isolate the contributors: initialisation occupying environments, downstream dependency, and the attainment metric, and report each one's share of the gap.

## R7.3 | Partially fixed
- Requests: (a) Explain how the risk budget relates to window-level compliance: resolved as a validated empirical mapping and a stated mechanism; final figures and text open.
- Changed / rationale: Shares R2.3 (637596a).
- Evidence: As R2.3; at 13 s and eps 0.02 the per-record constraint holds at 1024 MB while ~96% of windows violate (NA-7).
- Remaining: Blocker: regeneration. Next: as R2.3. Pass: as R2.3.
- Suggested response: The relation is empirical: the weekly violating-window rate rises monotonically with eps, and a prediction interval fitted on validation weeks covered [pending] of held-out weeks. Because eps bounds a per-record probability, it must sit below the 1% per-window allowance when warm misses dominate, which we now state.

## R7.4 | Partially fixed
- Requests: (a) Compare with a simpler memory-adaptive calibrated-quantile controller: resolved (pre-calibration); manuscript inclusion is the author's decision D1.
- Changed / rationale: Shares R2.6 (a396f40, 7980b69).
- Evidence: As R2.6.
- Remaining: Blocker: author decision D1. Next: as R2.6. Pass: as R2.6.
- Suggested response: Added: a calibrated-quantile controller that chooses memory by estimated warm-service feasibility, tuned under the common rule and verified to adapt. In the regimes tested, joint optimisation provides no benefit beyond this automatic memory selection: the simple controller meets the target at equal or lower cost (see R2.6).

## R7.5 | Partially fixed
- Requests: Sensitivity of decisions, cost and compliance, especially under sudden spikes, to: (a) cold-start behaviour: resolved, pre-calibration (initialisation direction). (b) Activation lag (implied by the spike scenarios): resolved, pre-calibration. (c) Upper-tail demand behaviour: open. (d) Memory-dependent execution times: open. (e) Scale-in smoothing: open.
- Changed / rationale: a4187f7 (with per-scenario results, including the new spike). The calibration sweep (dc528db, R2.11) adds update rate, clipping, feedback delay and initial offset; none of (a)-(e) is among them, so the items below are unchanged.
- Evidence: Lag sweep by scenario: PRISM new-spike violating windows 2.11% / 2.50% / 2.26% at L = 2 / 5 / 10 (docs/revision/sensitivity/rows.jsonl); init-direction results NA-7.
- Remaining: Blocker: AWS for measured centres. Next: plan #80 and the Phase S set (upper tail, nonscaling, hysteresis). Pass: each sweep centred on a measured value.
- Suggested response: [partly pending] We sweep each assumption around a measured centre and report the spike scenarios separately; lag and initialisation are done in simulation, the rest are [pending].

## R7.6 | Not fixed
- Requests: (a) Clarify which differences are statistically meaningful: open. (b) Avoid reading small differences as superiority: open.
- Changed / rationale: Manuscript work (P-A6 "within 1.6%" row, P-B2). The paper's own paired intervals against QuantProv-q90 include zero (reviewer 5).
- Evidence: Paper Tables VI and XII (as quoted).
- Remaining: Blocker: regeneration for final intervals. Next: plan #108, #64. Pass: every comparison carries its interval; no superiority claim where it includes zero.
- Suggested response: We accept this: every pooled figure carries its per-trace and per-scenario range, intervals that include zero are reported as such, and no ordering is claimed where the interval includes zero.

## R7.7 | Partially fixed
- Requests: (a) Make the updated code, workload settings, simulator configurations and test scripts available: open (prepared locally; release is the author's action). (b) Clarify which findings are demonstrated in simulation and which need a real environment: resolved in the repository (REPRODUCE.md section 6); manuscript scope statement open.
- Changed / rationale: REPRODUCE.md (8bf6152, 69d5049, 95163b2); checksum verification works on Windows checkouts (efcfd12); trace set with checksums (4c43769).
- Evidence: REPRODUCE.md; tests/test_manifest_verify.py.
- Remaining: Blocker: release decision. Next: release with REPRODUCE.md; add the scope table (P-D R7.7 row). Pass: repository reachable; scope table in the paper.
- Suggested response: The repository, with configurations, workload generator settings, test scripts and REPRODUCE.md, is available [link pending]. We list which findings rest on simulation and which still need measurement on a real platform.
