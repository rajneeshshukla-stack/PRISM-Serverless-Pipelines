#!/usr/bin/env python3
"""R1 (post hoc, added 31 Oct 2026): replay of REAL production arrival traces.

Five functions of the Huawei Private 2023 trace (requests per minute, days 28-55 =
28 consecutive days; CC BY 4.0, https://github.com/sir-lab/data-release), thinned
binomially to a mean of 600 pipeline executions per minute (data/real/make_csvs.py).
Each trace replaces the synthetic generator; everything else is the main protocol
(Section V): forecaster trained on days 1-14, every family tuned on days 15-21 by the
Section V-C rule over the full E1 grids, the selection frozen and applied to days 22-28.
No scheduled trigger minutes are assumed known (trigger feature constant zero).
Simulator, prices, latency model, and policies are unchanged (fast simulator).

Usage: python experiments/run_real_traces.py [--fns 150 72 60 183 42]
"""
from __future__ import annotations
import argparse, os, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from prism_repro.config import PipelineConfig, PrismConfig  # noqa: E402
from prism_repro.experiment import TraceBundle  # noqa: E402
from prism_repro.trace_io import load_minute_csv  # noqa: E402
from prism_repro.workload import MIN_PER_DAY  # noqa: E402
import run_experiments as RE  # noqa: E402

SEED_OF = {"150": 201, "72": 202, "60": 203, "183": 204, "42": 205}  # seeds of the simulator draws


class RealTraceBundle(TraceBundle):
    def __init__(self, fn: str, cfg: PipelineConfig):
        counts = load_minute_csv(os.path.join(ROOT, "data", "real", f"huawei_fn{fn}.csv"))[:28 * MIN_PER_DAY]
        self.seed, self.cfg = SEED_OF[fn], cfg
        self.wp = None
        self.scenarios = ("real",)
        self.traces = {"real": {"counts": counts, "trigger_minutes_known": np.array([], dtype=int)}}
        self.trigger_minutes = np.array([], dtype=int)
        self.pc = PrismConfig()
        self.fc_names = ("gbm",)
        self._draws, self._khist, self.forecasts, self.forecast_quality, self.models = {}, {}, {}, {}, {}
        self._train_forecasters()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fns", nargs="+", default=list(SEED_OF))
    a = ap.parse_args()
    st = RE.Store("R1")
    for fn in a.fns:
        seed = SEED_OF[fn]
        if st.done(seed):
            print(f"[R1] fn {fn} done, skipping", flush=True)
            continue
        t = time.time()
        b = RealTraceBundle(fn, PipelineConfig())
        rows, arrays = [], {}
        # forecast quality on the test week
        f = b.forecasts[("real", "test", "gbm")]
        fr = RE.forecast_row(st, seed, "real", "gbm", f)
        fr.update(kind="forecast", synthetic=False, trace=f"huawei_fn{fn}")
        rows.append(fr)
        for wk in ("val", "test"):
            for spec in RE.grid_specs():
                r = RE.run_one(st, b, "real", wk, spec, rows, arrays)
                r.update(synthetic=False, trace=f"huawei_fn{fn}")
            print(f"[R1] fn {fn} {wk}: {len(rows)} rows, {time.time()-t:.0f}s", flush=True)
        st.save(seed, rows, arrays)


if __name__ == "__main__":
    main()
