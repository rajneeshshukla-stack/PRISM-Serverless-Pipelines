#!/bin/bash
# v1-submitted tree, Linux, Python 3.12.3 pinned: rerun E1 for seeds 101-105 (one process per seed, separate result
# directories, so the stored results/raw is never written), then compare every row with the stored E1 rows.
set -u
cd ~/prism_linux/tag/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
L=~/prism_linux/tag_e1.log
echo "$(date -u +%FT%TZ) START v1-submitted E1 on Linux" > $L
run() { s=$1; PRISM_RESULTS=$HOME/prism_linux/tag_e1_$s $PY experiments/run_experiments.py --exp E1 --seeds $s > $HOME/prism_linux/tag_e1_$s.out 2>&1; echo "$(date -u +%FT%TZ) END seed $s exit $?" >> $L; }
export -f run; export PY L
printf '%s\n' 101 102 103 104 105 | xargs -P 3 -I{} bash -c 'run {}'
echo "$(date -u +%FT%TZ) DONE" >> $L
