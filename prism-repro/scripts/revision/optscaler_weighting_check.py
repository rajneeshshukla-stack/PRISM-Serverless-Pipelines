#!/usr/bin/env python3
"""POST HOC: compare the equal-weight MLE ratio (A4) with the y^2-weighted least-squares ratio that unclipped OLR with
x proportional to y tends to (sum y K / sum y^2), on pre-validation history, per stage; and the ratio by load decile.
usage: venv/Scripts/python scripts/revision/optscaler_weighting_check.py <out json> <seed>"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "src")); sys.path.insert(0, HERE)
from prism_repro.config import PipelineConfig
from prism_repro.experiment import TraceBundle
import optscaler_policy as op
seed = int(sys.argv[2]); b = TraceBundle(seed, PipelineConfig()); ctx = b.context("stationary", "val")
ws = ctx.week_start; y = ctx.counts[:ws].astype(float); K = ctx.K_hist_default[:ws]; sel = y > 0
out = dict(seed=seed, stages=[])
q = np.quantile(y[sel], np.linspace(0, 1, 11))
for s in range(ctx.cfg.n_stages):
    w_mle, sig = op.mle_ratio(K[:, s], y)
    w_ls = float((y[sel] * K[sel, s]).sum() / (y[sel] ** 2).sum())
    dec = [float(np.mean(K[sel, s][(y[sel] >= q[i]) & (y[sel] <= q[i + 1])] / y[sel][(y[sel] >= q[i]) & (y[sel] <= q[i + 1])])) for i in range(10)]
    out["stages"].append(dict(stage=s, w_mle=w_mle, sigma=sig, w_ls_y2=w_ls, ratio_ls_over_mle=w_ls / w_mle, mean_ratio_by_load_decile=dec))
out["load_deciles"] = q.tolist()
json.dump(out, open(sys.argv[1], "w"), indent=1)
for st in out["stages"]: print(st["stage"], "w_mle %.4f sigma %.4f w_ls %.4f ls/mle %.2f" % (st["w_mle"], st["sigma"], st["w_ls_y2"], st["ratio_ls_over_mle"]), "deciles", [round(x, 4) for x in st["mean_ratio_by_load_decile"]])
print("y deciles", [round(x) for x in q])
