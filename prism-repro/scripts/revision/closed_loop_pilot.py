#!/usr/bin/env python3
"""Closed-loop PILOT under docs/revision/PRESPECIFICATION.md section 7 (R2.2, R6.3, R2.5, R3.5). EXPLORATORY.

PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION: the simulator's constants are assumed, not measured. Development seeds
101-103, stationary scenario, default deadline; PRISM, QuantProv-q90, Reactive and MemAdapt-q90 (GBM forecasts
online). Each policy is tuned on the closed-loop validation week by the common rule with the prespecified edge
expansion, then its selected setting runs on the held-out test week (identical workloads and draws for every policy).
Each (trace, policy) group is saved as it completes with the commit, environment, configuration and seed.

Usage: python closed_loop_pilot.py <code_root> <out_dir> [--workers=N]  |  ... <out_dir> --analyse
"""
import glob
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.join(ROOT, "src"))
SEEDS = (101, 102, 103)
SC = "stationary"
FAMILIES = {"PRISM": (dict(family="PRISM"), "PRISM"),
            "QuantProv_q90": (dict(family="QuantProv", tau_idx=2), "QuantProv"),
            "Reactive": (dict(family="Reactive"), "Reactive"),
            "MemAdapt_q90": (dict(family="MemAdapt", tau_idx=2), "QuantProv")}
KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "overflow_share", "p99_latency")


def week_run(b, cfg, spec, p, week):
    from prism_repro.closed_loop import PolicyController
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import WEEK_START, make_policy
    ws = WEEK_START[week]
    counts = b.traces[SC]["counts"][ws:ws + 7 * 1440]
    dr = EventDraws(cfg, counts, b.seed, 2 if week == "val" else 3)
    pol = make_policy(dict(spec, param=p))
    t0 = time.time()
    res = simulate_events(cfg, dr, controller=PolicyController(pol, b, SC, week=week))
    s = res["summary"]
    me = res["raw"]["mem_epoch"]
    row = dict(week=week, param=p, runtime_s=round(time.time() - t0, 1), n_requests=int(dr.n),
               share_mem_ge_2048=float(np.mean(me >= 2048)), **{k: float(s[k]) for k in KEYS})
    if hasattr(pol, "rec"):
        row["kappa_mean"] = float(pol.rec["kappa"].mean())
        row["infeasible_share"] = float(1 - pol.rec["feasible"].mean())
    return row


def job(task):
    seed, fam = task
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import GRIDS, GRIDS_WIDE, TraceBundle, select_by_rule
    cfg = PipelineConfig()
    b = TraceBundle(seed, cfg, scenarios=(SC,))
    spec, gname = FAMILIES[fam]
    grid, wide = list(GRIDS[gname]), list(GRIDS_WIDE[gname])
    val = {p: week_run(b, cfg, spec, p, "val") for p in grid}
    expansions = []
    while True:                               # prespecified edge expansion (PRESPECIFICATION.md section 4)
        rows = [dict(param=p, cost=r["cost"], violating_window_rate=r["violating_window_rate"]) for p, r in val.items()]
        sel = select_by_rule(rows)["param"]
        ps = sorted(val)
        nxt = None
        if sel == ps[0]:
            lower = [q for q in wide if q < ps[0]]
            nxt = max(lower) if lower else None
        elif sel == ps[-1]:
            upper = [q for q in wide if q > ps[-1]]
            nxt = min(upper) if upper else None
        if nxt is None:
            break
        expansions.append(nxt)
        val[nxt] = week_run(b, cfg, spec, nxt, "val")
    ps = sorted(val)
    test = week_run(b, cfg, spec, sel, "test")
    return dict(seed=seed, family=fam, scenario=SC, grid=grid, expansions=expansions, selected=sel,
                edge_hit=bool(sel in (ps[0], ps[-1])), validation=[val[p] for p in ps], test=test)


def run(out, workers):
    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    import scipy
    import sklearn
    from prism_repro.config import PipelineConfig, PrismConfig
    meta = dict(commit=commit, platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__, seeds=list(SEEDS), scenario=SC,
                pipeline_config=PipelineConfig().to_dict(), prism_config=str(PrismConfig()),
                label="PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION; exploratory pilot (PRESPECIFICATION.md section 7)")
    json.dump(meta, open(os.path.join(out, "environment.json"), "w"), indent=1, default=str)
    tasks = [(s, f) for s in SEEDS for f in FAMILIES]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(job, tasks):
            r["commit"] = commit
            with open(os.path.join(out, f"group_{r['seed']}_{r['family']}.json"), "w") as fh:
                json.dump(r, fh, indent=1)
            print(r["seed"], r["family"], "selected", r["selected"], "expansions", r["expansions"], flush=True)


def _t(x):
    from scipy import stats
    x = np.asarray(x, float)
    return x.mean(), stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def analyse(out):
    G = {(g["seed"], g["family"]): g for g in (json.load(open(p)) for p in glob.glob(os.path.join(out, "group_*.json")))}
    meta = json.load(open(os.path.join(out, "environment.json")))
    print(f"{meta['label']}\nCommit {meta['commit']}; {meta['platform']}; seeds {meta['seeds']}, {meta['scenario']}, "
          "default deadline; one held-out test week per trace.\n")
    print("Selected settings (validation week, common rule, prespecified edge expansion) and held-out test week:")
    print("  family         trace | selected (expansions) | edge | val: cost, violating | TEST: cost, violating windows, "
          "met 2% | cold-start ratio | kappa")
    for fam in FAMILIES:
        for s in SEEDS:
            g = G.get((s, fam))
            if not g:
                continue
            v = next(r for r in g["validation"] if r["param"] == g["selected"])
            t = g["test"]
            kap = f"{t['kappa_mean']:.3f}" if "kappa_mean" in t else "-"
            print(f"  {fam:14s} {s} | {g['selected']:>6} ({g['expansions'] or '-'}) | {'EDGE' if g['edge_hit'] else '    '} | "
                  f"{v['cost']:8.1f}, {100 * v['violating_window_rate']:5.2f}% | {t['cost']:8.1f}, "
                  f"{100 * t['violating_window_rate']:5.2f}%, {'yes' if t['violating_window_rate'] <= 0.02 + 1e-12 else 'NO '} | "
                  f"{t['cold_start_ratio']:.5f} | {kap}")
    print("\nPaired differences on the test weeks, PRISM minus comparator, across the independent traces "
          f"(mean, 95% t interval, df = {len(SEEDS) - 1}; per trace):")
    for comp in ("QuantProv_q90", "Reactive", "MemAdapt_q90"):
        ok = [s for s in SEEDS if (s, "PRISM") in G and (s, comp) in G]
        if len(ok) < 2:
            continue
        dc = [100 * (G[(s, "PRISM")]["test"]["cost"] / G[(s, comp)]["test"]["cost"] - 1) for s in ok]
        dv = [100 * (G[(s, "PRISM")]["test"]["violating_window_rate"] - G[(s, comp)]["test"]["violating_window_rate"]) for s in ok]
        (mc, hc), (mv, hv) = _t(dc), _t(dv)
        similar = abs(mv) + hv <= 0.5
        print(f"  vs {comp:14s} cost {mc:+.1f} +/- {hc:.1f}% ({', '.join(f'{x:+.1f}' for x in dc)}) | violating windows "
              f"{mv:+.2f} +/- {hv:.2f} points ({', '.join(f'{x:+.2f}' for x in dv)}) | similar compliance (+/-0.5): "
              f"{'yes' if similar else 'NO'}")
    rt = [r["runtime_s"] for g in G.values() for r in g["validation"] + [g["test"]]]
    print(f"\nRuntime: {len(rt)} closed-loop weeks, median {np.median(rt):.0f} s, total {sum(rt) / 3600:.1f} CPU-h.")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        w = [int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")]
        run(out, w[0] if w else 4)
