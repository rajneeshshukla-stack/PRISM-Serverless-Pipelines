#!/bin/bash
# P2 sensitivity (RUN_PLAN.md). Patched Linux clone ~/prism_linux/calib2_3edc386 (3edc386 + candidate_exec_p2.patch),
# pinned py312, resumable. Usage: bash run_linux.sh <group G0|G1|G2|G3> [workers]
set -u
cd ~/prism_linux/calib2_3edc386/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
F=$(ls -d /mnt/c/Users/*/PRISM-Serverless-Pipelines/prism-repro/docs/revision/calibration_20261124/exec_factor_measured.json | head -1)
~/prism_linux/py312/bin/python scripts/revision/p2_closed_loop.py ~/prism_linux/p2_20261124 "$F" --group=$1 --workers=${2:-2}
echo "$1 exit $?"
