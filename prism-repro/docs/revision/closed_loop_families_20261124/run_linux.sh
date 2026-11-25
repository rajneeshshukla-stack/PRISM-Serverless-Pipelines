#!/bin/bash
# Comparator runs (PLAN.md): set CMPe (QuantProv_q90, Reactive, PredHead+hyst), set CMPb (PredHead, QuantProv_q99,
# Static, Scheduled), then OnDemand. Same output directory as the kappa study, so the bundles and PRISM's arm A (set K)
# are reused. Clean clone of 3edc386, pinned py312, checkpointed per week; rerun to resume. Usage: bash run_linux.sh <workers>
set -u
W=${1:-3}
R=~/prism_linux/cl_3edc386/prism-repro; OUT=~/prism_linux/kappa_20261124
cd "$R"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
echo "workers $W, start $(date -u +%FT%TZ)"
$PY scripts/revision/closed_loop_exploratory.py run "$OUT" --sets=CMPe --workers=$W --seeds=101-105; echo "CMPe exit $?"
$PY scripts/revision/closed_loop_exploratory.py run "$OUT" --sets=CMPb --workers=$W --seeds=101-105; echo "CMPb exit $?"
$PY scripts/revision/closed_loop_exploratory.py ondemand "$OUT" --workers=$W; echo "ondemand exit $?"
echo "end $(date -u +%FT%TZ)"
