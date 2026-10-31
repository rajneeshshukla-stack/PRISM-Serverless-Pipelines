"""Forecasting stack (§IV-A to §IV-C, §V-C, Supplement S7).

* QuantileGBM: four HistGradientBoostingRegressor models with pinball loss.
* Reference forecasters: seasonal-naive, last-5-min max, EWMA, each with
  empirical ratio quantiles from the training period.
* ConformalScaler: multiplicative adaptive-conformal offset (Eq. (13)) with delay.
* quantile_function / scenarios: monotone piecewise-linear quantile function and
  100 stratified demand scenarios (§IV-C).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import DAY, FeatureBuilder

TAUS = (0.1, 0.5, 0.9, 0.99)

# ASSUMPTION D07: hyper-parameters fixed a priori (not tuned on any evaluation data)
GBM_PARAMS = dict(max_iter=200, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                  l2_regularization=0.0, early_stopping=False, random_state=0)


def cummax_rows(q: np.ndarray) -> np.ndarray:
    return np.maximum.accumulate(q, axis=-1)


class QuantileGBM:
    name = "gbm"

    def __init__(self, fb: FeatureBuilder, params=None):
        self.fb = fb
        self.params = dict(GBM_PARAMS, **(params or {}))
        self.models = {}

    def fit(self, t_lo: int, t_hi: int):
        """Fit on decision minutes t in [t_lo, t_hi) whose targets lie inside [.., t_hi)."""
        ts = np.arange(max(t_lo, self.fb.min_t), t_hi - 6)
        X, lev = self.fb.matrix(ts)
        y = self.fb.target(ts) / lev
        for tau in TAUS:
            m = HistGradientBoostingRegressor(loss="quantile", quantile=tau, **self.params)
            m.fit(X, y)
            self.models[tau] = m
        self.train_range = (int(ts[0]), int(ts[-1]))
        return self

    def predict(self, ts) -> np.ndarray:
        """Raw quantiles (n,4) rescaled to counts, cumulative-max ordered (Alg. 1 step 3)."""
        X, lev = self.fb.matrix(ts)
        q = np.column_stack([self.models[t].predict(X) for t in TAUS]) * lev[:, None]
        return cummax_rows(np.maximum(q, 0.0))

    def predict_one(self, t: int) -> np.ndarray:
        return self.predict(np.array([t]))[0]


class RatioQuantileForecaster:
    """Point forecast x empirical quantiles of (outcome / forecast) on training data."""

    def __init__(self, fb: FeatureBuilder, kind: str, ewma_alpha: float = 0.1):
        if kind not in ("seasonal_naive", "last5max", "ewma"):
            raise ValueError(kind)
        self.fb, self.kind, self.name = fb, kind, kind
        N = fb.counts
        if kind == "ewma":  # ASSUMPTION D18: alpha = 0.1 per minute
            e = np.empty(len(N))
            e[0] = N[0]
            for i in range(1, len(N)):
                e[i] = ewma_alpha * N[i] + (1 - ewma_alpha) * e[i - 1]
            self._ewma = e

    def point(self, ts):
        ts = np.asarray(ts, int)
        if self.kind == "seasonal_naive":
            return self.fb.y[ts - DAY]
        if self.kind == "last5max":
            return self.fb.rmax5[ts]
        return self._ewma[ts]

    def fit(self, t_lo, t_hi):
        ts = np.arange(max(t_lo, self.fb.min_t), t_hi - 6)
        f = np.maximum(self.point(ts), 1.0)
        r = self.fb.target(ts) / f
        self.ratio_q = np.quantile(r, TAUS)
        return self

    def predict(self, ts):
        f = np.maximum(self.point(ts), 1.0)
        return cummax_rows(f[:, None] * self.ratio_q[None, :])

    def predict_one(self, t):
        return self.predict(np.array([t]))[0]


@dataclass
class ConformalScaler:
    """Eq. (13): s_{k+1} = clip(s_k + gamma (1[Y_{k-1} > U_{k-1}] - target), s_min, s_max), i.e. two-epoch delay."""

    gamma: float = 0.05
    target: float = 0.01
    s_min: float = -0.3
    s_max: float = 0.8
    delay: int = 2
    s: float = 0.0

    def run(self, q_raw: np.ndarray, y: np.ndarray, s0: float = 0.0):
        """Batch replay over consecutive epochs. Returns (calibrated quantiles, offset used
        at each epoch, number of order reversals before re-ordering). The offset used at
        epoch k incorporates outcomes of epochs <= k - delay (§IV-B)."""
        K = len(q_raw)
        s_used = np.empty(K)
        s = s0
        pending = []  # (epoch index, U)
        for k in range(K):
            # outcomes of epochs <= k - delay are now known
            while pending and pending[0][0] <= k - self.delay:
                j, U = pending.pop(0)
                if np.isfinite(y[j]):
                    s = float(np.clip(s + self.gamma * ((y[j] > U) - self.target), self.s_min, self.s_max))
            s_used[k] = s
            U = q_raw[k, 3] * np.exp(s)
            pending.append((k, U))
        q = calibrate(q_raw, s_used)
        rev = int(np.sum(np.any(np.diff(apply_offset(q_raw, s_used), axis=1) < 0, axis=1)))
        self.s = s
        return q, s_used, rev


def apply_offset(q_raw, s):
    q = np.array(q_raw, float, copy=True)
    f = np.exp(np.asarray(s, float))
    q[..., 2] = q[..., 2] * f
    q[..., 3] = q[..., 3] * f
    return q


def calibrate(q_raw, s):
    """Offset on q0.9 and q0.99, then cumulative maximum (ordering after calibration)."""
    return cummax_rows(apply_offset(q_raw, s))


PROB_KNOTS = np.array([0.1, 0.5, 0.9, 0.99, 0.999])


def quantile_knots(q4: np.ndarray) -> np.ndarray:
    """Five knot values incl. exponential-tail extrapolation q0.999 = q0.99 + (q0.99 - q0.9)."""
    q4 = np.maximum.accumulate(np.asarray(q4, float))
    return np.append(q4, q4[3] + (q4[3] - q4[2]))


def quantile_function(q4: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Monotone piecewise-linear quantile function; linear extension of the lower tail
    (slope of the 0.1-0.5 segment) and of the upper tail (slope of 0.99-0.999)."""
    k = quantile_knots(q4)
    p = np.asarray(p, float)
    out = np.interp(p, PROB_KNOTS, k)
    lo = p < PROB_KNOTS[0]
    slope_lo = (k[1] - k[0]) / (PROB_KNOTS[1] - PROB_KNOTS[0])
    out[lo] = k[0] - slope_lo * (PROB_KNOTS[0] - p[lo])
    hi = p > PROB_KNOTS[-1]
    slope_hi = (k[4] - k[3]) / (PROB_KNOTS[4] - PROB_KNOTS[3])
    out[hi] = k[4] + slope_hi * (p[hi] - PROB_KNOTS[-1])
    out = np.maximum(out, 0.0)
    return np.maximum.accumulate(out)


def stratified_levels(n: int) -> np.ndarray:
    """ASSUMPTION D09: equally spaced probability levels (i + 0.5)/n."""
    return (np.arange(n) + 0.5) / n


def scenarios(q4: np.ndarray, n: int = 100) -> np.ndarray:
    return quantile_function(q4, stratified_levels(n))
