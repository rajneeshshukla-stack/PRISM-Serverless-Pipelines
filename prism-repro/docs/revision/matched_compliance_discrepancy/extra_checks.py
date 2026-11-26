#!/usr/bin/env python3
"""Supporting checks for FINDINGS_20261122.md (read-only; PRE-CALIBRATION, POST HOC, fast simulator):
(1) the rows where the v1-submitted tree and HEAD with both switches reverted differ; (2) stored rows against the
v1-submitted tree rerun on this laptop, per trace; (3) the current-code real-trace replay (Table XII analogue), PRISM
minus QuantProv-q90 at the validation-selected paper-grid settings.
usage: python extra_checks.py <prism-repro root>   (writes replay_20261122/extra_checks.txt)"""
import csv, json, os, sys
import numpy as np
from scipy import stats
ROOT = sys.argv[1]
R = os.path.join(ROOT, "docs/revision/matched_compliance_discrepancy/replay_20261122")
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import GRIDS, select_by_rule
out = []; P = out.append
def rp(v):
    d = {}
    for s in (101, 102, 103, 104, 105):
        for l in open(os.path.join(R, f"rows_{s}_{v}.jsonl"), encoding="utf-8"):
            r = json.loads(l); d[(s, r["scenario"], r["family"], r["param"])] = (r["cost"], r["violating_window_rate"])
    return d
tag, os_ = rp("tag"), rp("occupancy+sampled")
diff = [k for k in tag if tag[k] != os_[k]]
P(f"(1) v1-submitted tree vs HEAD (occupancy + sampled): {len(tag) - len(diff)} of {len(tag)} rows identical; differing rows:")
for k in diff:
    P(f"    {k}: cost {100 * (os_[k][0] / tag[k][0] - 1):+.5f}%, violating windows {tag[k][1]:.5f} -> {os_[k][1]:.5f}")
st = {}
for r in csv.DictReader(open(os.path.join(ROOT, "results/tables/revision/pc_billing_runs.csv"), encoding="utf-8")):
    if r["week"] == "test" and r["policy"] in ("PRISM", "QuantProv_q90") and r["param"]:
        st[(int(r["seed"]), r["scenario"], r["policy"], float(r["param"]))] = (float(r["cost"]), float(r["viol"]))
P("(2) stored rows vs the v1-submitted tree on this laptop, per trace (PRISM and QuantProv-q90, 64 rows each):")
for s in (101, 102, 103, 104, 105):
    ks = [k for k in tag if k[0] == s and k in st]
    dc = [abs(100 * (tag[k][0] / st[k][0] - 1)) for k in ks]
    P(f"    {s}: identical {sum(st[k] == tag[k] for k in ks)}/{len(ks)}; mean |cost change| {np.mean(dc):.2f}%, max {max(dc):.2f}%")
g = {"PRISM": GRIDS["PRISM"], "QuantProv_q90": GRIDS["QuantProv"]}
c = {}
for s in (201, 202, 203, 204, 205):
    rows = [json.loads(l) for l in open(os.path.join(ROOT, f"docs/revision/grid_studies/rows_real_{s}.jsonl"), encoding="utf-8")]
    for fam in g:
        sel = select_by_rule([r for r in rows if r["family"] == fam and r["week"] == "val" and r["param"] in g[fam]])
        t = [r for r in rows if r["family"] == fam and r["week"] == "test" and r["param"] == sel["param"]][0]
        c[(s, fam)] = (sel["param"], t["cost"], t["violating_window_rate"])
d = np.array([100 * (c[(s, "PRISM")][1] / c[(s, "QuantProv_q90")][1] - 1) for s in (201, 202, 203, 204, 205)])
v = np.array([100 * (c[(s, "PRISM")][2] - c[(s, "QuantProv_q90")][2]) for s in (201, 202, 203, 204, 205)])
hw = lambda x: stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
P("(3) current-code real-trace replay (HEAD 78ba419, Huawei traces 201-205, paper grid, validation-selected), PRISM minus QuantProv-q90:")
P(f"    cost {d.mean():+.2f} +/- {hw(d):.2f}% (per trace {np.round(d, 1).tolist()}); violating windows {v.mean():+.2f} +/- {hw(v):.2f} points")
P(f"    selections: " + "; ".join(f"{s} PRISM {c[(s, 'PRISM')][0]:g} / QP {c[(s, 'QuantProv_q90')][0]:g}" for s in (201, 202, 203, 204, 205)))
txt = "\n".join(out) + "\n"
open(os.path.join(R, "extra_checks.txt"), "w", encoding="utf-8", newline="\n").write(txt)
print(txt)
