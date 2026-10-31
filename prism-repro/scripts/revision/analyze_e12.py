#!/usr/bin/env python3
"""Analyse E12 (event-level re-tuning on stored schedules). Usage: python analyze_e12.py <E12 dir>"""
import glob, json, os, sys
import numpy as np, pandas as pd
from scipy import stats
rows = []
for p in sorted(glob.glob(os.path.join(sys.argv[1], "E12_seed*.jsonl"))):
    rows += [json.loads(l) for l in open(p)]
df = pd.DataFrame(rows)
val = df[df.week == "val"]; test = df[df.week == "test"]
SC = ["stationary", "growth", "bursty", "new_spike"]
FAM = ["OnDemand", "Static", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "PRISM"]
seeds = sorted(test.seed.unique())
print("seeds complete:", seeds)
def hw(x):
    x = np.asarray(x, float); return stats.t.ppf(0.975, len(x)-1)*x.std(ddof=1)/np.sqrt(len(x)) if len(x) > 1 else float('nan')
print("\n## Selected parameter per seed (event-level validation)")
for f in FAM:
    sel = test[test.family == f].groupby("seed").spec.first()
    print(f"{f:15s}", {s: (v.get('param') if isinstance(v, dict) else v) for s, v in sel.items()})
print("\n## Validation: does any grid point reach <=2%? min viol per family per seed")
for f in FAM:
    g = val[val.family == f].groupby("seed").violating_window_rate.min()*100
    print(f"{f:15s}", {s: round(v, 2) for s, v in g.items()})
print("\n## Test weeks under event-level tuning: cost / viol% (mean ± hw over seeds)")
for sc in SC:
    print("--", sc)
    for f in FAM:
        g = test[(test.family == f) & (test.scenario == sc)]
        print(f"   {f:15s} {g.cost.mean():7,.0f} ± {hw(g.cost):4.0f} | {g.violating_window_rate.mean()*100:5.2f} ± {hw(g.violating_window_rate*100):4.2f} | meet {int((g.violating_window_rate<=0.02+1e-12).sum())}/{len(g)}")
print("\n## Aggregate over all test weeks")
for f in FAM:
    g = test[test.family == f]
    print(f"   {f:15s} cost {g.cost.mean():7,.0f}  viol {g.violating_window_rate.mean()*100:5.2f}  meet {np.mean(g.violating_window_rate<=0.02+1e-12)*100:4.0f}%  n={len(g)}")
print("\n## Paired PRISM minus X (per seed, per scenario)")
for x in ["PredHead", "PredHead+hyst", "QuantProv_q90", "Static", "Reactive"]:
    for sc in SC + ["all"]:
        a = test[(test.family == "PRISM") & ((test.scenario == sc) if sc != "all" else True)].set_index(["seed", "scenario"])
        b = test[(test.family == x) & ((test.scenario == sc) if sc != "all" else True)].set_index(["seed", "scenario"])
        dc = (a.cost / b.cost - 1) * 100; dv = (a.violating_window_rate - b.violating_window_rate) * 100
        if sc == "all":
            dc = dc.groupby("seed").mean(); dv = dv.groupby("seed").mean()
        print(f"   vs {x:14s} {sc:10s} cost {dc.mean():+6.1f} ± {hw(dc):4.1f}%  viol {dv.mean():+6.2f} ± {hw(dv):4.2f} pp  PRISM cheaper {int((dc<0).sum())}/{len(dc)}  fewer viol {int((dv<0).sum())}/{len(dv)}")
