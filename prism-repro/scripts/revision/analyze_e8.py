#!/usr/bin/env python3
"""E8 analysis (reference forecasters). Reference-forecaster rows come from E8 (run during revision;
numpy-only, environment-independent); gradient-boosting rows come from E2 (forecast) and E1 (provisioning),
which were produced in the original build environment.
Usage: python analyze_e8.py <repo_root> <e8_rows.jsonl> [<more e8 rows> ...]"""
import json, sys, os
import numpy as np, pandas as pd
from scipy import stats
ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import select_by_rule
rows = []
for p in sys.argv[2:]:
    rows += [json.loads(l) for l in open(p)]
df = pd.DataFrame(rows)
fc = df[df.kind == "forecast"].drop_duplicates(["seed", "scenario", "forecaster"], keep="last")
fc = fc[fc.forecaster != "gbm"]
e2 = pd.DataFrame([json.loads(l) for l in open(os.path.join(ROOT, "results/raw/E2/rows.jsonl"))])
e2 = e2[e2.forecaster == "gbm"]
F = pd.concat([e2, fc])
SC = ["stationary", "growth", "bursty", "new_spike"]
print("## Forecast accuracy (raw quantiles; mean over 5 traces x 4 scenarios)")
for f, g in F.groupby("forecaster"):
    print(f"{f:15s} n={len(g):2d} MAPE {g.mape_median.mean():5.1f}  pin50 {g.pinball_50.mean():6.1f}  pin90 {g.pinball_90.mean():6.1f}  pin99 {g.pinball_99.mean():5.1f}  cov90 {g.cov90_raw.mean()*100:5.1f}%  cov99 {g.cov99_raw.mean()*100:5.1f}%  cov99cal {g.cov99_cal.mean()*100:5.1f}%")
print("\n## By scenario: MAPE / cov99 raw")
for f, g in F.groupby("forecaster"):
    print(f, " | ".join(f"{s}: {g[g.scenario==s].mape_median.mean():.1f}/{g[g.scenario==s].cov99_raw.mean()*100:.1f}" for s in SC))
# downstream
runs = df[df.kind != "forecast"].drop_duplicates("run_id", keep="last")
e1 = pd.DataFrame([json.loads(l) for l in open(os.path.join(ROOT, "results/raw/E1/rows.jsonl"))]).drop_duplicates("run_id", keep="last")
e1 = e1[e1.policy.isin(["PRISM", "QuantProv_q99"])].copy()
e1["policy"] = e1.policy.map({"PRISM": "PRISM[gbm]", "QuantProv_q99": "QuantProv_q99[gbm]"})
allr = pd.concat([e1, runs])
out = []
for (seed, pol), g in allr[allr.week == "val"].groupby(["seed", "policy"]):
    sel = select_by_rule(g.to_dict("records"))
    t = allr[(allr.week == "test") & (allr.seed == seed) & (allr.label == sel["label"])]
    for _, r in t.iterrows():
        out.append(dict(seed=seed, policy=pol, param=sel["param"], scenario=r.scenario, cost=r.cost, viol=r.violating_window_rate))
O = pd.DataFrame(out)
print("\n## Downstream (validation-tuned; test weeks; mean over traces): cost / viol% ; n traces")
order = ["PRISM[gbm]", "QuantProv_q99[gbm]", "PRISM[seasonal_naive]", "QuantProv_q99[seasonal_naive]", "PRISM[ewma]", "QuantProv_q99[ewma]", "PRISM[last5max]", "QuantProv_q99[last5max]"]
for p in order:
    g = O[O.policy == p]
    cells = []
    for s in SC:
        h = g[g.scenario == s]
        cells.append(f"{h.cost.mean():,.0f} / {h.viol.mean()*100:.2f}")
    allw = g
    print(f"{p:30s} " + " | ".join(cells) + f" || all20: {allw.cost.mean():,.0f} / {allw.viol.mean()*100:.2f} / meet {np.mean(allw.viol<=0.02+1e-12)*100:.0f}%  n={g.seed.nunique()} params={sorted(set(g.param))}")
# paired: reference PRISM vs GBM PRISM cost %
print("\n## Paired cost difference vs GBM (same method), % (mean ± t-hw over 5 traces), all scenarios pooled per trace")
for m in ["PRISM", "QuantProv_q99"]:
    base = O[O.policy == f"{m}[gbm]"].set_index(["seed", "scenario"])
    for f in ["seasonal_naive", "ewma", "last5max"]:
        o = O[O.policy == f"{m}[{f}]"].set_index(["seed", "scenario"])
        d = ((o.cost / base.cost - 1) * 100).groupby("seed").mean()
        dv = ((o.viol - base.viol) * 100).groupby("seed").mean()
        hw = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
        hv = stats.t.ppf(0.975, len(dv) - 1) * dv.std(ddof=1) / np.sqrt(len(dv))
        print(f"{m:14s} {f:15s} cost {d.mean():+6.1f} ± {hw:4.1f}%  viol {dv.mean():+5.2f} ± {hv:4.2f} pp  traces dearer {int((d>0).sum())}/5")
O.to_csv(os.path.join(os.path.dirname(sys.argv[2]), "E8_downstream_selected.csv"), index=False)
