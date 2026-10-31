"""Check that reference-forecaster outputs do not depend on the library environment:
recompute seed-101 forecast metrics and compare with the rows stored by the original build."""
import json, os, sys
ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "experiments"))
from prism_repro.config import PipelineConfig
from prism_repro.experiment import TraceBundle
from prism_repro.metrics import coverage, mape, pinball
import numpy as np
stored = [json.loads(l) for l in open(os.path.join(ROOT, "results/raw/E8/rows.jsonl"))]
stored = {(r["scenario"], r["forecaster"]): r for r in stored if r.get("kind") == "forecast" and r["seed"] == 101}
b = TraceBundle(101, PipelineConfig(), forecasters=("gbm", "seasonal_naive", "last5max", "ewma"))
import run_experiments as RE
for (sc, name), r0 in sorted(stored.items()):
    fr = RE.forecast_row(RE.Store("E8_check"), 101, sc, name, b.forecasts[(sc, "test", name)])
    print(f"{sc:11s} {name:15s} mape {r0['mape_median']:.6f} vs {fr['mape_median']:.6f}  cov99 {r0['cov99_raw']:.6f} vs {fr['cov99_raw']:.6f}  identical={abs(r0['mape_median']-fr['mape_median'])<1e-9 and abs(r0['pinball_90']-fr['pinball_90'])<1e-9}")
