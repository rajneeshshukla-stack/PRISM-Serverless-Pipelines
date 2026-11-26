#!/usr/bin/env python3
"""R3.6: run scripts/revision/level_choice_diagnostic.py on the regenerated rows at the regenerated selections.

Why: the diagnostic re-runs PRISM "at each trace's validation-selected epsilon", but it hard-codes the submitted
selections (SEL = {101: 0.02, 102: 0.03, 103: 0.05, 104: 0.05, 105: 0.05}, from the stored
E1_selected_parameters.md). On the regenerated E1 (current code, Erlang-B main configuration since f119bee) the
validation rule selects different eps values, so running the script unchanged would diagnose settings that are no
longer the selected ones.

What it does: computes each trace's selection from the regenerated E1 validation rows with the common rule
(prism_repro.experiment.select_by_rule over PRISM's untagged, successful rows; the same filter as
supplement_pertrace_tables.py), replaces that one SEL line in the script's source, and executes the source unchanged
otherwise. The script's "stored" columns then hold the regenerated E1 rows at the same eps, so its
max_abs_cost_pct_vs_stored and max_abs_viol_pp_vs_stored are a determinism check. The selections and the replaced line
are written next to the output as <out>.selection.json.

usage: python level_choice_regenerated.py <tree prism-repro> <out.json>   (run after normalize_labels.py)
"""
import json
import os
import sys

TREE, OUT = os.path.abspath(sys.argv[1]), sys.argv[2]
sys.path.insert(0, os.path.join(TREE, "src"))
from prism_repro.experiment import select_by_rule  # noqa: E402

SCRIPT = os.path.join(TREE, "scripts", "revision", "level_choice_diagnostic.py")
OLD = "SEL = {101: 0.02, 102: 0.03, 103: 0.05, 104: 0.05, 105: 0.05}   # results/tables/E1_selected_parameters.md"
rows = [json.loads(l) for l in open(os.path.join(TREE, "results", "raw", "E1", "rows.jsonl"), encoding="utf-8")]
sel = {}
for s in (101, 102, 103, 104, 105):
    v = [r for r in rows if r["seed"] == s and r["week"] == "val" and r.get("status") == "ok"
         and r["spec"]["family"] == "PRISM" and not r.get("tag")]
    sel[s] = float(select_by_rule(v)["spec"]["param"])
src = open(SCRIPT, encoding="utf-8").read()
if src.count(OLD) != 1:
    sys.exit(f"expected the SEL line exactly once in {SCRIPT}")
new = f"SEL = {sel!r}   # regenerated E1 selections (level_choice_regenerated.py)"
if OUT == "--dry":                      # show the selections and the replacement; run nothing
    print("selections:", sel, "\nreplaces:", OLD, "\nwith:    ", new)
    sys.exit(0)
json.dump(dict(selections=sel, replaced=OLD, with_=new), open(OUT + ".selection.json", "w", encoding="utf-8",
                                                             newline="\n"), indent=1)
print("selections:", sel, flush=True)
sys.argv = [SCRIPT, TREE, OUT]
exec(compile(src.replace(OLD, new), SCRIPT, "exec"), {"__name__": "__main__", "__file__": SCRIPT})
