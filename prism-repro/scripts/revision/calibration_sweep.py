#!/usr/bin/env python3
"""Sensitivity of the online calibration, and independent per-quantile offsets at matched compliance (R2.11, R7.5).

PRE-CALIBRATION, EXPLORATORY (fast simulator, assumed constants, current code). Plan tasks #76-78.

Part A, one-at-a-time sweep around the submitted calibration (gamma 0.05, clip [-0.3, 0.8], delay 2 epochs,
initial offset 0): gamma {0.02, 0.10}; clip {[-0.1, 0.5], [-0.5, 1.2]}; delay {3, 4}; initial offset {0.2, 0.4}.
For each setting and trace (seeds 101-105) PRISM and QuantProv-q90 are tuned on the validation week by the paper's
rule and run in the four held-out test weeks at the selected setting. Recorded: cost, violating windows, weeks
meeting the 2% target, selected parameter, coverage of the calibrated q0.9 and q0.99 in the test weeks, and the
mean offset.

Part B, shared (submitted Eq. (13)) against independent offsets (PrismConfig.conformal_per_quantile): every eps of
PRISM and every a of QuantProv-q90 runs on the validation week and on every test week, so that the comparison can be
made both with validation-selected settings and, post hoc, at matched compliance (cost interpolated on the frontier
over the parameter at equal violating-window rate, per trace, pooled over scenarios), not at matched eps.

Usage: python calibration_sweep.py <code_root> <out_dir> [A|B|both]
       python calibration_sweep.py <code_root> <out_dir> --analyse
"""
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
SCEN = ("stationary", "growth", "bursty", "new_spike")
SWEEP = {
    "gamma=0.02": dict(gamma=0.02), "gamma=0.10": dict(gamma=0.10),
    "clip=[-0.1,0.5]": dict(s_min=-0.1, s_max=0.5), "clip=[-0.5,1.2]": dict(s_min=-0.5, s_max=1.2),
    "delay=3": dict(conformal_delay_epochs=3), "delay=4": dict(conformal_delay_epochs=4),
    "s0=0.2": dict(conformal_s0=0.2), "s0=0.4": dict(conformal_s0=0.4),
}
MODES = {"shared": dict(), "independent": dict(conformal_per_quantile=True)}
FAMS = {"PRISM": ("PRISM", {}), "QuantProv_q90": ("QuantProv", {"tau_idx": 2})}


def _coverage(b):
    out = {}
    for sc in SCEN:
        f = b.forecasts[(sc, "test", "gbm")]
        ok = np.isfinite(f["y"])
        y, q = f["y"][ok], f["q_cal"][ok]
        out[sc] = dict(cov90=float((y <= q[:, 2]).mean()), cov99=float((y <= q[:, 3]).mean()),
                       offset=float(np.mean(f["s"])))
    return out


def job(task):
    part, name, seed = task
    from prism_repro.config import PipelineConfig, PrismConfig
    from prism_repro.experiment import GRIDS, TraceBundle, make_policy, select_by_rule
    from prism_repro.simulator import simulate
    t0 = time.time()
    pc = PrismConfig(**(SWEEP[name] if part == "A" else MODES[name]))
    pc.validate()
    b = TraceBundle(seed, PipelineConfig(), conformal=pc)
    cov = _coverage(b)
    rows = []
    for fam, (base, extra) in FAMS.items():
        val = []
        for p in GRIDS[base]:
            s = simulate(b.context("stationary", "val"), make_policy(dict(family=base, param=p, **extra), pc))["summary"]
            val.append(dict(param=p, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"])))
            rows.append(dict(part=part, setting=name, seed=seed, family=fam, week="val", scenario="validation", param=p,
                             cost=val[-1]["cost"], viol=val[-1]["violating_window_rate"]))
        sel = select_by_rule(val)["param"]
        params = [sel] if part == "A" else list(GRIDS[base])
        for p in params:
            for sc in SCEN:
                s = simulate(b.context(sc, "test"), make_policy(dict(family=base, param=p, **extra), pc))["summary"]
                rows.append(dict(part=part, setting=name, seed=seed, family=fam, week="test", scenario=sc, param=p,
                                 selected=bool(p == sel), cost=float(s["cost"]), viol=float(s["violating_window_rate"]),
                                 **{k: cov[sc][k] for k in ("cov90", "cov99", "offset")}))
    return rows, round(time.time() - t0, 1)


def run(out_dir, which):
    tasks = []
    if which in ("B", "both"):
        tasks += [("B", m, s) for m in MODES for s in SEEDS]
    if which in ("A", "both"):
        tasks += [("A", n, s) for n in SWEEP for s in SEEDS]
    with ProcessPoolExecutor(max_workers=5) as ex:
        for rows, t in ex.map(job, tasks):
            r0 = rows[0]
            with open(os.path.join(out_dir, f"rows_{r0['part']}_{r0['setting'].replace('=', '_').replace(',', '_')}_{r0['seed']}.jsonl"),
                      "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            print(f"{r0['part']} {r0['setting']} seed {r0['seed']}: {len(rows)} rows in {t}s", flush=True)
    import sklearn, scipy
    json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                   scipy=scipy.__version__, sklearn=sklearn.__version__),
              open(os.path.join(out_dir, "environment.json"), "w"), indent=1)


def envelope(pts):
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
    print("PRE-CALIBRATION, fast simulator, current code. Held-out test weeks; seeds 101-105 x 4 scenarios = 20 weeks.")

    def selected(part, setting, fam):
        return [r for r in rows if r["part"] == part and r["setting"] == setting and r["family"] == fam
                and r["week"] == "test" and r.get("selected")]

    def summ(t):
        c = np.array([r["cost"] for r in t]); v = np.array([r["viol"] for r in t])
        return c.mean(), 100 * v.mean(), int((v <= 0.02 + 1e-12).sum())

    print("\nA. Calibration sweep (validation-selected settings): cost USD/week | pooled violating windows | weeks met /20 | "
          "q0.9 / q0.99 coverage | mean offset")
    base = {f: summ(selected("B", "shared", f)) for f in FAMS}
    order = [("B", "shared", "submitted (gamma 0.05, clip [-0.3,0.8], delay 2, s0 0)")] + [("A", n, n) for n in SWEEP]
    for part, name, label in order:
        for fam in FAMS:
            t = selected(part, name, fam)
            if not t:
                continue
            c, v, met = summ(t)
            cov90 = np.mean([r["cov90"] for r in t]); cov99 = np.mean([r["cov99"] for r in t]); off = np.mean([r["offset"] for r in t])
            print(f"  {label:58s} {fam:13s} {c:7.1f} ({100*(c/base[fam][0]-1):+5.1f}%) | {v:4.2f}% | {met:2d}/20 | "
                  f"{100*cov90:4.1f}% / {100*cov99:4.1f}% | {off:.3f}")
    print("\nB. Shared vs independent offsets, validation-selected settings")
    for fam in FAMS:
        for m in MODES:
            c, v, met = summ(selected("B", m, fam))
            print(f"  {fam:13s} {m:11s}: cost {c:7.1f} | violating windows {v:4.2f}% | weeks met {met}/20")
    print("\nB. POST HOC matched compliance (frontier over the family's parameter on test weeks, per trace, pooled over "
          "scenarios): cost at equal violating-window rate")
    for target in (0.01, 0.015, 0.02):
        res = {}
        for fam in FAMS:
            for m in MODES:
                vals = []
                for s in SEEDS:
                    pts = {}
                    for r in rows:
                        if r["part"] == "B" and r["setting"] == m and r["family"] == fam and r["seed"] == s and r["week"] == "test":
                            pts.setdefault(r["param"], []).append((r["viol"], r["cost"]))
                    fr = envelope([(np.mean([p[0] for p in v]), np.mean([p[1] for p in v])) for v in pts.values()])
                    vals.append(cost_at(fr, target))
                res[(fam, m)] = np.array(vals)

        def diff(a, b):
            x, y = res[a], res[b]; ok = ~np.isnan(x) & ~np.isnan(y)
            d = 100 * (x[ok] / y[ok] - 1)
            return (f"{d.mean():+.2f}% (per trace {np.round(d, 2).tolist()}, {int(ok.sum())}/5)" if ok.any() else "n/a")
        print(f"  at {100*target:.1f}%: independent vs shared: PRISM {diff(('PRISM','independent'), ('PRISM','shared'))}; "
              f"QuantProv-q90 {diff(('QuantProv_q90','independent'), ('QuantProv_q90','shared'))}")
        print(f"            PRISM vs QuantProv-q90: shared {diff(('PRISM','shared'), ('QuantProv_q90','shared'))}; "
              f"independent {diff(('PRISM','independent'), ('QuantProv_q90','independent'))}")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        run(out, sys.argv[3] if len(sys.argv) > 3 else "both")
