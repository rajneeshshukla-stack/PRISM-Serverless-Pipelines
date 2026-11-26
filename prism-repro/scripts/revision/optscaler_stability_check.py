#!/usr/bin/env python3
"""Stability check of the OptScaler rows used for reporting (docs/revision/optscaler_r32_20261124): per trace, scenario
and stage, the range of w_k / w0 over the week and the epochs with P = 0. Rerun the same test weeks with the policy
traced; costs must equal rows.jsonl exactly. usage: venv/Scripts/python scripts/revision/optscaler_stability_check.py <out dir>"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "src")); sys.path.insert(0, HERE)
from prism_repro.config import PipelineConfig
from prism_repro.experiment import TraceBundle
from prism_repro.simulator import simulate
from prism_repro.workload import MAIN_SCENARIOS
import optscaler_policy as op

class T(op.OptScaler):
    def prepare(self, ctx):
        super().prepare(ctx); self.ws = []
    def decide(self, k, tel):
        P, m = super().decide(k, tel); self.ws.append((self.w / np.where(self.w0 > 0, self.w0, 1)).copy()); self.Ps = getattr(self, "Ps", []) + [P.copy()]; return P, m

out = sys.argv[1]
rows = {json.loads(l)["seed"]: json.loads(l) for l in open(os.path.join(out, "rows.jsonl"))}
res = []
for seed in sorted(rows):
    b = TraceBundle(seed, PipelineConfig())
    for sc in MAIN_SCENARIOS:
        pol = T(op.C_STAR_PUBLISHED)
        s = simulate(b.context(sc, "test"), pol)["summary"]
        r = np.array(pol.ws); P = np.array(pol.Ps)
        ref = rows[seed]["test"][f"published|{sc}"]["cost"]
        res.append(dict(seed=seed, scenario=sc, cost=s["cost"], cost_equals_rows=bool(abs(s["cost"] - ref) <= 1e-9 * ref),
                        w_ratio_min=float(r.min()), w_ratio_max=float(r.max()), epochs_P_zero=int((P == 0).sum())))
        print(res[-1], flush=True)
summary = dict(runs=len(res), all_costs_equal=bool(all(x["cost_equals_rows"] for x in res)),
               w_ratio_min=min(x["w_ratio_min"] for x in res), w_ratio_max=max(x["w_ratio_max"] for x in res),
               epochs_P_zero=sum(x["epochs_P_zero"] for x in res))
json.dump(dict(summary=summary, runs=res), open(os.path.join(out, "stability_published.json"), "w"), indent=1)
print(summary)
