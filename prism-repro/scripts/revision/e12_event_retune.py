#!/usr/bin/env python3
"""E12 (added in the revision): tune every family under the EVENT-LEVEL simulator.

Open-loop, like E9: the provisioning schedules are the ones the fast-simulator runs of E1
produced and stored (results/raw/E1/arrays_seed*.npz); no policy is re-run. For each seed:
  1. replay the stored VALIDATION-week schedule of every grid point through des.simulate_events;
  2. apply the paper's selection rule (cheapest with <= 2 % violating windows, else least
     violating) to the event-level validation metrics;
  3. replay the selected configuration's stored TEST-week schedule in each scenario.
Because only stored schedules are replayed, results do not depend on the scikit-learn version.
Usage: python e12_event_retune.py <repo_root> <out_dir> <seed> [<seed> ...]
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = sys.argv[1]
OUT = sys.argv[2]
SEEDS = [int(s) for s in sys.argv[3:]]
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, simulate_events  # noqa: E402
from prism_repro.experiment import GRIDS, make_policy, select_by_rule  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS, generate_trace  # noqa: E402

FAMS = {  # family name -> list of specs (subset of the E1 grids; all schedules exist in E1)
    "OnDemand": [dict(family="OnDemand")],
    "Static": [dict(family="Static", param=p) for p in (95, 97, 99, 99.5, 99.9)],
    "Reactive": [dict(family="Reactive", param=p) for p in (0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7)],
    "PredHead": [dict(family="PredHead", param=p) for p in GRIDS["PredHead"]],
    "PredHead+hyst": [dict(family="PredHead", param=p, hyst=True) for p in GRIDS["PredHead"]],
    "QuantProv_q90": [dict(family="QuantProv", tau_idx=2, param=p) for p in GRIDS["QuantProv"]],
    "PRISM": [dict(family="PRISM", param=p) for p in GRIDS["PRISM"]],
}
cfg = PipelineConfig()
os.makedirs(OUT, exist_ok=True)


def replay(arr, seed, scenario, week, label, counts, draws):
    key = f"E1|{seed}|{scenario}|{week}|{label}|"
    P_ep, m_ep = arr[key + "::P_epoch"], arr[key + "::mem_epoch"]
    t0 = time.perf_counter()
    res = simulate_events(cfg, draws, P_ep, m_ep, want_inflight=False, sample_seed=None)
    s = res["summary"]
    return dict(cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"]),
                record_attainment=float(s["record_attainment"]), slo_met=bool(s["slo_met"]),
                runtime_s=time.perf_counter() - t0)


for seed in SEEDS:
    path = os.path.join(OUT, f"E12_seed{seed}.jsonl")
    done = set()
    if os.path.exists(path):
        done = {(r["week"], r["scenario"], r["label"]) for r in map(json.loads, open(path))}
    arr = np.load(os.path.join(ROOT, "results", "raw", "E1", f"arrays_seed{seed}.npz"))
    # validation week = days 15-21 of the (shared) stationary trace, draw stream index 2 (as in E1)
    vc = generate_trace(seed, "stationary")["counts"][14 * 1440:21 * 1440]
    vdr = EventDraws(cfg, vc, seed, 2)
    val_rows = {}
    with open(path, "a") as f:
        for fam, specs in FAMS.items():
            rows = []
            for spec in specs:
                label = make_policy(spec).label
                if ("val", "validation", label) in done:
                    r = [json.loads(l) for l in open(path) if json.loads(l)["label"] == label
                         and json.loads(l)["week"] == "val"][0]
                else:
                    r = replay(arr, seed, "stationary", "val", label, vc, vdr)
                    r.update(seed=seed, week="val", scenario="validation", family=fam, label=label, spec=spec,
                             open_loop=True, synthetic=True)
                    f.write(json.dumps(r) + "\n"); f.flush()
                    print(f"[E12] {seed} val {label} {r['runtime_s']:.0f}s", flush=True)
                rows.append(r)
            val_rows[fam] = select_by_rule(rows)
        for sc in MAIN_SCENARIOS:
            tc = generate_trace(seed, sc)["counts"][21 * 1440:28 * 1440]
            tdr = EventDraws(cfg, tc, seed, 3)
            for fam, sel in val_rows.items():
                if ("test", sc, sel["label"]) in done:
                    continue
                r = replay(arr, seed, sc, "test", sel["label"], tc, tdr)
                r.update(seed=seed, week="test", scenario=sc, family=fam, label=sel["label"], spec=sel["spec"],
                         selected=True, open_loop=True, synthetic=True)
                f.write(json.dumps(r) + "\n"); f.flush()
                print(f"[E12] {seed} test {sc} {sel['label']} {r['runtime_s']:.0f}s", flush=True)
    print(f"[E12] seed {seed} complete", flush=True)
