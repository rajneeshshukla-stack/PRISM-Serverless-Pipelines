#!/usr/bin/env python3
"""P2 closed-loop sensitivity (RUN_PLAN.md): IND (rho 0) against SHR (rho 1), both with the per-size execution factors.
EXPLORATORY; development traces 101-105; seeds 106-130 refused. Runs from a prism-repro tree carrying
candidate_exec_p2.patch, with scripts/revision/closed_loop_exploratory.py and closed_loop_confirmatory.py present.
One group per call; resumable (existing week files are reused).
usage: python p2_closed_loop.py <out> <factors.json> --group=G0|G1|G2|G3 [--workers=2]
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
import closed_loop_exploratory as X  # noqa: E402

C = X.C
OUT, FACF = sys.argv[1], sys.argv[2]
OPTS = dict(a.split("=", 1) for a in sys.argv[3:] if a.startswith("--"))
GROUP, WORKERS = OPTS["--group"], int(OPTS.get("--workers", 2))
FAC = tuple((int(m), tuple(f)) for m, f in json.load(open(FACF))["exec_factor_measured"])
BASE = dict(exec_scaling="measured", exec_factor_measured=FAC)
K_EPS = {101: 0.01, 102: 0.01, 103: 0.03, 104: 0.03, 105: 0.03}       # closed_loop_kappa_20261124, arm A
QP_A = {101: 1.3, 102: 1.5, 103: 1.1, 104: 1.2, 105: 1.2}             # closed_loop_families_20261124, QuantProv-q90
DEV5, DEV3 = (101, 102, 103, 104, 105), (101, 102, 103)
SETS = {"I145": dict(BASE), "S145": dict(BASE, exec_common_frac=1.0),
        "I13": dict(BASE, deadline=13.0), "S13": dict(BASE, deadline=13.0, exec_common_frac=1.0)}
for name, cfg in SETS.items():
    C.SETS[name] = dict(seeds=DEV5, scenarios=("stationary",), families=("PRISM", "MemAdapt_q90"), cfg=cfg)


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    open(os.path.join(OUT, "run.log"), "a", encoding="utf-8", newline="\n").write(line + "\n")
    print(line, flush=True)


def want(t):
    return C.cfg_sha(C.make_cfg(C.SETS[t["set"]]["cfg"]))


def task(st, seed, fam, param, week, scen):
    if seed >= 106:
        raise SystemExit("seeds 106-130 are reserved")
    return dict(out=OUT, set=st, seed=seed, family=fam, param=param, week=week, scenario=scen)


def run_tasks(tasks, ex):
    todo = [t for t in tasks if C.load_week(OUT, t, want(t)) is None]
    futs = {ex.submit(X.week_task, t): t for t in todo}
    for f, t in futs.items():
        r = f.result()
        log(f"week {t['set']} {t['seed']} {t['family']} {t['week']} {t['param']}: cost {r['cost']:.1f}, "
            f"violating {100 * r['violating_window_rate']:.2f}%, >=2048 MB {100 * r['share_mem_ge_2048']:.1f}%")
    return [C.load_week(OUT, t, want(t)) for t in tasks]


def main():
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(group=GROUP, driver_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                   exploratory_sha256=hashlib.sha256(open(X.__file__, "rb").read()).hexdigest(),
                   factors_sha256=hashlib.sha256(open(FACF, "rb").read()).hexdigest(), workers=WORKERS,
                   started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
              open(os.path.join(OUT, f"provenance_{GROUP}_{int(time.time())}.json"), "w"), indent=1)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        if GROUP == "G0":
            run_tasks([task("I145", s, "PRISM", K_EPS[s], "test", "stationary") for s in DEV5], ex)
        elif GROUP == "G1":
            run_tasks([task("S145", s, "PRISM", K_EPS[s], "test", "stationary") for s in DEV5]
                      + [task(st, s, "MemAdapt_q90", QP_A[s], "test", "stationary") for st in ("I145", "S145") for s in DEV5], ex)
        elif GROUP == "G3":
            run_tasks([task("S13", s, fam, p, "test", "stationary") for s in DEV5
                       for fam, p in (("PRISM", 0.01), ("MemAdapt_q90", 0.6))], ex)
        elif GROUP == "G2":
            for st in ("I145", "S145"):
                for s in DEV3:
                    for fam in ("PRISM", "MemAdapt_q90"):
                        g = C.Group(st, s, fam, ("stationary",))
                        while True:
                            need = [p for p in g.grid + g.expansions if p not in g.val]
                            for p, r in zip(need, run_tasks([task(st, s, fam, p, "val", "validation") for p in need], ex)):
                                g.val[p] = r
                            kind, v = g.select()
                            if kind == "expand":
                                g.expansions.append(v)
                                continue
                            g.sel = v
                            break
                        g.tests["stationary"] = run_tasks([task(st, s, fam, g.sel, "test", "stationary")], ex)[0]
                        os.makedirs(os.path.join(OUT, "groups", st), exist_ok=True)
                        json.dump(g.record("3edc386+p2patch"), open(os.path.join(OUT, "groups", st, f"group_{s}_{fam}.json"), "w"), indent=1)
                        log(f"group {st} {s} {fam}: selected {g.sel} expansions {g.expansions or '-'}")
        else:
            raise SystemExit("unknown group")
    log(f"{GROUP} done")


if __name__ == "__main__":
    main()
