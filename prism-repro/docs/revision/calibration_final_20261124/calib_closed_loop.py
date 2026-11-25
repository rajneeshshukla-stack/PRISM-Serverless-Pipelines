#!/usr/bin/env python3
"""Bounded closed-loop check: legacy Eq. (2) against the per-size execution model (RUN_PLAN.md, 24 Nov 2026).
EXPLORATORY; development traces 101-105; seeds 106-130 are refused. Runs from a prism-repro tree that carries the
opt-in patch (exec_scaling = "measured"), with scripts/revision/closed_loop_exploratory.py and
closed_loop_confirmatory.py present. Resumable: each week is a JSON (+ .npz) written atomically; existing weeks are reused.

usage: python calib_closed_loop.py <out> <factors.json> [--workers=2] [--only=E14,F13,R13]
"""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "revision"))
import closed_loop_exploratory as X  # noqa: E402  (registers MemAdapt etc., patches the week task to save arrays)

C = X.C
OUT, FACF = sys.argv[1], sys.argv[2]
OPTS = dict(a.split("=", 1) for a in sys.argv[3:] if a.startswith("--"))
WORKERS = int(OPTS.get("--workers", 2))
ONLY = OPTS.get("--only", "E14,F13,R13").split(",")
FAC = tuple((int(m), tuple(f)) for m, f in json.load(open(FACF))["exec_factor_measured"])
MEAS = dict(exec_scaling="measured", exec_factor_measured=FAC)
K_EPS = {101: 0.01, 102: 0.01, 103: 0.03, 104: 0.03, 105: 0.03}   # set K arm A selections (closed_loop_kappa_20261124)
DEV5, DEV3 = (101, 102, 103, 104, 105), (101, 102, 103)
for name, cfg in {"E14_legacy": {}, "E14_meas": MEAS, "C13_legacy": {"deadline": 13.0},
                  "C13_meas": dict(deadline=13.0, **MEAS)}.items():
    C.SETS[name] = dict(seeds=DEV5, scenarios=("stationary",), families=("PRISM", "MemAdapt_q90"), cfg=cfg)


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    open(os.path.join(OUT, "run.log"), "a", encoding="utf-8", newline="\n").write(line + "\n")
    print(line, flush=True)


def want(t):
    return C.cfg_sha(C.make_cfg(C.SETS[t["set"]]["cfg"]))


def run_tasks(tasks, ex):
    """Run tasks not already saved; return rows in task order."""
    todo = [t for t in tasks if C.load_week(OUT, t, want(t)) is None]
    futs = {ex.submit(X.week_task, t): t for t in todo}
    for f, t in futs.items():
        r = f.result()
        log(f"week {t['set']} {t['seed']} {t['family']} {t['week']} {t['scenario']} {t['param']}: cost {r['cost']:.1f}, "
            f"violating {100 * r['violating_window_rate']:.2f}%, >=2048 MB {100 * r['share_mem_ge_2048']:.1f}%")
    return [C.load_week(OUT, t, want(t)) for t in tasks]


def task(st, seed, fam, param, week, scen):
    if seed >= 106:
        raise SystemExit("seeds 106-130 are reserved")
    return dict(out=OUT, set=st, seed=seed, family=fam, param=param, week=week, scenario=scen)


def main():
    os.makedirs(OUT, exist_ok=True)
    prov = dict(cwd_tree=os.path.basename(ROOT.rstrip("/")), driver_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                exploratory_sha256=hashlib.sha256(open(X.__file__, "rb").read()).hexdigest(),
                factors_sha256=hashlib.sha256(open(FACF, "rb").read()).hexdigest(), workers=WORKERS, only=ONLY,
                started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(prov, open(os.path.join(OUT, f"provenance_{int(time.time())}.json"), "w"), indent=1)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        if "E14" in ONLY:
            run_tasks([task(st, s, "PRISM", K_EPS[s], "test", "stationary") for st in ("E14_legacy", "E14_meas") for s in DEV5], ex)
            log("E14 done")
        if "F13" in ONLY:
            run_tasks([task(st, s, fam, p, "test", "stationary") for st in ("C13_legacy", "C13_meas") for s in DEV5
                       for fam, p in (("PRISM", 0.01), ("MemAdapt_q90", 0.6))], ex)
            log("F13 done")
        if "R13" in ONLY:
            groups = []
            for st in ("C13_legacy", "C13_meas"):
                for s in DEV3:
                    for fam in ("PRISM", "MemAdapt_q90"):
                        g = C.Group(st, s, fam, ("stationary",))
                        while True:
                            need = [p for p in g.grid + g.expansions if p not in g.val]
                            rows = run_tasks([task(st, s, fam, p, "val", "validation") for p in need], ex)
                            for p, r in zip(need, rows):
                                g.val[p] = r
                            kind, v = g.select()
                            if kind == "expand":
                                g.expansions.append(v)
                                continue
                            g.sel = v
                            break
                        g.tests["stationary"] = run_tasks([task(st, s, fam, g.sel, "test", "stationary")], ex)[0]
                        rec = g.record("3edc386+patch")
                        os.makedirs(os.path.join(OUT, "groups", st), exist_ok=True)
                        json.dump(rec, open(os.path.join(OUT, "groups", st, f"group_{s}_{fam}.json"), "w"), indent=1)
                        log(f"group {st} {s} {fam}: selected {g.sel} expansions {g.expansions or '-'}")
            log("R13 done")
    log("end")


if __name__ == "__main__":
    main()
