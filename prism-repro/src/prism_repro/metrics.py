"""Evaluation metrics (§III-C, §V-D, Supplement S9)."""
from __future__ import annotations

import numpy as np


def window_attainment(n: np.ndarray, ontime: np.ndarray, window: int = 15):
    """Record-level attainment per window = sum(on-time records)/sum(records).
    n and ontime are per-minute counts (ontime may be fractional = expected)."""
    n = np.asarray(n, float)
    ontime = np.asarray(ontime, float)
    if len(n) % window:
        raise ValueError("series length must be a multiple of the window")
    tot = n.reshape(-1, window).sum(1)
    ok = ontime.reshape(-1, window).sum(1)
    att = np.where(tot > 0, ok / np.where(tot > 0, tot, 1), 1.0)
    return att, tot - ok, tot


def runs_of_true(mask: np.ndarray):
    """Lengths of maximal runs of consecutive True values."""
    mask = np.asarray(mask, bool)
    if not mask.any():
        return np.array([], int)
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return ends - starts


def severity(att: np.ndarray, late: np.ndarray, tot: np.ndarray, thr: float = 0.99) -> dict:
    viol = att < thr - 1e-12
    runs = runs_of_true(viol)
    late_total = float(late.sum())
    return {
        "violating_window_rate": float(viol.mean()),
        "late_records": late_total,
        "attain_in_violating": float(1 - late[viol].sum() / tot[viol].sum()) if viol.any() else np.nan,
        "worst_window_attainment": float(att.min()),
        "longest_run": int(runs.max()) if len(runs) else 0,
        "mean_run": float(runs.mean()) if len(runs) else 0.0,
        "n_runs": int(len(runs)),
        "share_late_in_violating": float(late[viol].sum() / late_total) if late_total > 0 else 0.0,
    }


def weighted_quantile_hist(values: np.ndarray, weights: np.ndarray, q: float, res: float = 0.01,
                           vmax: float = 120.0) -> float:
    """Weighted quantile via a fine histogram (resolution res seconds)."""
    idx = np.minimum((np.asarray(values) / res).astype(np.int64), int(vmax / res))
    h = np.bincount(idx.ravel(), weights=np.broadcast_to(weights, values.shape).ravel(),
                    minlength=int(vmax / res) + 1)
    c = np.cumsum(h)
    if c[-1] <= 0:
        return float("nan")
    return float((np.searchsorted(c, q * c[-1]) + 0.5) * res)


def mape(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = y > 0
    return float(np.mean(np.abs(yhat[m] - y[m]) / y[m]) * 100)


def pinball(y, q, tau):
    y = np.asarray(y, float)
    q = np.asarray(q, float)
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def coverage(y, q):
    return float(np.mean(np.asarray(y) <= np.asarray(q)))
