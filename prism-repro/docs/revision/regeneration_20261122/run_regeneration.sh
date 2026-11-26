#!/usr/bin/env bash
# R3.6: regenerate every stored table from one commit, one environment and one platform (PRE-CALIBRATION).
# The tree is `git archive <commit> prism-repro`, exported to an ignored folder, with its copy of results/raw,
# results/tables and results/figures removed first, so nothing can read a submitted row. results/ of the
# repository itself is never written.
#
# usage (from anywhere, with absolute paths): bash <dir>/run_regeneration.sh <tree>/prism-repro <python> lane1|lane2|rest|post|analyse
# (post also needs REPO_ROOT=<repository prism-repro>, read only, for the stored tables it compares against)
set -uo pipefail
TREE="$1"; PY="$2"; LANE="$3"
cd "$TREE" || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
# UTF-8 mode: on Windows, redirected stdout and open() without an encoding default to cp1252, so captured tables
# ("±", "≤") were written in cp1252 and later read as UTF-8 (first post attempt, 23 Nov 18:53 UTC). I/O only.
export PYTHONUTF8=1
LOG="results/logs/regeneration_${LANE}.log"
mkdir -p results/raw results/tables/revision results/logs
step () {   # step <name> <command...>: run, time and log one step; continue on failure, record the exit code
  local name="$1"; shift
  local t0; t0=$(date -u +%s)
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START $name: $*" >> "$LOG"
  "$@" > "results/logs/${name}.out" 2> "results/logs/${name}.err"
  local rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) END   $name: exit $rc, $(( $(date -u +%s) - t0 )) s" >> "$LOG"
}
capture () {  # capture <name> <outfile> <command...>: as step, with stdout written to <outfile>
  local name="$1" outfile="$2"; shift 2
  local t0; t0=$(date -u +%s)
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START $name: $* > $outfile" >> "$LOG"
  "$@" > "$outfile" 2> "results/logs/${name}.err"
  local rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) END   $name: exit $rc, $(( $(date -u +%s) - t0 )) s" >> "$LOG"
}
S5="101 102 103 104 105"
case "$LANE" in
  lane1)
    step tests_full "$PY" -m unittest discover -s tests -v
    step E1  "$PY" experiments/run_experiments.py --exp E1  --seeds $S5
    step E9  "$PY" experiments/run_experiments.py --exp E9  --seeds 101 102 103
    mkdir -p results/raw/E12
    step E12 "$PY" scripts/revision/e12_event_retune.py . results/raw/E12 $S5
    step E2  "$PY" experiments/run_experiments.py --exp E2  --seeds $S5
    step E3  "$PY" experiments/run_experiments.py --exp E3  --seeds $S5
    step E10 "$PY" experiments/run_experiments.py --exp E10 --seeds 101
    step E4  "$PY" experiments/run_experiments.py --exp E4  --seeds 101 102
    step E6  "$PY" experiments/run_experiments.py --exp E6  --seeds $S5
    step E7  "$PY" experiments/run_experiments.py --exp E7  --seeds $S5
    step E5  "$PY" experiments/run_experiments.py --exp E5  --seeds 101 102
    step E11 "$PY" experiments/run_experiments.py --exp E11 --seeds $S5
    mkdir -p results/raw/E4b results/raw/R2
    for s in 101 102; do
      step "E4b_fixed_$s"    "$PY" scripts/revision/e4b_fixed_memory.py . "results/raw/E4b/e4b_seed$s.jsonl" "$s"
      step "E4b_ondemand_$s" "$PY" scripts/revision/e4b_ondemand.py     . "results/raw/E4b/e4b_ondemand_seed$s.jsonl" "$s"
      step "E4b_eps_$s"      "$PY" scripts/revision/e4b_prism_eps.py    . "results/raw/E4b/e4b_prism_eps_seed$s.jsonl" "$s"
      step "R2_$s"           "$PY" scripts/revision/r2_quantprov_memory.py . "results/raw/R2/r2_seed$s.jsonl" "$s"
    done
    step R1  "$PY" experiments/run_real_traces.py
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) LANE1 DONE" >> "$LOG"
    ;;
  lane2)
    step E8  "$PY" experiments/run_experiments.py --exp E8  --seeds $S5
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) LANE2 DONE" >> "$LOG"
    ;;
  rest)   # the steps still to run after lanes 1 and 2 were stopped, one at a time. E1 and E8 are complete; E9 failed
          # at fd8b01a (KeyError 'PRISM', results/logs/E9_unshimmed_failure.err), so E9, E3 and E7, which look up
          # PRISM's selection by name, run through run_exp_selection_shim.py; E12 resumes per run (seeds 101-103 complete)
    HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"; HERE="${REGEN_SCRIPTS:-$HERE}"
    step E9  "$PY" "$HERE/run_exp_selection_shim.py" . --exp E9 --seeds 101 102 103
    mkdir -p results/raw/E12
    step E12 "$PY" scripts/revision/e12_event_retune.py . results/raw/E12 $S5
    step E2  "$PY" experiments/run_experiments.py --exp E2  --seeds $S5
    step E3  "$PY" "$HERE/run_exp_selection_shim.py" . --exp E3 --seeds $S5
    step E10 "$PY" experiments/run_experiments.py --exp E10 --seeds 101
    step E4  "$PY" experiments/run_experiments.py --exp E4  --seeds 101 102
    step E6  "$PY" experiments/run_experiments.py --exp E6  --seeds $S5
    step E7  "$PY" "$HERE/run_exp_selection_shim.py" . --exp E7 --seeds $S5
    step E5  "$PY" experiments/run_experiments.py --exp E5  --seeds 101 102
    step E11 "$PY" experiments/run_experiments.py --exp E11 --seeds $S5
    step E11occ "$PY" "$HERE/e11_occupancy.py" . run
    mkdir -p results/raw/E4b results/raw/R2
    for s in 101 102; do
      step "E4b_fixed_$s"    "$PY" scripts/revision/e4b_fixed_memory.py . "results/raw/E4b/e4b_seed$s.jsonl" "$s"
      step "E4b_ondemand_$s" "$PY" scripts/revision/e4b_ondemand.py     . "results/raw/E4b/e4b_ondemand_seed$s.jsonl" "$s"
      step "E4b_eps_$s"      "$PY" scripts/revision/e4b_prism_eps.py    . "results/raw/E4b/e4b_prism_eps_seed$s.jsonl" "$s"
      step "R2_$s"           "$PY" scripts/revision/r2_quantprov_memory.py . "results/raw/R2/r2_seed$s.jsonl" "$s"
    done
    step R1  "$PY" experiments/run_real_traces.py
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) REST DONE" >> "$LOG"
    ;;
  post)   # analysis copy with normalised PRISM labels, then every analysis; one at a time
    HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"; HERE="${REGEN_SCRIPTS:-$HERE}"; REPO="${REPO_ROOT:?set REPO_ROOT}"
    step normalize   "$PY" "$HERE/normalize_labels.py" .
    step analyze     "$PY" scripts/analyze.py
    capture analyze_e8  results/tables/revision/E8_reference_forecasters_analysis.txt "$PY" scripts/revision/analyze_e8.py . results/raw/E8/rows.jsonl
    capture analyze_e12 results/tables/revision/E12_event_level_retuning_analysis.txt "$PY" scripts/revision/analyze_e12.py results/raw/E12
    capture posthoc     results/tables/revision/posthoc_matched_compliance.txt "$PY" scripts/revision/posthoc_analysis.py .
    capture pc_billing  results/tables/revision/pc_billing_bounds.txt "$PY" scripts/revision/pc_billing_bounds.py .
    capture mc_pertrace results/tables/revision/matched_compliance_pertrace.txt "$PY" scripts/revision/matched_compliance_pertrace.py .
    step analyze_real   "$PY" scripts/revision/analyze_real_traces.py
    step analyze_r2     "$PY" scripts/revision/analyze_r2.py
    step analyze_e4b    "$PY" scripts/revision/analyze_e4b.py results/raw/E4/rows.jsonl results/tables/revision/E4b_fixed_memory_summary.json results/raw/E4b/e4b_seed101.jsonl results/raw/E4b/e4b_seed102.jsonl results/raw/E4b/e4b_ondemand_seed101.jsonl results/raw/E4b/e4b_ondemand_seed102.jsonl results/raw/E4b/e4b_prism_eps_seed101.jsonl results/raw/E4b/e4b_prism_eps_seed102.jsonl
    step level_choice   "$PY" "$HERE/level_choice_regenerated.py" . results/tables/revision/level_choice_diagnostic.json
    step e11_table      "$PY" "$HERE/e11_occupancy.py" . table
    step r5m4_runs      "$PY" "$HERE/r5m4_missing_runs.py" . results/r5m4_missing
    step supplement     "$PY" scripts/revision/supplement_pertrace_tables.py . results/tables/revision/supplement_pertrace
    step statistical    "$PY" scripts/revision/statistical_meaning.py . results/tables/revision/statistical_meaning/summary.md
    step relabel        "$PY" "$HERE/relabel_regenerated.py" .
    step r76            "$PY" "$HERE/r76_matched_1pct.py" . "$REPO" results/tables/revision/r76_matched_1pct.txt
    step compare        "$PY" "$HERE/compare_tables.py" "$REPO" . results/table_comparison
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) POST DONE" >> "$LOG"
    ;;
  analyse)
    step analyze "$PY" scripts/analyze.py
    capture analyze_e8  results/tables/revision/E8_reference_forecasters_analysis.txt "$PY" scripts/revision/analyze_e8.py . results/raw/E8/rows.jsonl
    capture analyze_e12 results/tables/revision/E12_event_level_retuning_analysis.txt "$PY" scripts/revision/analyze_e12.py results/raw/E12
    capture posthoc     results/tables/revision/posthoc_matched_compliance.txt "$PY" scripts/revision/posthoc_analysis.py .
    capture pc_billing  results/tables/revision/pc_billing_bounds.txt "$PY" scripts/revision/pc_billing_bounds.py .
    capture mc_pertrace results/tables/revision/matched_compliance_pertrace.txt "$PY" scripts/revision/matched_compliance_pertrace.py .
    step analyze_real   "$PY" scripts/revision/analyze_real_traces.py
    step analyze_r2     "$PY" scripts/revision/analyze_r2.py
    step analyze_e4b    "$PY" scripts/revision/analyze_e4b.py results/raw/E4/rows.jsonl results/tables/revision/E4b_fixed_memory_summary.json results/raw/E4b/e4b_seed101.jsonl results/raw/E4b/e4b_seed102.jsonl results/raw/E4b/e4b_ondemand_seed101.jsonl results/raw/E4b/e4b_ondemand_seed102.jsonl results/raw/E4b/e4b_prism_eps_seed101.jsonl results/raw/E4b/e4b_prism_eps_seed102.jsonl
    step level_choice   "$PY" scripts/revision/level_choice_diagnostic.py . results/tables/revision/level_choice_diagnostic.json
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ANALYSE DONE" >> "$LOG"
    ;;
esac
