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
