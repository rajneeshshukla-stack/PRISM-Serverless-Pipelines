#!/usr/bin/env python3
"""R3.2 Stages A and B (PLAN.md in docs/revision/hybrid_reproduction_r32_20261124/): the paper's simulator on the first
week of the Azure Functions 2019 trace, fixed keep-alive policies and the hybrid histogram policy (no ARIMA), checked
against the prespecified criteria. Writes aggregates only (no trace rows). EXPLORATORY.

usage (from prism-repro/): venv/Scripts/python -I scripts/revision/hybrid_reproduction.py <dir with
       invocations_per_function_md.anon.d01..d07.csv> <out dir>
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hybrid_policy import fixed_keepalive, hybrid, no_unloading  # noqa: E402

DAYS, MIN_PER_DAY = 7, 1440
H = DAYS * MIN_PER_DAY
FIXED = (5, 10, 20, 30, 45, 60, 90, 120)
RANGES = (60, 120, 180, 240)


def load_apps(src):
    """{(HashOwner, HashApp): (active minutes, counts)} summed over the application's functions, days 1-7."""
    parts = []
    for d in range(1, DAYS + 1):
        df = pd.read_csv(os.path.join(src, f"invocations_per_function_md.anon.d{d:02d}.csv"))
        mcols = [str(i) for i in range(1, MIN_PER_DAY + 1)]
        g = df.groupby(["HashOwner", "HashApp"], sort=False)[mcols].sum()
        arr = g.to_numpy(dtype=np.int64)
        r, m = np.nonzero(arr)
        parts.append(pd.DataFrame({"app": g.index.to_numpy()[r], "minute": m + (d - 1) * MIN_PER_DAY,
                                   "count": arr[r, m]}))
    allp = pd.concat(parts, ignore_index=True).sort_values(["app", "minute"], kind="stable")
    out = {}
    for app, grp in allp.groupby("app", sort=False):
        out[app] = (grp["minute"].to_numpy(), grp["count"].to_numpy())
    return out


def summarise(rows, base_wasted=None):
    pct = np.array([100.0 * r["cold"] / r["invocations"] for r in rows])
    w = float(sum(r["wasted_min"] for r in rows))
    s = {"apps": len(rows), "p75_app_cold_pct": float(np.percentile(pct, 75)),
         "median_app_cold_pct": float(np.percentile(pct, 50)), "always_cold_apps_pct": float(100 * (pct >= 100).mean()),
         "wasted_min_total": w, "invocations": int(sum(r["invocations"] for r in rows)),
         "cold_total": int(sum(r["cold"] for r in rows))}
    if base_wasted:
        s["wasted_vs_fixed10"] = w / base_wasted
    return s


def main(src, out_dir, variant="counts"):
    """variant 'counts' is the prespecified run; 'active_minutes' (POST HOC diagnostic, never a verdict) counts each
    active minute as one invocation."""
    t0 = time.time()
    apps = load_apps(src)
    if variant == "active_minutes":
        apps = {k: (m, np.ones_like(c)) for k, (m, c) in apps.items()}
    elif variant != "counts":
        raise ValueError(variant)
    load_s = time.time() - t0
    res = {}
    res["fixed_10"] = summarise([fixed_keepalive(m, c, 10, H) for m, c in apps.values()])
    base = res["fixed_10"]["wasted_min_total"]
    for k in FIXED:
        res[f"fixed_{k}"] = summarise([fixed_keepalive(m, c, k, H) for m, c in apps.values()], base)
    res["no_unloading"] = summarise([no_unloading(m, c, H) for m, c in apps.values()], base)
    for mode in ("I", "II"):
        for rg in RANGES:
            rows = [hybrid(m, c, H, ka_mode=mode, range_min=rg) for m, c in apps.values()]
            s = summarise(rows, base)
            s["standard_share_mean"] = float(np.mean([r["standard_share"] for r in rows]))
            s["prewarm_share_mean"] = float(np.mean([r["prewarm_share"] for r in rows]))
            res[f"hybrid_{rg}min_{mode}"] = s
    f10, f60, f120 = res["fixed_10"], res["fixed_60"], res["fixed_120"]
    crit = {"A1 fixed 10-min p75 in [47.3, 53.3] (published 50.3)": 47.3 <= f10["p75_app_cold_pct"] <= 53.3,
            "A2 fixed 60-min p75 in [22, 28] (published 25)": 22 <= f60["p75_app_cold_pct"] <= 28,
            "A3 no unloading: always-cold apps in [3.0, 4.0]% (published 3.5)":
                3.0 <= res["no_unloading"]["always_cold_apps_pct"] <= 4.0,
            "A4 fixed 2-h wasted / fixed 10-min in [1.20, 1.35] (published 'almost 30% higher')":
                1.20 <= f120["wasted_vs_fixed10"] <= 1.35}
    for mode in ("I", "II"):
        h = res[f"hybrid_240min_{mode}"]
        crit[f"B1[{mode}] hybrid 4-h wasted / fixed 10-min in [0.90, 1.10]"] = 0.90 <= h["wasted_vs_fixed10"] <= 1.10
        ratio = f10["p75_app_cold_pct"] / h["p75_app_cold_pct"] if h["p75_app_cold_pct"] > 0 else float("inf")
        crit[f"B2[{mode}] p75 ratio fixed 10-min / hybrid 4-h in [2.0, 3.0] (published 2.5x)"] = 2.0 <= ratio <= 3.0
        crit[f"B3[{mode}] fixed 2-h p75 within 5 points of hybrid 4-h, and wasted fixed 2-h / hybrid 4-h in [1.30, 1.70]"] = \
            abs(f120["p75_app_cold_pct"] - h["p75_app_cold_pct"]) <= 5 and \
            1.30 <= f120["wasted_min_total"] / h["wasted_min_total"] <= 1.70
        res[f"derived_{mode}"] = {"p75_ratio_fixed10_over_hybrid4h": ratio,
                                  "wasted_fixed2h_over_hybrid4h": f120["wasted_min_total"] / h["wasted_min_total"],
                                  "p75_fixed2h_minus_hybrid4h": f120["p75_app_cold_pct"] - h["p75_app_cold_pct"],
                                  "B4_always_cold_apps_pct_published_10.5": h["always_cold_apps_pct"]}
    a_ok = all(v for k, v in crit.items() if k.startswith("A"))
    b_ok = {m: all(v for k, v in crit.items() if k.startswith(("B1[" + m, "B2[" + m, "B3[" + m))) for m in ("I", "II")}
    verdict = {"stage_A_pass": a_ok, "stage_B_pass_I": b_ok["I"], "stage_B_pass_II": b_ok["II"],
               "reproduction_pass": a_ok and (b_ok["I"] or b_ok["II"]),
               "interpretation_used": "I" if b_ok["I"] else ("II" if b_ok["II"] else None)}
    out = {"variant": variant if variant == "counts" else variant + " (POST HOC diagnostic; not a verdict)",
           "label": "EXPLORATORY; Azure Functions 2019 trace, days 1-7 (CC-BY, cite Shahrad et al. ATC'20); "
                    "paper's simulator (execution time 0, equal memory); hybrid without ARIMA",
           "apps": len(apps), "load_s": round(load_s, 1), "run_s": round(time.time() - t0, 1),
           "results": res, "criteria": crit, "verdict": verdict}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "reproduction.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    L = [out["label"], f"variant: {out['variant']}", f"applications: {len(apps)}", "",
         f"{'policy':22s} {'p75 app cold %':>15s} {'median %':>9s} {'always cold %':>14s} {'wasted / fixed10':>17s}"]
    for k, s in res.items():
        if k.startswith("derived"):
            continue
        L.append(f"{k:22s} {s['p75_app_cold_pct']:15.2f} {s['median_app_cold_pct']:9.2f} {s['always_cold_apps_pct']:14.2f} "
                 f"{s.get('wasted_vs_fixed10', 1.0):17.3f}")
    L += ["", "criteria (prespecified):"] + [f"  {'PASS' if v else 'FAIL'}  {k}" for k, v in crit.items()]
    L += ["", f"derived: {json.dumps({k: v for k, v in res.items() if k.startswith('derived')})}", f"verdict: {verdict}"]
    with open(os.path.join(out_dir, "reproduction.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "counts")
