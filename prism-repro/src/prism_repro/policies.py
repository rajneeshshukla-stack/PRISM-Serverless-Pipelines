"""Provisioning policies (§IV, §V-C). All baselines are independent
reconstructions from the manuscript's one-paragraph descriptions, not the
authors' code.

Interface: prepare(ctx) once per run; decide(k, telemetry) -> (P (S,), memory)
for decision epoch k, which controls week minutes 5k..5k+4 and may only read
telemetry of minutes <= 5k-2 (week-relative), i.e. ctx.decision_minute(k).
"""
from __future__ import annotations

import numpy as np

from .config import PipelineConfig, PrismConfig
from .forecast import scenarios as make_scenarios
from .latency import stage_means
from .optimizer import ChanceConstrainedOptimizer


class Policy:
    family = "base"

    def __init__(self, param=None):
        self.param = param

    @property
    def variant(self):
        return self.family

    @property
    def label(self):
        return self.variant if self.param is None else f"{self.variant}-{self.param}"

    def prepare(self, ctx):
        self.ctx = ctx
        self.cfg: PipelineConfig = ctx.cfg
        self.d = stage_means(self.cfg, self.cfg.default_mem)

    def _visible(self, k):
        """Last week-relative minute whose telemetry is visible at decision k."""
        return k * self.cfg.epoch_min - self.cfg.lag_min

    def info(self):
        return {}


class OnDemand(Policy):
    family = "OnDemand"

    def decide(self, k, tel):
        return np.zeros(self.cfg.n_stages), self.cfg.default_mem


class Static(Policy):
    family = "Static"

    def prepare(self, ctx):
        super().prepare(ctx)
        hist = ctx.K_hist_default[:ctx.week_start]
        self.P = np.ceil(np.percentile(hist, self.param, axis=0))

    def decide(self, k, tel):
        return self.P, self.cfg.default_mem


class Scheduled(Policy):
    """Hour-of-week profile of the 95th percentile of historical concurrency x headroom."""
    family = "Scheduled"

    def prepare(self, ctx):
        super().prepare(ctx)
        hist = ctx.K_hist_default[:ctx.week_start]
        how = (np.arange(ctx.week_start) // 60) % 168
        self.prof = np.zeros((168, self.cfg.n_stages))
        for h in range(168):
            sel = how == h
            self.prof[h] = np.percentile(hist[sel], 95, axis=0) if sel.any() else 0
        self.P = np.ceil(self.param * self.prof)

    def decide(self, k, tel):
        how = ((self.ctx.week_start + k * self.cfg.epoch_min) // 60) % 168
        return self.P[how], self.cfg.default_mem


class Reactive(Policy):
    """Target tracking: max concurrency of the last 5 visible minutes / u. Scale-out at
    once; scale-in only after 3 consecutive epochs below the current level, by at most
    10 % per epoch (floor, so pools drain; ASSUMPTION D25)."""
    family = "Reactive"

    def prepare(self, ctx):
        super().prepare(ctx)
        self.cur = None
        self.below = 0

    def decide(self, k, tel):
        v = self._visible(k)
        lo = v - 4
        if lo >= 0:
            Kwin = tel.K[lo:v + 1]
        else:  # pre-week minutes from history at default memory
            pre = self.ctx.K_hist_default[self.ctx.week_start + lo:self.ctx.week_start]
            Kwin = np.vstack([pre, tel.K[0:max(v + 1, 0)]])
        target = np.ceil(Kwin.max(0) / self.param - 1e-9)
        if self.cur is None:
            self.cur = target
        elif np.any(target > self.cur):
            self.cur = np.maximum(self.cur, target)
            self.below = 0
        elif np.any(target < self.cur):
            self.below += 1
            if self.below >= 3:
                self.cur = np.maximum(target, np.floor(0.9 * self.cur))
        else:
            self.below = 0
        return self.cur.copy(), self.cfg.default_mem


class _ForecastPolicy(Policy):
    fc_name = "gbm"

    def __init__(self, param=None, fc_name="gbm", hysteresis=None):
        super().__init__(param)
        self.fc_name = fc_name
        self.hyst = hysteresis

    def prepare(self, ctx):
        super().prepare(ctx)
        self.fc = ctx.forecasts[self.fc_name]
        self.prev = np.zeros(self.cfg.n_stages)

    def _smooth(self, P):
        if self.hyst:
            P = np.maximum(P, np.floor(self.hyst * self.prev))
        self.prev = P
        return P


class PredHead(_ForecastPolicy):
    """Median forecast x headroom h; 1024 MB. Scale-in rule only if hysteresis given (D17)."""
    family = "PredHead"

    @property
    def variant(self):
        return f"PredHead{'+hyst' if self.hyst else ''}" + ("" if self.fc_name == "gbm" else f"[{self.fc_name}]")

    def decide(self, k, tel):
        y = self.param * self.fc["q_cal"][k, 1]
        return self._smooth(np.ceil(y * self.d / 60.0 - 1e-9)), self.cfg.default_mem


class QuantProv(_ForecastPolicy):
    """P_s = ceil(a q_tau d_s(1024)/60) from the calibrated quantile, with the PRISM
    scale-in rule (§V-C, Eq. (18))."""
    family = "QuantProv"

    def __init__(self, tau_idx: int, a: float, fc_name="gbm"):
        super().__init__(a, fc_name, hysteresis=0.85)
        self.tau_idx = tau_idx

    @property
    def variant(self):
        tau = {2: "q90", 3: "q99"}[self.tau_idx]
        return f"QuantProv_{tau}" + ("" if self.fc_name == "gbm" else f"[{self.fc_name}]")

    def decide(self, k, tel):
        y = self.param * self.fc["q_cal"][k, self.tau_idx]
        return self._smooth(np.ceil(y * self.d / 60.0 - 1e-9)), self.cfg.default_mem


class PRISM(Policy):
    family = "PRISM"

    def __init__(self, pcfg: PrismConfig, fc_name="gbm", oracle=False, tag=""):
        super().__init__(pcfg.eps)
        self.pcfg, self.fc_name, self.oracle, self.tag = pcfg, fc_name, oracle, tag

    @property
    def variant(self):
        base = "Oracle" if self.oracle else ("PRISM_EB" if self.pcfg.risk_model == "erlangb" else "PRISM")
        return f"{base}{self.tag}" + ("" if self.fc_name == "gbm" else f"[{self.fc_name}]")

    def prepare(self, ctx):
        super().prepare(ctx)
        self.opt = ChanceConstrainedOptimizer(self.cfg, self.pcfg, ctx.r_mean_peak)
        fc = ctx.forecasts[self.fc_name]
        self.q = fc["q_cal"] if self.pcfg.use_conformal else fc["q_raw"]
        self.y = fc["y"]
        self.mem = self.cfg.default_mem
        self.prev = np.zeros(self.cfg.n_stages)
        self.kappa = self.pcfg.kappa_prior
        self.cum_overflow = 0.0
        self.last_seen = -1
        E = ctx.n_epochs
        self.rec = dict(feasible=np.ones(E, bool), excess=np.zeros(E), kappa=np.zeros(E),
                        level=np.zeros(E))

    def _update_kappa(self, k, tel):
        v = self._visible(k)
        lo = self.last_seen + 1
        if v >= lo and v >= 0:
            lo = max(lo, 0)
            od = tel.n_od[lo:v + 1].sum()
            cold = tel.cold[lo:v + 1].sum()
            self.cum_overflow += od
            if od > 0 and self.cum_overflow >= self.pcfg.kappa_min_overflow:
                a = self.pcfg.kappa_alpha
                self.kappa = (1 - a) * self.kappa + a * (cold / od)
                self.kappa = float(np.clip(self.kappa, *self.pcfg.kappa_clip))
            self.last_seen = v

    def decide(self, k, tel):
        pc = self.pcfg
        self._update_kappa(k, tel)
        if self.oracle:
            scen = np.full(pc.n_scenarios, float(self.y[k]))
        else:
            scen = make_scenarios(self.q[k], pc.n_scenarios)
        if pc.optimise_memory and k % pc.memory_every == 0:
            mems = self.cfg.mem_options
        else:
            mems = (self.mem,)
        dec = self.opt.decide(scen, mems, self.kappa)
        P = dec.P.astype(float)
        if pc.use_hysteresis and dec.mem == self.mem:
            P = np.maximum(P, np.floor(pc.hysteresis * self.prev))
        if pc.cap is not None:
            P = np.minimum(P, pc.cap)
        self.prev, self.mem = P, dec.mem
        self.rec["feasible"][k] = dec.feasible
        self.rec["excess"][k] = dec.excess
        self.rec["kappa"][k] = self.kappa
        self.rec["level"][k] = dec.level
        return P, dec.mem

    def info(self):
        r = self.rec
        return dict(infeasible_share=float(1 - r["feasible"].mean()),
                    mean_excess_infeasible=float(r["excess"][~r["feasible"]].mean()) if (~r["feasible"]).any() else 0.0,
                    max_excess=float(r["excess"].max()), kappa_mean=float(r["kappa"].mean()),
                    feasible_epoch=r["feasible"], excess_epoch=r["excess"].astype(np.float32),
                    kappa_epoch=r["kappa"].astype(np.float32))
