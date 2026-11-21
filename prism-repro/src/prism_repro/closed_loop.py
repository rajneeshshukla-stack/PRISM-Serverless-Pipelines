"""Closed-loop control for the event-level simulator (R2.2, R6.3). SIMULATION ONLY.

`des.simulate_events(cfg, draws, controller=...)` asks a controller for each epoch's decision after showing it the
telemetry observed so far. This module supplies the controllers:

* `PolicyController` drives any fast-simulator policy (policies.PRISM, QuantProv, Reactive, ...) unchanged: its
  `prepare(ctx)` and `decide(k, tel)` are called as in simulator.simulate, with `tel` the event-level telemetry.
  What the policy can reach is restricted to the past. Its context holds no trace counts and only the pre-week part
  of the history concurrency; its forecasts are not the precomputed schedule but arrays filled epoch by epoch by
  `OnlineForecast` from the arrivals observed in the telemetry, and its cold-hit estimate (PRISM) reads the
  event-level overflow and cold starts through `tel` as it would in the fast simulator.
* `ScheduleController` replays a fixed schedule; closed-loop replay of a schedule is byte-identical to the open loop.

Nothing here changes a forecaster, the optimiser, the risk model or a constant: the trained forecasting models and
the conformal update rule (forecast.ConformalScaler, Eq. (13)) are the bundle's, stepped online.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

from .config import PipelineConfig
from .experiment import FORECASTERS, WEEK_START, TraceBundle
from .features import FeatureBuilder, forecast_horizon, min_feedback_delay
from .forecast import ConformalScaler, QuantileGBM, RatioQuantileForecaster, calibrate


@dataclass
class ClosedLoopContext:
    """What a policy's prepare(ctx) may use in closed loop: past information only."""
    cfg: PipelineConfig
    week_start: int
    K_hist_default: np.ndarray            # history concurrency, minutes before the week only
    forecasts: Dict[str, dict] = field(default_factory=dict)
    r_mean_peak: float = 0.8
    n_epochs: int = 0
    bill_init: bool = True


class OnlineForecast:
    """A bundle forecaster run online. At decision k (global minute t = week_start + k*E - L) it sees the pre-week
    history and the arrivals the telemetry has shown, nothing later: the feature builder is given a counts array that
    ends at minute t. The conformal offset follows Eq. (13) as forecast.ConformalScaler.run does, but each outcome
    (the realised window peak of an earlier epoch) is read from those observed arrivals once it is observable.
    `arrays` (q_raw, q_cal, s, y) is what the policy reads; entries are filled at decision time (y when observed).

    Initial state: for the test week, the offset and the not-yet-applied outcomes carried over from the validation
    week as the bundle's continuous replay leaves them (past information); for the validation week, the configured
    initial offset (no warm-up)."""

    def __init__(self, bundle: TraceBundle, scenario: str, week: str, name: str, cfg: PipelineConfig, n_epochs: int):
        self.spec, self.model = FORECASTERS[name], bundle.models[name]
        self.ws = WEEK_START[week]
        sc_eff = bundle.scenarios[0] if week == "val" else scenario
        self.hist = bundle.traces[sc_eff]["counts"][:self.ws].astype(float)
        self.trigger = bundle.trigger_minutes
        self.E, self.L = cfg.epoch_min, cfg.lag_min
        self.h_lo, self.h_hi = forecast_horizon(cfg)
        pc = bundle.pc
        self.scaler = ConformalScaler(pc.gamma, pc.target_miss, pc.s_min, pc.s_max,
                                      max(pc.conformal_delay_epochs, min_feedback_delay(cfg)),
                                      per_quantile=pc.conformal_per_quantile)
        self.cfg = cfg
        K = n_epochs
        width = 2 if pc.conformal_per_quantile else None
        self.arrays = dict(q_raw=np.full((K, 4), np.nan), q_cal=np.full((K, 4), np.nan),
                           s=np.full((K, 2) if width else K, np.nan), y=np.full(K, np.nan))
        self.pending = []                    # (epoch index relative to this week, U) not yet resolved
        if week == "test":
            v = bundle.forecasts[(scenario, "val", name)]
            s_val, q_val = v["s"], v["q_raw"]
            Kv = len(s_val)
            self.s = np.array(s_val[-1], float) if width else float(s_val[-1])
            for j in range(Kv - self.scaler.delay, Kv):     # validation epochs whose outcomes are still pending
                self.pending.append((j - Kv, self._upper(q_val[j], s_val[j])))
        else:
            if pc.conformal_warmup_days:
                raise NotImplementedError("closed loop on the validation week with a conformal warm-up")
            self.s = np.full(2, pc.conformal_s0) if width else float(pc.conformal_s0)

    def _upper(self, q_row, s):
        if self.scaler.per_quantile:
            return q_row[2:4] * np.exp(np.asarray(s, float))
        return q_row[3] * np.exp(float(s))

    def _predictor(self, counts):
        spec = self.spec
        fb = FeatureBuilder(counts, self.trigger, drop_groups=spec.get("drop", ()),
                            normalise=spec.get("normalise", True), horizon=(self.h_lo, self.h_hi))
        if spec["kind"] == "gbm":
            p = QuantileGBM(fb)
            p.models = self.model.models
        else:
            p = RatioQuantileForecaster(fb, spec["kind"])
            p.ratio_q = self.model.ratio_q
        return p

    def step(self, k: int, tel) -> None:
        v = k * self.E - self.L                                  # last observed minute of the week
        t = self.ws + v                                          # the same minute in trace time
        if v >= 0:
            seen = tel.N[:v + 1]
            if not np.all(np.isfinite(seen)):
                raise RuntimeError(f"epoch {k}: arrivals up to minute {v} are not all observed")
            counts = np.concatenate([self.hist, seen])
        else:
            counts = self.hist[:self.ws + v + 1]
        sc, a = self.scaler, self.arrays
        while self.pending and self.pending[0][0] <= k - sc.delay:   # outcomes now observable (Eq. (13) delay)
            j, U = self.pending.pop(0)
            tj = self.ws + j * self.E - self.L
            if tj + self.h_hi > t:
                raise RuntimeError(f"epoch {k}: outcome of epoch {j} is not observable yet")
            y = float(counts[tj + self.h_lo:tj + self.h_hi + 1].max())
            if j >= 0:
                a["y"][j] = y
            if np.isfinite(y):
                if sc.per_quantile:
                    tgt = np.array([sc.target_q90, sc.target])
                    self.s = np.clip(self.s + sc.gamma * ((y > U) - tgt), sc.s_min, sc.s_max)
                else:
                    self.s = float(np.clip(self.s + sc.gamma * ((y > U) - sc.target), sc.s_min, sc.s_max))
        q = self._predictor(counts).predict(np.array([t]))[0]
        a["q_raw"][k] = q
        a["s"][k] = self.s
        a["q_cal"][k] = calibrate(q[None, :], a["s"][k:k + 1])[0]
        self.pending.append((k, self._upper(q, self.s)))


class PolicyController:
    """Drive a fast-simulator policy from event-level telemetry (closed loop). `scenario` and `week` select the
    bundle's history and conformal carry-over; the event draws must be of the same trace-week."""

    def __init__(self, policy, bundle: TraceBundle, scenario: str, week: str = "test"):
        if getattr(policy, "oracle", False):
            raise ValueError("the oracle reads the realised demand of the epoch it decides; it has no closed loop")
        self.policy, self.bundle, self.scenario, self.week = policy, bundle, scenario, week
        self.forecasts = {}

    def start(self, cfg: PipelineConfig, n_min: int, n_epochs: int) -> None:
        b = self.bundle
        if (cfg.epoch_min, cfg.lag_min) != (b.cfg.epoch_min, b.cfg.lag_min):
            raise ValueError("the event configuration's epoch and lag must be the bundle's (forecast horizon)")
        ws = WEEK_START[self.week]
        sc_eff = b.scenarios[0] if self.week == "val" else self.scenario
        used = getattr(self.policy, "fc_name", None)      # the forecaster the policy reads, if any
        if used is not None and used not in b.fc_names:
            raise ValueError(f"policy reads forecaster {used!r}, which the bundle did not train")
        names = () if used is None else (used,)
        self.forecasts = {nm: OnlineForecast(b, self.scenario, self.week, nm, cfg, n_epochs) for nm in names}
        ctx = ClosedLoopContext(cfg=cfg, week_start=ws, K_hist_default=b.K_hist(sc_eff)[:ws].copy(),
                                forecasts={nm: f.arrays for nm, f in self.forecasts.items()},
                                r_mean_peak=b.r_mean_peak, n_epochs=n_epochs)
        self.policy.prepare(ctx)

    def decide(self, k: int, tel):
        for f in self.forecasts.values():
            f.step(k, tel)
        return self.policy.decide(k, tel)


class ScheduleController:
    """Replays a fixed schedule through the closed loop (ignores the telemetry)."""

    def __init__(self, P_epoch, mem_epoch):
        self.P, self.mem = np.asarray(P_epoch, float), np.asarray(mem_epoch)

    def decide(self, k: int, tel):
        return self.P[k], int(self.mem[k])
