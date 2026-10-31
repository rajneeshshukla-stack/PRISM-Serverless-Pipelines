"""Loader for real or external per-minute arrival traces (generic CSV).

The manuscript mentions a loader for the public Huawei serverless trace format; that
format and data were not accessible here, so this generic loader is provided instead
(ASSUMPTION D21). Expected CSV columns: `minute` (consecutive integers from 0) and
`count` (non-negative integer arrivals of pipeline executions in that minute).
A trace must cover at least 28 days (40,320 minutes) to support the §V-B splits.
"""
from __future__ import annotations

import csv

import numpy as np

REQUIRED = ("minute", "count")


def load_minute_csv(path: str, min_minutes: int = 28 * 1440) -> np.ndarray:
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (rd.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}; expected {REQUIRED}")
        m, c = [], []
        for i, row in enumerate(rd):
            try:
                m.append(int(row["minute"]))
                c.append(int(row["count"]))
            except (TypeError, ValueError):
                raise ValueError(f"{path}: row {i + 2} has a non-integer minute/count")
    m, c = np.asarray(m), np.asarray(c)
    if len(m) == 0:
        raise ValueError(f"{path}: empty trace")
    if not np.array_equal(m, np.arange(m[0], m[0] + len(m))):
        raise ValueError(f"{path}: minutes must be consecutive integers without gaps")
    if np.any(c < 0):
        raise ValueError(f"{path}: negative counts")
    if len(c) < min_minutes:
        raise ValueError(f"{path}: {len(c)} minutes < required {min_minutes}")
    return c.astype(np.int64)
