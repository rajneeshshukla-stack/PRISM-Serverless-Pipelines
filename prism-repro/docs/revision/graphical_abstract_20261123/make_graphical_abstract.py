#!/usr/bin/env python3
"""R4.10, R5.m5: standalone graphical-abstract draft from ONE labelled result set, with every value read from its source
table and checked before drawing (not the manuscript figure).

Result set: current code (fd8b01a + 6e0f05c), Linux x86-64 (Python 3.12.3, pinned packages; the platform on which the
submitted results reproduce exactly), fast simulator, PRE-CALIBRATION, five development traces, new-spike test week.
  headline: ../label_fix_20261123/outputs/linux_tables/T5_test_weeks.md (Table V), rows new_spike x {PRISM,
            PredHead+hyst, PredHead}
  caption:  linux_e4b/E4b_fixed_memory_summary.json (Table S14, same platform and code), best_PredHead_2048_vs_best_PRISM_pct

usage: python make_graphical_abstract.py <out dir>
"""
import csv
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
T5 = os.path.join(HERE, "..", "label_fix_20261123", "outputs", "linux_tables", "T5_test_weeks.md")
E4B = os.path.join(HERE, "linux_e4b", "E4b_fixed_memory_summary.json")
TITLE = ("Joint Cost-SLA Provisioning of Concurrency and Memory for Serverless Data Pipelines:\n"
         "A Chance-Constrained Formulation and a Simulation Study under Workload Shift")
LABEL = ("Fast simulator, PRE-CALIBRATION (assumed constants), new-spike test week, mean and 95% t interval over 5 development "
         "traces; current code (fd8b01a + 6e0f05c) on Linux x86-64. Values change with the reporting platform and the calibrated rerun.")
BARS = [("PRISM", "PRISM", "#2a78d6"), ("PredHead+hyst", "Smoothed headroom\n(stronger\ncomparator)", "#eb6834"),
        ("PredHead", "Unsmoothed\nheadroom", "#1baf7a")]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def pm(s):
    m = re.match(r"\s*([\d,.]+)\s*±\s*([\d,.]+)", s)
    return float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))


vals = {}
for line in open(T5, encoding="utf-8"):
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) >= 9 and c[0] == "new_spike" and c[1] in {b[0] for b in BARS}:
        cost, viol = pm(c[2]), pm(c[3])
        vals[c[1]] = dict(cost=cost[0], cost_h=cost[1], viol=viol[0], viol_h=viol[1], slo_met=c[7], n=int(c[8]))
assert set(vals) == {b[0] for b in BARS} and all(v["n"] == 5 for v in vals.values()), vals

e4b = json.load(open(E4B, encoding="utf-8"))
short = [r for r in e4b["regimes"] if r["deadline"] < 14.5 and r["eps"] == 0.02]
rng = [r["best_PredHead_2048_vs_best_PRISM_pct"] for r in short]
share = [r["best_PRISM_with_memory"]["share_ge2048"] for r in short]
default = [r for r in e4b["regimes"] if r["deadline"] == 14.5]

with open(os.path.join(OUT, "inputs.csv"), "w", encoding="utf-8", newline="\n") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["quantity", "policy", "value", "half_width_95", "unit", "n_traces", "source"])
    for p, _, _ in BARS:
        v = vals[p]
        w.writerow(["violating windows", p, v["viol"], v["viol_h"], "% of 15-min windows", v["n"], "T5_test_weeks.md new_spike"])
        w.writerow(["weekly cost", p, v["cost"], v["cost_h"], "USD/week", v["n"], "T5_test_weeks.md new_spike"])
    for r in short:
        w.writerow(["2048 MB headroom cheaper than best PRISM", f"ns{r['nonscaling']} D{r['deadline']}",
                    round(r["best_PredHead_2048_vs_best_PRISM_pct"], 2), "", "%", 2, "E4b_fixed_memory_summary.json"])

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2})
fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), facecolor=SURF)
for ax, key, h, ylab, fmt in ((axes[0], "viol", "viol_h", "Violating 15-min windows (%)", "{:.2f}%"),
                              (axes[1], "cost", "cost_h", "Weekly cost (USD)", "{:,.0f}")):
    ax.set_facecolor(SURF)
    xs = range(len(BARS))
    for x, (p, lab, col) in zip(xs, BARS):
        v = vals[p]
        ax.bar(x, v[key], width=0.56, color=col, edgecolor=SURF, linewidth=2, zorder=2)
        ax.errorbar(x, v[key], yerr=v[h], fmt="none", ecolor=INK2, elinewidth=1.2, capsize=4, zorder=3)
        ax.text(x, v[key] + v[h] * 1.08 + (0.15 if key == "viol" else 25), fmt.format(v[key]), ha="center", va="bottom",
                color=INK, fontsize=10)
    ax.set_xticks(list(xs), [b[1] for b in BARS])
    ax.set_ylabel(ylab)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="both", length=0)
axes[0].axhline(2.0, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
axes[0].text(1.5, 2.12, "2% target", va="bottom", ha="center", color=INK2, fontsize=9)
axes[1].set_ylim(0, max(vals[p]["cost"] + vals[p]["cost_h"] for p, _, _ in BARS) * 1.18)
fig.suptitle(TITLE, color=INK, fontsize=12.5, y=0.99)
fig.text(0.5, 0.015, LABEL, ha="center", va="bottom", color=INK2, fontsize=7.6, wrap=True)
fig.tight_layout(rect=(0, 0.06, 1, 0.93))
for ext in ("svg", "png"):
    fig.savefig(os.path.join(OUT, f"graphical_abstract_draft.{ext}"), dpi=200, facecolor=SURF)

cap = (f"Under a new spike, PRISM violated {vals['PRISM']['viol']:.2f}% of 15-minute windows (95% interval "
       f"+/-{vals['PRISM']['viol_h']:.2f}), against {vals['PredHead+hyst']['viol']:.2f}% (+/-{vals['PredHead+hyst']['viol_h']:.2f}) "
       f"for smoothed headroom and {vals['PredHead']['viol']:.2f}% (+/-{vals['PredHead']['viol_h']:.2f}) for unsmoothed headroom, "
       f"at a weekly cost of USD {vals['PRISM']['cost']:,.0f}, against {vals['PredHead+hyst']['cost']:,.0f} and "
       f"{vals['PredHead']['cost']:,.0f}: both headroom rules were cheaper, and PRISM did not meet the 2% target on average "
       f"(it met the target on {round(int(vals['PRISM']['slo_met'].rstrip('%')) * vals['PRISM']['n'] / 100)} of {vals['PRISM']['n']} traces). When the default 1024 MB cannot meet the deadline, PRISM selects a "
       f"larger memory size if its risk budget is small enough ("
       f"{'2048 MB or more in every epoch' if min(share) == 100 else f'2048 MB or more in {min(share):.0f}-{max(share):.0f}% of its epochs'} at eps 0.02); a fixed 2048 MB headroom rule met the deadline at {min(rng):.0f}-{max(rng):.0f}% lower cost in "
       f"the regimes tested (two traces, post hoc, no caps), and adaptation to changes in execution characteristics within a run was not tested. Fast simulator, "
       f"assumed constants, five development traces, Linux x86-64.")
open(os.path.join(OUT, "caption_draft.txt"), "w", encoding="utf-8", newline="\n").write(cap + "\n")
print(json.dumps(dict(headline=vals, caption_range_pct=[round(min(rng), 2), round(max(rng), 2)], share_ge2048=share,
                      default_deadline=[round(r["best_PredHead_2048_vs_best_PRISM_pct"], 2) for r in default]), indent=1))
print(cap)
