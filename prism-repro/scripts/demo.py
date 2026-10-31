#!/usr/bin/env python3
"""Short end-to-end demonstration (~1-2 min on one core). It exercises the real
pipeline — synthetic workload, forecaster training, conformal calibration, PRISM
optimiser, baselines, fast simulator and (unless --fast) the event-level simulator —
on DEVELOPMENT seed 7. It is a functional demonstration, NOT research evidence;
outputs go to results/demo/ and are not used by any table or claim.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, run_policy  # noqa: E402
from prism_repro.metrics import coverage, mape  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--fast", action="store_true", help="skip the event-level simulator")
a = ap.parse_args()
t0 = time.time()
cfg = PipelineConfig()
b = TraceBundle(7, cfg, scenarios=("stationary",))
f = b.forecasts[("stationary", "val", "gbm")]
print(f"[demo] SYNTHETIC trace seed 7; forecaster trained on days 1-14 in {time.time()-t0:.1f}s")
print(f"[demo] validation week: median MAPE {mape(f['y'], f['q_raw'][:, 1]):.1f}%, "
      f"q99 coverage raw {coverage(f['y'], f['q_raw'][:, 3]):.3f}, calibrated {coverage(f['y'], f['q_cal'][:, 3]):.3f}")
out = []
for spec in (dict(family="OnDemand"), dict(family="PredHead", param=1.3), dict(family="PRISM", param=0.05)):
    r = run_policy(b, "stationary", "val", spec)
    s = r["summary"]
    out.append(dict(label=s["label"], cost=round(s["cost"], 1), violating_windows=round(s["violating_window_rate"], 4),
                    record_attainment=round(s["record_attainment"], 5), infeasible_share=s.get("infeasible_share")))
    print(f"[demo] fast sim  {s['label']:14s} cost {s['cost']:8.1f} USD  violating windows {s['violating_window_rate']*100:5.2f}%")
    if spec["family"] == "PRISM":
        sched = r["raw"]
if not a.fast:
    from prism_repro.des import EventDraws, simulate_events
    counts = b.traces["stationary"]["counts"][14 * 1440:15 * 1440]  # first validation day only
    ev = simulate_events(cfg, EventDraws(cfg, counts, 7, 2), sched["P_epoch"][:288], sched["mem_epoch"][:288])["summary"]
    print(f"[demo] event-level, PRISM schedule, first day: cost {ev['cost']:.1f} USD, violating windows {ev['violating_window_rate']*100:.2f}%")
    out.append(dict(label="PRISM schedule, event-level, day 1", cost=ev["cost"], violating_windows=ev["violating_window_rate"]))
os.makedirs(os.path.join(ROOT, "results", "demo"), exist_ok=True)
json.dump(dict(note="DEMONSTRATION on development seed 7; not research evidence", synthetic=True, rows=out),
          open(os.path.join(ROOT, "results", "demo", "demo_output.json"), "w"), indent=1, default=float)
print(f"[demo] done in {time.time()-t0:.0f}s -> results/demo/demo_output.json")
