# Proposed manuscript changes

Branch `phase-e-review`, 21 Nov 2026. The manuscript was not opened or edited in this pass. Each proposal quotes
the passage **as the reviewer quotes it** (page and line numbers are the reviewers'), so every one is marked
**[check against current text]**. Figures marked *pending* are produced by the regeneration on measured constants;
until then the proposal gives the supported argument only. Evidence and provenance: `notes/number_audit.md`.

Naming rule: the *Erlang-B relative error* (1.92%) and the *end-to-end integer-search saving* (1.92%) are
unrelated; never print either unnamed or next to the other.

## A. The optimizer: a narrow, evidenced claim (R2.5, R2.13, R2.21, R4.1, R6.7, R7.1; also R5.M5, R5.M7)

### A1. State the reduction at the default deadline (§IV-C and §VII-B) — R4.1, R5.M5
Reviewer 4: "Please state what PRISM reduces to at the default deadline. Feasibility is checked at the 0.895 level
(Section IV-C). Utilization is below break-even, so the smallest feasible level won in all but 16 of 40,293 feasible
epochs (Section VII-B)." **[check against current text]**

Proposed (end of §IV-C): "At the default deadline the formulation reduces to a simple rule. Feasibility is
evaluated near the calibrated 0.9 quantile, utilisation is below the break-even point at which provisioned capacity
becomes cheaper than on-demand execution, the cold-hit estimate sits at its floor, and one demand level drives
every stage through (15). The cheapest feasible candidate is then almost always the smallest feasible member of the
one-parameter family, and PRISM behaves as a calibrated-0.9-quantile rule with a load-dependent scale, close to
QuantProv-q90. Reviewer 4's reading of this regime is correct, and we state it here rather than leave it to be
derived."

### A2. The level-choice statistic (§VII-B) — R2.17, R4.1, R6.7, R7.1
Proposed: "In a post hoc re-run of the submitted code (Linux, Python 3.13.18), the optimiser chose a level above
the smallest feasible one in 16 of 40,293 epochs that had a feasible candidate (40,320 epochs in all). After the
corrections in Section V-E the corresponding share stays below 0.07% of the epochs with a feasible candidate in
every environment we tested; the exact count varies between environments, so we report the bound." Do **not**
print 22, 26 or 10 as reproducible counts. The variation is not floating-point near-ties (instrumented: every
above-smallest choice saves 1e-5 to 6e-3 of the epoch cost); it follows forecast inputs that differ between
platforms (A6). Do not attribute it to a library version.

**Correction to A1 and A2 (21 Nov 2026).** The 0.07% bound holds at the per-trace eps the diagnostic fixes, those
the submitted run selected (0.02 to 0.05). Run at every eps on all 20 held-out weeks (common demand, current code,
Windows; `docs/revision/stage_demand_e2e/`), the share is at most 0.11% for eps up to 0.05 (43 of 40,307 at 0.03)
but 23.7% at eps = 0.08, the top of the grid. On current code the validation rule selects 0.08 for three of the
five traces, and at those selections 14.7% of the feasible epochs (5,908 of 40,316) are above the smallest. A2 must
therefore name its eps ("at the eps selected in the submitted run, 0.02 to 0.05"), and A1's "almost always" holds
only for eps up to 0.05. The end-to-end cost effect of these choices is small (same folder: PRISM against
QuantProv-q90 at the selected settings and at matched compliance).

### A3. What the restriction costs (§VI, new subsection) — R2.13, R2.5, R4.1, R7.1
Proposed: "PRISM evaluates a one-parameter family of capacity vectors. We measured what that restriction costs in
two ways, which should not be confused. As a static benchmark, integer coordinate descent from PRISM's chosen
vector, under the same per-epoch feasibility rule, found cheaper feasible vectors in all 16 configurations tested
(four ε values, two memory sizes, two demand sets): the gap averaged 2.71% (range 1.52–5.90%). End to end, in six
offline test-week replays (traces 101–103, stationary and new-spike demand) in which PRISM's vector was refined in
this way every epoch, the **end-to-end integer-search saving** averaged 1.92% (range 1.53–2.66%). It was not free:
the share of violating windows rose in four of the six runs, and in two (trace 103, stationary 1.93% → 2.38%, and
new spike 1.79% → 2.08%) it crossed the 2% target that unrefined PRISM met. A cheaper per-stage vector existed in
96.6–99.7% of the epochs in which PRISM's decision was feasible. The searched vectors are an offline benchmark, not
a policy PRISM can run as specified." [the end-to-end figures come from one Linux run of
`scripts/revision/integer_search_e2e.py`; add that script and its output to the repository before submission]

Remove or replace any wording that the restriction "binds in 97–99.7% of epochs" (wrong low end; the quantity is
the existence of a cheaper vector, not a binding constraint).

### A4. Where the candidate family fails (§VI or §VIII) — R4.1, R2.5, R7.1, R2.21
Proposed: "The evaluated pipeline sends the same demand to every stage. When stages see different demand the
restriction matters more. In a static benchmark at 1024 MB with the paper's demand quantiles, the family's gap to an
integer search was 2.90% with common demand (the baseline of this comparison), 5.06% when stage 2 filters half the
records and 5.78% when stage 4 batches 10:1. When stages 3–4 see three times stage 1's records, no member of the
family is feasible on the paper's candidate grid (upper bound 1.15× the largest scenario) for any ε tested; widening
the bound to 4.0 makes it feasible at ε = 0.02, at 17.40% above the searched vector. These are static results for one
profile each. They show the limits of the one-parameter family, not an end-to-end advantage of the optimiser, which
we did not test in these regimes." Utilisation above break-even (Reviewer 4's second test) is *not run*: say so.

### A5. Contribution list, title and abstract — R2.21, R4.1, R5.M7, R3.8
Reviewer 5 quotes p. 17, lines 82–89: robustness "comes from a calibrated upper quantile with online recalibration and
from scale-in smoothing", and the optimizer "has no demonstrated cost or robustness advantage over the calibrated
rules". **[check against current text]**
Proposed contribution sentence: "(i) a chance-constrained formulation of per-stage provisioned concurrency and
memory in AWS Lambda billing terms; (ii) a like-for-like evaluation protocol that tunes every policy by one rule;
(iii) the attribution, in the evaluated simulations, of robustness to the calibrated upper quantile and scale-in
smoothing; (iv) a measurement of what the formulation's one-parameter candidate family costs, which is small when
every stage sees the same demand and large, or infeasible on the paper's grid, under the stage-specific profiles
tested." Present PRISM as a simulation-evaluated framework (R2.21). Title: an author decision (Reviewer 4 offers
"test the optimizer where this fails, or present PRISM as one rule among the families and adjust the title"); the
evidence supports keeping a scoped optimizer claim only if A3–A4 are stated as above.

### A6. Wording that overstates the optimizer (flag list) **[check each against current text]**
| Passage (as quoted) | Reviewer | Proposed change |
|---|---|---|
| "calibrated-90%-quantile rule" (p. 1, l. 16) | R5.M7 | rename, e.g. "q0.9 scaled by the 99%-coverage offset" (it scales q0.9 by the offset that targets 99% coverage) |
| "within 1.6%" (p. 1, l. 16; p. 17, l. 85) | R5.M7, R7.6 | "within 1.6% pooled across traces and scenarios; up to about 4% per scenario at 1.5% violating windows; paired intervals against QuantProv-q90 include zero" |
| "13–29% saving" (p. 1, l. 16–17; p. 17, l. 87) | R5.M7 | label pooled; add "0.2–22% per trace; 11–16% with the omitted charges at their upper bound" (re-derive after regeneration) |
| "supported calibration and cost orderings" (p. 1, l. 20–21) | R5.M7 | name which orderings held and which did not |
| "Much of the benefit credited to uncertainty-aware controllers can thus come from two inexpensive ingredients" (p. 2, l. 91–93) | R5.m1 | "In the simulated pipeline studied here, much of the benefit ..." |
| graphical-abstract caption "memory adaptation helping satisfy tighter latency targets" | R4.4, R5.m5 | narrow to: PRISM selects larger memory when ε is below the warm miss probability at 1024 MB; a fixed 2048 MB headroom rule was 14–29% cheaper (two traces, post hoc); within-run adaptation untested |
| any statement that the optimizer "earns its place" or "decides" the outcome at the default deadline | R4.1, R6.7, R7.1 | replace with A1 and A4 |

## B. Compliance, the chance constraint and the floor (R2.3, R7.3, R2.4, R2.12, R5.M5, R3.4)

### B1. Record-level budget versus the window SLA (§III-C, §VIII) — R2.3, R7.3, R3.4, R5.M5
Proposed: "ε bounds the modelled per-record miss probability; the operational target is that at most 2% of the
672 fifteen-minute windows in a week have fewer than 99% of their records on time. ε is a tuned parameter, not a
guarantee. Two consequences follow. First, if ε exceeds the per-window allowance of 1% while the warm miss
probability at the chosen memory lies between them, the constraint can be met while almost every window violates:
at a 13 s deadline with ε = 0.02, PRISM keeps 1024 MB, whose warm miss probability is 1.18%, and about 96% of windows
violate under every initialisation model we tried. Second, the mapping from ε to the weekly outcome is empirical. We
fit it on validation weeks with the trace as the unit and checked it on held-out weeks: the violating-window rate
rises monotonically with ε, and a 95% prediction interval fitted on validation covered 96.7–98.3% of held-out test
weeks." Final curve and operator rule: *pending* (regeneration). [stored-code curve: only ε = 0.005 keeps the upper
bound within 2%; current code: ε = 0.02]

### B2. Weekly compliance, not only pooled rates (§VI, Table V and the abstract) — R2.4, R5.M7, R7.6
Proposed principle: report, for every family, the number of held-out weeks meeting the 2% target beside the pooled
rate. Evidence from current code (fast simulator, pre-calibration): the submitted configuration meets the target in
12 of 20 weeks at a pooled 1.78%; all eight misses (2.23–3.42%) are on traces where validation chose the largest ε
in the grid. Final counts: *pending*. Do not present a pooled rate below 2% as meeting the target.

### B3. The cold-hit estimate and its floor (§IV-B, §VII) — R2.12, R5.M5
Proposed: "With ε retuned by the same rule, lowering the floor from 0.1 to 0.001 let the estimate follow the
measured cold-start-to-overflow ratio (mean 0.06 instead of 0.10) but did not save cost at equal compliance: at
matched compliance the lower floor cost 2.8–3.7% more; with ε selected on validation it cost 12.3% more and met the
target in 20 of 20 held-out weeks against 12 of 20. Under the default configuration the floor therefore acts as a
conservative constant that the ε tuning compensates for; the adaptive estimate is not what makes PRISM work."
Delete any earlier statement that removing the floor saves 13–21% (fixed-ε, superseded).

## C. Simulation fidelity, sensitivity and platform (R2.1, R5.M1, R5.M2, R1.2, R1.3, R4.3, R7.5, R2.8)

### C1. Abstract and conclusions: the fast simulator matches the controller's load model by design — R5.M1, R3.3
Reviewer 5: the robustness sentences (p. 1, l. 12–15) and the conclusions "should also say, as Section VIII does,
that the fast simulator matches the controller's load model by design." **[check against current text]** Add that
sentence until the closed-loop evaluation replaces the fast simulator as the primary evaluator (*pending*).

### C2. Lag and initialisation sensitivity (§VI, new) — R1.3, R4.3, R5.M2, R1.2
Proposed (pre-calibration wording; replace with the sweep centred on measured values when available): "With every
family retuned at each lag, PRISM's weekly cost at L = 5 and 10 minutes was within 3% of its cost at L = 2 and
stayed about 25% below reactive provisioning. The online recalibration became more conservative without retuning:
the mean offset scaled the raw upper quantiles by 1.48, 1.56 and 1.66 at L = 2, 5 and 10. When initialisation is
constant in memory or grows with it, PRISM still moves to 2048 MB where 1024 MB cannot meet a 12 s deadline and stays
compliant, at 3.4% and 5.4% higher cost than under Eq. (3)." State the limits: fast simulator, assumed constants,
two traces for the initialisation runs. Do not cite the reactive-compliance improvement at longer lags until it is
explained.

### C3. Reproducibility statement (§V-E or the data-availability section) — R2.16, R5.M6, R3.6, R7.7, R2.17
Proposed: "Policies without a learned forecaster reproduce bit for bit across platforms. Forecast-driven results
reproduce exactly only on the reference platform (Linux x86-64) with the pinned package versions: on Windows with the
same versions, PRISM's weekly cost differed by up to 4.1%. We report all results from the reference platform and
give the platform with every figure." Move commit prefixes, library-version history and the defect audit to the
repository (`PROVENANCE.md`, `KNOWN_ISSUES.md`, `REPRODUCE.md`) — R4.11 — keeping in the paper one sentence on the
unexplained divergence of the earlier prototype (R2.17) and a pointer to the repository.

## D. Editorial and minor (verify each against the current text)

| ID | Proposal |
|---|---|
| R5.m2 | Table II: rename the epoch length (τ) or the quantile level, and the stage index (s) or the offset s_k; apply in the supplement too |
| R5.m3 | p. 10, l. 61–63: cite Table IV for the five-trace means (97.3% against 97.2%), not Fig. S2b |
| R5.m4 | add supplementary tables for the per-trace ablation (p. 12, l. 40–43) and the QuantProv memory results (p. 16, l. 33–48); values refresh after the regeneration |
| R5.m5, R4.10 | graphical abstract: show smoothed headroom (3.24%) beside PRISM (1.55%) and unsmoothed headroom (6.67%) under the new spike; match the image title to the article title; narrow the caption (A6) |
| R5.R | add pages to [5] (1281–1297) and [19] (1–8); replace the dead URL of [41]; audit the list against IEEE style |
| R4.5 | name a pipeline with per-record deadlines in §I (a synchronous or interactive pipeline in which each record carries its own deadline), since AWS guidance says asynchronous pipelines rarely need provisioned concurrency |
| R1.4 | add a short portability paragraph: the chance constraint, forecaster and recalibration are provider-independent; the cost model and the concurrency semantics (billing granularity, minimum instances, cold-start behaviour) are what change for Azure Functions or Cloud Run |
| R2.10 | describe the Huawei replay throughout as real arrivals with simulated execution, cold starts, billing and SLA outcomes; never as end-to-end validation |
| R2.22, R3.8 | fix the date placeholders, DOI and volume/year; italicise single-letter variables; make the AI-use disclosure consistent; add a funding statement; label every analysis prespecified, post hoc, corrected or version- and platform-specific (also R6.6) |
| R3.8, R4 (Q3) | shorten the abstract; it currently carries ten numerical results and three post hoc labels (Reviewer 4). Conflict with R5.M7's added qualifiers: keep only figures that survive B2 and A3 |
| R1.1, R2.20 | operator guidance and the safety margin: *pending* (closed-loop and platform data) |
| R4.4 | narrow RQ4 to the demonstrated claim unless per-stage memory and within-run change are tested |
| R7.7 | add a scope table: what the simulations show, and what still needs a real platform (measured initialisation, lag, overflow and billing) |

## E. Manuscript-only queue: exact drafts (prepared 21 Nov 2026)

Status of every item below: **prepared**, not applied. Each quotes the reviewer's location; check each against the
current text before applying. None contains a new number.

**E1. Portability (R1.4), §VIII, new paragraph after the limitations list.**
"Portability. The formulation separates what is provider-specific from what is not. The quantile forecaster, the
conformal recalibration and the chance constraint on the per-record miss probability do not depend on the provider.
Three inputs do: the cost model (Eqs. (8)-(9)), which on Azure Functions would price pre-warmed instances of the
Premium plan per instance-hour and on Cloud Run minimum instances per vCPU- and GiB-second; the concurrency semantics,
since Cloud Run serves several requests per instance where Lambda serves one; and the cold-start model (Eq. (3)),
whose memory dependence differs across platforms. Porting PRISM means re-deriving the risk model for the platform's
concurrency semantics and refitting the cold-start and billing constants; we have not done so."

**E2. Replay scope (R2.10), abstract, §VI-J and Table XIII caption.**
Wherever the Huawei replay is described, use: "a trace-driven replay in which only the arrival times are real;
execution times, cold starts, billing and SLA outcomes are simulated". Table XIII caption, append: "Real arrival
traces; all other quantities simulated. Not an end-to-end validation." Delete or rephrase any sentence that calls the
replay validation on production workloads [check the abstract and conclusions].

**E3. Notation (R5.m2), Table II and every use in paper and supplement.** Epoch length tau -> Delta (seconds;
Delta = 300); the quantile level stays tau. Stage index s -> j; the conformal offset stays s_k. Keep the supplement
consistent.

**E4. Citation (R5.m3), p. 10, lines 61-63.** Replace "Fig. S2b" with "Table IV" for the five-trace means (97.3%
against 97.2%).

**E5. References (R5.R).** [5]: add "pp. 1281-1297". [19]: add "pp. 1-8". [41]: replace the dead URL with the
archived copy or the current documentation page for the same content, with an access date. Audit the list against
IEEE style.

**E6. Presentation (R3.8, R2.22).** Abstract: at most one number per claim, moving the post hoc labels into the body
(Reviewer 4: ten numbers and three labels now). Align §I's contribution list with §VII-B. AI-use disclosure: one
sentence, identical in the cover letter and the paper, stating which tool was used for what [authors to fill].
Funding: "This research received no external funding." or the actual grant [authors to fill]. Replace date
placeholders; complete the DOI, volume and year fields.

**E7. Overgeneralised claim (R5.m1), p. 2, lines 91-93.** Replace "Much of the benefit credited to
uncertainty-aware controllers can thus come from two inexpensive ingredients" with "In the simulated pipeline we
study, much of the benefit we first credited to the uncertainty-aware controller came from two inexpensive
ingredients: calibration of the forecast and smoothing of scale-in decisions."

**E8. Named use case (R4.5), §I.** "PRISM targets synchronous or interactive pipelines in which each record carries
its own deadline, for example a document-ingestion pipeline that must return a classified, redacted and indexed
document to the requesting user within seconds. Asynchronous batch pipelines, which the provider's guidance notes
rarely need provisioned concurrency, are outside this scope."

**E9. Graphical abstract (R4.10, R5.m5).** Figure instructions: (1) the image title must equal the article title;
(2) the headline panel shows three bars for the new-spike scenario (Table V): PRISM 1.55%, smoothed headroom 3.24%
and unsmoothed headroom 6.67% violating windows, the smoothed bar labelled as the stronger comparator; (3) caption:
replace "memory adaptation helping satisfy tighter latency targets" with the narrowing chosen in F, for example "a
larger memory size is selected when the default size cannot meet the deadline". Values refresh at the regeneration.

**E10. Provenance prose (R4.11a).** Move prototype, commit-prefix, library-version and defect-audit prose from §V-E
and §S1 to the repository (REPRODUCE.md, KNOWN_ISSUES.md). Leave one sentence in §V-E: "Code, configuration, seeds
and the record of which code state and platform produced each result are in the repository [ref]." (R4.11b, one
primary evaluation and one main table, waits for the closed-loop runs.)

**E11. Analysis labels (R2.22b, R6.6).** Every table and figure caption ends with one label: "prespecified"
(docs/revision/PRESPECIFICATION.md, frozen in d16fbea), "post hoc", "corrected" or "version- and platform-specific".
All revision results so far are post hoc or pre-calibration and are labelled so.

## F. RQ4 and the abstract's memory claim: options, not a choice (R2.6, R7.4, R3.7, R4.4, R2.7, R4.10, R5.m5)

Evidence (pre-calibration, supersedes at recalibration): `docs/revision/memadapt/` (7980b69): a warm-feasibility
memory rule with calibrated-quantile capacity meets 2% as PRISM does in every short-slack regime and costs less
(PRISM +27.9% at 13 s, +19.8% at 12 s, +8.3% at non-scaling 0.15 and 12 s; +4.7% at 11 s with 0.39 points fewer
violating windows); fixed-2048 MB headroom is cheaper still; the two tie at the default deadline. These are
fast-simulator numbers, and the fast simulator understates event-level cold starts about 3x
(`docs/revision/kappa_gap/`).

- **F1. Narrow.** RQ4 becomes "When the default memory size cannot meet the deadline, does selecting a larger size
  restore compliance, and at what cost?"; answer: yes, and a one-line warm-feasibility rule achieves it at lower
  cost than joint optimisation in the regimes tested. Caption as E9. Addresses R2.6 and R7.4 (with the baseline in
  Table IX), R3.7, R4.4(b), R4.10, R5.m5; answers R2.7 and R4.4(a) as stated limitations.
- **F2. Narrow and test.** F1, plus the within-run change of execution time (decision D4(c)), the one setting in
  which an online memory decision could beat a once-per-regime choice. Adds R2.7 and R4.4(a) if run. Cost: plan
  #99-100.
- **F3. Keep RQ4 as stated.** Not supported by the evidence above; leaves R2.6, R7.4, R3.7 and R4.4 open.

## G. AWS measurement plan under the applied quota of 10 (R1.2, R1.3, R2.8, R2.14, R2.20, R3.1, R4.3, R4.8, R5.M2, R6.1, R6.2, R7.5)

The quota increase to 1,000 was denied on 20 Nov 2026; the applied concurrency quota is 10, so provisioned
concurrency cannot be configured at all.

| Campaign | Feasible at quota 10 | Comments it serves | Smallest design |
|---|---|---|---|
| Initialisation duration vs memory (five sizes, decision D6) | Yes: one cold start at a time | R1.2, R3.1, R4.8, R5.M2, R2.8, R6.2 | per size about 200 forced cold starts (new version, or idle beyond the keep-alive); init duration from the REPORT lines; fit the log-normal and its truncation |
| Warm service time vs memory | Yes | R2.8, R6.2, R7.5 (memory-dependent execution) | per stage and size about 1,000 warm invocations at concurrency up to 10 |
| Orchestration overhead (Step Functions) | Yes | R2.8, R2.20 | per transition, from the execution histories of the runs above |
| Billing reconciliation | Partly: on-demand and request charges only | R2.14 | compare the cost model's on-demand and request terms with the bill of the runs above |
| Activation lag of provisioned concurrency | **No** | R1.3, R4.3, R6.1 | keep the simulated lag sweep (L = 2, 5, 10) and state the lag is unmeasured |
| Burst overflow beyond provisioned capacity | **No** | R6.1, R6.2 | keep the simulated loss routing and state it is unmeasured |

What the quota allows still decides RQ4's direction (initialisation against memory, the decisive gate) and
recalibrates every cold-start constant, which matters more after `docs/revision/kappa_gap/`. The
provisioned-concurrency mechanisms stay simulated, and the paper must say so.

## H. Corrections after the kappa diagnostic (21 Nov 2026; `docs/revision/kappa_gap/`)

- **B3 (R2.12, R5.M5) is on hold.** Its conclusion (keep the 0.1 floor; the lower floor costs 2.8-3.7% more at
  matched compliance) was measured in the fast simulator, where kappa sits on the floor in 89.7% of epochs and the
  unfloored estimate is 0.05, a sixth of the event-level one (0.33 on the same schedules). Do not put B3 in the
  letter until the floor comparison is rerun in the closed loop. What can be said now: "In the fast simulator the
  estimate sits at its floor most of the time; at event level it does not (0.33-0.44), so its role is assessed in the
  closed loop."
- **C1 (R5.M1, R3.3) gains a sentence.** After "the fast simulator matches the controller's load model by design",
  add: "On identical provisioning decisions it produces about a third of the event-level simulator's cold starts per
  on-demand request (3.2x fewer over ten traces) and a quarter of its violating windows (0.70% against 2.89%),
  because its per-minute concurrency omits the occupancy of initialisation. Its compliance figures are therefore
  optimistic, and compliance claims rest on the event-level simulator." (Pre-calibration; supersedes at
  recalibration.)
- **A1-A4 (R2.5, R4.1, R7.1, R6.7)** stand as fast-simulator results and must say so; the closed-loop pilot
  (`docs/revision/closed_loop_pilot/`) is the first event-level comparison and is exploratory.

## I. Drafts after the scope decisions of 22 Nov 2026 (D4, D5, D2; not applied; check the locations against the current text)

**I1. RQ4 (R4.4, R2.7).**
- **Replace RQ4** in Section I and in the RQ4 row of Table XIII: "RQ4: When default memory is insufficient in the fixed
  workload regimes studied, can increasing memory restore deadline compliance, and at what cost?"
- **Answer, for Section VI-G and Table IX / S14** (add MemAdapt and keep the fixed-size rows; figures to be
  regenerated; exploratory, pre-calibration simulation): "Yes. Where 1024 MB cannot meet the deadline (12-13 s), every
  setting of the quantile rule at a fixed 1024 MB violates all windows, and moving to 2048 MB restores compliance (5 of 5
  weeks within 2%). That costs 38% more per week than at the default deadline when half of each stage's work does not
  scale with memory, and 6% more when 15% does not. A rule that selects the smallest warm-feasible size reaches the same
  compliance at lower cost than PRISM's joint optimisation: PRISM costs 8-28% more than the rule (equivalently, the rule
  costs 8-22% less than PRISM). Only at 11 s does PRISM meet the target in more weeks (5 of 5 against 3 of 5), at 4.7%
  higher cost."
- **Limitation, for Section VIII:** "RQ4 is answered only for fixed workload regimes, with one memory size shared by
  the four stages. We did not test per-stage memory sizes or changes in CPU intensity, memory demand, execution time or
  initialisation time within a run. The results therefore do not show whether online memory optimisation adds value
  beyond a one-time memory choice."
- **Also change:**
  - the abstract's memory sentence;
  - the third conclusion (p. 17, l. 89-95);
  - the graphical-abstract caption (E9 and A6: "a larger memory size is selected when the default size cannot meet
    the deadline"; also R5.m5(c));
  - any contribution statement that credits joint online memory optimisation.
- **Reply to R4.4:** "We narrowed RQ4 as suggested: it now asks whether, when default memory is insufficient in the
  fixed regimes studied, increasing memory restores deadline compliance, and at what cost. Section VIII states that
  PRISM uses one memory size shared by all stages and that per-stage sizes and within-run changes were not tested. In
  those regimes (exploratory, pre-calibration simulation), a simple rule that picks the smallest warm-feasible size
  restores compliance at lower cost than PRISM: PRISM's cost is 8-28% higher than the rule's. Only at the tightest
  deadline does PRISM meet the target in more weeks (5 of 5 against 3 of 5), at 4.7% higher cost [figures to be
  regenerated]. The graphical-abstract caption is narrowed accordingly."
- **Reply to R2.7:** "We did not run scenarios in which execution characteristics change during a run. RQ4 is narrowed
  to the fixed regimes studied, and we state as a limitation that the experiment the reviewer describes, which would
  test whether online memory optimisation helps beyond a one-time configuration decision, remains to be done."
  R2.7 stays open.

**I2. Less-structured traffic (R2.9)** (`prism-repro/docs/revision/less_structured_r29_20261122/`; exploratory,
pre-calibration, fast simulator).
- **Add to Section VI-J** (real traces) or a new exploratory subsection, with a supplementary table: the 10 Region 2
  traces, their structure (CV, burstiness, forecast error) and all families' test-week cost and compliance.
- **Reply:** "We evaluated every family on ten further production arrival traces, from the Huawei Public Cloud Trace
  2025, Region 2. They have no designed spikes or known trigger minutes, include irregular bursts (a 99.9th percentile
  up to 39 times the median, and one trace with long idle periods), and span forecast errors from 5% to 56%. We used
  the same tuning rule and split as for the other real traces. PRISM met the 2% target on 7 of 10 traces, as did the
  calibrated q90 rule; static provisioning met it on all 10. No paired cost difference between PRISM and the
  calibrated-quantile, reactive, static or smoothed-headroom policies was distinguishable from zero, and PRISM's
  relative cost was not associated with forecast difficulty. We also evaluated every family under an unannounced change
  of the spike schedule. We therefore do not claim that the predictive cost advantage observed on the synthetic
  traces carries over to less structured traffic [figures to be regenerated]."

**I3. Hybrid histogram baseline (R3.2)** (`prism-repro/docs/revision/hybrid_histogram_r32_20261122/`; option (c) of
D2, pending the author's confirmation of [3]).
- **Add to Section II:** "The hybrid histogram policy of [3] sets, for each application, when its single loaded image
  is unloaded and pre-warmed, from a histogram of idle times with one-minute bins. Its authors exclude cold starts that
  arise when load spikes require new instances, and it reduces the provider's idle memory, which customers are not
  billed for. In every workload studied here, each stage is invoked at least once a minute, so the policy never
  unloads an application and sets no number of concurrent instances. It therefore does not address the provisioned
  concurrency decision that PRISM and the baselines in Table V make."
- **Reply:** "We examined the hybrid histogram policy of [3] in detail. It decides the keep-alive and pre-warming
  windows of one application image for infrequently invoked applications, and its authors explicitly leave aside cold
  starts caused by load spikes that need new instances. Applied to our workloads, where every stage receives requests
  every minute, it keeps every stage loaded at all times (pre-warming window 0, keep-alive 1.1 minutes) and makes no
  provisioning decision, so adding it to Table V would not test a concurrency controller. We explain this in Section
  II [and, if confirmed against the AWS documentation, note that our reactive baseline follows the provider's
  target-tracking rule for provisioned concurrency]."

## J. Drafts from the multi-memory AWS calibration (memcal-1; R2.8, R3.1, R6.2, R2.14; also R1.2, R4.3, R5.M2)

Prepared 22 Nov 2026 from commit fd8b01a (`prism-repro/docs/revision/aws_memcal_20261122/`). Not applied: the
manuscript is not in the repository. **Every section, table and figure reference below is [pending]** until the
drafts are placed in the current text.

**Scope of the evidence:**
- The four docpipe-1 stage functions were invoked **individually**, on demand, with no Step Functions and no
  provisioned concurrency. PRISM's controller did not run.
- The handlers import only standard-library modules and do no application start-up work (`INIT_ROWS = 0`).
- The client was a laptop in us-east-2, with at most 8 invocations in flight.
- The three blocks were repeats on one afternoon (22 Nov 2026), not on separate days.

Section G's "quota of 10" premise is superseded for the on-demand rows: those were run here, at a concurrency limit
read as 400 (D7). The provisioned-concurrency rows of G are still unmeasured.

**J1. Measurements on AWS Lambda (new subsection [section: pending]; new table [table: pending]) — R2.8, R6.2.**
- **Text:** "We measured the four stage functions on AWS Lambda (us-east-2, on demand, x86_64, Python 3.12) at 512,
  1024, 2048 and 3008 MB: 20,992 invocations, 1,312 per stage and size (312 forced cold, 1,000 warm). They ran in
  three consecutive blocks on one afternoon, each with every stage and size in randomised order, from a client
  outside AWS with at most eight invocations in flight. Every invocation was matched by request ID to Lambda's own
  REPORT record, with no errors or throttling. Warm execution time halved from 512 to 1024 MB (2.01-2.04 times
  faster), fell 1.73-1.75 times more at 2048 MB and did not fall further at 3008 MB [table: pending]. Lambda's
  reported initialisation (Init Duration) had a median of 113.7-116.0 ms for every stage and size (5th-95th
  percentiles 94.7-136.6 ms). The first-call penalty seen by the client (median cold minus median warm end-to-end
  time) was 226-258 ms for three stages at every size. For the aggregate stage it was 513, 374, 315 and 309 ms; there
  the cold invocation's own execution was longer, while initialisation did not change. Across the three blocks,
  median warm execution times agreed within 0.41% and median initialisation within 1.1-4.6 ms. The functions do no
  application start-up work, so these values describe the platform, not the 6 s initialisation assumed in the
  simulations."
- **Table** [table: pending]: per stage × memory, the warm Duration median, the Init Duration median (p05-p95) and
  the client-observed first-call penalty P. Source: `tables/timings.csv` (block = all) and
  `tables/decomposition_fit.csv`. The warm medians in ms are:

  | Stage | 512 MB | 1024 MB | 2048 MB | 3008 MB |
  |---|---|---|---|---|
  | ingest | 1,624 | 801 | 463 | 463 |
  | transform | 8,039 | 3,994 | 2,292 | 2,287 |
  | aggregate | 5,093 | 2,529 | 1,451 | 1,451 |
  | load | 2,453 | 1,205 | 689 | 688 |

**J2. What Eq. (3) models ([section: pending], where Eq. (3) is defined) — R3.1, R1.2, R5.M2.**
- **Add after Eq. (3):** "Eq. (3) models the time from a request's arrival at a cold environment to the start of
  service, which includes the platform's initialisation, environment creation and any extra work of the first call.
  On AWS Lambda, the platform's reported initialisation did not change with memory for our stage functions (slope of
  log initialisation on log memory between +0.001 and +0.008, against −0.273 implied by Eq. (3) over 512-3008 MB).
  The first-call penalty seen by the client fell at Eq. (3)'s rate only for a stage whose first call does CPU-bound
  work (slope −0.288, 95% interval −0.309 to −0.269), and at less than half that rate pooled over the four stages
  (−0.116, 95% interval −0.131 to −0.100) [section: pending]. We therefore read Eq. (3) as a model of the first-call
  penalty, not of the platform's initialisation; its magnitude for application start-up was not measured."
- **Do not change** Eq. (3)'s parameters in the text until the simulator is recalibrated and the tables are
  regenerated. How the simulator should represent application start-up remains open (R5.M2).

**J3. Threats to validity ([section: pending]) — R2.8, R3.1, R6.2.**
- **Add:** "The platform measurements cover on-demand invocations of the stage functions from a client outside
  AWS, on one afternoon, for functions without application start-up work. They do not cover provisioned-concurrency
  activation, overflow under a burst, day-to-day variation or the provider's bill. The simulator's constants have not
  yet been recalibrated on them."

**J4. Cost against the bill ([section: pending], where the cost model is defined) — R2.14.**
- **Add:** "For the measurement campaign, the usage reported by Lambda gives 55,234.5 billed GB-s and 20,992
  requests, USD 0.92 at the public us-east-2 list prices (duration and requests only; free tier not assumed).
  Billed duration equalled the reported duration plus initialisation, rounded up to 1 ms, in 21,154 of 21,248
  invocations; the other 94 were 1 ms higher, all where the reported sum was a whole number of milliseconds.
  Reconciliation with the provider's billing records is pending [section: pending]."
- **Do not claim** a reconciliation. Cost Explorer returned DataUnavailableException and showed no service-level
  amounts (author-reported; no saved output).

## K. Drafts from the confirmatory closed-loop runs and the regeneration (22-23 Nov 2026; not applied)

Sources: `prism-repro/docs/revision/confirmatory_20261122/RESULTS.md` (C1-C3, prespecified, PRE-CALIBRATION);
`prism-repro/docs/revision/regeneration_20261122/README.md` (every stored table rebuilt at fd8b01a, PRE-CALIBRATION);
`prism-repro/docs/revision/graphical_abstract_20261122/caption.md`. The manuscript is not in the repository; locations
are the reviewers' citations, **[check against current text]**.

**K1. Primary evaluation structure (R4.11(b), R2.1, R4.2, R6.4, R6.5).**
- **§V, evaluation protocol.** "All primary comparisons are run in the event-level simulator in closed loop. Each
  epoch, every policy sees the telemetry of minutes up to 5k - 2 only, and window attainment is computed from every
  request's latency. The comparisons C1-C3, the traces (seeds 106-130), the split, the tuning rule, the grid-edge
  expansion and the inference rules were fixed before the runs (prespecification, d16fbea)."
- **§VI-A, main results:** one table (K2). **§VI-B onwards, exploratory:** per-scenario breakdowns, matched-compliance
  frontiers (post hoc), memory regimes, real-trace replays, sensitivity sweeps, fast-simulator screening; each
  labelled. **Supplement:** the fast-simulator tables, regenerated (K5). **Repository:** provenance prose (E10).

**K2. Main comparison table [table number pending].** Unfavourable and null rows are not to be reordered away.
Caption: "Prespecified; pre-calibration constants; 25 traces (seeds 106-130); closed-loop event-level simulator;
paired by trace (df 24). A difference requires the 95% interval to exclude zero; a tie requires it within +/-2%;
similar compliance requires the violating-window interval within +/-0.5 points. Cost is the simulator's modelled
weekly cost at the assumed prices, not an AWS charge." Row order: C1 (the primary baseline R6.4 asks for; null), C3
(unfavourable), C2 (favourable).

| Comparison | Modelled mean weekly cost (USD) | Pooled violating windows | Weeks meeting 2% | Cost, PRISM minus comparator | Violating windows, points | Call |
|---|---|---|---|---|---|---|
| C1: PRISM vs QuantProv-q90 (14.5 s, 4 scenarios) | 1,456.5 vs 1,454.6 | 1.58% vs 1.69% | 81 vs 72 of 100 | +0.30% [-1.42, +2.01]; cheaper on 11, costlier on 14 | -0.106 [-0.274, +0.062] | not distinguishable; not a tie (upper end 2.01%); similar compliance |
| C3: PRISM vs MemAdapt-q90 (12 s, stationary) | 1,672.8 vs 1,487.6 | 1.17% vs 1.83% | 24 vs 17 of 25 | +13.06% [+8.50, +17.63]; costlier on 21 | -0.655 [-0.921, -0.389] | PRISM costlier; cost comparison confounded by compliance |
| C2: PRISM vs Reactive | 1,456.5 vs 1,982.9 | 1.58% vs 1.56% | 81 vs 75 of 100 | -26.49% [-28.76, -24.23]; cheaper on 25 | +0.018 [-0.296, +0.332] | PRISM cheaper; similar compliance |

**K3. R3.3: Table X next to Table V, and the unmatched test.**
- Place Table X directly after the main results, as the reason the primary evaluation is event-level.
- §V-A: "The event-level simulator draws no peak concurrency; each request is placed within its minute and routed
  individually, so its evaluation does not use the matched peak draw behind Eq. (14). Changing that draw's parameter
  from 0.45 to 0.90 leaves the event-level outcome of a fixed schedule bit-identical, while the fast simulator's
  changes."
- Table X values: the submitted Table X gives PRISM 1.44% (fast) and 3.75% (event level); the regenerated one
  1.69% and 6.14%. Its driver (E9) needs the released-code lookup fix before the table is rebuilt for the paper.

**K4. R5.M7(f): rename the "calibrated-90%-quantile rule".** "the offset-scaled q0.9 rule (QuantProv-q90)", defined
once: "the q0.9 forecast, scaled by the conformal offset that targets 99% coverage of the window peak, times a tuned
factor a".

**K5. R3.6: regeneration statement (§V-E or data availability).** "Every table was regenerated from one commit
(fd8b01a) in one environment (Windows 11, Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0). Three
experiment drivers (E3, E7, E9) required a one-line correction of a policy-label lookup to run at that commit; the
correction, every other deviation, the commands and the checksums are in the repository." Do **not** write that the
released scripts regenerate every table unchanged. [Platform: the regeneration ran on Windows 11, while REPRODUCE.md
names Linux x86-64 as the reference platform for forecast-driven results; state whichever platform the reported
tables come from (decision pending). Release of the corrected code to the reviewers: author's action.]

**K6. Numbers that change with the regeneration (if the paper reports regenerated tables).**
- Table V new spike: PRISM 2.11% violating windows (was 1.55%), SLO met 2 of 5 traces (was 4 of 5).
- Suppl. Table S4: PRISM 1,150 USD / 1.78% (was 1,267 / 1.36%); PRISM now costs more than QuantProv-q90 (1,142).
- Table VI against QuantProv-q90: +1.6, +1.3, 0.0, -0.1% (was -2.8 to -3.9%); every interval still includes 0.
- Table XII (Huawei): PRISM is not the lowest-violating family (QuantProv-q90 0.18%, PRISM 0.33%).
- E11 (Eq. (5) against Erlang-B): use `E11_erlangb_regenerated.md`; the stock table is degenerate on the current code.
- Table X: PRISM 1.69% fast, 6.14% event level (was 1.44%, 3.75%); see K3.
- E1 and Table XII selections: PRISM at eps 0.08, the top of its grid, on 3 of 5 development traces and 4 of 5
  Huawei traces; state the grid edge.
- Causes: only the 1.0% matched comparison is decomposed (exact attainment and Erlang-B, plus a platform residual);
  do not attribute the other shifts.
- Platform (23 Nov 2026, `prism-repro/docs/revision/label_fix_20261123/`): the submitted results reproduce exactly on
  Linux x86-64 with the pinned versions, not on Windows; every value above is the Windows regeneration. With the
  current code, Linux gives Table V new spike PRISM 2.62% (smoothed 4.02%, unsmoothed 7.62%), S4 PRISM 1,130 against
  QuantProv-q90 1,139 USD (the ordering reverses), Table X 1.98% / 6.99%, and the 1.0% matched comparison
  -1.98 +/- 2.09% (includes zero; 1.5% excludes it narrowly). Report one platform and state it; C1-C3 ran on Windows.
- Graphical abstract: 2.11 / 4.11 / 7.92% (was 1.55 / 3.24 / 6.67%); caption range 13-27% (was 14-29%).

**K7. R5.M7 and R7.6: wording limits.**
- Do not state or imply a cost advantage over QuantProv-q90: C1 is not distinguishable (+0.30% [-1.42, +2.01]) and
  not a tie; Tables VI and XII intervals include 0.
- Matched compliance (R7.6; POST HOC, must not be presented as confirmatory). Agreed wording:
  "In the post hoc matched-compliance analysis, we used test-week results from five development traces in the fast
  simulator with assumed constants. The interpolated paired cost interval excluded zero at the 1.5% target on Linux
  (-1.8% [-3.3%, -0.3%]) and at the 1.0% target on Windows (-2.3% [-4.3%, -0.3%]), both on all five traces. In both
  cases, the endpoint closest to zero was within 0.3 percentage points of zero, and the target at which the interval
  excluded zero varied by platform. No regenerated interval fell entirely within +/-2%, the tie margin prespecified
  for C1-C3 and used here as a benchmark. These results therefore provide only limited, platform- and
  target-specific evidence of lower cost: they do not establish a cost advantage that is consistent across targets
  or platforms, and they leave equivalence unestablished. The estimates at the 2.0% target on both platforms, and at
  the 1.5% target on Windows, used four traces, because PRISM's frontier did not bracket the target on trace 105."
  Full-precision figures: `prism-repro/docs/revision/label_fix_20261123/outputs/r76_endpoints_full_precision.json`.
  The submitted code gave -0.4% [-3.7%, +2.9%] at 1.0% (stored rows, a Linux result); the change to the corrected
  code includes 0 on both platforms (-1.9 +/- 2.4 points Windows, -1.6 +/- 2.0 Linux) and comes mostly from exact
  attainment together with Erlang-B. Do not attribute it to exact attainment alone.
- Two different 1.0% statistics: the pooled matched difference ("within 1.6%"; -1.5% Windows, -1.7% Linux) and the
  paired per-trace mean (-2.3% Windows, -2.0% Linux, with the intervals above). Cite each with its scope.
- Memory (C3): the memory-adaptive q90 rule is 13% cheaper than PRISM at 12 s but meets the target in fewer weeks
  (17 against 24 of 25), so the comparison is confounded by compliance; do not write that it meets the target as PRISM
  does, except for the fast-simulator regimes. Do not call any comparison a tie unless its interval lies within +/-2%.
- The savings against Static and Reactive hold in the regenerated tables (vs Static -12.6 to -18.3%; vs Reactive
  -23.5 to -26.9%, matched compliance, POST HOC) and in C2 (-26.49%, confirmatory).

**K8. Graphical abstract (R4.10, R5.m5).** `prism-repro/docs/revision/graphical_abstract_20261122/caption.md`
(sections 1-4).
