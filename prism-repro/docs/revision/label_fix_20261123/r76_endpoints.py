#!/usr/bin/env python3
"""R7.6: full-precision interval endpoints and bracketing counts of the post hoc matched-compliance comparison, from the
saved pc_billing_runs.csv files (no simulation). The envelope, interpolation, pairing and t-interval functions are taken
verbatim from ../regeneration_20261122/r76_matched_1pct.py (its source up to the first load() call is executed).

usage: python r76_endpoints.py <windows tree> <linux analysis tree> <stored repo> <out.json>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WIN, LIN, REPO, OUT = sys.argv[1:5]
src = open(os.path.join(HERE, "..", "regeneration_20261122", "r76_matched_1pct.py"), encoding="utf-8").read()
head = src[:src.index("regen = load(")]
ns = {"__name__": "r76", "__file__": "r76_matched_1pct.py"}
sys.argv = ["r76_matched_1pct.py", WIN, REPO, os.devnull]
exec(compile(head, "r76_matched_1pct.py", "exec"), ns)

res = {}
for name, root in (("windows", WIN), ("linux", LIN), ("stored", REPO)):
    data = ns["load"](os.path.join(root, "results", "tables", "revision", "pc_billing_runs.csv"))
    res[name] = {}
    for T in (0.010, 0.015, 0.020):
        per = {}
        for fam in ns["FAMS"]:
            per[fam] = [ns["at"](ns["envelope"](ns["points"](data, s, fam)), T)[0] for s in ns["SEEDS"]]
        used = [s for s, a, b in zip(ns["SEEDS"], per["PRISM"], per["QuantProv_q90"]) if np.isfinite(a) and np.isfinite(b)]
        d = [100 * (a / b - 1) for a, b in zip(per["PRISM"], per["QuantProv_q90"]) if np.isfinite(a) and np.isfinite(b)]
        m, h = ns["tint"](d)
        res[name][f"{100 * T:.1f}%"] = dict(mean=m, half_width=h, lower=m - h, upper=m + h, n=len(d), traces_used=used,
                                            not_bracketed=[s for s in ns["SEEDS"] if s not in used],
                                            per_trace=d, excludes_zero=bool(m + h < 0 or m - h > 0),
                                            within_2pct=bool(m - h >= -2 and m + h <= 2))
json.dump(res, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
for name, r in res.items():
    for t, v in r.items():
        print(f"{name:8s} {t}: {v['mean']:+.4f} [{v['lower']:+.4f}, {v['upper']:+.4f}] n {v['n']} not bracketed "
              f"{v['not_bracketed']} excludes0 {v['excludes_zero']} within2 {v['within_2pct']}")
