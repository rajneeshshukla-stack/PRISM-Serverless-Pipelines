#!/bin/bash
# Linux x86-64 (WSL2 Ubuntu 26.04), Python 3.12.3, pinned packages: rebuild E1, then E3, E7, E9, then analyze.py,
# with the normal commands. E1 runs one process per seed (PRISM_RESULTS per seed; seeds are independent), then the
# per-seed outputs are concatenated in seed order, as a single sequential run would write them.
set -u
cd ~/prism_linux/fix/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
PY=~/prism_linux/py312/bin/python
L=results/logs/linux_rebuild.log
log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
log "START platform $(uname -srm); python $($PY -c 'import sys;print(sys.version.split()[0])')"
run_e1() { s=$1; PRISM_RESULTS=$PWD/results/raw_e1_$s $PY experiments/run_experiments.py --exp E1 --seeds $s \
  > results/logs/E1_$s.out 2> results/logs/E1_$s.err; log "END E1 seed $s exit $?"; }
export -f run_e1 log; export PY L
log "START E1 seeds 101-105 (3 processes at a time)"
printf '%s\n' 101 102 103 104 105 | xargs -P 3 -I{} bash -c 'run_e1 {}'
mkdir -p results/raw/E1
for s in 101 102 103 104 105; do cat results/raw_e1_$s/E1/rows.jsonl >> results/raw/E1/rows.jsonl; cp results/raw_e1_$s/E1/arrays_seed$s.npz results/raw/E1/; done
log "MERGED E1: $(wc -l < results/raw/E1/rows.jsonl) rows"
for e in E3 E7 E9; do
  case $e in E9) seeds="101 102 103";; *) seeds="101 102 103 104 105";; esac
  ( $PY experiments/run_experiments.py --exp $e --seeds $seeds > results/logs/$e.out 2> results/logs/$e.err; log "END $e exit $?" ) &
done
wait
$PY scripts/analyze.py > results/logs/analyze.out 2> results/logs/analyze.err; log "END analyze exit $?"
log "DONE"
