#!/usr/bin/env python3
"""Driver check (RUN_PLAN.md section 2, step 2): does closed_loop_confirmatory.py reproduce the saved exploratory pilot
for trace 101? Compares every saved field of group_101_<family>.json (selection, expansions, edge hit, every validation
row and the stationary test row) except runtime_s, which is wall time, and commit.

usage: python compare_pilot101.py <saved pilot run dir> <new groups dir>   (prints the report; exit 1 on any mismatch)"""
import json
import os
import sys

SAVED, NEW = sys.argv[1], sys.argv[2]
SKIP = {"runtime_s"}
bad, n_rows, n_fields = [], 0, 0
for fam in ("PRISM", "QuantProv_q90", "Reactive", "MemAdapt_q90"):
    a = json.load(open(os.path.join(SAVED, f"group_101_{fam}.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(NEW, f"group_101_{fam}.json"), encoding="utf-8"))
    for k in ("grid", "expansions", "selected", "edge_hit"):
        if a[k] != b[k]:
            bad.append((fam, k, a[k], b[k]))
    av = {r["param"]: r for r in a["validation"]}
    bv = {r["param"]: r for r in b["validation"]}
    if sorted(av) != sorted(bv):
        bad.append((fam, "validation params", sorted(av), sorted(bv)))
    pairs = [(f"val {p}", av[p], bv.get(p)) for p in sorted(av)] + [("test", a["test"], b["test"])]
    for label, ra, rb in pairs:
        n_rows += 1
        if rb is None:
            bad.append((fam, label, "missing in new"))
            continue
        for k, v in ra.items():
            if k in SKIP:
                continue
            n_fields += 1
            if rb.get(k) != v:
                bad.append((fam, label, k, v, rb.get(k)))
    rt_a = sum(r["runtime_s"] for r in a["validation"]) + a["test"]["runtime_s"]
    rt_b = sum(r["runtime_s"] for r in b["validation"]) + b["test"]["runtime_s"]
    print(f"{fam:14s} selected {a['selected']} -> {b['selected']}; expansions {a['expansions']} -> {b['expansions']}; "
          f"rows {len(av) + 1}; week time saved {rt_a / 60:.1f} min, new {rt_b / 60:.1f} min")
print(f"compared {n_rows} rows, {n_fields} fields (runtime_s and commit excluded): "
      f"{'IDENTICAL' if not bad else f'{len(bad)} MISMATCHES'}")
for x in bad[:40]:
    print("  MISMATCH", x)
sys.exit(1 if bad else 0)
