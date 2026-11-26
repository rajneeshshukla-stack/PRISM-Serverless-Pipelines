#!/usr/bin/env python3
"""Group A (CAL145) analysis per RUN_PLAN.md: interpretation rule 1 (14.5 s P2 finding), rule 2 (edges) and the
C1-C2 part of rule 3. Reads only the group JSON written by cal_closed_loop.py. Standard library only.
usage: python analyse_group_A.py <run dir> <out prefix>
"""
import glob
import json
import os
import sys

RUN, PREFIX = sys.argv[1], sys.argv[2]
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "QuantProv_q90", "Reactive", "MemAdapt_q90")
C12 = ("PRISM", "QuantProv_q90", "Reactive")
G = {}
for p in glob.glob(os.path.join(RUN, "groups", "CAL145", "group_*.json")):
    g = json.load(open(p))
    G[(g["seed"], g["family"])] = g
missing = [(s, f) for s in SEEDS for f in FAMS if (s, f) not in G]
if missing:
    raise SystemExit(f"incomplete group A: {missing}")


def short(r):
    return dict(param=r["param"], cost=round(r["cost"], 1), viol=round(100 * r["violating_window_rate"], 2),
                attain=round(100 * r["record_attainment"], 2), ge2048=round(100 * r["share_mem_ge_2048"], 1),
                requests=r["n_requests"], counts_sha256=r["counts_sha256"])


rows, edges = [], {}
for s in SEEDS:
    for f in FAMS:
        g = G[(s, f)]
        val = sorted(g["validation"], key=lambda r: r["param"])
        params = [r["param"] for r in val]
        i = params.index(g["selected"])
        neigh = [short(val[j]) for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(val)]
        rows.append(dict(seed=s, family=f, selected=g["selected"], expansions=g["expansions"],
                         wide_bounds=g["wide_bounds"], unresolved_edge=g["unresolved_edge"],
                         any_val_compliant=any(r["violating_window_rate"] <= 0.02 + 1e-12 for r in val),
                         selected_val=short(val[i]), neighbours_val=neigh, test=short(g["test"])))
        edges.setdefault(f, []).append(s) if g["unresolved_edge"] else None

T = {(r["seed"], r["family"]): r["test"] for r in rows}
rule1 = dict(
    ge2048_every_trace={f: all(T[(s, f)]["ge2048"] >= 95.0 for s in SEEDS) for f in ("PRISM", "MemAdapt_q90")},
    meets_2pct_traces={f: sum(T[(s, f)]["viol"] <= 2.0 for s in SEEDS) for f in ("PRISM", "MemAdapt_q90")},
    prism_costlier_traces=sum(T[(s, "PRISM")]["cost"] > T[(s, "MemAdapt_q90")]["cost"] for s in SEEDS),
    prism_premium_pct={s: round(100 * (T[(s, "PRISM")]["cost"] / T[(s, "MemAdapt_q90")]["cost"] - 1), 1)
                       for s in SEEDS})
rule1["verified"] = (all(rule1["ge2048_every_trace"].values()) and all(v >= 4 for v in rule1["meets_2pct_traces"].values())
                     and rule1["prism_costlier_traces"] >= 4)
edge_counts = {f: len(edges.get(f, [])) for f in FAMS}
c12_fail = {f: edges.get(f, []) for f in C12 if edge_counts[f] >= 2}
streams = {}
for r in rows:
    streams.setdefault((r["seed"], "test"), set()).add(r["test"]["counts_sha256"])
    streams.setdefault((r["seed"], "val"), set()).add(r["selected_val"]["counts_sha256"])
identical_streams = all(len(v) == 1 for v in streams.values())
out = dict(rows=rows, rule1=rule1, edge_traces={f: edges.get(f, []) for f in FAMS}, edge_counts=edge_counts,
           c12_edge_rule_failed_for=c12_fail, identical_request_streams=identical_streams)
json.dump(out, open(PREFIX + ".json", "w"), indent=1)

L = ["Group A: CAL (per-size factors, rho 0.998, start-up truncated at 10 s), 14.5 s, traces 101-105, "
     "prespecified tuning; stationary test week", ""]
L.append(f"{'trace':>5} {'family':<14} {'sel':>6} {'edge':>5} {'compliant val?':>14} | test: {'cost':>7} "
         f"{'viol%':>6} {'attain%':>7} {'>=2048%':>7}")
for r in rows:
    t = r["test"]
    L.append(f"{r['seed']:>5} {r['family']:<14} {r['selected']:>6} {'YES' if r['unresolved_edge'] else '-':>5} "
             f"{'yes' if r['any_val_compliant'] else 'none':>14} | {t['cost']:>13.1f} {t['viol']:>6.2f} "
             f"{t['attain']:>7.2f} {t['ge2048']:>7.1f}")
L += ["", "Neighbouring validation weeks (param: cost / violating % / >=2048 MB %):"]
for r in rows:
    if r["unresolved_edge"]:
        sv = r["selected_val"]
        nb = "; ".join(f"{n['param']}: {n['cost']} / {n['viol']} / {n['ge2048']}" for n in r["neighbours_val"])
        L.append(f"  {r['seed']} {r['family']}: selected {sv['param']}: {sv['cost']} / {sv['viol']} / {sv['ge2048']}"
                 f"  | {nb}")
L += ["", f"Rule 1 (14.5 s P2 finding): {'VERIFIED' if rule1['verified'] else 'NOT VERIFIED - revise as observed'}",
      f"  >=2048 MB in >=95% of epochs on every trace: {rule1['ge2048_every_trace']}",
      f"  traces meeting 2%: {rule1['meets_2pct_traces']} (need >=4 each)",
      f"  PRISM costlier than MemAdapt: {rule1['prism_costlier_traces']}/5 (need >=4); "
      f"premium %: {rule1['prism_premium_pct']}",
      "", f"Unresolved edges (traces): {out['edge_traces']}",
      f"C1-C2 edge rule (no C1-C2 family at an unresolved edge on >=2/5): "
      f"{'FAILED for ' + str(c12_fail) if c12_fail else 'passed'}",
      f"Identical request streams per (trace, week) across families: {identical_streams}"]
open(PREFIX + ".txt", "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("\n".join(L))
