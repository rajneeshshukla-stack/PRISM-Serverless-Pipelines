#!/usr/bin/env python3
"""R2.14(a): effect of the verified 1 ms billing rule on the C1-C3 cost comparisons (no simulation).

The simulator bills continuous mean durations (src/prism_repro/simulator.py, Eqs. (8)-(9)); AWS bills each invocation's
duration rounded up to whole ms (billing_rules.billed_ms). For continuous durations the increment averages 0.5 ms
(at most 1 ms) per invocation. Per test week: invocations = n_requests x 4 stages (C1-C3 week records); memory = 1024 MB
for the share of minutes below 2048 MB and up to 3008 MB for share_mem_ge_2048 (bound); rate = the on-demand price
(upper bound; PC-served invocations pay the lower provisioned-duration price). The adjusted cost is cost + increment;
the paired comparison is recomputed exactly as closed_loop_confirmatory.analyse: per trace, the four-scenario (C1/C2) or
one-scenario (C3) mean cost, PRISM / comparator - 1, then the mean and 95% t interval over the 25 traces.
Labels: PRE-CALIBRATION, Windows, prespecified comparisons; the adjustment is EXPLORATORY.

usage: python rounding_effect_c1c3.py <confirmatory run dir> <out.json>
"""
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

RUN, OUT = sys.argv[1], sys.argv[2]
OD, PCD, STAGES = 1.66667e-5, 9.7222e-6, 4
cases = {"mid": (0.0005, OD, 2.0), "upper": (0.001, OD, 3008 / 1024), "lower_rate": (0.0005, PCD, 2.0)}
G = defaultdict(dict)
for p in glob.glob(os.path.join(RUN, "groups", "*", "*.json")):
    g = json.load(open(p, encoding="utf-8"))
    G[(g["set"], g["seed"])][g["family"]] = g["tests"]


def week_cost(t, case):
    if case is None:
        return t["cost"]
    inc_s, rate, g_hi = cases[case]
    s = t["share_mem_ge_2048"]
    gb = (1 - s) * 1.0 + s * g_hi
    return t["cost"] + t["n_requests"] * STAGES * inc_s * gb * rate


def tint(d):
    d = np.asarray(d, float)
    return float(d.mean()), float(stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)))


out = {"cases": {k: dict(increment_ms=v[0] * 1000, rate_usd_per_gbs=v[1], memory_ge2048_gb=v[2]) for k, v in cases.items()}}
for comp, st, a, b in (("C1", "C1C2", "PRISM", "QuantProv_q90"), ("C2", "C1C2", "PRISM", "Reactive"),
                       ("C3", "C3", "PRISM", "MemAdapt_q90")):
    res = {}
    for case in (None, "mid", "upper", "lower_rate"):
        d, rel = [], []
        for (s_, seed), fam in sorted(G.items()):
            if s_ != st:
                continue
            ca = np.mean([week_cost(t, case) for t in fam[a]])
            cb = np.mean([week_cost(t, case) for t in fam[b]])
            d.append(100 * (ca / cb - 1))
            if case:
                rel += [100 * (week_cost(t, case) / t["cost"] - 1) for f in (a, b) for t in fam[f]]
        m, h = tint(d)
        res[case or "as_run"] = dict(mean=m, lower=m - h, upper=m + h, n=len(d),
                                     cost_change_pct_range=[min(rel), max(rel)] if rel else None)
    base = res["as_run"]["mean"]
    for k in ("mid", "upper", "lower_rate"):
        res[k]["shift_points"] = res[k]["mean"] - base
    out[comp] = res
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
for comp in ("C1", "C2", "C3"):
    r = out[comp]
    print(f"{comp}: as run {r['as_run']['mean']:+.4f} [{r['as_run']['lower']:+.4f}, {r['as_run']['upper']:+.4f}]; "
          f"mid {r['mid']['mean']:+.4f} (shift {r['mid']['shift_points']:+.5f} pt); upper {r['upper']['mean']:+.4f} "
          f"(shift {r['upper']['shift_points']:+.5f} pt); per-week cost change {r['upper']['cost_change_pct_range'][0]:.4f}"
          f"-{r['upper']['cost_change_pct_range'][1]:.4f}% (upper)")
