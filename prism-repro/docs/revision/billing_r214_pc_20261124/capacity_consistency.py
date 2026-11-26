#!/usr/bin/env python3
"""R2.14(a): does the simulator's provisioned-capacity billing (P x memory x 60 s per minute, simulator.py) agree with
AWS's stated rule (billed from enabling to disabling, rounded up to five minutes; pc_billing_rules.capacity_gb_s) on
PRISM's actual schedules? And what would a lead time for activation cost, as a bound? No simulation; stored E1
schedules of the E12-selected PRISM label, development traces 101-105, the four test scenarios. EXPLORATORY.

Mapping (stated): per stage, each maximal run of consecutive 5-minute epochs with P > 0 at one memory size is one
enabled period (a memory change needs a new published version, so it ends the period); within it, P changes at epoch
boundaries are amount changes.
Activation-lead bound (ASSUMPTION, not an AWS rule): AWS says provisioned concurrency "doesn't come online
immediately", with "a minute or two of preparation". If the operator therefore enables each increase one epoch (5
minutes) early so that it is READY when the epoch starts, every increase of P is billed for one extra epoch.

usage (from prism-repro/): venv/Scripts/python docs/revision/billing_r214_pc_20261124/capacity_consistency.py <out.json>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from pc_billing_rules import capacity_gb_s  # noqa: E402
from prism_repro.config import PipelineConfig  # noqa: E402

E = 5
SCEN = ("stationary", "growth", "bursty", "new_spike")
price = PipelineConfig().prices.pc


def periods(P_s, mem):
    """Enabled periods for one stage: lists of (start_s, end_s, concurrency) segments."""
    out, cur = [], []
    for k, (p, m) in enumerate(zip(P_s, mem)):
        a, b = k * E * 60.0, (k + 1) * E * 60.0
        if p > 0 and cur and cur[-1][3] == m:
            cur.append((a, b, float(p), m))
        else:
            if cur:
                out.append(cur)
            cur = [(a, b, float(p), m)] if p > 0 else []
    if cur:
        out.append(cur)
    return out


rows = []
for seed in (101, 102, 103, 104, 105):
    lab = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "E12", f"E12_seed{seed}.jsonl"))
           if json.loads(l)["family"] == "PRISM" and json.loads(l)["week"] == "test" and json.loads(l).get("selected")][0]["label"]
    arr = np.load(os.path.join(ROOT, "results", "raw", "E1", f"arrays_seed{seed}.npz"))
    for sc in SCEN:
        k = f"E1|{seed}|{sc}|test|{lab}|"
        P, mem = arr[k + "::P_epoch"].astype(float), arr[k + "::mem_epoch"].astype(int)
        g = mem / 1024.0
        sim = float((P * g[:, None] * E * 60.0).sum())          # simulator: per minute, 60 s x P x GB
        aws_p = aws_s = 0.0
        for s in range(P.shape[1]):
            for per in periods(P[:, s], mem):
                segs = [(a, b, c) for a, b, c, _ in per]
                aws_p += capacity_gb_s(segs, per[0][3], "period")
                aws_s += capacity_gb_s(segs, per[0][3], "segment")
        inc = np.maximum(np.diff(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0), 0)
        lead = float((inc * g[:, None] * E * 60.0).sum())
        rows.append(dict(seed=seed, scenario=sc, label=lab, sim_gb_s=sim, aws_period_gb_s=aws_p, aws_segment_gb_s=aws_s,
                         lead_bound_gb_s=lead, lead_bound_share_of_capacity=lead / sim if sim else 0.0,
                         lead_bound_usd=lead * price))
eq = all(abs(r["sim_gb_s"] - r["aws_period_gb_s"]) < 1e-6 and abs(r["sim_gb_s"] - r["aws_segment_gb_s"]) < 1e-6
         for r in rows)
sh = [r["lead_bound_share_of_capacity"] for r in rows]
out = dict(label="EXPLORATORY; stored E1 schedules (E12-selected PRISM), development traces, test weeks; no simulation",
           weeks=len(rows), simulator_equals_aws_rule_both_readings=eq,
           lead_bound_share_of_capacity=dict(min=min(sh), max=max(sh), mean=float(np.mean(sh))), rows=rows)
json.dump(out, open(sys.argv[1], "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
