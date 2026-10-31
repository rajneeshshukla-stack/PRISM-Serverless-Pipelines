# Evaluation protocol (written before any evaluation-seed run)

> Note added 30 Oct 2026: the first commit of this file (`6db1f8d`, 23:15:54 UTC) followed the start of the first
> stored evaluation run (23:12:16 UTC) by about four minutes; see the change log (section 9) and `PROVENANCE.md`.

**Written:** 2026-10-29, before running any experiment on evaluation seeds 101–105.
**What had been seen at that time:** analytic checks (Eq. 3, Table 3 miss probabilities, break-even) and one smoke run of six configurations on the *validation week of development seed 7* (OnDemand, Static-95, Reactive-0.6, PredHead-1.3, QuantProv_q90-1.0, PRISM-0.05). Nothing was changed in the generator, simulator, policies or grids as a result of those smoke values. All workload-generator parameters (ASSUMPTIONS D14) were fixed before the smoke run.

Changes made after this point are logged in §9 with reasons and dates.

## 1. Questions and directional hypotheses

These restate the manuscript's claims as testable statements under *this* reconstruction. A hypothesis "supported" means the direction holds in the mean and in at least 4 of 5 traces (or the 95 % t-interval of the paired difference excludes zero).

| ID | Hypothesis (from manuscript) | Claim IDs |
|---|---|---|
| H1 | Stationary test week: validation-tuned PredHead is cheaper than validation-tuned PRISM. | C13, C14 |
| H2 | New-spike test week: PRISM has fewer violating windows than PredHead. | C13, C14 |
| H3 | Removing conformal recalibration (ε fixed) raises PRISM's violating-window rate in each scenario. | C17 |
| H4 | QuantProv (q90 or q99, tuned scale) reaches a violating-window rate no worse than PRISM + 0.5 pp in the shifted scenarios, at higher cost. | C33 |
| H5 | With D = 12 s, every fixed-1024-MB policy violates ≥ 90 % of windows while PRISM with memory optimisation meets ≤ 2 %. | C19 |
| H6 | Reactive and static provisioning meet the 2 % target in more test weeks than PRISM, at higher mean cost. | C15 |
| H7 | Raw q99 coverage < 0.99 and conformal recalibration raises it towards 0.99 in every scenario. | C11 |
| H8 | Event-level re-evaluation of the same frozen schedules: costs within 2 % of the fast simulator, violating-window rates higher. | C21 |
| H9 | Erlang-B matches the event-level overflow share more closely than occupancy o(P,c) at mean or c_eff. | C22 |

Analytic claims (C01–C07, C39) are checked by unit tests, not by hypothesis tests.

## 2. Experimental units, data and splits

* Unit: one (trace seed, scenario) test week. Evaluation seeds **101, 102, 103, 104, 105** (chosen a priori; the manuscript mentions "seed 101" but not its full list). Development seed **7** (smoke tests only, never reported as evidence).
* Data: SYNTHETIC traces from `prism_repro.workload.generate_trace` (28 days, minute resolution). Train days 0–13, validation days 14–20, test days 21–27. Scenarios: stationary, growth, bursty, new_spike (main) and shifted_triggers (feature ablation only).
* Leakage controls: forecasters are fitted only on decision minutes whose targets end before day 14; conformal offsets start at 0 at the validation-week start and use outcomes with a two-epoch delay; history baselines use data before the evaluated week only; parameters are selected on validation only.

## 3. Methods, grids and tuning budget

Identical one-parameter grids for every seed:

| Family | Grid |
|---|---|
| OnDemand | — (1024 MB) |
| Static-p | 50, 60, 70, 80, 90, 95, 97, 99, 99.5, 99.9 |
| Scheduled-h | 1.0 … 2.0 step 0.2 |
| Reactive-u | 0.40 … 0.90 step 0.05 |
| PredHead-h | 1.0 … 2.0 step 0.1 (no scale-in rule, as written in §5.3) |
| PredHead+hyst-h | same grid, with the 0.85 scale-in rule (pre-registered sensitivity for ambiguity D17) |
| QuantProv_q90-a, QuantProv_q99-a | a = 0.6 … 1.5 step 0.1 (grid not in manuscript; D16) |
| PRISM-ε | 0.005, 0.01, 0.02, 0.03, 0.05, 0.08; δ = 0.1 |

**Selection rule (all families):** cheapest configuration with ≤ 2 % violating windows on the validation week; if none, the least violating (ties → cheaper). Selected parameters are frozen and applied to all test scenarios. "Retuned" values (selected on the test week) are reported only as a labelled diagnostic.

Every method sees the same arrivals, the same common random numbers and the same prices. Each configuration is a deterministic single run (no repeated runs are needed for a fixed seed); variability is across the five traces.

## 4. Metrics

Primary: total weekly cost (USD, simulated); violating-window rate (share of 672 fifteen-minute windows with record-level attainment < 99 %); SLO met (≤ 2 %). Secondary: record-level attainment, p99 latency (sampled), billing utilisation, mean total provisioned concurrency, cold-start ratio, severity/persistence (late records, attainment in violating windows, worst window, run lengths), churn (minutes with a change, environments added), infeasible-epoch share and excess, decision time. Forecast metrics: MAPE of the median, pinball loss at τ = 0.5/0.9/0.99, empirical coverage of q50/q90/q99 raw and calibrated.

## 5. Statistics

Means with 95 % t-intervals over the 5 traces (t₀.₉₇₅,₄ = 2.776); paired PRISM−PredHead differences per trace with t-intervals and sign counts. Windows within a week are autocorrelated and are **not** treated as independent samples. With n = 5, intervals are wide; no multiplicity correction is applied and all hypotheses are reported regardless of outcome.

## 6. Experiments (priority order on a 1-core machine)

| ID | Content | Seeds |
|---|---|---|
| E1 | Main protocol: all grids on validation and the four test scenarios | 101–105 |
| E2 | Forecast accuracy and calibration (no simulation) | 101–105 |
| E3 | PRISM ablations at validation-chosen ε on test weeks: no conformal; Oracle; quantile-feasibility mode (stationary, new spike); no hysteresis over the full ε grid (stationary, new spike) | 101–105 |
| E4 | Memory regimes: D ∈ {14.5, 13, 12, 11} with non-scaling 0.5 and D ∈ {14.5, 12} with 0.15; PRISM with/without memory at ε = 0.02 (and ε = 0.01 at D = 13); PredHead best-on-test; OnDemand; stationary test week | 101, 102 |
| E5 | Simulator-assumption sensitivity: keep-alive 5/30 min, init 3/9 s; reduced grids as in Table 9 caption; validation-tuned; stationary and growth test weeks | 101, 102 |
| E6 | Platform caps 250/60/40 at ε = 0.02 (stationary, new spike) | 101–105 |
| E7 | Feature-group ablations at the full model's validation-chosen ε, incl. shifted-trigger scenario | 101–105 |
| E8 | Reference forecasters + PRISM and + QuantProv_q99, validation-tuned | 101–103 |
| E9 | Event-level re-evaluation of frozen E1 schedules (scope set by compute; see §8) | subset |
| E10 | Controller overhead: online full decision cycle over one test week | 101 |
| E11 | PRISM-EB (Erlang-B) full grid under the fast simulator | 101–105 |

## 7. Exclusions and failures

No run is excluded. A run that raises an error is recorded as failed with its traceback and the failure is reported; it is not silently retried with different settings. Grid-edge selections are reported.

## 8. Stopping and scope rules

Experiments run in the priority order above until complete or until compute in this session runs out; anything not executed is listed as *not executed* in `REMAINING_WORK.md` with the command to run it. The event-level simulator (E9) is pure Python; its scope (traces × scenarios × policies) is fixed after a timing measurement on the development seed, and the chosen scope is recorded here before its outputs are inspected.

## 9. Protocol change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-29 | (initial version) | — |
| 2026-10-29 | E9 scope fixed after timing the event-level simulator on development seed 7 (≈1.5 µs per stage-request; ≈45–60 s per policy-week): seeds 101–103 × four test scenarios × six validation-tuned policies (OnDemand, Static, Scheduled, Reactive, PredHead, PRISM) replayed from E1 schedules (72 runs). Overflow-estimate comparison (Table 11 analogue), in-flight maximum ratio and latency-sampling flips on seed 101 (stationary, new spike). Full event-level re-tuning (§6.8.1; ≈750 runs ≈ 12 h on one core) is **not executed** and marked blocked by compute. | Compute budget on a single core; decided before any E9 output existed. |
| 2026-10-29 | Execution order changed to E1, E2, E3, E10, E6, E7, E9, E4, E5, E11, E8 (was E1, E2, E3, E6, E7, E4, E5, E11, E8, E10, E9). No experiment content changed. | Run the event-level fidelity check before the lower-priority E11/E8 in case compute runs out. No E2–E11 output existed when the order was changed; only E1 seed 101 rows existed and had not been inspected. |
| 2026-10-29 | While debugging `scripts/analyze.py`, partial E1 results (3 of 5 seeds) were displayed. No protocol, code or grid change followed. | Disclosure. |
| 2026-10-29 | After E1 and E2 completed (and were inspected), order changed again to E3, E10, E4, E9, E6, E7, E5, E11, E8. If compute runs out, E9 may be truncated to the seed/scenario chunks completed; the executed scope will be reported. | Remaining compute (~2.5 h on one core) exceeds the session; E4 (memory, a stated contribution) and E9 (fidelity) were prioritised. Content of all experiments unchanged; no output of E3–E11 existed. |
| 2026-10-30 | Verdict rule for C12 in `scripts/build_claim_matrix.py` tightened after E1 was inspected: it now checks the 1 % as well as the 2 % level, matching the claim's wording "at every compliance level". | The earlier rule did not test the claim as written; the change can only lower the verdict. |
| 2026-10-30 | E8 extended from seeds 101–103 to 101–105 and completed during the manuscript revision, in two batches (101–103; 104–105) under scikit-learn 1.9.1 (original runs: 1.8.0). The reference forecasters use no learned model; the gradient-boosting rows of T18/T19 are taken from E2/E1 (original environment), and `scripts/analyze.py` was changed to do so. The 16 partial E8 rows from the original environment are kept as `results/raw/E8/rows_partial_seed101_original_env.jsonl`. | Reviewer request. Post hoc: E1–E11 outputs had been inspected. |
| 2026-10-30 | E12 added: event-level re-tuning by open-loop replay of stored E1 schedules, seeds 101–105; OnDemand, Static (*p* ∈ {95, 97, 99, 99.5, 99.9}), Reactive (*u* ∈ {0.40, …, 0.70}), PredHead, PredHead+S, QuantProv_q90 and PRISM; Scheduled and QuantProv_q99 omitted for compute; 395 replays. A reduced form of the full re-tuning marked *not executed* above. Code: `scripts/revision/e12_event_retune.py`, `scripts/revision/analyze_e12.py`. | Reviewer request. Post hoc: E1–E11 outputs had been inspected. |
| 2026-10-30 | Post hoc analyses added (no new simulation): matched-compliance frontiers (`scripts/revision/posthoc_analysis.py`), per-trace matched-compliance intervals (`matched_compliance_pertrace.py`) and bounds on two provisioned-concurrency billing items the simulators do not model (`pc_billing_bounds.py`). Outputs in `results/tables/revision/`; provenance in `RUN_MANIFEST_REVISION.json`. | Exploratory; labelled post hoc in the manuscript. |
| 2026-10-30 | Provenance notes added during the manuscript correction (Stage 2.1), no change to experiments: (a) the E1 runs of seeds 101–103 ran on source `af08337…` and all later runs on `8c1710f…`; the difference between the two source states was not logged at the time; re-simulation shows the non-forecast runs bit-identical and the forecast-driven runs within the library-version effect (`PROVENANCE.md`); (b) the first commit of this protocol (`6db1f8d`, 23:15:54 UTC) follows the start of the first stored E1 run (23:12:16 UTC) by about four minutes; (c) code defects found by the audit (two first-epoch edge cases; warm pool kept across memory changes) are listed in `KNOWN_ISSUES.md`; their corrections are not applied to the stored results. | Transparency; recorded post hoc. |
| 2026-10-30 | Corrective patch for the defects of entry (c) added as `patches/m12_m5_corrections.patch`, with four tests; a paired re-simulation of 435 stored configurations with and without the patch changed no violating-window rate or target outcome and changed cost by at most USD 0.21 per week (`patches/diagnostic/`). The stored results were not regenerated; the experiments were not re-run. | Post hoc correction, documented; no change to reported results. |
| 2026-10-30 | Post hoc E4b (`scripts/revision/e4b_*.py`, raw rows in `results/raw/E4b/`): in the memory regimes of E4 (two traces, stationary test week), PredHead at fixed 2048 and 3008 MB, on-demand at both sizes, PRISM over its full epsilon grid, and re-runs of the stored E4 configurations; run under scikit-learn 1.9.1. Post hoc level-choice diagnostic (`scripts/revision/level_choice_diagnostic.py`): PRISM at the selected epsilon in the 20 test weeks, logging whether the chosen capacity level exceeds the smallest feasible one. Both were added after a review of the manuscript asked whether online memory sizing beats a fixed larger size and whether the cost model changes capacity decisions. | Exploratory; labelled post hoc in the manuscript (Section VI-G, Suppl. S9, S11). |
| 2026-10-30 | Release candidate: the claim-verdict matrix, the comparison and readiness reports, the specification audit and the correction package (review material on an earlier manuscript version) are not part of the release; `scripts/build_claim_matrix.py` (mentioned above) is therefore not included, and `REMAINING_WORK.md` (mentioned above) is not included: the items not executed or not tested are listed in `KNOWN_ISSUES.md` (section "Not executed or not tested"). The original run logs (`results/logs/`) are included. | Release curation. |
