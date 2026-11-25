#!/bin/bash
# Platform check of the closed-loop event-level path: the confirmatory driver's pilot101 set (seed 101, a development
# trace; stationary; PRISM, QuantProv_q90, Reactive, MemAdapt_q90) on Linux, to compare with the Windows
# ../pilot101_check run of the same driver and code. No confirmatory seed is used. Usage:
#   bash run_linux.sh "<prism-repro on /mnt/c>" "<fresh output dir in the Linux home>" "<this dir>"
set -u
R="$1"; W="$2"; O="$3"
cd "$R"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
echo "start $(date -u +%FT%TZ) $(uname -srm)" > "$O/run_log.txt"
$PY scripts/revision/closed_loop_confirmatory.py run "$W" --sets=pilot101 --workers=4 >> "$O/run_log.txt" 2>&1; echo "run exit $?" >> "$O/run_log.txt"
cp -r "$W/groups" "$W/environment.json" "$W/failures.json" "$O/" 2>/dev/null; cp "$W/run.log" "$O/driver_run.log" 2>/dev/null
echo "end $(date -u +%FT%TZ)" >> "$O/run_log.txt"
