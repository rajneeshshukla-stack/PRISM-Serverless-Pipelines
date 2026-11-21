#!/usr/bin/env python3
"""Empirical mapping from PRISM's per-record risk budget epsilon to the window-level outcome (R2.3, R7.3).

Reviewer 2 asks for "a statistically validated mapping between the per-record risk budget and the
operational compliance target". From PRISM runs over the epsilon grid this builds, per epsilon:

  curve        violating-window rate on VALIDATION weeks, trace as the unit: mean and 95% t-interval
               over traces, and a 95% prediction interval for one new trace-week
  hold-out     (i)  validation -> test: share of held-out test trace-weeks inside the prediction interval
               (ii) leave one trace out: the curve is refitted on the other traces' validation weeks and
                    the held-out trace's test weeks are scored against it
  operator     the largest epsilon whose upper prediction bound stays within the 2% target

It reads PRISM rows only. Row formats: stored E1 rows (results/raw/E1/rows.jsonl; spec.family ==
"PRISM", no tag) or the kappa-floor rows (scripts/revision/kappa_floor_retune.py; arm == "floor0.1").
The stored E1 rows come from the code tagged v1-submitted; treat their mapping as provisional.

Usage: python eps_window_mapping.py <code_root> <rows.jsonl | dir> [...] [--out f.json]
"""
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

TARGET = 0.02


def prism_points(rows):
    """(seed, week, scenario, eps, violating_window_rate) of PRISM runs at the submitted settings."""
    out = []
    for r in rows:
        if "arm" in r:                                  # kappa_floor_retune rows
            if r["arm"] != "floor0.1":
                continue
            eps = r["eps"]
        else:                                           # experiment rows
            spec = r.get("spec", {})
            if spec.get("family") != "PRISM" or r.get("tag") or spec.get("prism") or spec.get("fc"):
                continue
            eps = spec["param"]
        out.append((r["seed"], r["week"], r.get("scenario"), float(eps), float(r["violating_window_rate"])))
    return out


def curve(points, week, seeds=None):
    """Per epsilon: per-trace mean over that trace's weeks, then mean, CI and PI over traces."""
    by = defaultdict(lambda: defaultdict(list))
    for s, w, _, e, v in points:
        if w == week and (seeds is None or s in seeds):
            by[e][s].append(v)
    res = {}
    for e, per in sorted(by.items()):
        x = np.array([np.mean(v) for v in per.values()])
        n = len(x)
        m, sd = float(x.mean()), float(x.std(ddof=1)) if n > 1 else float("nan")
        t = stats.t.ppf(0.975, n - 1) if n > 1 else float("nan")
        res[e] = dict(n_traces=n, mean=m, ci=(m - t * sd / np.sqrt(n), m + t * sd / np.sqrt(n)),
                      pi=(max(0.0, m - t * sd * np.sqrt(1 + 1 / n)), m + t * sd * np.sqrt(1 + 1 / n)),
                      share_weeks_meeting=float(np.mean([v <= TARGET + 1e-12 for vv in per.values() for v in vv])))
    return res


def coverage(points, cur, week="test", seeds=None):
    hits = [cur[e]["pi"][0] - 1e-12 <= v <= cur[e]["pi"][1] + 1e-12
            for s, w, _, e, v in points if w == week and (seeds is None or s in seeds) and e in cur]
    return float(np.mean(hits)) if hits else float("nan"), len(hits)


def analyse(points):
    seeds = sorted({p[0] for p in points})
    val = curve(points, "val")
    test = curve(points, "test")
    cov, n = coverage(points, val)
    loo = []
    for s in seeds:
        c = curve(points, "val", [x for x in seeds if x != s])
        loo.append(coverage(points, c, "test", [s]))
    loo_hits = sum(c * k for c, k in loo)
    loo_n = sum(k for _, k in loo)
    eps = sorted(val)
    rho = stats.spearmanr(eps, [val[e]["mean"] for e in eps]).correlation if len(eps) > 2 else float("nan")
    ok = [e for e in eps if val[e]["pi"][1] <= TARGET]
    return dict(seeds=seeds, validation_curve=val, test_curve=test,
                val_to_test_pi_coverage=cov, n_test_weeks=n,
                loo_pi_coverage=loo_hits / loo_n if loo_n else float("nan"), loo_n=loo_n,
                spearman_eps_vs_val_rate=float(rho),
                operator_max_eps_upper_pi_within_target=(max(ok) if ok else None))


def load(paths):
    rows = []
    for p in paths:
        for f in (sorted(glob.glob(os.path.join(p, "*.jsonl"))) if os.path.isdir(p) else [p]):
            with open(f, encoding="utf-8") as fh:
                rows += [json.loads(l) for l in fh if l.strip()]
    return rows


def main():
    args = sys.argv[2:]
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    res = analyse(prism_points(load(args)))
    print(f"traces {res['seeds']}")
    print(" eps     | validation: mean [95% CI over traces]   PI (one trace-week)    weeks<=2% | test mean  weeks<=2%")
    for e, v in res["validation_curve"].items():
        t = res["test_curve"].get(e, {})
        print(f" {e:<7g} | {100*v['mean']:5.2f}% [{100*v['ci'][0]:5.2f}, {100*v['ci'][1]:5.2f}]   "
              f"[{100*v['pi'][0]:5.2f}, {100*v['pi'][1]:5.2f}]   {100*v['share_weeks_meeting']:5.1f}%   | "
              f"{100*t.get('mean', float('nan')):5.2f}%    {100*t.get('share_weeks_meeting', float('nan')):5.1f}%")
    print(f"monotone? Spearman(eps, validation rate) = {res['spearman_eps_vs_val_rate']:.3f}")
    print(f"held-out coverage of the 95% PI: validation->test {100*res['val_to_test_pi_coverage']:.1f}% "
          f"of {res['n_test_weeks']} test weeks; leave-one-trace-out {100*res['loo_pi_coverage']:.1f}% of {res['loo_n']}")
    print(f"operator rule: largest eps with upper PI <= 2%: {res['operator_max_eps_upper_pi_within_target']}")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
