#!/usr/bin/env python3
"""Re-simulate a deterministic subset of stored E1 runs with the CURRENT code and compare
with the stored rows. Exact equality is expected (same seeds, same draws). Usage:
  python scripts/check_reproducibility.py [--seed 101] [--scenario stationary]"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, run_policy  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=101)
ap.add_argument("--scenario", default="stationary")
a = ap.parse_args()
stored = {}
for l in open(os.path.join(ROOT, "results", "raw", "E1", "rows.jsonl")):
    r = json.loads(l)
    if r["seed"] == a.seed and r["week"] == "test" and r["scenario"] == a.scenario:
        stored[r["label"]] = r
labels = ["OnDemand", "Static-95", "Reactive-0.6", "PredHead-1.3", "QuantProv_q90-1.0", "PRISM-0.05"]
b = TraceBundle(a.seed, PipelineConfig(), scenarios=("stationary", a.scenario) if a.scenario != "stationary" else ("stationary",))
out, ok = [], True
for lab in labels:
    s0 = stored[lab]
    s1 = run_policy(b, a.scenario, "test", s0["spec"])["summary"]
    same = all(s0[k] == s1[k] for k in ("cost", "violating_window_rate", "record_attainment", "late_records"))
    ok &= same
    out.append(dict(label=lab, stored_source=s0["source_sha256"][:12], cost_stored=s0["cost"], cost_now=s1["cost"],
                    viol_stored=s0["violating_window_rate"], viol_now=s1["violating_window_rate"], identical=same))
    print(f"{lab:20s} identical={same} cost {s0['cost']:.6f} vs {s1['cost']:.6f}")
os.makedirs(os.path.join(ROOT, "results", "verification"), exist_ok=True)
json.dump(dict(seed=a.seed, scenario=a.scenario, all_identical=ok, runs=out),
          open(os.path.join(ROOT, "results", "verification", f"reproducibility_seed{a.seed}_{a.scenario}.json"), "w"), indent=1)
print("ALL IDENTICAL" if ok else "DIFFERENCES FOUND")
sys.exit(0 if ok else 1)
