# PRISM Serverless Pipelines — Author-Run Verification: Summary

- **Executor:** Rajneesh Shukla
- **Execution Timestamp (UTC):** 2026-11-07T15:07:50Z to 2026-11-07T15:10:43Z
- **Machine:** Ubuntu on Windows Subsystem for Linux (WSL), x86_64, 8 logical CPUs, WSL: True
- **Python Runtime:** Python 3.14.4; isolated virtual environment (`venv`) active; dependencies installed (NumPy 2.4.4, SciPy, Pandas, etc.)
- **Verification Status:** **PASS** (100% success across all policies and experiment groups E1–E11 with 0 failures)

| Check / Verification Step | Status | Detail |
|---|---|---|
| **Environment & Python Runtime** | **PASS** | Python 3.14.4 and NumPy 2.4.4 verified in isolated virtual environment (`venv`) |
| **Reproducibility & Integrity Check (`check_reproducibility.py`)** | **PASS** | Cryptographic checks and data manifests verified (`ALL IDENTICAL`) |
| **Simulation Campaign (`run_all.sh`)** | **PASS** | Full multi-seed sweep across experiment groups E1–E11 executed successfully with zero faults |
| **Analysis & Zero-Failure Audit (`analyze.py`)** | **PASS** | Validated row counts and zero failure criteria across all simulation runs |
| **Artifact & Archive Packaging (`out_run.tar.gz`)** | **PASS** | Bundled full results directory, logs, summary tables (`results/tables/`), and evaluation figures (`results/figures/`) |

## Experiment Execution Breakdown

| Experiment Group | Seeds | Rows & Status |
|---|---|---|
| **E1** | 5 seeds (101–105) | 1,900 rows, failed=0 |
| **E2** | 5 seeds (101–105) | 20 rows, failed=0 |
| **E3** | 5 seeds (101–105) | 110 rows, failed=0 |
| **E4** | 2 seeds (101–102) | 172 rows, failed=0 |
| **E5** | 2 seeds (101–102) | 540 rows, failed=0 |
| **E6** | 5 seeds (101–105) | 40 rows, failed=0 |
| **E7** | 5 seeds (101–105) | 180 rows, failed=0 |
| **E8** | 5 seeds (101–105) | 1,280 rows, failed=0 |
| **E9** | 3 seeds (101–103) | 72 rows, failed=0 |
| **E10** | 1 seed (101) | 1 row, failed=0 |
| **E11** | 5 seeds (101–105) | 150 rows, failed=0 |

## Audit Verdict & Notes
All automated verification checks, simulation runs, and metric analysis steps completed successfully with zero unhandled exceptions or policy deviations. The detailed execution logs, raw metric files (`.jsonl`), array outputs (`.npz`), and generated figures are securely archived within `out_run.tar.gz` and cataloged in the local `results/` structure.
