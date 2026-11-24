#!/usr/bin/env python3
"""R7.6 / R5.M7: the 1.0% matched-compliance comparison, PRISM against QuantProv-q90, regenerated on one pinned
implementation. POST HOC (matched compliance uses test-week knowledge), EXPLORATORY, PRE-CALIBRATION, fast simulator,
development traces 101-105 (the stored Table VII design).

Input: the regenerated tree's results/tables/revision/pc_billing_runs.csv (written by scripts/revision/pc_billing_bounds.py
from the regenerated results/raw/E1), restricted to test weeks and the paper grid, exactly as the stored analysis and
docs/revision/matched_compliance_discrepancy/mc_discrepancy.py (whose envelope, interpolation and pairing rules are copied
verbatim below).

Reports, per trace and family: the settings bracketing each target on the lower-left (violating windows, cost) frontier
and their achieved violating-window rates; the interpolated cost; the cheapest evaluated setting that actually meets the
target (no interpolation); the paired PRISM / QuantProv-q90 - 1 difference with a 95% t interval (df 4); and the
prespecified classification (PRESPECIFICATION.md section 5 criteria, applied here to a post hoc comparison: a difference
only if the interval excludes zero, a tie only if it lies within +/- 2%).

usage: python r76_matched_1pct.py <regenerated tree prism-repro> <repo prism-repro> <out.txt>
"""
import csv
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

TREE, REPO, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(TREE, "src"))
from prism_repro.experiment import GRIDS  # noqa: E402

SCEN = ("stationary", "growth", "bursty", "new_spike")
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "QuantProv_q90")
GRID = {"PRISM": GRIDS["PRISM"], "QuantProv_q90": GRIDS["QuantProv"]}
L = []
P = L.append


def load(path):
    src = defaultdict(list)
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["week"] == "test" and r["policy"] in FAMS and r["param"] != "":
            src[(int(r["seed"]), r["policy"], float(r["param"]))].append((r["scenario"], float(r["viol"]), float(r["cost"])))
    return src


def points(src, s, fam):
    out = []
    for p in GRID[fam]:
        v = src.get((s, fam, float(p)), [])
        if sorted(x[0] for x in v) == sorted(SCEN):
            out.append((float(p), float(np.mean([x[1] for x in v])), float(np.mean([x[2] for x in v]))))
    return out


def envelope(pts):  # identical rule in both stored scripts
    keep, best = [], np.inf
    for p, v, c in sorted(pts, key=lambda x: (x[1], x[2])):
        if c < best - 1e-9:
            keep.append((p, v, c))
            best = c
    return keep


def at(keep, t):
    if not keep or t < keep[0][1] - 1e-12:
        return np.nan, None
    for a, b in zip(keep, keep[1:]):
        if a[1] <= t <= b[1]:
            return (a[2] + (b[2] - a[2]) * (t - a[1]) / (b[1] - a[1]) if b[1] > a[1] else a[2]), (a, b)
    return np.nan, None


def tint(d):
    d = np.asarray(d, float)
    return float(d.mean()), float(stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)))


def classify(m, h):
    lo, hi = m - h, m + h
    if hi < 0:
        return "difference (PRISM cheaper): interval excludes zero"
    if lo > 0:
        return "difference (PRISM costlier): interval excludes zero"
    if lo >= -2 and hi <= 2:
        return "tie: interval within +/-2%"
    return "not distinguishable: interval includes zero and extends beyond +/-2%"


regen = load(os.path.join(TREE, "results", "tables", "revision", "pc_billing_runs.csv"))
stored = load(os.path.join(REPO, "results", "tables", "revision", "pc_billing_runs.csv"))
P("R7.6: PRISM against QuantProv-q90 at matched compliance. POST HOC, EXPLORATORY, PRE-CALIBRATION, fast simulator,")
P("development traces 101-105, test weeks (four-scenario mean per setting), paper grid. Regenerated on one pinned")
P("implementation (the regeneration tree); the stored rows are shown for comparison.\n")
for T in (0.010, 0.015, 0.020):
    res = {}
    for name, src in (("regenerated", regen), ("stored", stored)):
        per = {}
        for fam in FAMS:
            per[fam] = []
            for s in SEEDS:
                keep = envelope(points(src, s, fam))
                c, br = at(keep, T)
                ev = [x for x in points(src, s, fam) if x[1] <= T + 1e-12]
                evc = min(ev, key=lambda x: (x[2], x[1])) if ev else None
                per[fam].append(dict(seed=s, cost=c, bracket=br, evaluated=evc, n_points=len(points(src, s, fam))))
        pairs = [(a["cost"], b["cost"]) for a, b in zip(per["PRISM"], per["QuantProv_q90"])]
        ok = [np.isfinite(a) and np.isfinite(b) for a, b in pairs]
        d = [100 * (a / b - 1) for (a, b), o in zip(pairs, ok) if o]
        ev_pairs = [(a["evaluated"], b["evaluated"]) for a, b in zip(per["PRISM"], per["QuantProv_q90"])]
        de = [100 * (a[2] / b[2] - 1) for a, b in ev_pairs if a and b]
        res[name] = (per, d, de, sum(ok))
    P(f"## Target {100 * T:.1f}% violating windows")
    for name in ("regenerated", "stored"):
        per, d, de, nok = res[name]
        if len(d) >= 2:
            m, h = tint(d)
            P(f"  {name:11s} interpolated: PRISM minus QuantProv-q90 {m:+.2f} +/- {h:.2f}% (n {len(d)}; per trace "
              f"{', '.join(f'{x:+.1f}' for x in d)}) -> {classify(m, h)}")
        if len(de) >= 2:
            m, h = tint(de)
            P(f"  {name:11s} evaluated (cheapest setting actually meeting the target, no interpolation): {m:+.2f} +/- {h:.2f}% "
              f"(n {len(de)}; {', '.join(f'{x:+.1f}' for x in de)})")
    per, d, de, nok = res["regenerated"]
    P(f"  bracketing (regenerated): {nok} of 5 traces bracketed for both families")
    for fam in FAMS:
        for e in per[fam]:
            br = e["bracket"]
            b_txt = (f"[{br[0][0]} at {100 * br[0][1]:.2f}%, {br[1][0]} at {100 * br[1][1]:.2f}%]" if br else "NOT BRACKETED")
            ev = e["evaluated"]
            ev_txt = f"{ev[0]} at {100 * ev[1]:.2f}%, cost {ev[2]:.1f}" if ev else "none meets the target"
            P(f"    {fam:14s} {e['seed']}: bracket {b_txt}; interpolated cost {e['cost']:.1f}; evaluated {ev_txt}; "
              f"{e['n_points']} complete settings")
    if T == 0.010:
        sd, rd = res["stored"][1], res["regenerated"][1]
        if len(sd) == len(rd) == 5:
            m, h = tint(np.array(rd) - np.array(sd))
            P(f"  change regenerated minus stored, paired by trace: {m:+.2f} +/- {h:.2f} points")
    P("")
P("Reference figures (docs/revision/matched_compliance_discrepancy/FINDINGS_20261122.md): stored -0.36 +/- 3.30%;")
P("controlled replay at HEAD defaults on this laptop -2.27 +/- 2.02% (exact attainment and Erlang-B switched on).")
open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("\n".join(L))
