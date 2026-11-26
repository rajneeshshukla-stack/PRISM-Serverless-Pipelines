#!/usr/bin/env python3
"""R5.m4: complete the two per-trace supplement tables with the combinations run by r5m4_missing_runs.py.
EXPLORATORY, PRE-CALIBRATION, fast simulator, development traces (as the stored tables). Reads only; writes one file.

1. Ablation table: the "not run" cells of supplement_pertrace/pertrace_tables.md (no scale-in rule and quantile
   feasibility, growth and bursty test weeks) are filled from results/r5m4_missing/ablation_variants.jsonl. The same
   file reruns the stationary and new-spike cells, which must equal the E3-derived cells already in the table
   (consistency check, reported).
2. QuantProv memory table: per regime, trace, rule and memory size, the POST HOC selection (cheapest grid point with
   at most 2% violating windows on the test week, else the least violating; as results/tables/R2_quantprov_memory.md)
   is redone on the widened grid (GRIDS_WIDE: paper grid 0.6-1.5 plus 0.4, 0.5, 1.6, 1.8, 2.0) and set beside the
   paper-grid selection, with edge hits flagged.

usage: python r5m4_tables.py <regenerated tree prism-repro> <out.md>
"""
import json
import glob
import os
import re
import sys

TREE, OUT = sys.argv[1], sys.argv[2]
RES = os.path.join(TREE, "results")
cell = lambda c, v: f"{c:,.0f} / {100 * v:.2f}%"  # noqa: E731
jl = lambda p: [json.loads(l) for f in sorted(glob.glob(p)) for l in open(f, encoding="utf-8") if l.strip()]  # noqa: E731

# 1. ablation
ab = {(r["seed"], r["scenario"], r["variant"]): r for r in jl(os.path.join(RES, "r5m4_missing", "ablation_variants.jsonl"))}
src = open(os.path.join(RES, "tables", "revision", "supplement_pertrace", "pertrace_tables.md"), encoding="utf-8").read()
part1 = src.split("# Per-trace QuantProv memory results", 1)[0]
lines, filled, checks = [], 0, []
for line in part1.splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 8 and c[0].isdigit():
        seed, sc = int(c[0]), c[2]
        got = {v: cell(ab[(seed, sc, v)]["cost"], ab[(seed, sc, v)]["violating_window_rate"]) for v in ("nohyst", "qmode")}
        if c[6] == "not run" and c[7] == "not run":
            c[6], c[7] = got["nohyst"] + " (new)", got["qmode"] + " (new)"
            filled += 2
        else:
            checks.append((seed, sc, c[6] == got["nohyst"], c[7] == got["qmode"], c[6], got["nohyst"], c[7], got["qmode"]))
        line = "| " + " | ".join(c) + " |"
    lines.append(line)
part1 = "\n".join(lines)
part1 = part1.replace("# Per-trace PRISM ablations (REGENERATED rows at fd8b01a, test weeks;",
                      "# Per-trace PRISM ablations, complete (REGENERATED rows at fd8b01a, test weeks;", 1)

# 2. QuantProv widened grid
r2 = jl(os.path.join(RES, "raw", "R2", "r2_seed*.jsonl"))
wd = jl(os.path.join(RES, "r5m4_missing", "quantprov_memory_widened.jsonl"))
param = lambda r: r["spec"]["param"] if "spec" in r else r["param"]  # noqa: E731


def pick(rs):
    ok = [r for r in rs if r["violating_window_rate"] <= 0.02 + 1e-12]
    return min(ok, key=lambda r: (r["cost"], r["violating_window_rate"])) if ok else \
        min(rs, key=lambda r: (r["violating_window_rate"], r["cost"]))


rows2, changed, edge_paper, edge_wide, n2 = [], 0, 0, 0, 0
edge_kind = {"infeasible at every a (least violating, then cheapest)": 0,
             "meets 2% at the grid end (cost would fall further)": 0}
regimes = sorted({(r["nonscaling"], r["deadline"]) for r in r2}, key=lambda x: (-x[0], -x[1]))
for ns, D in regimes:
    for seed in (101, 102):
        for fam in ("q90", "q99"):
            for mem in (1024, 2048):
                lab = f"QuantProv_{fam}{mem}"
                paper = [r for r in r2 if r["seed"] == seed and r["nonscaling"] == ns and r["deadline"] == D
                         and r["label"].split("-")[0] == lab]
                extra = [r for r in wd if r["seed"] == seed and r["nonscaling"] == ns and r["deadline"] == D
                         and r["label"].split("-")[0] == lab]
                assert len(paper) == 10 and len(extra) == 5, (ns, D, seed, lab, len(paper), len(extra))
                p, w = pick(paper), pick(paper + extra)
                pg, wg = sorted(param(r) for r in paper), sorted(param(r) for r in paper + extra)
                ep, ew = param(p) in (pg[0], pg[-1]), param(w) in (wg[0], wg[-1])
                if ew:
                    infeasible = all(r["violating_window_rate"] > 0.02 + 1e-12 for r in paper + extra)
                    edge_kind["infeasible at every a (least violating, then cheapest)" if infeasible else
                              "meets 2% at the grid end (cost would fall further)"] += 1
                n2 += 1
                changed += param(p) != param(w)
                edge_paper += ep
                edge_wide += ew
                rows2.append(f"| {ns} | {D} | {seed} | QP-{fam} {mem} | {cell(p['cost'], p['violating_window_rate'])} (a {param(p)}"
                             f"{', edge' if ep else ''}) | {cell(w['cost'], w['violating_window_rate'])} (a {param(w)}"
                             f"{', edge' if ew else ''}) | {'yes' if param(p) != param(w) else 'no'} |")

out = [part1.rstrip(), "",
       f"Filled cells: {filled} (marked \"(new)\"): no scale-in rule and quantile feasibility for the growth and bursty test",
       "weeks, run by docs/revision/regeneration_20261122/r5m4_missing_runs.py at the same validation-selected eps.",
       f"Consistency: the stationary and new-spike cells rerun by the same script equal the E3-derived cells in "
       f"{sum(a and b for _, _, a, b, *_ in checks)} of {len(checks)} rows.", ""]
bad = [c for c in checks if not (c[2] and c[3])]
if bad:
    out += ["Rows that differ (table cell vs rerun):", ""] + [f"- {s} {sc}: no scale-in {a} vs {b}; quantile {x} vs {y}"
                                                           for s, sc, _, _, a, b, x, y in bad] + [""]
out += ["", "# QuantProv memory results on the widened grid (REGENERATED rows at fd8b01a, stationary test week; POST HOC)", "",
        "Same selection rule as results/tables/R2_quantprov_memory.md (cheapest grid point with at most 2% violating",
        "windows on the test week, else the least violating). Paper grid a = 0.6-1.5 (results/raw/R2); widened grid adds",
        "a = 0.4, 0.5, 1.6, 1.8, 2.0 (experiment.GRIDS_WIDE; results/r5m4_missing/quantprov_memory_widened.jsonl).",
        "\"edge\" = the selection is at an end of the grid searched.", "",
        "| Non-scaling | Deadline s | Trace | Rule, memory MB | Paper grid | Widened grid | Selection changed |",
        "|---|---|---|---|---|---|---|"] + rows2 + ["",
        f"Selections changed by widening: {changed} of {n2}. Edge selections: paper grid {edge_paper} of {n2}; "
        f"widened grid {edge_wide} of {n2}.",
        "Widened-grid edge selections by kind: " + "; ".join(f"{k}: {v}" for k, v in edge_kind.items()) + ".",
        "Where the rule still meets 2% at a = 0.4 (all at 2048 MB), the QuantProv cost is an upper bound set by the grid,",
        "so the stored QuantProv-2048 costs (paper grid, a = 0.6) overstate what the rule can reach; this weakens, not",
        "strengthens, the comparison in PRISM's favour. The 1024 MB cells at deadlines of 13 s or less violate 100% of",
        "windows at every a, so their selection is the cheapest infeasible setting and the edge flag carries no meaning.", ""]
open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print(f"filled {filled}; consistency {sum(a and b for _, _, a, b, *_ in checks)}/{len(checks)}; "
      f"widened changed {changed}/{n2}; edge paper {edge_paper}, widened {edge_wide}")
