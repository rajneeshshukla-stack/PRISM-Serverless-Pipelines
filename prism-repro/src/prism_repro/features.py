"""Feature construction for the window-peak forecaster (§IV-A, Eq. (12)).

Decision at minute t observes counts N_0..N_t and controls minutes t+2..t+6, so
the target is Y_t = max_{j=2..6} N_{t+j}. Every feature uses only N_u with u<=t
(enforced by tests/test_controller.py::TestFeatures::test_no_lookahead).
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

LAGS = (0, 1, 2, 4, 9, 14, 29, 59)
H_LO, H_HI = 2, 6
DAY = 1440
GROUPS = {
    "trigger": ("minute_of_hour", "trigger_flag"),
    "prevday": ("prev_peak", "prev_count", "level_ratio_prev"),
}


def window_peak_target(counts: np.ndarray) -> np.ndarray:
    """Y_t for every t (NaN where the window exceeds the trace)."""
    n = len(counts)
    y = np.full(n, np.nan)
    w = sliding_window_view(counts.astype(float), H_HI - H_LO + 1)  # w[i]=N_i..N_{i+4}
    idx = np.arange(n - H_HI)
    y[idx] = w[idx + H_LO].max(1)
    return y


def _trailing(fn, x, w):
    out = np.full(len(x), np.nan)
    v = sliding_window_view(x, w)
    out[w - 1:] = fn(v, axis=1)
    return out


class FeatureBuilder:
    """Builds the feature matrix for all minutes of a trace once (batch), so that
    online and batch use the same code path (Supplement S9)."""

    def __init__(self, counts: np.ndarray, trigger_minutes, drop_groups=(), normalise: bool = True):
        self.counts = counts.astype(float)
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
        self.y = window_peak_target(N)
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
        for j in range(H_LO, H_HI + 1):
            flag = np.maximum(flag, np.isin((t + j) % 60, self.trigger_minutes).astype(float))
        self.trig = flag
        # window mean / window peak ratio for r (§III-D (iv)): mean of N_{t+2..t+6}
        w = sliding_window_view(N, H_HI - H_LO + 1)
        self.ymean = np.full(n, np.nan)
        idx = np.arange(n - H_HI)
        self.ymean[idx] = w[idx + H_LO].mean(1)

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
            # previous-day realised window peak is known at t because t-DAY+6 < t
            cols += [self.y[tp] / lp, N[tp] / lp, self.level[ts] / self.level[tp]]
        if "trigger" not in self.drop:
            cols += [self.moh[ts].astype(float)]
        cols += [self.sin_t[ts], self.cos_t[ts], self.wkend[ts], self.wkend_prev[ts]]
        if "trigger" not in self.drop:
            cols += [self.trig[ts]]
        return np.column_stack(cols), lev

    def target(self, ts):
        return self.y[np.asarray(ts, int)]


def online_features(N: np.ndarray, t: int, trigger_minutes, drop_groups=(), normalise: bool = True):
    """Independent single-step feature computation from raw history N[0..t] only
    (used for the overhead measurement and as an oracle for the batch builder)."""
    N = np.asarray(N[:t + 1], float)
    drop = set(drop_groups)

    def level_at(u):
        return max(1.0, float(N[u - 59:u + 1].mean()))

    def peak_at(u):  # realised window peak of decision minute u (requires u + 6 <= t)
        return float(N[u + H_LO:u + H_HI + 1].max())

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
        f += [float(any(((t + j) % 60) in set(np.asarray(trigger_minutes).tolist()) for j in range(H_LO, H_HI + 1)))]
    return np.array(f), lev
