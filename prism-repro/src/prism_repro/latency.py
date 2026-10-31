"""Latency and memory-scaling model (§III-A, Eqs. (2)-(3), Supplementary Table S1) and Monte Carlo
estimation of the warm miss probability v_w(m) and cold miss probability rho(m)
(§III-C)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import PipelineConfig


def duration_factor(m: float, nonscaling: float) -> float:
    """Eq. (2) scaling factor relative to 1024 MB."""
    if m <= 0:
        raise ValueError("memory must be positive")
    return nonscaling + (1.0 - nonscaling) * 1024.0 / m


def stage_means(cfg: PipelineConfig, m: float) -> np.ndarray:
    """Mean warm execution time per stage (s) at memory m."""
    return np.asarray(cfg.warm_mean_1024, float) * duration_factor(m, cfg.nonscaling)


def init_mean(cfg: PipelineConfig, m: float) -> float:
    return cfg.init_mean_1024 * duration_factor(m, cfg.init_nonscaling)


def gb(m: float) -> float:
    return m / 1024.0


def lognormal_mult(z: np.ndarray, sigma: float) -> np.ndarray:
    """Mean-one log-normal multiplier exp(sigma z - sigma^2/2) (D01)."""
    return np.exp(sigma * z - 0.5 * sigma * sigma)


def miss_probabilities(cfg: PipelineConfig, m: float, n: int = 400_000, seed: int = 12345):
    """Monte Carlo v_w(m) and rho(m).

    rho(m): probability that a record with a cold start in exactly one stage misses
    the deadline, averaged uniformly over the stage that is cold (ASSUMPTION D03).
    Returns (v_w, rho, rho_per_stage, mc_standard_error_v_w).
    """
    rng = np.random.default_rng(seed)
    S = cfg.n_stages
    d = stage_means(cfg, m)
    ex = d[None, :] * lognormal_mult(rng.standard_normal((n, S)), cfg.exec_shape)
    ov = cfg.overhead_mean * lognormal_mult(rng.standard_normal((n, S)), cfg.overhead_shape)
    warm = ex.sum(1) + ov.sum(1)
    init = init_mean(cfg, m) * lognormal_mult(rng.standard_normal(n), cfg.init_shape)
    v_w = float(np.mean(warm > cfg.deadline))
    # a cold start in any one stage adds the same init distribution (stage-independent init)
    rho = float(np.mean(warm + init > cfg.deadline))
    se = float(np.sqrt(max(v_w * (1 - v_w), 1e-12) / n))
    return v_w, rho, [rho] * S, se


@lru_cache(maxsize=256)
def _miss_cached(key):
    cfg_items, m = key
    cfg = PipelineConfig(**dict(cfg_items))
    return miss_probabilities(cfg, m)[:2]


def miss_table(cfg: PipelineConfig) -> dict:
    """{m: (v_w, rho)} for all memory options, cached on the latency-relevant fields."""
    keys = ("warm_mean_1024", "exec_shape", "overhead_mean", "overhead_shape", "init_mean_1024",
            "init_shape", "nonscaling", "init_nonscaling", "deadline")
    items = tuple((k, getattr(cfg, k)) for k in keys)
    return {m: _miss_cached((items, m)) for m in cfg.mem_options}
