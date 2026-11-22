#!/usr/bin/env python3
"""Analyse the matched replay (R7.6, R5.M7(d)): 1.0% matched-compliance PRISM vs QuantProv-q90 per row set, the
per-trace paired observations, bracketing, and which change moves which family. Read-only on all inputs.
PRE-CALIBRATION, POST HOC, fast simulator, development traces 101-105.
usage: python analyse_replay.py <prism-repro root>   (writes replay_20261122/analysis.txt)"""
import csv, json, os, sys
from collections import defaultdict
import numpy as np
from scipy import stats

ROOT = sys.argv[1]
R = os.path.join(ROOT, "docs/revision/matched_compliance_discrepancy/replay_20261122")
SCEN = ("stationary", "growth", "bursty", "new_spike")
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "QuantProv_q90")
T = 0.010
out = []
P = out.append

def load_stored():
    d = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(ROOT, "results/tables/revision/pc_billing_runs.csv"), encoding="utf-8")):
        if r["week"] == "test" and r["policy"] in FAMS and r["param"] != "":
            d[(int(r["seed"]), r["policy"])][(r["scenario"], float(r["param"]))] = (float(r["viol"]), float(r["cost"]))
    return d

def load_grid():
    d = defaultdict(dict)
    grid = {"PRISM": {0.005, 0.01, 0.02, 0.03, 0.05, 0.08}, "QuantProv_q90": {round(0.6 + 0.1 * k, 1) for k in range(10)}}
    for s in SEEDS:
        for l in open(os.path.join(ROOT, f"docs/revision/grid_studies/rows_posthoc_{s}.jsonl"), encoding="utf-8"):
            r = json.loads(l)
            if r["stage"] == "grid_wide" and r["family"] in FAMS and r["param"] is not None and round(r["param"], 3) in grid[r["family"]]:
                d[(s, r["family"])][(r["scenario"], float(r["param"]))] = (r["violating_window_rate"], r["cost"])
    return d

def load_replay(variant):
    d = defaultdict(dict)
    for s in SEEDS:
        p = os.path.join(R, f"rows_{s}_{variant}.jsonl")
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    d[(s, r["family"])][(r["scenario"], float(r["param"]))] = (r["violating_window_rate"], r["cost"])
    return d

def points(d, s, fam):
    by = defaultdict(list)
    for (sc, p), vc in d.get((s, fam), {}).items():
        by[p].append(vc)
    return sorted((p, float(np.mean([v for v, _ in x])), float(np.mean([c for _, c in x]))) for p, x in by.items() if len(x) == 4)

def envelope(pts):
    keep, best = [], np.inf
    for p, v, c in sorted(pts, key=lambda x: (x[1], x[2])):
        if c < best - 1e-9:
            keep.append((p, v, c)); best = c
    return keep

def at(keep, t):
    if not keep or t < keep[0][1] - 1e-12:
        return np.nan, "below frontier"
    for a, b in zip(keep, keep[1:]):
        if a[1] <= t <= b[1]:
            return (a[2] + (b[2] - a[2]) * (t - a[1]) / (b[1] - a[1]) if b[1] > a[1] else a[2]), f"[{a[0]:g}, {b[0]:g}]"
    return np.nan, "beyond frontier"

def mc(dp, dq):
    """per-trace PRISM/QP - 1 at T, with PRISM rows from dp and QP rows from dq."""
    res = []
    for s in SEEDS:
        cp, bp = at(envelope(points(dp, s, "PRISM")), T)
        cq, bq = at(envelope(points(dq, s, "QuantProv_q90")), T)
        res.append((s, cp, bp, cq, bq, 100 * (cp / cq - 1) if np.isfinite(cp) and np.isfinite(cq) else np.nan))
    return res

def summ(xs):
    x = np.array([v for v in xs if np.isfinite(v)])
    if len(x) < 2:
        return f"n={len(x)}"
    hw = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return f"{x.mean():+5.2f} +/- {hw:4.2f} (n={len(x)}, {'excludes' if abs(x.mean()) > hw else 'includes'} 0)"

SETS = [("stored (Linux, submitted runs)", load_stored()), ("v1-submitted code, this laptop", load_replay("tag")),
        ("HEAD, occupancy + sampled", load_replay("occupancy+sampled")), ("HEAD, occupancy (exact attainment)", load_replay("occupancy")),
        ("HEAD, Erlang-B + sampled", load_replay("sampled")), ("HEAD defaults (grid_studies)", load_grid())]
P("MATCHED REPLAY ANALYSIS, 1.0% target, PRISM minus QuantProv-q90 (% of QuantProv-q90 cost); PRE-CALIBRATION, POST HOC")
P("Each set: per-trace frontier interpolation, four-scenario means, paired by trace, 95% t interval (df = n-1).")
P("")
res = {}
for name, d in SETS:
    r = mc(d, d); res[name] = r
    P(f"{name:38s} {summ([x[5] for x in r])}")
    for s, cp, bp, cq, bq, dd in r:
        P(f"    {s}: PRISM {cp:7.1f} {bp:15s} QP {cq:7.1f} {bq:15s} d {dd:+5.1f}")
P("")
P("Change between consecutive sets, per trace (d_next - d_prev, points) and paired 95% t interval:")
names = [n for n, _ in SETS]
for a, b in zip(names, names[1:]):
    pass
chain = [names[0], names[1], names[2], names[5]]
for a, b in [(names[0], names[1]), (names[1], names[2]), (names[2], names[3]), (names[2], names[4]), (names[3], names[5]), (names[4], names[5]), (names[2], names[5]), (names[0], names[5])]:
    da = [x[5] for x in res[a]]; db = [x[5] for x in res[b]]
    diff = [y - x for x, y in zip(da, db)]
    P(f"  {a} -> {b}: {summ(diff)}  per trace {np.round(diff, 1).tolist()}")
P("")
P("Swaps (PRISM rows from one set, QP rows from another):")
D = dict(SETS)
for pa, qa in [(names[5], names[0]), (names[0], names[5]), (names[3], names[2]), (names[2], names[3])]:
    P(f"  PRISM {pa} / QP {qa}: {summ([x[5] for x in mc(D[pa], D[qa])])}")
P("")
P("Per-setting change, mean over traces and scenarios (cost %, violating windows in points):")
for a, b in [(names[0], names[1]), (names[1], names[2]), (names[2], names[3]), (names[2], names[4]), (names[2], names[5])]:
    for fam in FAMS:
        dc, dv, n, same = [], [], 0, 0
        for s in SEEDS:
            A, B = D[a].get((s, fam), {}), D[b].get((s, fam), {})
            for k in A:
                if k in B:
                    n += 1
                    same += A[k] == B[k]
                    dc.append(100 * (B[k][1] / A[k][1] - 1)); dv.append(100 * (B[k][0] - A[k][0]))
        if n:
            P(f"  {fam:13s} {a} -> {b}: n={n}, identical {same}; cost {np.mean(dc):+.2f}% (range {min(dc):+.2f} to {max(dc):+.2f}); "
              f"viol {np.mean(dv):+.3f} pts (range {min(dv):+.2f} to {max(dv):+.2f})")
txt = "\n".join(out) + "\n"
open(os.path.join(R, "analysis.txt"), "w", encoding="utf-8", newline="\n").write(txt)
print(txt)
