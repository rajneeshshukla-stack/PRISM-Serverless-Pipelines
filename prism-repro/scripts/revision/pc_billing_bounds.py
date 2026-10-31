#!/usr/bin/env python3
"""Added in the pre-submission audit (post hoc; no new simulation). Usage: python pc_billing_bounds.py [<repo_root>]
Audit: size of two provisioned-concurrency (PC) billing components the cost model omits, computed from the
stored E1 schedules (no new simulation):
  (a) initialisation of newly provisioned environments, billed per environment added
      (rate bracket: provisioned-duration price π_pcd .. on-demand price π_od), and
  (b) billing of newly requested capacity during the 2-minute activation lag (π_pc), if AWS bills from request.
Then re-run the paper's selected-configuration and matched-compliance comparisons with the adjusted costs."""
import json, os, sys
import numpy as np, pandas as pd
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "tables", "revision", "pc_billing_runs.csv")
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig
from prism_repro.latency import init_mean
from prism_repro.experiment import select_by_rule
cfg = PipelineConfig(); pr = cfg.prices
INIT = {m: init_mean(cfg, m) for m in cfg.mem_options}
rows = pd.DataFrame([json.loads(l) for l in open(f"{ROOT}/results/raw/E1/rows.jsonl")]).drop_duplicates("run_id", keep="last")
out = []
for seed in sorted(rows.seed.unique()):
    arr = np.load(f"{ROOT}/results/raw/E1/arrays_seed{seed}.npz")
    for _, r in rows[rows.seed == seed].iterrows():
        sc = r.scenario if r.week == "test" else "stationary"
        key = f"E1|{seed}|{sc}|{r.week}|{r.label}|"
        P = arr[key + "::P_epoch"].astype(float); m = arr[key + "::mem_epoch"]
        g = m / 1024.0
        inc = np.maximum(np.diff(P, axis=0), 0.0)          # environments added per epoch (from epoch 1)
        added = inc.sum(axis=1)                               # per epoch, all stages
        ini = np.array([INIT[int(x)] for x in m[1:]])
        init_lo = float((added * ini * g[1:] * pr.pcd).sum())
        init_hi = float((added * ini * g[1:] * pr.od).sum())
        lag = float((added * 120.0 * g[1:] * pr.pc).sum())
        out.append(dict(seed=seed, week=r.week, scenario=r.scenario, policy=r.policy, label=r.label, param=r.param,
                        cost=r.cost, viol=r.violating_window_rate, added=float(added.sum()),
                        init_lo=init_lo, init_hi=init_hi, lag=lag))
D = pd.DataFrame(out)
D.to_csv(OUT, index=False)
val, test = D[D.week == "val"], D[D.week == "test"]
sel = []
for (seed, pol), g in val.groupby(["seed", "policy"]):
    s = select_by_rule(g.rename(columns={"viol": "violating_window_rate"}).to_dict("records"))
    sel.append(test[(test.seed == seed) & (test.label == s["label"])])
S = pd.concat(sel)
print("## Selected configurations, all 20 test weeks: omitted PC billing as % of modelled cost")
for pol, g in S.groupby("policy"):
    print(f"{pol:15s} added env/week {g.added.mean():9,.0f}   init {100*g.init_lo.sum()/g.cost.sum():4.2f}–{100*g.init_hi.sum()/g.cost.sum():4.2f}%   "
          f"activation-lag {100*g.lag.sum()/g.cost.sum():4.2f}%   both(upper) {100*(g.init_hi+g.lag).sum()/g.cost.sum():4.2f}%")

def envelope(df, col):
    g = df.groupby("param").agg(cost=(col, "mean"), viol=("viol", "mean")).reset_index().sort_values(["viol", "cost"])
    keep, best = [], np.inf
    for _, r in g.iterrows():
        if r.cost < best - 1e-9: keep.append((r.viol, r.cost)); best = r.cost
    return keep
def at(keep, t):
    if t < keep[0][0] - 1e-12: return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1: return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return keep[-1][1]
test = test.assign(cost_adj=test.cost + test.init_hi + test.lag)
fams = ["PRISM", "QuantProv_q90", "QuantProv_q99", "PredHead+hyst", "PredHead", "Static", "Reactive"]
print("\n## Matched compliance, pooled over 20 test weeks: modelled cost vs cost + omitted PC billing (upper bracket)")
for col in ["cost", "cost_adj"]:
    res = {f: [at(envelope(test[test.policy == f], col), t / 100) for t in (1.0, 1.5, 2.0)] for f in fams}
    print(col)
    for f in fams: print(f"   {f:15s} " + "  ".join("   n.r." if np.isnan(x) else f"{x:7,.0f}" for x in res[f]))
    p = np.array(res["PRISM"])
    for f in ["QuantProv_q90", "PredHead+hyst", "Static", "Reactive"]:
        print(f"   PRISM vs {f:14s} " + "  ".join(f"{100*(p[i]/res[f][i]-1):+5.1f}%" for i in range(3)))
