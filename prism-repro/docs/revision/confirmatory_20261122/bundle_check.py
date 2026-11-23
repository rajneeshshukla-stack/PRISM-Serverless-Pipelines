#!/usr/bin/env python3
"""Check of the driver's shared-bundle path (added after the trace-101 reproduction started).

1. bundle_task() builds the seed-101 bundle once and pickles it; the reloaded bundle must equal a freshly built one in
   every trace, forecast, pre-week history array and model prediction.
2. week_task() then runs one closed-loop week from the reloaded bundle (Reactive 0.6, validation week, the fastest
   family); the row must equal the reproduction's row for the same week in every field but wall time and process id.

usage (from prism-repro/): python docs/revision/confirmatory_20261122/bundle_check.py <tmp_out> <reproduction out dir>
"""
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "revision"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import closed_loop_confirmatory as D  # noqa: E402

TMP, REPRO = sys.argv[1], sys.argv[2]
os.makedirs(TMP, exist_ok=True)
rep = {}
info = D.bundle_task(dict(out=TMP, seed=101, cfg={}))
rep["bundle"] = info
cfg, fresh = D.build_bundle(101, {})
with open(D.bundle_file(TMP, 101, info["cfg_sha"]), "rb") as fh:
    loaded = pickle.load(fh)
eq = {}
for sc in D.MAIN:
    eq[f"counts {sc}"] = bool(np.array_equal(fresh.traces[sc]["counts"], loaded.traces[sc]["counts"]))
    eq[f"K_hist {sc}"] = bool(np.array_equal(fresh.K_hist(sc), loaded.K_hist(sc)))
for key, v in fresh.forecasts.items():
    for k2, arr in v.items():
        eq[f"forecast {key} {k2}"] = bool(np.array_equal(np.asarray(arr), np.asarray(loaded.forecasts[key][k2])))
fb = fresh._builder(fresh.traces["stationary"]["counts"], {})
ts = np.arange(fb.min_t, fb.min_t + 2000)
eq["model predictions (2000 epochs)"] = bool(np.array_equal(fresh.models["gbm"].predict(ts), loaded.models["gbm"].predict(ts)))
eq["r_mean_peak"] = fresh.r_mean_peak == loaded.r_mean_peak
rep["reloaded_equals_fresh"] = eq
t = dict(out=TMP, set="pilot101", seed=101, family="Reactive", param=0.6, week="val", scenario="validation")
row = D.week_task(t)
ref = json.load(open(D.week_file(REPRO, t), encoding="utf-8"))
skip = {"runtime_s", "pid", "finished_utc"}
diff = {k: (ref.get(k), row.get(k)) for k in set(ref) | set(row) if k not in skip and ref.get(k) != row.get(k)}
rep["week_from_loaded_bundle_equals_reproduction"] = dict(identical=not diff, differences=diff)
rep["ok"] = all(eq.values()) and not diff
json.dump(rep, open(os.path.join(TMP, "bundle_check.json"), "w", encoding="utf-8", newline="\n"), indent=1, default=str)
print(json.dumps(rep, indent=1, default=str))
sys.exit(0 if rep["ok"] else 1)
