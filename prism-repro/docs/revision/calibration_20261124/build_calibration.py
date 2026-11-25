#!/usr/bin/env python3
"""Calibration evidence for the final PRISM evaluation (24 Nov 2026; R1.2, R2.8(b), R4.3, R4.8, R5.M2, R7.5(d)).
No AWS call and no simulation. Inputs: the saved, sanitized memcal-1 aggregates (../aws_memcal_20261122/tables/).

Outputs (into this folder):
  exec_factor_measured.json   the per-stage execution-time factors relative to 1024 MB, from the FIT split only
                              (warm Duration medians, FIT visits), for the opt-in "measured" mode
  heldout_exec_measured.csv   the held-out check of that mode on the CHECK split (existing prespecified split):
                              absolute (FIT median against the CHECK median's 95% batch-bootstrap interval) and scaling
                              (FIT factor against CHECK median(m) / CHECK median(1024))
  heldout_coverage.txt        the 37/56 breakdown of the existing held-out check, by quantity, with every miss
usage (from prism-repro/): python docs/revision/calibration_20261124/build_calibration.py
"""
import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, "..", "aws_memcal_20261122", "tables")
STAGES = ("ingest", "transform", "aggregate", "load")
SIZES = (512, 1024, 2048, 3008)
REPEAT = 0.0041   # between-block spread of warm medians (RESULTS.md "Within-day repeatability": within 0.41%)

rows = list(csv.DictReader(open(os.path.join(T, "heldout_check.csv"))))
warm = {(r["stage"], int(r["memory_mb"])): r for r in rows if r["quantity"].startswith("warm Duration median")}
assert len(warm) == 16

# 1. factors from FIT only
fit = {k: float(r["fit_split_value"]) for k, r in warm.items()}
fac = {m: tuple(round(fit[(s, m)] / fit[(s, 1024)], 6) for s in STAGES) for m in SIZES}
json.dump(dict(source="memcal-1 FIT-split warm Duration medians (../aws_memcal_20261122/tables/heldout_check.csv, "
                      "fit_split_value), ratio to the same stage's 1024 MB FIT median",
               stages=STAGES, exec_factor_measured=[[m, list(fac[m])] for m in SIZES]),
          open(os.path.join(HERE, "exec_factor_measured.json"), "w", encoding="utf-8", newline="\n"), indent=1)

# 2. held-out check of the measured mode on CHECK
out = []
for s in STAGES:
    c1024 = float(warm[(s, 1024)]["check_observed"])
    for m in SIZES:
        r = warm[(s, m)]
        obs, lo, hi = float(r["check_observed"]), float(r["check_lo"]), float(r["check_hi"])
        pred_abs = fit[(s, m)]
        f_check = obs / c1024
        out.append(dict(stage=s, memory_mb=m, fit_median_s=pred_abs, check_median_s=obs, check_lo=lo, check_hi=hi,
                        abs_inside=lo <= pred_abs <= hi, abs_rel_error=round((pred_abs - obs) / obs, 5),
                        abs_within_block_repeatability=abs(pred_abs - obs) / obs <= REPEAT,
                        factor_fit=fac[m][STAGES.index(s)], factor_check=round(f_check, 6),
                        factor_rel_error=round((fac[m][STAGES.index(s)] - f_check) / f_check, 5),
                        eq2_predicted_s=float(r["predicted"]), eq2_rel_error=float(r["rel_error"])))
with open(os.path.join(HERE, "heldout_exec_measured.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)

# 3. the existing 37/56 breakdown
by = defaultdict(lambda: [0, 0, []])
for r in rows:
    q = by[r["quantity"]]
    q[0] += 1
    if r["inside_check_interval"] == "True":
        q[1] += 1
    else:
        q[2].append(f"{r['stage']} {r['memory_mb']} MB: predicted {float(r['predicted']):.4f}, observed "
                    f"{float(r['check_observed']):.4f} [{float(r['check_lo']):.4f}, {float(r['check_hi']):.4f}], "
                    f"rel {float(r['rel_error']):+.4f}")
lines = [f"Existing held-out check (aws_memcal_20261122/tables/heldout_check.csv): "
         f"{sum(v[1] for v in by.values())} of {sum(v[0] for v in by.values())} inside the CHECK 95% interval"]
for k, (n, ok, miss) in by.items():
    lines.append(f"\n{k}: {ok}/{n}")
    lines += [f"  miss: {x}" for x in miss]
nm = [o for o in out if o["memory_mb"] != 1024]
lines.append("\nMeasured per-size execution-time mode (FIT factors), on CHECK:")
lines.append(f"  absolute, inside the CHECK interval: {sum(o['abs_inside'] for o in out)}/16; within the 0.41% "
             f"between-block repeatability: {sum(o['abs_within_block_repeatability'] for o in out)}/16; "
             f"|rel error| max {max(abs(o['abs_rel_error']) for o in out):.4f}")
lines.append(f"  scaling factor vs CHECK factor (12 non-reference cells): |rel error| max "
             f"{max(abs(o['factor_rel_error']) for o in nm):.4f}, mean {sum(abs(o['factor_rel_error']) for o in nm) / 12:.4f}")
lines.append(f"  Eq. (2) form on the same cells: |rel error| max {max(abs(o['eq2_rel_error']) for o in out):.4f}, "
             f"mean {sum(abs(o['eq2_rel_error']) for o in out) / 16:.4f}")
open(os.path.join(HERE, "heldout_coverage.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("\n".join(lines))
print("factors:", json.dumps({m: fac[m] for m in SIZES}))
