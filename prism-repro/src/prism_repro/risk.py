"""Overflow and record-violation risk model (§III-B, §III-C, §IV-C; Eqs. (4)-(7), (14)).

Closed forms (K ~ Poisson(c)):
  occupancy  o(P,c) = E[(K-P)+]/c = P(K>=P) - (P/c) P(K>P)
  Erlang-B   B(P,c) = pmf(P;c)/cdf(P;c)
Both are validated against brute-force summation in tests/test_analytic.py (TestOverflowFormulas).
"""
from __future__ import annotations

import numpy as np
from scipy import special


def poisson_sf(k, c):
    """P(K > k) for K~Poisson(c); k may be negative (returns 1)."""
    k = np.asarray(k, float)
    c = np.asarray(c, float)
    out = np.where(k < 0, 1.0, special.pdtrc(np.maximum(k, 0), np.maximum(c, 0)))
    return np.where(c <= 0, np.where(k < 0, 1.0, 0.0), out)


def poisson_pmf(k, c):
    k = np.asarray(k, float)
    c = np.asarray(c, float)
    safe_c = np.where(c > 0, c, 1.0)
    val = np.exp(k * np.log(safe_c) - safe_c - special.gammaln(k + 1))
    return np.where(c > 0, val, (k == 0).astype(float))


def occupancy_overflow(P, c):
    """o(P,c) = E[(K-P)+]/c, zero when c == 0.

    Uses sf(P-1) = sf(P) + pmf(P), so o = sf(P)(1 - P/c) + pmf(P): one incomplete-gamma
    evaluation instead of two (tested against brute-force summation)."""
    P = np.asarray(P, float)
    c = np.asarray(c, float)
    safe_c = np.where(c > 0, c, 1.0)
    sf = special.pdtrc(np.maximum(P, 0), safe_c)
    val = sf * (1.0 - P / safe_c) + poisson_pmf(P, safe_c)
    return np.where(c > 0, np.clip(val, 0.0, 1.0), 0.0)


def erlang_b(P, c):
    """Erlang-B blocking B(P,c) = pmf(P;c)/cdf(P;c); B(0,c)=1 for c>0, 0 for c=0."""
    P = np.asarray(P, float)
    c = np.asarray(c, float)
    safe_c = np.where(c > 0, c, 1.0)
    logpmf = P * np.log(safe_c) - safe_c - special.gammaln(P + 1)
    cdf = special.pdtr(P, safe_c)
    val = np.exp(logpmf) / np.maximum(cdf, 1e-300)
    return np.where(c > 0, np.clip(val, 0.0, 1.0), 0.0)


def erlang_b_recursive(P: int, c: float) -> float:
    """Reference implementation via the standard recursion (oracle for tests)."""
    b = 1.0
    for k in range(1, int(P) + 1):
        b = c * b / (k + c * b)
    return b if c > 0 else 0.0


def c_eff(c):
    """Effective peak mean used by the optimiser (§IV-C, Eq. (14))."""
    c = np.asarray(c, float)
    return 1.011 * c + 0.88 * np.sqrt(np.maximum(c, 0.0))


def overflow_prob(P, c, model: str = "occupancy", use_ceff: bool = True):
    """Per-stage overflow fraction f_s used in Eq. (6).

    model='occupancy' reproduces the paper's main-experiment risk model (o at c_eff);
    model='erlangb' is PRISM-EB (Supplement S6). The paper does not state whether PRISM-EB
    also uses c_eff; we evaluate Erlang-B at the mean load c (exact for Poisson
    arrivals) unless use_ceff is True (ASSUMPTION D23).
    """
    if model == "occupancy":
        return occupancy_overflow(P, c_eff(c) if use_ceff else c)
    if model == "erlangb":
        return erlang_b(P, c_eff(c) if use_ceff else c)
    raise ValueError(model)


def record_violation(f, kappa: float, v_w: float, rho: float, axis: int = -1):
    """Eqs. (6)-(7): p_c = 1 - prod_s(1 - kappa f_s); v = (1-p_c) v_w + p_c rho."""
    f = np.asarray(f, float)
    p_c = 1.0 - np.prod(1.0 - kappa * f, axis=axis)
    return (1.0 - p_c) * v_w + p_c * rho
