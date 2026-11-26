#!/usr/bin/env python3
"""End-to-end test of the optimiser where its reduction to a quantile rule should fail (R2.5, R4.1, R7.1, R6.7).

PRE-CALIBRATION, EXPLORATORY: fast simulator, assumed constants, current code. Reviewer 4 names two tests:
stage-specific demand, and utilisation above break-even with a wider eps grid. The static probe
(stage_demand_gap.py) found the paper's one-parameter family infeasible under fan-out on the paper's grid; this
runs whole held-out weeks.

Part P, per-stage demand phi (PipelineConfig.stage_demand), paper's grids (GRIDS). Profiles: common (1,1,1,1),
filter (1,1,0.5,0.5), fan-out (1,1,3,3), batch (1,1,1,0.1). Families:
  PRISM            the paper's candidate family (15), P_s = ceil(y d_s / 60); the risk and cost model knows phi
  PRISM-phi        candidate family proportional to the per-stage load, P_s = ceil(y phi_s d_s / 60)
  QuantProv_q90    calibrated q0.9 rule scaled by phi_s d_s (the rule knows phi, as PRISM's risk model does)
  PredHead+S       point-forecast headroom rule with the scale-in rule, scaled by phi_s d_s (validation-selected only)
  QuantProv_q90-blind  REFERENCE ONLY: q0.9 rule scaled by d_s, ignoring phi (what knowing phi is worth)
Part B, wider eps grid (GRIDS_WIDE, eps up to 0.20) where the cost term can choose the level:
  default_wide     the paper's workload and prices
  smooth6000_wide  smoother, larger workload (6000 records/min, AR log-noise sd 0.03, no random bursts, gamma
                   shape 400): billing utilisation reaches 0.58-0.69
  be0.30_wide      the paper's workload, provisioned-capacity price halved: break-even utilisation 0.30
  Families: PRISM and QuantProv_q90.

Every parameter value runs on the validation week and every test week (seeds 101-105, four scenarios) for the
frontier families. Reported: (1) validation-selected settings on the 20 held-out weeks, paired against
QuantProv_q90 (t intervals over the 20 weeks); (2) POST HOC matched compliance: per trace, cost on the frontier over
the parameter (mean over the four test weeks), interpolated at equal violating-window rate; (3) per eps, the share
of epochs in which PRISM's optimiser chose a level above the smallest feasible one (the reduction holds where this
is near zero).

Usage: python stage_demand_e2e.py <code_root> <out_dir> [P|B|both]  |  ... <out_dir> --analyse
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
SCEN = ("stationary", "growth", "bursty", "new_spike")
PROFILES = {"common": None, "filter": (1.0, 1.0, 0.5, 0.5), "fanout": (1.0, 1.0, 3.0, 3.0), "batch": (1.0, 1.0, 1.0, 0.1)}
REGIMES = ("default_wide", "smooth6000_wide", "be0.30_wide")
SMOOTH = dict(mean_rate=6000.0, ar_sd=0.03, bursts_per_day=0.0, gamma_shape=400.0)
TARGETS = (0.01, 0.015, 0.02)


def _setup(part, key):
    """(PipelineConfig, WorkloadParams or None) for one profile / regime."""
    from prism_repro.config import PipelineConfig
    from prism_repro.workload import WorkloadParams
    cfg = PipelineConfig()
    if part == "P":
        return cfg.with_(stage_demand=PROFILES[key]), None
    if key == "smooth6000_wide":
        return cfg, WorkloadParams(**SMOOTH)
    if key == "be0.30_wide":
        return cfg.with_(prices=dataclasses.replace(cfg.prices, pc=cfg.prices.pc * 0.5)), None
    return cfg, None


def _families(part, key):
    """name -> (spec for make_policy, grid, run the whole grid on test weeks)."""
    from prism_repro.experiment import GRIDS, GRIDS_WIDE
    G = GRIDS_WIDE if part == "B" else GRIDS
    fams = {"PRISM": (dict(family="PRISM"), G["PRISM"], True)}
    if part == "P" and key != "common":
        fams["PRISM-phi"] = (dict(family="PRISM", prism={"family_follows_stage_demand": True}), G["PRISM"], True)
    fams["QuantProv_q90"] = (dict(family="QuantProv", tau_idx=2), G["QuantProv"], True)
    if part == "P":
        fams["PredHead+S"] = (dict(family="PredHead", hyst=True), G["PredHead"], False)
        if key != "common":
            fams["QuantProv_q90-blind"] = (dict(family="QuantProv", tau_idx=2, blind=True), G["QuantProv"], True)
    return fams


def _policy(spec, p):
    from prism_repro.experiment import make_policy
    from prism_repro.latency import stage_means
    from prism_repro.policies import QuantProv
    if spec.get("blind"):
        class QuantProvBlind(QuantProv):
            def prepare(self, ctx):
                super().prepare(ctx)
                self.d = stage_means(self.cfg, self.cfg.default_mem)   # ignores phi
        return QuantProvBlind(spec["tau_idx"], p)
    return make_policy(dict(spec, param=p))


def job(task):
    part, key, seed = task
    from prism_repro import optimizer as optmod
    from prism_repro.experiment import TraceBundle, select_by_rule
    from prism_repro.simulator import simulate
    counter = {"feasible": 0, "above": 0}
    o_eval, o_dec = optmod.ChanceConstrainedOptimizer.evaluate, optmod.ChanceConstrainedOptimizer.decide

    def evaluate(self, *a, **k):
        r = o_eval(self, *a, **k)
        self._last_ev = r
        return r

    def decide(self, scen, mems, kappa):   # decisions unchanged; counts as level_choice_margins.py does
        d = o_dec(self, scen, mems, kappa)
        ev = self._last_ev
        if d.feasible:
            feas = ev["feas"] >= 1 - self.pcfg.delta - 1e-12
            i = list(ev["mems"]).index(d.mem)
            j = int(np.argmin(np.abs(np.asarray(ev["ys"]) - d.level)))
            counter["feasible"] += 1
            counter["above"] += int(j != int(np.argmax(feas[i])))
        return d
    optmod.ChanceConstrainedOptimizer.evaluate, optmod.ChanceConstrainedOptimizer.decide = evaluate, decide
    t0 = time.time()
    cfg, wp = _setup(part, key)
    b = TraceBundle(seed, cfg, wparams=wp)
    rows = []
    for fam, (spec, grid, frontier) in _families(part, key).items():
        val = []
        for p in grid:
            counter["feasible"] = counter["above"] = 0
            s = simulate(b.context("stationary", "val"), _policy(spec, p))["summary"]
            val.append(dict(param=p, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"])))
            rows.append(dict(part=part, key=key, seed=seed, family=fam, week="val", scenario="validation", param=p,
                             cost=val[-1]["cost"], viol=val[-1]["violating_window_rate"],
                             utilisation=float(s["billing_utilisation"]),
                             feasible_epochs=counter["feasible"], above_smallest=counter["above"]))
        sel = select_by_rule(val)["param"]
        for p in (grid if frontier else [sel]):
            for sc in SCEN:
                counter["feasible"] = counter["above"] = 0
                s = simulate(b.context(sc, "test"), _policy(spec, p))["summary"]
                rows.append(dict(part=part, key=key, seed=seed, family=fam, week="test", scenario=sc, param=p,
                                 selected=bool(p == sel), cost=float(s["cost"]), viol=float(s["violating_window_rate"]),
                                 utilisation=float(s["billing_utilisation"]),
                                 feasible_epochs=counter["feasible"], above_smallest=counter["above"]))
    return rows, round(time.time() - t0, 1)


def run(out_dir, which, workers):
    tasks = []
    if which in ("P", "both"):
        tasks += [("P", k, s) for k in PROFILES for s in SEEDS]
    if which in ("B", "both"):
        tasks += [("B", k, s) for k in REGIMES for s in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows, t in ex.map(job, tasks):
            r0 = rows[0]
            with open(os.path.join(out_dir, f"rows_{r0['part']}_{r0['key']}_{r0['seed']}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            print(f"{r0['part']} {r0['key']} seed {r0['seed']}: {len(rows)} rows in {t}s", flush=True)
    import scipy
    import sklearn
    json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                   scipy=scipy.__version__, sklearn=sklearn.__version__), open(os.path.join(out_dir, "environment.json"), "w"),
              indent=1)


def envelope(pts):
    """Lower-left frontier of (violating rate, cost) points: cost strictly falls as the violating rate rises."""
    keep, best = [], np.inf
    for v, c in sorted(pts):
        if c < best - 1e-9:
            keep.append((v, c))
            best = c
    return keep


def cost_at(keep, t):
    """Cost on the frontier at violating rate t (linear interpolation); NaN outside the frontier's range."""
    if not keep or t < keep[0][0] - 1e-12:
        return np.nan
    for (v0, c0), (v1, c1) in zip(keep, keep[1:]):
        if v0 <= t <= v1:
            return c0 + (c1 - c0) * (t - v0) / (v1 - v0) if v1 > v0 else c0
    return keep[-1][1] if t >= keep[-1][0] - 1e-12 else np.nan


def _tci(x):
    from scipy import stats
    x = np.asarray(x, float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
    return x.mean(), h


def analyse(out_dir):
    rows = [json.loads(line) for p in sorted(glob.glob(os.path.join(out_dir, "rows_*.jsonl"))) for line in open(p)]
    env = json.load(open(os.path.join(out_dir, "environment.json"))) if os.path.exists(os.path.join(out_dir, "environment.json")) else {}
    print("PRE-CALIBRATION, EXPLORATORY. Fast simulator, assumed constants, current code. "
          f"Environment: {env}.\nSeeds 101-105 x 4 held-out test scenarios = 20 weeks per cell; violating windows "
          "pooled over the week (672 windows, 2% = 13 windows allowed).")
    order = [("P", k) for k in PROFILES] + [("B", k) for k in REGIMES]
    for part, key in [g for g in order if any(r["part"] == g[0] and r["key"] == g[1] for r in rows)]:
        R = [r for r in rows if r["part"] == part and r["key"] == key]
        fams = list(dict.fromkeys(r["family"] for r in R))
        head = f"phi = {PROFILES[key]}" if part == "P" else {
            "default_wide": "paper's workload and prices, GRIDS_WIDE",
            "smooth6000_wide": "smooth 6000/min workload, GRIDS_WIDE",
            "be0.30_wide": "provisioned price halved (break-even 0.30), GRIDS_WIDE"}[key]
        print(f"\n=== {part} {key} ({head})")
        print("  (1) validation-selected, 20 held-out weeks: mean cost USD/week | mean violating windows | weeks "
              "within 2% | billing utilisation | PRISM epochs above the smallest feasible level")
        sel = {}
        for f in fams:
            t = sorted([r for r in R if r["family"] == f and r["week"] == "test" and r.get("selected")],
                       key=lambda r: (r["seed"], SCEN.index(r["scenario"])))
            if len(t) != 20:
                continue
            sel[f] = t
            c = np.array([r["cost"] for r in t])
            v = np.array([r["viol"] for r in t])
            fe, ab = sum(r["feasible_epochs"] for r in t), sum(r["above_smallest"] for r in t)
            ps = sorted({r["param"] for r in t})
            extra = f" | {ab} of {fe} ({100 * ab / max(fe, 1):.1f}%)" if f.startswith("PRISM") else ""
            note = " [REFERENCE: ignores phi]" if f.endswith("-blind") else ""
            print(f"    {f:19s} {c.mean():9.1f} | {100 * v.mean():5.2f}% | {int((v <= 0.02 + 1e-12).sum()):2d}/20 | "
                  f"{np.mean([r['utilisation'] for r in t]):.3f}{extra} | selected {ps}{note}")
        if "QuantProv_q90" in sel:
            q = sel["QuantProv_q90"]
            for f in [x for x in sel if x != "QuantProv_q90"]:
                dc = [100 * (a["cost"] / b_["cost"] - 1) for a, b_ in zip(sel[f], q)]
                dv = [100 * (a["viol"] - b_["viol"]) for a, b_ in zip(sel[f], q)]
                (mc, hc), (mv, hv) = _tci(dc), _tci(dv)
                cheaper = sum(x < 0 for x in dc)
                print(f"    {f} vs QuantProv_q90, paired over 20 weeks: cost {mc:+.1f} +/- {hc:.1f}% "
                      f"(cheaper in {cheaper}/20), violating windows {mv:+.2f} +/- {hv:.2f} points")
        print("  (2) POST HOC matched compliance (per trace, frontier over the parameter, mean of 4 test weeks): "
              "cost relative to QuantProv_q90 at equal violating-window rate")
        for target in TARGETS:
            res = {}
            for f in fams:
                vals = []
                for s in SEEDS:
                    pts = {}
                    for r in R:
                        if r["family"] == f and r["seed"] == s and r["week"] == "test":
                            pts.setdefault(r["param"], []).append((r["viol"], r["cost"]))
                    if len(pts) < 2:
                        vals.append(np.nan)
                        continue
                    vals.append(cost_at(envelope([(np.mean([p[0] for p in v]), np.mean([p[1] for p in v]))
                                                  for v in pts.values()]), target))
                res[f] = np.array(vals)
            parts = []
            y = res.get("QuantProv_q90")
            for f in [x for x in fams if x != "QuantProv_q90" and not np.all(np.isnan(res[x]))]:
                x = res[f]
                ok = ~np.isnan(x) & ~np.isnan(y)
                if not ok.any():
                    parts.append(f"{f}: no common point")
                    continue
                d = 100 * (x[ok] / y[ok] - 1)
                parts.append(f"{f} {d.mean():+.2f}% (traces {', '.join(f'{z:+.1f}' for z in d)}; {int(ok.sum())}/5)")
            print(f"    at {100 * target:.1f}%: " + ("; ".join(parts) if parts else "no family interpolable"))
            yb = res.get("QuantProv_q90-blind")
            if yb is not None:   # same allocation shape as PRISM's paper family (P_s proportional to d_s)
                x = res["PRISM"]
                ok = ~np.isnan(x) & ~np.isnan(yb)
                if ok.any():
                    d = 100 * (x[ok] / yb[ok] - 1)
                    print(f"      same allocation shape: PRISM vs QuantProv_q90-blind {d.mean():+.2f}% "
                          f"(traces {', '.join(f'{z:+.1f}' for z in d)}; {int(ok.sum())}/5)")
        if "QuantProv_q90-blind" in sel:
            q = sel["QuantProv_q90-blind"]
            dc = [100 * (a["cost"] / b_["cost"] - 1) for a, b_ in zip(sel["PRISM"], q)]
            dv = [100 * (a["viol"] - b_["viol"]) for a, b_ in zip(sel["PRISM"], q)]
            (mc, hc), (mv, hv) = _tci(dc), _tci(dv)
            print(f"  same allocation shape, validation-selected: PRISM vs QuantProv_q90-blind cost {mc:+.1f} +/- {hc:.1f}% "
                  f"(cheaper in {sum(x < 0 for x in dc)}/20), violating windows {mv:+.2f} +/- {hv:.2f} points")
        for f in [x for x in fams if x.startswith("PRISM")]:
            print(f"  (3) {f} per eps over the 20 test weeks: eps | mean cost | mean violating windows | utilisation | "
                  "epochs above the smallest feasible level")
            for p in sorted({r["param"] for r in R if r["family"] == f}):
                t = [r for r in R if r["family"] == f and r["week"] == "test" and r["param"] == p]
                if len(t) != 20:
                    continue
                fe, ab = sum(r["feasible_epochs"] for r in t), sum(r["above_smallest"] for r in t)
                print(f"      {p:6.3f} | {np.mean([r['cost'] for r in t]):9.1f} | {100 * np.mean([r['viol'] for r in t]):5.2f}% | "
                      f"{np.mean([r['utilisation'] for r in t]):.3f} | {100 * ab / max(fe, 1):5.1f}% of {fe} feasible "
                      f"(of {20 * 2016} epochs)")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        args = [a for a in sys.argv[3:] if not a.startswith("--")]
        w = [int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")]
        run(out, args[0] if args else "both", w[0] if w else 5)
