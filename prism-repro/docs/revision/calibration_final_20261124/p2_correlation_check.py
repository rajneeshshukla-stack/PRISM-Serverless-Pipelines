#!/usr/bin/env python3
"""P2 check (24 Nov 2026): the simulator draws each stage's execution-time multiplier independently (latency.py,
lognormal_mult over (n, S)); under SPEC.md P2 one document's length drives all four stages, so the multipliers are
common to the stages of a record. This compares the warm end-to-end miss probability v_w under both readings, with
the same marginal spread (sigma 0.30, mean-one log-normal), the same overheads (0.1 s per stage, sigma 0.30) and the
stage means of each model. No simulation of policies; a direct Monte Carlo of warm latency.
usage: python p2_correlation_check.py <prism-repro root with src/> <out.json>"""
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.latency import lognormal_mult, stage_means  # noqa: E402

FAC = tuple((int(m), tuple(f)) for m, f in json.load(open(os.path.join(
    ROOT, "..", "..", "..", "docs", "revision", "calibration_20261124", "exec_factor_measured.json")))["exec_factor_measured"]) \
    if os.path.exists(os.path.join(ROOT, "..", "..", "..", "docs", "revision", "calibration_20261124")) else None


def vw(cfg, m, common, n=400_000, seed=20261124):
    rng = np.random.default_rng([seed, int(m)])
    S = cfg.n_stages
    d = stage_means(cfg, m)
    if common:
        X = np.repeat(lognormal_mult(rng.standard_normal((n, 1)), cfg.exec_shape), S, axis=1)
    else:
        X = lognormal_mult(rng.standard_normal((n, S)), cfg.exec_shape)
    Y = cfg.overhead_mean * lognormal_mult(rng.standard_normal((n, S)), cfg.overhead_shape)
    lat = (X * d).sum(1) + Y.sum(1)
    return float(np.mean(lat > cfg.deadline)), float(np.quantile(lat, 0.99))


def main(out):
    res = {}
    models = {"legacy_eq2": {}}
    if FAC:
        models["measured"] = dict(exec_scaling="measured", exec_factor_measured=FAC)
    for name, over in models.items():
        for dl in (14.5, 13.0, 12.0):
            cfg = PipelineConfig().with_(deadline=dl, **over)
            for m in cfg.mem_options:
                ind, ind99 = vw(cfg, m, False)
                com, com99 = vw(cfg, m, True)
                res[f"{name}|{dl}|{m}"] = dict(vw_independent=ind, vw_common=com, p99_independent_s=ind99, p99_common_s=com99)
                print(f"{name:10s} {dl:5.1f} s {m:4d} MB  v_w independent {ind:.5f}  common {com:.5f}   p99 {ind99:.2f} -> {com99:.2f} s")
    json.dump(res, open(out, "w", encoding="utf-8", newline="\n"), indent=1)


if __name__ == "__main__":
    main(sys.argv[2])
