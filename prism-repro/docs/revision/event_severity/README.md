# Event-level violation severity, persistence, modelling factors and extra capacity (R2.4, R7.2; R1.1 evidence)

**Labels.**
- PRE-CALIBRATION: assumed constants (Table S1).
- POST HOC and OPEN LOOP.
- Simulation results throughout; nothing here is a platform measurement.

**Code.** `scripts/revision/event_severity_factors.py` (new in this pass, uncommitted) on the code of HEAD 78ba419,
with `src/` and `experiments/` clean (`environment.json`).

**Platform.** One Windows 11 laptop (4 cores).

**What is replayed.** No policy is re-run. Each replay passes a provisioning and memory schedule that the submitted
fast-simulator experiment E1 stored (`results/raw/E1/arrays_seed*.npz`) through the current event-level simulator
(`des.simulate_events`), exactly as the paper's E9 (Table X) and E12 (Table XI) did. Seeds 101-105 are used; the
confirmatory seeds 106-130 are not.

**Provenance.**
- Started 22 Nov 2026 05:39:28Z with 4 workers. It was stopped at about 05:55Z after 39 rows (trace 101): with the
  fast-simulator suite running beside it, seven CPU-bound processes on 4 physical cores ran about 4x slow, and the full
  design would have taken about five hours.
- The design was then trimmed (see the script's header); the rows already written were kept.
- It was resumed after the fast-simulator suites finished (`run.log`). `summary.txt` is the `--analyse` output on the
  saved rows.

**Rows.** One JSON row per replay, in `rows_<group>_<seed>_<scenario>.jsonl`. Each row carries the full summary and
the attainment of each of the 672 windows.

## Design (as trimmed)

**R2.4, Reviewer 2's comment 4.** "Please investigate which workload conditions and modeling factors cause PRISM to
miss the target. An analysis of violation severity, persistence, and required additional provisioning would help
distinguish minor compliance failures from significant operational disruptions."

All of the following use the 20 test weeks of Table XI.
- **Severity and persistence, OBSERVED.** The E12 (event-level validation) selections of PRISM, QuantProv-q90 and
  Reactive, from the per-window attainment. Measures:
  - violating windows per week, against the allowance of 13 of 672;
  - attainment in violating windows, and in the worst window;
  - runs of consecutive violating windows;
  - late records.
- **Workload conditions, ASSOCIATION.** PRISM's violating windows are tabulated by where the window falls in the hour
  (the scheduled spikes sit at minutes 0, 1 and 30; the new-spike slot at 15-16), by random bursts, by
  arrival-rate decile and by scenario.
- **Modelling factors, CAUSAL within the simulator.** PRISM's schedules are replayed with initialisation made
  instantaneous, and separately with the keep-alive made unlimited. These variants change no request draw.
- **Extra provisioning, ESTIMATED.** PRISM's schedules are replayed with every stage's provisioned capacity raised by
  a uniform margin of 10, 20, 30 or 50% (P' = ceil(P (1 + m))). This gives the smallest margin that meets 2% in each
  missed week, and the effect of each uniform margin on all 20 weeks and on cost. These are counterfactuals, not a
  policy the controller could have run without hindsight.

**R7.2, Reviewer 7's comment 2** ("which simulation assumptions contribute ... most to the higher violation rates").
On the Table X schedules (E1 fast-simulator selections; seeds 101-103 x 4 scenarios = 12 weeks), PRISM's
fast-to-event gap in violating windows is decomposed. The replay runs under the event model, with each factor removed
and with both removed. The fast-simulator values are the stored submitted ones (E9 rows).

## Results

(Filled from `summary.txt` below.)
