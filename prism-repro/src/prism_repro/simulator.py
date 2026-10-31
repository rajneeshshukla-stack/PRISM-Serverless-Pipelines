"""Fast per-minute simulator (§V-A). SIMULATION ONLY — no cloud execution.

Per minute t and stage s:
  K[t,s]   peak concurrency: Poisson(c * Z_t) restricted to its upper 45 %,
           c = N_t d_s(m)/60, Z_t = exp(sigma z_t) (median-1 log-normal intensity).
           Policy independent given memory (common random numbers).
  OD       = (K - P)+  on-demand concurrency
  pool     = max OD over the previous keep-alive minutes (warm on-demand envs, D12)
  new envs = (OD - pool)+ ; cold starts nu = min(new envs, overflow requests)
  overflow requests n_od = N * OD/K (D13)
Latency: 100 sampled requests per minute, volume weighted; each stage is cold with
probability nu/N (§V-A). Costs follow Eqs. (8)-(9) with tau = 60 s per minute.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
from scipy import stats

from .config import PipelineConfig
from .latency import gb, init_mean, lognormal_mult, stage_means
from .metrics import severity, weighted_quantile_hist, window_attainment

WEEK = 7 * 1440


class WeekDraws:
    """Common random numbers for one trace-week; shared by all policies and by all
    test scenarios of a trace."""

    def __init__(self, cfg: PipelineConfig, seed: int, week_index: int, n_min: int = WEEK):
        rng = np.random.default_rng([seed, 100 + week_index])
        S, I = cfg.n_stages, cfg.latency_samples
        self.cfg, self.n_min = cfg, n_min
        self.u_peak = rng.uniform(1 - cfg.peak_upper_frac, 1.0, size=(n_min, S))
        self.z_int = rng.standard_normal(n_min)
        self.ex = lognormal_mult(rng.standard_normal((n_min, I, S)), cfg.exec_shape).astype(np.float32)
        ov = cfg.overhead_mean * lognormal_mult(rng.standard_normal((n_min, I, S)), cfg.overhead_shape)
        self.ov_sum = ov.sum(-1).astype(np.float32)
        self.init = lognormal_mult(rng.standard_normal((n_min, I, S)), cfg.init_shape).astype(np.float32)
        self.u_cold = rng.uniform(size=(n_min, I, S)).astype(np.float32)
        self._warm = {}

    def peak_concurrency(self, counts: np.ndarray, m: int) -> np.ndarray:
        d = stage_means(self.cfg, m)
        lam = counts[:, None] * d[None, :] / 60.0 * np.exp(self.cfg.intensity_sigma * self.z_int)[:, None]
        return np.where(lam > 0, stats.poisson.ppf(self.u_peak, np.maximum(lam, 1e-12)), 0.0)

    def warm_total(self, m: int) -> np.ndarray:
        if m not in self._warm:
            d = stage_means(self.cfg, m).astype(np.float32)
            self._warm[m] = (self.ex * d[None, None, :]).sum(-1) + self.ov_sum
        return self._warm[m]


@dataclass
class Telemetry:
    N: np.ndarray        # arrivals per minute (week)
    K: np.ndarray        # observed peak concurrency (n,S) under the applied memory
    P: np.ndarray        # provisioned level per minute
    n_od: np.ndarray     # overflow requests
    cold: np.ndarray     # cold starts
    filled: int = 0      # minutes simulated so far


@dataclass
class SimContext:
    cfg: PipelineConfig
    counts: np.ndarray            # full trace counts (global minutes)
    week_start: int               # global minute of week start
    draws: WeekDraws
    K_hist_default: np.ndarray    # (global minutes, S) peak concurrency at default memory
    forecasts: Dict[str, dict] = field(default_factory=dict)  # name -> per-epoch arrays
    r_mean_peak: float = 0.8
    bill_init: bool = True
    _Kweek: Dict[int, np.ndarray] = field(default_factory=dict)

    @property
    def n_epochs(self) -> int:
        return WEEK // self.cfg.epoch_min

    def week_counts(self) -> np.ndarray:
        return self.counts[self.week_start:self.week_start + WEEK]

    def K_week(self, m: int) -> np.ndarray:
        if m not in self._Kweek:
            self._Kweek[m] = self.draws.peak_concurrency(self.week_counts().astype(float), m)
        return self._Kweek[m]

    def decision_minute(self, k: int) -> int:
        """Global minute of decision k (controls week minutes 5k..5k+4)."""
        return self.week_start + k * self.cfg.epoch_min - self.cfg.lag_min


def simulate(ctx: SimContext, policy, keep_raw: bool = True) -> dict:
    cfg, pr = ctx.cfg, ctx.cfg.prices
    S, E = cfg.n_stages, cfg.epoch_min
    N = ctx.week_counts().astype(float)
    n = len(N)
    tel = Telemetry(N=N, K=np.zeros((n, S)), P=np.zeros((n, S)), n_od=np.zeros((n, S)),
                    cold=np.zeros((n, S)))
    mem_min = np.full(n, cfg.default_mem, dtype=np.int32)
    OD = np.zeros((n, S))
    policy.prepare(ctx)
    t0 = time.perf_counter()
    dec_times = []
    ka = cfg.keepalive_min
    pre_pool = None
    for k in range(ctx.n_epochs):
        td = time.perf_counter()
        P, m = policy.decide(k, tel)
        dec_times.append(time.perf_counter() - td)
        P = np.asarray(P, float)
        if P.shape != (S,) or np.any(P < 0) or not np.all(np.isfinite(P)):
            raise ValueError(f"policy {policy.label} returned invalid P {P}")
        a, b = k * E, (k + 1) * E
        K = ctx.K_week(m)[a:b]
        if k == 0:  # initial warm pool from the 10 pre-week minutes at default memory (D24)
            Kpre = ctx.K_hist_default[ctx.week_start - ka:ctx.week_start]
            pre_pool = np.maximum(Kpre - P[None, :], 0).max(0) if ka > 0 else np.zeros(S)
        od = np.maximum(K - P[None, :], 0.0)
        new = np.zeros_like(od)
        for i in range(E):  # pool from previous ka minutes of on-demand concurrency
            t = a + i
            lo = max(0, t - ka)
            pool = OD[lo:t].max(0) if t > lo else np.zeros(S)
            if t < ka:
                pool = np.maximum(pool, pre_pool)
            new[i] = np.maximum(od[i] - pool, 0.0)
            OD[t] = od[i]
        share = np.where(K > 0, od / np.where(K > 0, K, 1.0), 0.0)
        n_od = N[a:b, None] * share
        cold = np.minimum(new, n_od)
        tel.K[a:b], tel.P[a:b], tel.n_od[a:b], tel.cold[a:b] = K, P[None, :], n_od, cold
        mem_min[a:b] = m
        tel.filled = b
    sim_time = time.perf_counter() - t0

    # ---- costs (Eqs. (8)-(9), per minute) ----
    mems = np.unique(mem_min)
    D = np.stack([stage_means(cfg, int(mm)) for mm in mem_min.tolist()]) if len(mems) > 1 else \
        np.broadcast_to(stage_means(cfg, int(mems[0])), (n, S))
    g = mem_min / 1024.0
    ini = np.array([init_mean(cfg, int(mm)) for mm in mem_min]) if len(mems) > 1 else \
        np.full(n, init_mean(cfg, int(mems[0])))
    n_pc = N[:, None] - tel.n_od
    c_pc = (tel.P * g[:, None] * 60.0 * pr.pc).sum()
    c_pcd = (n_pc * D * g[:, None] * pr.pcd).sum()
    c_od = (tel.n_od * D * g[:, None] * pr.od).sum()
    c_init = (tel.cold * ini[:, None] * g[:, None] * pr.od).sum() if ctx.bill_init else 0.0
    c_req = N.sum() * S * pr.req
    total = c_pc + c_pcd + c_od + c_init + c_req

    # ---- latency (sampled, volume weighted) ----
    dr = ctx.draws
    cr = np.where(N[:, None] > 0, tel.cold / np.maximum(N[:, None], 1), 0.0).astype(np.float32)
    lat = np.empty((n, cfg.latency_samples), np.float32)
    for mm in mems:
        sel = mem_min == mm
        cold_ind = dr.u_cold[sel] < cr[sel][:, None, :]
        lat[sel] = dr.warm_total(int(mm))[sel] + (cold_ind * dr.init[sel]).sum(-1) * np.float32(init_mean(cfg, int(mm)))
    frac_ok = (lat <= cfg.deadline).mean(1)
    att, late, tot = window_attainment(N, N * frac_ok, cfg.window_min)
    sev = severity(att, late, tot, 1 - cfg.sla_eps)
    p99 = weighted_quantile_hist(lat, (N / cfg.latency_samples)[:, None], 0.99)

    busy_pc = (n_pc * D * g[:, None]).sum()
    prov = (tel.P * g[:, None] * 60.0).sum()
    Ptot = tel.P.sum(1)
    chg = np.any(np.diff(tel.P, axis=0) != 0, axis=1)
    added = np.maximum(np.diff(tel.P, axis=0), 0).sum()
    info = policy.info()
    out = dict(
        policy=policy.variant, label=policy.label, param=policy.param,
        cost=total, cost_pc=c_pc, cost_pcd=c_pcd, cost_od=c_od, cost_init=c_init, cost_req=c_req,
        record_attainment=float((N * frac_ok).sum() / N.sum()),
        p99_latency=p99, billing_utilisation=float(busy_pc / prov) if prov > 0 else 0.0,
        mean_provisioned=float(Ptot.mean()), overflow_share=float(tel.n_od.sum() / (N.sum() * S)),
        cold_start_ratio=float(tel.cold.sum() / (N.sum() * S)),
        minutes_with_change=int(chg.sum()), envs_added=float(added),
        share_mem_ge_2048=float(np.mean(mem_min >= 2048)),
        slo_met=bool(sev["violating_window_rate"] <= cfg.slo_violating_window_target + 1e-12),
        sim_seconds=sim_time, decision_ms_median=float(np.median(dec_times) * 1e3),
        decision_ms_p99=float(np.quantile(dec_times, 0.99) * 1e3),
        **sev,
    )
    for kk, vv in info.items():
        if np.isscalar(vv):
            out[kk] = vv
    raw = None
    if keep_raw:
        raw = dict(window_attainment=att.astype(np.float32), window_late=late.astype(np.float32),
                   window_records=tot.astype(np.float32),
                   P_epoch=tel.P[::E].astype(np.int32), mem_epoch=mem_min[::E].astype(np.int32))
        for kk, vv in info.items():
            if isinstance(vv, np.ndarray):
                raw[kk] = vv
    return {"summary": out, "raw": raw, "telemetry": tel}
