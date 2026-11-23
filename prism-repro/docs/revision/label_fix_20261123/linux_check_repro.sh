#!/bin/bash
set -u
cd ~/prism_linux/tag/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
for sc in stationary new_spike; do
  echo "== check_reproducibility.py --seed 101 --scenario $sc (v1-submitted tree, Linux)"
  ~/prism_linux/py312/bin/python scripts/check_reproducibility.py --seed 101 --scenario "$sc" 2>&1 | tail -12
done
