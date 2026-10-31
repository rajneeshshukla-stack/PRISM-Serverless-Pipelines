# Assumptions and decisions register

Every item below is a choice made in this **independent reimplementation** where the manuscript is silent or ambiguous. None was tuned to reproduce manuscript numbers. "Effect" states the expected effect on conclusions; "Sens." says whether a sensitivity analysis exists or is needed. Requirement IDs (R..) refer to a specification audit of the earlier manuscript version that is not part of this release; section, equation and table numbers refer to that version. The paper's Supplementary Table S1 lists the final values.

## Latency, risk and cost model

| ID | Missing / ambiguous | Selected interpretation | Why reasonable | Alternatives | Effect | Sens. |
|---|---|---|---|---|---|---|
| D01 (R02) | Meaning of "log-normal shape 0.30" and of stated means | σ of the underlying normal; distributions parameterised so the stated value is the *mean* | Reproduces Table 3 exactly: v_w = 25.1 % / 0.22 % / <0.01 % and ρ(1024) = 0.531 (tests `test_C06`) | σ as coefficient of variation; stated value as median | Other choices would not reproduce Table 3 | Not needed (validated) |
| D02 (R07, R23) | Intensity factor of the fast simulator | Median-one log-normal Z = exp(σz), σ = 0.148, derived from c_eff's factor 1.011 = exp(σ²/2) | The 0.88√c term equals the normal-approximation mean excess of the upper 45 % (φ(z₀.₅₅)/0.45 = 0.8796); test `test_C05` shows the simulator's sampling and c_eff agree within 2 % | Mean-one intensity | Small; affects overflow levels only | Not needed |
| D03 (R09) | Which stage is cold for ρ(m) | Irrelevant: initialisation time does not depend on the stage and latency is a sum | — | — | None | — |
| D04 (R11) | Value of r (mean/peak in the activation window) | Estimated per trace from the training period (≈0.79) | Manuscript says it is measured on history, ≈0.8 | Fixed 0.8 | Negligible | No |
| D05 (R13) | Decision timing | Decision k at week minute 5k−2 observes N_≤t, capacity active for minutes 5k…5k+4 = t+2…t+6 | Matches Eq. 7 offsets and the 2-min lag exactly | — | — | — |
| D23 | Whether PRISM-EB uses c_eff | Erlang-B at the mean load of the forecast peak (no c_eff) | Erlang-B is exact for Poisson arrivals at the mean load; c_eff was introduced to correct the occupancy statistic | Erlang-B at c_eff | Direction: c_eff would be more conservative | No (E11 only) |
| D28 | Billed durations in the fast simulator | Mean durations d_s(m) per execution (expected GB-s); the event-level simulator bills the drawn durations | Fast simulator has no per-request durations | — | Costs equal in expectation | Checked by E9 cost agreement |

## Forecasting and calibration

| ID | Missing / ambiguous | Selected interpretation | Why | Alternatives | Effect | Sens. |
|---|---|---|---|---|---|---|
| D06 (R14) | Rolling-std window; exact previous-day count feature | std over 15 min; previous-day features = realised window peak and count at t−1440, each over the previous day's floored 60-min level, plus level ratio | Closest literal reading of §4.1 | std over 5 or 60 min; window-mean count | Small | Feature-group ablation (E7) |
| D07 (R15) | GBM hyper-parameters | `max_iter=200, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40`, no early stopping, `random_state=0`; one sample per training minute (days 2–14; day 1 lacks previous-day features) | Fixed a priori, conventional values; deterministic | sklearn defaults; tuned | Affects forecast accuracy levels | No (not tuned on any evaluation data) |
| D08 (R16) | Conformal initial state / continuity | s = 0 at the start of the validation week; updates run continuously through validation and test; every test scenario continues from the identical validation-week state | Continuous operation; no in-sample residuals (training ends at day 14) | Reset at each week | Small, early-week only | No |
| D09 (R18) | Placement of 100 stratified levels; tails | p_i = (i+0.5)/100; above 0.999 linear with the 0.99–0.999 slope; below 0.1 linear with the 0.1–0.5 slope, floored at 0 | Deterministic, symmetric stratification | p_i = i/101 etc. | Negligible | No |
| D18 (R33) | Reference forecasters | Seasonal-naive = realised window peak 24 h earlier; last-5-min max; EWMA α = 0.1/min; ratio quantiles from training period | §6.15 wording | Other α | Affects E8 only | No |

## PRISM controller and baselines

| ID | Missing / ambiguous | Selected interpretation | Why | Alternatives | Effect | Sens. |
|---|---|---|---|---|---|---|
| D10 (R19) | κ EWMA weight and "enough overflow" | α = 0.1 per epoch; leave the 0.35 prior after 1,000 cumulative overflow requests; clip [0.1, 1] | Conventional; prevents early noise | Other α / thresholds | In this simulator κ is usually at the 0.1 floor (see results), so the threshold rarely matters | No |
| D16 (R31) | QuantProv scale grid | a ∈ {0.6, …, 1.5} step 0.1 | Brackets a = 1 symmetrically, same size as other grids | Finer grid | Selection granularity | No |
| D17 (R31, X09) | Whether PredHead uses the scale-in rule | No (literal reading of §5.3) | QuantProv's use is stated explicitly, PredHead's is not | With rule | Hysteresis is worth several % cost (§6.11), so it can move the PRISM–PredHead cost gap | **Yes: PredHead+hyst pre-registered (E1)** |
| D25 | Reactive scale-in details | Scale-out immediately per stage; joint counter of consecutive epochs with some stage below and none above; then floor(0.9·P) per epoch | "limited to 10 % per epoch"; floor so pools drain | ceil(0.9P); per-stage counters | Small | No |
| D26 (R32) | "Per-stage peak concurrency in the history" | The fast simulator's policy-independent peak-concurrency draws at 1024 MB for all minutes before the evaluated week | Equals platform telemetry in this model | Mean concurrency | Static/scheduled levels | No |
| D27 | Memory epochs | k mod 12 = 0 with k counted from week start (hour boundaries) | Algorithm 1 step 5 | — | — | — |
| D30 | Oracle | All 100 scenarios equal to the realised window peak; same κ, hysteresis and memory logic as PRISM | §5.3 "PRISM's optimizer given the true realised window peak" | — | — | — |
| D32 | State carried between weeks | None except the conformal offset (D08) and the pre-week history used by features, history baselines, reactive window and the initial keep-alive pool | Weeks are evaluated separately in the manuscript | Carry policy state | First epochs only | No |

## Simulator

| ID | Missing / ambiguous | Selected interpretation | Why | Alternatives | Effect | Sens. |
|---|---|---|---|---|---|---|
| D11 (R23) | How the upper-45 % peak is sampled | u ~ U(0.55, 1) per (minute, stage), shared across memory sizes; Z per minute shared across stages; K = Poisson⁻¹(u; c·Z) | Common random numbers across policies, memories and scenarios | Independent draws per memory | — | — |
| D12 (R24) | Keep-alive pool | pool_t = max on-demand concurrency over the previous 10 min; new environments = (OD_t − pool_t)⁺ are cold; cold ≤ overflow requests; initial pool from the 10 pre-week minutes under the first decision | Literal reading of §5.1 | Exponential decay of the pool | Sets cold-start counts | Keep-alive 5/30 min in E5 |
| D13 (R25) | Overflow request share | n_od = N·(K−P)⁺/K | §6.8 says the fast simulator's share is "an occupancy at an arrival-seen peak level" | (K−P)⁺/c | Cost split PC/OD | Compared with event-level in E9 |
| D19 (R35) | Event-level simulator construction | Stage-by-stage sequential pass (exact because downstream never affects upstream); loss routing to provisioned envs; LIFO reuse of idle on-demand envs, expiry after keep-alive; cold start occupies init+exec; capacity changes at minute boundaries without pre-empting busy envs | §6.8 description | Full global event queue (equivalent here) | — | Erlang-B oracle test |
| D20 | Event-level scope | 3 traces × 4 scenarios × 6 policies, frozen E1 schedules (open loop) | Compute (see protocol log) | Full re-tuning (§6.8.1) | §6.8.1 claims untested | **Blocked by compute** |
| D24 | Week start state | Hysteresis reference P = 0, κ = prior, first decision uses pre-week history | — | Warm start from previous week | First hour only | No |
| D29 | p99 latency | From the 100 sampled latencies per minute, volume weighted, via a 10 ms histogram | — | Exact sort | ≤10 ms | No |

## Workload (SYNTHETIC) — D14

| Item | Value | Basis |
|---|---|---|
| Mean rate | analytic scale so the expected stationary mean is 600/min | §5.2 |
| Diurnal | 1 + 0.35 cos(2π(h−14)/24) + 0.10 cos(4π(h−10)/24) | "two harmonics"; amplitudes/phases **assumed** |
| Weekly | Sat × 0.65, Sun × 0.55; day 0 = Monday | §5.2 (−35 %, −45 %); weekday **assumed** |
| AR(1) | log-noise φ = 0.99 per minute, stationary s.d. 0.08 | **assumed** |
| Fan-out spikes | +200 % of baseline at :00 and :01, +100 % at :30 | §5.2 |
| Random bursts | Poisson 4/day; additive amplitude U(1, 3.5) × baseline; duration U{2,…,10} min | rate and amplitude §5.2; additive form and duration **assumed** |
| Count noise | Poisson(rate × Gamma(40, 1/40)) | "gamma-mixed Poisson"; shape **assumed** |
| Growth | baseline × (1 + 0.4·min(1, (t − day 21)/3 days)) | §5.2 |
| Bursty | adds an independent burst stream of the same rate in the test week | §5.2 "doubled" |
| New spike | +150 % at :15 and :16, baseline × 1.2 | §5.2 |
| Shifted triggers | spikes at :10, :11 (+200 %) and :40 (+100 %) in test week | §5.2 |
| Seeds | evaluation 101–105, development 7 (D15) | manuscript names seed 101 only |

All scenarios of a seed share days 0–20 exactly (tested) and share the test-week noise, burst and gamma draws.

**Consequence:** absolute costs and violation rates are properties of these assumed parameters and of the simulator. Only orderings, directions and approximate magnitudes are compared with the manuscript.

## Pricing and provenance — D22

The four prices are taken from the manuscript (§3.4) as stated. They are *not* asserted to be current provider prices; see `docs/PRICING_PROVENANCE.md`. Orchestration fees and data transfer are excluded, as in the manuscript.

## Repository-level decisions

| ID | Decision |
|---|---|
| G1 | The manuscript (.docx) is **not** included in the repository; only its SHA-256 is recorded. |
| G2 | No open-source licence has been selected (ownership of the method and coauthor rights are unresolved); see `LICENSE_PENDING.md` (the authors have since agreed to release the code; the licence is still to be chosen). |
| G3 | No figure values were digitised from the manuscript; manuscript numbers are transcribed from its tables and labelled as reported claims. |
| G4 | Real-trace replay is not implemented for the Huawei format (format not accessible; no network). A generic per-minute CSV loader with schema validation is provided instead (D21). |
