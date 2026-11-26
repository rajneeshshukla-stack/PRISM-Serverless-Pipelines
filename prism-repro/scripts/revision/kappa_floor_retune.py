#!/usr/bin/env python3
"""Cold-hit floor: does PRISM keep its compliance when epsilon is RETUNED at a lower floor? (R2.12)

The earlier fixed-epsilon diagnostic lowered the kappa floor from 0.1 to 0.001 at the validation-
selected epsilon and found lower cost but more violating windows. That is not a fair comparison,
because epsilon was selected with the floor at 0.1. Here both arms are tuned by the paper's rule:

  arms        floor 0.1 (submitted, kappa_clip = (0.1, 1.0)) and floor 0.001 (kappa_clip = (0.001, 1.0))
  traces      seeds 101-105, all four test scenarios, GBM forecaster, current code and defaults
  validation  every epsilon in GRIDS["PRISM"] on the validation week; select_by_rule (Section V-C)
  test        (a) VALIDATION-SELECTED epsilon per arm: held-out test weeks, the primary comparison
              (b) every epsilon on every test week: frontier for a POST HOC matched-compliance
                  comparison (cost interpolated at equal violating-window rate, as in the paper)

Fast simulator, pre-calibration constants: exploratory evidence, to be rerun at the regeneration.
Usage: python kappa_floor_retune.py <code_root> <out_dir> [seed ...]      (writes rows_<seed>.jsonl)
       python kappa_floor_retune.py <code_root> <out_dir> --analyse        (reads them, prints summary)
"""
import glob
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import GRIDS, TraceBundle, make_policy, select_by_rule  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS  # noqa: E402

ARMS = {"floor0.1": (0.1, 1.0), "floor0.001": (0.001, 1.0)}
SEEDS = (101, 102, 103, 104, 105)
KEYS = ("cost", "violating_window_rate", "record_attainment", "kappa_mean", "slo_met")


def _run(b, sc, wk, eps, clip):
    r = simulate(b.context(sc, wk), make_policy({"family": "PRISM", "param": eps, "prism": {"kappa_clip": clip}}))
    s = r["summary"] if "summary" in r else r
    return {k: (float(s[k]) if k != "slo_met" else bool(s[k])) for k in KEYS if k in s}


def run_seed(seed, out_dir):
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig())
    rows = []
    for arm, clip in ARMS.items():
        for eps in GRIDS["PRISM"]:
            rows.append(dict(seed=seed, arm=arm, week="val", scenario="validation", eps=eps,
                             **_run(b, MAIN_SCENARIOS[0], "val", eps, clip)))
        for sc in MAIN_SCENARIOS:
            for eps in GRIDS["PRISM"]:
                rows.append(dict(seed=seed, arm=arm, week="test", scenario=sc, eps=eps,
                                 **_run(b, sc, "test", eps, clip)))
    with open(os.path.join(out_dir, f"rows_{seed}.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return seed, len(rows), round(time.time() - t0, 1)


def envelope(pts):
    """Lower-left cost/violation frontier over epsilon (same construction as the paper)."""
    keep, best = [], np.inf
    for v, c in sorted(pts):
        if c < best - 1e-9:
            keep.append((v, c)); best = c
    return keep


def cost_at(keep, t):
    if not keep or t < keep[0][0] - 1e-12:
        return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1:
            return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return keep[-1][1] if abs(t - keep[-1][0]) < 1e-12 else np.nan


def analyse(out_dir):
    rows = [json.loads(l) for p in sorted(glob.glob(os.path.join(out_dir, "rows_*.jsonl"))) for l in open(p)]
    seeds = sorted({r["seed"] for r in rows})
    print(f"rows: {len(rows)}; seeds: {seeds}")
    sel = {}
    print("\n(a) VALIDATION-SELECTED epsilon, held-out test weeks (primary comparison)")
    for arm in ARMS:
        for s in seeds:
            v = [dict(r, spec={"param": r["eps"]}) for r in rows if r["seed"] == s and r["arm"] == arm and r["week"] == "val"]
            sel[arm, s] = select_by_rule(v)["eps"]
    print("   selected eps:", {arm: [sel[arm, s] for s in seeds] for arm in ARMS})
    for sc in MAIN_SCENARIOS:
        line = []
        for arm in ARMS:
            t = [r for r in rows if r["week"] == "test" and r["scenario"] == sc and r["arm"] == arm
                 and r["eps"] == sel[arm, r["seed"]]]
            c = np.mean([r["cost"] for r in t]); v = 100 * np.mean([r["violating_window_rate"] for r in t])
            met = sum(r["violating_window_rate"] <= 0.02 + 1e-12 for r in t)
            km = np.mean([r.get("kappa_mean", np.nan) for r in t])
            line.append(f"{arm}: cost {c:7.1f} viol {v:5.2f}% met {met}/{len(t)} kappa {km:.3f}")
        print(f"   {sc:10s} " + " | ".join(line))
    tot = {arm: [r for r in rows if r["week"] == "test" and r["arm"] == arm and r["eps"] == sel[arm, r["seed"]]]
           for arm in ARMS}
    for arm, t in tot.items():
        print(f"   ALL {arm}: mean cost {np.mean([r['cost'] for r in t]):.1f}, mean viol "
              f"{100*np.mean([r['violating_window_rate'] for r in t]):.2f}%, met "
              f"{sum(r['violating_window_rate'] <= 0.02 + 1e-12 for r in t)}/{len(t)}")
    d = [100 * (a["cost"] / b["cost"] - 1) for a, b in zip(
        sorted(tot["floor0.001"], key=lambda r: (r["seed"], r["scenario"])),
        sorted(tot["floor0.1"], key=lambda r: (r["seed"], r["scenario"])))]
    print(f"   paired cost change floor0.001 vs floor0.1: mean {np.mean(d):+.2f}% "
          f"[{min(d):+.2f}, {max(d):+.2f}] over {len(d)} trace-scenario weeks")
    print("\n(b) POST HOC matched compliance (frontier over epsilon on test weeks, per trace, pooled over scenarios)")
    for target in (0.01, 0.015, 0.02):
        res = {}
        for arm in ARMS:
            res[arm] = []
            for s in seeds:
                pts = {}
                for r in rows:
                    if r["seed"] == s and r["arm"] == arm and r["week"] == "test":
                        pts.setdefault(r["eps"], []).append((r["violating_window_rate"], r["cost"]))
                frontier = envelope([(np.mean([p[0] for p in v]), np.mean([p[1] for p in v])) for v in pts.values()])
                res[arm].append(cost_at(frontier, target))
        a, b = np.array(res["floor0.001"]), np.array(res["floor0.1"])
        ok = ~np.isnan(a) & ~np.isnan(b)
        dd = 100 * (a[ok] / b[ok] - 1)
        print(f"   at {100*target:.1f}% violating windows: floor0.001 vs floor0.1 cost "
              f"{'n.r.' if not ok.any() else f'{dd.mean():+.2f}% (per trace {np.round(dd, 2).tolist()})'}; "
              f"interpolable traces {int(ok.sum())}/{len(seeds)}")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        seeds = [int(x) for x in sys.argv[3:]] or list(SEEDS)
        with ProcessPoolExecutor(max_workers=min(len(seeds), 5)) as ex:
            for res in ex.map(run_seed, seeds, [out] * len(seeds)):
                print("seed %d: %d rows in %ss" % res, flush=True)
        analyse(out)
