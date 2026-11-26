#!/usr/bin/env python3
"""Per-trace supplementary tables for the ablation and the QuantProv memory results (R5.m4). Stored rows only.

Reviewer 5 (minor 4): "No table shows the per-trace ablation and QuantProv memory results given there; they belong
in the supplement." This builds both tables per trace from the stored submitted rows, with no new simulation, and
checks that their means over traces reproduce the stored mean tables (results/tables/E3_ablation_conformal_oracle.md
and results/tables/R2_quantprov_memory.md) to the printed precision. Values are the SUBMITTED ones (pre-calibration)
and change at the regeneration; the tables are for the supplement once regenerated.

  Ablation (E3, test weeks, PRISM at each trace's validation-chosen eps): PRISM (E1 row), no conformal recalibration
  (E3 tag noconf), forecast oracle (E3 tag oracle), and, for the two scenarios E3 ran them in, the no-scale-in-rule
  variant at the same eps (E3 tag nohyst) and quantile feasibility mode (E3 tag qmode).
  QuantProv memory (R2 and E4b, two traces, six regimes): per trace, the cheapest grid point with <= 2% violating
  windows on the TEST week, else the least violating (test-week knowledge, as the stored analysis; POST HOC).

Usage: python supplement_pertrace_tables.py <code_root> <out_dir>
"""
import glob
import json
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
L = lambda p: [json.loads(l) for f in sorted(glob.glob(os.path.join(ROOT, p))) for l in open(f, encoding="utf-8") if l.strip()]  # noqa
SC = ("stationary", "growth", "bursty", "new_spike")
SEEDS = (101, 102, 103, 104, 105)


def sel(rs):
    ok = [r for r in rs if r["violating_window_rate"] <= 0.02 + 1e-12]
    return min(ok, key=lambda r: (r["cost"], r["violating_window_rate"])) if ok else \
        min(rs, key=lambda r: (r["violating_window_rate"], r["cost"]))


def fmt(r):
    return f"{r['cost']:,.0f} / {100 * r['violating_window_rate']:.2f}%"


lines, checks = [], []
# ------------------------------------------------------------------ ablation
e1 = [r for r in L("results/raw/E1/rows.jsonl") if r.get("status") == "ok"]
e3 = [r for r in L("results/raw/E3/rows.jsonl") if r.get("status") == "ok"]
eps = {}
for s in SEEDS:
    v = [r for r in e1 if r["seed"] == s and r["week"] == "val" and r["spec"]["family"] == "PRISM" and not r.get("tag")]
    eps[s] = sel(v)["spec"]["param"]
lines += ["# Per-trace PRISM ablations (SUBMITTED rows, test weeks; cost USD / violating windows)", "",
          "PRISM at each trace's validation-chosen eps; the variants use the same eps. Pre-calibration; values change at",
          "the regeneration. Built by scripts/revision/supplement_pertrace_tables.py from results/raw/E1 and results/raw/E3.",
          "", "| Trace | eps | Scenario | PRISM | No conformal | Oracle forecast | No scale-in rule | Quantile feasibility |",
          "|---|---|---|---|---|---|---|---|"]
agg = {sc: {k: [] for k in ("prism", "noconf", "oracle")} for sc in SC}
for s in SEEDS:
    for sc in SC:
        p = [r for r in e1 if r["seed"] == s and r["week"] == "test" and r["scenario"] == sc
             and r["spec"]["family"] == "PRISM" and r["spec"].get("param") == eps[s] and not r.get("tag")]
        nc = [r for r in e3 if r["seed"] == s and r["scenario"] == sc and r["tag"] == "noconf"]
        orc = [r for r in e3 if r["seed"] == s and r["scenario"] == sc and r["tag"] == "oracle"]
        nh = [r for r in e3 if r["seed"] == s and r["scenario"] == sc and r["tag"] == "nohyst"
              and r["spec"].get("param") == eps[s]]
        qm = [r for r in e3 if r["seed"] == s and r["scenario"] == sc and r["tag"] == "qmode"]
        assert len(p) == 1 and len(nc) == 1 and len(orc) == 1, (s, sc, len(p), len(nc), len(orc))
        for k, x in (("prism", p[0]), ("noconf", nc[0]), ("oracle", orc[0])):
            agg[sc][k].append(x)
        lines.append(f"| {s} | {eps[s]:g} | {sc} | {fmt(p[0])} | {fmt(nc[0])} | {fmt(orc[0])} | "
                     f"{fmt(nh[0]) if nh else 'not run'} | {fmt(qm[0]) if qm else 'not run'} |")
lines += ["", "Mean over the five traces (must equal results/tables/E3_ablation_conformal_oracle.md):", "",
          "| Scenario | PRISM | No conformal | Oracle | traces where removing conformal raised violations |", "|---|---|---|---|---|"]
stored = open(os.path.join(ROOT, "results", "tables", "E3_ablation_conformal_oracle.md"), encoding="utf-8").read()
for sc in SC:
    m = {k: (sum(r["cost"] for r in v) / 5, 100 * sum(r["violating_window_rate"] for r in v) / 5) for k, v in agg[sc].items()}
    raised = sum(a["violating_window_rate"] > b["violating_window_rate"] for a, b in zip(agg[sc]["noconf"], agg[sc]["prism"]))
    row = (f"| {sc} | {m['prism'][0]:,.0f} / {m['prism'][1]:.2f}% | {m['noconf'][0]:,.0f} / {m['noconf'][1]:.2f}% | "
           f"{m['oracle'][0]:,.0f} / {m['oracle'][1]:.2f}% | {raised}/5 |")
    lines.append(row)
    probe = f"{m['prism'][0]:,.0f} / {m['prism'][1]:.2f}%"
    checks.append((f"ablation mean {sc}", probe in stored and f"{m['noconf'][0]:,.0f} / {m['noconf'][1]:.2f}%" in stored
                   and f"{m['oracle'][0]:,.0f} / {m['oracle'][1]:.2f}%" in stored))
# ------------------------------------------------------------------ QuantProv memory
r2 = L("results/raw/R2/r2_seed*.jsonl")
e4b = L("results/raw/E4b/e4b_seed*.jsonl")
pe = L("results/raw/E4b/e4b_prism_eps_seed*.jsonl")
lines += ["", "", "# Per-trace QuantProv memory results (SUBMITTED rows, stationary test week; POST HOC selection)", "",
          "Per trace, the cheapest grid point with at most 2% violating windows on the test week, else the least violating",
          "(test-week knowledge, as results/tables/R2_quantprov_memory.md). Cell: cost USD / violating windows (setting).",
          "Built from results/raw/R2 and results/raw/E4b.", "",
          "| Non-scaling | Deadline s | Trace | PRISM with memory | QP-q90 1024 | QP-q99 1024 | QP-q90 2048 | QP-q99 2048 | PredHead 1024 | PredHead 2048 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
stored2 = open(os.path.join(ROOT, "results", "tables", "R2_quantprov_memory.md"), encoding="utf-8").read()
for ns, D in [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]:
    g = [r for r in r2 if r["nonscaling"] == ns and r["deadline"] == D]
    h = [r for r in e4b if r["nonscaling"] == ns and r["deadline"] == D]
    means = {}
    for s in (101, 102):
        cells = []
        bp = sel([r for r in pe if r["seed"] == s and r["nonscaling"] == ns and r["deadline"] == D])
        cells.append(f"{fmt(bp)} (eps {bp['eps']:g})")
        means.setdefault("PRISM", []).append(bp)
        for mm in (1024, 2048):          # column order of the header: q90 1024, q99 1024, q90 2048, q99 2048
            for nm in ("q90", "q99"):
                b = sel([r for r in g if r["seed"] == s and r["label"].startswith(f"QuantProv_{nm}{mm}-")])
                cells.append(f"{fmt(b)} (a {b['spec']['param']:g})")
                means.setdefault(f"{nm}{mm}", []).append(b)
        for mm in (1024, 2048):
            b = sel([r for r in h if r["seed"] == s and r["label"].startswith(f"PredHead{mm}-")])
            cells.append(f"{fmt(b)} (h {b['spec']['param']:g})")
            means.setdefault(f"PH{mm}", []).append(b)
        lines.append(f"| {ns} | {D} | {s} | " + " | ".join(cells) + " |")
    for k, v in means.items():
        probe = f"{sum(r['cost'] for r in v) / 2:,.0f} / {100 * sum(r['violating_window_rate'] for r in v) / 2:.2f}"
        checks.append((f"memory mean {ns}/{D} {k}", probe in stored2))
lines += ["", "Reproduction of the stored mean tables from these per-trace values:", ""]
lines += [f"- {name}: {'reproduced' if ok else 'NOT REPRODUCED'}" for name, ok in checks]
txt = "\n".join(lines) + "\n"
with open(os.path.join(OUT, "pertrace_tables.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print(txt)
print(f"checks: {sum(ok for _, ok in checks)} of {len(checks)} reproduced")
sys.exit(0 if all(ok for _, ok in checks) else 1)
