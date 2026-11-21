#!/usr/bin/env python3
"""Per-week compliance of validation-selected PRISM on held-out test weeks (R2.4, R2.12, R5.M4). Post hoc analysis.

The paper's target is per test week: at most 2% of the week's 672 fifteen-minute windows may violate (a window
violates when fewer than 99% of its records meet the deadline; config.slo_violating_window_target = 0.02,
sla_eps = 0.01). A pooled rate below 2% can hide individual weeks above it. This reads the current-code rows
of scripts/revision/kappa_floor_retune.py (fast simulator, pre-calibration constants; seeds 101-105, every
epsilon on the validation week and on every test week) for the submitted floor (kappa_clip 0.1) and reports:

  (1) the epsilon selected on validation per trace (select_by_rule), its validation rate and grid position;
  (2) every held-out week at the selected epsilon: violating windows out of 672, margin to the 13-window
      allowance (2% of 672 = 13.44), cost, mean kappa; and how the pooled rate is computed;
  (3) POST HOC (selected with test-week knowledge, never for tuning): cost and compliance of alternative
      selection rules on the same weeks. A rule chosen from these numbers must be validated on traces that
      no analysis has seen (seeds 106-130 in data/trace_set_revision.json) before it is adopted.

Usage: python weekly_compliance.py <code_root> [<rows_dir>]   (default rows: docs/revision/kappa_floor)
"""
import glob
import json
import os
import sys

import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
ROWS = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "docs", "revision", "kappa_floor")
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import select_by_rule  # noqa: E402

W, ALLOW = 672, 0.02
SC = ("stationary", "growth", "bursty", "new_spike")


def main():
    rows = [json.loads(l) for p in sorted(glob.glob(os.path.join(ROWS, "rows_*.jsonl"))) for l in open(p)]
    A = [r for r in rows if r["arm"] == "floor0.1"]
    seeds = sorted({r["seed"] for r in A})
    grid = sorted({r["eps"] for r in A})

    def val(s):
        return [dict(r, spec={"param": r["eps"]}) for r in A if r["seed"] == s and r["week"] == "val"]

    def test(s, sc, e):
        return next(r for r in A if r["week"] == "test" and r["seed"] == s and r["scenario"] == sc and r["eps"] == e)

    print("(1) validation selection (floor 0.1; current code; fast simulator)")
    sel = {}
    for s in seeds:
        ch = select_by_rule(val(s))
        sel[s] = ch["eps"]
        print(f"  seed {s}: eps {ch['eps']} ({'TOP OF GRID' if ch['eps'] == max(grid) else 'interior'}); validation "
              f"{100 * ch['violating_window_rate']:.2f}% = {round(ch['violating_window_rate'] * W)} windows")
    print("\n(2) held-out test weeks at the selected eps")
    T = [test(s, sc, sel[s]) for s in seeds for sc in SC]
    for r in T:
        n = round(r["violating_window_rate"] * W)
        print(f"  {r['seed']} {r['scenario']:10s} eps {r['eps']:<5} {n:2d}/672 windows ({100 * r['violating_window_rate']:.2f}%), "
              f"{n - 13:+d} vs the 13-window allowance, {'MISS' if r['violating_window_rate'] > ALLOW + 1e-12 else 'met'}; "
              f"cost {r['cost']:.1f}, kappa {r['kappa_mean']:.3f}")
    v = np.array([r["violating_window_rate"] for r in T])
    miss = [r for r in T if r["violating_window_rate"] > ALLOW + 1e-12]
    print(f"  pooled: mean of {len(v)} weekly rates {100 * v.mean():.2f}% = {round(v.sum() * W)}/{len(v) * W} windows "
          f"(every week has 672 windows, so the two agree); weeks met {len(v) - len(miss)}/{len(v)}")
    print(f"  misses by trace {dict((s, sum(r['seed'] == s for r in miss)) for s in seeds)}; "
          f"by scenario {dict((sc, sum(r['scenario'] == sc for r in miss)) for sc in SC)}; "
          f"at the top-of-grid eps: {sum(r['eps'] == max(grid) for r in miss)} of {len(miss)} "
          f"(weeks at that eps: {sum(r['eps'] == max(grid) for r in T)})")
    print("\n(3) POST HOC alternatives on the same weeks (test-week knowledge; not a validation)")
    rules = {
        "submitted rule (cheapest with validation <= 2%)": {s: sel[s] for s in seeds},
        "validation margin (cheapest with validation <= 1.5%)": {s: select_by_rule(val(s), threshold=0.015)["eps"] for s in seeds},
        "eps capped at 0.05 (largest interior grid value)": {s: min(sel[s], 0.05) for s in seeds},
        "uniform eps 0.03": {s: 0.03 for s in seeds},
        "uniform eps 0.02 (operator rule of eps_window_mapping.py on these rows)": {s: 0.02 for s in seeds},
    }
    base = np.array([r["cost"] for r in T])
    for name, chosen in rules.items():
        R = [test(s, sc, chosen[s]) for s in seeds for sc in SC]
        c = np.array([r["cost"] for r in R])
        vv = np.array([r["violating_window_rate"] for r in R])
        print(f"  {name}: eps {[chosen[s] for s in seeds]}; cost {100 * (c.mean() / base.mean() - 1):+.1f}% vs submitted; "
              f"pooled {100 * vv.mean():.2f}%; weeks met {int((vv <= ALLOW + 1e-12).sum())}/{len(vv)}; worst week {100 * vv.max():.2f}%")


if __name__ == "__main__":
    main()
