"""Scenario-based chance-constrained optimiser (§IV-C to §IV-D, Eq. (11), Algorithm 1 steps 5-7).

For each memory m in the allowed set and each demand level y of the grid
{0} U linspace(0.5 min(scen), 1.15 max(scen), 20), the candidate capacity is
P_s = ceil(y d_s(m)/60) (clipped to the cap). For every scenario lambda_i the
risk model gives v (Eqs. (6)-(7)) and the cost model gives the epoch cost (Eqs. (8)-(9)).
Feasible: share of scenarios with v <= eps is >= 1 - delta. Choose the cheapest
feasible candidate; if none, the most feasible (ties by cost) and flag.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import PipelineConfig, PrismConfig
from .latency import gb, init_mean, miss_table, stage_means
from .risk import overflow_prob


@dataclass
class Decision:
    P: np.ndarray
    mem: int
    feasible: bool
    feas_frac: float
    excess: float          # v at the (1-delta) scenario quantile minus eps (fallback only, else 0)
    exp_cost: float
    level: float


class ChanceConstrainedOptimizer:
    def __init__(self, cfg: PipelineConfig, pcfg: PrismConfig, r_mean_peak: float = 0.8):
        self.cfg, self.pcfg, self.r = cfg, pcfg, float(r_mean_peak)
        self.mt = miss_table(cfg)
        self.mems = np.array(cfg.mem_options)
        self.d = {m: stage_means(cfg, m) for m in cfg.mem_options}
        self.init = {m: init_mean(cfg, m) for m in cfg.mem_options}
        self.use_ceff = pcfg.use_ceff if pcfg.risk_model == "occupancy" else False

    def candidates(self, scen: np.ndarray) -> np.ndarray:
        lo, hi = self.pcfg.level_lo * scen.min(), self.pcfg.level_hi * scen.max()
        return np.concatenate([[0.0], np.linspace(lo, hi, self.pcfg.n_levels)])

    def evaluate(self, scen: np.ndarray, mems, kappa: float):
        """Return dict of arrays over (M, Y): feasible fraction, expected cost, P (M,Y,S),
        and v at the (1-delta) quantile scenario."""
        cfg, pc, pr = self.cfg, self.pcfg, self.cfg.prices
        scen = np.asarray(scen, float)
        ys = self.candidates(scen)
        tau = cfg.epoch_min * 60.0
        S = cfg.n_stages
        mems = list(mems)
        Ms = len(mems)
        D = np.stack([self.d[m] for m in mems])                      # (M,S)
        P = np.ceil(ys[None, :, None] * D[:, None, :] / 60.0 - 1e-9)  # (M,Y,S)
        if pc.cap is not None:
            P = np.minimum(P, pc.cap)
        lam = scen  # (I,)
        c = lam[None, None, :, None] * D[:, None, None, :] / 60.0     # (M,1,I,S)
        f = overflow_prob(P[:, :, None, :], c, pc.risk_model, self.use_ceff)  # (M,Y,I,S)
        vw = np.array([self.mt[m][0] for m in mems])[:, None, None]
        rho = np.array([self.mt[m][1] for m in mems])[:, None, None]
        p_c = 1.0 - np.prod(1.0 - kappa * f, axis=-1)                # (M,Y,I)
        v = (1.0 - p_c) * vw + p_c * rho
        if pc.feasibility_mode == "scenarios":
            feas_frac = np.mean(v <= pc.eps, axis=-1)
            cost_idx = slice(None)
        else:  # single evaluation at the (1-delta) quantile (§IV-C; Supplement S9); cost on every 5th scenario
            iq = int(np.ceil((1 - pc.delta) * len(lam))) - 1
            feas_frac = (v[..., iq] <= pc.eps).astype(float)
            cost_idx = slice(None, None, 5)
        iq = min(len(lam) - 1, max(0, int(np.ceil((1 - pc.delta) * len(lam))) - 1))
        v_q = v[..., iq]
        g = np.array([gb(m) for m in mems])[:, None, None, None]
        n_exec = self.r * lam[cost_idx] * cfg.epoch_min                 # expected executions (§III-D (iv))
        fc = f[:, :, cost_idx, :]
        n = n_exec[None, None, :, None]
        Dm = D[:, None, None, :]
        initm = np.array([self.init[m] for m in mems])[:, None, None, None]
        cost = (P[:, :, None, :] * g * tau * pr.pc
                + n * (1 - fc) * Dm * g * pr.pcd
                + n * fc * Dm * g * pr.od
                + kappa * n * fc * initm * g * pr.od).sum(-1) + S * n_exec[None, None, :] * pr.req
        exp_cost = cost.mean(-1)                                      # (M,Y)
        return dict(ys=ys, P=P, feas=feas_frac, cost=exp_cost, v_q=v_q, mems=mems)

    def decide(self, scen: np.ndarray, mems, kappa: float) -> Decision:
        ev = self.evaluate(scen, mems, kappa)
        feas = ev["feas"] >= 1 - self.pcfg.delta - 1e-12
        cost = ev["cost"]
        if feas.any():
            masked = np.where(feas, cost, np.inf)
            i, j = np.unravel_index(np.argmin(masked), masked.shape)
            excess = 0.0
            ok = True
        else:  # fallback: highest feasibility fraction, ties broken by cost
            fmax = ev["feas"].max()
            masked = np.where(ev["feas"] >= fmax - 1e-12, cost, np.inf)
            i, j = np.unravel_index(np.argmin(masked), masked.shape)
            excess = float(ev["v_q"][i, j] - self.pcfg.eps)
            ok = False
        return Decision(P=ev["P"][i, j].astype(int), mem=int(ev["mems"][i]), feasible=ok,
                        feas_frac=float(ev["feas"][i, j]), excess=max(excess, 0.0),
                        exp_cost=float(cost[i, j]), level=float(ev["ys"][j]))
