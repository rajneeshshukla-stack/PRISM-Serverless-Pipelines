#!/usr/bin/env python3
"""Analysis of the bounded calibration check (RUN_PLAN.md). usage: python analyse_calib.py <out dir> <kappa out dir> <result.json>"""
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

OUT, KOUT, RES = sys.argv[1:4]
DEV5, DEV3 = (101, 102, 103, 104, 105), (101, 102, 103)
K_EPS = {101: 0.01, 102: 0.01, 103: 0.03, 104: 0.03, 105: 0.03}


def load(d, st):
    rows = {}
    for p in glob.glob(os.path.join(d, "weeks", st, "*", "*", "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        k = (r["seed"], r["family"], r["week"], r["scenario"], json.dumps(r["param"]))
        assert k not in rows, ("duplicate", st, k)
        npz = p[:-5] + ".npz"
        if os.path.exists(npz):
            a = np.load(npz)
            me = a["mem_epoch"]
            r["mem_share"] = {int(m): float(np.mean(me == m)) for m in (512, 1024, 2048, 3008)}
        rows[k] = r
    return rows


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def paired(a, b, seeds):
    dc = [100 * (b[s]["cost"] - a[s]["cost"]) / a[s]["cost"] for s in seeds]
    dv = [100 * (b[s]["violating_window_rate"] - a[s]["violating_window_rate"]) for s in seeds]
    return dict(cost_pct=dict(mean=float(np.mean(dc)), hw=hw(dc), per_trace=dc),
                viol_pp=dict(mean=float(np.mean(dv)), hw=hw(dv), per_trace=dv))


def brief(r):
    return dict(cost=round(r["cost"], 1), viol_pct=round(100 * r["violating_window_rate"], 3),
                meets=bool(r["violating_window_rate"] <= 0.02 + 1e-12), mem_share=r.get("mem_share"))


res = {}
W = {st: load(OUT, st) for st in ("E14_legacy", "E14_meas", "C13_legacy", "C13_meas")}
K = load(KOUT, "K")
# paired inputs: identical request streams per trace and week across every set
shas = defaultdict(set)
for st, rows in list(W.items()) + [("K", K)]:
    for r in rows.values():
        shas[(r["seed"], r["week"], r["scenario"])].add(r["counts_sha256"])
res["request_streams_identical"] = all(len(v) == 1 for v in shas.values())
res["weeks"] = {st: len(v) for st, v in W.items()}
# E14: legacy equality and default-deadline regression
eq, reg = {}, {}
for s in DEV5:
    k = (s, "PRISM", "test", "stationary", json.dumps(K_EPS[s]))
    L, Kr, M = W["E14_legacy"].get(k), K.get(k), W["E14_meas"].get(k)
    if L and Kr:
        eq[s] = dict(cost_equal=L["cost"] == Kr["cost"], viol_equal=L["violating_window_rate"] == Kr["violating_window_rate"],
                     all_keys_equal=all(L[x] == Kr[x] for x in ("cost", "violating_window_rate", "record_attainment",
                                                                   "cold_start_ratio", "overflow_share", "p99_latency")))
    if L and M:
        reg[s] = dict(legacy=brief(L), measured=brief(M), cost_change_pct=100 * (M["cost"] - L["cost"]) / L["cost"],
                      verdict_changed=brief(L)["meets"] != brief(M)["meets"])
res["E14_legacy_equals_K"] = eq
res["E14_regression"] = reg
# F13: fixed policies at 13 s
F = {}
for fam, p in (("PRISM", 0.01), ("MemAdapt_q90", 0.6)):
    a = {s: W["C13_legacy"].get((s, fam, "test", "stationary", json.dumps(p))) for s in DEV5}
    b = {s: W["C13_meas"].get((s, fam, "test", "stationary", json.dumps(p))) for s in DEV5}
    ok = [s for s in DEV5 if a[s] and b[s]]
    F[fam] = dict(traces=ok, legacy={s: brief(a[s]) for s in ok}, measured={s: brief(b[s]) for s in ok},
                  measured_minus_legacy=paired(a, b, ok) if len(ok) > 1 else None)
prem = {}
for model, st in (("legacy", "C13_legacy"), ("measured", "C13_meas")):
    pr = {}
    for s in DEV5:
        P = W[st].get((s, "PRISM", "test", "stationary", json.dumps(0.01)))
        M = W[st].get((s, "MemAdapt_q90", "test", "stationary", json.dumps(0.6)))
        if P and M:
            pr[s] = 100 * (P["cost"] - M["cost"]) / M["cost"]
    prem[model] = dict(per_trace=pr, mean=float(np.mean(list(pr.values()))) if pr else None,
                       hw=hw(list(pr.values())) if len(pr) > 1 else None)
F["prism_minus_memadapt_pct"] = prem
res["F13"] = F
# R13: retuned
R = {}
for st in ("C13_legacy", "C13_meas"):
    for p in glob.glob(os.path.join(OUT, "groups", st, "*.json")):
        g = json.load(open(p, encoding="utf-8"))
        ps = sorted(v["param"] for v in g["validation"])
        R[f"{st}|{g['seed']}|{g['family']}"] = dict(selected=g["selected"], expansions=g["expansions"],
                                                     at_widened_edge=g["selected"] in (ps[0], ps[-1]) and bool(g["expansions"]),
                                                     test=brief(g["tests"][0]))
res["R13"] = R
json.dump(res, open(RES, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("request_streams_identical", "weeks", "E14_legacy_equals_K")}, indent=1))
for s, r in reg.items():
    print("E14", s, r["legacy"]["cost"], "->", r["measured"]["cost"], f"{r['cost_change_pct']:+.2f}%", r["legacy"]["viol_pct"], "->",
          r["measured"]["viol_pct"], "verdict changed" if r["verdict_changed"] else "")
for fam in ("PRISM", "MemAdapt_q90"):
    f = F[fam]
    for s in f["traces"]:
        print("F13", fam, s, f["legacy"][s]["cost"], "->", f["measured"][s]["cost"], "| viol", f["legacy"][s]["viol_pct"], "->",
              f["measured"][s]["viol_pct"], "| mem legacy", f["legacy"][s]["mem_share"], "measured", f["measured"][s]["mem_share"])
    if f["measured_minus_legacy"]:
        m = f["measured_minus_legacy"]
        print("F13", fam, "measured - legacy: cost %+.2f +/- %.2f%%, viol %+.3f +/- %.3f pp" % (
            m["cost_pct"]["mean"], m["cost_pct"]["hw"], m["viol_pp"]["mean"], m["viol_pp"]["hw"]))
print("F13 PRISM - MemAdapt premium:", {k: (round(v["mean"], 2) if v["mean"] is not None else None, v["per_trace"]) for k, v in prem.items()})
for k, v in sorted(R.items()):
    print("R13", k, v)
