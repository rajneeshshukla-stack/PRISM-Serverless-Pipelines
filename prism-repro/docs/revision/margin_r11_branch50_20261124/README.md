# R1.1(b): the search for traces that exercise rule E's 50% branch (24 Nov 2026). Result: INSUFFICIENT, so the branch stays unvalidated

EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event-level simulator. No AWS.
- **Excluded seeds:** 101-105 (development), 106-130 (confirmatory, frozen) and 131-135 (already used).
- **Fixed before any new schedule or replay:** `PLAN.md`, with its SHA-256 in `PLAN.sha256`; it still verifies.
- **Unchanged and reused:** the rule, the tuning procedure and the simulator configuration of
  `../margin_r11_fresh_20261124/`.

## Result

**Search:** seeds 136-165, the full bound of 30 seeds, using 126 event-level validation replays (`search_log.jsonl`,
`screen_rows.jsonl`).

**Eligible** (the validation selects ε ≥ 0.03): **2 of 30**, seeds **152** and **162**, both at ε = 0.03. That is
6.7% (95% Clopper-Pearson 0.8-22.1%).

| Seed | Validation violating %, by ε (0.005, 0.01, 0.02, 0.03, 0.05, 0.08) | Selected |
|---|---|---|
| 152 | 0.74, 1.04, 1.49, **1.94**, 2.23, 2.38 | 0.03 |
| 162 | 0.89, 1.34, 1.49, **1.79**, 2.83, 4.02 | 0.03 |
| 149 | 2.23, 2.08, 2.83, 3.42, 4.02, 5.21 (no ε meets 2%; least violating) | 0.01 |
| 27 others | ε ≥ 0.03 does not meet 2%, and ε = 0.005 does | ≤ 0.02 |

**Prespecified criterion:** at least 3 eligible traces are needed for a verdict. **INSUFFICIENT (2 < 3): the 50%
branch is left unvalidated.**

As the plan requires, only the search results are reported. The test-week schedules of seeds 152 and 162 were computed
(`sched_test_seed152.npz`, `sched_test_seed162.npz`), but their held-out test weeks were not replayed or inspected
(`test_rows.jsonl` does not exist).

## What follows

- **The ε ≥ 0.03 branch is rare** under the tuning procedure: 1 of 5 development traces and 2 of 30 fresh ones select
  it.
- **Validating it at the plan's minimum of 3 traces** needs a larger, again prespecified search, or a design that does
  not depend on rare selections.
- **Any held-out replay of 152 and 162** would be descriptive only and could not validate the branch under this plan.
- **The verified 10% finding stands within its tested scope** (`../margin_r11_fresh_20261124/`): validation-selected
  ε ≤ 0.02, 5 fresh traces, 20 of 20 weeks, open loop, pre-calibration.

## Files

- `PLAN.md`, `PLAN.sha256`
- `search_log.jsonl`, `screen_rows.jsonl`
- `screen.log`, `screen_last.out`, `stage1_val.log`, `stage1_test.log`
- `sched_val_seed*.npz`, `sched_test_seed{152,162}.npz`
- `result.txt`, `result.json`
- `../../../scripts/revision/margin_branch50_r11.py`
- `SHA256SUMS`
