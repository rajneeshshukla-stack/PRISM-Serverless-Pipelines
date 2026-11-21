#!/usr/bin/env python3
"""R1.2: how does initialisation time change with memory? EXPLORATORY, POST HOC, EXTERNAL HISTORICAL DATA.

Not a PRISM measurement. Two independent sources, kept apart:

A. SeBS artifact (AWS Lambda, us-east-1, invocation timestamps November 2020; DOI 10.5281/zenodo.5209001).
   Controlled: the same function deployed at several memory sizes, cold and warm batches.
   Primary measure: Lambda's reported initialisation duration, provider_times.initialization (us).
   Cross-check: cold-minus-warm client time, median(times.client | cold) - median(times.client | warm).
   Uncertainty: bootstrap over cold batches (about 50 concurrent invocations each, split at client-time gaps
   > 5 s), resampled within each memory size; with about 5 batches per size the intervals are approximate.
   Eq. (3) as implemented (prism_repro.latency.init_factor, init_scaling="eq3"): f(m) = 0.7 + 0.3 * 1024 / m.

B. Huawei Public Cloud 2025 cold starts (arXiv 2410.06145), five regions, 31 days. Observational production data
   on another platform. totalCost_cold_start equals podAllocationCost + deployCodeCost + deployDependencyCost +
   schedulingCost (checked here). Memory and CPU limit come from the pool name in podID; both are user choices,
   so they are confounded with function and runtime. Reported per region: event and function-weighted medians per
   memory pool; within-function comparisons (the same funcName/userID seen in pools of different memory); and,
   for Region 2 only (the only region with runtimes), the within-function comparison by runtime.

Inputs are verified against additional data/MANIFEST.tsv before use. Raw data is read in place, never copied.
Usage: python -I r12_init_vs_memory.py "<repo>/additional data" <out_dir>
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import platform
import re
import sys
import time

import numpy as np
import pandas as pd
import scipy
from scipy import stats

DATA, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(20261121)
B_SEBS, B_HW, MIN_EVENTS = 2000, 1000, 20
PRISM_SIZES = (512, 1024, 2048, 3008)
BENCH = {"120": "uploader", "210_node": "thumbnailer (Node.js)", "210_python": "thumbnailer (Python)",
         "311": "compression", "411": "image recognition (large package)", "503": "graph BFS"}
LOG = open(os.path.join(OUT, "run.log"), "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n"); LOG.flush()


def eq3(m):
    return 0.7 + 0.3 * 1024.0 / np.asarray(m, float)


def slope(mem, med):
    """OLS slope of log(median) on log(memory): the elasticity of the median with memory."""
    x, y = np.log(np.asarray(mem, float)), np.log(np.asarray(med, float))
    return float(np.polyfit(x, y, 1)[0])


def ci(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    return (float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))) if len(a) else (np.nan, np.nan)


def direction(lo, hi):
    return "decreasing" if hi < 0 else "increasing" if lo > 0 else "inconclusive"


# ------------------------------------------------------------------------------------------------ input check
t0 = time.time()
man = {r["dest_path"]: r for r in csv.DictReader(open(os.path.join(DATA, "MANIFEST.tsv"), encoding="utf-8"),
                                                  delimiter="\t")}
used = [p for p in man if p.startswith("sebs_aws_2020/data/performance/aws_perf_cost/") and p.endswith(".json")]
used += [f"huawei_public_2025/cold_starts/R{i}.zip" for i in range(1, 6)] + ["huawei_public_2025/df_funcID_runtime_triggerType.csv"]
for p in used:
    h = hashlib.sha256()
    with open(os.path.join(DATA, p), "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    assert h.hexdigest() == man[p]["sha256"], f"input differs from MANIFEST: {p}"
log(f"inputs verified against MANIFEST.tsv: {len(used)} files")

# ------------------------------------------------------------------------------------------------ A. SeBS
def batches(recs):
    """Split invocations into batches at client-time gaps > 5 s (SeBS fires each batch concurrently)."""
    t = np.array([dt.datetime.fromisoformat(r["times"]["client_begin"]).timestamp() for r in recs])
    o = np.argsort(t)
    ids = np.empty(len(t), int); ids[o] = np.r_[0, np.cumsum(np.diff(t[o]) > 5.0)]
    return ids, float(t.min())


S, rows_a, trend_a, missing_a = {}, [], [], []
for f in sorted(glob.glob(os.path.join(DATA, "sebs_aws_2020/data/performance/aws_perf_cost/*/perf-cost/*-processed.json"))):
    b, kind, mem = re.search(r"aws_perf_cost[\\/]([^\\/]+)[\\/]perf-cost[\\/](cold|warm)_results_(\d+)", f).groups()
    j = json.load(open(f, encoding="utf-8"))
    recs = [r for inv in j["_invocations"].values() for r in inv.values()]
    runtime = j.get("config", {}).get("experiments", {}).get("runtime", {})
    keep = [r for r in recs if bool((r.get("stats") or {}).get("cold_start")) == (kind == "cold")
            and not (r.get("stats") or {}).get("failure")]
    # 47 cold invocations are billed at another memory size than their file's label (mostly the previous size of
    # the sweep): excluded. Records with no billing at all (the same 299 that lack an init duration) are kept for
    # the client-time cross-check; they have no init value, so they never enter the primary measure.
    other_mem = sum((r.get("billing") or {}).get("_memory") not in (None, int(mem)) for r in keep)
    keep = [r for r in keep if (r.get("billing") or {}).get("_memory") in (None, int(mem))]
    bid, start = batches(keep)
    S[(b, kind, int(mem))] = dict(other_mem=other_mem,
        init=np.array([((r.get("provider_times") or {}).get("initialization") or 0) / 1e6 for r in keep]),
        client=np.array([r["times"]["client"] / 1e6 for r in keep]), batch=bid, start=start,
        n_raw=len(recs), n_excluded=len(recs) - len(keep),     # cold flag mismatch, failure, or other memory
        runtime=f"{runtime.get('language', '?')} {runtime.get('version', '')}".strip(),
        unexpected=(j.get("statistics") or {}).get("unexpected_warms_count" if kind == "cold" else "unexpected_colds_count"))


def boot_median(x, bid, n_b):
    """Bootstrap medians of x (NaN = missing) resampling whole batches."""
    groups = [x[bid == g] for g in np.unique(bid)]
    out = np.empty(n_b)
    for i in range(n_b):
        pick = RNG.integers(0, len(groups), len(groups))
        v = np.concatenate([groups[k] for k in pick]); v = v[np.isfinite(v)]
        out[i] = np.median(v) if len(v) else np.nan
    return out


for b in BENCH:
    mems = sorted(m for (bb, k, m) in S if bb == b and k == "cold" and (bb, "warm", m) in S)
    boots_i, boots_c, med_i, med_c = {}, {}, {}, {}
    for m in mems:
        c, w = S[(b, "cold", m)], S[(b, "warm", m)]
        init = np.where(c["init"] > 0, c["init"], np.nan)
        n_init = int(np.isfinite(init).sum())
        bi = boot_median(init, c["batch"], B_SEBS)
        bc, bw = boot_median(c["client"], c["batch"], B_SEBS), boot_median(w["client"], w["batch"], B_SEBS)
        med_i[m], boots_i[m] = float(np.nanmedian(init)), bi
        med_c[m], boots_c[m] = float(np.median(c["client"]) - np.median(w["client"])), bc - bw
        missing_a.append(dict(benchmark=b, memory_mb=m, cold_records=c["n_raw"], cold_used=len(c["init"]),
                              cold_excluded_total=c["n_excluded"], cold_excluded_billed_other_memory=c["other_mem"],
                              init_present=n_init,
                              init_missing=len(c["init"]) - n_init,
                              init_missing_pct=round(100 * (len(c["init"]) - n_init) / max(len(c["init"]), 1), 1),
                              cold_batches=len(np.unique(c["batch"])), warm_used=len(w["client"]),
                              unexpected_in_cold_file=c["unexpected"], unexpected_in_warm_file=w["unexpected"],
                              cold_run_start_utc=dt.datetime.fromtimestamp(c["start"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M")))
        rows_a.append(dict(benchmark=b, name=BENCH[b], runtime=c["runtime"], memory_mb=m,
                           init_median_s=round(med_i[m], 4), init_ci_lo=round(ci(bi)[0], 4), init_ci_hi=round(ci(bi)[1], 4),
                           cmw_median_s=round(med_c[m], 4), cmw_ci_lo=round(ci(bc - bw)[0], 4), cmw_ci_hi=round(ci(bc - bw)[1], 4)))
    ref = 1024
    for r in rows_a:
        if r["benchmark"] == b:
            m = r["memory_mb"]
            q = boots_i[m] / boots_i[ref]
            r.update(init_ratio_to_1024=round(med_i[m] / med_i[ref], 3), ratio_ci_lo=round(ci(q)[0], 3),
                     ratio_ci_hi=round(ci(q)[1], 3), eq3_ratio=round(float(eq3(m)), 3),
                     eq3_inside_ci=bool(ci(q)[0] <= eq3(m) <= ci(q)[1]))
    # Sizes were run in sequence, some on a later day (2020-11-18 instead of 2020-11-11): a sensitivity analysis
    # keeps only the sizes run on the benchmark's most common cold-run day, so a day effect cannot pose as memory.
    day = {m: dt.datetime.fromtimestamp(S[(b, "cold", m)]["start"], dt.timezone.utc).date() for m in mems}
    modal = max(set(day.values()), key=list(day.values()).count)
    same = [m for m in mems if day[m] == modal]
    ranges = [("PRISM sizes 512-3008", [m for m in mems if m in PRISM_SIZES]), ("all sizes", mems)]
    if len(same) < len(mems):
        ranges.append((f"same-day sizes only ({modal})", same))
    for rng_name, sizes in ranges:
        if len(sizes) < 3:
            trend_a.append(dict(benchmark=b, name=BENCH[b], range=rng_name, sizes="/".join(map(str, sizes)),
                                init_direction="not estimable (< 3 sizes)"))
            continue
        si = np.array([slope(sizes, [boots_i[m][k] for m in sizes]) for k in range(B_SEBS)])
        sc = np.array([slope(sizes, [max(boots_c[m][k], 1e-6) for m in sizes]) for k in range(B_SEBS)])
        pos_c = all(med_c[m] > 0 for m in sizes)
        se, s_eq = slope(sizes, [med_i[m] for m in sizes]), slope(sizes, eq3(sizes))
        lo, hi = ci(si)
        # Eq. (3) agreement: direction, and whether its elasticity lies inside the bootstrap interval
        agree = ("yes, direction and slope" if direction(lo, hi) == "decreasing" and lo <= s_eq <= hi else
                 "direction only; steeper than Eq. (3)" if direction(lo, hi) == "decreasing" and hi < s_eq else
                 "direction only; flatter than Eq. (3)" if direction(lo, hi) == "decreasing" else
                 "no: increasing" if direction(lo, hi) == "increasing" else "inconclusive")
        steps = [(a, c2) for a, c2 in zip(sizes, sizes[1:])
                 if ci(boots_i[c2] / boots_i[a])[0] > 1.0]           # a step up whose interval excludes no change
        trend_a.append(dict(benchmark=b, name=BENCH[b], runtime=S[(b, "cold", mems[0])]["runtime"], range=rng_name,
                            sizes="/".join(map(str, sizes)), init_slope=round(se, 3), init_slope_lo=round(lo, 3),
                            init_slope_hi=round(hi, 3), eq3_slope=round(s_eq, 3), init_direction=direction(lo, hi),
                            eq3_agreement=agree,
                            significant_increases_between_adjacent_sizes=";".join(f"{a}->{c2}" for a, c2 in steps) or "none",
                            cmw_slope=round(slope(sizes, [med_c[m] for m in sizes]), 3) if pos_c else np.nan,
                            cmw_slope_lo=round(ci(sc)[0], 3), cmw_slope_hi=round(ci(sc)[1], 3),
                            cmw_direction=direction(*ci(sc)) if pos_c else "undefined (non-positive median)",
                            cross_check_agrees=(direction(*ci(sc)) == direction(lo, hi)) if pos_c else False))
pd.DataFrame(rows_a).to_csv(os.path.join(OUT, "sebs_by_benchmark_memory.csv"), index=False)
pd.DataFrame(trend_a).to_csv(os.path.join(OUT, "sebs_trend.csv"), index=False)
pd.DataFrame(missing_a).to_csv(os.path.join(OUT, "sebs_missingness.csv"), index=False)
log(f"SeBS done: {len(rows_a)} benchmark-memory cells ({time.time() - t0:.0f} s)")

# ------------------------------------------------------------------------------------------------ B. Huawei
COLS = ["funcName", "userID", "podID", "totalCost_cold_start", "podAllocationCost", "deployCodeCost",
        "deployDependencyCost", "schedulingCost"]
rt = pd.read_csv(os.path.join(DATA, "huawei_public_2025/df_funcID_runtime_triggerType.csv"))
KNOWN_RT = {"Python3", "Java", "Node.js", "Python2", "Custom", "PHP7.3", "Go1.x", "C#"}
rt["runtime_clean"] = rt["runtime"].where(rt["runtime"].isin(KNOWN_RT), "unknown")
rt_map = dict(zip(rt["funcID"], rt["runtime_clean"]))
reg_rows, wf_rows, rt_rows, comp_rows, qa_rows = [], [], [], [], []


def within_function(fm, label, extra):
    """fm: per (func, mem) medians with event counts. One log-log slope per function seen in >= 2 memory sizes."""
    fm = fm[fm["n"] >= MIN_EVENTS]
    sl = [slope(g["mem"], g["med"]) for _, g in fm.groupby("fkey") if g["mem"].nunique() >= 2]
    sl = np.array(sl)
    if len(sl) == 0:
        wf_rows.append(dict(scope=label, **extra, functions=0))
        return
    bs = np.array([np.median(RNG.choice(sl, len(sl))) for _ in range(B_HW)])
    k = int((sl < 0).sum())
    wf_rows.append(dict(scope=label, **extra, functions=len(sl), share_decreasing=round(k / len(sl), 3),
                        share_increasing=round(float((sl > 0).mean()), 3), median_slope=round(float(np.median(sl)), 3),
                        slope_ci_lo=round(ci(bs)[0], 3), slope_ci_hi=round(ci(bs)[1], 3),
                        sign_test_p=float(stats.binomtest(k, int((sl != 0).sum()) or 1).pvalue) if (sl != 0).any() else np.nan,
                        direction=direction(*ci(bs))))


for reg in range(1, 6):
    z = __import__("zipfile").ZipFile(os.path.join(DATA, f"huawei_public_2025/cold_starts/R{reg}.zip"))
    parts, days = [], 0
    for name in sorted(n for n in z.namelist() if n.endswith(".csv")):
        with z.open(name) as fh:
            d = pd.read_csv(fh, usecols=COLS)
        days += 1
        pool = d["podID"].astype(str).str.rpartition("-")[0]
        up = pd.Series(pool.unique())
        # Two pool families encode CPU and memory the same way: standard "poolNN-<cpu>-<mem>" and
        # "custom-<cpu>-<mem>". The main analysis uses standard pools; custom pools are reported separately.
        cm = up.str.extract(r"^(pool\d+|custom)-(\d+)-(\d+)$")
        ptype = pool.map(dict(zip(up, np.where(cm[0] == "custom", "custom", np.where(cm[0].notna(), "standard", None)))))
        cpu = pool.map(dict(zip(up, cm[1].astype(float)))); mem = pool.map(dict(zip(up, cm[2].astype(float))))
        parts.append(pd.DataFrame({"fkey": d["funcName"].astype(str) + "---" + d["userID"].astype(str),
                                   "pool": pool, "ptype": ptype, "cpu": cpu, "mem": mem,
                                   **{c: d[c].astype("float32") for c in COLS[3:]}}))
    d = pd.concat(parts, ignore_index=True); del parts
    comp_sum = d[COLS[4:]].sum(axis=1)
    qa_rows.append(dict(region=f"R{reg}", day_files=days, events=len(d), functions=d["fkey"].nunique(),
                        pools=d["pool"].nunique(), unparsed_pool=int(d["mem"].isna().sum()),
                        custom_pool_events=int((d["ptype"] == "custom").sum()),
                        missing_total=int(d["totalCost_cold_start"].isna().sum()),
                        nonpositive_total=int((d["totalCost_cold_start"] <= 0).sum()),
                        total_equals_component_sum_share=round(float((np.abs(d["totalCost_cold_start"] - comp_sum) < 1e-3).mean()), 5)))
    d = d[d["mem"].notna() & (d["totalCost_cold_start"] > 0)]
    for pt, g in d[d["ptype"] == "custom"].groupby("mem"):      # custom pools: descriptive only
        f = g.groupby("fkey")["totalCost_cold_start"].agg(["median", "size"])
        f = f[f["size"] >= MIN_EVENTS]["median"].to_numpy()
        reg_rows.append(dict(region=f"R{reg}", pool_type="custom", memory_mb=int(pt),
                             cpu_millicores="/".join(str(int(c)) for c in sorted(g["cpu"].unique())),
                             events=len(g), functions=g["fkey"].nunique(), functions_ge20=len(f),
                             event_median_s=round(float(g["totalCost_cold_start"].median()), 3),
                             event_p90_s=round(float(g["totalCost_cold_start"].quantile(0.9)), 3),
                             function_weighted_median_s=round(float(np.median(f)), 3) if len(f) else np.nan))
    d = d[d["ptype"] == "standard"]
    fm = d.groupby(["fkey", "mem"], observed=True)["totalCost_cold_start"].agg(med="median", n="size").reset_index()
    for m, g in d.groupby("mem"):
        f = fm[(fm["mem"] == m) & (fm["n"] >= MIN_EVENTS)]["med"].to_numpy()
        bs = [np.median(RNG.choice(f, len(f))) for _ in range(B_HW)] if len(f) else [np.nan]
        reg_rows.append(dict(region=f"R{reg}", pool_type="standard", memory_mb=int(m), cpu_millicores="/".join(str(int(c)) for c in sorted(g["cpu"].unique())),
                             events=len(g), functions=g["fkey"].nunique(), functions_ge20=len(f),
                             event_median_s=round(float(g["totalCost_cold_start"].median()), 3),
                             event_p90_s=round(float(g["totalCost_cold_start"].quantile(0.9)), 3),
                             function_weighted_median_s=round(float(np.median(f)), 3) if len(f) else np.nan,
                             fw_ci_lo=round(ci(bs)[0], 3), fw_ci_hi=round(ci(bs)[1], 3)))
        comp_rows.append(dict(region=f"R{reg}", memory_mb=int(m), events=len(g),
                              **{f"median_{c}": round(float(g[c].median()), 4) for c in COLS[4:]},
                              **{f"share_of_total_{c}": round(float(g[c].sum() / g["totalCost_cold_start"].sum()), 3) for c in COLS[4:]}))
    within_function(fm, "region", dict(region=f"R{reg}", runtime="all"))
    if reg == 2:                                 # runtimes exist only for Region 2 (funcID = funcName---userID---pool)
        d["runtime"] = (d["fkey"] + "---" + d["pool"]).map(rt_map).fillna("unmatched")
        qa_rows[-1]["runtime_matched_share"] = round(float((d["runtime"] != "unmatched").mean()), 4)
        frt = d.groupby(["fkey", "mem", "runtime"], observed=True)["totalCost_cold_start"].agg(med="median", n="size").reset_index()
        for r_name, g in frt.groupby("runtime"):
            within_function(g, "region x runtime", dict(region="R2", runtime=r_name))
            for m, gm in g[g["n"] >= MIN_EVENTS].groupby("mem"):
                rt_rows.append(dict(region="R2", runtime=r_name, memory_mb=int(m), functions_ge20=len(gm),
                                    function_weighted_median_s=round(float(gm["med"].median()), 3)))
    log(f"Huawei R{reg}: {len(d):,} events, {days} days ({time.time() - t0:.0f} s)")
    del d

pd.DataFrame(reg_rows).to_csv(os.path.join(OUT, "huawei_region_memory.csv"), index=False)
pd.DataFrame(wf_rows).to_csv(os.path.join(OUT, "huawei_within_function.csv"), index=False)
pd.DataFrame(rt_rows).to_csv(os.path.join(OUT, "huawei_R2_runtime_memory.csv"), index=False)
pd.DataFrame(comp_rows).to_csv(os.path.join(OUT, "huawei_components.csv"), index=False)
pd.DataFrame(qa_rows).to_csv(os.path.join(OUT, "huawei_quality.csv"), index=False)
json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__,
               scipy=scipy.__version__, seed=20261121, bootstrap=dict(sebs=B_SEBS, huawei=B_HW),
               min_events_per_function_pool=MIN_EVENTS, eq3="f(m) = 0.7 + 0.3*1024/m (prism_repro.latency.init_factor, eq3)",
               label="EXPLORATORY, POST HOC; external historical data; not a PRISM measurement"),
          open(os.path.join(OUT, "environment.json"), "w"), indent=1)
log(f"done in {time.time() - t0:.0f} s")
