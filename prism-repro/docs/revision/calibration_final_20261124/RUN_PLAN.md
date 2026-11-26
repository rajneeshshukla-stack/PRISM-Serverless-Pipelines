# Bounded Linux closed-loop check: legacy Eq. (2) against the per-size execution model (plan fixed before the run, 24 Nov 2026)

EXPLORATORY. Development traces 101-105 only; seeds 106-130 are not used. Closed-loop event-level simulator. Every
other constant is the pre-calibration default, so these runs are PARTIALLY CALIBRATED at most (DECISIONS.md section 7).
This is not a confirmatory run.

## Build and environment

- **Code:** a fresh Linux clone of 3edc386 (`~/prism_linux/calib_3edc386`), plus
  `../calibration_20261124/candidate_exec_measured.patch`. That clone's `src/` is modified by design. The R6.1 pinned
  files in the main tree are untouched.
- **Driver:** `scripts/revision/calib_closed_loop.py`. It reuses the C1-C3 driver's bundles, week task (through
  `closed_loop_exploratory.py`, which adds per-epoch arrays), selection rule and edge expansion. It does not use the
  C1-C3 clean-code guard, which would refuse the patched `src/`. Provenance is recorded instead: the patch SHA-256 and
  the driver SHA-256.
- **Environment:** Linux x86-64 (WSL2), the pinned `py312` (scikit-learn 1.8.0), 2 worker processes, one BLAS thread,
  checkpointed per week (resumable).
- **Linux checks first:** `test_exec_measured` (11 tests) and the full suite in the clone, plus the byte-identical gate
  (`tests.test_simulation.TestByteIdenticalRerun`).

## Models

- **legacy:** `exec_scaling` = "eq2", `nonscaling` = 0.5.
- **measured:** `exec_scaling` = "measured", factors from `../calibration_20261124/exec_factor_measured.json`.

The two models share every other setting and the same event draws: draw keys depend on trace and week only.

## Runs, in order

| Set | What it tests | Deadline | Policies and settings | Traces | Weeks | Expected weeks |
|---|---|---|---|---|---|---|
| **E14 legacy** | Linux legacy equality of the patched build: must equal set K arm A of `../closed_loop_kappa_20261124/` exactly | 14.5 s | PRISM at K's selected eps (0.01, 0.01, 0.03, 0.03, 0.03) | 101-105 | test stationary | 5 |
| **E14 measured** | Default-deadline regression: does the measured model change PRISM at 14.5 s? | 14.5 s | same fixed eps | 101-105 | test stationary | 5 |
| **F13** | Fixed-policy model effect at short slack (RQ4/MemAdapt); trace sensitivity of the smoke result | 13 s | PRISM eps 0.01; MemAdapt-q90 a = 0.6 (the fast-simulator selections at 13 s, `../memadapt/summary.txt`, all traces) | 101-105 | test stationary | 2 models x 2 policies x 5 = 20 |
| **R13** | Retuned comparison: does the model change selections? | 13 s | PRISM over `GRIDS["PRISM"]`, MemAdapt-q90 over `GRIDS["QuantProv"]`; the common rule and edge expansion, applied identically to both models | 101-103 | validation stationary (grid) + test stationary | 2 models x 3 traces x (6 + 10 + 2) = 108 (more if edges expand) |

The total is about 138 closed-loop weeks.

## Metrics (per week)

- cost (USD);
- violating-window rate;
- share of minutes at 2048 MB or more;
- the memory sizes used, and the share of epochs at each;
- mean provisioned level;
- the selected setting (R13).

## Paired comparisons (measured minus legacy, same trace, policy and setting)

- cost (%) and violating windows (points), with mean +/- 95% t half-width over 5 traces (F13, E14) or 3 traces (R13);
- the PRISM-minus-MemAdapt premium under each model (F13 per trace; R13 at the selected settings).

## Questions this answers, and rules fixed in advance

1. **Are 2048 and 3008 MB still similar in modelled execution time?** By construction yes in the measured model (the
   factors differ by <= 0.6%). Report whether PRISM still selects 3008 MB.
2. **Does the 13 s smoke result hold beyond trace 101?** "Holds" means, in F13, on 4 or more of 5 traces:
   - a cost reduction of at least 10% for both policies under the measured model;
   - an unchanged weekly SLA verdict (meets 2% or not);
   - a reduced PRISM-over-MemAdapt premium.
3. **Do selections change** (R13)?
4. **E14 legacy** must equal K's rows exactly (cost and violating-window rate). Otherwise the comparison stops and is
   investigated.
5. **E14 measured:** a regression is any change of SLA verdict or a cost change above 1% at 14.5 s. Such a change is
   reported; it does not stop the run.

## Checks

- expected weeks present;
- failures.json empty;
- no duplicate week files;
- identical `counts_sha256` per trace and week across models and policies;
- R13 selections not at a widened-grid edge (or flagged).
