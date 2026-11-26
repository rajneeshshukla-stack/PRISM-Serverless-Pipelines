#!/usr/bin/env python3
"""Corrected start-up rerun (init_scaling "constant"): week counts, selections and grid edges (RUN_PLAN.md rule 2),
paired PRISM vs MemAdapt-q90 cost and compliance per trace at 14.5 s (CAL145C) and 12 s (CAL12C), rule 1, and the
readiness rule 3. C1-C2 readiness combines the corrected PRISM groups with the saved Group A QuantProv-q90 and Reactive
groups, only if the equivalence check passed. Also compares each corrected group with its Eq. (3) counterpart.
usage: python analyse_p3.py <old run dir> <new run dir> <equivalence.txt> <out prefix>
"""
import glob
import json
import os
import sys

OLD, NEW, EQV, PREFIX = sys.argv[1:5]
SEEDS = (101, 102, 103, 104, 105)
FAMS = ("PRISM", "MemAdapt_q90")
BASE = {"PRISM": 6, "MemAdapt_q90": 10}
equiv = "VERDICT: fixed-1024 MB results are equivalent" in open(EQV, encoding="utf-8").read()


def groups(run, st):
    return {(g["seed"], g["family"]): g for g in
            (json.load(open(p)) for p in glob.glob(os.path.join(run, "groups", st, "group_*.json")))}


def short(r):
    return dict(param=r["param"], cost=round(r["cost"], 1), viol=round(100 * r["violating_window_rate"], 2),
                attain=round(100 * r["record_attainment"], 2), ge2048=round(100 * r["share_mem_ge_2048"], 1),
                prov=round(r["mean_provisioned"], 1), counts_sha256=r["counts_sha256"])


out, L = {}, []
for st, old_st, dl in (("CAL145C", "CAL145", "14.5 s"), ("CAL12C", "CAL12", "12 s")):
    G, GO = groups(NEW, st), groups(OLD, old_st)
    missing = [(s, f) for s in SEEDS for f in FAMS if (s, f) not in G]
    files = [p for f in FAMS for p in glob.glob(os.path.join(NEW, "weeks", st, "*", f, "*.json"))]
    eq_files = [p for f in ("QuantProv_q90", "Reactive") for p in glob.glob(os.path.join(NEW, "weeks", st, "*", f, "*.json"))]
    bad = [p for p in files if not os.path.exists(p[:-5] + ".npz")]
    keys = [(g["seed"], g["family"], r["param"], "val") for g in G.values() for r in g["validation"]] + \
           [(g["seed"], g["family"], g["test"]["param"], "test") for g in G.values()]
    exp = sum(len(g["expansions"]) for g in G.values())
    wk = dict(planned_base=len(SEEDS) * sum(n + 1 for n in BASE.values()), expansions=exp,
              planned_total=len(SEEDS) * sum(n + 1 for n in BASE.values()) + exp, week_files=len(files),
              group_weeks=len(keys), duplicates=len(keys) - len(set(keys)), missing_npz=len(bad), groups_missing=missing,
              orphan_weeks=len(files) - len(keys), equivalence_weeks=len(eq_files))
    rows, edges, paired = [], {f: [] for f in FAMS}, []
    for (s, f), g in sorted(G.items()):
        val = sorted(g["validation"], key=lambda r: r["param"])
        ps = [r["param"] for r in val]
        i = ps.index(g["selected"])
        o = GO.get((s, f))
        rows.append(dict(seed=s, family=f, selected=g["selected"], expansions=g["expansions"],
                         unresolved_edge=g["unresolved_edge"], wide_bounds=g["wide_bounds"],
                         any_val_compliant=any(r["violating_window_rate"] <= 0.02 + 1e-12 for r in val),
                         val=[short(r) for r in val], selected_val=short(val[i]),
                         neighbours_val=[short(val[j]) for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(val)],
                         test=short(g["test"]), eq3_selected=o["selected"] if o else None,
                         eq3_test=short(o["test"]) if o else None))
        if g["unresolved_edge"]:
            edges[f].append(s)
    T = {(r["seed"], r["family"]): r["test"] for r in rows}
    for s in SEEDS:
        if (s, "PRISM") in T and (s, "MemAdapt_q90") in T:
            p, m = T[(s, "PRISM")], T[(s, "MemAdapt_q90")]
            paired.append(dict(seed=s, prism=p, memadapt=m, premium_pct=round(100 * (p["cost"] / m["cost"] - 1), 1),
                               viol_diff_pts=round(m["viol"] - p["viol"], 2), same_stream=p["counts_sha256"] == m["counts_sha256"]))
    streams = {}
    for r in rows:
        streams.setdefault((r["seed"], "test"), set()).add(r["test"]["counts_sha256"])
        streams.setdefault((r["seed"], "val"), set()).add(r["selected_val"]["counts_sha256"])
    rule1 = None
    if st == "CAL145C" and len(paired) == 5:
        rule1 = dict(ge2048_every_trace={f: all(T[(s, f)]["ge2048"] >= 95 for s in SEEDS) for f in FAMS},
                     meets_2pct={f: sum(T[(s, f)]["viol"] <= 2.0 for s in SEEDS) for f in FAMS},
                     prism_costlier=sum(x["premium_pct"] > 0 for x in paired))
        rule1["verified"] = (all(rule1["ge2048_every_trace"].values()) and all(v >= 4 for v in rule1["meets_2pct"].values())
                             and rule1["prism_costlier"] >= 4)
    out[st] = dict(weeks=wk, rows=rows, paired=paired, edges=edges, identical_streams=all(len(v) == 1 for v in streams.values()),
                   rule1=rule1)
    L += ["", f"=== {st}: CAL with init_scaling 'constant', {dl}, traces 101-105, PRISM and MemAdapt-q90 ===",
          f"Weeks: planned {wk['planned_base']} base + {exp} expansions = {wk['planned_total']}; week files {wk['week_files']}; "
          f"group weeks {wk['group_weeks']}; orphans {wk['orphan_weeks']}; duplicates {wk['duplicates']}; missing npz {wk['missing_npz']}; "
          f"groups missing {missing or 'none'} (plus {wk['equivalence_weeks']} fixed-1024 MB equivalence weeks, group E)",
          f"{'trace':>5} {'family':<13} {'sel':>6} {'edge':>5} | test: {'cost':>7} {'viol%':>6} {'attain%':>7} {'>=2048%':>7} {'prov':>6} | Eq.(3): sel, cost, viol%"]
    for r in rows:
        t, o = r["test"], r["eq3_test"] or {}
        L.append(f"{r['seed']:>5} {r['family']:<13} {r['selected']:>6} {'YES' if r['unresolved_edge'] else '-':>5} | "
                 f"{t['cost']:>13.1f} {t['viol']:>6.2f} {t['attain']:>7.2f} {t['ge2048']:>7.1f} {t['prov']:>6.1f} | "
                 f"{r['eq3_selected']}, {o.get('cost')}, {o.get('viol')}")
    L.append("Validation grids (param: cost / violating % / >=2048 MB %):")
    for r in rows:
        L.append(f"  {r['seed']} {r['family']}: " + "; ".join(f"{v['param']}: {v['cost']} / {v['viol']} / {v['ge2048']}" for v in r["val"]))
    L.append("Paired test weeks, PRISM vs MemAdapt-q90:")
    for x in paired:
        L.append(f"  {x['seed']}: cost {x['prism']['cost']} vs {x['memadapt']['cost']} (PRISM {x['premium_pct']:+.1f}%); violating "
                 f"{x['prism']['viol']}% vs {x['memadapt']['viol']}% (MemAdapt minus PRISM {x['viol_diff_pts']:+.2f} pts); "
                 f"attainment {x['prism']['attain']}% vs {x['memadapt']['attain']}%; same stream {x['same_stream']}")
    L.append(f"Unresolved edges (traces): {edges}; identical request streams: {out[st]['identical_streams']}")
    if rule1:
        L.append(f"Rule 1 (14.5 s P2 finding): {'VERIFIED' if rule1['verified'] else 'NOT VERIFIED'} {rule1}")

c12 = out["CAL145C"]["edges"]["PRISM"]
old_a = groups(OLD, "CAL145")
qr = {f: [s for s in SEEDS if old_a[(s, f)]["unresolved_edge"]] for f in ("QuantProv_q90", "Reactive")} if equiv else None
c12_fail = {f: v for f, v in ({"PRISM": c12, **(qr or {})}).items() if len(v) >= 2}
c3_fail = {f: v for f, v in out["CAL12C"]["edges"].items() if len(v) >= 2}
complete = all(not out[s]["weeks"]["groups_missing"] and not out[s]["weeks"]["duplicates"] and not out[s]["weeks"]["missing_npz"]
               and not out[s]["weeks"]["orphan_weeks"]
               and out[s]["identical_streams"] for s in out)
out["readiness"] = dict(equivalence_passed=equiv, reused_fixed_1024=qr, complete=complete,
                        c1c2_edge_fail=c12_fail, c3_edge_fail=c3_fail,
                        c1c2_ready=bool(equiv and complete and not c12_fail), c3_ready=bool(complete and not c3_fail))
L += ["", f"Equivalence of fixed-1024 MB results under the two start-up settings: {'PASSED' if equiv else 'NOT PASSED'}",
      f"C1-C2 (14.5 s; PRISM corrected, QuantProv-q90 and Reactive reused from Group A{'' if equiv else ' - NOT reused'}): "
      f"edges {({'PRISM': c12, **(qr or {})})}; {'READY' if out['readiness']['c1c2_ready'] else 'NOT READY'}",
      f"C3 (12 s; PRISM and MemAdapt-q90 corrected): edges {out['CAL12C']['edges']}; {'READY' if out['readiness']['c3_ready'] else 'NOT READY'}"]
json.dump(out, open(PREFIX + ".json", "w"), indent=1)
open(PREFIX + ".txt", "w", encoding="utf-8", newline="\n").write("\n".join(L).lstrip("\n") + "\n")
print("\n".join(L))
