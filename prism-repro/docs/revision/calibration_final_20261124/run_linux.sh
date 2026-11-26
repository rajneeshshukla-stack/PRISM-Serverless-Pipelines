#!/bin/bash
# Bounded check (RUN_PLAN.md). Patched Linux clone ~/prism_linux/calib_3edc386 (3edc386 + candidate patch), pinned py312,
# 2 workers, resumable (rerun the same command to continue).
set -u
cd ~/prism_linux/calib_3edc386/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
F=$(ls -d /mnt/c/Users/*/PRISM-Serverless-Pipelines/prism-repro/docs/revision/calibration_20261124/exec_factor_measured.json | head -1)
~/prism_linux/py312/bin/python scripts/revision/calib_closed_loop.py ~/prism_linux/calib_cmp_20261124 "$F" --workers=${1:-2} --only=${2:-E14,F13,R13}
echo "exit $?"
