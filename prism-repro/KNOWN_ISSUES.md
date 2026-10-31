# Known issues

## Code defects found after the runs (corrected by a separate patch; stored results not regenerated)

The program code in `src/`, `experiments/` and `scripts/` is the one that produced every stored result. The
patch `patches/m12_m5_corrections.patch` corrects the three defects below and adds four tests
(`tests/test_stage21_fixes.py`; all four fail without the patch, three by assertion and one with an error).
It is not applied, because applying it
to the stored results would require re-running the experiments; `patches/README.md` explains how to apply it.

| ID | Defect | Where | Paper |
|---|---|---|---|
| M12 (a) | At the first epoch of a week, reactive tracking reads pre-week minute -1, one minute beyond its visible horizon | `src/prism_repro/policies.py` (`Reactive.decide`) | Suppl. S1 |
| M12 (b) | The fast simulator treats every pre-week on-demand environment as warm for the first ten minutes, including environments whose 10-minute keep-alive has expired | `src/prism_repro/simulator.py` (`simulate`, k = 0) | Suppl. S1 |
| M5 (c) | When PRISM changes memory, neither simulator empties the warm on-demand pool, and the billing bound counts no re-provisioned environments, so cold starts and initialization charges after a switch are under-counted (this favors memory co-optimization). PRISM changes memory 6 times in its 20 main test weeks, up to 41 times in a test week (50 in a validation week) at epsilon = 0.005, up to 14 times in E4 and up to 26 in E6 | `simulator.py`, `des.py`, `scripts/revision/pc_billing_bounds.py` | Section VI-G; Suppl. S1 |

**Measured effect.** A paired re-simulation with and without the patch, in the same software environment
(Python 3.13.18, scikit-learn 1.9.1), covered 435 stored configurations: the validation-selected configuration
of every family in all 20 test weeks (180), the validation grids of the policies without a learned forecaster
(140), PRISM at epsilon = 0.005 and 0.01 in all test weeks (40), the E4 runs of Table IX (14) and the E6 runs of
Suppl. Table S5 (40), event-level replays of stored PRISM-0.005 schedules (8), and every forecast-driven
validation run within one window of the 2% threshold on either side (13). No violating-window rate or target
outcome changed, and cost changed by at most USD 0.21 per week (0.012%), below the printed precision of every
reported number. The runs without a learned forecaster reproduced the stored results exactly without the patch,
which checks the harness. Scripts, raw outputs and the summary: `patches/diagnostic/`.

## Modeling choices the paper discloses

| ID | Choice | Paper |
|---|---|---|
| M1 | The activation lag L = 2 means that a decision taken once minute t is observed applies from minute t + 2 (one minute after the last observation); `features.H_LO, H_HI = 2, 6` do not follow `cfg.lag_min` | Sections III-B, IV-A, VIII; Suppl. Table S1 |
| M2 | The fast simulator's intensity factor (sigma = 0.148) was derived from the constant 1.011 of PRISM's effective load c_eff, so the simulator's expected peak approximately equals c_eff (`ASSUMPTIONS_AND_DECISIONS.md`, D02) | Sections V-A, VIII |
| M3 | Without capacity caps, epochs without a feasible grid level reflect the grid's upper bound (1.15 times the largest scenario): a feasible capacity exists at the default deadline. Under caps (E6), such epochs often coincide with a binding cap | Section IV-D; Suppl. S9 |
| M7 | The conformal offset starts at zero at the start of the validation week (0.19-0.34 by its end); validation-week offsets are not stored | Section V-C |
| M21 | Execution-time speed-ups above 1,769 MB assume multi-threaded stage code | Section III-A |
| P7 | E1 runs of seeds 101-103 used an earlier source state (`af08337...`) than all other runs (`8c1710f...`); see `PROVENANCE.md` | Suppl. S1 |

## Not executed or not tested

| Item | Status | More | Command or prerequisite |
|---|---|---|---|
| Full event-level re-tuning | Only the reduced event-level re-tuning E12 was run (open-loop replay of stored schedules; scheduled provisioning and QuantProv-q99 not retuned; static and reactive grids reduced) | `EVALUATION_PROTOCOL.md` (change log); paper Section VI-I | Full open-loop version: add Scheduled, QuantProv_q99 and the full Static and Reactive grids to `FAMS` in `scripts/revision/e12_event_retune.py`, then `python scripts/revision/e12_event_retune.py . <out_dir> 101 102 103 104 105`. A closed-loop variant would also need PRISM's cold-hit estimate and the reactive baseline's telemetry to come from the event-level simulator |
| Fixed larger memory under capacity caps | Not run (E4b covers the uncapped memory regimes only) | paper Section VI-G | Add PredHead/QuantProv at `default_mem=2048` to the E6 cap runs (baselines need a per-stage cap) |
| Real traces | Not run; every workload is synthetic | `docs/DATA_CARD.md`; paper Section IX | Convert a public trace to `minute,count`, load it with `prism_repro.trace_io.load_minute_csv`, pass the counts in place of `generate_trace(...)["counts"]` in `experiment.TraceBundle`, and rerun E1-E3; check the trace licence first |
| Run-level comparison with the earlier prototype | Not run; the prototype's code and outputs are not available (the paper compares only its reported results) | paper Section V-E | Needs the prototype's code and raw results; run both implementations on the same trace and compare decisions epoch by epoch |
| Clean install | Not tested (packages were preinstalled; no network) | `docs/TEST_REPORT.md` ("Not tested") | `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m unittest discover -s tests` |
| CI and Docker | Not tested | `docs/TEST_REPORT.md` | Run `.github/workflows/tests.yml` once; `docker build .` |
| Other platforms and Python versions | Linux x86-64 only. The tests were run under Python 3.12.3 with the pinned versions and, in later checks (30 Oct 2026), under Python 3.13.18 with numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, scikit-learn 1.9.1 and matplotlib 3.11.2 (48 of 48 passed; 52 of 52 with the patch); `docs/TEST_REPORT.md` and the header of `requirements.txt` describe only the 3.12.3 run | `docs/TEST_REPORT.md` | - |
