"""Feature construction for the window-peak forecaster (§IV-A, Eq. (12)).

Decision at minute t observes counts N_0..N_t and controls minutes t+2..t+6, so
the target is Y_t = max_{j=2..6} N_{t+j} (at the default lag L = 2; forecast_horizon gives
the horizon for other lags). Every feature uses only N_u with u<=t
(enforced by tests/test_controller.py::TestFeatures::test_no_lookahead).
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

LAGS = (0, 1, 2, 4, 9, 14, 29, 59)
H_LO, H_HI = 2, 6   # horizon at the default lag L = 2 and 5-min epochs; see forecast_horizon
DAY = 1440


def forecast_horizon(cfg) -> tuple:
    """(H_LO, H_HI) for an activation lag L = cfg.lag_min (R1.3, R4.3, M1): the decision at
    minute t = 5k - L controls minutes 5k..5k+E-1, i.e. t+L .. t+L+E-1. Returns (2, 6) at the
    defaults, the horizon the submitted runs used."""
    return int(cfg.lag_min), int(cfg.lag_min + cfg.epoch_min - 1)


def min_feedback_delay(cfg) -> int:
    """Fewest epochs after which epoch k's realised window peak is observable: its window ends
    at minute 5k+E-1 and decision k+j observes minutes <= 5(k+j) - L. Equals 2 at the defaults
    and 3 at L = 10, where a fixed delay of 2 would read the future."""
    E, L = int(cfg.epoch_min), int(cfg.lag_min)
    return -(-(E - 1 + L) // E)
GROUPS = {
    "trigger": ("minute_of_hour", "trigger_flag"),
    "prevday": ("prev_peak", "prev_count", "level_ratio_prev"),
}


def window_peak_target(counts: np.ndarray, horizon: tuple = (H_LO, H_HI)) -> np.ndarray:
    """Y_t = max_{j=h_lo..h_hi} N_{t+j} for every t (NaN where the window exceeds the trace)."""
    h_lo, h_hi = horizon
    n = len(counts)
    y = np.full(n, np.nan)
    w = sliding_window_view(counts.astype(float), h_hi - h_lo + 1)  # w[i]=N_i..N_{i+h_hi-h_lo}
    idx = np.arange(n - h_hi)
    y[idx] = w[idx + h_lo].max(1)
    return y


def _trailing(fn, x, w):
    out = np.full(len(x), np.nan)
    v = sliding_window_view(x, w)
    out[w - 1:] = fn(v, axis=1)
    return out


class FeatureBuilder:
    """Builds the feature matrix for all minutes of a trace once (batch), so that
    online and batch use the same code path (Supplement S9)."""

    def __init__(self, counts: np.ndarray, trigger_minutes, drop_groups=(), normalise: bool = True,
                 horizon: tuple = (H_LO, H_HI)):
        self.counts = counts.astype(float)
        self.h_lo, self.h_hi = horizon
        self.trigger_minutes = np.asarray(trigger_minutes)
        self.drop = set(drop_groups)
        self.normalise = normalise
        self._precompute()

    def _precompute(self):
        N = self.counts
        n = len(N)
        self.level = np.maximum(1.0, _trailing(np.mean, N, 60))  # floored trailing 60-min mean
        self.rmax5 = _trailing(np.max, N, 5)
        self.rmax15 = _trailing(np.max, N, 15)
        self.rstd15 = _trailing(np.std, N, 15)
        self.y = window_peak_target(N, (self.h_lo, self.h_hi))
        t = np.arange(n)
        moh = t % 60
        hod = (t % DAY) / 60.0
        dow = (t // DAY) % 7
        self.moh = moh
        self.sin_t = np.sin(2 * np.pi * hod / 24)
        self.cos_t = np.cos(2 * np.pi * hod / 24)
        self.wkend = (dow >= 5).astype(float)
        self.wkend_prev = (((dow - 1) % 7) >= 5).astype(float)
        flag = np.zeros(n)
        for j in range(self.h_lo, self.h_hi + 1):
            flag = np.maximum(flag, np.isin((t + j) % 60, self.trigger_minutes).astype(float))
        self.trig = flag
        # window mean / window peak ratio for r (§III-D (iv)): mean of N_{t+h_lo..t+h_hi}
        w = sliding_window_view(N, self.h_hi - self.h_lo + 1)
        self.ymean = np.full(n, np.nan)
        idx = np.arange(n - self.h_hi)
        self.ymean[idx] = w[idx + self.h_lo].mean(1)

    @property
    def min_t(self) -> int:
        return DAY + 60  # need previous-day features and a 60-min level

    def names(self):
        nm = [f"lag{l}" for l in LAGS] + ["rmax5", "rmax15", "rstd15"]
        if "prevday" not in self.drop:
            nm += ["prev_peak", "prev_count", "level_ratio_prev"]
        if "trigger" not in self.drop:
            nm += ["minute_of_hour"]
        nm += ["sin_tod", "cos_tod", "weekend", "weekend_prev"]
        if "trigger" not in self.drop:
            nm += ["trigger_flag"]
        return nm

    def matrix(self, ts: np.ndarray):
        """Feature matrix X and normaliser (level) for decision minutes ts."""
        ts = np.asarray(ts, int)
        if ts.min() < self.min_t:
            raise ValueError("decision time lacks history for features")
        N = self.counts
        lev = self.level[ts] if self.normalise else np.ones(len(ts))
        cols = [N[ts - l] / lev for l in LAGS]
        cols += [self.rmax5[ts] / lev, self.rmax15[ts] / lev, self.rstd15[ts] / lev]
        if "prevday" not in self.drop:
            tp = ts - DAY
            lp = self.level[tp] if self.normalise else np.ones(len(ts))
            # previous-day realised window peak is known at t because t-DAY+h_hi < t
            cols += [self.y[tp] / lp, N[tp] / lp, self.level[ts] / self.level[tp]]
        if "trigger" not in self.drop:
            cols += [self.moh[ts].astype(float)]
        cols += [self.sin_t[ts], self.cos_t[ts], self.wkend[ts], self.wkend_prev[ts]]
        if "trigger" not in self.drop:
            cols += [self.trig[ts]]
        return np.column_stack(cols), lev

    def target(self, ts):
        return self.y[np.asarray(ts, int)]


def online_features(N: np.ndarray, t: int, trigger_minutes, drop_groups=(), normalise: bool = True,
                    horizon: tuple = (H_LO, H_HI)):
    """Independent single-step feature computation from raw history N[0..t] only
    (used for the overhead measurement and as an oracle for the batch builder)."""
    N = np.asarray(N[:t + 1], float)
    drop = set(drop_groups)
    h_lo, h_hi = horizon

    def level_at(u):
        return max(1.0, float(N[u - 59:u + 1].mean()))

    def peak_at(u):  # realised window peak of decision minute u (requires u + h_hi <= t)
        return float(N[u + h_lo:u + h_hi + 1].max())

    lev = level_at(t) if normalise else 1.0
    f = [N[t - l] / lev for l in LAGS]
    f += [N[t - 4:t + 1].max() / lev, N[t - 14:t + 1].max() / lev, N[t - 14:t + 1].std() / lev]
    if "prevday" not in drop:
        tp = t - DAY
        lp = level_at(tp) if normalise else 1.0
        f += [peak_at(tp) / lp, N[tp] / lp, level_at(t) / level_at(tp)]
    if "trigger" not in drop:
        f += [float(t % 60)]
    hod = (t % DAY) / 60.0
    dow = (t // DAY) % 7
    f += [np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24), float(dow >= 5), float(((dow - 1) % 7) >= 5)]
    if "trigger" not in drop:
        f += [float(any(((t + j) % 60) in set(np.asarray(trigger_minutes).tolist()) for j in range(h_lo, h_hi + 1)))]
    return np.array(f), lev
