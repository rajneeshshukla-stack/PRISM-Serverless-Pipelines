#!/usr/bin/env python3
"""Grid studies in the fast simulator: refined near-target evaluation (R2.19) and widened grids (R4.7, R5.M4(c)).

PRE-CALIBRATION, POST HOC (test-week analyses) / EXPLORATORY: fast simulator, assumed constants (Table S1), current
code, one machine. Every family is re-run on the CURRENT code, because the stored submitted rows (results/raw) are
not reproduced by it (exact attainment 1ab053c, corrections 33d1000, platform; NA-1, docs/revision/table6_versions);
mixing stored and new points would mix code versions. Seeds 101-105 are the paper's five development traces; the
confirmatory seeds 106-130 are not used.

--suite=posthoc  (seeds 101-105, the four test weeks of each)
    1. Every family on experiment.GRIDS_WIDE, which contains the paper's GRIDS, so both the paper's grid and the
       widened grid are evaluated on the same code (post hoc test-week edge audit, R5.M4(c)).
    2. R2.19: for PRISM, QuantProv-q90, PredHead+S, Static and Reactive, the paper's matched-compliance method
       (scripts/revision/matched_compliance_pertrace.py: per trace, mean cost and violating-window rate over the four
       test weeks per setting, lower envelope, linear interpolation at 1.0 / 1.5 / 2.0 %) is applied to the paper's
       GRIDS points; each envelope segment that brackets a target is then evaluated at REFINE interior settings, and
       the interpolated cost is compared with what evaluated configurations achieve.
--suite=real     (the five Huawei arrival traces of R1, seeds 201-205)
    The R1 protocol (experiments/run_real_traces.py: train days 1-14, validate on 15-21 by the common rule, test on
    22-28) with every family on GRIDS_WIDE; selections with the paper's GRIDS and with GRIDS_WIDE, edge audit of both
    (R4.7(b)).

Rows are appended as each run finishes (resumable). Usage:
    python fast_grid_studies.py <code_root> <out_dir> --suite=posthoc|real [--workers=N]
    python fast_grid_studies.py <code_root> <out_dir> --suite=posthoc|real --analyse
"""
import json
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(".")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "revision"))

SYN_SEEDS = (101, 102, 103, 104, 105)
SCENARIOS = ("stationary", "growth", "bursty", "new_spike")
REAL_FNS = {"150": 201, "72": 202, "60": 203, "183": 204, "42": 205}
TARGETS = (0.010, 0.015, 0.020)
R219_FAMS = ("PRISM", "QuantProv_q90", "PredHead+hyst", "Static", "Reactive")
REFINE = 5
FAMILIES = ("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90",
            "QuantProv_q99", "PRISM")


def grids():
    from prism_repro.experiment import GRIDS, GRIDS_WIDE
    base = {"PredHead+hyst": "PredHead", "QuantProv_q90": "QuantProv", "QuantProv_q99": "QuantProv"}
    g = {f: GRIDS[base.get(f, f)] for f in FAMILIES if f != "OnDemand"}
    w = {f: GRIDS_WIDE[base.get(f, f)] for f in FAMILIES if f != "OnDemand"}
    return g, w


def spec_of(fam, p):
    if fam == "OnDemand":
        return dict(family="OnDemand")
    if fam == "PredHead+hyst":
        return dict(family="PredHead", param=p, hyst=True)
    if fam.startswith("QuantProv"):
        return dict(family="QuantProv", tau_idx=2 if fam.endswith("q90") else 3, param=p)
    return dict(family=fam, param=p)


def envelope(points):
    """points: list of (param, viol, cost); lower-left envelope as in matched_compliance_pertrace.py."""
    keep, best = [], np.inf
    for p, v, c in sorted(points, key=lambda x: (x[1], x[2])):
        if c < best - 1e-9:
            keep.append((p, v, c))
            best = c
    return keep


def interp(keep, t):
    if not keep or t < keep[0][1] - 1e-12:
        return np.nan, None
    for a, b in zip(keep, keep[1:]):
        if a[1] <= t <= b[1]:
            c = a[2] + (b[2] - a[2]) * (t - a[1]) / (b[1] - a[1]) if b[1] > a[1] else a[2]
            return c, (a, b)
    return np.nan, None


def mean_points(rows, fam, params=None):
    acc = defaultdict(list)
    for r in rows:
        if r["family"] == fam and r.get("param") is not None and (params is None or r["param"] in params):
            acc[r["param"]].append((r["violating_window_rate"], r["cost"]))
    return [(p, float(np.mean([x[0] for x in v])), float(np.mean([x[1] for x in v])))
            for p, v in acc.items() if len(v) == len(SCENARIOS)]


def row_of(bundle, sc, week, fam, p, stage, run_policy):
    t0 = time.perf_counter()
    res = run_policy(bundle, sc, week, spec_of(fam, p))
    s = res["summary"]
    return dict(seed=bundle.seed, scenario=sc, week=week, family=fam, param=p, stage=stage,
                spec=spec_of(fam, p), cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"]),
                record_attainment=float(s["record_attainment"]), slo_met=bool(s["slo_met"]),
                runtime_s=time.perf_counter() - t0)


def task_posthoc(seed, out_dir):
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, run_policy
    g, w = grids()
    path = os.path.join(out_dir, f"rows_posthoc_{seed}.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []
    done = {(r["scenario"], r["family"], r["param"]) for r in rows}
    b = TraceBundle(seed, PipelineConfig())
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        jobs = [(sc, "OnDemand", None) for sc in SCENARIOS]
        jobs += [(sc, fam, p) for sc in SCENARIOS for fam in FAMILIES if fam != "OnDemand" for p in w[fam]]
        for sc, fam, p in jobs:
            if (sc, fam, p) in done:
                continue
            r = row_of(b, sc, "test", fam, p, "grid_wide", run_policy)
            f.write(json.dumps(r) + "\n"); f.flush(); rows.append(r); done.add((sc, fam, p)); n += 1
        # R2.19 refinement inside each paper-grid envelope segment that brackets a target
        for fam in R219_FAMS:
            keep = envelope(mean_points(rows, fam, set(g[fam])))
            segs = set()
            for t in TARGETS:
                _, seg = interp(keep, t)
                if seg:
                    segs.add((seg[0][0], seg[1][0]))
            for p0, p1 in sorted(segs):
                for k in range(1, REFINE + 1):
                    p = p0 + (p1 - p0) * k / (REFINE + 1)
                    p = round(p, 3 if fam == "Static" else 4)
                    if p in (p0, p1):
                        continue
                    for sc in SCENARIOS:
                        if (sc, fam, p) in done:
                            continue
                        r = row_of(b, sc, "test", fam, p, "refined", run_policy)
                        f.write(json.dumps(r) + "\n"); f.flush(); rows.append(r); done.add((sc, fam, p)); n += 1
    return f"posthoc {seed}", n


def task_real(fn, out_dir):
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import run_policy
    from run_real_traces import RealTraceBundle
    g, w = grids()
    seed = REAL_FNS[fn]
    path = os.path.join(out_dir, f"rows_real_{seed}.jsonl")
    done = set()
    if os.path.exists(path):
        done = {(r["week"], r["family"], r["param"]) for r in map(json.loads, open(path, encoding="utf-8"))}
    b = RealTraceBundle(fn, PipelineConfig())
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for wk in ("val", "test"):
            jobs = [("OnDemand", None)] + [(fam, p) for fam in FAMILIES if fam != "OnDemand" for p in w[fam]]
            for fam, p in jobs:
                if (wk, fam, p) in done:
                    continue
                r = row_of(b, "real", wk, fam, p, "grid_wide", run_policy)
                r.update(trace=f"huawei_fn{fn}", synthetic=False)
                f.write(json.dumps(r) + "\n"); f.flush(); done.add((wk, fam, p)); n += 1
    return f"real {fn}", n


def environment():
    import numpy, scipy, sklearn
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "src", "experiments"],
                           capture_output=True, text=True).stdout.strip()
    return dict(platform=platform.platform(), python=platform.python_version(), numpy=numpy.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__, git_head=head,
                src_and_experiments_clean=(dirty == ""), cpu_count=os.cpu_count())


# ------------------------------------------------------------------------------------------------ analysis
def load(out_dir, suite):
    rows = []
    for fn in sorted(os.listdir(out_dir)):
        if fn.startswith(f"rows_{suite}_") and fn.endswith(".jsonl"):
            rows += [json.loads(l) for l in open(os.path.join(out_dir, fn), encoding="utf-8") if l.strip()]
    return rows


def select(rows, threshold=0.02):
    from prism_repro.experiment import select_by_rule
    return select_by_rule(rows, threshold)


def edge_side(v, grid):
    return "low" if v == min(grid) else "high" if v == max(grid) else ""


def analyse_posthoc(out_dir):
    from scipy import stats
    g, w = grids()
    rows = load(out_dir, "posthoc")
    L = []
    P = L.append
    P("FAST-SIMULATOR GRID STUDIES ON THE SYNTHETIC TEST WEEKS (current code; pre-calibration; POST HOC)")
    P(f"Rows: {len(rows)} (seeds {sorted({r['seed'] for r in rows})}); stages: "
      f"{dict((s, sum(r['stage'] == s for r in rows)) for s in ('grid_wide', 'refined'))}")
    P("")
    # ------------------------------------------------------------ R2.19
    P("## R2.19: interpolated matched-compliance costs against evaluated configurations")
    P("  Per trace: mean over the four test weeks per setting; 'interp' = the paper's method on the paper's grid;")
    P("  'refined interp' = the same method after adding the evaluated interior settings; 'achievable' = the cheapest")
    P("  evaluated setting (paper grid + interior) whose four-week mean violating-window rate is at or below the target.")
    res = {}
    for t in TARGETS:
        P(f"  target {100*t:.1f}%")
        for fam in R219_FAMS:
            out = []
            for s in SYN_SEEDS:
                R = [r for r in rows if r["seed"] == s]
                base = mean_points(R, fam, set(g[fam]))
                allp = mean_points([r for r in R if r["param"] is not None and
                                    (r["param"] in set(g[fam]) or r["stage"] == "refined")], fam)
                ci, seg = interp(envelope(base), t)
                cr, _ = interp(envelope(allp), t)
                ok = [c for p, v, c in allp if v <= t + 1e-12]
                ca = min(ok) if ok else np.nan
                inner = [(p, v, c) for p, v, c in allp if seg and min(seg[0][0], seg[1][0]) < p < max(seg[0][0], seg[1][0])]
                out.append(dict(seed=s, interp=ci, refined=cr, achievable=ca, seg=seg, n_inner=len(inner)))
            res[(t, fam)] = out
            d_ref = [100 * (o["refined"] / o["interp"] - 1) for o in out if np.isfinite(o["interp"]) and np.isfinite(o["refined"])]
            d_ach = [100 * (o["achievable"] / o["interp"] - 1) for o in out if np.isfinite(o["interp"]) and np.isfinite(o["achievable"])]
            segtxt = "; ".join(f"{o['seed']}: " + (f"[{o['seg'][0][0]:g}, {o['seg'][1][0]:g}]" if o["seg"] else "n.r.")
                               for o in out)
            P(f"    {fam:14s} refined-interp vs interp: " + (f"{min(d_ref):+.2f} to {max(d_ref):+.2f}% (n={len(d_ref)})" if d_ref else "n/a")
              + "; achievable vs interp: " + (f"{min(d_ach):+.2f} to {max(d_ach):+.2f}% (n={len(d_ach)})" if d_ach else "n/a")
              + f"; bracketing settings {segtxt}")
    P("")
    P("  Paired PRISM minus comparator at matched compliance (per trace, % of comparator cost; mean +/- 95% t half-width):")
    for t in TARGETS:
        for fam in R219_FAMS[1:]:
            line = []
            for k in ("interp", "refined", "achievable"):
                p = np.array([o[k] for o in res[(t, "PRISM")]], float)
                q = np.array([o[k] for o in res[(t, fam)]], float)
                ok = np.isfinite(p) & np.isfinite(q)
                d = 100 * (p[ok] / q[ok] - 1)
                hw = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
                line.append(f"{k} {d.mean():+5.1f} +/- {hw:4.1f} (n={ok.sum()})" if len(d) else f"{k} n/a")
            P(f"    {100*t:.1f}%  vs {fam:14s} " + " | ".join(line))
    P("")
    # ------------------------------------------------------------ post hoc edges
    P("## R5.M4(c): post hoc test-week selections (test-week knowledge), paper grid against widened grid")
    from grid_edge_audit import family_key
    n_g = n_w = n_tot = 0
    lines = []
    for s in SYN_SEEDS:
        for sc in SCENARIOS:
            for fam in FAMILIES[1:]:
                R = [r for r in rows if r["seed"] == s and r["scenario"] == sc and r["family"] == fam
                     and r["stage"] == "grid_wide"]
                Rg = [r for r in R if r["param"] in set(g[fam])]
                if len(Rg) < 2:
                    continue
                n_tot += 1
                sg, sw = select(Rg), select(R)
                eg, ew = edge_side(sg["param"], g[fam]), edge_side(sw["param"], w[fam])
                n_g += bool(eg); n_w += bool(ew)
                if eg or ew:
                    lines.append(f"    {s} {sc:10s} {fam:14s} paper grid: {sg['param']:g} {eg or 'interior'}"
                                 f"{'' if sg['violating_window_rate'] <= 0.02 + 1e-12 else ' (none met 2%)'}"
                                 f" ({100*sg['violating_window_rate']:.2f}%, {sg['cost']:,.0f}) -> widened: {sw['param']:g} "
                                 f"{ew or 'interior'}{'' if sw['violating_window_rate'] <= 0.02 + 1e-12 else ' (none met 2%)'}"
                                 f" ({100*sw['violating_window_rate']:.2f}%, {sw['cost']:,.0f})")
    P(f"  edge selections: paper grid {n_g} of {n_tot}; widened grid {n_w} of {n_tot}")
    L.extend(lines)
    P("")
    txt = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "summary_posthoc.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)


def analyse_real(out_dir):
    g, w = grids()
    rows = load(out_dir, "real")
    stored = [json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", "R1", "rows.jsonl"), encoding="utf-8")]
    from grid_edge_audit import family_key
    st_sel = {}
    for s in sorted(REAL_FNS.values()):
        for fam in FAMILIES:
            R = [r for r in stored if r.get("seed") == s and r.get("week") == "val" and r.get("spec")
                 and family_key(r["spec"]) == fam and not r.get("tag")]
            if R:
                st_sel[(s, fam)] = select(R)
    L = []
    P = L.append
    P("REAL-TRACE REPLAY (R1 protocol) WITH THE PAPER'S AND THE WIDENED GRIDS (current code; post hoc study of")
    P("five Huawei arrival traces; fast simulator; pre-calibration)")
    P(f"Rows: {len(rows)}")
    P("")
    P("  trace  family          stored R1 sel (submitted code)  paper grid sel (current)        widened grid sel (current)")
    n_st = n_g = n_w = n = 0
    test_rows = {}
    for s in sorted(REAL_FNS.values()):
        for fam in FAMILIES:
            V = [r for r in rows if r["seed"] == s and r["week"] == "val" and r["family"] == fam]
            T = {r["param"]: r for r in rows if r["seed"] == s and r["week"] == "test" and r["family"] == fam}
            if fam == "OnDemand":
                if V:
                    t = T.get(None)
                    test_rows[(s, fam, "g")] = test_rows[(s, fam, "w")] = t
                continue
            Vg = [r for r in V if r["param"] in set(g[fam])]
            if len(Vg) < 2:
                continue
            n += 1
            sg, sw = select(Vg), select(V)
            eg, ew = edge_side(sg["param"], g[fam]), edge_side(sw["param"], w[fam])
            o = st_sel.get((s, fam))
            eo = edge_side(float(o["spec"]["param"]), g[fam]) if o else ""
            n_st += bool(eo); n_g += bool(eg); n_w += bool(ew)
            test_rows[(s, fam, "g")] = T.get(sg["param"])
            test_rows[(s, fam, "w")] = T.get(sw["param"])
            fmt = lambda r, e: (f"{r['param'] if 'param' in r else r['spec']['param']:g} {e or 'int.'}"
                                f" val {100*r['violating_window_rate']:.2f}%" + ("" if r["violating_window_rate"] <= 0.02 + 1e-12 else "*"))
            P(f"  {s}    {fam:14s}  {fmt(o, eo) if o else 'n/a':30s}  {fmt(sg, eg):30s}  {fmt(sw, ew)}")
    P("")
    P(f"  edge selections: stored R1 {n_st} of {n}; current code, paper grid {n_g} of {n}; widened grid {n_w} of {n}")
    P("  (* = no setting met the 2% validation threshold, so the least violating was taken)")
    P("")
    P("  Test week (days 22-28) of the validation-selected settings: cost USD / violating windows %, and whether the")
    P("  2% target is met; paper grid -> widened grid")
    for fam in FAMILIES:
        cells = []
        for s in sorted(REAL_FNS.values()):
            a, b = test_rows.get((s, fam, "g")), test_rows.get((s, fam, "w"))
            if a and b:
                cells.append(f"{s}: {a['cost']:,.0f}/{100*a['violating_window_rate']:.2f}{'+' if a['violating_window_rate'] <= 0.02 + 1e-12 else '-'}"
                             f" -> {b['cost']:,.0f}/{100*b['violating_window_rate']:.2f}{'+' if b['violating_window_rate'] <= 0.02 + 1e-12 else '-'}")
        if cells:
            P(f"    {fam:14s} " + "; ".join(cells))
    P("  (+ meets the 2% target on the test week, - misses)")
    for k, name in (("g", "paper grid"), ("w", "widened grid")):
        met = {fam: sum(1 for s in REAL_FNS.values() if test_rows.get((s, fam, k)) and
                        test_rows[(s, fam, k)]["violating_window_rate"] <= 0.02 + 1e-12) for fam in FAMILIES}
        P(f"  test weeks meeting the target, {name}: " + ", ".join(f"{f} {m}/5" for f, m in met.items()))
    P("")
    txt = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "summary_real.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)


def main():
    out_dir = os.path.abspath(sys.argv[2])
    args = sys.argv[3:]
    suite = next((a.split("=")[1] for a in args if a.startswith("--suite=")), None)
    if suite not in ("posthoc", "real"):
        sys.exit("--suite=posthoc|real required")
    os.makedirs(out_dir, exist_ok=True)
    if "--analyse" in args:
        (analyse_posthoc if suite == "posthoc" else analyse_real)(out_dir)
        return
    workers = int(next((a.split("=")[1] for a in args if a.startswith("--workers=")), "3"))
    env = environment()
    with open(os.path.join(out_dir, f"environment_{suite}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(env, f, indent=1)
    print(f"start {suite} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} workers={workers} env={json.dumps(env)}",
          flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        if suite == "posthoc":
            futs = [ex.submit(task_posthoc, s, out_dir) for s in SYN_SEEDS]
        else:
            futs = [ex.submit(task_real, fn, out_dir) for fn in REAL_FNS]
        for fu in as_completed(futs):
            name, n = fu.result()
            print(f"task done {name}: {n} new rows {time.strftime('%H:%M:%SZ', time.gmtime())}", flush=True)
    print(f"end {suite} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)


if __name__ == "__main__":
    main()
