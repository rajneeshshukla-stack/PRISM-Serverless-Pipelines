#!/usr/bin/env python3
"""Group B (CAL12, the C3 deadline) analysis per RUN_PLAN.md: week counts, selections and grid edges (rule 2), paired
PRISM vs MemAdapt_q90 cost and compliance per trace, and the C3 part of readiness rule 3. Reads only the group and week
JSON written by cal_closed_loop.py. Standard library only.
usage: python analyse_group_B.py <run dir> <out prefix>
"""
import glob
import json
import os
import sys

RUN, PREFIX = sys.argv[1], sys.argv[2]
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "MemAdapt_q90")
BASE = {"PRISM": 6, "MemAdapt_q90": 10}          # GRIDS sizes: PRISM eps grid, QuantProv-type a grid
G = {}
for p in glob.glob(os.path.join(RUN, "groups", "CAL12", "group_*.json")):
    g = json.load(open(p))
    G[(g["seed"], g["family"])] = g
missing = [(s, f) for s in SEEDS for f in FAMS if (s, f) not in G]

week_files = glob.glob(os.path.join(RUN, "weeks", "CAL12", "*", "*", "*.json"))
unreadable = []
for p in week_files:
    try:
        json.load(open(p, encoding="utf-8"))
        if not os.path.exists(p[:-5] + ".npz"):
            unreadable.append(p)
    except Exception:
        unreadable.append(p)
planned_base = len(SEEDS) * sum(n + 1 for n in BASE.values())
expansions = sum(len(g["expansions"]) for g in G.values())


def short(r):
    return dict(param=r["param"], cost=round(r["cost"], 1), viol=round(100 * r["violating_window_rate"], 2),
                attain=round(100 * r["record_attainment"], 2), ge2048=round(100 * r["share_mem_ge_2048"], 1),
                counts_sha256=r["counts_sha256"])


rows, edges = [], {f: [] for f in FAMS}
for (s, f), g in sorted(G.items()):
    val = sorted(g["validation"], key=lambda r: r["param"])
    params = [r["param"] for r in val]
    i = params.index(g["selected"])
    rows.append(dict(seed=s, family=f, selected=g["selected"], expansions=g["expansions"], wide_bounds=g["wide_bounds"],
                     unresolved_edge=g["unresolved_edge"],
                     any_val_compliant=any(r["violating_window_rate"] <= 0.02 + 1e-12 for r in val),
                     selected_val=short(val[i]),
                     neighbours_val=[short(val[j]) for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(val)],
                     test=short(g["test"])))
    if g["unresolved_edge"]:
        edges[f].append(s)
T = {(r["seed"], r["family"]): r["test"] for r in rows}
paired = []
for s in SEEDS:
    if (s, "PRISM") in T and (s, "MemAdapt_q90") in T:
        p, m = T[(s, "PRISM")], T[(s, "MemAdapt_q90")]
        paired.append(dict(seed=s, prism_cost=p["cost"], memadapt_cost=m["cost"],
                           prism_premium_pct=round(100 * (p["cost"] / m["cost"] - 1), 1),
                           prism_viol=p["viol"], memadapt_viol=m["viol"],
                           prism_meets_2pct=p["viol"] <= 2.0, memadapt_meets_2pct=m["viol"] <= 2.0,
                           prism_ge2048=p["ge2048"], memadapt_ge2048=m["ge2048"],
                           same_stream=p["counts_sha256"] == m["counts_sha256"]))
streams = {}
for r in rows:
    streams.setdefault((r["seed"], "test"), set()).add(r["test"]["counts_sha256"])
    streams.setdefault((r["seed"], "val"), set()).add(r["selected_val"]["counts_sha256"])
identical = all(len(v) == 1 for v in streams.values())
edge_fail = {f: v for f, v in edges.items() if len(v) >= 2}
c3_ready = not missing and not unreadable and identical and not edge_fail
out = dict(weeks=dict(planned_base=planned_base, expansions_triggered=expansions, planned_total=planned_base + expansions,
                      completed=len(week_files) - len(unreadable), failed_or_unreadable=len(unreadable),
                      groups_missing=missing),
           rows=rows, paired=paired, edge_traces=edges, c3_edge_rule_failed_for=edge_fail,
           identical_request_streams=identical, c3_ready=c3_ready)
json.dump(out, open(PREFIX + ".json", "w"), indent=1)

w = out["weeks"]
L = ["Group B: CAL (per-size factors, rho 0.998, start-up truncated at 10 s), 12 s deadline, traces 101-105, "
     "prespecified tuning; stationary test week", "",
     f"Weeks: planned {w['planned_base']} base + {w['expansions_triggered']} edge expansions = {w['planned_total']}; "
     f"completed {w['completed']}; failed/unreadable {w['failed_or_unreadable']}; groups missing {missing or 'none'}", "",
     f"{'trace':>5} {'family':<13} {'sel':>6} {'edge':>5} {'compliant val?':>14} | test: {'cost':>7} {'viol%':>6} "
     f"{'attain%':>7} {'>=2048%':>7}"]
for r in rows:
    t = r["test"]
    L.append(f"{r['seed']:>5} {r['family']:<13} {r['selected']:>6} {'YES' if r['unresolved_edge'] else '-':>5} "
             f"{'yes' if r['any_val_compliant'] else 'none':>14} | {t['cost']:>13.1f} {t['viol']:>6.2f} "
             f"{t['attain']:>7.2f} {t['ge2048']:>7.1f}")
L += ["", "Neighbouring validation weeks at each selection (param: cost / violating % / >=2048 MB %):"]
for r in rows:
    sv = r["selected_val"]
    nb = "; ".join(f"{n['param']}: {n['cost']} / {n['viol']} / {n['ge2048']}" for n in r["neighbours_val"])
    L.append(f"  {r['seed']} {r['family']}: selected {sv['param']}: {sv['cost']} / {sv['viol']} / {sv['ge2048']}  | {nb}")
L += ["", "Paired test weeks (same request stream), PRISM vs MemAdapt_q90:"]
for p in paired:
    L.append(f"  {p['seed']}: cost {p['prism_cost']} vs {p['memadapt_cost']} (PRISM {p['prism_premium_pct']:+.1f}%); "
             f"violating {p['prism_viol']}% vs {p['memadapt_viol']}%; >=2048 MB {p['prism_ge2048']}% vs "
             f"{p['memadapt_ge2048']}%; same stream {p['same_stream']}")
L += ["", f"Unresolved edges (traces): {edges}",
      f"C3 edge rule (no C3 family at an unresolved edge on >=2/5): {'FAILED for ' + str(edge_fail) if edge_fail else 'passed'}",
      f"Identical request streams per (trace, week): {identical}",
      f"C3 readiness (Group B part of rule 3): {'READY' if c3_ready else 'NOT READY'}"]
open(PREFIX + ".txt", "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("\n".join(L))
