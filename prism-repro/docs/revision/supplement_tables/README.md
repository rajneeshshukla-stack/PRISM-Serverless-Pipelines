# Per-trace supplementary tables (R5.m4)

**Scope.**
- These are stored submitted rows only. No new simulation was run.
- All values are pre-calibration, and they change at the regeneration. They are prepared for the supplement once
  regenerated; no manuscript edit was made.

Reviewer 5 (minor 4): "No table shows the per-trace ablation and QuantProv memory results given there; they belong in
the supplement."

**Reproduce:**

```
python prism-repro/scripts/revision/supplement_pertrace_tables.py prism-repro prism-repro/docs/revision/supplement_tables
```

`pertrace_tables.md` contains two tables.

**Per-trace PRISM ablations.**
- Coverage: five traces, four test weeks each.
- Setting: PRISM at each trace's validation-chosen eps.
- Variants, each at that same eps:
  - without conformal recalibration;
  - with a forecast oracle;
  - without the scale-in rule;
  - in quantile feasibility mode.
- The last two were stored only for the stationary and new-spike weeks.

**Per-trace QuantProv memory results.**
- Coverage: two traces, six memory regimes, the stationary test week.
- Selection: post hoc, the cheapest setting within 2% on the test week, as the stored analysis did.

**Verification.** The means over traces reproduce the stored mean tables `results/tables/E3_ablation_conformal_oracle.md`
and `results/tables/R2_quantprov_memory.md` in all 46 checked cells; the script exits non-zero otherwise.

**One observation the reviewer did not raise.** In the memory table, QuantProv at 2048 MB is selected at the bottom edge
of its grid (a = 0.6) in most regimes. A wider grid could therefore make it cheaper still (compare R4.7 and R5.M4).
