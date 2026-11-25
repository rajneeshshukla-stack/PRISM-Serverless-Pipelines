#!/usr/bin/env python3
"""Smoke test of the opt-in measured execution-time mode, and the legacy-equality check (24 Nov 2026). EXPLORATORY,
PRE-CALIBRATION in every other constant; fast simulator; development trace 101 only (seeds 106-130 are not used).

usage: python smoke_exec_measured.py <code root: a prism-repro tree> <out.json> [--legacy-only]
  --legacy-only  run only the legacy configuration (for the pinned tree, which has no measured mode)
For each mode (legacy Eq. (2), non-scaling 0.5; measured per-size factors from exec_factor_measured.json) and each
regime (default deadline 14.5 s; short deadline 13 s, where 1024 MB cannot meet the deadline):
  - warm miss probability v_w(m) and cold miss rho(m) per memory size (latency.miss_table);
  - PRISM tuned on the validation week over GRIDS["PRISM"] by experiment.select_by_rule, then the stationary and
    new-spike test weeks; MemAdapt-q90 likewise over GRIDS["QuantProv"] (13 s only, where memory matters).
Reported per run: cost, violating-window rate, share of minutes at >= 2048 MB, memory sizes used.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import GRIDS, TraceBundle, make_policy, select_by_rule  # noqa: E402
from prism_repro.latency import miss_table  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 101
FAC = tuple((int(m), tuple(f)) for m, f in json.load(open(os.path.join(HERE, "exec_factor_measured.json")))["exec_factor_measured"])


def cfgs(legacy_only):
    out = {"legacy": {}}
    if not legacy_only:
        out["measured"] = dict(exec_scaling="measured", exec_factor_measured=FAC)
    return out


def run(b, sc, wk, spec):
    r = simulate(b.context(sc, wk), make_policy(spec))
    s, raw = r["summary"], r["raw"]
    return dict(cost=float(s["cost"]), viol=float(s["violating_window_rate"]), share_ge2048=float(s["share_mem_ge_2048"]),
                mems=sorted(int(x) for x in np.unique(raw["mem_epoch"])))


def tune(b, fam, grid, extra):
    val = []
    for p in grid:
        r = run(b, "stationary", "val", dict(family=fam, param=p, **extra))
        val.append(dict(param=p, cost=r["cost"], violating_window_rate=r["viol"], **{k: r[k] for k in ("share_ge2048", "mems")}))
    sel = select_by_rule(val)
    tests = {sc: run(b, sc, "test", dict(family=fam, param=sel["param"], **extra)) for sc in ("stationary", "new_spike")}
    return dict(selected=sel["param"], validation=val, tests=tests)


def main(out, legacy_only):
    res = {}
    for mode, over in cfgs(legacy_only).items():
        for dl in (14.5, 13.0):
            cfg = PipelineConfig().with_(deadline=dl, **over)
            mt = miss_table(cfg)
            b = TraceBundle(SEED, cfg)
            r = dict(miss_table={str(m): [float(v) for v in mt[m]] for m in cfg.mem_options},
                     PRISM=tune(b, "PRISM", GRIDS["PRISM"], {}))
            if dl == 13.0:
                r["MemAdapt_q90"] = tune(b, "MemAdapt", GRIDS["QuantProv"], {"tau_idx": 2})
            res[f"{mode}|{dl}"] = r
            print(mode, dl, "PRISM eps", r["PRISM"]["selected"],
                  {sc: (round(t["cost"], 1), round(100 * t["viol"], 2), t["mems"]) for sc, t in r["PRISM"]["tests"].items()},
                  "| MemAdapt", r.get("MemAdapt_q90", {}).get("selected"),
                  {sc: (round(t["cost"], 1), round(100 * t["viol"], 2), t["mems"]) for sc, t in r.get("MemAdapt_q90", {}).get("tests", {}).items()},
                  flush=True)
    json.dump(res, open(out, "w", encoding="utf-8", newline="\n"), indent=1)


if __name__ == "__main__":
    main(sys.argv[2], "--legacy-only" in sys.argv)
