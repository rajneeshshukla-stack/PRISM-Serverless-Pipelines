# Closed-loop event-level evaluation: runtime and compute budget (R2.2, R6.3)

Pre-calibration infrastructure note; one Windows machine (8 cores, 16 GB), Python 3.12.9, numpy 2.4.4.

## Runtime per simulated week (seed 101, stationary test week, 6.04M requests)

| Mode | Time |
|---|---|
| Open-loop event replay of a schedule | 29-35 s |
| Closed loop, PRISM with GBM forecasts, feature history untrimmed | 232 s |
| Closed loop, PRISM with GBM forecasts, week-aligned trimmed history | 170 s |

The trimmed and untrimmed closed-loop weeks give identical outputs (all 38 fields of summary, raw arrays, decisions and
telemetry). Forecasts are bitwise identical over whole weeks for GBM and seasonal-naive on two scenarios (2,016
epochs each) and equal the stored batch schedule; `tests/test_des_closed_loop.py::TestOnlineForecastTrim`.

Profile of the online forecast step (60 epochs, GBM): half rebuilding the feature arrays over the whole history, half
the forecaster's own per-tree prediction (4 models x 200 trees per decision). The trim removes most of the first half;
the second is the forecaster's and is not changed. Remaining per-week cost for PRISM: GBM prediction about 50 s,
optimiser about 15-30 s, event routing about 30 s, features about 12 s.

## Compute budget for a closed-loop retuning (the E12 analogue)

Per-week estimates: forecast-driven rules (PredHead, PredHead+S, QuantProv-q90/q99, MemAdapt) about 110 s; PRISM
170 s; rules without forecasts (Static, Scheduled, Reactive, OnDemand) about 35 s. Paper grids: Static 10,
Scheduled 6, Reactive 11, PredHead 11, PredHead+S 11, QuantProv-q90 10, QuantProv-q99 10, MemAdapt 10, PRISM 6.

| Design per trace | CPU time per trace | 5 traces | 25 traces (seeds 106-130) |
|---|---|---|---|
| Validation grid (85 weeks) + selected setting on 4 test weeks (36 weeks) | about 3.0 h | 15 h | 75 h |
| + every grid point on 4 test weeks (matched compliance, 340 weeks) | about 10.7 h | 53 h | 267 h |

At 4-5 parallel workers (each closed-loop week holds about 2-3 GB), the validation-selected design for the 25
confirmatory traces takes **about 15-19 hours wall clock**; adding matched-compliance frontiers takes **about 2.5-3
days** (267 CPU-h at 4-5 workers). Both are feasible on this machine but not inside one session; the pilot (3 traces, 1 scenario, 4 families)
costs about 2-3 hours wall clock. The budget assumes the machine stays awake (it suspended for about three hours on
the night of 20-21 Nov).
