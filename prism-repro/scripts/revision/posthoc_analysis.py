#!/usr/bin/env python3
"""POST-HOC analyses of EXISTING results in prism-repro.zip (no new simulations).
Not pre-registered: exploratory, reported as such. Usage: python posthoc_analysis.py <repo_root>"""
import json, os, sys
import numpy as np, pandas as pd
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/v/prism-repro"
sys.path.insert(0, ROOT + "/src")
from prism_repro.experiment import select_by_rule
def rows(e):
    df = pd.DataFrame([json.loads(l) for l in open(f"{ROOT}/results/raw/{e}/rows.jsonl")])
    return df.drop_duplicates("run_id", keep="last")
e1 = rows("E1"); val = e1[e1.week == "val"]; test = e1[e1.week == "test"]
SC = ["stationary", "growth", "bursty", "new_spike"]
V = ["Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]
SEL = {(s, v): select_by_rule(g.to_dict("records")) for (s, v), g in val.groupby(["seed", "policy"])}
seeds = sorted(e1.seed.unique())
out = {}
print("## A. Selected parameter per trace (validation rule)")
print("| trace | " + " | ".join(V) + " |\n|" + "---|" * (len(V) + 1))
for s in seeds:
    print(f"| {s} | " + " | ".join(str(SEL[(s, v)]["param"]) for v in V) + " |")
print("\n## B. Per-trace test results of the selected configuration: cost USD / violating windows %")
for v in ["PredHead", "PredHead+hyst", "PRISM", "QuantProv_q90", "QuantProv_q99", "Reactive", "Static"]:
    print(f"\n### {v}\n| trace | " + " | ".join(SC) + " |\n|---|---|---|---|---|")
    for s in seeds:
        c = []
        for sc in SC:
            r = test[(test.seed == s) & (test.scenario == sc) & (test.label == SEL[(s, v)]["label"])].iloc[0]
            c.append(f"{r.cost:,.0f} / {r.violating_window_rate*100:.2f}")
        print(f"| {s} | " + " | ".join(c) + " |")
print("\n## C. Dependence on the fixed parameter: share of the 20 test weeks meeting 2 % | mean cost | mean viol % (test-week knowledge; diagnostic)")
for v in ["PRISM", "Reactive", "Static", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99"]:
    g = test[test.policy == v].groupby("param").agg(slo=("slo_met", "mean"), cost=("cost", "mean"), viol=("violating_window_rate", "mean"), n=("cost", "size"))
    print(f"\n### {v}\n" + "; ".join(f"{p}: {r.slo*100:.0f}% | {r.cost:,.0f} | {r.viol*100:.2f}" for p, r in g.iterrows()))
def envelope(df):
    g = df.groupby("param").agg(cost=("cost", "mean"), viol=("violating_window_rate", "mean")).reset_index().sort_values(["viol", "cost"])
    keep, best = [], np.inf
    for _, r in g.iterrows():
        if r.cost < best - 1e-9: keep.append((r.viol, r.cost)); best = r.cost
    return keep
def cost_at(keep, t):
    if t < keep[0][0] - 1e-12: return None
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1: return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return keep[-1][1]
print("\n## D. Matched-compliance comparison: interpolated mean weekly cost (USD) on the Pareto frontier of each family's grid at a target violating-window rate (post hoc, test weeks)")
fam = ["PRISM", "QuantProv_q90", "QuantProv_q99", "PredHead", "PredHead+hyst", "Reactive", "Static", "Scheduled"]
for label, sel in [("pooled over 20 test weeks", test)] + [(sc, test[test.scenario == sc]) for sc in SC]:
    print(f"\n### {label}\n| family | min viol reachable % | cost @1.0% | cost @1.5% | cost @2.0% |\n|---|---|---|---|---|")
    for f in fam:
        k = envelope(sel[sel.policy == f]); cs = []
        for t in (0.010, 0.015, 0.020):
            c = cost_at(k, t); cs.append("not reachable" if c is None else f"{c:,.0f}")
        print(f"| {f} | {k[0][0]*100:.2f} | " + " | ".join(cs) + " |")
print("\n## E. kappa over time (PRISM at the validation-selected eps)")
ks, shares, byday = [], [], []
for s in seeds:
    A = np.load(f"{ROOT}/results/raw/E1/arrays_seed{s}.npz")
    for sc in SC:
        r = test[(test.seed == s) & (test.scenario == sc) & (test.label == SEL[(s, "PRISM")]["label"])].iloc[0]
        k = A[r.run_id + "::kappa_epoch"].astype(float); ks.append(k.mean()); shares.append(np.mean(k < 0.105))
        byday.append(k.reshape(7, -1).mean(1))
byday = np.array(byday)
print(f"mean kappa per test week: min {min(ks):.3f} max {max(ks):.3f} mean {np.mean(ks):.3f}; share of epochs with kappa < 0.105: mean {np.mean(shares)*100:.1f}% (range {min(shares)*100:.1f}-{max(shares)*100:.1f}%)")
print("mean kappa by test day (mean over 20 weeks): " + ", ".join(f"{x:.3f}" for x in byday.mean(0)))
print("\n## F. Memory sizes chosen by PRISM: share of epochs by size (mean over 5 traces)")
mems = [512, 1024, 2048, 3008]
print("### E1 validation-selected PRISM, test weeks\n| scenario | " + " | ".join(f"{m} MB" for m in mems) + " | max over weeks of share >=2048 MB |\n|---|---|---|---|---|---|")
for sc in SC:
    sh, mx = [], []
    for s in seeds:
        A = np.load(f"{ROOT}/results/raw/E1/arrays_seed{s}.npz")
        r = test[(test.seed == s) & (test.scenario == sc) & (test.label == SEL[(s, "PRISM")]["label"])].iloc[0]
        m = A[r.run_id + "::mem_epoch"]; sh.append([np.mean(m == x) for x in mems]); mx.append(np.mean(m >= 2048))
    print(f"| {sc} | " + " | ".join(f"{x*100:.1f}%" for x in np.mean(sh, 0)) + f" | {max(mx)*100:.1f}% |")
e6 = rows("E6")
print("\n### E6 caps (eps = 0.02)\n| scenario | cap | " + " | ".join(f"{m} MB" for m in mems) + " |\n|---|---|---|---|---|---|")
for sc in ["stationary", "new_spike"]:
    for tag in ["capNone", "cap250", "cap60", "cap40"]:
        sh = []
        for s in seeds:
            A = np.load(f"{ROOT}/results/raw/E6/arrays_seed{s}.npz")
            r = e6[(e6.seed == s) & (e6.scenario == sc) & (e6.tag == tag)].iloc[0]
            m = A[r.run_id + "::mem_epoch"]; sh.append([np.mean(m == x) for x in mems])
        print(f"| {sc} | {tag[3:]} | " + " | ".join(f"{x*100:.1f}%" for x in np.mean(sh, 0)) + " |")
