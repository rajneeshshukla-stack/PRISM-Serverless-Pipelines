#!/usr/bin/env python3
"""R3.2 independent decision check (NOT a Table V comparison: the reproduction did not pass its prespecified
criteria, PLAN.md). Runs hybrid_policy.hybrid_windows per stage on the 25 Table V test weeks (development traces
101-105 x five scenarios) and compares the image-loaded decision with the platform keep-alive that Table V's
On-demand row assumes (PipelineConfig.keepalive_min). Every stage of a record is invoked within seconds of the
record's arrival, below the 1-minute resolution, so each stage sees the arrival minutes. EXPLORATORY.

usage (from prism-repro/): venv/Scripts/python scripts/revision/hybrid_tablev_decisions.py <out dir>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from hybrid_policy import fixed_keepalive, hybrid, hybrid_windows  # noqa: E402
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import WEEK_START  # noqa: E402
from prism_repro.workload import SCENARIOS, generate_trace  # noqa: E402

WEEK = 7 * 1440


def main(out_dir):
    ka = PipelineConfig().keepalive_min
    rows = []
    for seed in (101, 102, 103, 104, 105):
        for sc in SCENARIOS:
            c = np.asarray(generate_trace(seed, sc)["counts"], dtype=np.int64)
            w = c[WEEK_START["test"]:WEEK_START["test"] + WEEK]
            m = np.nonzero(w)[0]
            cnt = w[m]
            a, b, std = hybrid_windows(m, cnt)
            gaps = np.diff(m)
            h = hybrid(m, cnt, WEEK)
            f = fixed_keepalive(m, cnt, ka, WEEK)
            # minutes where the policy's image would be unloaded while requests are pending: an IT outside [a, b]
            unload = int((~((gaps >= a[1:len(m)]) & (gaps <= b[1:len(m)]))).sum())
            rows.append({"trace": f"{seed} {sc}", "minutes": int(len(w)), "empty_minutes": int((w == 0).sum()),
                         "min_per_minute": int(w.min()), "max_IT_min": int(gaps.max()) if len(gaps) else 0,
                         "prewarm_max_min": float(a.max()), "loaded_until_min_last": float(b[-1]),
                         "standard_keepalive_share": float(std.mean()),
                         "its_outside_window": unload, "platform_keepalive_min": ka,
                         "its_beyond_platform_keepalive": int((gaps > ka).sum()),
                         "app_cold_hybrid": h["cold"], "app_cold_fixed_platform": f["cold"]})
    same = all(r["its_outside_window"] == 0 and r["its_beyond_platform_keepalive"] == 0 and r["prewarm_max_min"] == 0
               for r in rows)
    out = {"label": "EXPLORATORY decision check; NOT a Table V comparison (reproduction did not pass); fast-simulator "
                    "synthetic development traces, test weeks", "rows": rows,
           "decisions_identical_to_platform_keepalive_on_all": same}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "tablev_decisions.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    L = [out["label"], ""]
    for r in rows:
        L.append(f"  {r['trace']:22s} empty min {r['empty_minutes']:3d}  min/minute {r['min_per_minute']:4d}  max IT "
                 f"{r['max_IT_min']} min  pre-warm max {r['prewarm_max_min']:.1f}  loaded until {r['loaded_until_min_last']:.1f} "
                 f"min  ITs outside window {r['its_outside_window']}  ITs > platform {r['platform_keepalive_min']} min "
                 f"{r['its_beyond_platform_keepalive']}  app cold starts {r['app_cold_hybrid']} / {r['app_cold_fixed_platform']}")
    L += ["", f"decisions identical to the platform keep-alive on all 25: {same}"]
    with open(os.path.join(out_dir, "tablev_decisions.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
