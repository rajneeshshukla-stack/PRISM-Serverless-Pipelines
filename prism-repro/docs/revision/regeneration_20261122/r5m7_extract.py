#!/usr/bin/env python3
"""R5.M7 audit: extract, from one results tree, every figure the comment cites, so stored and regenerated values can
be set side by side. Reads tables only; runs nothing.

Sources (paper table -> file, as in prism-repro/README.md):
  (a) 13-29% pooled saving, per-trace range, omitted charges: results/tables/revision/pc_billing_bounds.txt,
      matched_compliance_pertrace.txt (Table VII family, POST HOC)
  (b) "within 1.6%", per-scenario spread at 1.5%: pc_billing_bounds.txt; posthoc_matched_compliance.txt section D
      (Table VII, POST HOC)
  (c), (e) orderings: results/tables/R1_real_traces.md (Table XII, POST HOC replay) and
      E1_aggregate_all_test_weeks.md (Suppl. Table S4)
  (d) paired cost intervals against QuantProv-q90: T6_paired_PRISM_vs_QuantProvq90.md (Table VI) and Table XII

usage: python r5m7_extract.py <prism-repro root> <out.json>
"""
import json
import os
import re
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
TAB = os.path.join(ROOT, "results", "tables")
R = lambda *p: open(os.path.join(TAB, *p), encoding="utf-8").read()  # noqa: E731
num = lambda s: float(s.replace(",", "").replace("+", ""))  # noqa: E731
out = {"root": ROOT.replace(os.sep, "/")}       # as given on the command line (relative paths keep private paths out)

# matched_compliance_pertrace.txt
mc, tgt = {}, None
for line in R("revision", "matched_compliance_pertrace.txt").splitlines():
    m = re.match(r"target ([\d.]+)%", line)
    if m:
        tgt = m.group(1)
        mc[tgt] = {}
        continue
    m = re.match(r"\s+PRISM vs (\S+)\s+([+-]?[\d.]+) ±\s+([\d.]+)%\s+\(n=(\d+); per trace \[([^\]]*)\]\)", line)
    if m and tgt:
        mc[tgt][m.group(1)] = dict(mean=num(m.group(2)), h=num(m.group(3)), n=int(m.group(4)),
                                   per_trace=[num(x) for x in m.group(5).split(",")])
out["matched_compliance_pertrace"] = mc

# pc_billing_bounds.txt, matched-compliance part
pcb, blk = {}, None
txt = R("revision", "pc_billing_bounds.txt")
for line in txt.split("## Matched compliance", 1)[1].splitlines():
    if line.strip() in ("cost", "cost_adj"):
        blk = line.strip()
        pcb[blk] = {}
        continue
    m = re.match(r"\s+PRISM vs (\S+)\s+([+-]?[\d.]+)%\s+([+-]?[\d.]+)%\s+([+-]?[\d.]+)%", line)
    if m and blk:
        pcb[blk][m.group(1)] = [num(m.group(i)) for i in (2, 3, 4)]
out["pc_billing_matched"] = pcb

# posthoc_matched_compliance.txt section D (Table VII)
d = R("revision", "posthoc_matched_compliance.txt").split("## D.", 1)[1].split("## E.", 1)[0]
t7 = {}
for part in d.split("### ")[1:]:
    scope = part.splitlines()[0].strip()
    t7[scope] = {}
    for line in part.splitlines()[3:]:
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) == 5:
            t7[scope][c[0]] = [None if "reach" in x else num(x) for x in c[2:5]]
spread = {}
for scope, fam in t7.items():
    row = {}
    for i, lev in enumerate(("1.0", "1.5", "2.0")):
        p = fam.get("PRISM", [None] * 3)[i]
        for f in ("QuantProv_q90", "PredHead+hyst"):
            v = fam.get(f, [None] * 3)[i]
            row[f"{f}@{lev}"] = None if p is None or v is None else round(100 * (p / v - 1), 2)
    spread[scope] = row
out["table7"] = t7
out["table7_prism_vs_pct"] = spread

# Table VI (T6 PRISM vs QuantProv-q90)
t6 = {}
for line in R("T6_paired_PRISM_vs_QuantProvq90.md").splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 7 and c[0] in ("stationary", "growth", "bursty", "new_spike"):
        m, h = [num(x) for x in c[2].split("±")]
        t6[c[0]] = dict(cost_pct=m, h=h, includes_zero=bool(m - h <= 0 <= m + h), viol_pp=c[3], n=int(c[6]))
out["table6_vs_QuantProv_q90"] = t6

# Table XII (R1)
r1 = R("R1_real_traces.md")
fam, paired = {}, {}
for line in r1.splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 6 and "±" in c[2] and c[0] != "Family":
        fam[c[0]] = dict(cost=num(c[2].split("±")[0]), viol=num(c[3].split("±")[0]))
    elif len(c) == 3 and "±" in c[1] and c[0] != "Comparator":
        m, rest = c[1].split("±")
        h = num(rest.split("(")[0])
        paired[c[0]] = dict(cost_pct=num(m), h=h, includes_zero=bool(num(m) - h <= 0 <= num(m) + h), viol=c[2])
out["table12_families"] = fam
out["table12_paired"] = paired
# Suppl. Table S4 (E1 aggregate)
s4 = {}
for line in R("E1_aggregate_all_test_weeks.md").splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 5 and c[0] and c[0][0].isalpha() and c[0] != "Policy" and not c[0].startswith(":"):
        s4[c[0]] = dict(cost=num(c[1]), viol=num(c[2]), slo_met=c[3])
out["tableS4"] = s4


def lab(x):
    return {"On-demand": "OnDemand", "PredHead+S": "PredHead+hyst", "QuantProv-q90": "QuantProv_q90",
            "QuantProv-q99": "QuantProv_q99"}.get(x, x)


o = {}
if fam:
    lowest = min(fam, key=lambda k: fam[k]["viol"])
    o["huawei_lowest_violating"] = lowest
    o["huawei_prism_cost_vs_quantprov"] = {lab(k): ("below" if fam["PRISM"]["cost"] < fam[k]["cost"] else "above")
                                           for k in ("QuantProv-q90", "QuantProv-q99") if k in fam}
if s4:
    o["synthetic_prism_cost_vs_quantprov"] = {k: ("below" if s4["PRISM"]["cost"] < s4[k]["cost"] else "above")
                                              for k in ("QuantProv_q90", "QuantProv_q99") if k in s4}
    o["synthetic_lowest_violating"] = min(s4, key=lambda k: s4[k]["viol"])
o["table6_all_include_zero"] = all(v["includes_zero"] for v in t6.values()) if t6 else None
o["table12_vs_QuantProv_q90_includes_zero"] = paired.get("QuantProv-q90", {}).get("includes_zero")
out["orderings"] = o
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps(o, indent=1))
print("pooled saving vs Static (cost):", pcb.get("cost", {}).get("Static"), "| vs Reactive:", pcb.get("cost", {}).get("Reactive"),
      "| vs Static (cost_adj):", pcb.get("cost_adj", {}).get("Static"))
print("per-trace vs Static at 1.0%:", mc.get("1.0", {}).get("Static", {}).get("per_trace"))
print("within-1.6% rows:", {k: pcb.get("cost", {}).get(k) for k in ("QuantProv_q90", "PredHead+hyst")})
print("Table VII at 1.5% (PRISM vs %):", {s: {k: v for k, v in r.items() if "@1.5" in k} for s, r in spread.items()})
