#!/usr/bin/env python3
"""Expanded trace set with recorded seeds (R2.18, R3.5, R5.M4; also R6.5).

Defines the 30 SYNTHETIC evaluation traces for the revision: the original evaluation seeds
101-105 plus 106-130, fixed a priori (no output of any policy on 106-130 existed when they were
chosen; development seed 7 and the real-trace seeds 201-205 are excluded). For every seed and
scenario it records the SHA-256 of the per-minute counts, so a later run can prove it used the
same traces, and it screens per-trace properties of the 25 new traces against the original five.

The screen is a sanity check of the generator, not a hypothesis test of anything reported: each
statistic of the new traces is compared with the original five by a two-sided Mann-Whitney test
(alpha = 0.01, uncorrected) and by range (new-trace median inside the original five's range).

Usage: python trace_set.py <code_root> <manifest_out.json>
"""
import hashlib
import json
import os
import sys

import numpy as np

if __name__ == '__main__':  # importable; argv only read when run directly
    sys.path.insert(0, os.path.join(sys.argv[1], 'src'))
from prism_repro.workload import MIN_PER_DAY, SCENARIOS, WorkloadParams, generate_trace  # noqa: E402

ORIGINAL = tuple(range(101, 106))
NEW = tuple(range(106, 131))
SEEDS = ORIGINAL + NEW
VAL, TEST = 14 * MIN_PER_DAY, 21 * MIN_PER_DAY


def counts_sha256(counts: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(counts, dtype="<i8").tobytes()).hexdigest()


def trace_stats(seed: int) -> dict:
    """Per-trace properties the evaluation depends on (all from generate_trace, no policy)."""
    tr = {sc: generate_trace(seed, sc)["counts"].astype(float) for sc in SCENARIOS}
    st = tr["stationary"]
    trig = generate_trace(seed, "stationary")["trigger_minutes_known"]
    moh = np.arange(len(st)) % 60
    on = np.isin(moh, trig)
    wk = st[TEST:]
    x, y = st[:-MIN_PER_DAY], st[MIN_PER_DAY:]
    return dict(
        mean_rate=float(st.mean()),
        cv_minute=float(st.std() / st.mean()),
        peak_to_mean_test=float(wk.max() / wk.mean()),
        p99_to_mean_test=float(np.quantile(wk, 0.99) / wk.mean()),
        daily_autocorr=float(np.corrcoef(x, y)[0, 1]),
        trigger_ratio=float(st[on].mean() / st[~on].mean()),
        growth_test_ratio=float(tr["growth"][TEST:].mean() / wk.mean()),
        bursty_test_ratio=float(tr["bursty"][TEST:].mean() / wk.mean()),
        new_spike_test_ratio=float(tr["new_spike"][TEST:].mean() / wk.mean()),
        val_test_ratio=float(st[VAL:TEST].mean() / wk.mean()),
        first21_identical=bool(all(np.array_equal(tr[sc][:TEST], st[:TEST]) for sc in SCENARIOS)),
    )


def screen(stats: dict, alpha: float = 0.01) -> dict:
    from scipy.stats import mannwhitneyu
    out = {}
    for k in next(iter(stats.values())):
        if k == "first21_identical":
            continue
        a = np.array([stats[s][k] for s in ORIGINAL])
        b = np.array([stats[s][k] for s in NEW])
        p = float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
        out[k] = dict(original_min=float(a.min()), original_max=float(a.max()),
                      new_median=float(np.median(b)), new_min=float(b.min()), new_max=float(b.max()),
                      mw_p=p, median_in_original_range=bool(a.min() <= np.median(b) <= a.max()),
                      flag=bool(p < alpha))
    return out


def build_manifest() -> dict:
    stats = {s: trace_stats(s) for s in SEEDS}
    return dict(
        description="Revision trace set: SYNTHETIC traces, seeds fixed a priori (R2.18, R3.5, R5.M4)",
        seeds=list(SEEDS), original_seeds=list(ORIGINAL), new_seeds=list(NEW),
        scenarios=list(SCENARIOS), workload_params=WorkloadParams().__dict__,
        counts_sha256={str(s): {sc: counts_sha256(generate_trace(s, sc)["counts"]) for sc in SCENARIOS}
                       for s in SEEDS},
        all_first21_identical=all(v["first21_identical"] for v in stats.values()),
        per_trace=stats, screen=screen(stats))


def main():
    m = build_manifest()
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    print(f"{len(m['seeds'])} seeds; first 21 days identical across scenarios: {m['all_first21_identical']}")
    for k, v in m["screen"].items():
        print(f"  {k:22s} original [{v['original_min']:.4f}, {v['original_max']:.4f}]  new median "
              f"{v['new_median']:.4f} [{v['new_min']:.4f}, {v['new_max']:.4f}]  MW p={v['mw_p']:.3f}"
              f"{'  FLAG' if v['flag'] else ''}")


if __name__ == '__main__':
    main()
