#!/usr/bin/env bash
# Pre-registered experiments in priority order (EVALUATION_PROTOCOL.md §6 and change log).
# Every experiment is resumable; completed seeds/chunks are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
SEEDS="101 102 103 104 105"
mkdir -p results/logs
run () { python3 experiments/run_experiments.py --exp "$1" --seeds ${@:2} 2>&1 | tee -a "results/logs/$1.log"; }
run E1 $SEEDS
run E2 $SEEDS
run E3 $SEEDS
run E10 101
run E4 101 102
run E9 101 102 103
run E6 $SEEDS
run E7 $SEEDS
run E5 101 102
run E11 $SEEDS
run E8 101 102 103
