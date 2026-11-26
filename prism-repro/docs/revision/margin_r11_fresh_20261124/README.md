# R1.1(b): the trace-103 failures diagnosed, a revised margin rule, and an incomplete fresh-trace validation (24 Nov 2026)

EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event-level simulator. No AWS. The confirmatory seeds 106-130 and
`../PRESPECIFICATION.md` are untouched. `PLAN.md` was fixed before any fresh run (SHA-256 in `PLAN.sha256`).

## 1. Result first: the locked criterion passes, but only rule E's 10% branch was exercised

`result.txt` and `result.json` are produced by `margin_fresh_r11.py analyse`. `PLAN.md` still verifies against
`PLAN.sha256`.

**History of the run.** The first run, with five parallel processes, was stopped for low memory after all 30 validation
replays. The 60 test-week replays were then run on 24 Nov 2026, one seed at a time, resuming from the saved rows. All
20 fresh weeks are eligible, and every replay completed.

| Margin (fresh seeds 131-135, 20 test weeks) | Weeks meeting 2% | 95% Clopper-Pearson | Cost of the margin, mean (range) |
|---|---|---|---|
| 0 | 16 / 20 | 56-94% | — |
| **Rule E (prespecified)** | **20 / 20** | **83-100%** | **+6.1% (+5.4 to +6.6%)** |
| Rule U (uniform 50%) | 20 / 20 | 83-100% | +29.2% (+25.8 to +31.8%) |

**The prespecified criterion is met:** at least 18 of 20 fresh weeks meet 2% under rule E. It passes.

**Failures at margin 0:**
- seed 133 bursty, growth and new spike, each 2.08%;
- seed 134 new spike, 2.08%.

All four meet 2% at the 10% margin. Seed 133 is the fresh trace with 103-like validation slack (ε = 0.02, 0.07 points
below 2%).

**Only the 10% branch was exercised.**
- All five fresh traces selected ε ≤ 0.02: 0.01, 0.005, 0.02, 0.005 and 0.005.
- So on these seeds rule E is identical to a uniform 10% margin.
- **The 50% branch (ε ≥ 0.03) is unvalidated.** It rests on one development trace (103), and it stays an open item
  until fresh traces that select ε ≥ 0.03 are tested.
- Further seeds must not be chosen by their outcome.

**Seed 135** meets 2% at no ε on its validation week. The selection rule falls back to the least violating budget
(0.005, 2.23%). Its four test weeks still meet 2% at the 10% margin.

## 2. Reproduction

`../margin_r11_20261123/margin_rule.py`, rerun, is byte-identical to `../margin_r11_20261123/result.txt`. Leave one
trace out gives 16 of 20 held-out weeks meeting 2%. All four failures are trace 103, at the 10% margin chosen from the
other traces: 2.08-2.83%.

## 3. Diagnosis (PLAN.md section 2)

**Supported by the logs:**
- **Source:** `../event_severity_resumed_20261122/rows_R24_*.jsonl` and `../../../results/raw/E12/E12_seed*.jsonl`.
- **103's selection had the least slack.** Its event-level validation selection chose the largest risk budget
  (ε = 0.03; the other traces chose 0.005-0.02), and met 2% by the smallest slack (0.07 points; others 0.21-0.51).
- **103's validation week was the easiest.** It was the lowest or second-lowest at every ε.
- **The test-week shift was largest on 103:** +1.38 points (others −0.26 to +0.41).
- **More overflow:** 1.10-1.17% on 103, against 0.32-0.86% elsewhere.
- **Initialisation is the cause.** With instantaneous initialisation, all 20 weeks have 0.00% violating windows.

**Hypotheses, not shown:**
- H1: fewer random bursts in 103's validation week;
- H2: the selection rule rewards an easy validation week with a riskier ε;
- H3: the effect persists under calibrated constants.

## 4. The revised rule (defined before testing)

**Rule E:** margin 10% if the selected ε ≤ 0.02, and 50% if ε ≥ 0.03.
- It uses only what the operator knows at decision time: the validation-selected ε.
- Trace 103 is development evidence for the 50% branch. It is the only development trace in that branch.

**Comparator, rule U:** a uniform 50%.

## 5. Checks of the pipeline used for fresh traces

- **The current code does not reproduce the stored schedules.** On Windows the difference is up to 41 units of P,
  with 2.38% against 1.93% validation violating windows; on Linux it is up to 23 units, with 2.23% against 1.93%
  (`codepath_check_current_code_windows.json`; the Linux run of the current code is reported here only).
- The reason is a code change, not only the platform: since f119bee, PRISM's default risk model is Erlang-B, and the
  stored E1 rows come from the v1-submitted code.
- **Stage 1 (schedules)** therefore uses the v1-submitted tree on Linux (Python 3.12.3, the pinned packages). It
  reproduces all 30 stored trace-103 schedules byte for byte (`codepath_check_stage1_v1_linux.json`).
- **Stage 2 (event-level replay)** uses the current `des.py`, as the stored margin rows did. It reproduces the stored
  E12 validation rate exactly (1.9345%; cost within USD 0.0012; `codepath_check_stage2.json`).

## 6. Fresh traces 131-135: what was obtained

These are validation-week replays, event level, at every ε (`rows_<seed>.jsonl`, `fresh_selection.json`):

| Seed | Selected ε | Its validation rate | Slack to 2% | Rule E margin |
|---|---|---|---|---|
| 131 | 0.01 | 1.786% | 0.21 | 10% |
| 132 | 0.005 | 1.339% | 0.66 | 10% |
| 133 | 0.02 | 1.935% | 0.07 (103-like) | 10% |
| 134 | 0.005 | 1.637% | 0.36 | 10% |
| 135 | 0.005 | **2.232%** (no ε meets 2%; the least violating is selected) | −0.23 | 10% |

**The test weeks** were run one seed at a time (`stage2_resume_<seed>.log`), and the result is in section 1. The
commands, for a rerun from scratch:

```
venv/Scripts/python scripts/revision/margin_fresh_r11.py docs/revision/margin_r11_fresh_20261124 run 131
(... 132, 133, 134, 135, one after another)
venv/Scripts/python scripts/revision/margin_fresh_r11.py docs/revision/margin_r11_fresh_20261124 analyse
```

## 7. What stays open

- **R1.1(b):**
  - For PRISM configurations whose validation-selected ε ≤ 0.02, a 10% margin passed its prespecified fresh-trace
    test (20 of 20 weeks, +6.1% cost). This is open-loop simulation with assumed constants, not a production margin.
  - The ε ≥ 0.03 branch (50%) is unvalidated.
  - A recommendation for operators still needs the calibrated closed-loop evaluation and a live check.
- **R1.1(a):** the size of violations on AWS Lambda needs the live run (R6.1).
- **Not claimed:** any production margin, and any AWS violation estimate.
