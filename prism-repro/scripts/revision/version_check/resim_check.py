#!/usr/bin/env python3
"""Version-sensitivity check (post hoc; added in the Stage 2 correction of the manuscript).

Re-simulates stored E1 test-week runs with the current code in the CURRENT software environment
and compares each with its stored row. Runs without a learned forecaster (OnDemand, Static,
Scheduled, Reactive) are expected to be bit-identical in any environment; forecast-driven runs
(PredHead, PredHead+S, QuantProv, PRISM) are bit-identical only in the pinned environment of
requirements.txt, because the gradient-boosted forecaster changes with the scikit-learn release.

Usage (from the package root):
  python scripts/revision/version_check/resim_check.py --seeds 101,102,103,104 --scenario new_spike
Writes resim_<scenario>_<seeds>.json next to this script and prints the summary used in
Supplementary Section S1.
"""
import argparse, collections, json, os, platform, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, run_policy  # noqa: E402

NON_FORECAST = {"OnDemand", "Static", "Scheduled", "Reactive"}
KEYS = ("cost", "violating_window_rate", "record_attainment", "late_records")

ap = argparse.ArgumentParser()
ap.add_argument("--seeds", default="101,102,103,104")
ap.add_argument("--scenario", default="new_spike")
a = ap.parse_args()
seeds = [int(s) for s in a.seeds.split(",")]
rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "E1", "rows.jsonl"))]
out = []
for seed in seeds:
    b = TraceBundle(seed, PipelineConfig(),
                    scenarios=("stationary", a.scenario) if a.scenario != "stationary" else ("stationary",))
    for r in (r for r in rows if r["seed"] == seed and r["week"] == "test" and r["scenario"] == a.scenario):
        s1 = run_policy(b, a.scenario, "test", r["spec"])["summary"]
        out.append(dict(seed=seed, sha=r["source_sha256"][:7], label=r["label"], family=r["spec"].get("family"),
                        identical=all(r[k] == s1[k] for k in KEYS),
                        dcost_pct=100 * (s1["cost"] / r["cost"] - 1),
                        dviol_pp=100 * (s1["violating_window_rate"] - r["violating_window_rate"])))
dst = os.path.join(HERE, f"resim_{a.scenario}_{'-'.join(map(str, seeds))}.json")
json.dump(out, open(dst, "w"), indent=0)

nf = [o for o in out if o["family"] in NON_FORECAST]
fc = [o for o in out if o["family"] not in NON_FORECAST]
dc = np.abs([o["dcost_pct"] for o in fc]); dv = np.abs([o["dviol_pp"] for o in fc])
import sklearn, scipy, pandas  # noqa: E402
print(f"environment: Python {platform.python_version()}, numpy {np.__version__}, scipy {scipy.__version__}, "
      f"pandas {pandas.__version__}, scikit-learn {sklearn.__version__}")
print(f"runs without a learned forecaster: {len(nf)}, bit-identical: {sum(o['identical'] for o in nf)}")
if fc:
    print(f"forecast-driven runs: {len(fc)}, bit-identical: {sum(o['identical'] for o in fc)}; "
          f"|cost change| median {np.median(dc):.3f}%, max {dc.max():.3f}%; "
          f"violating-window rate changed in {int((dv > 0).sum())} runs, by at most {dv.max():.3f} points")
print(f"written: {os.path.relpath(dst, ROOT)}")
