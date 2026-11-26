#!/bin/bash
# Calibrated build (RUN_PLAN.md): Linux clone ~/prism_linux/calibrated_92e3e68 (92e3e68 + candidate_exec_p2.patch),
# pinned py312, resumable. Usage: bash run_linux.sh <group R|A|B|D> [workers]
set -u
cd ~/prism_linux/calibrated_92e3e68/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
F=$(ls -d /mnt/c/Users/*/PRISM-Serverless-Pipelines/prism-repro/docs/revision/calibration_20261124/exec_factor_measured.json | head -1)
~/prism_linux/py312/bin/python scripts/revision/cal_closed_loop.py ~/prism_linux/calbuild_20261125 "$F" --group=$1 --workers=${2:-2}
echo "$1 exit $?"
