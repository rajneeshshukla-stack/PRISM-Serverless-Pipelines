# Which paired differences are distinguishable from zero (R7.6, R5.M7(d), R6.4)

**Scope.** This uses stored submitted rows only, with no new simulation. The values are pre-calibration. The method:

- paired differences, PRISM minus each comparator;
- 95% t intervals over the five traces (df = 4);
- three comparison sets:
  - the validation-selected configurations (Table VI analogue);
  - post hoc matched compliance (Table VII analogue);
  - the post hoc real-trace replay (Table XII analogue).

**Reproduce:**

```
python prism-repro/scripts/revision/statistical_meaning.py prism-repro prism-repro/docs/revision/statistical_meaning/summary.md
```

**Check.** The per-scenario cost differences against QuantProv-q90 and against PredHead+S reproduce
`results/tables/T6_paired_PRISM_vs_QuantProvq90.md` and `T6_paired_PRISM_vs_PredHeadHyst.md` in 4 of 4 scenarios each.

## Findings (`summary.md`)

**PRISM against QuantProv-q90: no paired cost interval excludes zero, in any of the three sets.** That is:

- Selected configurations: every scenario, and the four pooled. Pooled cost -3.5 +/- 7.5%; violating windows
  +0.12 +/- 0.18 points.
- Matched compliance: all three targets. -0.4 +/- 3.3% at 1.0%, -0.4 +/- 2.1% at 1.5%, +0.2 +/- 1.2% at 2.0%.
- Real traces: +2.4 +/- 4.0%; violating windows -0.27 +/- 0.67 points.

This confirms Reviewer 5's statement that "all paired cost intervals against QuantProv-q90 include zero" (R5.M7(d)).

**Differences that do exclude zero, by set:**
- **Selected configurations.** Against PredHead+S, PRISM costs more and has fewer violating windows: pooled
  +10.6 +/- 4.6% and -0.92 +/- 0.58 points. It is cheaper than Reactive (-26.6 +/- 3.1%) and than Static
  (-15.0 +/- 4.9%), but its violating-window differences against those two include zero.
- **Matched compliance.** PRISM is cheaper than Static and than Reactive at every target. Against PredHead+S the
  interval includes zero at every target.
- **Real traces.** 2 of 7 cost intervals and 1 of 7 violating-window intervals exclude zero.

**How to read "includes 0".** It means five traces cannot distinguish the policies at the 95% level; it does not show
they are equivalent. An equivalence statement needs a margin chosen in advance, which is the author's choice.
