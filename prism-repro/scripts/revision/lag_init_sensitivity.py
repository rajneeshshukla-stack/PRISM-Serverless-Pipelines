#!/usr/bin/env python3
"""Activation-lag and init-vs-memory sensitivity in the fast simulator (R1.2, R1.3, R4.3, R5.M2, R7.5).

PRE-CALIBRATION, EXPLORATORY. Reviewers ask for runs at L = 5 and 10 minutes and with initialisation time
constant or growing with memory. Both can be run before the AWS campaign; only the measured centre point (the
measured lag, the measured init curve) waits for it. Nothing here is a final table.

Part LAG (R1.3, R4.3, R5.M2): for L in 2, 5, 10 minutes the whole stack follows the lag (forecast horizon
and conformal delay: features.forecast_horizon / min_feedback_delay). Per trace (seeds 101-105) and L, every
family below is tuned on the validation week by the paper's rule (experiment.select_by_rule) over its grid in
experiment.GRIDS and run in the four held-out test weeks at the selected setting:
    PRISM (eps), QuantProv-q90 (a), PredHead+S (h, smoothed), Reactive (u).
It records cost, violating-window rate, weeks meeting the 2% target, the selected parameter and the mean
conformal offset of the test week (does a longer lag need a more conservative offset?).

Part INIT (R1.2, R5.M2): the regime where memory matters (nonscaling 0.5, deadline 13 s and 12 s; stationary
test week; seeds 101-102, as E4), PRISM at eps = 0.02 with memory optimisation and with memory fixed at
1024 MB, for init_scaling in eq3 (submitted), constant and inverted (latency.init_factor). It records cost,
violating-window rate and PRISM's share of epochs at >= 2048 MB: does the system still move to larger memory,
and does memory co-optimisation still pay, when initialisation does not shorten with memory?

Usage: python lag_init_sensitivity.py <code_root> <out_dir> [lag|init|both]
"""
import dataclasses
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.join(ROOT, "src"))

SEEDS = (101, 102, 103, 104, 105)
LAGS = (2, 5, 10)
FAMILIES = (("PRISM", {}), ("QuantProv_q90", {"tau_idx": 2}), ("PredHead+S", {"hyst": True}), ("Reactive", {}))
INIT_MODES = ("eq3", "constant", "inverted")
INIT_REGIMES = ((0.5, 13.0), (0.5, 12.0))
INIT_SEEDS = (101, 102)


def _spec(fam, extra, p):
    base = {"PRISM": "PRISM", "QuantProv_q90": "QuantProv", "PredHead+S": "PredHead", "Reactive": "Reactive"}[fam]
    return dict(family=base, param=p, **extra)


def _grid(fam):
    from prism_repro.experiment import GRIDS
    return GRIDS[{"QuantProv_q90": "QuantProv", "PredHead+S": "PredHead"}.get(fam, fam)]


def lag_job(job):
    seed, L = job
    import numpy as np
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, make_policy, select_by_rule
    from prism_repro.simulator import simulate
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig().with_(lag_min=L))
    out = []
    for fam, extra in FAMILIES:
        val = []
        for p in _grid(fam):
            s = simulate(b.context("stationary", "val"), make_policy(_spec(fam, extra, p)))["summary"]
            val.append(dict(param=p, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"])))
        sel = select_by_rule(val)
        for sc in ("stationary", "growth", "bursty", "new_spike"):
            s = simulate(b.context(sc, "test"), make_policy(_spec(fam, extra, sel["param"])))["summary"]
            fc = b.forecasts[(sc, "test", "gbm")]
            out.append(dict(part="lag", seed=seed, lag=L, family=fam, scenario=sc, param=sel["param"],
                            val_viol=sel["violating_window_rate"], cost=float(s["cost"]),
                            viol=float(s["violating_window_rate"]), met=bool(s["violating_window_rate"] <= 0.02 + 1e-12),
                            mean_offset_test=float(np.mean(fc["s"]))))
    return out, round(time.time() - t0, 1)


def init_job(job):
    seed, mode = job
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, make_policy
    from prism_repro.simulator import simulate
    t0 = time.time()
    out = []
    bundles = {}
    for ns, D in INIT_REGIMES:
        if ns not in bundles:
            bundles[ns] = TraceBundle(seed, PipelineConfig().with_(nonscaling=ns), scenarios=("stationary",))
        b = bundles[ns]
        cfg = b.cfg.with_(deadline=D, init_scaling=mode)
        ctx = dataclasses.replace(b.context("stationary", "test"), cfg=cfg, _Kweek={})
        for tag, spec in (("PRISM-mem", dict(family="PRISM", param=0.02)),
                          ("PRISM-1024", dict(family="PRISM", param=0.02, prism=dict(optimise_memory=False))),
                          ("OnDemand", dict(family="OnDemand"))):
            s = simulate(ctx, make_policy(spec))["summary"]
            out.append(dict(part="init", seed=seed, init_scaling=mode, nonscaling=ns, deadline=D, policy=tag,
                            cost=float(s["cost"]), viol=float(s["violating_window_rate"]),
                            share_mem_ge_2048=float(s.get("share_mem_ge_2048", 0.0))))
    return out, round(time.time() - t0, 1)


if __name__ == "__main__":
    out_dir = sys.argv[2]
    part = sys.argv[3] if len(sys.argv) > 3 else "both"
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(max_workers=5) as ex:
        futs = []
        if part in ("lag", "both"):
            futs += [ex.submit(lag_job, (s, L)) for L in LAGS for s in SEEDS]
        if part in ("init", "both"):
            futs += [ex.submit(init_job, (s, m)) for m in INIT_MODES for s in INIT_SEEDS]
        for f in futs:
            r, t = f.result()
            rows += r
            print(f"{r[0]['part']} seed {r[0]['seed']} {r[0].get('lag', r[0].get('init_scaling'))}: {len(r)} rows in {t}s",
                  flush=True)
    env = dict(python=sys.version)
    for m in ("numpy", "scipy", "sklearn"):
        env[m] = __import__(m).__version__
    with open(os.path.join(out_dir, "rows.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(out_dir, "environment.json"), "w", encoding="utf-8") as fh:
        json.dump(env, fh, indent=1)
    print("wrote", len(rows), "rows")
