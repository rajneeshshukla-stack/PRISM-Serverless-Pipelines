# PROVISIONAL training split with an out-of-sample conformal warm-up (R4.6, R5.M3)

**PROVISIONAL.** This split is a candidate for the author's decision (notes/decisions_pending.md, D3), not the
paper's protocol; nothing here replaces a published number. PRE-CALIBRATION, fast simulator, assumed constants,
current code, one Windows machine (`environment.json`: Windows 11, Python 3.12.9, numpy 2.4.4, scipy 1.17.1,
scikit-learn 1.8.0). Forecast-driven results depend on the platform (NA-1).

**Provenance.** `scripts/revision/provisional_split.py . <out> --workers=2`, run 21 Nov 2026 13:03Z to 14:22:29Z
(`run.log`) in a separate worktree at commit 31b8c50. `summary.txt` is `python scripts/revision/provisional_split.py
. docs/revision/provisional_split --analyse` on the committed rows (`rows_<split>_<seed>.jsonl`).

**Splits.** Submitted: forecasters fitted on days 0-13; the conformal offset starts at 0 on day 14, the first day
of validation. PROVISIONAL: fitted on days 0-10 (`PrismConfig.forecast_train_days = 11`); the conformal update is
replayed on the out-of-sample days 11-13 (`conformal_warmup_days = 3`); validation (days 14-20) and test (21-27) as
before. Per split and trace (seeds 101-105): PRISM, QuantProv-q90 and the no-recalibration ablation (PRISM on the
raw forecast) tuned on validation by the common rule, then run on the four held-out test weeks.

## Findings (validation beside test, PROVISIONAL)

| Split | Family | Validation: violating windows, cost | Test (20 weeks): violating windows, cost | Weeks within 2% |
|---|---|---|---|---|
| submitted | PRISM | 1.58%, 945.6 | 1.78%, 1150.1 | 12/20 |
| PROVISIONAL | PRISM | 1.55%, 946.8 | 2.11%, 1115.5 | 9/20 |
| submitted | QuantProv-q90 | 1.79%, 922.5 | 1.95%, 1141.8 | 11/20 |
| PROVISIONAL | QuantProv-q90 | 1.64%, 934.3 | 2.23%, 1121.9 | 8/20 |
| submitted | PRISM no recalibration | 1.88%, 914.6 | 2.98%, 1048.1 | 5/20 |
| PROVISIONAL | PRISM no recalibration | 1.85%, 914.3 | 2.97%, 1047.9 | 6/20 |

Costs in USD per week (means over traces); per-trace rows, with each selected setting, in `summary.txt`.

1. **The warm-up works as R4.6 asks.** The offset enters validation at 0.22-0.37 (submitted: 0 by construction),
   close to the level at the start of the test week (0.26-0.46). Calibrated q0.9 coverage on validation rises from
   94.4-98.2% to 98.0-98.7%, now matching the test weeks (98.0-98.6%).
2. **It removes a conservatism the submitted results relied on.** With validation no longer replayed from a cold
   offset, the rule selects cheaper settings: PRISM eps = 0.08, the top of the grid, on all five traces (submitted:
   three). Test cost falls 3.0% (PRISM) and 1.7% (QuantProv-q90), but test compliance falls with it: PRISM meets 2%
   in 9 of 20 weeks (12 submitted) with a pooled rate of 2.11%, above the 2% target; QuantProv-q90 in 8 (11).
   Validation still looks compliant (1.55%, 1.64%): the gap between the validation week and the test weeks widens.
   This agrees with the calibration sweep's initial-offset result (`docs/revision/calibration/`, finding 3).
3. **The no-recalibration ablation does not depend on the split** (selections unchanged; test 2.97-2.98%, 5-6/20
   weeks): its raw forecast is the same apart from the shorter training range. Recalibration is what keeps PRISM's
   test compliance near target under both splits.

**Caveats.** Fitting on 11 days instead of 14 changes every forecast (raw q0.9 coverage stays about 86%). The
selections sit at the grid edge, so the test outcomes depend on the grid as well as the split (KNOWN_ISSUES:
grid-edge audit; weekly compliance). One validation week per trace.
