#!/usr/bin/env python3
"""R2.7 within-run shift experiment (docs/revision/r27_shift_20261124/PLAN.md). EXPLORATORY; src/ is not changed.

simulate_shift(ctxA, ctxB, cp, policy) is prism_repro.simulator.simulate with every execution-dependent input spliced
at week minute cp: before cp it uses ctxA (configuration A), from cp on ctxB (configuration B, same trace and same
random draws, different execution times). With ctxB None it must equal simulator.simulate exactly (checked in
`check`). PRISMOnline is an EXPLORATORY variant, kept separate from the published PRISM: at epoch k_est it rebuilds
its optimiser and stage means from configuration B (the shared estimate); memory can be fixed (one-time).

usage (from prism-repro/): venv/Scripts/python scripts/revision/r27_shift.py <out dir> check|run|analyse
"""
import dataclasses
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import WEEK_INDEX, TraceBundle, make_policy  # noqa: E402
from prism_repro.latency import (attainment_table, init_mean, init_seconds, poisson_binomial, stage_demand,  # noqa: E402
                                 stage_means)
from prism_repro.metrics import severity, weighted_quantile_hist, window_attainment  # noqa: E402
from prism_repro.optimizer import ChanceConstrainedOptimizer  # noqa: E402
from prism_repro.policies import PRISM  # noqa: E402
from prism_repro.simulator import Telemetry, WeekDraws, simulate  # noqa: E402

SEEDS = (101, 102, 103, 104, 105)
CP = 3 * 1440                     # start of test-week day 4
DELAY = 60                        # minutes until the shared estimate
FACTOR = float(os.environ.get("R27_FACTOR", "1.5"))   # 1.5 is the prespecified shift; others are POST HOC
EPS = 0.02
FIXED = (1024, 2048, 3008)


def shifted_cfg(cfg):
    return cfg.with_(warm_mean_1024=tuple(FACTOR * x for x in cfg.warm_mean_1024))


def ctx_for(ctxA, cfgB, seed):
    return dataclasses.replace(ctxA, cfg=cfgB, draws=WeekDraws(cfgB, seed, WEEK_INDEX["test"]), _Kweek={})


def simulate_shift(ctxA, ctxB, cp, policy):
    """simulator.simulate (3edc386) with execution-dependent inputs taken from ctxB for week minutes >= cp."""
    cfg, pr = ctxA.cfg, ctxA.cfg.prices
    S, E = cfg.n_stages, cfg.epoch_min
    N = ctxA.week_counts().astype(float)
    n = len(N)
    phi = stage_demand(cfg)
    NS = N[:, None] * phi[None, :]
    tel = Telemetry(N=N, K=np.zeros((n, S)), P=np.zeros((n, S)), n_od=np.zeros((n, S)), cold=np.zeros((n, S)))
    mem_min = np.full(n, cfg.default_mem, dtype=np.int32)
    OD = np.zeros((n, S))
    policy.prepare(ctxA)
    ka = cfg.keepalive_min
    pre_od, seg_start, m_prev = None, 0, None
    after = np.arange(n) >= (cp if ctxB is not None else n)

    def Kweek(m):
        KA = ctxA.K_week(m)
        return np.where(after[:, None], ctxB.K_week(m), KA) if ctxB is not None else KA

    for k in range(ctxA.n_epochs):
        P, m = policy.decide(k, tel)
        P = np.asarray(P, float)
        if P.shape != (S,) or np.any(P < 0) or not np.all(np.isfinite(P)):
            raise ValueError(f"policy returned invalid P {P}")
        a, b = k * E, (k + 1) * E
        K = Kweek(m)[a:b]
        if k == 0:
            Kpre = ctxA.K_hist_default[ctxA.week_start - ka:ctxA.week_start]
            pre_od = np.maximum(Kpre - P[None, :], 0) if ka > 0 else np.zeros((0, S))
            if m != cfg.default_mem:
                pre_od = np.zeros_like(pre_od)
        if m_prev is not None and m != m_prev:
            seg_start = a
        m_prev = m
        od = np.maximum(K - P[None, :], 0.0)
        new = np.zeros_like(od)
        for i in range(E):
            t = a + i
            lo = max(0, t - ka, seg_start)
            pool = OD[lo:t].max(0) if t > lo else np.zeros(S)
            if t < ka and seg_start == 0:
                pool = np.maximum(pool, pre_od[t:].max(0) if t < len(pre_od) else 0.0)
            new[i] = np.maximum(od[i] - pool, 0.0)
            OD[t] = od[i]
        share = np.where(K > 0, od / np.where(K > 0, K, 1.0), 0.0)
        n_od = NS[a:b] * share
        cold = np.minimum(new, n_od)
        tel.K[a:b], tel.P[a:b], tel.n_od[a:b], tel.cold[a:b] = K, P[None, :], n_od, cold
        mem_min[a:b] = m
        tel.filled = b

    def cfg_at(t):
        return ctxB.cfg if (ctxB is not None and after[t]) else cfg

    seg = [(cfg, ~after)] + ([(ctxB.cfg, after)] if ctxB is not None else [])
    D = np.zeros((n, S))
    ini = np.zeros(n)
    for c, mask in seg:
        for mm in np.unique(mem_min[mask]):
            sel = mask & (mem_min == mm)
            D[sel] = stage_means(c, int(mm))
            ini[sel] = init_mean(c, int(mm))
    g = mem_min / 1024.0
    n_pc = NS - tel.n_od
    c_pc = (tel.P * g[:, None] * 60.0 * pr.pc).sum()
    c_pcd = (n_pc * D * g[:, None] * pr.pcd).sum()
    c_od = (tel.n_od * D * g[:, None] * pr.od).sum()
    c_init = (tel.cold * ini[:, None] * g[:, None] * pr.od).sum() if ctxA.bill_init else 0.0
    c_req = N.sum() * float(phi.sum()) * pr.req
    total = c_pc + c_pcd + c_od + c_init + c_req

    cr = np.where(NS > 0, tel.cold / np.where(NS > 0, NS, 1.0), 0.0).astype(np.float32)
    lat = np.empty((n, cfg.latency_samples), np.float32)
    frac_ok = np.empty(n, np.float64)
    for c, mask in seg:
        dr = ctxA.draws if c is cfg else ctxB.draws
        for mm in np.unique(mem_min[mask]):
            sel = mask & (mem_min == mm)
            cold_ind = dr.u_cold[sel] < cr[sel][:, None, :]
            if c.init_max_s is None:
                lat[sel] = dr.warm_total(int(mm))[sel] + (cold_ind * dr.init[sel]).sum(-1) * np.float32(init_mean(c, int(mm)))
            else:
                lat[sel] = dr.warm_total(int(mm))[sel] + (cold_ind * init_seconds(c, dr.init[sel], int(mm))).sum(-1)
            if c.exact_attainment:
                w = poisson_binomial(np.clip(cr[sel].astype(np.float64), 0.0, 1.0))
                frac_ok[sel] = w @ attainment_table(c, int(mm))
            else:
                frac_ok[sel] = (lat[sel] <= c.deadline).mean(1)
    att, late, tot = window_attainment(N, N * frac_ok, cfg.window_min)
    sev = severity(att, late, tot, 1 - cfg.sla_eps)
    p99 = weighted_quantile_hist(lat, (N / cfg.latency_samples)[:, None], 0.99)
    out = dict(cost=total, cost_pc=c_pc, cost_pcd=c_pcd, cost_od=c_od, cost_init=c_init, cost_req=c_req,
               record_attainment=float((N * frac_ok).sum() / N.sum()), p99_latency=p99,
               overflow_share=float(tel.n_od.sum() / (N.sum() * float(phi.sum()))),
               cold_start_ratio=float(tel.cold.sum() / (N.sum() * float(phi.sum()))),
               share_mem_ge_2048=float(np.mean(mem_min >= 2048)),
               slo_met=bool(sev["violating_window_rate"] <= cfg.slo_violating_window_target + 1e-12), **sev)
    return {"summary": out, "att": att, "mem_min": mem_min, "P": tel.P}


class PRISMOnline(PRISM):
    """EXPLORATORY variant (not the published configuration): the published PRISM, except that at epoch k_est it
    adopts configuration cfg_new (the shared estimate), and its memory may be fixed (one-time configuration)."""

    def __init__(self, base: PRISM, cfg_new, k_est, fixed_mem=None):
        super().__init__(base.pcfg, base.fc_name)
        self.cfg_new, self.k_est, self.fixed_mem = cfg_new, k_est, fixed_mem

    def _restrict(self, c):
        return c.with_(mem_options=(self.fixed_mem,), default_mem=self.fixed_mem) if self.fixed_mem else c

    def prepare(self, ctx):
        self._rmp = ctx.r_mean_peak
        super().prepare(dataclasses.replace(ctx, cfg=self._restrict(ctx.cfg)))

    def decide(self, k, tel):
        if self.cfg_new is not None and k == self.k_est:
            self.cfg = self._restrict(self.cfg_new)
            self.d = stage_means(self.cfg, self.cfg.default_mem) * stage_demand(self.cfg)
            self.opt = ChanceConstrainedOptimizer(self.cfg, self.pcfg, self._rmp)
        return super().decide(k, tel)


SUMMARY_KEYS = ("cost", "cost_pc", "cost_pcd", "cost_od", "cost_init", "cost_req", "record_attainment", "p99_latency",
                "overflow_share", "cold_start_ratio", "violating_window_rate", "slo_met")


def check(out):
    """No shift: simulate_shift must equal simulator.simulate; PRISMOnline with no estimate must equal PRISM."""
    cfg = PipelineConfig()
    b = TraceBundle(101, cfg)
    ctx = b.context("stationary", "test")
    ref = simulate(ctx, make_policy(dict(family="PRISM", param=EPS)))["summary"]
    got = simulate_shift(b.context("stationary", "test"), None, CP, make_policy(dict(family="PRISM", param=EPS)))["summary"]
    online = simulate_shift(b.context("stationary", "test"), None, CP,
                            PRISMOnline(make_policy(dict(family="PRISM", param=EPS)), None, 0))["summary"]
    same = {k: (bool(ref[k] == got[k]), bool(ref[k] == online[k])) for k in SUMMARY_KEYS}
    res = {"all_identical": all(a and b2 for a, b2 in same.values()), "fields": {k: list(v) for k, v in same.items()},
           "ref_violating": ref["violating_window_rate"], "ref_cost": ref["cost"]}
    with open(os.path.join(out, "check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res))


def post(att, start_min, window_min=15, target=0.99):
    w = att[start_min // window_min:]
    return float(np.mean(w < target - 1e-12))      # as metrics.severity


def run(out):
    cfg = PipelineConfig()
    cfgB = shifted_cfg(cfg)
    k_est = (CP + DELAY) // cfg.epoch_min
    path = os.path.join(out, "rows.jsonl")
    done = set()
    if os.path.exists(path):
        done = {json.loads(l)["key"] for l in open(path, encoding="utf-8")}
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for seed in SEEDS:
            t = time.time()
            b = TraceBundle(seed, cfg)
            variants = [("A_online_dynamic", lambda: PRISMOnline(make_policy(dict(family="PRISM", param=EPS)), cfgB, k_est)),
                        ("C_published_no_estimate", lambda: make_policy(dict(family="PRISM", param=EPS)))]
            variants += [(f"B_online_fixed_{m}", (lambda m=m: PRISMOnline(make_policy(dict(family="PRISM", param=EPS)),
                                                                          cfgB, k_est, fixed_mem=m))) for m in FIXED]
            for name, mk in variants:
                key = f"{seed}|{name}"
                if key in done:
                    continue
                ctxA = b.context("stationary", "test")
                ctxB = ctx_for(ctxA, cfgB, seed)
                t0 = time.perf_counter()
                r = simulate_shift(ctxA, ctxB, CP, mk())
                s = r["summary"]
                mem_day = [int(np.bincount(r["mem_min"][d * 1440:(d + 1) * 1440]).argmax()) for d in range(7)]
                row = dict(key=key, seed=seed, variant=name, **{k: (float(s[k]) if not isinstance(s[k], bool) else s[k])
                                                                 for k in SUMMARY_KEYS},
                           post_shift_violating=post(r["att"], CP), post_estimate_violating=post(r["att"], CP + DELAY),
                           pre_shift_violating=float(np.mean(r["att"][:CP // 15] < 0.99 - 1e-12)),
                           memory_modal_by_day=mem_day, runtime_s=time.perf_counter() - t0)
                f.write(json.dumps(row) + "\n"); f.flush()
                print(f"[{seed}] {name}: viol {100 * row['violating_window_rate']:.2f}% (post {100 * row['post_shift_violating']:.2f}%) "
                      f"cost {row['cost']:.0f} mem/day {mem_day} {row['runtime_s']:.0f}s", flush=True)
            print(f"[{seed}] done in {time.time() - t:.0f}s", flush=True)


def analyse(out):
    rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(out, "rows.jsonl"), encoding="utf-8")}
    L = ["R2.7 within-run shift (warm execution time x1.5 at test-week day 4). EXPLORATORY, fast simulator, "
         "PRE-CALIBRATION, development traces, Windows. Plan: docs/revision/r27_shift_20261124/PLAN.md", ""]
    c1 = c2 = 0
    per = []
    for seed in SEEDS:
        g = lambda v: rows[f"{seed}|{v}"]  # noqa: E731
        A, B1 = g("A_online_dynamic"), g("B_online_fixed_1024")
        Bs = [g(f"B_online_fixed_{m}") for m in FIXED]
        okB = [x for x in Bs if x["slo_met"]]
        best = min(okB, key=lambda x: x["cost"]) if okB else None
        k1 = (A["slo_met"] and not B1["slo_met"]) or (A["slo_met"] and B1["slo_met"] and A["cost"] <= 0.95 * B1["cost"]) or \
             (not A["slo_met"] and not B1["slo_met"] and A["violating_window_rate"] <= B1["violating_window_rate"] - 0.005)
        k2 = A["slo_met"] and (best is None or A["cost"] <= 0.95 * best["cost"])
        c1 += k1; c2 += k2
        per.append((seed, k1, k2))
        L.append(f"trace {seed}:")
        for v in ("A_online_dynamic", "B_online_fixed_1024", "B_online_fixed_2048", "B_online_fixed_3008",
                  "C_published_no_estimate"):
            x = g(v)
            L.append(f"  {v:26s} week viol {100 * x['violating_window_rate']:5.2f}%  pre {100 * x['pre_shift_violating']:5.2f}%  "
                     f"post-shift {100 * x['post_shift_violating']:5.2f}%  post-estimate {100 * x['post_estimate_violating']:5.2f}%  "
                     f"cost {x['cost']:7.1f}  memory by day {x['memory_modal_by_day']}")
        L.append(f"  best one-time in hindsight: {best['variant'] if best else 'none meets 2%'}"
                 + (f" (A cost {100 * (A['cost'] / best['cost'] - 1):+.1f}%)" if best else "")
                 + f"; criterion 1: {k1}; criterion 2: {k2}")
    L += ["", f"criterion 1 (benefit over the pre-shift one-time configuration): {c1} of 5 traces -> "
              f"{'BENEFIT' if c1 >= 4 else 'no demonstrated benefit'}",
          f"criterion 2 (benefit no one-time configuration achieves): {c2} of 5 traces -> "
          f"{'BENEFIT' if c2 >= 4 else 'no demonstrated benefit'}"]
    with open(os.path.join(out, "result.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    o = sys.argv[1]
    os.makedirs(o, exist_ok=True)
    {"check": check, "run": run, "analyse": analyse}[sys.argv[2]](o)
