#!/usr/bin/env python3
"""R2.14(a): the verified billing components applied together to saved fast-simulator records (E1 rows, as written by the
current code), as a separately labelled revised estimate. The historical tables are not changed. EXPLORATORY,
PRE-CALIBRATION.

Component map (each simulator term maps to exactly one AWS charge; checked per row: the terms sum to `cost`):
  cost_pc   capacity, P x memory x 60 s x PC price         = AWS "amount of concurrency you configure" (verified equal to
                                                            AWS's enabling-to-disabling rule on these schedules)
  cost_pcd  invocations served by PC, n_pc x D x GB x PCD   = AWS PC compute; the documented rule rounds each duration up
                                                            to 1 ms (U4, not measured)
  cost_od   overflow invocations, n_od x D x GB x OD price  = AWS on-demand duration; verified rule floor(D + Init) + 1 ms
  cost_init cold starts x init x GB x OD price               = AWS on-demand Init (billed; verified)
  cost_req  invocations x request price                     = AWS requests
  not charged: initialisation of PC environments (U1) and recycling (U2): no AWS rule; left open.
No term is counted twice: PC capacity and PC compute are separate AWS charges; an invocation is either on PC (cost_pcd)
or overflow (cost_od, plus cost_init if cold); Init is billed only for on-demand cold starts.

Revised estimate per row (records hold totals, not per-invocation durations):
  rounding: each invocation's duration is rounded up to the next ms; for continuous durations the expected increment is
  0.5 ms (mid) and at most 1 ms (upper). Counts: invocations = cost_req / REQ; n_od = overflow_share x invocations;
  n_pc = invocations - n_od. Memory: GB = 1 for the share of minutes below 2048 MB; for the share at >= 2048 MB the upper
  bound uses 3008 MB (the largest option) and the mid estimate 2048 MB.
  lead (optional, an ASSUMPTION, not an AWS rule): comparator_lead_bound.py's one-epoch-early activation bound.
usage (from prism-repro/): python docs/revision/billing_r214_pc_20261124/integrated_estimate.py <rows dir with E1/> <lead json> <out.json>
"""
import json
import math
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import select_by_rule  # noqa: E402

PR = PipelineConfig().prices
SEEDS = (101, 102, 103, 104, 105)
SCEN = ("stationary", "growth", "bursty", "new_spike")
FAMILIES = ("PRISM_EB", "QuantProv_q90", "QuantProv_q99", "PredHead", "PredHead+hyst", "Reactive", "Static", "Scheduled")


def decomposition_gap(row):
    return row["cost"] - (row["cost_pc"] + row["cost_pcd"] + row["cost_od"] + row["cost_init"] + row["cost_req"])


def rounding_increment_usd(row, ms, upper):
    """USD added by rounding every invocation's duration up by `ms` milliseconds (0.5 expected, 1.0 bound)."""
    inv = row["cost_req"] / PR.req
    n_od = row["overflow_share"] * inv
    n_pc = inv - n_od
    share = float(row.get("share_mem_ge_2048", 0.0))
    g = (1.0 - share) * 1.0 + share * ((3008 if upper else 2048) / 1024.0)
    return ms / 1000.0 * g * (n_pc * PR.pcd + n_od * PR.od)


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)))


def main(rows_dir, lead_json, out):
    rows = [json.loads(l) for l in open(os.path.join(rows_dir, "E1", "rows.jsonl"))]
    lead = json.load(open(lead_json, encoding="utf-8")) if lead_json != "-" else None
    gaps = [abs(decomposition_gap(r)) / r["cost"] for r in rows if r["status"] == "ok"]
    sel = {}
    for seed in SEEDS:
        for fam in FAMILIES:
            val = [r for r in rows if r["seed"] == seed and r["week"] == "val" and r["status"] == "ok" and r["policy"] == fam]
            key = json.dumps(select_by_rule(val)["spec"], sort_keys=True)
            for sc in SCEN:
                r = [x for x in rows if x["seed"] == seed and x["week"] == "test" and x["scenario"] == sc
                     and x["policy"] == fam and json.dumps(x["spec"], sort_keys=True) == key]
                assert len(r) == 1
                sel[(seed, fam, sc)] = r[0]
    variants = {"as_run": lambda r: r["cost"],
                "rounding_mid": lambda r: r["cost"] + rounding_increment_usd(r, 0.5, False),
                "rounding_upper": lambda r: r["cost"] + rounding_increment_usd(r, 1.0, True)}
    share = {v: [] for v in variants}
    for r in sel.values():
        for v, f in variants.items():
            share[v].append((f(r) - r["cost"]) / r["cost"] * 100)
    paired = {}
    for comp in FAMILIES[1:]:
        for sc in SCEN:
            e = {}
            for v, f in variants.items():
                d = [100 * (f(sel[(s, "PRISM_EB", sc)]) - f(sel[(s, comp, sc)])) / f(sel[(s, comp, sc)]) for s in SEEDS]
                e[v] = dict(mean=float(np.mean(d)), hw=hw(d))
            if lead is not None:
                lp = lead["paired_prism_minus_comparator_cost_pct"][f"{comp}|{sc}"]
                e["lead_bound_only"] = dict(mean=lp["adj"], hw=lp["adj_hw"])
            e["max_shift_rounding_points"] = max(abs(e["rounding_mid"]["mean"] - e["as_run"]["mean"]),
                                                 abs(e["rounding_upper"]["mean"] - e["as_run"]["mean"]))
            e["excl0"] = {v: bool(abs(x["mean"]) > x["hw"]) for v, x in e.items() if isinstance(x, dict) and "hw" in x}
            paired[f"{comp}|{sc}"] = e
    o = dict(label="EXPLORATORY revised estimate on saved E1 rows (validation-selected settings, development traces, test "
                   "weeks); PRE-CALIBRATION; historical tables unchanged",
             rows_dir=os.path.basename(os.path.normpath(rows_dir)),
             decomposition_max_relative_gap=max(gaps), rows_checked=len(gaps),
             cost_increase_pct={v: dict(min=min(x), max=max(x), mean=float(np.mean(x))) for v, x in share.items()},
             max_paired_shift_rounding_points=max(e["max_shift_rounding_points"] for e in paired.values()),
             classification_changes_rounding=[k for k, e in paired.items()
                                              if e["excl0"]["as_run"] != e["excl0"]["rounding_upper"]
                                              or e["excl0"]["as_run"] != e["excl0"]["rounding_mid"]],
             paired=paired)
    json.dump(o, open(out, "w", encoding="utf-8", newline="\n"), indent=1)
    print(json.dumps({k: v for k, v in o.items() if k != "paired"}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
