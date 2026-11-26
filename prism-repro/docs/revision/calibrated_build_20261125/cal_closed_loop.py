#!/usr/bin/env python3
"""Calibrated simulator build: regression checks R2-R4 and development groups A, B, D (RUN_PLAN.md). Development traces
101-105 only; seeds >= 106 refused. Runs from a prism-repro tree carrying candidate_exec_p2.patch with
scripts/revision/closed_loop_exploratory.py and closed_loop_confirmatory.py present. One group per call; resumable.
usage: python cal_closed_loop.py <out> <factors.json> --group=R|A|B|D [--workers=2]
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
MEAS = dict(exec_scaling="measured", exec_factor_measured=FAC)
CAL = dict(MEAS, exec_common_frac=0.998, init_max_s=10.0)
K_EPS = {101: 0.01, 102: 0.01, 103: 0.03, 104: 0.03, 105: 0.03}
DEV5 = (101, 102, 103, 104, 105)
FAMS_A = ("PRISM", "QuantProv_q90", "Reactive", "MemAdapt_q90")
FAMS_B = ("PRISM", "MemAdapt_q90")
SETS = {"LEG145": {}, "I145": dict(MEAS), "S145": dict(MEAS, exec_common_frac=1.0),
        "CAL145": dict(CAL), "CAL12": dict(CAL, deadline=12.0)}
for name, cfg in SETS.items():
    C.SETS[name] = dict(seeds=DEV5, scenarios=("stationary",), families=FAMS_A, cfg=cfg)
# diagnostic values below the lowest GRIDS_WIDE value, per grid (RUN_PLAN.md group D)
BELOW = {"QuantProv": [0.3, 0.2], "PRISM": [0.001], "Reactive": [0.25, 0.20]}


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


def tune(st, fams, ex):
    for s in DEV5:
        for fam in fams:
            p = os.path.join(OUT, "groups", st, f"group_{s}_{fam}.json")
            if os.path.exists(p):
                continue
            g = C.Group(st, s, fam, ("stationary",))
            while True:
                need = [q for q in g.grid + g.expansions if q not in g.val]
                for q, r in zip(need, run_tasks([task(st, s, fam, q, "val", "validation") for q in need], ex)):
                    g.val[q] = r
                kind, v = g.select()
                if kind == "expand":
                    g.expansions.append(v)
                    continue
                g.sel = v
                break
            g.tests["stationary"] = run_tasks([task(st, s, fam, g.sel, "test", "stationary")], ex)[0]
            rec = g.record("92e3e68+candidate_exec_p2.patch")
            rec["wide_bounds"] = [min(g.wide), max(g.wide)]
            rec["unresolved_edge"] = bool(g.sel in (min(g.wide), max(g.wide)))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            json.dump(rec, open(p, "w"), indent=1)
            log(f"group {st} {s} {fam}: selected {g.sel} expansions {g.expansions or '-'}"
                f"{' UNRESOLVED EDGE' if rec['unresolved_edge'] else ''}")


def main():
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(group=GROUP, driver_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                   exploratory_sha256=hashlib.sha256(open(X.__file__, "rb").read()).hexdigest(),
                   factors_sha256=hashlib.sha256(open(FACF, "rb").read()).hexdigest(), workers=WORKERS,
                   cfg_sha={k: C.cfg_sha(C.make_cfg(v)) for k, v in SETS.items()},
                   started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
              open(os.path.join(OUT, f"provenance_{GROUP}_{int(time.time())}.json"), "w"), indent=1)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        if GROUP == "R":
            run_tasks([task(st, s, "PRISM", K_EPS[s], "test", "stationary") for st in ("LEG145", "I145", "S145")
                       for s in DEV5], ex)
        elif GROUP == "A":
            tune("CAL145", FAMS_A, ex)
        elif GROUP == "B":
            tune("CAL12", FAMS_B, ex)
        elif GROUP == "D":
            from prism_repro.experiment import GRIDS_WIDE
            tasks = []
            for st in ("CAL145", "CAL12"):
                for p in sorted(__import__("glob").glob(os.path.join(OUT, "groups", st, "*.json"))):
                    g = json.load(open(p))
                    gname = C.FAMILIES[g["family"]][1]
                    if g["selected"] == min(GRIDS_WIDE[gname]):
                        tasks += [task(st, g["seed"], g["family"], q, "val", "validation") for q in BELOW[gname]]
            log(f"D: {len(tasks)} diagnostic validation weeks")
            run_tasks(tasks, ex)
        else:
            raise SystemExit("unknown group")
    log(f"{GROUP} done")


if __name__ == "__main__":
    main()
