#!/usr/bin/env python3
"""End-to-end check of the integer-search gap (R2.13; also R2.5, R4.1, R6.7, R7.1). OFFLINE BENCHMARK, post hoc.

The response letter cites a 1.92% mean end-to-end saving from six offline test-week replays run with
scripts/revision/integer_search_e2e.py in one Linux sandbox. That script was not available on the machine
where this check was written; this file is an INDEPENDENT reconstruction from its description, not the
cited script. Being different code, its numbers are not comparable digit for digit with the cited ones, and
it supports no claim about the cited script on any platform. The cited script remains the canonical source.

What it does. For each run it simulates PRISM twice on the same test week: (base) unchanged; (searched) with
ChanceConstrainedOptimizer.decide wrapped so that, in every epoch where PRISM's own decision is feasible,
integer coordinate descent (integer_search_gap.coord_search, the evaluator validated against the
optimiser by tests/test_controller.py) starts from PRISM's chosen vector and returns the cheapest vector it
finds that still meets the same per-epoch feasibility rule (share of scenarios with v <= eps >= 1 - delta),
at PRISM's chosen memory size, kappa and load ratio. Hysteresis and everything after the optimiser are
unchanged. The searched vector is an offline benchmark: it is not a policy PRISM could run as specified.

  runs     seeds 101, 102, 103 x {stationary, new_spike}, test weeks, GBM forecaster, current code defaults
  epsilon  the E1 validation-selected values used by level_choice_diagnostic.py: 101 -> 0.02, 102 -> 0.03,
           103 -> 0.05
  reports  cost (USD/week), violating-window rate, and "epochs improved" = epochs in which the search found
           a cheaper feasible vector / epochs in which PRISM's decision was feasible (the search's domain)

Usage: python integer_search_e2e_check.py <code_root> <out.json> [seed:scenario ...]
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'revision'))

SEL = {101: 0.02, 102: 0.03, 103: 0.05}
RUNS = [(s, sc) for s in SEL for sc in ("stationary", "new_spike")]


def one(run):
    seed, sc = run
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, make_policy
    from prism_repro.simulator import simulate
    from prism_repro import optimizer as optmod
    from integer_search_gap import coord_search, eval_P
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig(), scenarios=("stationary", sc) if sc != "stationary" else ("stationary",))
    spec = {"family": "PRISM", "param": SEL[seed]}
    base = simulate(b.context(sc, "test"), make_policy(spec))["summary"]
    orig = optmod.ChanceConstrainedOptimizer.decide
    stats = dict(feasible=0, improved=0, rel_gain=[])

    def decide(self, scen, mems, kappa):
        dec = orig(self, scen, mems, kappa)
        if not dec.feasible:
            return dec
        stats["feasible"] += 1
        c0, _ = eval_P(dec.P, dec.mem, scen, kappa, self.pcfg, self.cfg, self.r)
        P1, c1 = coord_search(dec.P, dec.mem, scen, kappa, self.pcfg, self.cfg, self.r)
        if c1 < c0 - 1e-12:
            stats["improved"] += 1
            stats["rel_gain"].append((c0 - c1) / c0)
            _, f1 = eval_P(P1, dec.mem, scen, kappa, self.pcfg, self.cfg, self.r)
            return optmod.Decision(P=np.asarray(P1).astype(int), mem=dec.mem, feasible=True, feas_frac=f1,
                                   excess=0.0, exp_cost=c1, level=dec.level)
        return dec

    optmod.ChanceConstrainedOptimizer.decide = decide
    try:
        srch = simulate(b.context(sc, "test"), make_policy(spec))["summary"]
    finally:
        optmod.ChanceConstrainedOptimizer.decide = orig
    return dict(seed=seed, scenario=sc, eps=SEL[seed], base_cost=float(base["cost"]), searched_cost=float(srch["cost"]),
                saving=float(1 - srch["cost"] / base["cost"]),
                base_viol=float(base["violating_window_rate"]), searched_viol=float(srch["violating_window_rate"]),
                epochs_improved=stats["improved"], epochs_feasible=stats["feasible"],
                median_static_gain_improved=float(np.median(stats["rel_gain"])) if stats["rel_gain"] else None,
                runtime_s=round(time.time() - t0, 1))


if __name__ == "__main__":
    out = sys.argv[2]
    runs = [tuple((int(x.split(":")[0]), x.split(":")[1])) for x in sys.argv[3:]] or RUNS
    with ProcessPoolExecutor(max_workers=min(6, len(runs))) as ex:
        res = list(ex.map(one, runs))
    for r in res:
        print(f"{r['seed']} {r['scenario']:10s} base {r['base_cost']:8.2f} searched {r['searched_cost']:8.2f} "
              f"saving {100*r['saving']:5.2f}%  viol {100*r['base_viol']:.2f}% -> {100*r['searched_viol']:.2f}%  "
              f"improved {r['epochs_improved']}/{r['epochs_feasible']}", flush=True)
    sav = [r["saving"] for r in res]
    worse = sum(r["searched_viol"] > r["base_viol"] + 1e-12 for r in res)
    crossed = [f"{r['seed']}/{r['scenario']}" for r in res if r["base_viol"] <= 0.02 + 1e-12 < r["searched_viol"]]
    tot = dict(runs=len(res), mean_saving=float(np.mean(sav)), min_saving=float(min(sav)), max_saving=float(max(sav)),
               runs_compliance_worse=worse, runs_crossing_2pct_target=crossed,
               improved_share_range=[min(r["epochs_improved"] / r["epochs_feasible"] for r in res),
                                     max(r["epochs_improved"] / r["epochs_feasible"] for r in res)])
    env = dict(python=sys.version)
    for m in ("numpy", "scipy", "sklearn"):
        env[m] = __import__(m).__version__
    json.dump(dict(runs=res, totals=tot, environment=env), open(out, "w"), indent=1)
    print(tot)
