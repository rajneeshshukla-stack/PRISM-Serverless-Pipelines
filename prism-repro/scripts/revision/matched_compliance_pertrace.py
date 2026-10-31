"""Added in the pre-submission audit (post hoc). Run pc_billing_bounds.py first. Usage: python matched_compliance_pertrace.py [<repo_root>]
Audit: per-trace matched-compliance costs (same frontier method as the paper, applied per trace over its
four test weeks) to put an uncertainty on the pooled 'within 1.5%' and '13-29%' statements."""
import os, sys
import numpy as np, pandas as pd
from scipy import stats
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = pd.read_csv(os.path.join(ROOT, "results", "tables", "revision", "pc_billing_runs.csv"))  # written by pc_billing_bounds.py
T = D[D.week == "test"]
def envelope(df):
    g = df.groupby("param").agg(cost=("cost", "mean"), viol=("viol", "mean")).reset_index().sort_values(["viol", "cost"])
    keep, best = [], np.inf
    for _, r in g.iterrows():
        if r.cost < best - 1e-9: keep.append((r.viol, r.cost)); best = r.cost
    return keep
def at(keep, t):
    if t < keep[0][0] - 1e-12: return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1: return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return np.nan  # beyond the frontier's highest violation rate: not interpolable
fams = ["PRISM", "QuantProv_q90", "PredHead+hyst", "Static", "Reactive"]
for t in (1.0, 1.5, 2.0):
    C = {f: [at(envelope(T[(T.policy == f) & (T.seed == s)]), t/100) for s in sorted(T.seed.unique())] for f in fams}
    print(f"target {t}%: per-trace interpolated cost")
    for f in fams: print(f"   {f:14s}", ["n.r." if np.isnan(x) else round(x) for x in C[f]])
    p = np.array(C["PRISM"], float)
    for f in fams[1:]:
        q = np.array(C[f], float); ok = ~np.isnan(p) & ~np.isnan(q)
        d = 100 * (p[ok] / q[ok] - 1)
        hw = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
        print(f"   PRISM vs {f:13s} {d.mean():+6.1f} ± {hw:4.1f}%  (n={ok.sum()}; per trace {np.round(d,1).tolist()})")
