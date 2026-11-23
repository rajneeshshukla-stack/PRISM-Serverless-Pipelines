#!/usr/bin/env python3
"""R3.3: does the event-level evaluator depend on the fast simulator's match to Eq. (14)? EXPLORATORY, development seed
101 only (PRESPECIFICATION.md section 3), PRE-CALIBRATION defaults.

The match: the fast simulator draws each minute's peak concurrency as a Poisson quantile at u ~ U(1 - peak_upper_frac, 1)
(simulator.WeekDraws, "the upper 45%"), the construction behind Eq. (14), whose mean is close to the effective load
PRISM plans for. The check holds one provisioning schedule fixed (PRISM, eps 0.02, from a fast-simulator run on the
validation week) and evaluates it under two configurations that differ only in peak_upper_frac (0.45, the default, and
0.90): in the event-level simulator (open-loop replay, des.simulate_events) and in the fast simulator.
  - If the event-level outcome is bit-identical under both, its evaluation does not use the matched construction.
  - The fast simulator's outcome is expected to change, which shows the knob is live there.

usage (from prism-repro/): python docs/revision/confirmatory_20261122/r33_match_check.py <out.json>
"""
import dataclasses
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig                              # noqa: E402
from prism_repro.des import EventDraws, simulate_events                     # noqa: E402
from prism_repro.experiment import WEEK_START, TraceBundle, run_policy      # noqa: E402
from prism_repro.policies import Policy                                     # noqa: E402
from prism_repro.simulator import WeekDraws, simulate                       # noqa: E402

OUT = sys.argv[1]
KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "overflow_share", "p99_latency")
cfgA = PipelineConfig()
cfgB = cfgA.with_(peak_upper_frac=0.90)
b = TraceBundle(101, cfgA, scenarios=("stationary",))
spec = dict(family="PRISM", param=0.02)
fast = run_policy(b, "stationary", "val", spec)
P, mem = fast["raw"]["P_epoch"].astype(float), fast["raw"]["mem_epoch"].astype(int)


class FixedSchedule(Policy):
    family = "Fixed"

    def __init__(self, P, mem):
        super().__init__(None)
        self.Ps, self.ms = P, mem

    def decide(self, k, tel):
        return self.Ps[k], int(self.ms[k])


rep = dict(label="EXPLORATORY, development seed 101, validation week, PRE-CALIBRATION defaults",
           schedule=dict(source="PRISM eps 0.02, fast simulator, validation week", epochs=int(len(P)),
                         mean_P=float(P.mean()), share_mem_ge_2048=float(np.mean(mem >= 2048))))
ws = WEEK_START["val"]
counts = b.traces["stationary"]["counts"][ws:ws + 7 * 1440]
ev = {}
for name, cfg in (("peak_upper_frac 0.45 (default)", cfgA), ("peak_upper_frac 0.90", cfgB)):
    t0 = time.time()
    r = simulate_events(cfg, EventDraws(cfg, counts, 101, 2), P_epoch=P, mem_epoch=mem)
    ev[name] = {k: float(r["summary"][k]) for k in KEYS}
    ev[name]["runtime_s"] = round(time.time() - t0, 1)
fs = {}
ctxA = b.context("stationary", "val")
for name, cfg in (("peak_upper_frac 0.45 (default)", cfgA), ("peak_upper_frac 0.90", cfgB)):
    ctx = ctxA if cfg is cfgA else dataclasses.replace(ctxA, cfg=cfg, draws=WeekDraws(cfg, 101, 2), _Kweek={})
    r = simulate(ctx, FixedSchedule(P, mem))
    fs[name] = {k: float(r["summary"][k]) for k in KEYS if k in r["summary"]}
names = list(ev)
rep["event_level_open_loop"] = ev
rep["event_level_identical"] = all(ev[names[0]][k] == ev[names[1]][k] for k in KEYS)
rep["fast_simulator"] = fs
rep["fast_simulator_changes"] = any(fs[names[0]][k] != fs[names[1]][k] for k in fs[names[0]])
rep["fast_simulator_self_check"] = dict(
    note="the fixed schedule replayed in the fast simulator at the default reproduces the fast run's own outcome",
    run=float(fast["summary"]["violating_window_rate"]), replay=fs[names[0]]["violating_window_rate"],
    identical=float(fast["summary"]["violating_window_rate"]) == fs[names[0]]["violating_window_rate"])
rep["ok"] = rep["event_level_identical"] and rep["fast_simulator_changes"]
json.dump(rep, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps(rep, indent=1))
sys.exit(0 if rep["ok"] else 1)
