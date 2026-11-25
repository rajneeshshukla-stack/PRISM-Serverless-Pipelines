#!/bin/bash
# kappa-floor study (PLAN.md): set K (arms A, B, F tuned), then the sensitivity arms (B, F at A's eps).
# Clean clone of HEAD 3edc386 (~/prism_linux/cl_3edc386) with scripts/revision/closed_loop_exploratory.py copied in;
# pinned py312 (Python 3.12.3, scikit-learn 1.8.0); output in the Linux home, checkpointed per week (rerun to resume).
set -u
R=~/prism_linux/cl_3edc386/prism-repro; OUT=~/prism_linux/kappa_20261124
cd "$R"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
$PY scripts/revision/closed_loop_exploratory.py run "$OUT" --sets=K --workers=4 --seeds=101-105; echo "run exit $?"
$PY scripts/revision/closed_loop_exploratory.py sens "$OUT" --workers=4; echo "sens exit $?"
