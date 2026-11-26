#!/usr/bin/env python3
"""Memory-adaptive calibrated-quantile baseline against PRISM in the memory regimes of Table IX (R2.6, R3.7, R7.4).

PRE-CALIBRATION, EXPLORATORY: fast simulator, assumed constants, current code.
Reviewers 2, 3 and 7 ask whether PRISM's joint online memory sizing adds anything beyond a simple
memory-selection rule; the stored post hoc comparison (results/tables/revision/E4b_fixed_memory_summary.json)
found headroom at a fixed 2048 MB 14-29% cheaper than PRISM's best setting in the short-slack regimes, with the
fixed size chosen offline and the setting with test-week knowledge.

Families, each tuned by the common validation rule (cheapest with validation violating-window rate <= 2%):
  PRISM              joint capacity and memory (paper's eps grid)
  MemAdapt_q90       policies.MemAdapt: memory = smallest size with warm miss probability v_w(m) <= 0.005 (latency
                     model, fixed in advance), capacity = QuantProv-q90 at that size (paper's QuantProv grid)
  QuantProv_q90@1024 the calibrated-quantile rule at the default memory (memory-blind)
  QuantProv_q90@2048 the same rule at 2048 MB chosen once, offline
  PredHead@2048      the fixed-2048 MB headroom rule of the stored comparison (Table S14), no scale-in rule
  MemAdapt sensitivity to tau_w (0.002, 0.01): reported as the memory chosen; run only where it changes the size.

Regimes: those of E4 / Table IX, (non-scaling fraction, deadline s) = (0.5, 14.5), (0.5, 13), (0.5, 12), (0.5, 11),
(0.15, 14.5), (0.15, 12). Traces: seeds 101-105 (E4 used two), stationary validation week for tuning, stationary
test week for evaluation, as E4. Fixed-memory runs set default_mem as scripts/revision/r2_quantprov_memory.py does.

Reported per regime: memory chosen (MemAdapt) and used (PRISM: share of minutes at >= 2048 MB, memory changes per
week); validation-selected test outcomes; POST HOC matched compliance (per trace, frontier over the parameter,
interpolated at equal violating-window rate) relative to MemAdapt_q90; and, for comparison with the stored analysis,
POST HOC the cheapest setting meeting the 2% target on the test week (test-week knowledge, as E4b).

Usage: python memadapt_compare.py <code_root> <out_dir> [--workers=N]  |  ... <out_dir> --analyse
"""
import dataclasses
import glob
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
REGIMES = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
TAU_W, TAU_W_SENS = 0.005, (0.002, 0.01)
TARGETS = (0.01, 0.015, 0.02)
REF = "MemAdapt_q90"


def _families(cfg):
    from prism_repro.experiment import GRIDS
    from prism_repro.latency import miss_table
    vw = miss_table(cfg)

    def chosen(tw):
        ok = [m for m in sorted(cfg.mem_options) if vw[m][0] <= tw]
        return ok[0] if ok else max(cfg.mem_options)
    fams = {"PRISM": (dict(family="PRISM"), GRIDS["PRISM"], None),
            REF: (dict(family="MemAdapt", tau_idx=2, tau_w=TAU_W), GRIDS["QuantProv"], None)}
    for tw in TAU_W_SENS:
        if chosen(tw) != chosen(TAU_W):
            fams[f"MemAdapt_q90[tw{tw:g}]"] = (dict(family="MemAdapt", tau_idx=2, tau_w=tw), GRIDS["QuantProv"], None)
    fams["QuantProv_q90@1024"] = (dict(family="QuantProv", tau_idx=2), GRIDS["QuantProv"], 1024)
    fams["QuantProv_q90@2048"] = (dict(family="QuantProv", tau_idx=2), GRIDS["QuantProv"], 2048)
    fams["PredHead@2048"] = (dict(family="PredHead"), GRIDS["PredHead"], 2048)
    return fams, {tw: chosen(tw) for tw in (TAU_W,) + TAU_W_SENS}, {m: float(vw[m][0]) for m in cfg.mem_options}


def job(task):
    seed, ns = task
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, make_policy, select_by_rule
    from prism_repro.simulator import simulate
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig().with_(nonscaling=ns), scenarios=("stationary",))
    rows = []
    for ns_, D in [r for r in REGIMES if r[0] == ns]:
        base = b.cfg.with_(deadline=D)
        fams, mem_choice, vw = _families(base)
        for fam, (spec, grid, mem) in fams.items():
            cfg = base if mem is None else base.with_(default_mem=mem)
            val = []

            def one(week, p):
                ctx = dataclasses.replace(b.context("stationary", week), cfg=cfg, _Kweek={})
                pol = make_policy(dict(spec, param=p))
                res = simulate(ctx, pol)
                s, me = res["summary"], res["raw"]["mem_epoch"]
                return dict(seed=seed, nonscaling=ns, deadline=D, family=fam, week=week, param=p,
                            cost=float(s["cost"]), viol=float(s["violating_window_rate"]),
                            share_ge2048=float(s["share_mem_ge_2048"]), mem_changes=int(np.sum(me[1:] != me[:-1])),
                            mems_used=sorted({int(x) for x in np.unique(me)}),
                            mem_log=[list(x) for x in getattr(pol, "mem_log", [])],
                            mean_provisioned=float(s["mean_provisioned"]),
                            mem_choice=mem_choice if fam.startswith("MemAdapt") else None,
                            vw=vw if fam == REF else None)
            for p in grid:
                r = one("val", p)
                rows.append(r)
                val.append(dict(param=p, cost=r["cost"], violating_window_rate=r["viol"]))
            sel = select_by_rule(val)["param"]
            for p in grid:
                r = one("test", p)
                r["selected"] = bool(p == sel)
                rows.append(r)
    return rows, round(time.time() - t0, 1)


def run(out_dir, workers):
    tasks = [(s, ns) for ns in (0.5, 0.15) for s in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows, t in ex.map(job, tasks):
            r0 = rows[0]
            with open(os.path.join(out_dir, f"rows_{r0['seed']}_ns{r0['nonscaling']}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            print(f"seed {r0['seed']} ns {r0['nonscaling']}: {len(rows)} rows in {t}s", flush=True)
    import scipy
    import sklearn
    json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                   scipy=scipy.__version__, sklearn=sklearn.__version__),
              open(os.path.join(out_dir, "environment.json"), "w"), indent=1)


def envelope(pts):
    keep, best = [], np.inf
    for v, c in sorted(pts):
        if c < best - 1e-9:
            keep.append((v, c))
            best = c
    return keep


def cost_at(keep, t):
    if not keep or t < keep[0][0] - 1e-12:
        return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1:
            return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return keep[-1][1] if t >= keep[-1][0] - 1e-12 else np.nan


def analyse(out_dir):
    rows = [json.loads(line) for p in sorted(glob.glob(os.path.join(out_dir, "rows_*.jsonl"))) for line in open(p)]
    envp = os.path.join(out_dir, "environment.json")
    env = json.load(open(envp)) if os.path.exists(envp) else {}
    print("PRE-CALIBRATION, EXPLORATORY. Fast simulator, assumed constants, current code. "
          f"Environment: {env}.\nSeeds 101-105, stationary validation week (tuning) and stationary test week "
          "(evaluation) per trace, as E4. Violating windows pooled over the week (672 windows; 2% = 13 allowed).")
    for ns, D in REGIMES:
        R = [r for r in rows if r["nonscaling"] == ns and r["deadline"] == D]
        if not R:
            continue
        fams = list(dict.fromkeys(r["family"] for r in R))
        ref = next(r for r in R if r["family"] == REF)
        mc = ref["mem_choice"]
        print(f"\n=== non-scaling {ns}, deadline {D} s")
        print("  warm miss probability v_w(m): " + ", ".join(f"{m} MB {v:.4f}" for m, v in ref["vw"].items())
              + f" -> MemAdapt chooses {mc[str(TAU_W)]} MB (tau_w {TAU_W}); "
              + ", ".join(f"tau_w {tw}: {mc[str(tw)]} MB" for tw in TAU_W_SENS))
        print("  (1) validation-selected, 5 held-out test weeks: mean cost USD/week | mean violating windows | "
              "weeks within 2% | minutes at >= 2048 MB | memory changes per week | selected settings")
        sel = {}
        for f in fams:
            t = sorted([r for r in R if r["family"] == f and r["week"] == "test" and r.get("selected")], key=lambda r: r["seed"])
            if len(t) != len(SEEDS):
                continue
            sel[f] = t
            c, v = np.array([r["cost"] for r in t]), np.array([r["viol"] for r in t])
            print(f"    {f:22s} {c.mean():8.1f} | {100 * v.mean():6.2f}% | {int((v <= 0.02 + 1e-12).sum())}/5 | "
                  f"{100 * np.mean([r['share_ge2048'] for r in t]):5.1f}% | {np.mean([r['mem_changes'] for r in t]):6.1f} | "
                  f"{[r['param'] for r in t]}")
        if REF in sel:
            for f in [x for x in sel if x != REF]:
                d = [100 * (a["cost"] / b_["cost"] - 1) for a, b_ in zip(sel[f], sel[REF])]
                dv = [100 * (a["viol"] - b_["viol"]) for a, b_ in zip(sel[f], sel[REF])]
                print(f"      {f} vs {REF}: cost {np.mean(d):+.1f}% (per trace {', '.join(f'{x:+.1f}' for x in d)}), "
                      f"violating windows {np.mean(dv):+.2f} points")
        print(f"  (2) POST HOC matched compliance, cost relative to {REF} at equal violating-window rate "
              "(per trace, frontier over the parameter)")
        for target in TARGETS:
            res = {}
            for f in fams:
                vals = []
                for s in SEEDS:
                    pts = [(r["viol"], r["cost"]) for r in R if r["family"] == f and r["seed"] == s and r["week"] == "test"]
                    vals.append(cost_at(envelope(pts), target) if len(pts) > 1 else np.nan)
                res[f] = np.array(vals)
            parts = []
            for f in [x for x in fams if x != REF]:
                x, y = res[f], res[REF]
                ok = ~np.isnan(x) & ~np.isnan(y)
                if not ok.any():
                    parts.append(f"{f}: no common point")
                    continue
                d = 100 * (x[ok] / y[ok] - 1)
                parts.append(f"{f} {d.mean():+.1f}% ({int(ok.sum())}/5: {', '.join(f'{z:+.1f}' for z in d)})")
            print(f"    at {100 * target:.1f}%: " + "; ".join(parts))
        print("  (3) POST HOC with test-week knowledge (as the stored E4b analysis): cheapest setting within 2% on the "
              "test week, mean over the traces where one exists")
        for f in fams:
            best = []
            for s in SEEDS:
                ok = [r for r in R if r["family"] == f and r["seed"] == s and r["week"] == "test" and r["viol"] <= 0.02 + 1e-12]
                best.append(min(ok, key=lambda r: r["cost"]) if ok else None)
            have = [x for x in best if x is not None]
            if have:
                print(f"    {f:22s} {np.mean([x['cost'] for x in have]):8.1f} USD/week ({len(have)}/5 traces have one; "
                      f"settings {[x['param'] for x in have]})")
            else:
                print(f"    {f:22s} no setting within 2% on any trace")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        w = [int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")]
        run(out, w[0] if w else 5)
