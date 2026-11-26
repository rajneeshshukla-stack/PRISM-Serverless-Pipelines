#!/usr/bin/env python3
"""Event-level violation severity, persistence, modelling factors and extra capacity (R2.4; R7.2; R1.1 evidence).

PRE-CALIBRATION, POST HOC, OPEN LOOP: assumed constants (Table S1), current code, stored schedules. Nothing is
re-optimised: every run replays a provisioning and memory schedule stored by the submitted fast-simulator
experiment E1 (results/raw/E1/arrays_seed*.npz) through the event-level simulator (des.simulate_events), exactly
as the paper's event-level experiments E9 (Table X) and E12 (Table XI) did. Only the event-level code is current,
so the replays also measure what the corrections applied since submission (33d1000) change.

Group R24 (Reviewer 2, comment 4; seeds 101-105 x 4 scenarios = the 20 test weeks of Table XI):
  * the E12 (event-level validation) selections of PRISM, QuantProv-q90 and Reactive, replayed with their per-window
    attainment (severity and persistence: OBSERVED in the simulator); PredHead+S and Static were replayed for trace
    101 only before the design was trimmed and are not tabled;
  * PRISM's E12 schedule under two single-factor modelling counterfactuals of the event model (initialisation
    instantaneous; keep-alive unlimited), to test which modelling factors produce the misses;
  * PRISM's E12 schedule with every stage's provisioned capacity raised by a uniform margin m (P' = ceil(P (1 + m)),
    m in MARGINS), to ESTIMATE the extra provisioning that would have met the 2% target.
Group R72 (Reviewer 7, comment 2; seeds 101-103 x 4 scenarios = the 12 test weeks of Table X):
  * the E1 (fast-simulator validation) selection of PRISM, the schedule of Table X, under the event model, each
    counterfactual and both together, to decompose PRISM's fast-to-event gap in violating windows.

The counterfactual configurations change only init_mean_1024 and keepalive_min, which do not enter EventDraws, so
every variant replays identical requests (same arrivals and per-request draws).

Usage:  python event_severity_factors.py <code_root> <out_dir> [--workers=N] [--groups=R24,R72]
        python event_severity_factors.py <code_root> <out_dir> --analyse      (writes <out_dir>/summary.txt)
"""
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(".")
sys.path.insert(0, os.path.join(ROOT, "src"))

SEEDS = (101, 102, 103, 104, 105)
SEEDS_T10 = (101, 102, 103)
SCENARIOS = ("stationary", "growth", "bursty", "new_spike")
# Trimmed 22 Nov 2026 after the first 39 rows (trace 101): the laptop has 4 physical cores and the full design (472
# replays) would have taken about five hours. Rows already computed for the dropped items are kept in the files; the
# analysis tables only families and variants that have every week (it prints the counts).
FAM24 = ("PRISM", "QuantProv_q90", "Reactive")
FAM72 = ("PRISM",)
VARIANTS = ("event", "init_instant", "keepalive_unlimited", "init_instant+keepalive_unlimited")
VARIANTS24 = ("init_instant", "keepalive_unlimited")          # PRISM's E12 schedules, single factors only
MARGINS = (0.10, 0.20, 0.30, 0.50)
TARGET = 0.02
SCALARS = ("cost", "cost_pc", "cost_od", "cost_init", "record_attainment", "violating_window_rate", "slo_met",
           "late_records", "attain_in_violating", "worst_window_attainment", "longest_run", "mean_run", "n_runs",
           "share_late_in_violating", "cold_start_ratio", "overflow_share", "p99_latency", "n_requests")


def variant_cfg(cfg, variant):
    kw = {}
    if "init_instant" in variant:
        kw["init_mean_1024"] = 1e-9
    if "keepalive_unlimited" in variant:
        kw["keepalive_min"] = 10 ** 6
    return cfg.with_(**kw) if kw else cfg


def stored_labels():
    """E12 test-week selections (seed, family) -> label; E9 labels (seed, scenario, family) -> label."""
    e12 = {}
    for s in SEEDS:
        for line in open(os.path.join(ROOT, "results", "raw", "E12", f"E12_seed{s}.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r["week"] == "test" and r.get("selected"):
                e12[(s, r["family"])] = r["label"]
    e9 = {}
    for line in open(os.path.join(ROOT, "results", "raw", "E9", "rows.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        e9[(r["seed"], r["scenario"], r["policy"])] = r["label"]
    return e12, e9


def jobs_for(group, seed, sc, e12, e9):
    out = []
    if group == "R24":
        for fam in FAM24:
            out.append(dict(set="E12sel", family=fam, label=e12[(seed, fam)], variant="event", margin=0.0))
        lab = e12[(seed, "PRISM")]
        out += [dict(set="E12sel", family="PRISM", label=lab, variant=v, margin=0.0) for v in VARIANTS24]
        out += [dict(set="E12sel", family="PRISM", label=lab, variant="event", margin=m) for m in MARGINS]
    else:
        for fam in FAM72:
            out += [dict(set="E1sel", family=fam, label=e9[(seed, sc, fam)], variant=v, margin=0.0) for v in VARIANTS]
    return out


def key_of(j):
    return f"{j['set']}|{j['family']}|{j['label']}|{j['variant']}|{j['margin']:g}"


def run_task(group, seed, sc, out_dir):
    from prism_repro.config import PipelineConfig
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.workload import generate_trace
    cfg = PipelineConfig()
    e12, e9 = stored_labels()
    path = os.path.join(out_dir, f"rows_{group}_{seed}_{sc}.jsonl")
    done = set()
    if os.path.exists(path):
        done = {json.loads(l)["key"] for l in open(path, encoding="utf-8") if l.strip()}
    todo = [j for j in jobs_for(group, seed, sc, e12, e9) if key_of(j) not in done]
    if not todo:
        return group, seed, sc, 0
    arr = np.load(os.path.join(ROOT, "results", "raw", "E1", f"arrays_seed{seed}.npz"))
    tc = generate_trace(seed, sc)["counts"][21 * 1440:28 * 1440]
    draws = EventDraws(cfg, tc, seed, 3)          # test week, draw stream index 3, as E9 and E12
    cache = {}
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for j in todo:
            ck = (j["label"], j["variant"], j["margin"])
            if ck not in cache:
                k = f"E1|{seed}|{sc}|test|{j['label']}|"
                P, m = arr[k + "::P_epoch"].astype(float), arr[k + "::mem_epoch"]
                if j["margin"]:
                    P = np.ceil(P * (1.0 + j["margin"]) - 1e-9)
                t0 = time.perf_counter()
                res = simulate_events(variant_cfg(cfg, j["variant"]), draws, P, m, want_inflight=False,
                                      sample_seed=None)
                s = res["summary"]
                cache[ck] = dict({k2: (float(s[k2]) if isinstance(s.get(k2), (int, float, np.floating, np.integer))
                                       and not isinstance(s.get(k2), bool) else s.get(k2)) for k2 in SCALARS},
                                 window_attainment=[round(float(x), 6) for x in res["raw"]["window_attainment"]],
                                 mean_P=[round(float(x), 3) for x in P.mean(axis=0)],
                                 runtime_s=time.perf_counter() - t0)
            row = dict(key=key_of(j), group=group, seed=seed, scenario=sc, **j, **cache[ck])
            f.write(json.dumps(row) + "\n")
            f.flush()
            n += 1
            print(f"[{group}] {seed} {sc} {key_of(j)} viol {row['violating_window_rate']:.4f} "
                  f"cost {row['cost']:.0f} {row['runtime_s']:.0f}s", flush=True)
    return group, seed, sc, n


def environment():
    import numpy, scipy, sklearn
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "src", "experiments"],
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        head, dirty = "unknown", "unknown"
    return dict(platform=platform.platform(), python=platform.python_version(), numpy=numpy.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__, git_head=head,
                src_and_experiments_clean=(dirty == ""), cpu_count=os.cpu_count())


# --------------------------------------------------------------------------------------------- analysis
def load(out_dir):
    rows = []
    for fn in sorted(os.listdir(out_dir)):
        if fn.startswith("rows_") and fn.endswith(".jsonl"):
            rows += [json.loads(l) for l in open(os.path.join(out_dir, fn), encoding="utf-8") if l.strip()]
    return rows


def window_features(seed, sc):
    """Per 15-minute window of the test week: quarter of the hour, burst minutes, mean arrival rate, day."""
    from prism_repro.workload import WorkloadParams, _spike_profile, generate_trace
    p = WorkloadParams()
    tr = generate_trace(seed, sc)
    lo, hi = 21 * 1440, 28 * 1440
    t = np.arange(lo, hi)
    moh = t % 60
    spikes = _spike_profile(moh, p.spike_minutes)
    if sc == "new_spike":
        spikes = spikes + _spike_profile(moh, p.new_spike_minutes)
    excess = tr["rate"][lo:hi] / tr["baseline"][lo:hi] - 1.0 - spikes   # random-burst amplitude (additive, D14c)
    burst = excess > 1e-9
    W = (hi - lo) // 15
    q = (np.arange(W) % 4)                     # 0: :00-:14 (spikes at :00, :01), 1: :15-:29, 2: :30-:44, 3: :45-:59
    rate = tr["counts"][lo:hi].reshape(W, 15).mean(axis=1)
    return dict(quarter=q, burst=burst.reshape(W, 15).any(axis=1), rate=rate,
                day=np.arange(W) // 96, hour=(np.arange(W) % 96) // 4)


def runs(mask):
    out, c = [], 0
    for v in mask:
        if v:
            c += 1
        elif c:
            out.append(c)
            c = 0
    if c:
        out.append(c)
    return out


def analyse(out_dir):
    rows = load(out_dir)
    L = []
    P = L.append
    by = {r["key"] + f"|{r['seed']}|{r['scenario']}": r for r in rows}
    e12_stored = {}
    for s in SEEDS:
        for line in open(os.path.join(ROOT, "results", "raw", "E12", f"E12_seed{s}.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r["week"] == "test" and r.get("selected"):
                e12_stored[(s, r["scenario"], r["family"])] = r
    e9 = {(r["seed"], r["scenario"], r["policy"]): r
          for r in map(json.loads, open(os.path.join(ROOT, "results", "raw", "E9", "rows.jsonl"), encoding="utf-8"))}
    allow = int(math.floor(TARGET * 672 + 1e-9))     # 13 of 672 windows

    def get(st, fam, seed, sc, variant="event", margin=0.0):
        for r in rows:
            if (r["set"], r["family"], r["seed"], r["scenario"], r["variant"]) == (st, fam, seed, sc, variant) \
                    and abs(r["margin"] - margin) < 1e-12:
                return r
        return None

    P("EVENT-LEVEL SEVERITY, MODELLING FACTORS AND EXTRA CAPACITY (R2.4; R7.2; R1.1 evidence)")
    P("Pre-calibration, post hoc, open loop: stored E1 schedules replayed through the current event-level code.")
    P(f"Rows: {len(rows)}; target {TARGET:.0%} of 672 windows = at most {allow} violating windows per week.")
    P("")
    # ---------------------------------------------------------------- reproduction
    P("## 1. Reproduction of the stored event-level results (current des.py against the stored rows)")
    for st, fams, ref in (("E12sel", FAM24, "E12 (Table XI)"), ("E1sel", FAM72, "E9 (Table X)")):
        dc, dv, n, same, du = [], [], 0, 0, []
        for fam in fams:
            for s in (SEEDS if st == "E12sel" else SEEDS_T10):
                for sc in SCENARIOS:
                    r = get(st, fam, s, sc)
                    if r is None:
                        continue
                    if st == "E12sel":
                        o = e12_stored.get((s, sc, fam))
                        oc, ov = (o["cost"], o["violating_window_rate"]) if o else (None, None)
                    else:
                        o = e9.get((s, sc, fam))
                        oc, ov = (o["event_cost"], o["event_violating_window_rate"]) if o else (None, None)
                    if oc is None:
                        continue
                    n += 1
                    du.append(abs(r["cost"] - oc))
                    dc.append(100 * (r["cost"] / oc - 1))
                    dv.append(100 * (r["violating_window_rate"] - ov))
                    same += int(abs(r["cost"] - oc) < 1e-6 and abs(r["violating_window_rate"] - ov) < 1e-12)
        if n:
            P(f"  {ref}: {n} replays; identical in cost and violating windows: {same}; largest cost difference "
              f"USD {max(du):.4f} ({max(abs(x) for x in dc):.5f}%); violating-window change {min(dv):+.2f} to "
              f"{max(dv):+.2f} points (identical in {sum(abs(x) < 1e-9 for x in dv)} of {n})")
    P("")
    # ---------------------------------------------------------------- severity
    P("## 2. Severity and persistence of the E12 selections, 20 test weeks (OBSERVED in the simulator)")
    P("  family          weeks<=2%  viol%  late rec/wk  attain in viol  worst window  longest run  mean run  runs/wk")
    for fam in ("PRISM", "QuantProv_q90", "Reactive", "PredHead+hyst", "Static"):
        R = [get("E12sel", fam, s, sc) for s in SEEDS for sc in SCENARIOS]
        R = [r for r in R if r]
        if len(R) < len(SEEDS) * len(SCENARIOS):
            P(f"  {fam:15s} omitted: {len(R)} of {len(SEEDS) * len(SCENARIOS)} weeks replayed (trimmed design)")
            continue
        aiv = [r["attain_in_violating"] for r in R if r["attain_in_violating"] is not None
               and not (isinstance(r["attain_in_violating"], float) and math.isnan(r["attain_in_violating"]))]
        P(f"  {fam:15s} {sum(r['violating_window_rate'] <= TARGET + 1e-12 for r in R):3d}/{len(R):<3d}   "
          f"{100*np.mean([r['violating_window_rate'] for r in R]):5.2f}  {np.mean([r['late_records'] for r in R]):10,.0f}"
          f"   {100*np.mean(aiv) if aiv else float('nan'):11.2f}%   {100*np.mean([r['worst_window_attainment'] for r in R]):9.2f}%"
          f"   {np.mean([r['longest_run'] for r in R]):8.2f}   {np.mean([r['mean_run'] for r in R]):6.2f}"
          f"   {np.mean([r['n_runs'] for r in R]):6.1f}")
    P("")
    P("  PRISM, every test week (E12 selection): violating windows of 672 (allowance 13), worst window, longest run")
    miss = []
    for s in SEEDS:
        for sc in SCENARIOS:
            r = get("E12sel", "PRISM", s, sc)
            if not r:
                continue
            att = np.array(r["window_attainment"])
            v = att < 0.99 - 1e-12
            nv = int(v.sum())
            if nv > allow:
                miss.append((s, sc, r))
            depth = 100 * (0.99 - att[v]) if nv else np.array([0.0])
            nb = int((v & window_features(s, sc)["burst"]).sum())
            P(f"    {s} {sc:10s} {r['label']:12s} {nv:3d} ({nv - allow:+3d})  worst {100*att.min():6.2f}%  "
              f"longest run {max(runs(v)) if nv else 0}  median shortfall {np.median(depth):.2f} points  "
              f"in burst windows {nb}/{nv}  {'MISS' if nv > allow else 'met'}")
    P(f"  PRISM misses: {len(miss)} of 20 weeks")
    P("")
    # ---------------------------------------------------------------- workload conditions
    P("## 3. Workload conditions of PRISM's violating windows (association, OBSERVED; E12 selections, 20 weeks)")
    tot_w, tot_v = Counter(), Counter()
    burst_w, burst_v, nb_w, nb_v = 0, 0, 0, 0
    dec_w, dec_v = Counter(), Counter()
    per_sc = defaultdict(lambda: [0, 0])
    for s in SEEDS:
        for sc in SCENARIOS:
            r = get("E12sel", "PRISM", s, sc)
            if not r:
                continue
            v = np.array(r["window_attainment"]) < 0.99 - 1e-12
            wf = window_features(s, sc)
            for qq in range(4):
                tot_w[qq] += int((wf["quarter"] == qq).sum())
                tot_v[qq] += int((v & (wf["quarter"] == qq)).sum())
            burst_w += int(wf["burst"].sum()); burst_v += int((v & wf["burst"]).sum())
            nb_w += int((~wf["burst"]).sum()); nb_v += int((v & ~wf["burst"]).sum())
            dec = np.minimum((np.argsort(np.argsort(wf["rate"])) * 10) // len(wf["rate"]), 9)
            for d in range(10):
                dec_w[d] += int((dec == d).sum()); dec_v[d] += int((v & (dec == d)).sum())
            per_sc[sc][0] += int(v.sum()); per_sc[sc][1] += 672
    names = {0: ":00-:14 (scheduled spikes at :00-:01, 2x+2x)", 1: ":15-:29 (new-spike slot :15-:16; empty otherwise)",
             2: ":30-:44 (scheduled spike at :30, 1x)", 3: ":45-:59 (no scheduled spike)"}
    for qq in range(4):
        P(f"  window {names[qq]:52s} {tot_v[qq]:4d} of {tot_w[qq]:5d} violating ({100*tot_v[qq]/max(tot_w[qq],1):.2f}%)")
    P(f"  windows with a random burst:    {burst_v:4d} of {burst_w:5d} violating ({100*burst_v/max(burst_w,1):.2f}%)")
    P(f"  windows without a random burst: {nb_v:4d} of {nb_w:5d} violating ({100*nb_v/max(nb_w,1):.2f}%)")
    P("  by arrival-rate decile of the week (0 = quietest): " +
      ", ".join(f"{d}: {100*dec_v[d]/max(dec_w[d],1):.1f}%" for d in range(10)))
    P("  by scenario: " + ", ".join(f"{k} {100*a/b:.2f}%" for k, (a, b) in per_sc.items()))
    P("")
    # ---------------------------------------------------------------- modelling factors
    P("## 4. Modelling factors (counterfactual replays of PRISM's E12 schedules; CAUSAL within the simulator)")
    for vv in ("event",) + VARIANTS24:
        R = [get("E12sel", "PRISM", s, sc, vv) for s in SEEDS for sc in SCENARIOS]
        R = [r for r in R if r]
        if len(R) == len(SEEDS) * len(SCENARIOS):
            P(f"  {vv:34s} weeks<=2% {sum(r['violating_window_rate'] <= TARGET + 1e-12 for r in R):2d}/{len(R)}  "
              f"viol {100*np.mean([r['violating_window_rate'] for r in R]):5.2f}%  cost {np.mean([r['cost'] for r in R]):7,.0f}"
              f"  cold-start ratio {np.mean([r['cold_start_ratio'] for r in R]):.5f}")
    P("")
    # ---------------------------------------------------------------- extra capacity
    P("## 5. Extra provisioning (ESTIMATED by counterfactual replay: uniform margin on every stage's capacity)")
    for s in SEEDS:
        for sc in SCENARIOS:
            base = get("E12sel", "PRISM", s, sc)
            if not base:
                continue
            need = None
            for m in (0.0,) + MARGINS:
                r = base if m == 0 else get("E12sel", "PRISM", s, sc, "event", m)
                if r and r["violating_window_rate"] <= TARGET + 1e-12:
                    need = (m, r)
                    break
            if base["violating_window_rate"] > TARGET + 1e-12:
                P(f"    {s} {sc:10s} miss at {100*base['violating_window_rate']:.2f}%: smallest margin meeting 2% = "
                  + (f"{100*need[0]:.0f}% (cost +{100*(need[1]['cost']/base['cost']-1):.1f}%, viol "
                     f"{100*need[1]['violating_window_rate']:.2f}%)" if need else f"none up to {100*MARGINS[-1]:.0f}%"))
    for m in MARGINS:
        R = [get("E12sel", "PRISM", s, sc, "event", m) for s in SEEDS for sc in SCENARIOS]
        B = [get("E12sel", "PRISM", s, sc) for s in SEEDS for sc in SCENARIOS]
        ok = [(r, b) for r, b in zip(R, B) if r and b]
        if ok:
            P(f"  uniform margin {100*m:3.0f}%: weeks<=2% {sum(r['violating_window_rate'] <= TARGET + 1e-12 for r, _ in ok):2d}/"
              f"{len(ok)}, viol {100*np.mean([r['violating_window_rate'] for r, _ in ok]):5.2f}%, cost "
              f"{100*np.mean([r['cost']/b['cost'] - 1 for r, b in ok]):+5.1f}% (mean over weeks)")
    P("")
    # ---------------------------------------------------------------- R7.2 decomposition
    P("## 6. Fast-to-event gap on the Table X schedules (E1 selections, seeds 101-103 x 4 scenarios = 12 weeks)")
    P("  fast = stored submitted fast-simulator result (E9 rows); the other columns are current event-level replays.")
    P("  family     fast   event   init-instant  keep-alive-unlim  both    gap closed by: init  keep-alive  both")
    for fam in FAM72:
        vals = {vv: [] for vv in VARIANTS}
        fast = []
        for s in SEEDS_T10:
            for sc in SCENARIOS:
                rr = {vv: get("E1sel", fam, s, sc, vv) for vv in VARIANTS}
                o = e9.get((s, sc, fam))
                if not all(rr.values()) or o is None:
                    continue
                fast.append(o["fast_violating_window_rate"])
                for vv in VARIANTS:
                    vals[vv].append(rr[vv]["violating_window_rate"])
        if not fast:
            continue
        F = 100 * np.mean(fast)
        E, I, K, B = (100 * np.mean(vals[v]) for v in VARIANTS)
        g = E - F
        P(f"  {fam:9s} {F:5.2f}  {E:5.2f}   {I:9.2f}   {K:12.2f}    {B:6.2f}     "
          f"{100*(E-I)/g if g else float('nan'):5.0f}%  {100*(E-K)/g if g else float('nan'):8.0f}%  "
          f"{100*(E-B)/g if g else float('nan'):5.0f}%   (n={len(fast)})")
    P("")
    P("Labels: OBSERVED = counted in the simulator's output; ESTIMATED = counterfactual replay, not a policy the")
    P("controller could have run without hindsight; all values pre-calibration (assumed constants) and open loop.")
    txt = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)


def main():
    out_dir = os.path.abspath(sys.argv[2])
    args = sys.argv[3:]
    os.makedirs(out_dir, exist_ok=True)
    if "--analyse" in args:
        analyse(out_dir)
        return
    workers = int(next((a.split("=")[1] for a in args if a.startswith("--workers=")), "4"))
    groups = next((a.split("=")[1] for a in args if a.startswith("--groups=")), "R24,R72").split(",")
    env = environment()
    with open(os.path.join(out_dir, "environment.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(env, f, indent=1)
    tasks = [(g, s, sc) for g in groups for s in (SEEDS if g == "R24" else SEEDS_T10) for sc in SCENARIOS]
    print(f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} tasks={len(tasks)} workers={workers} "
          f"env={json.dumps(env)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_task, g, s, sc, out_dir) for g, s, sc in tasks]
        for fu in as_completed(futs):
            g, s, sc, n = fu.result()
            print(f"task done {g} {s} {sc}: {n} new rows", flush=True)
    print(f"end {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)


if __name__ == "__main__":
    main()
