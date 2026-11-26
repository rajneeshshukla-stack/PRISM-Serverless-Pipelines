# R5.M1(e), R2.2(b): every baseline family under the closed loop. Results (24 Nov 2026)

EXPLORATORY. PRE-CALIBRATION. Closed-loop event-level simulator with exact per-request attainment. Development traces
101-105 only; the confirmatory seeds 106-130 and the frozen C1-C3 are untouched and separate. No AWS.

`PLAN.md` was hashed at 15:57:49Z, before any comparator run. The first comparator week ran at 17:33Z.

## 1. What ran, and verification

| Set | Families | Groups | Weeks | Failures |
|---|---|---|---|---|
| K (arm A, reused) | PRISM | 5 | (from the κ study) | 0 |
| CMPe | QuantProv-q90, Reactive, PredHead+S (`PredHead+hyst`) | 15/15 | 223 | 0 |
| CMPb | PredHead, QuantProv-q99, Static, Scheduled | 20/20 | 277 (211 run + 66 resumed from checkpoint) | 0 |
| OD | OnDemand (no parameter) | — | 20/20 | 0 |

**Matching:** the request streams are identical for every family on each trace and week (`counts_sha256`); the
validation week uses draw key 2 and the test weeks key 3. The duplicate check passed.

**Provenance** (`environment.json`, 5 run segments): all on commit 3edc386 with `src/`, `experiments/` and `tests/`
clean; C1-C3 driver 3f909dc9...; the exploratory wrapper `scripts/revision/closed_loop_exploratory.py`; Linux x86-64;
`py312` with scikit-learn 1.8.0.

**Tuning:** the common rule with the prespecified edge expansion over `GRIDS_WIDE`. Expansions occurred for
QuantProv-q90 (1 trace), PredHead+S (1), PredHead (2, up to 3.0) and Scheduled (5). **No final selection is at a grid
edge.**

**Interruption:** Claude Code stopped the first CMPb attempt (3 workers) under host memory pressure. The checkpoints
were confirmed: 66 complete weeks, no partial files. The run resumed with 2 workers as authorised, and reused every
saved week (`run_stdout.txt`).

**Files:**
- `analysis.json`, `analysis_stdout.txt` (`scripts/revision/closed_loop_exploratory_analyse.py families`);
- `groups/`, `weeks/` (week JSON plus per-epoch `.npz`);
- `run.log`, `environment.json`, `failures.json`, `bundles.json`, `run_linux.sh`.

## 2. Results

Cost (USD/week) / violating windows (%) [weeks meeting 2%], mean +/- 95% half-width over 5 traces:

| Family | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| PRISM | 1,236 +/- 100 / 1.93 +/- 0.67 [3] | 1,594 +/- 92 / 1.76 +/- 0.50 [5] | 1,381 +/- 53 / 2.20 +/- 0.48 [2] | 1,595 +/- 91 / 1.67 +/- 0.48 [4] |
| QuantProv-q90 | 1,248 +/- 148 / 1.96 +/- 0.87 [2] | 1,641 +/- 188 / 1.73 +/- 0.79 [3] | 1,423 +/- 138 / 2.08 +/- 0.82 [2] | 1,653 +/- 183 / 1.67 +/- 1.08 [4] |
| Reactive | 1,759 +/- 55 / 1.43 +/- 0.77 [4] | 2,250 +/- 72 / 1.73 +/- 0.61 [4] | 1,841 +/- 66 / 1.58 +/- 0.50 [4] | 2,165 +/- 76 / 1.76 +/- 0.78 [4] |
| PredHead+S | 1,146 +/- 122 / 2.44 +/- 1.17 [2] | 1,495 +/- 158 / 2.53 +/- 1.12 [2] | 1,180 +/- 121 / 4.35 +/- 1.50 [0] | 1,415 +/- 148 / 3.96 +/- 3.45 [1] |
| PredHead | 1,088 +/- 117 / 2.83 +/- 1.03 [0] | 1,417 +/- 153 / 2.74 +/- 0.76 [0] | 1,120 +/- 124 / 4.97 +/- 1.36 [0] | 1,351 +/- 140 / 10.42 +/- 7.79 [0] |
| QuantProv-q99 | 1,350 +/- 107 / 1.13 +/- 0.56 [5] | 1,777 +/- 125 / 1.07 +/- 0.46 [5] | 1,545 +/- 87 / 1.10 +/- 0.61 [5] | 1,794 +/- 92 / 0.83 +/- 0.53 [5] |
| Static | 1,534 +/- 85 / 0.89 +/- 0.74 [5] | 1,695 +/- 84 / 4.43 +/- 1.68 [0] | 1,552 +/- 84 / 1.28 +/- 1.03 [4] | 1,666 +/- 84 / 3.21 +/- 2.01 [0] |
| Scheduled | 1,450 +/- 47 / 0.80 +/- 0.38 [5] | 1,612 +/- 46 / 6.34 +/- 1.68 [0] | 1,468 +/- 44 / 1.55 +/- 0.71 [4] | 1,583 +/- 47 / 3.96 +/- 1.10 [0] |
| OnDemand | 874 +/- 13 / 33.30 +/- 1.21 [0] | 1,142 +/- 15 / 34.46 +/- 0.67 [0] | 903 +/- 10 / 34.02 +/- 1.37 [0] | 1,099 +/- 15 / 52.35 +/- 1.03 [0] |

**R5.M1(e), new spike.** Paired PRISM minus comparator (cost %, relative to the comparator; violating windows,
points; 5 traces, df 4; in parentheses, traces in which PRISM is cheaper / has fewer violating windows):

| Comparator | Cost | Violating windows | Reading |
|---|---|---|---|
| QuantProv-q90 | −3.19 +/- 5.50% (4) | −0.00 +/- 0.67 (3) | Not distinguishable in cost; compliance is not within the +/-0.5 comparability band, so no tie is claimed |
| Reactive | **−26.32 +/- 3.08%** (5) | −0.09 +/- 0.81 (2) | PRISM cheaper on every trace, at similar mean compliance. The interval is wider than +/-0.5, so the comparison is formally confounded |
| PredHead+S | **+13.11 +/- 7.95%** (0) | −2.29 +/- 3.13 (5) | PRISM costlier on every trace and has fewer violating windows on every trace. The violating-window interval includes 0. A cost-compliance trade-off, not a ranking |

**R2.2(b), the other families,** read across the four scenarios:
- **QuantProv-q99:** PRISM 8-11% cheaper, with 0.7-1.1 more points of violating windows; QuantProv-q99 meets 2% on 20
  of 20.
- **PredHead (unsmoothed):** PRISM 13-24% costlier, with 0.9-8.8 fewer points; PredHead meets 2% on 0 of 20.
- **Static and Scheduled:** costlier than PRISM in every scenario except Scheduled in the new spike (+0.77 +/- 4.40%,
  not distinguishable). They meet 2% in stationary (5 of 5) and bursty (4 of 5), but on 0 of 5 traces in growth and
  new spike, where PRISM has 1.6-4.6 fewer points. In stationary, PRISM is 15-19% cheaper, with 1.0-1.1 more points.
- **OnDemand:** violates 33-52% of windows.

## 3. Consistency with earlier evidence

- **C2** (closed loop, 25 confirmatory traces, Windows): PRISM 26.5% cheaper than Reactive at similar compliance.
  Here: 25-30% on 5 development traces. Consistent.
- **C1:** PRISM against QuantProv-q90, +0.30% [−1.42, +2.01]. Here −0.7 to −3.2%, all intervals including 0.
  Consistent: not distinguishable.
- **Fast simulator (Table V, Linux):** new spike PRISM 2.62%, PredHead+S 4.02%, PredHead 7.62%. The closed loop
  keeps the same ordering of compliance (1.67 / 3.96 / 10.42%). The levels differ because each family is retuned and
  evaluated at event level: PRISM's rate is lower here, and PredHead's higher.
- The closed-loop tuning selects tighter settings than the fast simulator for every forecast-driven family (for
  example PRISM eps 0.01-0.03 against 0.03-0.08). So costs here are higher than in Table V and are not comparable
  with it.

## 4. Limits

- Five development traces (df 4, wide intervals). One deadline (14.5 s). PRE-CALIBRATION constants.
- MemAdapt-q90 was not run (PLAN.md): at 14.5 s its outcomes equal QuantProv-q90's.
- No matched-compliance frontier.
- Exploratory, separate from the frozen C1-C3.
