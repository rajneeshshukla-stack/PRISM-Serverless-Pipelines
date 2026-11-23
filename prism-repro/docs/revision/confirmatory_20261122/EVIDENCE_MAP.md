# Reviewer-to-evidence map for the 13 target comments (22-23 Nov 2026)

**Sources:**
- Wording: `review-inputs/detailed review comments.txt`.
- Baseline tracker: `PRISM_Tracker_dispositions_aws_ce_requery_verified_20261122-160015.xlsx`, SHA-256
  `aacfc8da...`, with an identical copy in `PRISM_tracker_backups`. Totals: 0 Fixed, 42 Partially fixed, 30 Not fixed,
  1 No change warranted.
- Branch `closed-loop` at fd8b01a.

ID case is preserved: R5.M7 is Reviewer 5's major comment 7, and R5.m4 and R5.m5 are minor comments 4 and 5.

**Criterion (tracker About sheet):**
- **Partially fixed:** at least one substantive request resolved, another open.
- **Not fixed:** substantive work or verification remains, and no substantive request is resolved.
- **Fixed:** only when the full request is satisfied, including any manuscript edit.

The manuscript is not in the repository, so no comment can be Fixed in this pass.

**Labels:**
- CONF: prespecified confirmatory (C1-C3, seeds 106-130).
- EXPL: exploratory.
- POST HOC: uses test-week knowledge.
- PRE-CAL: assumed constants.

All results below are PRE-CAL.

| ID | Reviewer wording (key clause) | Subrequest | Evidence (artifact: result) | Still needed | Criterion for "addressed" |
|---|---|---|---|---|---|
| R2.1 | "Please make the event-level simulation the primary evaluation environment or provide a calibrated approximation demonstrated to reproduce its compliance behavior adequately." | (a) event level as the primary evaluation | `run/summary.txt`, `run/tables/` (CONF): C1-C3 in the closed-loop event-level simulator. `checks/smoke_check_101.json`: exact attainment and telemetry cutoff verified | manuscript: make it the primary table (K1, K2) | the primary comparisons come from the event-level closed loop |
| R2.1 | | (b) calibrated approximation | not pursued; (a) is taken | none | n/a: the comment offers (a) or (b) |
| R2.18 | "Please consider additional independent workload realizations and repeated experiments using different simulation configurations. The analysis should also distinguish exploratory post hoc comparisons from confirmatory findings." | (a) more realisations, repeated experiments | 25 confirmatory traces (seeds 106-130) in C1-C3, plus the C3 configuration (12 s deadline); traces checked against the manifest (`trace_verification.json`) | calibrated rerun (a second configuration), after the blockers in `CONSTANTS.md` | results on traces beyond the original five, by trace |
| R2.18 | | (b) label post hoc versus confirmatory | prespecification frozen in d16fbea, before any run on seeds 106-130; every output here carries its label | manuscript labels (E11) | every table and figure labelled |
| R3.3 | "The fast simulator was derived from the constant in Eq. 14 (Section V(A)). Please add a test without this match and move the event level Table X next to Table V." | (a) a test without the match | C1-C3 (CONF) at event level. `checks/r33_match_check.json`: the event-level evaluation is bit-identical when the matched-draw parameter changes 0.45 to 0.90, while the fast simulator's changes (README, R3.3) | none technically | the evaluation does not use the matched construction, and comparisons exist under it |
| R3.3 | | (b) move Table X next to Table V | proposal K3 | manuscript edit | table placed |
| R3.6 | "Please rerun all tables with the patched code in one library version (Sections V(E), VI(G), Supplementary S1) and share the code now." | (a) rerun all tables in one version | `../regeneration_20261122/`: tables regenerated at fd8b01a in one environment, compared table by table with the stored ones | complete the regeneration steps (run after C1-C3) | every stored table rebuilt from one commit and environment, with commands and checksums |
| R3.6 | | (b) share the code now | repository prepared locally | author's outward action | code reachable by the reviewers |
| R4.2 | "Please make a closed loop event level simulation, with exact attainment, the primary evaluation." | (a) | closed loop: tests 30/30 and the smoke check (cutoff 5k-2 at every decision; no lookahead with GBM forecasts). Exact attainment: smoke check B (6,122,799 of 6,122,799 requests counted). Primary evaluation: C1-C3 (CONF) | manuscript: primary table (K1, K2) | primary comparisons from the closed-loop event level with exact attainment |
| R4.10 | "The graphical abstract should show smoothed headroom at 3.24% next to the 6.67%." | (a) | `../graphical_abstract_20261122/`: inputs verified against Table V | figure edit | figure redrawn |
| R4.11 | "The prototype, commit and library version details in Section V-E and Section S1 read as release notes. They would sit better in the repository." (and Q3: one primary evaluation) | (a) move provenance prose | REPRODUCE.md, KNOWN_ISSUES.md and PROVENANCE.md hold it; proposal E10 | manuscript edit | prose moved |
| R4.11 | | (b) one primary evaluation, one main table, a separate exploratory section | C1-C3 give the primary evaluation and main table (K1, K2) | manuscript restructure | structure in place |
| R5.M7 | "The abstract and conclusions state results more broadly than Section VI ..." | (a)-(f) | audit in `../regeneration_20261122/` (R5.M7 section), against the tables the reviewer cites, on regenerated and confirmatory values | manuscript wording | each claim labelled and scoped |
| R5.m4 | "No table shows the per-trace ablation and QuantProv memory results given there; they belong in the supplement." | (a) | `../regeneration_20261122/` per-trace tables, with the missing combinations run | insert into the supplement | tables exist and are complete |
| R5.m5 | "Smoothed headroom (3.24%) should be shown as well. The title on its image also differs from the article title ... The caption's ... needs narrowing to the third conclusion." | (a), (b), (c) | `../graphical_abstract_20261122/`: inputs, title, caption | figure edit | figure redrawn, title matched, caption narrowed |
| R6.4 | "Compare PRISM directly with a simple calibrated-q90 + smoothing controller as the primary baseline." | (a) | C1 (CONF), PRISM against QuantProv-q90: same GBM forecaster and conformal offset, same 0.85 scale-in rule (smoke check D: forecast arrays identical) | manuscript: C1 leads the main table | primary comparison exists with paired cost and compliance |
| R6.5 | "Expand beyond five traces and report stronger statistical evidence." | (a) | C1-C3 on 25 traces, paired 95% t intervals (df 24), direction counts, prespecified criteria | manuscript | 25-trace primary results with intervals |
| R7.6 | "The authors should clarify which differences are statistically meaningful and avoid interpreting small numerical differences as established superiority." | (a) which differences are meaningful | C1-C3 (CONF) classifications by the prespecified criteria; the 1.0% matched-compliance comparison regenerated (POST HOC) | manuscript wording | every comparison carries its interval and classification |
| R7.6 | | (b) no superiority from small differences | as (a) | manuscript wording | no superiority claim where an interval includes zero |
