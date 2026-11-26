#!/usr/bin/env python3
"""PROVISIONAL training split with an out-of-sample conformal warm-up (R4.6, R5.M3).

PROVISIONAL: the split is a candidate for the author's decision, not the paper's protocol. Fast simulator,
assumed constants, current code. Nothing here replaces a published number.

Submitted split: the forecaster is fitted on days 0-13 and the conformal offset starts at zero at the start of the
validation week (day 14), so the validation week is replayed with a cold offset while the test week (day 21)
inherits a warm one. A warm-up on the days before validation does not help under that split, because those days
are in the training range (the offset ends the warm-up near 0.04; NA-7).
PROVISIONAL split: fit on days 0-10 (PrismConfig.forecast_train_days = 11), replay the conformal update on the
out-of-sample days 11-13 (conformal_warmup_days = 3), then validate (days 14-20) and test (days 21-27) as before.

Per split and trace (seeds 101-105): PRISM, QuantProv-q90 and the no-recalibration ablation (PRISM on the raw
forecast, use_conformal = False) are tuned on the validation week by the common rule (cheapest with validation
violating-window rate <= 2%), then run on the four held-out test weeks. Reported in one table: the selected
setting, its validation-week result, and its test-week results. Also per trace: the offset at the start of
validation and of test, and q0.9 coverage of the calibrated forecast on both weeks (stationary trace).

Usage: python provisional_split.py <code_root> <out_dir> [--workers=N]  |  ... <out_dir> --analyse
"""
import glob
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.join(ROOT, "src"))

SEEDS = (101, 102, 103, 104, 105)
SCEN = ("stationary", "growth", "bursty", "new_spike")
SPLITS = {"submitted": dict(),
          "PROVISIONAL": dict(forecast_train_days=11, conformal_warmup_days=3)}
SPLIT_LABEL = {"submitted": "submitted split (fit days 0-13, offset starts at 0 on day 14)",
               "PROVISIONAL": "PROVISIONAL split (fit days 0-10, out-of-sample warm-up days 11-13)"}


def _families():
    from prism_repro.experiment import GRIDS
    return {"PRISM": (dict(family="PRISM"), GRIDS["PRISM"]),
            "QuantProv_q90": (dict(family="QuantProv", tau_idx=2), GRIDS["QuantProv"]),
            "PRISM no recalibration": (dict(family="PRISM", prism=dict(use_conformal=False)), GRIDS["PRISM"])}


def job(task):
    split, seed = task
    from prism_repro.config import PipelineConfig, PrismConfig
    from prism_repro.experiment import TraceBundle, make_policy, select_by_rule
    from prism_repro.simulator import simulate
    t0 = time.time()
    b = TraceBundle(seed, PipelineConfig(), conformal=PrismConfig().with_(**SPLITS[split]))
    diag = dict(split=split, seed=seed, kind="diagnostic")
    for wk in ("val", "test"):
        f = b.forecasts[("stationary", wk, "gbm")]
        diag[f"offset_start_{wk}"] = float(f["s"][0])
        diag[f"offset_mean_{wk}"] = float(np.mean(f["s"]))
        diag[f"q90_coverage_{wk}"] = float(np.mean(f["y"] <= f["q_cal"][:, 2]))
        diag[f"q99_coverage_{wk}"] = float(np.mean(f["y"] <= f["q_cal"][:, 3]))
        diag[f"q90_raw_coverage_{wk}"] = float(np.mean(f["y"] <= f["q_raw"][:, 2]))
    rows = [diag]
    for fam, (spec, grid) in _families().items():
        val = []
        for p in grid:
            s = simulate(b.context("stationary", "val"), make_policy(dict(spec, param=p)))["summary"]
            val.append(dict(param=p, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"])))
            rows.append(dict(split=split, seed=seed, kind="run", family=fam, week="val", scenario="validation", param=p,
                             cost=val[-1]["cost"], viol=val[-1]["violating_window_rate"]))
        sel = select_by_rule(val)
        rows.append(dict(split=split, seed=seed, kind="selection", family=fam, param=sel["param"],
                         val_cost=sel["cost"], val_viol=sel["violating_window_rate"],
                         val_meets=bool(sel["violating_window_rate"] <= 0.02 + 1e-12)))
        for sc in SCEN:
            s = simulate(b.context(sc, "test"), make_policy(dict(spec, param=sel["param"])))["summary"]
            rows.append(dict(split=split, seed=seed, kind="run", family=fam, week="test", scenario=sc,
                             param=sel["param"], selected=True, cost=float(s["cost"]),
                             viol=float(s["violating_window_rate"])))
    return rows, round(time.time() - t0, 1)


def run(out_dir, workers):
    tasks = [(sp, s) for sp in SPLITS for s in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows, t in ex.map(job, tasks):
            r0 = rows[0]
            with open(os.path.join(out_dir, f"rows_{r0['split']}_{r0['seed']}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            print(f"{r0['split']} seed {r0['seed']}: {len(rows)} rows in {t}s", flush=True)
    import scipy
    import sklearn
    json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                   scipy=scipy.__version__, sklearn=sklearn.__version__),
              open(os.path.join(out_dir, "environment.json"), "w"), indent=1)


def analyse(out_dir):
    rows = [json.loads(line) for p in sorted(glob.glob(os.path.join(out_dir, "rows_*.jsonl"))) for line in open(p)]
    envp = os.path.join(out_dir, "environment.json")
    env = json.load(open(envp)) if os.path.exists(envp) else {}
    print("PROVISIONAL TRAINING SPLIT, EXPLORATORY. Fast simulator, assumed constants, current code. "
          f"Environment: {env}.\nEach selected setting's validation-week result beside its test-week results "
          "(four held-out test weeks per trace). Violating windows pooled over the week (672 windows; 2% = 13 allowed).")
    print("\nConformal offset and coverage (stationary trace): offset at the start of validation | mean over validation | "
          "at the start of test | q0.9 coverage val / test (calibrated; raw)")
    for split in SPLITS:
        print(f"  {SPLIT_LABEL[split]}")
        for d in sorted([r for r in rows if r["kind"] == "diagnostic" and r["split"] == split], key=lambda r: r["seed"]):
            print(f"    seed {d['seed']}: {d['offset_start_val']:+.3f} | {d['offset_mean_val']:+.3f} | {d['offset_start_test']:+.3f} | "
                  f"{100 * d['q90_coverage_val']:.1f}% / {100 * d['q90_coverage_test']:.1f}% "
                  f"(raw {100 * d['q90_raw_coverage_val']:.1f}% / {100 * d['q90_raw_coverage_test']:.1f}%)")
    print("\nOne table: split | family | trace | selected | VALIDATION violating windows, cost | TEST violating windows "
          "(mean of 4), cost (mean of 4), weeks within 2%")
    for split in SPLITS:
        for fam in _families():
            sel = sorted([r for r in rows if r["kind"] == "selection" and r["split"] == split and r["family"] == fam],
                         key=lambda r: r["seed"])
            agg = []
            for s in sel:
                t = [r for r in rows if r["kind"] == "run" and r["week"] == "test" and r["split"] == split
                     and r["family"] == fam and r["seed"] == s["seed"]]
                tv, tc = np.array([r["viol"] for r in t]), np.array([r["cost"] for r in t])
                agg.append((s["val_viol"], s["val_cost"], tv.mean(), tc.mean(), int((tv <= 0.02 + 1e-12).sum())))
                print(f"  {split:11s} | {fam:22s} | {s['seed']} | {s['param']:>5} | {100 * s['val_viol']:5.2f}% {s['val_cost']:8.1f}"
                      f"{'' if s['val_meets'] else ' (none met 2%)'} | {100 * tv.mean():5.2f}% {tc.mean():8.1f} | "
                      f"{int((tv <= 0.02 + 1e-12).sum())}/4")
            if agg:
                a = np.array(agg)
                print(f"  {split:11s} | {fam:22s} | mean |       | {100 * a[:, 0].mean():5.2f}% {a[:, 1].mean():8.1f} | "
                      f"{100 * a[:, 2].mean():5.2f}% {a[:, 3].mean():8.1f} | {int(a[:, 4].sum())}/20")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        w = [int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")]
        run(out, w[0] if w else 5)
