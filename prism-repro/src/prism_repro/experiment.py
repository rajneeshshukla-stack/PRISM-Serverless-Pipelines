"""Experiment orchestration: builds SYNTHETIC trace bundles, trains forecasters on the
training split only, produces per-epoch forecasts for validation/test weeks, creates
simulation contexts and policies, and implements the §V-C tuning rule."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np

from .config import PipelineConfig, PrismConfig
from .features import FeatureBuilder
from .forecast import ConformalScaler, QuantileGBM, RatioQuantileForecaster
from .policies import PRISM, OnDemand, PredHead, QuantProv, Reactive, Scheduled, Static
from .simulator import WEEK, SimContext, WeekDraws, simulate
from .workload import MAIN_SCENARIOS, MIN_PER_DAY, WorkloadParams, generate_trace

WEEK_START = {"val": 14 * MIN_PER_DAY, "test": 21 * MIN_PER_DAY}
WEEK_INDEX = {"val": 2, "test": 3}

FORECASTERS = {
    "gbm": dict(kind="gbm"),
    "gbm_no_trigger": dict(kind="gbm", drop=("trigger",)),
    "gbm_no_prevday": dict(kind="gbm", drop=("prevday",)),
    "gbm_no_norm": dict(kind="gbm", normalise=False),
    "seasonal_naive": dict(kind="seasonal_naive"),
    "last5max": dict(kind="last5max"),
    "ewma": dict(kind="ewma"),
}


def sha256_array(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


class KDraws:
    """Light draws (peak concurrency only) for history weeks; identical stream prefix
    to WeekDraws so values coincide."""

    def __init__(self, cfg, seed, week_index):
        rng = np.random.default_rng([seed, 100 + week_index])
        self.u_peak = rng.uniform(1 - cfg.peak_upper_frac, 1.0, size=(WEEK, cfg.n_stages))
        self.z_int = rng.standard_normal(WEEK)
        self.cfg = cfg

    peak_concurrency = WeekDraws.peak_concurrency


class TraceBundle:
    def __init__(self, seed: int, cfg: PipelineConfig, wparams: WorkloadParams | None = None,
                 scenarios=MAIN_SCENARIOS, forecasters=("gbm",), conformal: PrismConfig | None = None):
        self.seed, self.cfg = seed, cfg
        self.wp = wparams or WorkloadParams()
        self.scenarios = tuple(scenarios)
        self.traces = {sc: generate_trace(seed, sc, self.wp) for sc in self.scenarios}
        base = self.traces[self.scenarios[0]]
        for sc in self.scenarios[1:]:  # first 21 days identical by construction
            assert np.array_equal(self.traces[sc]["counts"][:21 * MIN_PER_DAY], base["counts"][:21 * MIN_PER_DAY])
        self.trigger_minutes = base["trigger_minutes_known"]
        self.pc = conformal or PrismConfig()
        self.fc_names = tuple(forecasters)
        self._draws = {}
        self._khist = {}
        self.forecasts = {}  # (scenario, week, fc_name) -> dict
        self.forecast_quality = {}
        self.models = {}
        self._train_forecasters()

    # ---------------- forecasting ----------------
    def _builder(self, counts, spec):
        return FeatureBuilder(counts, self.trigger_minutes, drop_groups=spec.get("drop", ()),
                              normalise=spec.get("normalise", True))

    def _train_forecasters(self):
        train_hi = 14 * MIN_PER_DAY
        sc0 = self.scenarios[0]
        fb0 = self._builder(self.traces[sc0]["counts"], {})
        ts = np.arange(fb0.min_t, train_hi - 6)
        self.r_mean_peak = float(np.mean(fb0.ymean[ts] / np.maximum(fb0.y[ts], 1)))
        for name in self.fc_names:
            spec = FORECASTERS[name]
            fb = self._builder(self.traces[sc0]["counts"], spec)
            if spec["kind"] == "gbm":
                model = QuantileGBM(fb).fit(0, train_hi)
            else:
                model = RatioQuantileForecaster(fb, spec["kind"]).fit(0, train_hi)
            self.models[name] = model
            for sc in self.scenarios:
                fbs = self._builder(self.traces[sc]["counts"], spec)
                if spec["kind"] == "gbm":
                    pred = QuantileGBM(fbs)
                    pred.models = model.models
                else:
                    pred = RatioQuantileForecaster(fbs, spec["kind"])
                    pred.ratio_q = model.ratio_q
                ts_val = (WEEK_START["val"] + np.arange(WEEK // self.cfg.epoch_min) * self.cfg.epoch_min
                          - self.cfg.lag_min)
                ts_all = np.concatenate([ts_val, ts_val + WEEK])
                q_raw = pred.predict(ts_all)
                y = fbs.target(ts_all)
                cs = ConformalScaler(self.pc.gamma, self.pc.target_miss, self.pc.s_min, self.pc.s_max,
                                     self.pc.conformal_delay_epochs)
                q_cal, s_used, rev = cs.run(q_raw, y)
                K = len(ts_val)
                for wk, sl in (("val", slice(0, K)), ("test", slice(K, 2 * K))):
                    self.forecasts[(sc, wk, name)] = dict(q_raw=q_raw[sl], q_cal=q_cal[sl], s=s_used[sl],
                                                         y=y[sl], ts=ts_all[sl], reversals=rev)

    # ---------------- simulation contexts ----------------
    def draws(self, week_index):
        if week_index not in self._draws:
            self._draws[week_index] = WeekDraws(self.cfg, self.seed, week_index)
        return self._draws[week_index]

    def K_hist(self, scenario):
        if scenario not in self._khist:
            counts = self.traces[scenario]["counts"].astype(float)
            parts = []
            for w in range(4):
                kd = KDraws(self.cfg, self.seed, w) if w not in self._draws else self._draws[w]
                parts.append(kd.peak_concurrency(counts[w * WEEK:(w + 1) * WEEK], self.cfg.default_mem))
            self._khist[scenario] = np.vstack(parts)
        return self._khist[scenario]

    def context(self, scenario, week, bill_init=True) -> SimContext:
        sc_eff = self.scenarios[0] if week == "val" else scenario
        ctx = SimContext(cfg=self.cfg, counts=self.traces[sc_eff]["counts"], week_start=WEEK_START[week],
                         draws=self.draws(WEEK_INDEX[week]), K_hist_default=self.K_hist(sc_eff),
                         r_mean_peak=self.r_mean_peak, bill_init=bill_init)
        ctx.forecasts = {n: self.forecasts[(sc_eff, week, n)] for n in self.fc_names}
        return ctx

    def data_checksum(self, scenario):
        return sha256_array(self.traces[scenario]["counts"])


# ---------------- policies ----------------
GRIDS = {
    "Static": [50, 60, 70, 80, 90, 95, 97, 99, 99.5, 99.9],
    "Scheduled": [1.0, 1.2, 1.4, 1.6, 1.8, 2.0],
    "Reactive": [round(0.40 + 0.05 * i, 2) for i in range(11)],
    "PredHead": [round(1.0 + 0.1 * i, 1) for i in range(11)],
    "PRISM": [0.005, 0.01, 0.02, 0.03, 0.05, 0.08],
    "QuantProv": [round(0.6 + 0.1 * i, 1) for i in range(10)],  # ASSUMPTION D16
}


def make_policy(spec: dict, pcfg_base: PrismConfig | None = None):
    fam = spec["family"]
    p = spec.get("param")
    fc = spec.get("fc", "gbm")
    if fam == "OnDemand":
        return OnDemand()
    if fam == "Static":
        return Static(p)
    if fam == "Scheduled":
        return Scheduled(p)
    if fam == "Reactive":
        return Reactive(p)
    if fam == "PredHead":
        return PredHead(p, fc, hysteresis=0.85 if spec.get("hyst") else None)
    if fam == "QuantProv":
        return QuantProv(spec["tau_idx"], p, fc)
    if fam in ("PRISM", "Oracle"):
        base = pcfg_base or PrismConfig()
        pc = base.with_(eps=p, **spec.get("prism", {}))
        return PRISM(pc, fc, oracle=(fam == "Oracle"), tag=spec.get("tag", ""))
    raise ValueError(fam)


def run_policy(bundle: TraceBundle, scenario: str, week: str, spec: dict, pcfg_base=None, bill_init=True):
    ctx = bundle.context(scenario, week, bill_init)
    pol = make_policy(spec, pcfg_base)
    res = simulate(ctx, pol)
    s = res["summary"]
    s.update(seed=bundle.seed, scenario=scenario if week == "test" else "validation", week=week,
             spec=json.dumps(spec, sort_keys=True), data_sha256=bundle.data_checksum(
                 bundle.scenarios[0] if week == "val" else scenario))
    return res


def select_by_rule(rows, threshold=0.02, key_cost="cost", key_viol="violating_window_rate"):
    """§V-C: cheapest configuration with violating-window rate <= threshold on
    validation; if none qualifies, the least violating (ties -> cheaper)."""
    ok = [r for r in rows if r[key_viol] <= threshold + 1e-12]
    if ok:
        return min(ok, key=lambda r: (r[key_cost], r[key_viol]))
    return min(rows, key=lambda r: (r[key_viol], r[key_cost]))
