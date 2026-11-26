#!/bin/bash
# R3.2 on the Linux reference platform: the prespecified OptScaler commands (d1, run, analyse) unchanged, with the
# comparator rows taken from the Linux E1 rows (R3.6 release inputs, linux/E1; current code). Usage:
#   bash run_linux.sh "<prism-repro on /mnt/c>" "<this dir>" "<linux E1 rows.jsonl>"
set -u
R="$1"; O="$2"; export PRISM_REGEN_E1="$3"
cd "$R"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
echo "start $(date -u +%FT%TZ) $(uname -srm) $($PY -c 'import sklearn,sys;print(sys.version.split()[0],sklearn.__version__)')" > "$O/run_log.txt"
$PY scripts/revision/optscaler_comparison.py "$O" d1 >> "$O/run_log.txt" 2>&1; echo "d1 exit $?" >> "$O/run_log.txt"
$PY scripts/revision/optscaler_comparison.py "$O" run 101 102 103 104 105 >> "$O/run_log.txt" 2>&1; echo "run exit $?" >> "$O/run_log.txt"
$PY scripts/revision/optscaler_comparison.py "$O" analyse > "$O/analyse_stdout.txt" 2>&1; echo "analyse exit $?" >> "$O/run_log.txt"
echo "end $(date -u +%FT%TZ)" >> "$O/run_log.txt"
