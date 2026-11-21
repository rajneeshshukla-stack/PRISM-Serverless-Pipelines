"""Latency and memory-scaling model (§III-A, Eqs. (2)-(3), Supplementary Table S1) and Monte Carlo
estimation of the warm miss probability v_w(m) and cold miss probability rho(m)
(§III-C)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.special import ndtr, ndtri

from .config import PipelineConfig


def duration_factor(m: float, nonscaling: float) -> float:
    """Eq. (2) scaling factor relative to 1024 MB."""
    if m <= 0:
        raise ValueError("memory must be positive")
    return nonscaling + (1.0 - nonscaling) * 1024.0 / m


def stage_means(cfg: PipelineConfig, m: float) -> np.ndarray:
    """Mean warm execution time per stage (s) at memory m."""
    return np.asarray(cfg.warm_mean_1024, float) * duration_factor(m, cfg.nonscaling)


def init_factor(cfg: PipelineConfig, m: float) -> float:
    """Init-vs-memory factor relative to 1024 MB under cfg.init_scaling (R1.2, R5.M2)."""
    mode = cfg.init_scaling
    if mode == "eq3":
        return duration_factor(m, cfg.init_nonscaling)
    if mode == "constant":
        return 1.0
    if mode == "inverted":
        return 1.0 / duration_factor(m, cfg.init_nonscaling)
    raise ValueError(f"init_factor undefined for init_scaling={mode!r}")


def _init_untruncated_mean(cfg: PipelineConfig, m: float) -> float:
    if cfg.init_scaling == "measured":
        return float(dict(cfg.init_mean_measured)[int(m)])
    return cfg.init_mean_1024 * init_factor(cfg, m)


def _init_cap_z(cfg: PipelineConfig, m: float) -> float:
    """Standard-normal quantile of the cap init_max_s under the untruncated log-normal."""
    mu, s = _init_untruncated_mean(cfg, m), cfg.init_shape
    return (np.log(cfg.init_max_s / mu) + 0.5 * s * s) / s


def init_mean(cfg: PipelineConfig, m: float) -> float:
    """Mean initialisation time (s) at memory m; the truncated mean when init_max_s is set (R4.8)."""
    mu = _init_untruncated_mean(cfg, m)
    if cfg.init_max_s is None or mu == 0 or cfg.init_shape == 0:
        return mu if cfg.init_max_s is None else min(mu, cfg.init_max_s)
    zc = _init_cap_z(cfg, m)
    return float(mu * ndtr(zc - cfg.init_shape) / ndtr(zc))


def init_seconds(cfg: PipelineConfig, mult, m: float) -> np.ndarray:
    """Initialisation times (s) from mean-one log-normal multipliers `mult` at memory m.

    Without init_max_s this is init_mean(m) * mult (the submitted model). With it, each
    multiplier is mapped through the inverse CDF of the log-normal truncated at init_max_s
    (R4.8): u = Phi(z) becomes u * Phi(z_cap). The map is monotone, so common random numbers
    across policies and memory sizes are preserved, and no draw exceeds the cap."""
    mult = np.asarray(mult)
    mu = _init_untruncated_mean(cfg, m)
    if cfg.init_max_s is None:
        return mu * mult
    s = cfg.init_shape
    if mu == 0 or s == 0:
        return np.minimum(mu * mult.astype(np.float64), cfg.init_max_s)
    z = (np.log(mult.astype(np.float64)) + 0.5 * s * s) / s
    zt = ndtri(ndtr(z) * ndtr(_init_cap_z(cfg, m)))
    return np.minimum(mu * np.exp(s * zt - 0.5 * s * s), cfg.init_max_s)


def gb(m: float) -> float:
    return m / 1024.0


def lognormal_mult(z: np.ndarray, sigma: float) -> np.ndarray:
    """Mean-one log-normal multiplier exp(sigma z - sigma^2/2) (D01)."""
    return np.exp(sigma * z - 0.5 * sigma * sigma)


def poisson_binomial(p: np.ndarray) -> np.ndarray:
    """PMF of the number of successes for independent, non-identical Bernoullis.

    p has shape (..., S); returns (..., S+1)."""
    S = p.shape[-1]
    w = np.zeros(p.shape[:-1] + (S + 1,), dtype=np.float64)
    w[..., 0] = 1.0
    for s in range(S):
        ps = p[..., s][..., None]
        nxt = np.zeros_like(w)
        nxt[..., 0] = w[..., 0] * (1.0 - ps[..., 0])
        nxt[..., 1:] = w[..., 1:] * (1.0 - ps) + w[..., :-1] * ps
        w = nxt
    return w


_ATTAIN_CACHE: dict = {}


def attainment_table(cfg, m: int) -> np.ndarray:
    """P(latency <= deadline | exactly k stages cold) at memory m, for k = 0..S (R5.M1).

    The per-stage initialisation multipliers are i.i.d. and init_mean(m) does not depend on
    the stage, so the latency distribution depends on the cold-start pattern only through the
    NUMBER of cold stages. That makes exact attainment a weighted sum over S+1 cases rather
    than a sample of requests. The conditional probabilities are estimated once, at high
    precision, from a fixed seed; the per-minute sampling noise of the previous approach is
    removed entirely.
    """
    key = (int(m), cfg.n_stages, tuple(cfg.warm_mean_1024), cfg.exec_shape, cfg.overhead_mean,
           cfg.overhead_shape, cfg.init_mean_1024, cfg.init_shape, cfg.nonscaling,
           cfg.init_nonscaling, cfg.deadline, cfg.exact_attainment_draws, cfg.init_max_s,
           cfg.init_scaling, cfg.init_mean_measured)
    hit = _ATTAIN_CACHE.get(key)
    if hit is not None:
        return hit
    S, n = cfg.n_stages, int(cfg.exact_attainment_draws)
    rng = np.random.default_rng([20261120, int(m)])
    X = lognormal_mult(rng.standard_normal((n, S)), cfg.exec_shape)
    Y = cfg.overhead_mean * lognormal_mult(rng.standard_normal((n, S)), cfg.overhead_shape)
    I = lognormal_mult(rng.standard_normal((n, S)), cfg.init_shape)
    warm = (X * stage_means(cfg, m)).sum(-1) + Y.sum(-1)
    if cfg.init_max_s is None:   # submitted model, kept bit-identical
        icum = init_mean(cfg, m) * np.concatenate([np.zeros((n, 1)), np.cumsum(I, axis=1)], axis=1)
    else:                        # R4.8: truncate each stage's init before summing
        icum = np.concatenate([np.zeros((n, 1)), np.cumsum(init_seconds(cfg, I, m), axis=1)], axis=1)
    out = np.array([float((warm + icum[:, k] <= cfg.deadline).mean()) for k in range(S + 1)])
    _ATTAIN_CACHE[key] = out
    return out


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
    init = init_seconds(cfg, lognormal_mult(rng.standard_normal(n), cfg.init_shape), m)
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
            "init_shape", "nonscaling", "init_nonscaling", "deadline", "init_max_s",
            "init_scaling", "init_mean_measured")
    items = tuple((k, getattr(cfg, k)) for k in keys)
    return {m: _miss_cached((items, m)) for m in cfg.mem_options}
