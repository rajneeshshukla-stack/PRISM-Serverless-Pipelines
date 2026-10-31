"""Event-level simulator (§V-A, §VI-H). SIMULATION ONLY.

Every request is an event. Arrivals are placed uniformly at random within each
minute; service, orchestration and initialisation draws of every request and stage
are fixed per (trace, week, scenario) so that every policy sees identical draws.
Per stage, a request is served by a free provisioned environment if one exists
(loss routing, so the provisioned pool is an M/G/P/P system); otherwise by an idle
warm on-demand environment (last-in first-out, retained for the keep-alive period);
otherwise it cold-starts, and the new environment is occupied for init + execution.
An upstream completion plus the orchestration delay is the downstream arrival.
Every request's latency is computed, so window attainment is exact.

This is an independent reconstruction of the manuscript's description; it is
open-loop: it replays provisioning schedules produced elsewhere (§VI-H).
"""
from __future__ import annotations

import heapq
from collections import deque

import numpy as np

from .config import PipelineConfig
from .latency import init_mean, lognormal_mult, stage_means
from .metrics import severity, weighted_quantile_hist, window_attainment


class EventDraws:
    def __init__(self, cfg: PipelineConfig, counts: np.ndarray, seed: int, key: int):
        rng = np.random.default_rng([seed, 500 + key])
        n_min = len(counts)
        S = cfg.n_stages
        self.counts = counts.astype(np.int64)
        self.minute = np.repeat(np.arange(n_min), self.counts)
        self.arrival = self.minute * 60.0 + rng.uniform(0, 60, len(self.minute))
        order = np.argsort(self.arrival, kind="stable")
        self.arrival, self.minute = self.arrival[order], self.minute[order]
        n = len(self.arrival)
        self.ex = lognormal_mult(rng.standard_normal((S, n)), cfg.exec_shape).astype(np.float32)
        self.ov = (cfg.overhead_mean * lognormal_mult(rng.standard_normal((S, n)), cfg.overhead_shape)).astype(np.float32)
        self.init = lognormal_mult(rng.standard_normal((S, n)), cfg.init_shape).astype(np.float32)
        self.n, self.n_min = n, n_min


def _stage_pass(arr, x, z, P_min, KA):
    """One stage. arr sorted ascending. Returns finish times, cold flags, provisioned flags."""
    n = len(arr)
    finish = np.empty(n)
    cold = np.zeros(n, bool)
    used_pc = np.zeros(n, bool)
    pc_busy, od_busy, idle = [], [], deque()
    hpush, hpop = heapq.heappush, heapq.heappop
    arr_l, x_l, z_l = arr.tolist(), x.tolist(), z.tolist()
    P_l = P_min.tolist()
    nP = len(P_l)
    for j in range(n):
        t = arr_l[j]
        while pc_busy and pc_busy[0] <= t:
            hpop(pc_busy)
        m = int(t // 60.0)
        Pm = P_l[m] if m < nP else P_l[-1]
        if len(pc_busy) < Pm:
            f = t + x_l[j]
            hpush(pc_busy, f)
            used_pc[j] = True
        else:
            while od_busy and od_busy[0] <= t:
                idle.append(hpop(od_busy))
            lim = t - KA
            while idle and idle[0] < lim:
                idle.popleft()
            if idle:
                idle.pop()
                f = t + x_l[j]
            else:
                f = t + z_l[j] + x_l[j]
                cold[j] = True
            hpush(od_busy, f)
        finish[j] = f
    return finish, cold, used_pc


def max_inflight_per_minute(arr, finish, n_min):
    """Maximum number of in-flight executions in each minute (sweep over +1/-1 events),
    including the level carried into a minute from earlier events."""
    times = np.concatenate([arr, finish])
    delta = np.concatenate([np.ones(len(arr)), -np.ones(len(finish))])
    o = np.lexsort((-delta, times))  # at equal times process arrivals first (conservative)
    times, level = times[o], np.cumsum(delta[o])
    mins = np.minimum((times // 60).astype(np.int64), n_min - 1)
    out = np.zeros(n_min)
    np.maximum.at(out, mins, level)
    # level in force at the start of each minute = level after the last earlier event
    k = np.searchsorted(times, np.arange(n_min) * 60.0, side="left") - 1
    carry = np.where(k >= 0, level[np.maximum(k, 0)], 0.0)
    return np.maximum(out, carry)


def simulate_events(cfg: PipelineConfig, draws: EventDraws, P_epoch: np.ndarray, mem_epoch: np.ndarray,
                    bill_init: bool = True, want_inflight: bool = False, sample_seed: int | None = None) -> dict:
    """Replay a provisioning schedule (per epoch, S stages) and memory schedule."""
    S, E = cfg.n_stages, cfg.epoch_min
    P_min = np.repeat(np.asarray(P_epoch, float), E, axis=0)[:draws.n_min]
    mem_min = np.repeat(np.asarray(mem_epoch), E)[:draws.n_min]
    pr = cfg.prices
    arr = draws.arrival.copy()
    idx = np.arange(draws.n)          # request id of each position
    cost = (P_min * (mem_min[:, None] / 1024.0) * 60.0 * pr.pc).sum() + draws.n * S * pr.req
    od_share, cold_ratio, inflight = [], [], []
    KA = cfg.keepalive_min * 60.0
    for s in range(S):
        m_req = mem_min[np.minimum((arr // 60).astype(np.int64), draws.n_min - 1)]
        d_s = np.array([stage_means(cfg, int(m))[s] for m in cfg.mem_options])
        ini = np.array([init_mean(cfg, int(m)) for m in cfg.mem_options])
        mi = np.searchsorted(np.array(cfg.mem_options), m_req)
        x = draws.ex[s, idx] * d_s[mi]
        z = draws.init[s, idx] * ini[mi]
        fin, cold, used_pc = _stage_pass(arr, x, z, P_min[:, s], KA)
        g = m_req / 1024.0
        cost += (x * g * np.where(used_pc, pr.pcd, pr.od)).sum()
        if bill_init:
            cost += (z * g * cold * pr.od).sum()
        od_share.append(1 - used_pc.mean())
        cold_ratio.append(cold.mean())
        if want_inflight:
            inflight.append(max_inflight_per_minute(arr, fin, draws.n_min))
        nxt = fin + draws.ov[s, idx]
        o = np.argsort(nxt, kind="stable")
        arr, idx = nxt[o], idx[o]
    done = np.empty(draws.n)
    done[idx] = arr                  # after final stage incl. its orchestration overhead
    lat = done - draws.arrival
    ok = lat <= cfg.deadline
    ontime = np.bincount(draws.minute, weights=ok.astype(float), minlength=draws.n_min)
    N = draws.counts.astype(float)
    att, late, tot = window_attainment(N, ontime, cfg.window_min)
    sev = severity(att, late, tot, 1 - cfg.sla_eps)
    out = dict(cost=float(cost), record_attainment=float(ok.mean()),
               p99_latency=weighted_quantile_hist(lat[None, :], np.ones((1, 1)), 0.99),
               overflow_share=float(np.mean(od_share)), cold_start_ratio=float(np.mean(cold_ratio)),
               slo_met=bool(sev["violating_window_rate"] <= cfg.slo_violating_window_target + 1e-12), **sev)
    raw = dict(window_attainment=att.astype(np.float32), overflow_share_stage=np.array(od_share))
    if want_inflight:
        raw["inflight_max"] = np.stack(inflight, 1).astype(np.float32)
    if sample_seed is not None:  # latency-sampling error of the fast simulator (Supplement S4)
        raw["sampling_flip_share"] = sampling_flips(draws, lat, cfg, sample_seed)
    return dict(summary=out, raw=raw)


def sampling_flips(draws: EventDraws, lat: np.ndarray, cfg: PipelineConfig, seed: int, reps: int = 5):
    """Share of windows whose compliance classification changes when attainment is
    estimated from 100 sampled requests per minute (volume weighted) instead of exactly."""
    N = draws.counts.astype(float)
    ok = (lat <= cfg.deadline).astype(float)
    exact_ot = np.bincount(draws.minute, weights=ok, minlength=draws.n_min)
    att_exact, _, _ = window_attainment(N, exact_ot, cfg.window_min)
    starts = np.concatenate([[0], np.cumsum(draws.counts)[:-1]])
    rng = np.random.default_rng(seed)
    flips = []
    k = cfg.latency_samples
    for _ in range(reps):
        pick = starts[:, None] + (rng.uniform(size=(draws.n_min, k)) * np.maximum(draws.counts, 1)[:, None]).astype(np.int64)
        pick = np.minimum(pick, len(ok) - 1)
        frac = np.where(draws.counts > 0, ok[pick].mean(1), 1.0)
        att_s, _, _ = window_attainment(N, N * frac, cfg.window_min)
        thr = 1 - cfg.sla_eps
        flips.append(np.mean((att_s < thr) != (att_exact < thr)))
    return np.array(flips)
