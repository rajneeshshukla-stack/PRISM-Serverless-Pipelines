#!/usr/bin/env python3
"""Which paired differences in the submitted comparisons are statistically distinguishable from zero (R7.6, R5.M7(d),
R6.4). Stored rows only; no new simulation. SUBMITTED values (pre-calibration), recomputed from results/raw.

For each comparison, PRISM minus comparator per trace (n = 5 traces), mean and 95% t interval (df = 4), and whether the
interval excludes zero. Three sets:
  A. Selected configurations (validation rule), per test scenario (Table VI analogue; E1 rows). The PRISM vs
     QuantProv-q90 and PRISM vs PredHead+S rows are checked against results/tables/T6_paired_*.md.
  B. Matched compliance (POST HOC, interpolated; Table VII analogue): the per-trace method of
     scripts/revision/matched_compliance_pertrace.py on results/tables/revision/pc_billing_runs.csv.
  C. Real-trace replay (POST HOC; Table XII analogue; R1 rows).
An interval that includes zero means the five traces cannot distinguish the two policies at the 95% level; it is
not evidence that they are equal (no equivalence margin is tested here: that choice is the author's).

Usage: python statistical_meaning.py <code_root> <out_file>
"""
import json
import os
import sys

import numpy as np
from scipy import stats

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import select_by_rule  # noqa: E402

SC = ("stationary", "growth", "bursty", "new_spike")
COMP = ("QuantProv_q90", "QuantProv_q99", "PredHead+hyst", "PredHead", "Reactive", "Static", "Scheduled")


def fam(spec):
    f = spec["family"]
    if f == "QuantProv":
        f += {2: "_q90", 3: "_q99"}[spec["tau_idx"]]
    if spec.get("hyst"):
        f += "+hyst"
    return f


def ci(d):
    d = np.asarray(d, float)
    hw = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
    return d.mean(), hw


def verdict(m, hw):
    return "excludes 0" if abs(m) > hw else "includes 0"


L = []
P = L.append
P("# Which paired differences are distinguishable from zero (submitted rows; n = 5 traces; 95% t intervals)")
P("")
P("Pre-calibration, submitted code and values. 'includes 0' = the five traces cannot distinguish the policies at the")
P("95% level; it is not a demonstration of equivalence. Built by scripts/revision/statistical_meaning.py.")
P("")
# ---------------------------------------------------------------------------- A
rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "E1", "rows.jsonl"), encoding="utf-8")]
rows = [r for r in rows if r.get("status") == "ok" and not r.get("tag") and r.get("spec", {}).get("family") != "OnDemand"]
seeds = sorted({r["seed"] for r in rows})
sel = {}
for s in seeds:
    for f in ("PRISM",) + COMP:
        v = [r for r in rows if r["seed"] == s and r["week"] == "val" and fam(r["spec"]) == f]
        sel[(s, f)] = select_by_rule(v)["label"]
test = {(r["seed"], r["scenario"], r["label"]): r for r in rows if r["week"] == "test"}
P("## A. Selected configurations (validation rule), PRISM minus comparator, per test scenario")
P("")
P("| Comparator | Scenario | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |")
P("|---|---|---|---|---|---|")
summary = {"A": [0, 0, 0, 0]}
for c in COMP:
    for sc in SC + ("all four",):
        dc, dv = [], []
        for s in seeds:
            scs = SC if sc == "all four" else (sc,)
            p = [test[(s, x, sel[(s, "PRISM")])] for x in scs]
            q = [test[(s, x, sel[(s, c)])] for x in scs]
            dc.append(100 * (np.mean([a["cost"] for a in p]) / np.mean([b["cost"] for b in q]) - 1))
            dv.append(100 * (np.mean([a["violating_window_rate"] for a in p]) - np.mean([b["violating_window_rate"] for b in q])))
        mc, hc = ci(dc)
        mv, hv = ci(dv)
        summary["A"][0] += verdict(mc, hc) == "excludes 0"; summary["A"][1] += 1
        summary["A"][2] += verdict(mv, hv) == "excludes 0"; summary["A"][3] += 1
        P(f"| {c} | {sc} | {mc:+.1f} +/- {hc:.1f} | {verdict(mc, hc)} | {mv:+.2f} +/- {hv:.2f} | {verdict(mv, hv)} |")
P("")
# check against the stored T6 tables (per scenario, cost % and violating-window points)
for c, fn in (("QuantProv_q90", "T6_paired_PRISM_vs_QuantProvq90.md"), ("PredHead+hyst", "T6_paired_PRISM_vs_PredHeadHyst.md")):
    txt = open(os.path.join(ROOT, "results", "tables", fn), encoding="utf-8").read()
    ok = 0
    for sc in SC:
        dc = [100 * (test[(s, sc, sel[(s, 'PRISM')])]["cost"] / test[(s, sc, sel[(s, c)])]["cost"] - 1) for s in seeds]
        mc, hc = ci(dc)
        ok += f"{mc:.1f} ± {hc:.1f}" in txt
    P(f"Check: PRISM vs {c} per-scenario cost % reproduces {fn} in {ok} of 4 scenarios.")
P("")
# ---------------------------------------------------------------------------- B
import pandas as pd  # noqa: E402
D = pd.read_csv(os.path.join(ROOT, "results", "tables", "revision", "pc_billing_runs.csv"))
T = D[D.week == "test"]


def envelope(df):
    g = df.groupby("param").agg(cost=("cost", "mean"), viol=("viol", "mean")).reset_index().sort_values(["viol", "cost"])
    keep, best = [], np.inf
    for _, r in g.iterrows():
        if r.cost < best - 1e-9:
            keep.append((r.viol, r.cost)); best = r.cost
    return keep


def at(keep, t):
    if t < keep[0][0] - 1e-12:
        return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1:
            return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return np.nan


P("## B. Matched compliance (POST HOC, interpolated per trace over its four test weeks), PRISM minus comparator")
P("")
P("| Target | Comparator | Cost % (mean +/- hw) | n traces | Cost |")
P("|---|---|---|---|---|")
summary["B"] = [0, 0]
for t in (1.0, 1.5, 2.0):
    C = {f: [at(envelope(T[(T.policy == f) & (T.seed == s)]), t / 100) for s in sorted(T.seed.unique())]
         for f in ("PRISM", "QuantProv_q90", "PredHead+hyst", "Static", "Reactive")}
    p = np.array(C["PRISM"], float)
    for f in ("QuantProv_q90", "PredHead+hyst", "Static", "Reactive"):
        q = np.array(C[f], float)
        ok = ~np.isnan(p) & ~np.isnan(q)
        d = 100 * (p[ok] / q[ok] - 1)
        m, hw = ci(d)
        summary["B"][0] += verdict(m, hw) == "excludes 0"; summary["B"][1] += 1
        P(f"| {t:.1f}% | {f} | {m:+.1f} +/- {hw:.1f} | {ok.sum()} | {verdict(m, hw)} |")
P("")
# ---------------------------------------------------------------------------- C
r1 = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "R1", "rows.jsonl"), encoding="utf-8")]
r1 = [r for r in r1 if r.get("status") == "ok" and r.get("spec") and not r.get("tag") and r["spec"].get("family") != "OnDemand"]
rs = sorted({r["seed"] for r in r1})
P("## C. Real-trace replay (POST HOC), selected configurations, PRISM minus comparator")
P("")
P("| Comparator | Cost % (mean +/- hw) | Cost | Violating windows, points | Violating windows |")
P("|---|---|---|---|---|")
summary["C"] = [0, 0, 0, 0]
for c in COMP:
    dc, dv = [], []
    for s in rs:
        def pick(f):
            v = [r for r in r1 if r["seed"] == s and r["week"] == "val" and fam(r["spec"]) == f]
            lab = select_by_rule(v)["label"]
            return [r for r in r1 if r["seed"] == s and r["week"] == "test" and r["label"] == lab][0]
        a, b = pick("PRISM"), pick(c)
        dc.append(100 * (a["cost"] / b["cost"] - 1))
        dv.append(100 * (a["violating_window_rate"] - b["violating_window_rate"]))
    mc, hc = ci(dc)
    mv, hv = ci(dv)
    summary["C"][0] += verdict(mc, hc) == "excludes 0"; summary["C"][1] += 1
    summary["C"][2] += verdict(mv, hv) == "excludes 0"; summary["C"][3] += 1
    P(f"| {c} | {mc:+.1f} +/- {hc:.1f} | {verdict(mc, hc)} | {mv:+.2f} +/- {hv:.2f} | {verdict(mv, hv)} |")
P("")
P("## Summary")
P(f"- A: cost intervals excluding zero {summary['A'][0]} of {summary['A'][1]}; violating-window intervals {summary['A'][2]} of {summary['A'][3]}.")
P(f"- B: cost intervals excluding zero {summary['B'][0]} of {summary['B'][1]}.")
P(f"- C: cost intervals excluding zero {summary['C'][0]} of {summary['C'][1]}; violating-window intervals {summary['C'][2]} of {summary['C'][3]}.")
txt = "\n".join(L) + "\n"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print(txt)
