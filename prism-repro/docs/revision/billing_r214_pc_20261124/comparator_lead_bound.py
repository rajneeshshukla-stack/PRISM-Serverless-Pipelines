#!/usr/bin/env python3
"""R2.14(a), the open part: the activation-lead bound for the comparators and its effect on the paired comparisons.
EXPLORATORY; no simulation. Input: completed E1 rows and arrays as the current code wrote them (e.g. the R3.6 release
inputs, linux/E1 or windows/E1). Every provisioning family is taken at its validation-selected setting (Section V-C rule,
experiment.select_by_rule), as in Table V. For each test week:
  - the simulator's capacity GB-s are checked against AWS's rule (pc_billing_rules.capacity_gb_s, both readings of U3),
    with the enabled-period mapping of capacity_consistency.py;
  - lead bound (ASSUMPTION, not an AWS rule; as capacity_consistency.py): every increase of P is enabled one epoch
    (5 minutes) early, so it is billed for one extra epoch at the capacity price.
Reported: each family's added share of weekly cost, and Table VI-style paired differences (PRISM minus comparator, cost
%) without and with the bound applied to both sides. Compliance is unchanged by construction (the bound adds cost only).
usage (from prism-repro/): python docs/revision/billing_r214_pc_20261124/comparator_lead_bound.py <rows dir with E1/> <out.json>
"""
import json
import math
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from pc_billing_rules import capacity_gb_s  # noqa: E402
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import select_by_rule  # noqa: E402

E = 5
SEEDS = (101, 102, 103, 104, 105)
SCEN = ("stationary", "growth", "bursty", "new_spike")
FAMILIES = ("PRISM_EB", "QuantProv_q90", "QuantProv_q99", "PredHead", "PredHead+hyst", "Reactive", "Static", "Scheduled")
price = PipelineConfig().prices.pc


def periods(P_s, mem):
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


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)))


def main(rows_dir, out):
    rows = [json.loads(l) for l in open(os.path.join(rows_dir, "E1", "rows.jsonl"))]
    res = {}
    all_equal = True
    for seed in SEEDS:
        arr = np.load(os.path.join(rows_dir, "E1", f"arrays_seed{seed}.npz"))
        for fam in FAMILIES:
            val = [r for r in rows if r["seed"] == seed and r["week"] == "val" and r["status"] == "ok" and r["policy"] == fam]
            sel = select_by_rule(val)
            key = json.dumps(sel["spec"], sort_keys=True)
            for sc in SCEN:
                r = [x for x in rows if x["seed"] == seed and x["week"] == "test" and x["scenario"] == sc
                     and x["policy"] == fam and json.dumps(x["spec"], sort_keys=True) == key]
                assert len(r) == 1, (seed, fam, sc, len(r))
                r = r[0]
                P = arr[r["run_id"] + "::P_epoch"].astype(float)
                mem = arr[r["run_id"] + "::mem_epoch"].astype(int)
                g = mem / 1024.0
                sim = float((P * g[:, None] * E * 60.0).sum())
                aws_p = aws_s = 0.0
                for s in range(P.shape[1]):
                    for per in periods(P[:, s], mem):
                        segs = [(a, b, c) for a, b, c, _ in per]
                        aws_p += capacity_gb_s(segs, per[0][3], "period")
                        aws_s += capacity_gb_s(segs, per[0][3], "segment")
                eq = abs(sim - aws_p) < 1e-6 * max(1.0, sim) and abs(sim - aws_s) < 1e-6 * max(1.0, sim)
                all_equal &= eq
                inc = np.maximum(np.diff(np.vstack([np.zeros((1, P.shape[1])), P]), axis=0), 0)
                lead_usd = float((inc * g[:, None] * E * 60.0).sum()) * price
                res[(seed, fam, sc)] = dict(spec=sel["spec"], cost=r["cost"], cost_pc=r["cost_pc"], lead_usd=lead_usd,
                                            viol=r["violating_window_rate"], sim_equals_aws=eq,
                                            cost_pc_check=abs(sim * price - r["cost_pc"]) <= 1e-6 * max(1.0, r["cost_pc"]))
    fam_share = {}
    for fam in FAMILIES:
        sh = [res[(s, fam, sc)]["lead_usd"] / res[(s, fam, sc)]["cost"] * 100 for s in SEEDS for sc in SCEN]
        fam_share[fam] = dict(min=min(sh), max=max(sh), mean=float(np.mean(sh)))
    paired = {}
    for comp in FAMILIES[1:]:
        for sc in SCEN:
            base = [100 * (res[(s, "PRISM_EB", sc)]["cost"] - res[(s, comp, sc)]["cost"]) / res[(s, comp, sc)]["cost"] for s in SEEDS]
            adj = [100 * ((res[(s, "PRISM_EB", sc)]["cost"] + res[(s, "PRISM_EB", sc)]["lead_usd"])
                          - (res[(s, comp, sc)]["cost"] + res[(s, comp, sc)]["lead_usd"]))
                   / (res[(s, comp, sc)]["cost"] + res[(s, comp, sc)]["lead_usd"]) for s in SEEDS]
            paired[f"{comp}|{sc}"] = dict(base=float(np.mean(base)), base_hw=hw(base), adj=float(np.mean(adj)), adj_hw=hw(adj),
                                          change=float(np.mean(adj) - np.mean(base)),
                                          base_cheaper=int(sum(x < 0 for x in base)), adj_cheaper=int(sum(x < 0 for x in adj)),
                                          sign_change=bool((np.mean(base) < 0) != (np.mean(adj) < 0)),
                                          excludes0_base=bool(abs(np.mean(base)) > hw(base)),
                                          excludes0_adj=bool(abs(np.mean(adj)) > hw(adj)))
    o = dict(label="EXPLORATORY; completed E1 rows, validation-selected settings, development traces 101-105, test weeks; "
                   "no simulation; lead bound is an ASSUMPTION (each increase enabled one epoch early)",
             rows_dir=os.path.basename(os.path.normpath(rows_dir)),
             simulator_capacity_equals_aws_rule_all=bool(all_equal),
             cost_pc_reproduced_all=bool(all(v["cost_pc_check"] for v in res.values())),
             lead_share_of_weekly_cost_pct=fam_share, paired_prism_minus_comparator_cost_pct=paired,
             selected={f"{s}|{fam}": res[(s, fam, "stationary")]["spec"].get("param") for s in SEEDS for fam in FAMILIES})
    json.dump(o, open(out, "w", encoding="utf-8", newline="\n"), indent=1)
    print("simulator capacity == AWS rule (all runs):", all_equal, "| cost_pc reproduced:", o["cost_pc_reproduced_all"])
    for fam, v in fam_share.items():
        print(f"  {fam:14s} lead bound share of weekly cost: {v['min']:.2f}-{v['max']:.2f}% (mean {v['mean']:.2f}%)")
    for k, v in paired.items():
        print(f"  PRISM - {k:28s} {v['base']:+6.2f} +/- {v['base_hw']:.2f} -> {v['adj']:+6.2f} +/- {v['adj_hw']:.2f} "
              f"(change {v['change']:+.2f}; cheaper {v['base_cheaper']}->{v['adj_cheaper']}; sign change {v['sign_change']}; "
              f"excl0 {v['excludes0_base']}->{v['excludes0_adj']})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
