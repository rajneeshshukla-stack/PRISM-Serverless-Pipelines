"""Controller overhead (§VI-J; Supplement S9): times the complete online decision cycle — feature
vector from raw arrival history, four quantile models, kappa update, conformal update,
scenario generation and optimisation — over every epoch of one test week. Also checks
that online forecasts equal the batch forecasts used in the experiments."""
from __future__ import annotations

import time

import numpy as np

from .config import PipelineConfig, PrismConfig
from .experiment import TraceBundle
from .features import online_features
from .forecast import TAUS, ConformalScaler, calibrate, cummax_rows, scenarios
from .optimizer import ChanceConstrainedOptimizer


def measure_overhead(seed: int, eps: float = 0.05, scenario: str = "stationary"):
    cfg, pc = PipelineConfig(), PrismConfig(eps=eps)
    b = TraceBundle(seed, cfg, scenarios=(scenario,))
    model = b.models["gbm"]
    fc = b.forecasts[(scenario, "test", "gbm")]
    counts = b.traces[scenario]["counts"]
    opt = ChanceConstrainedOptimizer(cfg, pc, b.r_mean_peak)
    cs = ConformalScaler(pc.gamma, pc.target_miss, pc.s_min, pc.s_max, pc.conformal_delay_epochs)
    ts = fc["ts"]
    K = len(ts)
    t_total, t_fc, t_opt = np.zeros(K), np.zeros(K), np.zeros(K)
    q_online = np.zeros((K, 4))
    s = float(fc["s"][0])  # offset carried over from the validation week (as in the batch run)
    pending = []
    kappa, mem = pc.kappa_prior, cfg.default_mem
    rng = np.random.default_rng(0)
    for k in range(K):
        t0 = time.perf_counter()
        # telemetry & kappa update (synthetic telemetry values; the arithmetic is what is timed)
        od, cold = rng.uniform(0, 500), rng.uniform(0, 50)
        kappa = float(np.clip(0.9 * kappa + 0.1 * cold / max(od, 1e-9), 0.1, 1.0))
        t1 = time.perf_counter()
        x, lev = online_features(counts, int(ts[k]), b.trigger_minutes)
        q = np.array([model.models[tau].predict(x[None, :])[0] for tau in TAUS]) * lev
        q = cummax_rows(np.maximum(q, 0.0))
        t2 = time.perf_counter()
        while pending and pending[0][0] <= k - cs.delay:
            j, U = pending.pop(0)
            s = float(np.clip(s + cs.gamma * ((fc["y"][j] > U) - cs.target), cs.s_min, cs.s_max))
        qc = calibrate(q[None, :], np.array([s]))[0]
        pending.append((k, q[3] * np.exp(s)))
        sc = scenarios(qc, pc.n_scenarios)
        mems = cfg.mem_options if k % pc.memory_every == 0 else (mem,)
        d = opt.decide(sc, mems, kappa)
        mem = d.mem
        t3 = time.perf_counter()
        q_online[k] = q
        t_total[k], t_fc[k], t_opt[k] = t3 - t0, t2 - t1, t3 - t2
    rel = np.abs(q_online - fc["q_raw"]) / np.maximum(np.abs(fc["q_raw"]), 1e-9)
    ms = lambda a, p: float(np.quantile(a, p) * 1e3)
    row = dict(seed=seed, scenario=scenario, epochs=K, total_ms_median=ms(t_total, 0.5),
               total_ms_p99=ms(t_total, 0.99), total_ms_max=float(t_total.max() * 1e3),
               forecast_ms_median=ms(t_fc, 0.5), forecast_ms_p99=ms(t_fc, 0.99),
               optimise_ms_median=ms(t_opt, 0.5), optimise_ms_p99=ms(t_opt, 0.99),
               online_vs_batch_max_rel_diff=float(rel.max()),
               online_equals_batch_identical=bool(rel.max() < 1e-9),
               busy_fraction_at_5min=float(np.median(t_total) / 300.0), synthetic=True)
    return row, dict(t_total=t_total.astype(np.float32), t_forecast=t_fc.astype(np.float32))
