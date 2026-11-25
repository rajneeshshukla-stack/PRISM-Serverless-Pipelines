#!/usr/bin/env python3
"""EXPLORATORY closed-loop event-level runs on development traces 101-105 (PRE-CALIBRATION), outside the frozen C1-C3
protocol: the kappa-floor study (R2.12(b), R5.M5; docs/revision/closed_loop_kappa_20261124/PLAN.md) and the missing
closed-loop comparator families (R5.M1(e), R2.2(b); docs/revision/closed_loop_families_20261124/PLAN.md).

It imports scripts/revision/closed_loop_confirmatory.py (the C1-C3 driver) unchanged and reuses its bundles, week task,
validation selection with the prespecified edge expansion, checkpointing and clean-code guard. It only adds families
and sets (on development seeds) and wraps the week task to also save per-epoch kappa, provisioned levels and memory
(<week file>.npz). Linux (fork start method) is assumed, so the patched globals reach the worker processes.

Usage (from prism-repro/ of a clean checkout):
  python scripts/revision/closed_loop_exploratory.py run <out> --sets=K [--workers=4] [--seeds=101-105]
  python scripts/revision/closed_loop_exploratory.py sens <out> [--workers=4]    # kappa sensitivity arms at A's eps
  python scripts/revision/closed_loop_exploratory.py ondemand <out> [--workers=4] # OnDemand test weeks (no tuning)
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import closed_loop_confirmatory as C  # noqa: E402

DEV = (101, 102, 103, 104, 105)
C.FAMILIES.update({
    "PRISM_kfloor0001": (dict(family="PRISM", prism={"kappa_clip": (0.001, 1.0)}), "PRISM"),
    "PRISM_kfrozen01": (dict(family="PRISM", prism={"kappa_clip": (0.1, 0.1)}), "PRISM"),
    "PredHead": (dict(family="PredHead"), "PredHead"),
    "PredHead+hyst": (dict(family="PredHead", hyst=True), "PredHead"),
    "QuantProv_q99": (dict(family="QuantProv", tau_idx=3), "QuantProv"),
    "Static": (dict(family="Static"), "Static"),
    "Scheduled": (dict(family="Scheduled"), "Scheduled"),
})
C.SETS.update({
    # kappa study: A = PRISM (default floor 0.1), B = floor 0.001, F = kappa frozen at 0.1
    "K": dict(seeds=DEV, scenarios=C.MAIN, families=("PRISM", "PRISM_kfloor0001", "PRISM_kfrozen01"), cfg={}),
    # comparators: R5.M1(e) narrower option first, then R2.2(b)'s remaining families
    "CMPe": dict(seeds=DEV, scenarios=C.MAIN, families=("QuantProv_q90", "Reactive", "PredHead+hyst"), cfg={}),   # PRISM: reuse set K's arm A
    "CMPb": dict(seeds=DEV, scenarios=C.MAIN, families=("PredHead", "QuantProv_q99", "Static", "Scheduled"), cfg={}),
})
SENS = ("PRISM_kfloor0001", "PRISM_kfrozen01")

_orig_week_task = C.week_task


def week_task(t):
    """The C1-C3 week task, verbatim (re-implemented here only to keep the policy object), plus per-epoch arrays."""
    import hashlib
    from prism_repro.closed_loop import PolicyController
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import WEEK_START, make_policy
    S = C.SETS[t["set"]]
    cfg, b = C._bundle(t["seed"], S["cfg"], t["out"])
    sc = b.scenarios[0] if t["week"] == "val" else t["scenario"]
    ws = WEEK_START[t["week"]]
    counts = b.traces[sc]["counts"][ws:ws + 7 * 1440]
    dr = EventDraws(cfg, counts, b.seed, 2 if t["week"] == "val" else 3)
    spec, _ = C.FAMILIES[t["family"]]
    pol = make_policy(dict(spec, param=t["param"]))
    t0 = time.time()
    res = simulate_events(cfg, dr, controller=PolicyController(pol, b, sc, week=t["week"]))
    s = res["summary"]
    me = res["raw"]["mem_epoch"]
    row = dict(week=t["week"], param=t["param"], runtime_s=round(time.time() - t0, 1), n_requests=int(dr.n),
               share_mem_ge_2048=float(np.mean(me >= 2048)), **{k: float(s[k]) for k in C.KEYS})
    arrays = dict(P_epoch=np.asarray(res["raw"]["P_epoch"], np.int32), mem_epoch=np.asarray(me, np.int32))
    if hasattr(pol, "rec"):
        kap = np.asarray(pol.rec["kappa"], float)
        row["kappa_mean"] = float(kap.mean())
        row["infeasible_share"] = float(1 - pol.rec["feasible"].mean())
        lo = float(pol.pcfg.kappa_clip[0])
        row["kappa_floor"] = lo
        row["kappa_at_or_below_0p1_share"] = float(np.mean(kap <= 0.1 + 1e-12))
        row["kappa_at_floor_share"] = float(np.mean(kap <= lo + 1e-12))
        row["kappa_p05"], row["kappa_p95"] = (float(x) for x in np.quantile(kap, [0.05, 0.95]))
        arrays["kappa_epoch"] = kap.astype(np.float32)
    row["mean_provisioned"] = float(np.asarray(res["raw"]["P_epoch"], float).sum(1).mean())
    row.update(scenario=t["scenario"], seed=t["seed"], family=t["family"], set=t["set"], cfg_sha=C.cfg_sha(cfg),
               counts_sha256=hashlib.sha256(np.ascontiguousarray(counts, dtype="<i8").tobytes()).hexdigest(),
               pid=os.getpid(), finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    p = C.week_file(t["out"], t)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    np.savez_compressed(p[:-5] + ".npz.tmp.npz", **arrays)
    os.replace(p[:-5] + ".npz.tmp.npz", p[:-5] + ".npz")
    tmp = p + f".tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(row, fh, indent=1)
    os.replace(tmp, p)
    return row


C.week_task = week_task


def sens(out, workers):
    """Sensitivity arms: B and F on the test weeks at A's (PRISM's) validation-selected eps, per trace."""
    tasks = []
    for seed in DEV:
        gp = os.path.join(out, "groups", "K", f"group_{seed}_PRISM.json")
        sel = json.load(open(gp, encoding="utf-8"))["selected"]
        for fam in SENS:
            for sc in C.MAIN:
                t = dict(out=out, set="K", seed=seed, family=fam, param=sel, week="test", scenario=sc)
                if C.load_week(out, t, C.cfg_sha(C.make_cfg({}))) is None:
                    tasks.append(t)
    print(f"sensitivity tasks to run: {len(tasks)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        fs = {ex.submit(week_task, t): t for t in tasks}
        for f in as_completed(fs):
            t = fs[f]
            r = f.result()
            print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} sens {t['seed']} {t['family']} {t['scenario']} "
                  f"{t['param']}: cost {r['cost']:.1f}, violating {100 * r['violating_window_rate']:.2f}%", flush=True)
    return 0


def ondemand(out, workers):
    """OnDemand (no provisioning, no parameter, no feedback): one event-level week per trace and test scenario."""
    C.FAMILIES.setdefault("OnDemand", (dict(family="OnDemand"), None))
    C.SETS.setdefault("OD", dict(seeds=DEV, scenarios=C.MAIN, families=("OnDemand",), cfg={}))
    tasks = [dict(out=out, set="OD", seed=s, family="OnDemand", param=None, week="test", scenario=sc)
             for s in DEV for sc in C.MAIN]
    tasks = [t for t in tasks if C.load_week(out, t, C.cfg_sha(C.make_cfg({}))) is None]
    print(f"OnDemand tasks to run: {len(tasks)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        fs = {ex.submit(week_task, t): t for t in tasks}
        for f in as_completed(fs):
            t, r = fs[f], f.result()
            print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} OnDemand {t['seed']} {t['scenario']}: "
                  f"cost {r['cost']:.1f}, violating {100 * r['violating_window_rate']:.2f}%", flush=True)
    return 0


if __name__ == "__main__":
    cmd, out = sys.argv[1], sys.argv[2]
    opts = dict(a.split("=", 1) for a in sys.argv[3:] if a.startswith("--"))
    workers = int(opts.get("--workers", 4))
    if cmd == "run":
        seeds = C._seeds(opts["--seeds"]) if "--seeds" in opts else None
        if seeds and any(s >= 106 for s in seeds):
            raise SystemExit("confirmatory seeds 106-130 are reserved; this driver runs development traces only")
        sys.exit(C.run(out, opts["--sets"].split(","), workers, seeds))
    elif cmd == "sens":
        sys.exit(sens(out, workers))
    elif cmd == "ondemand":
        sys.exit(ondemand(out, workers))
    else:
        raise SystemExit(__doc__)
