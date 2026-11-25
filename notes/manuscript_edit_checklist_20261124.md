# Manuscript-pass checklist: R4.4, R4.5, R4.10, R5.m5, R7.6 (plus the R3.2 and R6.1 text items), verified 24 Nov 2026

This file is for the later manuscript pass. Nothing here has been applied. The manuscript source is not in this
repository, so locations are given as sections, tables, captions and the page and line references the reviewers cite.
Confirm them in the manuscript. Wording sources are in `notes/manuscript_proposals.md`, with M18 superseding the parts
of M1-M4, M7 and K7 it names.

## R4.4: narrow RQ4

**Exact ask.** "Please narrow RQ4 or test it. AWS sets memory per function, but PRISM shares one size across stages.
It is also tested only in fixed regimes. ... The graphical abstract caption's 'memory adaptation helping satisfy
tighter latency targets' goes beyond this evidence."

**Scope, verified against code and saved results:**
- **One memory size for all stages:** `policies.PRISM.decide` returns a single size.
- **Re-decided hourly:** `PrismConfig.memory_every` = 12 five-minute epochs. Concurrency is decided every epoch.
  M1's "chosen at each decision epoch" was wrong, and M18(1) corrects it.
- **Execution characteristics fixed within each run** in the main study.
- **Observed load-driven memory changes** (`prism-repro/docs/revision/memadapt/summary.txt`): PRISM's selected
  settings made 1.8 changes per week at 13 s and 0.2 at 12 s (non-scaling 0.5), and 0 at 12 s (non-scaling 0.15). At
  13 s they used 2048 and 3008 MB in 4 of 5 weeks. The warm-feasibility rule made 0 changes and stayed at 2048 MB.
- **The R2.7 test is separate:** an exploratory step in execution time (`prism-repro/docs/revision/r27_shift_20261124/`).
  It is not part of RQ4's evidence. M18(3) gives the conditional wording.

**Cost trade-off at identical compliance, verified:**
- **8-28% more,** from the three regimes with identical violating windows:
  - +27.9% at 13 s (non-scaling 0.5);
  - +19.8% at 12 s (non-scaling 0.5);
  - +8.3% at 12 s (non-scaling 0.15).

  Both policies meet 2% in 5 of 5 weeks in each.
- **Not comparable** where compliance differs: 14.5 s (+1.6%) and 11 s (+4.7%).
- **C3:** PRISM +13.06% [+8.50, +17.63], with weeks meeting 2% 24 against 17 of 25. That is confounded. M2's and
  K7's "the rule costs/is 13% less/cheaper" inverts the base, and M18(2) and M18(5) correct it.

| # | Location | Edit | Text |
|---|---|---|---|
| 1 | Section I, research questions | Replace RQ4 | M18(1) |
| 2 | Table XIII, RQ4 row (question and scope columns) | Same scope | M18(1); scope: one shared size, chosen hourly; fixed execution characteristics; fast-simulator regimes; post hoc where labelled |
| 3 | Results, memory regimes (Section VI-G, Table IX; Table S14 for the 2048 MB headroom comparison) | State the answer at identical compliance only, with labels | M18(2) |
| 4 | Conclusions, the third conclusion (Reviewer 5: p. 17, ll. 89-95) | Same answer; remove any "memory adaptation helps" claim | M18(2), and M6's wording rules |
| 5 | Section VIII, limitations | Scope sentence | M3, or M18(3) if the R2.7 experiment is reported |
| 6 | Graphical-abstract caption | Narrowed memory clause | M4, or M18(3); see R5.m5 below |
| 7 | Abstract and contributions | Search for "memory adaptation", "joint optimisation" and "adapts"; narrow each to M18(2) | M6 |
| 8 | Reply R4.4 | Tracker suggested reply (M5) | Accurate. If the R2.7 experiment is reported, change "were not tested" to the M18(3) wording |

## R4.5: name a pipeline with per-record deadlines

**Exact ask.** "Please name a pipeline with per-record deadlines, since AWS's concurrency guidance says asynchronous
data pipelines do not usually need provisioned concurrency."

**Verified:**
- **The use case:** `prism-repro/aws_pipeline/SPEC.md`, "Proposed representative workload: synchronous document
  ingestion": the caller waits, four sequential stages, each record with its own deadline.
- **The deadline:** 14.5 s (`PipelineConfig.deadline`; SPEC.md "Deadline: 14.5 s per record, end to end").
- **The AWS quotes** are saved in `notes/decisions_pending.md` (verified 23 Nov 2026):
  - "Generally, interactive workloads benefit the most from the feature", and asynchronous data-processing pipelines
    "do not usually need provisioned concurrency", from provisioned-concurrency.html;
  - "doesn't come online immediately ... after a minute or two of preparation", from lambda-concurrency.html.

**Gap:** M7 cites only the first page for both claims. M18(4) gives both pages.

| # | Location | Edit | Text |
|---|---|---|---|
| 1 | Section I, motivation, where the problem setting is introduced (before the contributions) | Insert the use-case paragraph | M7, with the M18(4) citation |
| 2 | References | Add both AWS pages, with titles as fetched and the access date | M18(4) |
| 3 | Section V (setup) or Section VIII | Evidence sentence | M7's "Evidence sentence" |

The evidence sentence keeps three things distinct:
- the end-to-end integration test (`aws_live_integration/`): 39 of 40 in the **baseline arm** (on demand, fixed 1024 MB); the fixed-schedule arm met 29 of 40. *Corrected 24 Nov 2026: this line attached 39 of 40 to the fixed-schedule test; see M19(1).*
- the direct stage measurements (20,992 invocations; `aws_memcal_20261122/`);
- the pending adaptive run (R6.1).

The R4.5 reply (M8) is accurate as drafted.

## R4.10 and R5.m5: graphical abstract

**Exact asks:**
- **R4.10:** "The graphical abstract should show smoothed headroom at 3.24% next to the 6.67%."
- **R5.m5:**
  - (a) show smoothed headroom (3.24%);
  - (b) "The title on its image also differs from the article title and should match it";
  - (c) narrow "memory adaptation helping satisfy tighter latency targets" to the third conclusion.

**The draft:** `prism-repro/docs/revision/graphical_abstract_20261123/` (SHA256SUMS verified).
- **One labelled result set:** current code (fd8b01a + 6e0f05c), Linux x86-64, fast simulator, PRE-CALIBRATION,
  new-spike test week, five development traces.
- **The source table:** `prism-repro/docs/revision/label_fix_20261123/outputs/linux_tables/T5_test_weeks.md`, new-spike
  rows. They match `inputs.csv` exactly:
  - PRISM 2.62 ± 1.50% at USD 1,241 ± 135 (SLO met 20%);
  - smoothed headroom 4.02 ± 2.67% at USD 1,157 ± 74;
  - unsmoothed headroom 7.62 ± 2.31% at USD 1,082 ± 66.
- **Units:** % of 15-minute windows; USD per week; 95% t half-widths over 5 traces.
- **The title** equals the article title in the submission tag: `v1-submitted:prism-repro/CITATION.cff`
  (preferred-citation) and `README.md`. The older name in `src/prism_repro/__init__.py`, "A Joint Cost-SLA
  Optimization Framework for Serverless Data Pipelines via Predictive Workload Provisioning", is the likely title on
  the submitted image; the image itself is not in the repository. Confirm against the submission system. *24 Nov 2026: the author's copy of the submitted image is titled "PRISM: Predictive Resource and SLA Management for Serverless Data Pipelines" (M19(3)), not the `__init__.py` name.*
- **The caption's memory clause** has the narrowed form (M4). Its last clause follows M18(3). It makes no "memory
  adaptation helps" claim.

**Values that depend on the reporting platform, or will change with the calibrated rerun:**

| Quantity | Submitted (stored) | Windows, current code | Linux, current code (draft) |
|---|---|---|---|
| PRISM / smoothed / unsmoothed violating windows, new spike | 1.55 / 3.24 / 6.67% | 2.11 / 4.11 / 7.92% | 2.62 / 4.02 / 7.62% |
| PRISM traces meeting 2% (caption: "1 of 5") | 4 of 5 (80%) | 2 of 5 (40%) | 1 of 5 (20%) |
| PRISM / smoothed / unsmoothed weekly cost (USD) | 1,395 / 1,241 / 1,160 | 1,270 / 1,150 / 1,077 | 1,241 / 1,157 / 1,082 |
| 2048 MB headroom cheaper than PRISM's best setting (caption) | 14-29% | 13-27% | 13-27% |

Every value is PRE-CALIBRATION, and all of them change with the calibrated rerun.

| # | Location | Edit |
|---|---|---|
| 1 | Graphical-abstract image | Replace it with the draft, regenerated from the reporting platform's T5 table (`make_graphical_abstract.py` reads one table and checks its rows) |
| 2 | Graphical-abstract caption | `caption_draft.txt`, regenerated with the image; apply M18(3) to the last clause if the R2.7 experiment is reported; check "met the target on N of 5 traces" against the reporting platform |
| 3 | Replies R4.10 and R5.m5 | Keep the bracketed value alternatives until the reporting platform is chosen, then delete the others |

## R7.6: matched-compliance interpretation

**Exact ask.** "The authors should clarify which differences are statistically meaningful and avoid interpreting
small numerical differences as established superiority."

**Verified against `prism-repro/docs/revision/label_fix_20261123/outputs/r76_endpoints_full_precision.json`:**
- Linux 1.5%: −1.783 ± 1.512, i.e. [−3.295, −0.271]; all 5 traces bracket the target.
- Windows 1.0%: −2.270 ± 2.016, i.e. [−4.286, −0.254]; all 5 traces bracket the target.
- Only these two cells exclude 0. Each endpoint nearest zero lies within 0.3 points of zero.
- No regenerated cell lies within ±2%. Only the submitted code's 2.0% cell does, at +0.17 ± 1.18.
- Trace 105 is unbracketed at Windows 1.5% and 2.0%, and at Linux 2.0%.

**K7's other figures, verified:**
- the submitted code at 1.0%: −0.36 ± 3.30, i.e. −0.4% [−3.7%, +2.9%];
- the change between code versions at 1.0%: −1.91 ± 2.42 points (Windows) and −1.62 ± 2.03 (Linux), from
  `r76_matched_1pct.txt` on each platform;
- the pooled matched difference at 1.0%: −1.5% (Windows), −1.7% (Linux), −1.4% (submitted), from `pc_billing_bounds.txt`.

**The labels** are already in the agreed paragraph: POST HOC, fast simulator, five development traces, assumed
(pre-calibration) constants. So are the separation from the cheapest-setting comparison C1 and the distinction from
the pooled statistic.

| # | Location | Edit | Text |
|---|---|---|---|
| 1 | Matched-compliance results (the Table VII discussion) | Replace any superiority reading with the agreed paragraph | K7, agreed wording |
| 2 | Table VII caption, or a footnote | Label it POST HOC; give the traces bracketed per cell (n = 4 where trace 105 is unbracketed) | K7 |
| 3 | Abstract, "within 1.6%" (also R5.M7) | Say it is the pooled matched difference, with its scope | K7, third bullet |
| 4 | Any C3 sentence | "PRISM costs 13% more ... confounded by compliance" | M18(5) |
| 5 | Reply R7.6 | Tracker suggested reply | Verified. Delete the bracket once the reporting platform is chosen |

## R3.2 and R6.1: text items (for completeness)

- **R3.2:**
  - the Section II scope statement (M11 with M14);
  - the reproduction attempt in the supplement;
  - the reply, `prism-repro/docs/revision/r32_blocker_20261124/NOTE.md` section 6.

  This needs the author's confirmation of [3], and a decision on the unsent inquiry.
- **R6.1:**
  - the Section VIII limitation sentence (M13), until the live run;
  - after a run that meets `RUN_SHEET_20261124.md` section 4, a small-scale demonstration only (its section 6).
