# R3.2: OptScaler [16] as a published Table V baseline (24 Nov 2026). Result: the prespecified validation-tuned row is INVALID; the published-parameter row is valid

EXPLORATORY. PRE-CALIBRATION. Fast simulator, development traces 101-105, Windows, the regenerated E1 result set
(fd8b01a, whose `src/` equals HEAD 3edc386). Not part of the frozen C1-C3 protocol; seeds 106-130 unused. No AWS call.
The manuscript, the submitted results and the frozen prespecification are unchanged.

`PLAN.md` was fixed and hashed at 13:37:48 UTC, before any run (`sha256sum -c PLAN.sha256` gives OK). It has not been
edited since. Everything decided after the prespecified runs is labelled POST HOC below, and listed in section 7.

## 1. Results first

**Unfavourable: the prespecified validation-tuned row is not a valid baseline.** The common Section V-C rule selected
c* = 0.90-1.00, at or next to the grid's top. The top, 1.0, is the natural limit of a utilization cap. At those
targets the reactive module (Algorithm 1, online linear regression) diverged:
- 16 of 20 tuned test runs end with the stage-mean w_k outside [0.5, 2] times its MLE value;
- this happened in 9 of 75 validation runs, including the selected setting of traces 101 and 105, so the selection
  itself is affected;
- costs reach USD 17,951 +/- 33,750 (bursty) and USD 51.8 million (new spike, one trace at 2.6e8), i.e. meaningless.

That row is not reported as a baseline.

**Mechanism, as far as it was checked** (POST HOC; `outputs/posthoc_divergence_seed101_c1.0.json`, `..._seed103_c0.8.json`):
- in each diverged stage, w_k first left [0.5, 2] x w0. Only afterwards did the unit workload y/x exceed the stability
  bound of Algorithm 1's unnormalized step (eta (y/x)^2 > 2, i.e. y/x > 141 at eta = 1e-4). Then w_k ran away; where
  it went negative the stage was provisioned at 0 for most of the week (1,716 and 1,286 of 2,016 epochs on stage 0);
- feedback minutes with utilization saturated at 1 were only 0.3-5% of the total;
- the equal-weight MLE and the y^2-weighted least-squares ratio differ by only 4-7%
  (`outputs/posthoc_weighting_seed101.json`).

So the cause of the initial excursion is **not established**. Even at the published c* = 0.5, w_k ranges over
0.32-1.20 x w0 within a week (`outputs/stability_published.json`), without reaching the unstable region.

**Valid: OptScaler at its published parameters** (c* = 0.5, alpha = 0.95, eta = 1e-4 from the published selection
rule; a prespecified sensitivity row). Every run is stable: no epoch at P = 0, w_k within 0.32-1.20 x w0, and all 20
costs reproduced exactly. Mean +/- 95% half-width over five traces; in brackets, traces meeting the 2% target:

| | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| OptScaler [16], published parameters: cost (USD) | 1,367 +/- 20 | 1,764 +/- 24 | 1,391 +/- 18 | 1,671 +/- 22 |
| violating windows (%) | 0.12 +/- 0.15 [5] | 0.15 +/- 0.23 [5] | 0.27 +/- 0.33 [5] | 0.18 +/- 0.15 [5] |
| PRISM (same result set): cost (USD) | 981 +/- 93 | 1,273 +/- 125 | 1,076 +/- 104 | 1,270 +/- 123 |
| violating windows (%) | 1.55 +/- 0.97 [3] | 1.31 +/- 0.90 [4] | 2.14 +/- 1.07 [3] | 2.11 +/- 1.32 [2] |
| PRISM minus OptScaler: cost (%) | -28.3 +/- 6.4 | -27.8 +/- 6.7 | -22.7 +/- 7.5 | -24.0 +/- 7.2 |
| violating windows (points) | +1.43 +/- 1.03 | +1.16 +/- 1.04 | +1.88 +/- 1.09 | +1.93 +/- 1.27 |
| traces PRISM cheaper / fewer violating | 5 / 0 | 5 / 0 | 5 / 0 | 5 / 0 |

Every paired interval excludes 0, in both directions. **This is a cost-compliance trade-off, not a dominance:**
- at its published target, PRISM costs 23-28% less than OptScaler (relative to OptScaler's cost; OptScaler costs
  30-40% more than PRISM), and OptScaler has 1.2-1.9 points fewer violating
  windows;
- it meets the 2% target on all 20 trace-scenarios, PRISM on 12;
- the two rows are not at the same compliance, so neither is shown to be the better controller.

It also costs more than QuantProv-q99 in every scenario (1,048-1,386), which meets the target on 17 of 20.

**POST HOC diagnostic, the reactive module closed (eta = 0; the paper's documented "closed state", comparable to its
Madu baseline; not the full OptScaler).** The common rule then selects c* = 1.0 on all five traces, the grid's
natural top.

| | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| OptScaler, eta = 0, c* tuned: cost (USD) | 958 +/- 14 | 1,246 +/- 17 | 987 +/- 11 | 1,195 +/- 16 |
| violating windows (%) | 1.64 +/- 0.57 [4] | 1.52 +/- 0.48 [5] | 2.80 +/- 0.51 [0] | 4.35 +/- 1.19 [0] |
| PRISM minus it: cost (%) | +2.4 +/- 9.2 | +2.1 +/- 9.6 | +9.0 +/- 10.6 | +6.3 +/- 10.2 |
| violating windows (points) | -0.09 +/- 0.61 | -0.21 +/- 0.70 | -0.65 +/- 0.96 | **-2.23 +/- 1.36** |
| traces PRISM cheaper / fewer violating | 3 / 2 | 3 / 2 | 0 / 4 | 2 / 5 |

- Only the new-spike violating-window difference excludes 0: PRISM has fewer violating windows there.
- No cost difference is distinguishable with five traces.
- In the bursty and new-spike scenarios this variant meets the 2% target on 0 of 5 traces, against PRISM's 3 and 2.
- This is POST HOC and is not the published controller, so it supports no claim about OptScaler.

## 2. Validation of the implementation

- **V1, all pass** (`outputs/v1_unittest.txt`, 8 of 8):
  - the closed-form MLE equals numerical maximization of eq. (4);
  - eq. (13) by hand;
  - horizon independence when (6) is not binding;
  - Algorithm 1 by hand, and eta = 0 leaves w_k unchanged;
  - no look-ahead under perturbation of later telemetry and forecasts;
  - the eta selection is the argmin.
- **D1, pass** (`outputs/d1_determinism.json`). Rerunning PRISM's selected setting (eps 0.05) and OnDemand for trace
  101, stationary test week, reproduces the regenerated E1 rows exactly: USD 1,000.886..., 1.19%; USD 865.052...,
  16.67%. So the stored PRISM rows are a matched comparator: same code, platform, traces, forecasts and random
  numbers.
- **V2, reported** (`outputs/analysis.json` → `v2`). The share of minutes with K <= (w + z sigma) y, nominally 0.95:
  - in sample: 0.934-0.939;
  - out of sample (validation week): 0.926-0.942, over 5 traces x 4 stages.

  The normal model of eq. (4) slightly under-covers on this workload.
- **Selected eta** = 1e-4 on every trace (replay losses in `rows.jsonl`); the published value is 2e-4, in other units.

## 3. What was compared

- **Baseline.** OptScaler (D. Zou et al., Proc. VLDB Endow. 17(12):4090-4103, 2024; [16] in the submitted
  manuscript). It was implemented from arXiv 2311.12864v2 (eqs. 3-4 and 11-14, Algorithm 1), because no code is
  released: `scripts/revision/optscaler_policy.py`.
- **What it controls here:** each stage's provisioned concurrency, sized so that the predicted
  provisioned-concurrency utilization stays below c* with probability alpha, from the common median forecast of the
  epoch's peak arrivals. Memory stays at 1024 MB.
- **Mapping.** Assumptions A1-A12 are in `PLAN.md` section 2. The main ones:
  - utilization = min(K, P)/P;
  - w_b = sigma_b = 0;
  - the common GBM median forecast replaces the paper's Flow-attention forecaster, which is not specified;
  - h = 5 minutes;
  - the rate limit is not binding;
  - ceil rounding.
- **Same as every Table V row:** traces, weeks, forecasts, activation lag, decision epoch, price model, SLA metric
  (a 15-minute window violates when record attainment is below 99%), the 2% tuning threshold and the selection rule.
- **Comparator:** the regenerated E1 rows at each policy's validation-selected setting (PRISM eps 0.05, 0.03, 0.08,
  0.08, 0.08). The full table with all rows is in `outputs/table_v_with_optscaler.md`; the post hoc version is in
  `outputs/table_v_with_optscaler_posthoc_eta0.md`.

## 4. Limitations that affect interpretation

1. **Result set.** These are the regenerated Windows values, not the submitted Table V. PRISM's stationary cost here is
   981, against 1,073 submitted. Inserting the row requires the whole table from one result set; the
   reporting-platform decision is open. All values change with the calibrated rerun.
2. **Tuning.** The common rule could not be applied to the published controller: it selects targets at which
   Algorithm 1 diverges. The valid row uses the published c*, so it is not validation-tuned like the other rows. Its
   conservative target explains its high compliance and cost. This is a property of the published setting, not of
   PRISM.
3. **Scope.** OptScaler sets capacity only:
   - no memory; PRISM also chooses one shared memory size hourly;
   - no billing model;
   - no cold-start or deadline term: its SLO is a utilization cap.

   It was designed for long-running services on node clusters, at 30-minute intervals.
4. **Fidelity.** This is an independent implementation with stated mappings. The paper's own results were not
   reproduced, since its Alipay data are internal and its forecaster is unspecified. The forecaster is the common one,
   which the paper's own comparison protocol allows.
5. **Statistics.** Five development traces, wide intervals, no correction for the four scenarios. Fast simulator only.
6. **The hybrid histogram policy [3]** stays unreproduced (`../hybrid_reproduction_r32_20261124/`). Its 25-week
   application-loading decision check is a separate result and is not a cost or SLA comparison.

## 5. Reproduce (from `prism-repro/`; one thread per BLAS library, `PYTHONUTF8=1`)

```bash
venv/Scripts/python -m unittest -v scripts/revision/test_optscaler_policy.py              # V1, 8 tests
O=docs/revision/optscaler_r32_20261124/outputs
venv/Scripts/python scripts/revision/optscaler_comparison.py $O d1                        # D1, about 30 s
venv/Scripts/python scripts/revision/optscaler_comparison.py $O run 101 102 103 104 105   # about 8 min
venv/Scripts/python scripts/revision/optscaler_comparison.py $O analyse
venv/Scripts/python scripts/revision/optscaler_stability_check.py $O                      # published-row stability
# POST HOC
venv/Scripts/python scripts/revision/optscaler_comparison.py $O run_posthoc_eta0          # about 2 min
venv/Scripts/python scripts/revision/optscaler_comparison.py $O analyse_posthoc_eta0
venv/Scripts/python scripts/revision/optscaler_divergence_check.py $O/posthoc_divergence_seed101_c1.0.json 101 1.0
venv/Scripts/python scripts/revision/optscaler_divergence_check.py $O/posthoc_divergence_seed103_c0.8.json 103 0.8
venv/Scripts/python scripts/revision/optscaler_weighting_check.py $O/posthoc_weighting_seed101.json 101
```

The comparator rows are read from the regenerated E1 (`private/regen_20261122/.../raw_regenerated/E1/rows.jsonl`,
Git-ignored), or from `$PRISM_REGEN_E1`. Environment: Windows 11, Python 3.12.9, numpy 2.4.4, scipy 1.17.1,
scikit-learn 1.8.0. Prespecified runs 13:40-13:48 UTC; post hoc 13:50-13:52 UTC.

## 6. Files

- `PLAN.md`, `PLAN.sha256`, `PLAN_HASHED_AT.txt`;
- `TABLE_V_ROW.md`, `REPLY_DRAFT.md`;
- `outputs/`:
  - `rows.jsonl`, `analysis.json`, `table_v_with_optscaler.md`;
  - `rows_posthoc_eta0.jsonl`, `analysis_posthoc_eta0.json`, `table_v_with_optscaler_posthoc_eta0.md`;
  - `d1_determinism.json`, `v1_unittest.txt`, `stability_published.json`;
  - `posthoc_*.json`, run logs;
- `SHA256SUMS`.

## 7. Changes after the plan

The plan file itself is unchanged.
- **POST HOC, after the prespecified results were seen:**
  - the eta = 0 diagnostic;
  - the divergence, weighting and published-row stability checks;
  - the "invalid" verdict for the tuned row, because the plan named no stability criterion. The criterion applied is
    stage-mean w_k outside [0.5, 2] x w0, plus absurd costs.
- **Code:** `optscaler_comparison.py` gained the two post hoc commands. The prespecified commands are unchanged.
- **Not done:**
  - no retuning of the c* grid or the eta rule;
  - no normalized or clipped OLR (not in the paper);
  - no further variants.

## 8. Linux x86-64 reference platform (24 Nov 2026)

**What ran.** The prespecified commands, unchanged (`linux_20261124/run_linux.sh`):
- d1, run, analyse;
- the published-row stability check.

Setting: WSL2 x86-64, Python 3.12.3, the pinned `py312` environment (scikit-learn 1.8.0). The comparator rows are the
Linux E1 rows of the R3.6 release inputs (`linux/E1`, current code). The plan is unchanged; nothing was retuned.

**Checks:**
- **D1 passes.** PRISM (eps 0.08) on trace 101, stationary, reproduces the Linux E1 row exactly (USD 928.508); OnDemand
  matches as well.
- **The published row is stable.** All 20 costs are reproduced, no epoch has P = 0, and w_k stays at 0.32-1.20 x w0.
- **The validation-tuned row diverges again**, so it is still excluded. The selected c* are 0.90-1.00, with absurd
  costs: means up to USD 4.8e9. The Windows finding (section 1) reproduces on Linux. Those costs are not reported.

**Published-parameter OptScaler [16] against PRISM, Linux** (mean +/- 95% half-width over five traces; in brackets,
traces meeting 2%):

| | Stationary | Growth | Bursty | New spike |
|---|---|---|---|---|
| OptScaler: cost (USD) / violating windows (%) | 1,368 +/- 20 / 0.12 +/- 0.15 [5] | 1,765 +/- 24 / 0.15 +/- 0.23 [5] | 1,392 +/- 18 / 0.30 +/- 0.29 [5] | 1,671 +/- 21 / 0.15 +/- 0.13 [5] |
| PRISM | 968 +/- 107 / 1.70 +/- 0.96 [3] | 1,261 +/- 134 / 1.34 +/- 0.91 [4] | 1,053 +/- 109 / 2.35 +/- 0.99 [2] | 1,241 +/- 135 / 2.62 +/- 1.50 [1] |
| PRISM minus OptScaler: cost (%) | −29.3 +/- 7.4 | −28.6 +/- 7.2 | −24.4 +/- 7.9 | −25.7 +/- 7.6 |
| violating windows (points) | +1.58 +/- 1.00 | +1.19 +/- 1.03 | +2.05 +/- 0.94 | +2.47 +/- 1.43 |
| traces PRISM cheaper / fewer violating | 5 / 0 | 5 / 0 | 5 / 0 | 5 / 0 |

**Reading: the same as on Windows.** At its published target, OptScaler meets 2% on 20 of 20 trace-scenarios, against
PRISM's 10 of 20. PRISM costs 24-29% less than OptScaler (OptScaler costs 33-42% more than PRISM, mean of
per-trace ratios), and every paired interval excludes 0. The two controllers sit at different
compliance levels, so this is a trade-off, not a ranking. The paired differences on Linux and
Windows differ by 0.7-1.8 points in cost and 0.03-0.54 points in violating windows. The differences come from
PRISM's platform-dependent forecasts; OptScaler's published row changes by at most USD 1.

Files: `linux_20261124/`.

*[Base corrected 24 Nov 2026: the paired figure is (PRISM − OptScaler) / OptScaler, so PRISM costs 23-28% less than OptScaler; OptScaler costs 30-40% more than PRISM (mean of per-trace ratios). The earlier '23-28% more expensive than PRISM' inverted the base.]*
