#!/usr/bin/env python3
"""R2.9: all families on less-structured real arrival traces (Huawei Public Cloud 2025, Region 2), R1 protocol.

EXPLORATORY, POST HOC, PRE-CALIBRATION, fast simulator. The plan (selection rule, protocol, metrics) was fixed before
selection: docs/revision/less_structured_r29_20261122/PLAN.md (PLAN.sha256). Simulator draw seeds 301-310; the
confirmatory seeds 106-130 are not used. The derived traces stay local (no licence stated for the source).

usage (from prism-repro/):
  python scripts/revision/less_structured_region2.py . --select  <requests dir> <derived dir> <out dir>
  python scripts/revision/less_structured_region2.py . --run     <derived dir> <out dir> [--workers=N]
  python scripts/revision/less_structured_region2.py . --analyse <derived dir> <out dir>
"""
import glob, hashlib, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
WINDOW_DAYS, MIN_MEAN, MIN_ACTIVE, N_PICK, TARGET_MEAN = 28, 600.0, 0.95, 10, 600.0
SEED0, THIN_SEED0 = 301, 20261122
TARGET = 0.02


def select(req_dir, derived, out):
    import pandas as pd
    files = sorted(glob.glob(os.path.join(req_dir, "day_*.csv")))[:WINDOW_DAYS]
    assert len(files) == WINDOW_DAYS, len(files)
    frames = [pd.read_csv(f) for f in files]
    cols = sorted(set.intersection(*[set(f.columns) - {"day", "time"} for f in frames]))
    X = np.concatenate([f[cols].fillna(0).to_numpy(dtype=np.int64) for f in frames], axis=0)   # minutes x functions
    assert X.shape[0] == WINDOW_DAYS * 1440
    mean, active = X.mean(axis=0), (X > 0).mean(axis=0)
    elig = [i for i in range(len(cols)) if mean[i] >= MIN_MEAN and active[i] >= MIN_ACTIVE]
    order = sorted(elig, key=lambda i: hashlib.sha256(cols[i].encode()).hexdigest())
    pick = order[:N_PICK]
    os.makedirs(derived, exist_ok=True)
    sel = {"rule": dict(window_days=WINDOW_DAYS, min_mean=MIN_MEAN, min_active=MIN_ACTIVE, n_pick=N_PICK,
                        order="sha256(funcID) ascending", thin_seed0=THIN_SEED0, sim_seed0=SEED0),
           "source_files": {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files},
           "n_functions_in_window": len(cols), "n_eligible": len(elig), "selected": []}
    for rank, i in enumerate(pick):
        x = X[:, i]
        p = TARGET_MEAN / x.mean()
        y = np.random.default_rng(THIN_SEED0 + rank).binomial(x, p)
        path = os.path.join(derived, f"r2_{rank:02d}.csv")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("minute,count\n" + "".join(f"{m},{int(v)}\n" for m, v in enumerate(y)))
        sel["selected"].append(dict(rank=rank, sim_seed=SEED0 + rank, funcID=cols[i], source_mean=float(x.mean()),
                                    source_active=float(active[i]), thin_p=float(p), mean=float(y.mean()),
                                    zero_minutes=int((y == 0).sum()),
                                    counts_sha256=hashlib.sha256(y.astype("<i8").tobytes()).hexdigest()))
    os.makedirs(out, exist_ok=True)
    json.dump(sel, open(os.path.join(out, "selection.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(cols)} functions, {len(elig)} eligible, {len(pick)} selected")


def bundle(derived, rank):
    from prism_repro.config import PipelineConfig, PrismConfig
    from prism_repro.experiment import TraceBundle
    from prism_repro.trace_io import load_minute_csv

    class Region2Bundle(TraceBundle):
        def __init__(self):
            counts = load_minute_csv(os.path.join(derived, f"r2_{rank:02d}.csv"))[:WINDOW_DAYS * 1440]
            self.seed, self.cfg, self.wp = SEED0 + rank, PipelineConfig(), None
            self.scenarios = ("real",)
            self.traces = {"real": {"counts": counts, "trigger_minutes_known": np.array([], dtype=int)}}
            self.trigger_minutes = np.array([], dtype=int)
            self.pc = PrismConfig()
            self.fc_names = ("gbm",)
            self._draws, self._khist, self.forecasts, self.forecast_quality, self.models = {}, {}, {}, {}, {}
            self._train_forecasters()
    return Region2Bundle()


def task(derived, out, rank):
    import run_experiments as RE
    from prism_repro.experiment import run_policy
    from prism_repro.metrics import coverage, mape, pinball
    path = os.path.join(out, f"rows_r2_{rank:02d}.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []
    done = {(r["week"], json.dumps(r["spec"], sort_keys=True)) for r in rows if r.get("kind") == "run"}
    b = bundle(derived, rank)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if not any(r.get("kind") == "forecast" for r in rows):
            fc = b.forecasts[("real", "test", "gbm")]
            y, qr, qc = fc["y"], fc["q_raw"], fc["q_cal"]
            f.write(json.dumps(dict(kind="forecast", rank=rank, mape_median=float(mape(y, qr[:, 1])),
                                    pinball_90=float(pinball(y, qr[:, 2], 0.9)), cov90_cal=float(coverage(y, qc[:, 2])),
                                    cov99_cal=float(coverage(y, qc[:, 3])))) + "\n"); f.flush()
        for wk in ("val", "test"):
            for spec in RE.grid_specs():
                key = (wk, json.dumps(spec, sort_keys=True))
                if key in done:
                    continue
                t0 = time.perf_counter()
                s = run_policy(b, "real", wk, spec)["summary"]
                f.write(json.dumps(dict(kind="run", rank=rank, week=wk, spec=spec, cost=float(s["cost"]),
                                        violating_window_rate=float(s["violating_window_rate"]),
                                        runtime_s=time.perf_counter() - t0)) + "\n"); f.flush()
    return rank


def family(spec):
    f = spec["family"]
    if f == "PredHead" and spec.get("hyst"):
        return "PredHead+S"
    if f == "QuantProv":
        return "QuantProv-q90" if spec.get("tau_idx") == 2 else "QuantProv-q99"
    return f


def analyse(derived, out):
    from scipy import stats
    from prism_repro.experiment import select_by_rule
    from prism_repro.trace_io import load_minute_csv
    sel = json.load(open(os.path.join(out, "selection.json"), encoding="utf-8"))
    FAMS = ("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+S", "QuantProv-q90", "QuantProv-q99", "PRISM")
    L = ["R2.9: ALL FAMILIES ON LESS-STRUCTURED REAL TRACES (Huawei Public 2025, Region 2); R1 protocol; EXPLORATORY,",
         "POST HOC, PRE-CALIBRATION, fast simulator. Plan fixed before selection: PLAN.md.", "",
         f"Functions in the 28-day window: {sel['n_functions_in_window']}; eligible: {sel['n_eligible']}; selected: {len(sel['selected'])}", ""]
    res, fq, struct = {}, {}, {}
    for t in sel["selected"]:
        k = t["rank"]
        c = load_minute_csv(os.path.join(derived, f"r2_{k:02d}.csv"))[:WINDOW_DAYS * 1440].astype(float)
        ac = float(np.corrcoef(c[:-1440], c[1440:])[0, 1])
        struct[k] = dict(cv=float(c.std() / c.mean()), daily_autocorr=ac,
                         p999_over_median=float(np.percentile(c, 99.9) / max(np.median(c), 1)), zero_minutes=t["zero_minutes"])
        rows = [json.loads(l) for l in open(os.path.join(out, f"rows_r2_{k:02d}.jsonl"), encoding="utf-8")]
        fq[k] = next(r for r in rows if r["kind"] == "forecast")
        for fam in FAMS:
            val = [r for r in rows if r.get("kind") == "run" and r["week"] == "val" and family(r["spec"]) == fam]
            test = [r for r in rows if r.get("kind") == "run" and r["week"] == "test" and family(r["spec"]) == fam]
            if not val:
                continue
            s = select_by_rule(val)
            tt = next(r for r in test if r["spec"] == s["spec"])
            res[(k, fam)] = dict(param=s["spec"].get("param"), val_viol=s["violating_window_rate"], cost=tt["cost"],
                                 viol=tt["violating_window_rate"])
    ks = [t["rank"] for t in sel["selected"] if all((t["rank"], f) in res for f in FAMS)]
    L.append(f"Traces complete: {len(ks)} of {len(sel['selected'])}")
    L.append("Trace structure (28 days) and GBM test-week forecast quality:")
    for k in ks:
        s, q = struct[k], fq[k]
        L.append(f"  r2_{k:02d}: CV {s['cv']:.2f}, daily autocorr {s['daily_autocorr']:+.2f}, p99.9/median {s['p999_over_median']:.1f}, "
                 f"zero minutes {s['zero_minutes']}; median APE {q['mape_median']:.1f}%, pinball0.9 {q['pinball_90']:.1f}, "
                 f"cov90_cal {100*q['cov90_cal']:.1f}%")
    L.append("")
    L.append("Test week (days 21-27) at the validation-selected settings: mean over traces")
    L.append(f"  {'family':14s} {'cost USD':>9s} {'viol %':>7s} {'met 2%':>7s}  selected settings")
    for fam in FAMS:
        rr = [res[(k, fam)] for k in ks]
        L.append(f"  {fam:14s} {np.mean([r['cost'] for r in rr]):9,.0f} {100*np.mean([r['viol'] for r in rr]):7.2f} "
                 f"{sum(r['viol'] <= TARGET + 1e-12 for r in rr):>3d}/{len(rr)}  {[r['param'] for r in rr]}")
    L.append("")
    L.append("Paired PRISM minus comparator over traces (mean +/- 95% t half-width; traces where PRISM is cheaper / less violating):")
    hw = lambda x: stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    inc = lambda x: "includes 0" if abs(x.mean()) <= hw(x) else "excludes 0"
    adv_reactive = {}
    for fam in FAMS[:-1]:
        dc = np.array([100 * (res[(k, "PRISM")]["cost"] / res[(k, fam)]["cost"] - 1) for k in ks])
        dv = np.array([100 * (res[(k, "PRISM")]["viol"] - res[(k, fam)]["viol"]) for k in ks])
        if fam == "Reactive":
            adv_reactive = dict(zip(ks, dc))
        L.append(f"  vs {fam:14s} cost {dc.mean():+6.1f} +/- {hw(dc):4.1f}% ({inc(dc)}; cheaper in {int((dc < 0).sum())}/{len(ks)}); "
                 f"viol {dv.mean():+6.2f} +/- {hw(dv):4.2f} pts ({inc(dv)}; fewer in {int((dv < 0).sum())}/{len(ks)})")
    rho, p = stats.spearmanr([fq[k]["mape_median"] for k in ks], [adv_reactive[k] for k in ks])
    L.append("")
    L.append(f"Exploratory: Spearman(forecast median APE, PRISM cost vs Reactive) = {rho:+.2f} (p = {p:.2f}, n = {len(ks)})")
    # Grid-edge disclosure and per-trace table (the paper's GRIDS, fixed by PLAN.md; widened grids were not run).
    from prism_repro.experiment import GRIDS
    G = {"Static": GRIDS["Static"], "Scheduled": GRIDS["Scheduled"], "Reactive": GRIDS["Reactive"], "PredHead": GRIDS["PredHead"],
         "PredHead+S": GRIDS["PredHead"], "QuantProv-q90": GRIDS["QuantProv"], "QuantProv-q99": GRIDS["QuantProv"], "PRISM": GRIDS["PRISM"]}
    edge = lambda fam, v: "" if fam not in G else ("low" if v == min(G[fam]) else "high" if v == max(G[fam]) else "")
    table = [dict(trace=f"r2_{k:02d}", family=fam, selected=res[(k, fam)]["param"], edge=edge(fam, res[(k, fam)]["param"]),
                  val_viol_pct=round(100 * res[(k, fam)]["val_viol"], 2), test_cost_usd=round(res[(k, fam)]["cost"], 1),
                  test_viol_pct=round(100 * res[(k, fam)]["viol"], 2), met_2pct=res[(k, fam)]["viol"] <= TARGET + 1e-12)
             for k in ks for fam in FAMS]
    by_fam = {f: sum(1 for r in table if r["family"] == f and r["edge"]) for f in G}
    L.append(f"Validation selections at an edge of the paper's grid: {sum(by_fam.values())} of {len(G) * len(ks)} "
             f"(by family: {', '.join(f'{f} {n}' for f, n in by_fam.items())}); widened grids were not run.")
    import csv
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    with open(os.path.join(out, "tables", "per_trace.csv"), "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]), lineterminator="\n"); w.writeheader(); w.writerows(table)
    # Shareable selection record without source function identifiers (selection.json, which has them, stays local).
    pub = {k: v for k, v in sel.items() if k != "selected"}
    pub["selected"] = [{k: v for k, v in t.items() if k != "funcID"} for t in sel["selected"]]
    pub["note"] = "funcID omitted: source identifiers stay local while the data licence is unresolved (selection.json)."
    with open(os.path.join(out, "selection_public.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(pub, f, indent=1); f.write("\n")
    txt = "\n".join(L) + "\n"
    open(os.path.join(out, "summary.txt"), "w", encoding="utf-8", newline="\n").write(txt)
    print(txt)


def main():
    mode = sys.argv[2]
    if mode == "--select":
        return select(sys.argv[3], sys.argv[4], sys.argv[5])
    derived, out = sys.argv[3], sys.argv[4]
    if mode == "--analyse":
        return analyse(derived, out)
    sel = json.load(open(os.path.join(out, "selection.json"), encoding="utf-8"))
    workers = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--workers=")), "4"))
    print(f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} workers={workers}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for fu in as_completed([ex.submit(task, derived, out, t["rank"]) for t in sel["selected"]]):
            print(f"done r2_{fu.result():02d} {time.strftime('%H:%M:%SZ', time.gmtime())}", flush=True)
    print(f"end {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)


if __name__ == "__main__":
    main()
