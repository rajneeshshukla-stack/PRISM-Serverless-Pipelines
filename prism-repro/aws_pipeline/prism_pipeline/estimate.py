"""Cost and duration estimate for the smallest live test. Every input is an explicit assumption, listed in the output.

PRICES ARE UNVERIFIED: they are the published us-east-1/us-east-2 list prices as known to the preparer (x86 Lambda,
Step Functions Express, CloudWatch Logs standard ingestion), not checked against the live price list in this pass.
Check them for us-east-2 before approval and pass --price-* to recompute. Free tier is not assumed.
Duration of a stage at memory m, three bounds as in the measurement harness (the maximum is the planning figure):
  cpu_linear d(m) = d1024*1024/m;  vcpu_plateau d(m) = d1024*1024/min(m, 1769);  eq2_model d(m) = d1024*(0.5+0.5*1024/m)
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence

WARM_MEAN_1024 = {"ingest": 0.8, "transform": 4.0, "aggregate": 2.5, "load": 1.2}
PRICES_UNVERIFIED = {"lambda_gb_s": 0.0000166667, "lambda_request": 0.20 / 1e6, "sfn_request": 1.00 / 1e6,
                     "sfn_gb_s": 0.00001667, "logs_ingest_gb": 0.50, "logs_storage_gb_month": 0.03,
                     "lambda_pc_gb_s": 0.0000041667}   # provisioned concurrency, per configured GB-s (x86; UNVERIFIED)


def _d(d1024, m, model):
    if model == "cpu_linear":
        return d1024 * 1024 / m
    if model == "vcpu_plateau":
        return d1024 * 1024 / min(m, 1769)
    if model == "eq2_model":
        return d1024 * (0.5 + 0.5 * 1024 / m)
    raise ValueError(model)


def estimate(n_records: int, schedule_mb: Sequence[int], smoke: int = 3, calib_invocations_per_stage: int = 20,
             init_s: float = 1.0, cold_per_arm: int = 4 * 8, client_overhead_s: float = 0.15,
             transition_s: float = 0.1, log_bytes_per_invocation: int = 1500,
             prices: Optional[Dict[str, float]] = None) -> dict:
    """Two arms of n_records each (baseline on demand at 1024 MB; adapter arm on the memory schedule, records spread
    evenly over its epochs), a smoke test, and calibration. init_s: assumed INIT per cold start, billed as duration
    (AWS bills the INIT phase of on-demand functions); cold_per_arm: up to 8 new environments per stage per reset or
    memory change."""
    p = dict(PRICES_UNVERIFIED, **(prices or {}))
    w = WARM_MEAN_1024
    out = {"assumptions": {"n_records_per_arm": n_records, "schedule_mb": list(schedule_mb), "smoke_records": smoke,
                           "calibration_invocations_per_stage_max": calib_invocations_per_stage,
                           "init_s_per_cold_start": init_s, "cold_starts_per_reset": cold_per_arm,
                           "client_overhead_s": client_overhead_s, "transition_s": transition_s,
                           "prices": p, "prices_status": "UNVERIFIED list prices; check us-east-2 before approval",
                           "free_tier": "not assumed"}, "models": {}}
    changes = 1 + sum(1 for a, b in zip(schedule_mb, schedule_mb[1:]) if a != b)
    n_inv = 4 * (2 * n_records + smoke) + 4 * calib_invocations_per_stage
    n_exec = 2 * n_records + smoke
    for model in ("cpu_linear", "vcpu_plateau", "eq2_model"):
        per_rec = {m: sum(_d(w[s], m, model) * m / 1024 for s in w) for m in set(schedule_mb) | {1024}}
        e2e = {m: sum(_d(w[s], m, model) for s in w) + 4 * transition_s + client_overhead_s for m in per_rec}
        gbs_base = n_records * per_rec[1024]
        gbs_sched = sum(n_records / len(schedule_mb) * per_rec[m] for m in schedule_mb)
        gbs_smoke = smoke * per_rec[1024]
        gbs_cal = calib_invocations_per_stage * sum(w.values())           # upper: every probe at the target
        colds = cold_per_arm * (1 + changes) + 4 * 2                       # arms + calibration/smoke first calls
        gbs_init = colds * init_s * max(schedule_mb) / 1024
        gbs = gbs_base + gbs_sched + gbs_smoke + gbs_cal + gbs_init
        sfn_gbs = sum(0.0625 * math.ceil(e2e[1024] * 10) / 10 for _ in range(n_records + smoke)) + \
            sum(0.0625 * math.ceil(e2e[m] * 10) / 10 * n_records / len(schedule_mb) for m in schedule_mb)
        logs_gb = n_inv * log_bytes_per_invocation / 1e9
        cost = {"lambda_duration": gbs * p["lambda_gb_s"], "lambda_requests": n_inv * p["lambda_request"],
                "sfn_requests": n_exec * p["sfn_request"], "sfn_duration": sfn_gbs * p["sfn_gb_s"],
                "logs_ingest": logs_gb * p["logs_ingest_gb"],
                "logs_storage_7d": logs_gb * p["logs_storage_gb_month"] * 7 / 30}
        out["models"][model] = {"lambda_gb_s": round(gbs, 1), "lambda_invocations": n_inv, "sfn_executions": n_exec,
                                "e2e_s_by_memory": {m: round(v, 2) for m, v in sorted(e2e.items())},
                                "cost_usd": {k: round(v, 5) for k, v in cost.items()},
                                "total_usd": round(sum(cost.values()), 4)}
    worst = max(m["total_usd"] for m in out["models"].values())
    out["planning_total_usd_upper"] = worst
    out["suggested_budget_alarm_usd"] = 1.0
    return out
