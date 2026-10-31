#!/usr/bin/env python3
"""Analysis of R1 (real-trace replay). Writes results/tables/R1_real_traces.md and .json."""
import json, os, sys
import numpy as np
from scipy import stats
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import select_by_rule  # noqa: E402

rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "R1", "rows.jsonl"))]
runs = [r for r in rows if r.get("kind") != "forecast" and r["status"] == "ok"]
fq = [r for r in rows if r.get("kind") == "forecast"]
seeds = sorted(set(r["seed"] for r in runs))
FAM = ["OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]
NAME = {"PredHead+hyst": "PredHead+S", "QuantProv_q90": "QuantProv-q90", "QuantProv_q99": "QuantProv-q99", "OnDemand": "On-demand"}
sel = {}
for s in seeds:
    for f in FAM:
        val = [r for r in runs if r["seed"] == s and r["week"] == "val" and r["policy"] == f]
        pick = select_by_rule(val)
        test = [r for r in runs if r["seed"] == s and r["week"] == "test" and r["spec"] == pick["spec"]]
        assert len(test) == 1, (s, f)
        sel[(s, f)] = dict(param=pick.get("param"), val_vw=pick["violating_window_rate"], val_cost=pick["cost"],
                           cost=test[0]["cost"], vw=test[0]["violating_window_rate"],
                           util=test[0]["billing_utilisation"], att=test[0]["record_attainment"])


def ci(x):
    x = np.asarray(x, float); n = len(x)
    h = stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    return float(x.mean()), float(h)


out = {"seeds": seeds, "traces": {r["seed"]: r["trace"] for r in runs}, "families": {}, "paired": {}, "forecast": fq}
lines = ["| Family | Selected parameter (per trace) | Cost (USD) | Violating windows (%) | Traces meeting 2% | Billing util. |", "|---|---|---|---|---|---|"]
for f in FAM:
    c = [sel[(s, f)]["cost"] for s in seeds]; v = [100 * sel[(s, f)]["vw"] for s in seeds]
    met = sum(sel[(s, f)]["vw"] <= 0.02 + 1e-12 for s in seeds)
    u = [sel[(s, f)]["util"] for s in seeds]
    ps = ", ".join(str(sel[(s, f)]["param"]) for s in seeds)
    mc, hc = ci(c); mv, hv = ci(v)
    out["families"][f] = dict(cost=c, vw=v, met=met, params=[sel[(s, f)]["param"] for s in seeds], util=u,
                              per_trace=[sel[(s, f)] for s in seeds])
    lines.append(f"| {NAME.get(f, f)} | {ps} | {mc:,.0f} ± {hc:,.0f} | {mv:.2f} ± {hv:.2f} | {met}/5 | {np.mean(u):.2f} |")
lines += ["", "Paired PRISM minus comparator (mean ± 95% half-width over traces; cost % per trace; vw in points; counts = traces PRISM cheaper / fewer violating windows)", "",
          "| Comparator | Cost (%) | Violating windows (pp) |", "|---|---|---|"]
for f in ["PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "Static", "Scheduled", "Reactive", "OnDemand"]:
    dc = [100 * (sel[(s, "PRISM")]["cost"] / sel[(s, f)]["cost"] - 1) for s in seeds]
    dv = [100 * (sel[(s, "PRISM")]["vw"] - sel[(s, f)]["vw"]) for s in seeds]
    nc = sum(d < 0 for d in dc); nv = sum(d < 0 for d in dv)
    (mc, hc), (mv, hv) = ci(dc), ci(dv)
    out["paired"][f] = dict(cost_pct=dc, vw_pp=dv, cheaper=nc, fewer=nv)
    lines.append(f"| {NAME.get(f, f)} | {mc:+.1f} ± {hc:.1f} ({nc}) | {mv:+.2f} ± {hv:.2f} ({nv}) |")
lines += ["", "Forecast quality on the test week (per trace):", "", "| Trace | MAPE median (%) | cov90 raw | cov99 raw | cov90 cal | cov99 cal |", "|---|---|---|---|---|---|"]
for r in sorted(fq, key=lambda r: r["seed"]):
    lines.append(f"| {r['trace']} | {r['mape_median']:.1f} | {r['cov90_raw']:.3f} | {r['cov99_raw']:.3f} | {r['cov90_cal']:.3f} | {r['cov99_cal']:.3f} |")
lines += ["", "Per trace, selected configuration on the test week (cost USD / violating windows %):", "",
          "| Family | " + " | ".join(out["traces"][s] for s in seeds) + " |", "|---" * (len(seeds) + 1) + "|"]
for f in FAM:
    lines.append(f"| {NAME.get(f, f)} | " + " | ".join(f"{sel[(s, f)]['cost']:,.0f} / {100*sel[(s, f)]['vw']:.2f}" for s in seeds) + " |")
os.makedirs(os.path.join(ROOT, "results", "tables"), exist_ok=True)
open(os.path.join(ROOT, "results", "tables", "R1_real_traces.md"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(ROOT, "results", "tables", "R1_real_traces.json"), "w"), indent=1, default=str)
print("\n".join(lines))
