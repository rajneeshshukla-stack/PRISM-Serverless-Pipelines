#!/usr/bin/env python3
"""R1.1(b) revised margin rule on fresh traces (docs/revision/margin_r11_fresh_20261124/PLAN.md). EXPLORATORY,
PRE-CALIBRATION, OPEN LOOP. PRISM only, through the paper's E1 (fast-simulator schedules) and E12 (event-level
validation retuning) code paths, then test-week event-level replays at margins 0, 10% and 50%. Resumable: every
replay is appended to rows.jsonl as it finishes; keys already present are skipped.

usage (from prism-repro/):
  stage 1, Linux, v1-submitted tree (reproduces the stored E1):
       PRISM_ROOT=<v1 tree>/prism-repro python scripts/revision/margin_fresh_r11.py <out dir> check
       PRISM_ROOT=<v1 tree>/prism-repro python scripts/revision/margin_fresh_r11.py <out dir> schedules 131 132 133 134 135
  stage 2, this tree:
       venv/Scripts/python scripts/revision/margin_fresh_r11.py <out dir> run <seed> [<seed> ...]
       venv/Scripts/python scripts/revision/margin_fresh_r11.py <out dir> analyse
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Stage 1 ('schedules', 'check') computes fast-simulator schedules with the tree in PRISM_ROOT: the v1-submitted tree,
# which reproduces the stored E1 schedules on Linux. Stage 2 ('run', 'analyse') replays them at event level with this
# tree's current des.py, as ../event_severity_resumed_20261122 did for the stored schedules.
ROOT = os.path.abspath(os.environ.get("PRISM_ROOT", HERE_ROOT))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import GRIDS, select_by_rule  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS, generate_trace  # noqa: E402

CFG = PipelineConfig()
MARGINS = (0.0, 0.10, 0.50)
FRESH = (131, 132, 133, 134, 135)


def rule_E(eps):
    return 0.10 if eps <= 0.02 + 1e-12 else 0.50


def schedule(bundle, scenario, week, eps):
    from prism_repro.experiment import make_policy
    from prism_repro.simulator import simulate
    res = simulate(bundle.context(scenario, week, True), make_policy(dict(family="PRISM", param=eps)))
    return res["raw"]["P_epoch"].astype(float), res["raw"]["mem_epoch"], res["summary"]


def replay(draws, P, m, margin):
    from prism_repro.des import simulate_events
    if margin:
        P = np.ceil(P * (1.0 + margin) - 1e-9)
    t0 = time.perf_counter()
    s = simulate_events(CFG, draws, P, m, want_inflight=False, sample_seed=None)["summary"]
    return dict(cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"]),
                overflow_share=float(s["overflow_share"]), cold_start_ratio=float(s["cold_start_ratio"]),
                runtime_s=time.perf_counter() - t0)


def done_keys(path):
    """Rows from <out>/rows_<seed>.jsonl (one file per seed, so seeds can run in parallel processes)."""
    import glob
    out = {}
    for p in sorted(glob.glob(os.path.join(os.path.dirname(path), "rows_*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def schedules(out, seeds):
    """Stage 1: fast-simulator schedules of every eps on the validation week and every test week."""
    from prism_repro.experiment import TraceBundle
    for seed in seeds:
        path = os.path.join(out, f"sched_seed{seed}.npz")
        if os.path.exists(path):
            print(f"[{seed}] schedules present", flush=True)
            continue
        t, b, arr = time.time(), TraceBundle(seed, CFG), {}
        for wk, sc in [("val", "stationary")] + [("test", x) for x in MAIN_SCENARIOS]:
            for eps in GRIDS["PRISM"]:
                P, m, _ = schedule(b, sc, wk, eps)
                arr[f"{wk}|{sc}|{eps:g}::P"], arr[f"{wk}|{sc}|{eps:g}::m"] = P, m
        np.savez_compressed(path + ".tmp.npz", **arr)
        os.replace(path + ".tmp.npz", path)
        print(f"[{seed}] schedules {len(arr) // 2} in {time.time() - t:.0f}s", flush=True)


def check(out):
    """Stage-1 code-path check: trace 103's recomputed schedules against the stored E1 arrays (validation week, every
    eps; test weeks at the selected eps 0.03)."""
    schedules(out, [103])
    new = np.load(os.path.join(out, "sched_seed103.npz"))
    arr = np.load(os.path.join(HERE_ROOT, "results", "raw", "E1", "arrays_seed103.npz"))
    res = {}
    for wk, sc in [("val", "stationary")] + [("test", x) for x in MAIN_SCENARIOS]:
        for eps in GRIDS["PRISM"]:
            k = f"E1|103|{sc}|{wk}|PRISM-{eps:g}|"
            if k + "::P_epoch" not in arr:
                continue
            same = bool(np.array_equal(new[f"{wk}|{sc}|{eps:g}::P"], arr[k + "::P_epoch"].astype(float)) and
                        np.array_equal(new[f"{wk}|{sc}|{eps:g}::m"], arr[k + "::mem_epoch"]))
            res[f"{wk}|{sc}|{eps:g}"] = same
    out_d = {"tree": ROOT, "schedules_compared": len(res), "identical": sum(res.values()), "detail": res}
    with open(os.path.join(out, "codepath_check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out_d, f, indent=1)
    print(json.dumps({k: v for k, v in out_d.items() if k != "detail"}))


def run(out, seeds):
    done = done_keys(os.path.join(out, "rows.jsonl"))
    for seed in seeds:
        with open(os.path.join(out, f"rows_{seed}.jsonl"), "a", encoding="utf-8", newline="\n") as f:
            t = time.time()
            S = np.load(os.path.join(out, f"sched_seed{seed}.npz"))
            vc = generate_trace(seed, "stationary")["counts"][14 * 1440:21 * 1440]
            from prism_repro.des import EventDraws
            vdr = EventDraws(CFG, vc, seed, 2)
            vals = []
            for eps in GRIDS["PRISM"]:
                key = f"{seed}|val|{eps}"
                if key not in done:
                    P, m = S[f"val|stationary|{eps:g}::P"], S[f"val|stationary|{eps:g}::m"]
                    r = dict(key=key, seed=seed, week="val", scenario="validation", eps=eps, margin=0.0,
                             label=f"PRISM-{eps:g}", **replay(vdr, P, m, 0.0))
                    f.write(json.dumps(r) + "\n"); f.flush(); done[key] = r
                    print(f"[{seed}] val eps {eps}: viol {r['violating_window_rate']:.4f} {r['runtime_s']:.0f}s", flush=True)
                vals.append(dict(done[key], spec=dict(family="PRISM", param=eps)))
            sel = select_by_rule(vals)
            eps = sel["eps"]
            for sc in MAIN_SCENARIOS:
                tc = generate_trace(seed, sc)["counts"][21 * 1440:28 * 1440]
                tdr = None
                P = m = None
                for mg in MARGINS:
                    key = f"{seed}|test|{sc}|{eps}|{mg:g}"
                    if key in done:
                        continue
                    if P is None:
                        P, m = S[f"test|{sc}|{eps:g}::P"], S[f"test|{sc}|{eps:g}::m"]
                        tdr = EventDraws(CFG, tc, seed, 3)
                    r = dict(key=key, seed=seed, week="test", scenario=sc, eps=eps, margin=mg, selected=True,
                             rule_E_margin=rule_E(eps), **replay(tdr, P, m, mg))
                    f.write(json.dumps(r) + "\n"); f.flush(); done[key] = r
                    print(f"[{seed}] test {sc} eps {eps} margin {mg:g}: viol {r['violating_window_rate']:.4f} "
                          f"cost {r['cost']:.0f} {r['runtime_s']:.0f}s", flush=True)
            print(f"[{seed}] complete in {time.time() - t:.0f}s, selected eps {eps}", flush=True)


def cp(k, n):
    from scipy import stats
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return 100 * lo, 100 * hi


def analyse(out):
    rows = list(done_keys(os.path.join(out, "rows.jsonl")).values())
    test = {}
    for r in rows:
        if r["week"] == "test":
            test.setdefault((r["seed"], r["scenario"]), {})[r["margin"]] = r
    weeks = sorted(w for w, d in test.items() if set(d) == set(MARGINS))
    sel = {s: next(r["eps"] for r in rows if r["seed"] == s and r["week"] == "test") for s in sorted({w[0] for w in weeks})}
    L = ["R1.1(b) revised margin rule on fresh traces 131-135. EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event-level, "
         "Windows. Plan: docs/revision/margin_r11_fresh_20261124/PLAN.md", "",
         f"eligible weeks: {len(weeks)} of {5 * len(MAIN_SCENARIOS)}; selected eps per seed: {sel}"
         + ("; EXTRAPOLATION (eps > 0.03): " + str([s for s, e in sel.items() if e > 0.03]) if any(e > 0.03 for e in sel.values()) else ""), ""]
    res = {}
    for name, mfun in (("margin 0", lambda e: 0.0), ("rule E (eps-dependent 10%/50%)", rule_E),
                       ("rule U (uniform 50%)", lambda e: 0.50), ("uniform 10%", lambda e: 0.10)):
        ok, costs, fails = 0, [], []
        for w in weeks:
            d = test[w]
            mg = mfun(d[0.0]["eps"])
            r = d[mg]
            costs.append(r["cost"] / d[0.0]["cost"] - 1)
            if r["violating_window_rate"] <= 0.02 + 1e-12:
                ok += 1
            else:
                fails.append(f"{w[0]} {w[1]} eps {r['eps']}: {100 * r['violating_window_rate']:.2f}% at margin {int(100 * mg)}%")
        lo, hi = cp(ok, len(weeks))
        res[name] = dict(ok=ok, n=len(weeks), cp95=[lo, hi], cost_mean=float(np.mean(costs)), cost_min=float(min(costs)),
                         cost_max=float(max(costs)), fails=fails)
        L.append(f"{name}: {ok}/{len(weeks)} weeks meet 2% (95% Clopper-Pearson {lo:.0f}-{hi:.0f}%); cost of the margin mean "
                 f"{100 * np.mean(costs):+.1f}% (range {100 * min(costs):+.1f} to {100 * max(costs):+.1f}%)")
        L.append("   failures: " + ("; ".join(fails) if fails else "none"))
    e = res["rule E (eps-dependent 10%/50%)"]
    verdict = "PASS" if e["ok"] >= 18 and e["n"] == 20 else ("FAIL" if e["n"] == 20 else f"INCOMPLETE ({e['n']} of 20 weeks)")
    L += ["", f"prespecified criterion (rule E: >= 18 of 20 fresh weeks meet 2%): {verdict}"]
    val = sorted((r for r in rows if r["week"] == "val"), key=lambda r: (r["seed"], r["eps"]))
    L += ["", "validation-week event-level violating % by eps (selection input):"]
    for s in sorted({r["seed"] for r in val}):
        L.append(f"  {s}: " + ", ".join(f"{r['eps']:g}: {100 * r['violating_window_rate']:.2f}" for r in val if r["seed"] == s))
    with open(os.path.join(out, "result.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(out, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(results=res, selected_eps=sel, verdict=verdict), f, indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    {"check": lambda: check(out), "schedules": lambda: schedules(out, [int(x) for x in sys.argv[3:]] or list(FRESH)),
     "run": lambda: run(out, [int(s) for s in sys.argv[3:]] or list(FRESH)),
     "analyse": lambda: analyse(out)}[sys.argv[2]]()
