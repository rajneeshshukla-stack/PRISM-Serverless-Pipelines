"""R7.6 / R5.M7(d): why PRISM vs QuantProv-q90 at the 1.0% matched-compliance target is -0.4 +/- 3.3% on the stored rows
and -2.3 +/- 2.0% on the current-code rows. Read-only; recomputes from saved records only.
usage: python mc_discrepancy.py <prism-repro root>"""
import csv, json, os, sys
from collections import defaultdict
import numpy as np
from scipy import stats

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import GRIDS
SCEN = ("stationary", "growth", "bursty", "new_spike")
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "QuantProv_q90", "PredHead+hyst", "Static", "Reactive")
GRID = {"PRISM": GRIDS["PRISM"], "QuantProv_q90": GRIDS["QuantProv"], "PredHead+hyst": GRIDS["PredHead"],
        "Static": GRIDS["Static"], "Reactive": GRIDS["Reactive"]}

# stored: exactly the input of scripts/revision/matched_compliance_pertrace.py
stored = defaultdict(list)   # (seed, fam, param) -> [(scenario, viol, cost)]
for r in csv.DictReader(open(os.path.join(ROOT, "results/tables/revision/pc_billing_runs.csv"), encoding="utf-8")):
    if r["week"] == "test" and r["policy"] in FAMS and r["param"] != "":
        stored[(int(r["seed"]), r["policy"], float(r["param"]))].append((r["scenario"], float(r["viol"]), float(r["cost"])))
# current: fast_grid_studies rows, stage grid_wide, restricted to the paper's grid (as its 'interp' column)
current = defaultdict(list)
for s in SEEDS:
    for l in open(os.path.join(ROOT, f"docs/revision/grid_studies/rows_posthoc_{s}.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r["stage"] == "grid_wide" and r["family"] in FAMS and r.get("param") is not None and r["param"] in GRID[r["family"]]:
            current[(s, r["family"], float(r["param"]))].append((r["scenario"], r["violating_window_rate"], r["cost"]))

def points(src, s, fam):
    out = []
    for p in GRID[fam]:
        v = src.get((s, fam, float(p)), [])
        if sorted(x[0] for x in v) == sorted(SCEN):
            out.append((float(p), float(np.mean([x[1] for x in v])), float(np.mean([x[2] for x in v]))))
    return out

def envelope(pts):  # identical rule in both scripts
    keep, best = [], np.inf
    for p, v, c in sorted(pts, key=lambda x: (x[1], x[2])):
        if c < best - 1e-9:
            keep.append((p, v, c)); best = c
    return keep

def at(keep, t):
    if not keep or t < keep[0][1] - 1e-12:
        return np.nan, None
    for a, b in zip(keep, keep[1:]):
        if a[1] <= t <= b[1]:
            return (a[2] + (b[2] - a[2]) * (t - a[1]) / (b[1] - a[1]) if b[1] > a[1] else a[2]), (a[0], b[0])
    return np.nan, None

def paired(pc, qc):
    p, q = np.array(pc, float), np.array(qc, float)
    ok = np.isfinite(p) & np.isfinite(q)
    d = 100 * (p[ok] / q[ok] - 1)
    hw = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
    return d.mean(), hw, d

def interp_all(src, fam, t):
    return [at(envelope(points(src, s, fam)), t) for s in SEEDS]

T = 0.010
print("Inputs: stored = results/tables/revision/pc_billing_runs.csv (test weeks, submitted rows); current = "
      "docs/revision/grid_studies/rows_posthoc_*.jsonl (stage grid_wide, paper-grid settings only).")
print("Grid settings per family complete in all four scenarios (stored / current):",
      {f: (sum(len(points(stored, s, f)) for s in SEEDS), sum(len(points(current, s, f)) for s in SEEDS)) for f in FAMS})
print()
for name, P, Q in (("stored PRISM vs stored QP", stored, stored), ("current PRISM vs current QP", current, current),
                   ("current PRISM vs stored QP", current, stored), ("stored PRISM vs current QP", stored, current)):
    pc = [x[0] for x in interp_all(P, "PRISM", T)]; qc = [x[0] for x in interp_all(Q, "QuantProv_q90", T)]
    m, hw, d = paired(pc, qc)
    print(f"1.0%  {name:30s} {m:+5.1f} +/- {hw:3.1f}%  per trace {np.round(d, 1).tolist()}")
print()
for fam in ("PRISM", "QuantProv_q90"):
    a, b = interp_all(stored, fam, T), interp_all(current, fam, T)
    print(f"{fam}: interpolated cost at 1.0% per trace, stored -> current (bracketing settings):")
    for s, (cs, ss), (cc, sc) in zip(SEEDS, a, b):
        print(f"   {s}: {cs:7.1f} {ss} -> {cc:7.1f} {sc}   ({100*(cc/cs-1):+.1f}%)")
print()
print("Per setting, mean over the four test-week scenarios, current minus stored (cost %, violating windows in points):")
for fam in ("PRISM", "QuantProv_q90"):
    for s in SEEDS:
        ps = {p: (v, c) for p, v, c in points(stored, s, fam)}; pc_ = {p: (v, c) for p, v, c in points(current, s, fam)}
        cells = [f"{p:g}: {100*(pc_[p][1]/ps[p][1]-1):+.1f}% / {100*(pc_[p][0]-ps[p][0]):+.2f}" for p in sorted(ps) if p in pc_]
        print(f"   {fam:13s} {s}: " + "; ".join(cells))
