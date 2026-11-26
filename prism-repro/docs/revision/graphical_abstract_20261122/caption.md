# Graphical abstract: inputs, title and caption (R4.10, R5.m5)

Prepared 22 Nov 2026. The figure itself is not in the repository, so redrawing it is the author's edit. Every number
below is checked against its source (`inputs.csv` gives the file and row).

## What the reviewers ask

| ID | Wording | Prepared here |
|---|---|---|
| R4.10 | "The graphical abstract should show smoothed headroom at 3.24% next to the 6.67%." | headline panel inputs (1) |
| R5.m5 (a) | "Smoothed headroom (3.24%) should be shown as well." | the same |
| R5.m5 (b) | "The title on its image also differs from the article title and should match it." | title (2) |
| R5.m5 (c) | "The caption's 'memory adaptation helping satisfy tighter latency targets' needs narrowing to the third conclusion (p. 17, lines 89-95)." | caption (3) |

## 1. Headline panel (new-spike scenario)

Source: `results/tables/T5_test_weeks.md`, Table V. SUBMITTED, fast simulator, pre-calibration, 5 traces; the mean
with its 95% t half-width.

| Bar | Violating windows | Weekly cost (USD) |
|---|---|---|
| PRISM | 1.55 +/- 1.15% | 1,395 +/- 74 |
| Smoothed headroom (PredHead+S), the stronger comparator | 3.24 +/- 1.80% | 1,241 +/- 73 |
| Unsmoothed headroom (PredHead) | 6.67 +/- 1.66% | 1,160 +/- 45 |

**Honest-display note.** Both headroom rules are cheaper than PRISM in this scenario. A panel showing violating windows
alone would leave that out, so the bar labels or the caption should carry the cost too.

**Regenerated values.** After the regeneration at one commit (R3.6), the same row is read from the regenerated
`T5_test_weeks.md`; see `../regeneration_20261122/`. The figure should use the values of the version the paper
reports.

**Confirmatory alternative.** PredHead and PredHead+S are exploratory families in the prespecification, so the
confirmatory runs do not produce them. The confirmatory event-level comparison is PRISM against QuantProv-q90 (C1). Its
new-spike breakdown is EXPLORATORY: `../confirmatory_20261122/run/tables/C1C2_paired.csv`. Redrawing the panel with the
confirmatory comparator instead is an author decision, recorded in the tracker under R4.10.

## 2. Image title

The title must equal the article title: "Joint Cost-SLA Provisioning of Concurrency and Memory for Serverless Data
Pipelines: A Chance-Constrained Formulation and a Simulation Study under Workload Shift". The source is
`prism-repro/CITATION.cff`; check it against the submission system's title.

## 3. Caption

**Replace** "memory adaptation helping satisfy tighter latency targets" **with:**

> "When the default 1024 MB cannot meet the deadline, PRISM selects a larger memory size if its risk budget eps is
> small enough; a fixed 2048 MB headroom rule met the deadline at 14-29% lower cost in the regimes tested (two traces,
> post hoc, no caps), and adaptation to changes in execution characteristics within a run was not tested."

Check of each figure in that sentence:
- **"14-29% lower cost":** `results/tables/revision/E4b_fixed_memory_summary.json`, field `best_PredHead_2048_vs_best_PRISM_pct`. Headroom at 2048 MB against PRISM's best setting is 28.7% cheaper at 13 s, 24.2% at 12 s and 14.3% at 11 s (non-scaling 0.5), and 15.3% at 12 s (non-scaling 0.15). At the default 14.5 s headroom at 2048 MB costs 24.6% more, so the claim holds only in the short-slack regimes.
- **"two traces, post hoc, no caps":** E4b covers traces 101 and 102 and selects with test-week knowledge.
- **"PRISM selects a larger memory size if eps is small enough":** the third conclusion as R5.m5 quotes it ("Where 1024 MB fails the SLA, PRISM picks larger memory when eps is small enough"). The supporting rows are E4b (`share_ge2048`): 100% for PRISM's best settings in every short-slack regime (13, 12 and 11 s at non-scaling 0.5; 12 s at 0.15), and 0% at the default 14.5 s.
- **The memory claim:** it follows the narrowing of decision D4 (`notes/manuscript_proposals.md` I1).

## 4. Regenerated values (added 23 Nov 2026, after the R3.6 regeneration)

Source: the regenerated tree (`private/regen_20261122/prism-repro`, `git archive` of fd8b01a; see
`../regeneration_20261122/README.md`), the same rows as above; `inputs_regenerated.csv`. REGENERATED, fast simulator,
pre-calibration, 5 traces. The submitted values above are kept unchanged.

| Bar (new spike) | Violating windows, submitted | Violating windows, regenerated | Weekly cost (USD), submitted | Weekly cost (USD), regenerated |
|---|---|---|---|---|
| PRISM | 1.55 +/- 1.15% | 2.11 +/- 1.32% | 1,395 +/- 74 | 1,270 +/- 123 |
| Smoothed headroom (PredHead+S) | 3.24 +/- 1.80% | 4.11 +/- 2.28% | 1,241 +/- 73 | 1,150 +/- 54 |
| Unsmoothed headroom (PredHead) | 6.67 +/- 1.66% | 7.92 +/- 2.42% | 1,160 +/- 45 | 1,077 +/- 69 |

- The ordering is unchanged, and both headroom rules remain cheaper than PRISM in this scenario. PRISM's own
  violating rate rises to 2.11%, above the 2% target (SLO met on 2 of 5 traces, against 4 of 5 submitted).
- The figures "3.24%" and "6.67%" that R4.10 and R5.m5 name are the submitted values. If the paper reports the
  regenerated tables, the figure must use 4.11% and 7.92%, and the reply should say why the numbers changed.
- Caption range: on the regenerated E4b rows, headroom at 2048 MB is 27.3% cheaper at 13 s, 22.2% at 12 s and 12.9% at
  11 s (non-scaling 0.5), and 13.5% at 12 s (non-scaling 0.15); at 14.5 s it costs 32.2% more (non-scaling 0.5) and
  2.0% more (0.15). The caption's "14-29%" becomes "13-27%" with the regenerated values. PRISM's best settings use
  >= 2048 MB in every short-slack regime and 1024 MB at 14.5 s, as before.
