"""OptScaler (Zou et al., PVLDB 17(12), 2024; cited as [16] in the submitted manuscript) as a Table V policy.

Independent implementation from the paper (arXiv 2311.12864v2); no authors' code is released. EXPLORATORY (R3.2).
The mapping assumptions A1-A12 are listed in docs/revision/optscaler_r32_20261124/PLAN.md; their IDs appear below.

Per stage s (A1): P_s = ceil(m / c*) (A9), m = (psi^-1(alpha) sigma_k + w_k) y (eq. 13 with w_b = sigma_b = 0, A3),
y the common median forecast of the controlled window's peak per-minute arrivals (A5, A6). w_k, sigma_k by the
closed-form MLE of eq. (4) on pre-week history (A4); w_k then adjusted by OLR (Algorithm 1, A10).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from prism_repro.policies import Policy

ETA_GRID = (0.0, 1e-5, 1e-4, 2e-4, 1e-3, 5e-3)   # A11
C_STAR_PUBLISHED = 0.5
ALPHA = 0.95


def mle_ratio(K: np.ndarray, y: np.ndarray):
    """A4: MLE of K = w y + e, e ~ N(0, (sigma y)^2), over y > 0. Equivalent to r = K/y ~ N(w, sigma^2)."""
    sel = y > 0
    r = K[sel] / y[sel]
    w = float(r.mean())
    sig = float(np.sqrt(np.mean((r - w) ** 2)))
    return max(w, 0.0), max(sig, 0.0)          # non-negative constraints (both are already >= 0 for K >= 0)


def neg_loglik(params, K, y):
    """Negative log-likelihood of eq. (3)-(4) with w_b = sigma_b = 0 (used by test V1a only)."""
    w, sig = params
    sel = y > 0
    s = sig * y[sel]
    return float(np.sum(np.log(s) + 0.5 * ((K[sel] - w * y[sel]) / s) ** 2))


def olr_step(w, eta, y, x, c_obs):
    """Algorithm 1, one feedback point: c_hat = w y / x; e = c_hat - c; w <- w - eta e y / x."""
    u = y / x
    e = w * u - c_obs
    return w - eta * e * u, e


def provision(w, sig, y, c_star, z):
    """Eq. (13) with A3, rounded up (A9); X^min = 0, no X^max (A7)."""
    m = (z * sig + w) * y
    return np.maximum(np.ceil(m / c_star - 1e-9), 0.0)


def replay_loss(K, y, w0, sig0, eta, z, c_star=C_STAR_PUBLISHED):
    """A11: cumulative squared OLR loss on a history replay provisioned at the published target."""
    w = np.array(w0, float).copy()
    loss = 0.0
    for t in range(len(y)):
        if y[t] <= 0:
            continue
        x = np.maximum(1.0, np.ceil((w0 + z * sig0) * y[t] / c_star - 1e-9))
        c = np.minimum(K[t], x) / x
        w, e = olr_step(w, eta, y[t], x, c)
        loss += float(np.sum(e ** 2))
    return loss


def select_eta(K, y, w0, sig0, z, grid=ETA_GRID):
    losses = {eta: replay_loss(K, y, w0, sig0, eta, z) for eta in grid}
    best = min(grid, key=lambda e: (losses[e], e))
    return best, losses


class OptScaler(Policy):
    family = "OptScaler"

    def __init__(self, c_star, alpha=ALPHA, eta=None, fc_name="gbm"):
        super().__init__(c_star)
        self.alpha, self.eta_fixed, self.fc_name = alpha, eta, fc_name
        self.z = float(stats.norm.ppf(alpha))

    @property
    def variant(self):
        return "OptScaler" if self.alpha == ALPHA else f"OptScaler[a={self.alpha}]"

    def prepare(self, ctx):
        super().prepare(ctx)
        self.fc = ctx.forecasts[self.fc_name]
        ws = ctx.week_start
        y_hist = ctx.counts[:ws].astype(float)
        K_hist = ctx.K_hist_default[:ws]
        S = self.cfg.n_stages
        self.w0, self.sig = np.zeros(S), np.zeros(S)
        for s in range(S):
            self.w0[s], self.sig[s] = mle_ratio(K_hist[:, s], y_hist)
        if self.eta_fixed is None:   # A11: the 14-day forecaster training split
            hi = 14 * 1440
            self.eta, self.eta_losses = select_eta(K_hist[:hi], y_hist[:hi], self.w0, self.sig, self.z)
        else:
            self.eta, self.eta_losses = self.eta_fixed, {}
        self.w = self.w0.copy()
        self.fed_upto = -1          # last week-relative minute already used as OLR feedback

    def _feedback(self, tel, v):
        """A10: Algorithm 1 over visible in-week minutes (fed_upto, v]; skip minutes with P = 0."""
        for t in range(self.fed_upto + 1, v + 1):
            y = tel.N[t]
            if y <= 0:
                continue
            P, K = tel.P[t], tel.K[t]
            on = P > 0
            if not np.any(on):
                continue
            c = np.where(on, np.minimum(K, P) / np.where(on, P, 1.0), 0.0)
            w_new, _ = olr_step(self.w, self.eta, y, np.where(on, P, 1.0), c)
            self.w = np.where(on, w_new, self.w)
        self.fed_upto = max(self.fed_upto, v)

    def decide(self, k, tel):
        v = self._visible(k)
        if v >= 0 and self.eta > 0:
            self._feedback(tel, v)
        y = float(self.fc["q_cal"][k, 1])
        return provision(self.w, self.sig, y, self.param, self.z), self.cfg.default_mem

    def info(self):
        return dict(eta=self.eta, w0_mean=float(self.w0.mean()), sigma_mean=float(self.sig.mean()),
                    w_final_mean=float(self.w.mean()), z=self.z)
