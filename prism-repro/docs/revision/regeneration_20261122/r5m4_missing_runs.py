#!/usr/bin/env python3
"""R5.m4: the experimental combinations missing from the two per-trace supplement tables, run on the regenerated tree.
EXPLORATORY, PRE-CALIBRATION, fast simulator, development traces 101-105 (as the stored tables).

1. Ablation table (stored E3 design): the 'no scale-in rule' (use_hysteresis=False) and 'quantile feasibility'
   (feasibility_mode='quantile') variants were run for the stationary and new-spike test weeks only. Here they run at
   each trace's validation-selected eps (from the regenerated E1 rows, the same selection E3 uses) for the growth and
   bursty test weeks: 5 traces x 2 scenarios x 2 variants = 20 runs. The four stored scenarios are rerun too, as a
   consistency check against the regenerated E3 rows.
2. QuantProv memory table (stored R2 design): QuantProv-q90 at 2048 MB was selected at the bottom of its grid (a = 0.6)
   in 10 of 12 stored rows. Here every QuantProv rule and memory size of R2 also runs at the widened grid values of
   experiment.GRIDS_WIDE beyond both ends (a = 0.4, 0.5, 1.6, 1.8, 2.0), on the same two traces, six regimes and
   stationary test week, so the post hoc selection can be redone on the widened grid.

usage (from the tree's prism-repro/): python r5m4_missing_runs.py <tree prism-repro> <out_dir>
"""
import dataclasses
import json
import os
import sys
import time

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from prism_repro.config import PipelineConfig                              # noqa: E402
from prism_repro.experiment import GRIDS, GRIDS_WIDE, TraceBundle, make_policy, run_policy  # noqa: E402
from prism_repro.simulator import simulate                                  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS                             # noqa: E402
import run_experiments as RX                                                # noqa: E402  (selections(), RESULTS)

os.makedirs(OUT, exist_ok=True)
KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "share_mem_ge_2048", "mean_provisioned")

# 1. ablation variants for every scenario, at the validation-selected eps
f = open(os.path.join(OUT, "ablation_variants.jsonl"), "w", encoding="utf-8", newline="\n")
for seed in (101, 102, 103, 104, 105):
    eps = RX.selections(seed)["PRISM"]["param"]
    b = TraceBundle(seed, PipelineConfig())
    for sc in MAIN_SCENARIOS:
        for tag, prism in (("qmode", dict(feasibility_mode="quantile")), ("nohyst", dict(use_hysteresis=False))):
            spec = dict(family="PRISM", param=eps, tag=f"-{tag}", prism=prism)
            t0 = time.perf_counter()
            s = run_policy(b, sc, "test", spec)["summary"]
            row = dict(seed=seed, scenario=sc, variant=tag, eps=eps, stored_design=sc in ("stationary", "new_spike"),
                       runtime_s=round(time.perf_counter() - t0, 2), **{k: float(s[k]) for k in KEYS if k in s})
            f.write(json.dumps(row) + "\n")
            f.flush()
    print(f"ablation seed {seed} done (eps {eps})", flush=True)
f.close()

# 2. QuantProv memory rows on the widened grid (values beyond both ends of GRIDS['QuantProv'])
REGIMES = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
extra = [a for a in GRIDS_WIDE["QuantProv"] if a not in GRIDS["QuantProv"]]
f = open(os.path.join(OUT, "quantprov_memory_widened.jsonl"), "w", encoding="utf-8", newline="\n")
for seed in (101, 102):
    bundles = {}
    for ns, D in REGIMES:
        if ns not in bundles:
            bundles[ns] = TraceBundle(seed, PipelineConfig().with_(nonscaling=ns), scenarios=("stationary",))
        b = bundles[ns]
        for ti, nm in ((2, "q90"), (3, "q99")):
            for mem in (1024, 2048):
                for a in extra:
                    cfg = b.cfg.with_(deadline=D, default_mem=mem)
                    ctx = dataclasses.replace(b.context("stationary", "test"), cfg=cfg, _Kweek={})
                    t0 = time.perf_counter()
                    s = simulate(ctx, make_policy(dict(family="QuantProv", tau_idx=ti, param=a)))["summary"]
                    f.write(json.dumps(dict(seed=seed, nonscaling=ns, deadline=D, mem=mem, label=f"QuantProv_{nm}{mem}-{a}",
                                            param=a, widened=True, runtime_s=round(time.perf_counter() - t0, 2),
                                            **{k: float(s[k]) for k in KEYS if k in s})) + "\n")
                    f.flush()
        print(f"QuantProv widened seed {seed} ns {ns} D {D} done", flush=True)
f.close()
print("done")
