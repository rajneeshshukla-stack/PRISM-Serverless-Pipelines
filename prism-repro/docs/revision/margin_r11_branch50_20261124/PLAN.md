# R1.1(b): testing rule E's 50% branch on fresh traces (plan fixed before any new run, 24 Nov 2026)

EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event-level simulator. No AWS. This is a follow-up to
`../margin_r11_fresh_20261124/`, whose rule, criterion and results are unchanged. The confirmatory seeds 106-130, the
development seeds 101-105 and the seeds already used, 131-135, are excluded. This file's SHA-256 is recorded in
`PLAN.sha256` before any new schedule or replay is computed.

## What is held fixed (comparability)

- **Rule E, as locked in `../margin_r11_fresh_20261124/PLAN.md`:** margin 10% if the validation-selected ε ≤ 0.02, and
  50% if ε ≥ 0.03. Margins are applied as P → ceil(P x (1 + m)).
- **Tuning, exactly as before:**
  - fast-simulator schedules from the v1-submitted tree on Linux (Python 3.12.3, pinned packages), the stage that
    reproduced all 30 stored trace-103 schedules;
  - event-level validation replays with the current `des.py` (draw stream 2);
  - `select_by_rule`: the cheapest ε in `GRIDS["PRISM"]` with ≤ 2% violating windows, else the least violating.
- **Test replays:** test-week replays (draw stream 3) of the selected ε's fast-simulator schedules, in the four main
  scenarios.
- **Configuration:** `PipelineConfig()` defaults; `src/` unchanged at 3edc386.
- **Code:** `scripts/revision/margin_fresh_r11.py` (unchanged) for its functions, plus a new driver,
  `scripts/revision/margin_branch50_r11.py`.

## Bounded search (fixed now)

**Candidate seeds:** 136, 137, ..., 165, at most 30. They are processed in ascending order, and the search stops early
once 5 eligible traces are found. Seeds are not skipped or reordered for any reason other than a replay error, which
is reported.

**Eligibility, from validation data alone:** a seed is eligible if `select_by_rule` over its six event-level
validation replays selects ε ≥ 0.03. Test-week outcomes play no part.

**Exact screening, to save replays without changing the outcome of `select_by_rule`:**
1. Replay ε = 0.03, 0.05 and 0.08.
2. If any of them meets 2%: replay 0.005, 0.01 and 0.02, and apply `select_by_rule` to all six.
3. Otherwise, replay 0.005:
   - if it meets 2%, the seed is ineligible, because some ε ≤ 0.02 meets 2% and none ≥ 0.03 does;
   - otherwise, replay 0.01 and 0.02, and apply `select_by_rule` to all six (the least-violating fallback).

**Stage 1 for screening** computes validation-week schedules only. Test-week schedules are computed only for eligible
seeds, at the selected ε.

## Held-out comparison (fixed now)

For each eligible trace, its four test weeks are replayed with margins 0, 10% and 50% on matched inputs: the same
schedule, the same draws and the same configuration.

**Reported:**
- the number of independent eligible traces and of weeks;
- violating-window rates;
- weeks and traces (all four weeks) meeting 2%, each with a 95% Clopper-Pearson interval;
- paired cost overhead against margin 0, as the mean over traces with a t-interval when there are at least 3 traces;
- every failure;
- the full search log: seed, selected ε, eligibility, replays used.

## Criterion (fixed now)

- **Insufficient:** fewer than 3 eligible traces. The branch is then left unvalidated, and only the search results are
  reported.
- **The 50% branch passes** if, on the eligible traces' weeks, the 50% margin meets 2% in at least 90% of weeks
  (rounded up: for example 11 of 12, 14 of 16, 18 of 20). Otherwise it fails.
- **Also reported, without a criterion:** whether 10% would have sufficed on the same weeks, i.e. whether the 50% branch
  is necessary.

**Not claimed:** an AWS margin or an AWS violation rate. These results are open loop, with the assumed constants
(including the modelled 6 s start-up, P3).
