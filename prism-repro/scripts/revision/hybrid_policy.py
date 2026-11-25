#!/usr/bin/env python3
"""R3.2: the hybrid histogram policy of Shahrad et al. (USENIX ATC 2020, Section 4.2) and the paper's simulator
(Section 5.1), as prespecified in docs/revision/hybrid_reproduction_r32_20261124/PLAN.md. EXPLORATORY.

One application image per application. Input per application: the minutes with at least one invocation (sorted) and
their invocation counts, at the trace's 1-minute resolution; every invocation of minute m happens at time m and runs
for 0 time (the paper's simulator). Idle time (IT) = time from the previous invocation's end to this invocation.

Policies return, per application: invocations, cold starts, wasted memory time (image loaded, not executing), and
which mode decided each first-of-minute invocation.

Hybrid policy, as published: 1-minute bins over a range (default 240 min); ITs >= range are out of bounds (OOB) and
not in the histogram; head = 5th percentile rounded down to a bin's lower edge, tail = 99th percentile rounded up to
the bin's upper edge; pre-warm = head x (1 - margin), loaded until tail x (1 + margin) after the execution
(interpretation I) or for tail x (1 + margin) from the pre-warm load (interpretation II); if the histogram is empty or
the CV of its bin counts is below cv_min, standard keep-alive: pre-warm 0, keep-alive = range. ARIMA (for many OOB
ITs) is NOT implemented: its trigger is not specified (PLAN.md, choice 1).
"""
from __future__ import annotations

import numpy as np

RANGE_MIN, HEAD_PCT, TAIL_PCT, MARGIN, CV_MIN = 240, 5.0, 99.0, 0.10, 2.0


def _gaps(minutes):
    t = np.asarray(minutes, dtype=np.int64)
    return t, np.diff(t)                                   # ITs between consecutive active minutes (>= 1)


def fixed_keepalive(minutes, counts, keepalive_min: float, horizon_min: int) -> dict:
    """Fixed keep-alive (the providers' policy): the image stays loaded keepalive_min after every execution."""
    t, g = _gaps(minutes)
    c = np.asarray(counts, dtype=np.int64)
    cold = 1 + int((g > keepalive_min).sum())              # first invocation, then every IT beyond the window
    wasted = float(np.minimum(g, keepalive_min).sum()) + float(min(keepalive_min, horizon_min - t[-1]))
    return {"invocations": int(c.sum()), "cold": cold, "wasted_min": wasted}


def hybrid_windows(minutes, counts, range_min=RANGE_MIN, head_pct=HEAD_PCT, tail_pct=TAIL_PCT, margin=MARGIN,
                   cv_min=CV_MIN, ka_mode="I"):
    """Per active minute j: the (load_from, load_until) interval, relative to the previous execution, that the policy
    has set BEFORE minute j's first invocation (from the ITs of minutes < j), plus the interval after the last
    minute. Returns arrays a, b (length k + 1) and a boolean `standard` (non-representative histogram)."""
    t, g = _gaps(minutes)
    c = np.asarray(counts, dtype=np.int64)
    k = len(t)
    # ITs added after minute j: (c_j - 1) zeros (same-minute invocations) and, for j >= 1, one IT of g_{j-1}.
    vals = np.unique(np.concatenate([[0], g[g < range_min]]))
    add = np.zeros((k, len(vals)), dtype=np.int64)
    add[:, 0] = c - 1
    m = g < range_min
    np.add.at(add, (np.arange(1, k)[m], np.searchsorted(vals, g[m])), 1)
    H = np.vstack([np.zeros((1, len(vals)), dtype=np.int64), np.cumsum(add, axis=0)])   # H[j] = before minute j
    n = H.sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = n / range_min
        var = (H.astype(float) ** 2).sum(axis=1) / range_min - mean ** 2
        cv = np.sqrt(np.maximum(var, 0.0)) / mean
    standard = (n == 0) | ~(cv >= cv_min)
    cum = np.cumsum(H, axis=1)
    hi = np.argmax(cum >= (head_pct / 100.0) * n[:, None], axis=1)
    ti = np.argmax(cum >= (tail_pct / 100.0) * n[:, None], axis=1)
    head = vals[hi].astype(float)                          # lower edge of the bin holding the head percentile
    tail = vals[ti].astype(float) + 1.0                    # upper edge of the bin holding the tail percentile
    pw = head * (1 - margin)
    end = tail * (1 + margin)
    if ka_mode == "I":
        a, b = pw, np.maximum(end, pw)
    elif ka_mode == "II":
        a, b = pw, pw + end
    else:
        raise ValueError(ka_mode)
    a = np.where(standard, 0.0, a)
    b = np.where(standard, float(range_min), b)
    return a, b, standard


def hybrid(minutes, counts, horizon_min: int, ka_mode="I", **kw) -> dict:
    t, g = _gaps(minutes)
    c = np.asarray(counts, dtype=np.int64)
    a, b, standard = hybrid_windows(minutes, counts, ka_mode=ka_mode, **kw)
    # first-of-minute invocations j >= 1 use the window set after minute j - 1: index j of a, b
    aj, bj = a[1:len(t)], b[1:len(t)]
    warm = (g >= aj) & (g <= bj)
    wasted = float(np.where(warm, g - aj, np.where(g < aj, 0.0, bj - aj)).sum())
    cold = 1 + int((~warm).sum())
    # same-minute invocations (IT 0): cold when the window in force at that minute starts later than 0
    a_min = np.concatenate([[0.0], aj])                    # minute 0 starts with an empty histogram (standard)
    cold += int(((c - 1) * (a_min > 0)).sum())
    rem = horizon_min - t[-1]
    wasted += float(max(0.0, min(b[len(t)], rem) - a[len(t)]))
    return {"invocations": int(c.sum()), "cold": cold, "wasted_min": wasted,
            "standard_share": float(standard[:len(t)].mean()), "prewarm_share": float((a[:len(t)] > 0).mean())}


def no_unloading(minutes, counts, horizon_min: int) -> dict:
    t, g = _gaps(minutes)
    return {"invocations": int(np.asarray(counts).sum()), "cold": 1, "wasted_min": float(horizon_min - t[0])}
