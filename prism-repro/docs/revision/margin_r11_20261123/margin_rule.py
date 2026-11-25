#!/usr/bin/env python3
"""R1.1(b): leave-one-trace-out check of a uniform safety-margin rule (PLAN.md; no simulation).

usage: python margin_rule.py <rows dir: ../event_severity_resumed_20261122> <out.txt>
"""
import glob
import json
import os
import sys
from collections import defaultdict

from scipy import stats

ROWS, OUT = sys.argv[1], sys.argv[2]
GRID = (0.0, 0.1, 0.2, 0.3, 0.5)
R = defaultdict(dict)                                       # (seed, scenario) -> margin -> row
for f in sorted(glob.glob(os.path.join(ROWS, "rows_R24_*.jsonl"))):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        if r["family"] == "PRISM" and r["variant"] == "event" and r["margin"] in GRID:
            R[(r["seed"], r["scenario"])][r["margin"]] = r
weeks = sorted(R)
assert len(weeks) == 20 and all(set(R[w]) == set(GRID) for w in weeks), "20 weeks x 5 margins expected"
ok = lambda w, m: R[w][m]["violating_window_rate"] <= 0.02 + 1e-12  # noqa: E731
cost = lambda w, m: R[w][m]["cost"] / R[w][0.0]["cost"] - 1           # noqa: E731
seeds = sorted({s for s, _ in weeks})
L = ["R1.1(b): uniform safety-margin rule, leave one trace out. PRE-CALIBRATION, OPEN LOOP, POST HOC replay of PRISM's",
     "stored E12-selected schedules, event-level simulator, development traces 101-105 (20 weeks). Plan: PLAN.md.", ""]
L.append("In-sample (all 20 weeks): weeks meeting 2% by margin: " +
         ", ".join(f"{int(100 * m)}% {sum(ok(w, m) for w in weeks)}/20 (cost {100 * sum(cost(w, m) for w in weeks) / 20:+.1f}%)"
                   for m in GRID))
L.append("")
for name, q in (("strict", 1.0), ("lenient", 0.9)):
    held, fails, costs, chosen = 0, [], [], {}
    for s in seeds:
        train = [w for w in weeks if w[0] != s]
        test = [w for w in weeks if w[0] == s]
        m = next((m for m in GRID if sum(ok(w, m) for w in train) >= q * len(train) - 1e-9), None)
        chosen[s] = m
        if m is None:
            fails += [f"{w[0]} {w[1]} (no margin in the grid met the criterion)" for w in test]
            continue
        for w in test:
            costs.append(cost(w, m))
            if ok(w, m):
                held += 1
            else:
                fails.append(f"{w[0]} {w[1]}: {100 * R[w][m]['violating_window_rate']:.2f}% at margin {int(100 * m)}%")
    lo, hi = stats.beta.ppf(0.025, held, 21 - held) if held else 0.0, stats.beta.ppf(0.975, held + 1, 20 - held) if held < 20 else 1.0
    L.append(f"## {name} (q = {q}): chosen margin per held-out trace " + ", ".join(f"{s}: {int(100 * m)}%" if m is not None else f"{s}: none"
                                                                              for s, m in chosen.items()))
    L.append(f"   held-out weeks meeting 2%: {held}/20 (95% Clopper-Pearson {100 * lo:.0f}-{100 * hi:.0f}%); mean cost of the "
             f"margin {100 * sum(costs) / max(len(costs), 1):+.1f}% (range {100 * min(costs):+.1f} to {100 * max(costs):+.1f}%)")
    L.append("   held-out failures: " + ("; ".join(fails) if fails else "none"))
    L.append("")
open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("\n".join(L))
