# R2.12(b), R5.M5: the cold-hit (κ) floor under the closed loop. Results (24 Nov 2026)

EXPLORATORY. PRE-CALIBRATION. Closed-loop event-level simulator. Development traces 101-105. Linux x86-64, a clean
clone of 3edc386, pinned `py312`. Confirmatory seeds and C1-C3 untouched. No AWS.

`PLAN.md` was fixed before the run started. Its hash was taken a few minutes after the start, before any test-week
result was seen (`PLAN_HASHED_AT.txt`).

## 1. What ran, and coverage

- **Tuned arms (set K):** A (floor 0.1, the default), B (floor 0.001) and F (κ frozen at 0.1). Each was tuned by the
  common rule with the edge expansion, then run on the four test weeks of each trace.
  - 15 of 15 groups complete, 153 closed-loop weeks, 0 failures.
  - Identical request streams for every arm on each trace and week (`counts_sha256`).
- **Sensitivity (B and F at A's selected eps): 26 of 40 weeks.**
  - The background job was stopped by Claude Code because the **Windows host ran critically low on memory**; the job
    itself did not fail.
  - Missing: trace 104 (both arms, all 4 scenarios), trace 105 (F, all 4), trace 103 (F: growth, new spike).
  - The run is checkpointed, so `bash run_linux.sh` resumes the 14 missing weeks only.
- **Files:**
  - `analysis.json`, `analysis_stdout.txt` (`scripts/revision/closed_loop_exploratory_analyse.py kappa`);
  - `groups/`, `weeks/` (JSON per week, plus `.npz` with per-epoch κ, P and memory);
  - `run.log`, `run_stdout.txt`, `environment.json`, `failures.json`, `bundles.json`.

## 2. Results

**(1) The floor rarely binds under the closed loop, at the eps the rule selects.**

| | Share of epochs with κ <= 0.1 | κ mean | κ 5th percentile |
|---|---|---|---|
| A, tuned test weeks (20) | 0-2.3% (mean 0.19%) | 0.32-0.51 (0.42) | 0.12-0.31 |
| B, tuned test weeks (20) | 0-4.7% (mean 0.33%) | 0.32-0.51 (0.42) | 0.10-0.31 |

The closed-loop rule selected eps 0.01-0.03 for A, against 0.03-0.08 in the fast simulator (E1).

The floor binds at large eps. On the validation weeks, the share of epochs with κ <= 0.1 grows with eps:

| A, eps | 0.005-0.02 | 0.03 | 0.05 | 0.08 |
|---|---|---|---|---|
| Share with κ <= 0.1 | 0-6% | 3-20% | 19-39% | 44-62% |

At eps 0.08, B's unclipped κ falls to 0.04-0.07. A larger budget provisions less, so more requests overflow onto
on-demand environments that are already warm, and the cold-start-to-overflow ratio falls.

**The reviewer's observation (κ at 0.1 in most test epochs) holds for the fast simulator, not for this closed loop.**
Two things combine there: the fast simulator understates event-level cold starts about 3.2-fold (`../kappa_gap/`), and
its tuning selects larger eps.

**(2) Lowering the floor to 0.001 changes almost nothing at fixed eps** (B against A, same eps, same week; 4 traces,
because 104 is missing):
- provisioned vector P differs in 0-7.7% of epochs (mean 0.63%);
- memory identical;
- paired cost −0.07 +/- 0.22% (stationary), 0.00% elsewhere;
- violating windows +0.04 +/- 0.12 points or 0.00.

By the prespecified criterion (A at the floor in under 5% of test epochs; B equal to A in 95% or more of epochs, on
average), **the floor is inactive under the closed loop**.

**(3) Freezing κ at 0.1 (no adaptation) changes nearly every decision** (F against A at A's eps; 2-3 traces, because
of the missing weeks):
- P differs in 96-99.7% of epochs;
- 24-54 fewer provisioned units;
- memory differs in 0.6-11% of epochs;
- cost −7.3% to −9.5%;
- violating windows +0.50 to +0.99 points.

The estimator is therefore active: the measured κ, about 0.42, is far above 0.1, and it makes PRISM provision more.

**(4) Retuned comparisons** (each arm tuned on validation; all 5 traces; paired, arm minus A):

| | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| B: cost / violating windows | +4.86 +/- 6.69% / −0.27 +/- 0.58 | +3.12 +/- 4.12% / −0.12 +/- 0.15 (comparable) | +3.94 +/- 5.72% / −0.36 +/- 0.46 | +3.31 +/- 4.65% / −0.09 +/- 0.25 (comparable) |
| F: cost / violating windows | −2.54 +/- 3.43% / +0.09 +/- 0.36 (comparable) | −2.54 +/- 2.81% / +0.30 +/- 0.35 | −2.16 +/- 3.06% / +0.00 +/- 0.23 (comparable) | −2.35 +/- 2.39% / +0.30 +/- 0.55 |

No cost interval excludes 0. B selects a lower or equal eps on every trace (0.005-0.03 against A's 0.01-0.03), because
on the validation week its lower κ at large eps makes those settings violate more. It ends up costlier and slightly
more compliant, but not distinguishably so. F, retuned, is not distinguishable from A in cost; where compliance is
comparable (stationary, bursty), the differences are −2.5 and −2.2% with intervals including 0.

Tuned-arm means (cost USD / violating windows % [weeks meeting 2%], 5 traces):
- A: 1,236 / 1.93 [3], 1,594 / 1.76 [5], 1,381 / 2.20 [2], 1,595 / 1.67 [4];
- B: 1,297 / 1.67 [4], 1,644 / 1.64 [5], 1,436 / 1.85 [4], 1,648 / 1.58 [5];
- F: 1,204 / 2.02 [3], 1,553 / 2.05 [2], 1,352 / 2.20 [2], 1,558 / 1.96 [4].

## 3. What this answers

**R2.12, "operating conditions in which the estimator remains active":** the closed-loop event-level evaluation at the
eps the common rule selects (0.01-0.03). There κ averages about 0.42 and is at the floor in about 0.2% of test
epochs. It is pinned at the floor at large eps, and in the fast simulator.

**R2.12, "whether this component is necessary under the default configuration":**
- At fixed eps the adaptive estimate matters: it moves almost every decision, and freezing it at 0.1 saves 7-9% at
  0.5-1.0 more points of violating windows.
- Once eps is retuned, neither freezing κ nor lowering the floor gives a cost difference distinguishable from 0 (five
  traces).
- So the estimator sets the operating point, but its effect on the cost-compliance outcome is absorbed by the eps
  tuning. It is not shown to be necessary for the tuned result. This is a null, and it is reported as one.

**R5.M5 (the floor, not the measured ratio, may exclude the no-provisioning option):**
- Under the closed loop the measured κ (0.32-0.51) is far above the floor, so the floor is not what excludes any
  option.
- The reviewer's ratio of about 0.02, and κ at its floor, are fast-simulator quantities.

**Proposal B3** (the fast-simulator floor comparison) is not superseded: it answers a different question, in a
different simulator. Its closed-loop counterpart is this study. The proposal needs a closed-loop sentence; see
`notes/manuscript_proposals.md` M20.

## 4. Limits

- Five development traces.
- The F sensitivity covers 2-3 traces until the missing weeks are run.
- PRE-CALIBRATION: the cold-start ratio depends on the assumed 6 s start-up.
- One deadline (14.5 s).
- Exploratory, not part of the frozen protocol.
