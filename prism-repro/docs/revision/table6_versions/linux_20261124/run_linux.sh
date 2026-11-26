#!/bin/bash
# R5.M6 on the reference platform (Linux x86-64, WSL2): Table VI under scikit-learn 1.8.0 (~/prism_linux/py312, the pinned
# environment of label_fix_20261123/env/linux_py312_freeze.txt) and 1.9.1 (~/prism_linux/py312_sk191: the same pins with
# scikit-learn 1.9.1, which adds its dependency narwhals). Code: ~/prism_linux/fix/prism-repro (src/ and the experiment
# runner identical to HEAD 3edc386 after line-ending normalisation). Usage: bash run_linux.sh "<this dir>" "<table6_versions.py>"
set -u
O="$1"; S="$2"
cd ~/prism_linux/fix/prism-repro
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
echo "start $(date -u +%FT%TZ) $(uname -srm)" > "$O/run.log"
{ time ~/prism_linux/py312/bin/python "$S" . /tmp/t6_180.json ; } >> "$O/run.log" 2>&1
echo "mid $(date -u +%FT%TZ)" >> "$O/run.log"
{ time ~/prism_linux/py312_sk191/bin/python "$S" . /tmp/t6_191.json ; } >> "$O/run.log" 2>&1
cp /tmp/t6_180.json "$O/table6_sklearn_1.8.0.json"; cp /tmp/t6_191.json "$O/table6_sklearn_1.9.1.json"
~/prism_linux/py312/bin/python "$S" . --compare /tmp/t6_180.json /tmp/t6_191.json > "$O/comparison.txt" 2>&1
echo "end $(date -u +%FT%TZ) exit $?" >> "$O/run.log"
