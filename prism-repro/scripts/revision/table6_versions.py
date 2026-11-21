#!/usr/bin/env python3
"""Table VI (paired PRISM-minus-comparator differences) under one scikit-learn version (R5.M6, R2.17, R2.16).

Reviewer 5 asks for "the Table VI differences under both library versions". Run this script once in each
environment (same machine, same code, packages identical except scikit-learn) and compare the two outputs with
--compare. Method as scripts/analyze.py: per trace (seeds 101-105) every family is tuned on the validation week by
experiment.select_by_rule over its grid in experiment.GRIDS, then run in the four held-out test weeks at the
selected setting; Table VI pairs PRISM with each comparator by trace, per scenario: mean cost difference (USD and %)
and violating-window difference (points) with 95% t half-widths over traces, and the counts of traces in which
PRISM is cheaper / has fewer violating windows. Current code (corrected build), fast simulator; not the stored E1.

Usage: python table6_versions.py <code_root> <out.json>                 (one environment)
       python table6_versions.py <code_root> --compare <a.json> <b.json> (side by side, with differences)
"""
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.join(ROOT, "src"))

SEEDS = (101, 102, 103, 104, 105)
SCEN = ("stationary", "growth", "bursty", "new_spike")
FAMS = {"PRISM": ("PRISM", {}), "PredHead": ("PredHead", {}), "PredHead+hyst": ("PredHead", {"hyst": True}),
        "QuantProv_q90": ("QuantProv", {"tau_idx": 2})}
COMPARATORS = ("PredHead", "PredHead+hyst", "QuantProv_q90")


def seed_job(seed):
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import GRIDS, TraceBundle, make_policy, select_by_rule
    from prism_repro.simulator import simulate
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig())
    out = {}
    for fam, (base, extra) in FAMS.items():
        val = []
        for p in GRIDS[base]:
            s = simulate(b.context("stationary", "val"), make_policy(dict(family=base, param=p, **extra)))["summary"]
            val.append(dict(param=p, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"])))
        sel = select_by_rule(val)
        tests = {}
        for sc in SCEN:
            s = simulate(b.context(sc, "test"), make_policy(dict(family=base, param=sel["param"], **extra)))["summary"]
            tests[sc] = dict(cost=float(s["cost"]), viol=float(s["violating_window_rate"]))
        out[fam] = dict(selected=sel["param"], val_viol=sel["violating_window_rate"], test=tests)
    return seed, out, round(time.time() - t0, 1)


def tci(x):
    from scipy import stats
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return float(x.mean()) if n else float("nan"), float("nan")
    return float(x.mean()), float(stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n))


def table6(per_seed):
    rows = []
    for comp in COMPARATORS:
        for sc in SCEN:
            a = [per_seed[s]["PRISM"]["test"][sc] for s in SEEDS]
            b = [per_seed[s][comp]["test"][sc] for s in SEEDS]
            dc = np.array([x["cost"] - y["cost"] for x, y in zip(a, b)])
            dp = 100 * dc / np.array([y["cost"] for y in b])
            dv = 100 * np.array([x["viol"] - y["viol"] for x, y in zip(a, b)])
            rows.append(dict(comparator=comp, scenario=sc, cost_diff_usd=tci(dc), cost_diff_pct=tci(dp),
                             viol_diff_pp=tci(dv), prism_cheaper=int((dc < 0).sum()), prism_fewer_viol=int((dv < 0).sum())))
    return rows


def run(out_path):
    per = {}
    with ProcessPoolExecutor(max_workers=5) as ex:
        for seed, out, t in ex.map(seed_job, SEEDS):
            per[seed] = out
            print(f"seed {seed}: {t}s; selected " + ", ".join(f"{f}={out[f]['selected']}" for f in FAMS), flush=True)
    import sklearn, scipy, pandas
    env = dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__,
               pandas=pandas.__version__, sklearn=sklearn.__version__)
    res = dict(environment=env, per_seed={str(k): v for k, v in per.items()}, table6=table6(per))
    json.dump(res, open(out_path, "w", encoding="utf-8"), indent=1)
    print(json.dumps(env))


def fmt(m, h, d):
    return f"{m:+.{d}f} ± {h:.{d}f}" if np.isfinite(h) else f"{m:+.{d}f}"


def compare(pa, pb):
    A, B = (json.load(open(p, encoding="utf-8")) for p in (pa, pb))
    ea, eb = A["environment"], B["environment"]
    print(f"A: scikit-learn {ea['sklearn']} | B: scikit-learn {eb['sklearn']} | {ea['platform']}, Python {ea['python']}, "
          f"numpy {ea['numpy']}, scipy {ea['scipy']}, pandas {ea['pandas']}")
    same_env = all(ea[k] == eb[k] for k in ("platform", "python", "numpy", "scipy", "pandas"))
    print("only scikit-learn differs:", same_env)
    print("\nValidation selections (A -> B):")
    changed = 0
    for s in map(str, SEEDS):
        parts = []
        for f in FAMS:
            x, y = A["per_seed"][s][f]["selected"], B["per_seed"][s][f]["selected"]
            changed += x != y
            parts.append(f"{f} {x}" + ("" if x == y else f" -> {y}"))
        print(f"  {s}: " + "; ".join(parts))
    print(f"  selections that change: {changed} of {len(SEEDS) * len(FAMS)}")
    dv = [abs(A["per_seed"][s][f]["test"][sc]["viol"] - B["per_seed"][s][f]["test"][sc]["viol"]) * 100
          for s in map(str, SEEDS) for f in FAMS for sc in SCEN]
    dc = [abs(A["per_seed"][s][f]["test"][sc]["cost"] / B["per_seed"][s][f]["test"][sc]["cost"] - 1) * 100
          for s in map(str, SEEDS) for f in FAMS for sc in SCEN]
    print(f"  single-run test weeks: max |violating-window change| {max(dv):.2f} points, max |cost change| {max(dc):.2f}%")
    print("\nTable VI, PRISM minus comparator (mean ± 95% half-width over 5 traces): A | B | B - A")
    for ra, rb in zip(A["table6"], B["table6"]):
        assert (ra["comparator"], ra["scenario"]) == (rb["comparator"], rb["scenario"])
        print(f"  vs {ra['comparator']:13s} {ra['scenario']:10s} cost% {fmt(*ra['cost_diff_pct'], 1):>12s} | {fmt(*rb['cost_diff_pct'], 1):>12s} | "
              f"{rb['cost_diff_pct'][0] - ra['cost_diff_pct'][0]:+.1f}   viol pp {fmt(*ra['viol_diff_pp'], 2):>13s} | "
              f"{fmt(*rb['viol_diff_pp'], 2):>13s} | {rb['viol_diff_pp'][0] - ra['viol_diff_pp'][0]:+.2f}   cheaper "
              f"{ra['prism_cheaper']}/{rb['prism_cheaper']}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--compare":
        compare(sys.argv[3], sys.argv[4])
    else:
        run(sys.argv[2])
