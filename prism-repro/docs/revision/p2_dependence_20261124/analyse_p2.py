#!/usr/bin/env python3
"""Analysis of the P2 closed-loop sensitivity (RUN_PLAN.md). usage: python analyse_p2.py <p2 out> <calib_cmp out> <result.json>
IND at 13 s is the per-size run of ../calibration_final_20261124/ (set C13_meas, same factors and code path; the G0
check shows this build reproduces that code path exactly at rho = 0)."""
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

OUT, CMP, RES = sys.argv[1:4]
DEV5, DEV3 = (101, 102, 103, 104, 105), (101, 102, 103)
K_EPS = {101: 0.01, 102: 0.01, 103: 0.03, 104: 0.03, 105: 0.03}
QP_A = {101: 1.3, 102: 1.5, 103: 1.1, 104: 1.2, 105: 1.2}


def load(d, st):
    rows = {}
    for p in glob.glob(os.path.join(d, "weeks", st, "*", "*", "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        k = (r["seed"], r["family"], r["week"], json.dumps(r["param"]))
        assert k not in rows, ("duplicate", st, k)
        npz = p[:-5] + ".npz"
        if os.path.exists(npz):
            me = np.load(npz)["mem_epoch"]
            r["mem_share"] = {m: round(float(np.mean(me == m)), 4) for m in (512, 1024, 2048, 3008) if np.any(me == m)}
        rows[k] = r
    return rows


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def b(r):
    return dict(cost=round(r["cost"], 1), viol=round(100 * r["violating_window_rate"], 3),
                meets=bool(r["violating_window_rate"] <= 0.02 + 1e-12), mem=r.get("mem_share"))


def paired(I, S, seeds):
    dc = [100 * (S[s]["cost"] - I[s]["cost"]) / I[s]["cost"] for s in seeds]
    dv = [100 * (S[s]["violating_window_rate"] - I[s]["violating_window_rate"]) for s in seeds]
    flips = [s for s in seeds if b(I[s])["meets"] != b(S[s])["meets"]]
    return dict(n=len(seeds), cost_pct=[float(np.mean(dc)), hw(dc)], viol_pp=[float(np.mean(dv)), hw(dv)],
                cost_excl0=bool(abs(np.mean(dc)) > hw(dc)), verdict_flips=flips,
                per_trace={s: dict(IND=b(I[s]), SHR=b(S[s])) for s in seeds})


W = {st: load(OUT, st) for st in ("I145", "S145", "I13", "S13")}
W["I13"] = load(CMP, "C13_meas")
shas = defaultdict(set)
for st, rows in W.items():
    for r in rows.values():
        shas[(r["seed"], r["week"], r["scenario"])].add(r["counts_sha256"])
res = dict(request_streams_identical=all(len(v) == 1 for v in shas.values()), weeks={k: len(v) for k, v in W.items()})
g = lambda st, fam, p, s, wk="test": W[st].get((s, fam, wk, json.dumps(p)))
G1 = {}
for fam, par in (("PRISM", K_EPS), ("MemAdapt_q90", QP_A)):
    I = {s: g("I145", fam, par[s], s) for s in DEV5}
    S = {s: g("S145", fam, par[s], s) for s in DEV5}
    ok = [s for s in DEV5 if I[s] and S[s]]
    if len(ok) >= 2:
        G1[fam] = paired(I, S, ok)
res["G1_fixed_14.5"] = G1
G3 = {}
for fam, p in (("PRISM", 0.01), ("MemAdapt_q90", 0.6)):
    I = {s: g("I13", fam, p, s) for s in DEV5}
    S = {s: g("S13", fam, p, s) for s in DEV5}
    ok = [s for s in DEV5 if I[s] and S[s]]
    if len(ok) >= 2:
        G3[fam] = paired(I, S, ok)
if G3.get("PRISM") and G3.get("MemAdapt_q90"):
    for model in ("IND", "SHR"):
        pr = {s: 100 * (G3["PRISM"]["per_trace"][s][model]["cost"] - G3["MemAdapt_q90"]["per_trace"][s][model]["cost"])
              / G3["MemAdapt_q90"]["per_trace"][s][model]["cost"] for s in G3["PRISM"]["per_trace"]}
        G3[f"premium_{model}"] = dict(per_trace=pr, mean=float(np.mean(list(pr.values()))))
res["G3_fixed_13"] = G3
G2 = {}
for st in ("I145", "S145"):
    for p in glob.glob(os.path.join(OUT, "groups", st, "*.json")):
        gr = json.load(open(p, encoding="utf-8"))
        ps = sorted(v["param"] for v in gr["validation"])
        t = gr["tests"][0]
        G2[f"{st}|{gr['seed']}|{gr['family']}"] = dict(selected=gr["selected"], expansions=gr["expansions"],
                                                       edge=bool(gr["selected"] in (ps[0], ps[-1]) and gr["expansions"]),
                                                       test=dict(cost=round(t["cost"], 1), viol=round(100 * t["violating_window_rate"], 3),
                                                                 meets=bool(t["violating_window_rate"] <= 0.02 + 1e-12),
                                                                 share_ge2048=round(t["share_mem_ge_2048"], 4)))
res["G2_retuned_14.5"] = G2
json.dump(res, open(RES, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("request_streams_identical", "weeks")}))
for grp in ("G1_fixed_14.5", "G3_fixed_13"):
    for fam, v in res[grp].items():
        if fam.startswith("premium"):
            print(grp, fam, round(v["mean"], 2), {s: round(x, 1) for s, x in v["per_trace"].items()})
            continue
        print(grp, fam, "SHR-IND cost %+.2f +/- %.2f%% viol %+.3f +/- %.3f pp flips %s" % (
            v["cost_pct"][0], v["cost_pct"][1], v["viol_pp"][0], v["viol_pp"][1], v["verdict_flips"]))
        for s, pt in v["per_trace"].items():
            print("   ", s, "IND", pt["IND"], "| SHR", pt["SHR"])
for k, v in sorted(G2.items()):
    print("G2", k, v)
