# R3.2 alternative route: OptScaler [16] as a published Table V baseline. Plan fixed before any comparative run (24 Nov 2026)

EXPLORATORY. PRE-CALIBRATION (assumed `PipelineConfig()` constants). Fast simulator, development traces 101-105,
Windows. Not part of the frozen C1-C3 protocol; the confirmatory seeds 106-130 are not used. No AWS call. The
manuscript, the submitted results and the frozen prespecification are not changed.

This file is hashed in `PLAN.sha256` before the implementation is run on any validation or test week. Anything
changed after that is listed under "Changes after the plan" at the end, with the reason.

## 1. Why this baseline, and why the hybrid histogram route is not used

**The request.** Reviewer 3, comment 2: "Published baselines. Section V(C) uses no published controller. Please add,
for example, the hybrid histogram policy of reference 3 to Table V." Question 4: "The closest published controllers
are discussed but not used as comparison methods." "For example" names the hybrid histogram policy as one instance;
the request is for a published controller in Table V.

**Reference [3]** is confirmed from the submitted manuscript (Atypon ReX PDF of the initial submission, generated 31
Oct 2026): M. Shahrad et al., "Serverless in the wild: Characterizing and optimizing the serverless workload at a
large cloud provider," USENIX ATC 2020, pp. 205-218.

**The hybrid histogram route stays blocked** (`../r32_blocker_20261124/NOTE.md`, `../hybrid_reproduction_r32_20261124/`):
the locked reproduction failed A3 and B1; the ARIMA trigger, the minute-level conversion and the full workload are
not published (arXiv v1 and v2, checked on 24 Nov 2026, give no threshold either); and the policy decides whether an
application is loaded, not how many instances run. On every Table V test week each stage is invoked in every
minute, so no idle time is out of bounds and ARIMA would never be used there.

**Candidates checked (closest published controllers, manuscript Table I and Section II):**

| Controller | Code | Can it be implemented from the paper and mapped to per-stage provisioned concurrency without invented behaviour? |
|---|---|---|
| RobustScaler [14] (ICDE 2022) | none found | No. One instance per query, never reused; NHPP fit hyperparameters, start-up distribution and planning frequency not given |
| MPC pre-warming [19] (MASCOTS 2025) | none found | No. Horizon, control interval, all seven objective weights and forecaster settings not given |
| DROPS [5] (EuroSys 2026) | none found | Not assessable: the publisher refused the automated fetch (HTTP 403) |
| OptScaler [16] (PVLDB 17(12), 2024) | none found | **Yes, with stated mappings.** The controller (eqs. 3-4, 11-14; Algorithm 1) is fully specified with its published parameter values, and the paper states that its optimizers are compared "given the same input of the prediction results", so a common forecaster can be plugged in |

**Selected: OptScaler** (D. Zou et al., "OptScaler: A collaborative framework for robust autoscaling in the cloud,"
Proc. VLDB Endow. 17(12):4090-4103, 2024; text from arXiv 2311.12864v2, PDF SHA-256 3bafb02f..., kept privately).
It is cited as [16] in the submitted manuscript, is evaluated on the Azure Functions trace, and controls capacity
(horizontal scaling under a chance constraint), which is Table V's quantity. No code is released, so this is an
independent implementation from the paper.

## 2. What OptScaler controls, and the pipeline mapping

**Published controller.** Per cluster of nodes x serving workload y:
- reactive estimator (3)-(4): utilization c = w_b + y w_k / x + eps, eps ~ N(0, (sigma_b + y sigma_k / x)^2), fitted by
  maximum likelihood on history with non-negative parameters, then w_k adjusted online by OLR (Algorithm 1:
  e = c_hat - c, w_k <- w_k - eta e y/x);
- optimization (5)-(10) with chance constraint (11), P{c* >= c^d} >= alpha, whose deterministic form is (13):
  x^d >= m^d / (c* - w_b - psi^-1(alpha) sigma_b), m^d = max_{j in {d, d+1}} (psi^-1(alpha) sigma_k + w_k) y^j, y^j the
  peak predicted workload in interval j; objective (14) max sum m^d / x^d; rate limit (6) |u^d| <= (h/tau) s;
  bounds (10); "the solution u^1 can be rounded for implementation";
- published values: c* = 0.5, alpha = 0.95, h = 30 min (h = 10 and 60 also tested), tau = 5 min, s = 4, D in {1, 11},
  eta = 2e-4 "selected by minimizing the cumulative loss on the training data".

**Mapping (each item is a stated assumption, applied identically on every trace):**

| ID | OptScaler | This pipeline | Reason |
|---|---|---|---|
| A1 | cluster, node count x | each stage s separately (one LRA per cluster), x = P_s, its provisioned concurrency | Table V's decision variable |
| A2 | CPU utilization c | provisioned-concurrency utilization, observed c = min(K, P)/P, K the simulator's per-minute peak concurrency | the platform's utilization metric for this resource; K is the simulator's only concurrency telemetry |
| A3 | w_b, sigma_b | fixed at 0 | an idle provisioned environment has zero utilization; with P not observed in history they are not identifiable |
| A4 | MLE initialization | closed-form MLE of K_t = w_k y_t + e_t, e_t ~ N(0, (sigma_k y_t)^2) over all pre-week minutes with y_t > 0 (the history Static uses) | eq. (4) with A3; c x = K below saturation |
| A5 | proactive forecast y^d | the common calibrated GBM forecast of the epoch's peak per-minute arrivals, median quantile (`q_cal[k, 1]`), the same forecasts every Table V row uses | the paper compares optimizers on the same prediction input; its own quantile level is not stated and its baselines use 0.5 |
| A6 | interval h, max over {d, d+1} | h = 5 min, the decision epoch of every Table V row; m uses y^k only | the common forecast already targets the controlled window 5k..5k+4 under the 2-minute activation lag; no forecast for k+1 exists at decision time |
| A7 | rate limit (6), bounds (10) | not binding: X^min = 0, no X^max | no Table V row has an actuation rate limit; the node units of s have no counterpart |
| A8 | horizon D | D = 1 (published setting) | with (6) not binding, (13)-(14) decouple across d, so u^1 is the same for any D (checked in V1c) |
| A9 | rounding | ceil, P_s = ceil(m / c*) | rounding down would violate (13) |
| A10 | OLR feedback | at each decision, Algorithm 1 over the visible in-week minutes since the previous decision (T <= 5), using the applied P, observed arrivals and observed utilization; minutes with P = 0 give no utilization and are skipped | Algorithm 1 with T > 1 |
| A11 | eta tuning | grid {0, 1e-5, 1e-4, 2e-4, 1e-3, 5e-3}; per trace, minimize the cumulative squared OLR loss over the 14-day forecaster training split, replayed with x_t = max(1, ceil((w_k + z sigma_k) y_t / 0.5)) at the published c* = 0.5; ties to the smaller eta | the paper's rule; history has no provisioned level, so the replay provisions at the published target |
| A12 | memory | default 1024 MB, like every baseline | OptScaler does not set memory |

**What OptScaler does not do here:** it sets no memory size (PRISM shares one memory size across stages, chosen
hourly), uses no billing model, and does not reason about cold-start latency or deadlines; its SLO is a utilization
cap. These are differences in the published controller, not in the comparison.

## 3. Validation of the implementation (before any Table V week is run)

V1, required, all must pass (`scripts/revision/test_optscaler_policy.py`, hand-calculated):
- V1a: the closed-form MLE equals a numerical maximization of the eq. (4) likelihood (scipy) on a small sample,
  to 1e-5 relative;
- V1b: the decision equals eq. (13) with A3 and A9 on a worked example;
- V1c: for a 3-interval problem with (6) not binding, brute-force integer maximization of (14) under (13) gives the
  same first decision as D = 1;
- V1d: one OLR step equals Algorithm 1 by hand; eta = 0 leaves w_k unchanged ("simulates the closed state of the
  reactive module");
- V1e: no look-ahead: perturbing every telemetry value after the visible minute 5k - 2, and every forecast after
  epoch k, leaves decision k unchanged;
- V1f: the eta selection returns the grid value with the smallest replayed loss.

V2, reported, no pass/fail: the documented behaviour of (11), the share of minutes with K_t <= (w_k + z sigma_k) y_t,
in sample (fitting minutes) and out of sample (validation week, realized arrivals), per trace and stage. Values far
below 0.95 would mean that the estimator's normal model misfits this workload. That would be a finding about the
published controller on this workload, not an implementation error.

D1, required: rerunning PRISM's validation-selected setting, and OnDemand, for trace 101 on the stationary test week
in this tree gives cost and violating-window rate equal to the regenerated E1 rows (`private/regen_20261122`, fd8b01a,
whose `src/` equals HEAD 3edc386) to 1e-9. This shows that the stored PRISM rows are a matched comparator.

## 4. Tuning, workloads and runs

- Traces 101-105 (development); the validation week (stationary, week 3) for tuning; the four test weeks
  (stationary, growth, bursty, new spike, week 4); common random numbers as in E1.
- c* grid: 0.30, 0.35, ..., 1.00 (15 values; the published 0.5 is on it). Selection by the common Section V-C rule
  (`experiment.select_by_rule`): the cheapest setting with a violating-window rate <= 2% on validation, otherwise the
  least violating. alpha = 0.95 fixed (published). eta per A11.
- Runs: 15 validation runs per trace, then the four test weeks at the selected c*, and at the published c* = 0.5 as a
  sensitivity row. 115 runs in total.
- Comparator rows: PRISM and the other Table V rows from the regenerated E1 on Windows (fd8b01a), at their own
  validation-selected settings, recomputed with `select_by_rule`.

## 5. Metrics and reporting

- Per scenario: cost (USD) and violating-window rate (%), mean +/- 95% half-width over five traces (t, 4 df), and the
  traces meeting the 2% target, as in Table V. Reported together, never one without the other.
- Paired per trace, PRISM minus OptScaler: cost (%) and violating windows (points), mean +/- 95% half-width, and the
  traces in which PRISM was cheaper / had fewer violating windows, as in Table VI.
- Interpretation rule: a difference is called a difference only if its interval excludes 0; otherwise "not
  distinguishable with five traces". No claim of superiority, equivalence or a tie is made. A cost comparison is
  qualified when the two rows' compliance differs.
- Also reported: the selected c* and eta per trace, mean provisioned level, cold-start ratio, V2 coverage.
- Unfavourable or inconclusive results are reported as they stand.

## 6. What this comparison can and cannot support

It can support a statement about one published capacity controller, implemented from its paper with the mappings in
section 2, against PRISM under Table V's protocol, on five development traces, pre-calibration. It cannot support a
claim that OptScaler was reproduced (no reproduction of the paper's own results is attempted: its Alipay data are
internal and its forecaster is not specified), nor any claim about the hybrid histogram policy. The 25-week
application-loading decision check of the hybrid route stays separate and is not a cost or SLA comparison.
