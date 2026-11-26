#!/usr/bin/env python3
"""Analysis of the EXPLORATORY closed-loop runs (scripts/revision/closed_loop_exploratory.py), PRE-CALIBRATION.
usage: python closed_loop_exploratory_analyse.py kappa <out dir> <result.json>
       python closed_loop_exploratory_analyse.py families <out dir> <result.json>
Coverage checks: expected groups and weeks present, no stray or duplicate week files, failures.json empty, identical
request streams (counts_sha256) for every family on the same trace and week."""
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

SEEDS = (101, 102, 103, 104, 105)
SCEN = ("stationary", "growth", "bursty", "new_spike")


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def summ(x):
    return dict(mean=float(np.mean(x)), hw=hw(x), n=len(x))


def load_weeks(out, set_name):
    rows = {}
    for p in glob.glob(os.path.join(out, "weeks", set_name, "*", "*", "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        k = (r["seed"], r["family"], r["week"], r["scenario"], json.dumps(r["param"]))
        assert k not in rows, ("duplicate", k)
        rows[k] = dict(r, _path=p)
    return rows


def arrays(r):
    p = r["_path"][:-5] + ".npz"
    return dict(np.load(p)) if os.path.exists(p) else None


def groups(out, set_name):
    return {(g["seed"], g["family"]): g for g in
            (json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(out, "groups", set_name, "*.json")))}


def coverage(out, sets_fams):
    fails = json.load(open(os.path.join(out, "failures.json"), encoding="utf-8")) if os.path.exists(
        os.path.join(out, "failures.json")) else []
    rep = dict(failures=len(fails), groups={}, request_streams_identical=True)
    shas = defaultdict(set)
    for sn, fams in sets_fams.items():
        G = groups(out, sn)
        W = load_weeks(out, sn)
        for r in W.values():
            shas[(r["seed"], r["week"], r["scenario"])].add(r["counts_sha256"])
        missing = [(s, f) for s in SEEDS for f in fams if (s, f) not in G]
        bad_tests = [(s, f) for (s, f), g in G.items() if len(g["tests"]) != len(SCEN)]
        rep["groups"][sn] = dict(expected=len(SEEDS) * len(fams), present=len(G), missing=missing,
                                 incomplete=bad_tests, weeks=len(W))
    rep["request_streams_identical"] = all(len(v) == 1 for v in shas.values())
    return rep


def test_row(G, seed, fam, sc):
    g = G[(seed, fam)]
    return next(t for t in g["tests"] if t["scenario"] == sc)


def paired(a_rows, b_rows):
    """b minus a, per scenario: cost % (relative to a), violating windows (points); over the traces present in b."""
    out = {}
    for sc in SCEN:
        ss = [s for s in SEEDS if (s, sc) in b_rows]
        dc = [100 * (b_rows[(s, sc)]["cost"] - a_rows[(s, sc)]["cost"]) / a_rows[(s, sc)]["cost"] for s in ss]
        dv = [100 * (b_rows[(s, sc)]["violating_window_rate"] - a_rows[(s, sc)]["violating_window_rate"]) for s in ss]
        c, v = summ(dc), summ(dv)
        out[sc] = dict(cost_pct=c, viol_pp=v, lower_cost=sum(x < 0 for x in dc), fewer_viol=sum(x < 0 for x in dv),
                       cost_excl0=bool(abs(c["mean"]) > c["hw"]), viol_excl0=bool(abs(v["mean"]) > v["hw"]),
                       comparable=bool(abs(v["mean"]) + v["hw"] <= 0.5), traces=ss, per_trace_cost=dc, per_trace_viol=dv)
    return out


def table(rows):
    res = {}
    for sc in SCEN:
        c = [rows[(s, sc)]["cost"] for s in SEEDS]
        v = [100 * rows[(s, sc)]["violating_window_rate"] for s in SEEDS]
        res[sc] = dict(cost=summ(c), viol=summ(v), met=sum(x <= 2.0 + 1e-9 for x in v))
    return res


def kappa(out, res_path):
    A, B, F = "PRISM", "PRISM_kfloor0001", "PRISM_kfrozen01"
    G = groups(out, "K")
    W = load_weeks(out, "K")
    cov = coverage(out, {"K": (A, B, F)})
    sel = {s: G[(s, A)]["selected"] for s in SEEDS}
    tuned = {f: {(s, sc): test_row(G, s, f, sc) for s in SEEDS for sc in SCEN} for f in (A, B, F)}
    sens = {}
    for f in (B, F):
        sens[f] = {}
        for s in SEEDS:
            for sc in SCEN:
                k = (s, f, "test", sc, json.dumps(sel[s]))
                if k in W and arrays(W[k]) is not None:
                    sens[f][(s, sc)] = W[k]
    # kappa diagnostics on A's tuned test weeks and the sensitivity weeks, and decision differences against A
    diag = defaultdict(list)
    dec = {f: defaultdict(list) for f in (B, F)}
    for s in SEEDS:
        for sc in SCEN:
            a = tuned[A][(s, sc)]
            aw = W[(s, A, "test", sc, json.dumps(sel[s]))]
            arrA = arrays(aw)
            diag["A_at_floor_0p1"].append(a["kappa_at_floor_share"])
            diag["A_kappa_mean"].append(a["kappa_mean"])
            diag["A_kappa_p05"].append(a["kappa_p05"])
            for f in (B, F):
                if (s, sc) not in sens[f]:
                    continue
                b = sens[f][(s, sc)]
                arrB = arrays(b)
                if f == B:
                    diag["B_below_0p1"].append(b["kappa_at_or_below_0p1_share"])
                    diag["B_kappa_mean"].append(b["kappa_mean"])
                    diag["B_kappa_p05"].append(b["kappa_p05"])
                else:
                    diag["F_kappa_mean"].append(b["kappa_mean"])
                pdiff = np.any(arrA["P_epoch"] != arrB["P_epoch"], axis=1)
                mdiff = arrA["mem_epoch"] != arrB["mem_epoch"]
                dec[f]["epochs_P_differs"].append(float(pdiff.mean()))
                dec[f]["epochs_mem_differs"].append(float(mdiff.mean()))
                dec[f]["mean_provisioned_diff"].append(float(arrB["P_epoch"].sum(1).mean() - arrA["P_epoch"].sum(1).mean()))
    # validation-week kappa (A) at every eps
    val_floor = [r["kappa_at_floor_share"] for k, r in W.items() if k[1] == A and k[2] == "val"]
    res = dict(label="EXPLORATORY, PRE-CALIBRATION, closed-loop event level, development traces 101-105, Linux",
               coverage=cov, selected={f: {s: G[(s, f)]["selected"] for s in SEEDS} for f in (A, B, F)},
               expansions={f: {s: G[(s, f)]["expansions"] for s in SEEDS} for f in (A, B, F)},
               kappa_diagnostics={k: dict(min=float(np.min(v)), max=float(np.max(v)), mean=float(np.mean(v)))
                                  for k, v in diag.items()},
               validation_A_at_floor=dict(min=float(np.min(val_floor)), max=float(np.max(val_floor)), n=len(val_floor)),
               decisions_vs_A={f: {k: dict(min=float(np.min(v)), max=float(np.max(v)), mean=float(np.mean(v)))
                                   for k, v in d.items()} for f, d in dec.items()},
               tables_tuned={f: table(tuned[f]) for f in (A, B, F)},
               sensitivity_weeks_present={f: sorted(f"{s}|{sc}" for (s, sc) in sens[f]) for f in (B, F)},
               sensitivity_paired={f: paired(tuned[A], sens[f]) for f in (B, F)},
               retuned_paired={f: paired(tuned[A], tuned[f]) for f in (B, F)})
    json.dump(res, open(res_path, "w", encoding="utf-8", newline="\n"), indent=1)
    show(res)


def families(out, res_path):
    G_K = groups(out, "K")
    fams_e = ("QuantProv_q90", "Reactive", "PredHead+hyst")
    fams_b = ("PredHead", "QuantProv_q99", "Static", "Scheduled")
    Ge, Gb = groups(out, "CMPe"), groups(out, "CMPb")
    cov = coverage(out, {"K": ("PRISM",), "CMPe": fams_e, "CMPb": fams_b})
    rows = {"PRISM": {(s, sc): test_row(G_K, s, "PRISM", sc) for s in SEEDS for sc in SCEN}}
    for f in fams_e:
        rows[f] = {(s, sc): test_row(Ge, s, f, sc) for s in SEEDS for sc in SCEN}
    for f in fams_b:
        if all((s, f) in Gb for s in SEEDS):
            rows[f] = {(s, sc): test_row(Gb, s, f, sc) for s in SEEDS for sc in SCEN}
    W_od = load_weeks(out, "OD")
    if len(W_od) == len(SEEDS) * len(SCEN):
        rows["OnDemand"] = {(r["seed"], r["scenario"]): r for r in W_od.values()}
    sel = {f: {s: (Ge.get((s, f)) or Gb.get((s, f)) or G_K.get((s, f)) or {}).get("selected") for s in SEEDS}
           for f in rows if f != "OnDemand"}
    edges = {f: {s: (Ge.get((s, f)) or Gb.get((s, f)) or G_K.get((s, f)) or {}).get("edge_hit") for s in SEEDS}
             for f in rows if f != "OnDemand"}
    res = dict(label="EXPLORATORY, PRE-CALIBRATION, closed-loop event level, development traces 101-105, Linux",
               coverage=cov, families=list(rows), selected=sel, edge_hit=edges,
               tables={f: table(r) for f, r in rows.items()},
               paired_prism_minus={f: paired(rows[f], rows["PRISM"]) for f in rows if f != "PRISM"})
    json.dump(res, open(res_path, "w", encoding="utf-8", newline="\n"), indent=1)
    show(res)


def show(res):
    print(json.dumps({k: res[k] for k in res if k in ("coverage", "selected", "kappa_diagnostics", "validation_A_at_floor",
                                                       "decisions_vs_A", "families")}, indent=1, default=str))
    for key in ("tables_tuned", "tables"):
        for f, t in res.get(key, {}).items():
            print(f"{key} {f:18s} " + " | ".join(
                f"{sc}: {t[sc]['cost']['mean']:.0f}±{t[sc]['cost']['hw']:.0f} / {t[sc]['viol']['mean']:.2f}±{t[sc]['viol']['hw']:.2f} [{t[sc]['met']}]"
                for sc in SCEN))
    for key in ("sensitivity_paired", "retuned_paired", "paired_prism_minus"):
        for f, p in res.get(key, {}).items():
            print(f"{key} {f:18s} " + " | ".join(
                f"{sc}: {p[sc]['cost_pct']['mean']:+.2f}±{p[sc]['cost_pct']['hw']:.2f}% / {p[sc]['viol_pp']['mean']:+.2f}±{p[sc]['viol_pp']['hw']:.2f}pp"
                f" ({p[sc]['lower_cost']}/{p[sc]['fewer_viol']} of {len(p[sc]['traces'])}{', comparable' if p[sc]['comparable'] else ''})" for sc in SCEN))


if __name__ == "__main__":
    {"kappa": kappa, "families": families}[sys.argv[1]](sys.argv[2], sys.argv[3])
