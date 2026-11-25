#!/usr/bin/env python3
"""R1.1(b) follow-up: rule E's 50% branch on fresh traces (docs/revision/margin_r11_branch50_20261124/PLAN.md).
Reuses margin_fresh_r11.py (unchanged) for schedules, replays, rule E and intervals. EXPLORATORY, open loop,
pre-calibration. Resumable: every replay is appended as it finishes.

stage 1 (Linux, v1-submitted tree, as before):
  PRISM_ROOT=<v1 tree>/prism-repro python scripts/revision/margin_branch50_r11.py <out> sched_val <seed> [...]
  PRISM_ROOT=<v1 tree>/prism-repro python scripts/revision/margin_branch50_r11.py <out> sched_test <seed> <eps>
stage 2 (this tree):
  python scripts/revision/margin_branch50_r11.py <out> screen        # ascending 136..165, stops at 5 eligible
  python scripts/revision/margin_branch50_r11.py <out> run           # eligible seeds with test schedules
  python scripts/revision/margin_branch50_r11.py <out> analyse
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import margin_fresh_r11 as M  # noqa: E402  (locked script, unchanged)

SEEDS = tuple(range(136, 166))
MAX_ELIGIBLE = 5
MARGINS = (0.0, 0.10, 0.50)
HI = (0.03, 0.05, 0.08)


def _jl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def sched_val(out, seeds):
    from prism_repro.experiment import TraceBundle
    for seed in seeds:
        p = os.path.join(out, f"sched_val_seed{seed}.npz")
        if os.path.exists(p):
            continue
        t, b, arr = time.time(), TraceBundle(seed, M.CFG), {}
        for eps in M.GRIDS["PRISM"]:
            P, m, _ = M.schedule(b, "stationary", "val", eps)
            arr[f"val|stationary|{eps:g}::P"], arr[f"val|stationary|{eps:g}::m"] = P, m
        np.savez_compressed(p + ".tmp.npz", **arr)
        os.replace(p + ".tmp.npz", p)
        print(f"[{seed}] validation schedules in {time.time() - t:.0f}s", flush=True)


def sched_test(out, seed, eps):
    from prism_repro.experiment import TraceBundle
    p = os.path.join(out, f"sched_test_seed{seed}.npz")
    if os.path.exists(p):
        return
    t, b, arr = time.time(), TraceBundle(seed, M.CFG), {}
    for sc in M.MAIN_SCENARIOS:
        P, m, _ = M.schedule(b, sc, "test", eps)
        arr[f"test|{sc}|{eps:g}::P"], arr[f"test|{sc}|{eps:g}::m"] = P, m
    np.savez_compressed(p + ".tmp.npz", **arr)
    os.replace(p + ".tmp.npz", p)
    print(f"[{seed}] test schedules at eps {eps} in {time.time() - t:.0f}s", flush=True)


def screen(out):
    from prism_repro.des import EventDraws
    rows_p, log_p = os.path.join(out, "screen_rows.jsonl"), os.path.join(out, "search_log.jsonl")
    done = {r["key"]: r for r in _jl(rows_p)}
    logged = {r["seed"]: r for r in _jl(log_p)}
    for seed in SEEDS:
        if sum(1 for r in logged.values() if r["eligible"]) >= MAX_ELIGIBLE:
            print(f"stop: {MAX_ELIGIBLE} eligible traces found", flush=True)
            return
        if seed in logged:
            continue
        sp = os.path.join(out, f"sched_val_seed{seed}.npz")
        if not os.path.exists(sp):
            print(f"[{seed}] waiting for stage-1 validation schedules; stopping here (rerun screen to continue)", flush=True)
            return
        S = np.load(sp)
        vc = M.generate_trace(seed, "stationary")["counts"][14 * 1440:21 * 1440]
        vdr = EventDraws(M.CFG, vc, seed, 2)

        def val(eps):
            key = f"{seed}|val|{eps:g}"
            if key not in done:
                r = dict(key=key, seed=seed, week="val", eps=eps,
                         **M.replay(vdr, S[f"val|stationary|{eps:g}::P"], S[f"val|stationary|{eps:g}::m"], 0.0))
                with open(rows_p, "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(r) + "\n")
                done[key] = r
                print(f"[{seed}] val eps {eps:g}: {100 * r['violating_window_rate']:.3f}% ({r['runtime_s']:.0f}s)", flush=True)
            return done[key]

        ok = lambda r: r["violating_window_rate"] <= 0.02 + 1e-12  # noqa: E731
        hi = [val(e) for e in HI]
        if any(ok(r) for r in hi):
            allr, route = hi + [val(e) for e in (0.005, 0.01, 0.02)], "high meets: all six"
        else:
            lo = val(0.005)
            if ok(lo):
                allr, route = None, "no high meets; 0.005 meets -> ineligible"
            else:
                allr, route = hi + [lo, val(0.01), val(0.02)], "nothing meets so far: all six (fallback)"
        if allr is None:
            sel_eps, eligible = None, False
        else:
            sel = M.select_by_rule([dict(r, spec=dict(family="PRISM", param=r["eps"])) for r in allr])
            sel_eps, eligible = sel["eps"], sel["eps"] >= 0.03 - 1e-12
        entry = dict(seed=seed, route=route, replays=len([k for k in done if k.startswith(f"{seed}|")]),
                     selected_eps=sel_eps, eligible=bool(eligible),
                     val_violating={f"{k.split('|')[2]}": done[k]["violating_window_rate"] for k in done if k.startswith(f"{seed}|")})
        with open(log_p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry) + "\n")
        logged[seed] = entry
        print(f"[{seed}] {route}; selected {sel_eps}; eligible {eligible}", flush=True)
    print("search bound reached (seed 165)", flush=True)


def run(out):
    from prism_repro.des import EventDraws
    p = os.path.join(out, "test_rows.jsonl")
    done = {r["key"] for r in _jl(p)}
    for e in _jl(os.path.join(out, "search_log.jsonl")):
        if not e["eligible"]:
            continue
        seed, eps = e["seed"], e["selected_eps"]
        S = np.load(os.path.join(out, f"sched_test_seed{seed}.npz"))
        for sc in M.MAIN_SCENARIOS:
            tc = M.generate_trace(seed, sc)["counts"][21 * 1440:28 * 1440]
            tdr = None
            for mg in MARGINS:
                key = f"{seed}|test|{sc}|{eps:g}|{mg:g}"
                if key in done:
                    continue
                tdr = tdr or EventDraws(M.CFG, tc, seed, 3)
                r = dict(key=key, seed=seed, scenario=sc, eps=eps, margin=mg, rule_E_margin=M.rule_E(eps),
                         **M.replay(tdr, S[f"test|{sc}|{eps:g}::P"], S[f"test|{sc}|{eps:g}::m"], mg))
                with open(p, "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(r) + "\n")
                done.add(key)
                print(f"[{seed}] {sc} margin {mg:g}: {100 * r['violating_window_rate']:.2f}% cost {r['cost']:.0f}", flush=True)


def analyse(out):
    from scipy import stats
    log = _jl(os.path.join(out, "search_log.jsonl"))
    elig = [e for e in log if e["eligible"]]
    T = {}
    for r in _jl(os.path.join(out, "test_rows.jsonl")):
        T.setdefault(r["seed"], {}).setdefault(r["scenario"], {})[r["margin"]] = r
    L = ["R1.1(b) rule E 50% branch on fresh traces. EXPLORATORY, PRE-CALIBRATION, OPEN LOOP, event level. "
         "Plan: docs/revision/margin_r11_branch50_20261124/PLAN.md", "",
         f"search: {len(log)} seeds screened ({log[0]['seed'] if log else '-'}-{log[-1]['seed'] if log else '-'}), "
         f"{sum(e['replays'] for e in log)} validation replays; eligible (selected eps >= 0.03): {len(elig)}"]
    for e in log:
        L.append(f"  {e['seed']}: selected {e['selected_eps']}, eligible {e['eligible']} ({e['route']}; {e['replays']} replays)")
    res = dict(search=log, eligible=[e["seed"] for e in elig])
    complete = [s for s in (e["seed"] for e in elig) if s in T and all(set(T[s].get(sc, {})) == set(MARGINS)
                                                                        for sc in M.MAIN_SCENARIOS)]
    if len(elig) < 3:
        verdict = f"INSUFFICIENT ({len(elig)} eligible traces < 3): branch left unvalidated"
    elif len(complete) < len(elig):
        verdict = f"INCOMPLETE ({len(complete)} of {len(elig)} eligible traces replayed)"
    else:
        verdict = None
    if complete:
        n = 4 * len(complete)
        L.append("")
        for mg in MARGINS:
            met = [T[s][sc][mg]["violating_window_rate"] <= 0.02 + 1e-12 for s in complete for sc in M.MAIN_SCENARIOS]
            tr = [all(T[s][sc][mg]["violating_window_rate"] <= 0.02 + 1e-12 for sc in M.MAIN_SCENARIOS) for s in complete]
            k, kt = sum(met), sum(tr)
            ci = M.cp(k, n)
            cit = M.cp(kt, len(complete))
            cost = [np.mean([T[s][sc][mg]["cost"] / T[s][sc][0.0]["cost"] - 1 for sc in M.MAIN_SCENARIOS]) for s in complete]
            tci = (np.mean(cost) + stats.t.ppf([.025, .975], len(cost) - 1) * np.std(cost, ddof=1) / np.sqrt(len(cost))
                   if len(cost) >= 3 and mg else None)
            fails = [f"{s} {sc}: {100 * T[s][sc][mg]['violating_window_rate']:.2f}%" for s in complete for sc in M.MAIN_SCENARIOS
                     if T[s][sc][mg]["violating_window_rate"] > 0.02 + 1e-12]
            L.append(f"margin {int(100 * mg)}%: weeks {k}/{n} meet 2% (CP {ci[0]:.0f}-{ci[1]:.0f}%); traces all four weeks "
                     f"{kt}/{len(complete)} (CP {cit[0]:.0f}-{cit[1]:.0f}%); paired cost {100 * np.mean(cost):+.2f}%"
                     + (f" (t95 over traces {100 * tci[0]:+.2f} to {100 * tci[1]:+.2f}%)" if tci is not None else ""))
            L.append("   violating % by trace: " + "; ".join(f"{s}: " + ", ".join(f"{100 * T[s][sc][mg]['violating_window_rate']:.2f}"
                                                                          for sc in M.MAIN_SCENARIOS) for s in complete))
            L.append("   failures: " + ("; ".join(fails) if fails else "none"))
            res[f"margin_{mg:g}"] = dict(weeks_met=k, weeks=n, traces_met=kt, traces=len(complete), cost_mean=float(np.mean(cost)),
                                         cost_t95=[float(x) for x in tci] if tci is not None else None, fails=fails)
        if verdict is None:
            need = int(np.ceil(0.9 * n))
            verdict = ("PASS" if res["margin_0.5"]["weeks_met"] >= need else "FAIL") + f" (50% margin: {res['margin_0.5']['weeks_met']} of {n}; needs {need})"
    L += ["", f"prespecified criterion: {verdict}"]
    res["verdict"] = verdict
    with open(os.path.join(out, "result.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(out, "result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    out, mode = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if mode == "sched_val":
        sched_val(out, [int(x) for x in sys.argv[3:]] or list(SEEDS))
    elif mode == "sched_test":
        sched_test(out, int(sys.argv[3]), float(sys.argv[4]))
    else:
        {"screen": screen, "run": run, "analyse": analyse}[mode](out)
