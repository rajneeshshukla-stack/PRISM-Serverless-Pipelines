"""Runtime and cost estimate for a Design. Every input is an explicit assumption, listed in the output.

Warm duration of a stage proxy at memory m, three bounds (the maximum is reported as the planning figure):
  cpu_linear     d(m) = d1024 * 1024 / m                (CPU share proportional to memory)
  vcpu_plateau   d(m) = d1024 * 1024 / min(m, 1769)     (single-threaded work stops speeding up near one vCPU;
                                                          AWS documents one vCPU at 1,769 MB - verify before use)
  eq2_model      d(m) = d1024 * (0.5 + 0.5 * 1024 / m)  (the simulator's own Eq. (2), nonscaling 0.5)
Prices default to prism_repro.config.Prices (the manuscript's values; that module states they are NOT current
provider prices). Replace them with current regional prices before using the estimate to approve a run. The upper
cost figure assumes the INIT phase is billed like duration.
"""
from __future__ import annotations

from typing import Dict, Optional

from .design import Design

WARM_MEAN_1024 = {"ingest": 0.8, "transform": 4.0, "aggregate": 2.5, "load": 1.2}   # PipelineConfig.warm_mean_1024


def _d(d1024: float, m: int, model: str) -> float:
    if model == "cpu_linear":
        return d1024 * 1024 / m
    if model == "vcpu_plateau":
        return d1024 * 1024 / min(m, 1769)
    if model == "eq2_model":
        return d1024 * (0.5 + 0.5 * 1024 / m)
    raise ValueError(model)


def estimate(design: Design, warm_mean_1024: Optional[Dict[str, float]] = None, init_target_s: float = 2.0,
             platform_cold_s: float = 1.0, client_overhead_s: float = 0.05, update_wait_s: float = 10.0,
             price_gb_s: Optional[float] = None, price_request: Optional[float] = None,
             init_proxy_warm_s: float = 0.005) -> Dict:
    if price_gb_s is None or price_request is None:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
        from prism_repro.config import Prices
        p = Prices()
        price_gb_s = p.od if price_gb_s is None else price_gb_s
        price_request = p.req if price_request is None else price_request
    wm = warm_mean_1024 or WARM_MEAN_1024
    out = {"assumptions": {"warm_mean_1024_s": wm, "init_target_s_at_1024": init_target_s,
                           "platform_cold_s": platform_cold_s, "client_overhead_s": client_overhead_s,
                           "update_wait_s_per_visit": update_wait_s, "price_usd_per_gb_s": price_gb_s,
                           "price_usd_per_request": price_request,
                           "price_source": "manuscript values from prism_repro.config.Prices; NOT current prices",
                           "init_proxy_warm_s": init_proxy_warm_s},
           "models": {}}
    n_inv = sum(v.cold + sum(v.warm_batches) for v in design.visits)
    for model in ("cpu_linear", "vcpu_plateau", "eq2_model"):
        gbs = gbs_init = wall = 0.0
        per_block: Dict[int, float] = {}
        for v in design.visits:
            m, c = v.cell.memory_mb, v.cell
            if c.group == "main":
                d = _d(wm[c.variant], m, model)
                init_extra, first_extra = 0.0, 0.0
            else:
                d = init_proxy_warm_s
                work = _d(init_target_s, m, model)
                init_extra = work if c.variant == "init_module" else 0.0
                first_extra = work if c.variant == "init_first_call" else 0.0
            cold_dur = d + first_extra
            gbs += v.cold * cold_dur * m / 1024 + sum(v.warm_batches) * d * m / 1024
            gbs_init += v.cold * (platform_cold_s + init_extra) * m / 1024
            t = update_wait_s + (client_overhead_s + platform_cold_s + init_extra + cold_dur) \
                + len(v.warm_batches) * (client_overhead_s + d)
            wall += t
            per_block[v.block] = per_block.get(v.block, 0.0) + t
        cost = gbs * price_gb_s + n_inv * price_request
        out["models"][model] = {"billed_gb_s": round(gbs, 1), "init_gb_s_if_billed": round(gbs_init, 1),
                                "cost_usd": round(cost, 2),
                                "cost_usd_if_init_billed": round(cost + gbs_init * price_gb_s, 2),
                                "active_hours": round(wall / 3600, 2),
                                "active_hours_per_block": {b: round(h / 3600, 2) for b, h in sorted(per_block.items())}}
    worst = max(out["models"].values(), key=lambda x: x["cost_usd_if_init_billed"])
    out.update(invocations=n_inv, visits=len(design.visits),
               config_updates=len(design.visits),
               log_mb_approx=round(n_inv * 3 * 150 / 1e6, 1),
               planning_cost_usd_upper=worst["cost_usd_if_init_billed"],
               planning_active_hours_upper=max(x["active_hours"] for x in out["models"].values()))
    return out
