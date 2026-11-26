#!/usr/bin/env python3
"""Why does closed-loop kappa sit far above the fast simulator's? (R2.12, R5.M1, R2.2). DIAGNOSTIC, pre-calibration.

Per trace (seeds 101-105 x {stationary, new_spike}, held-out test week, PRISM eps = 0.02, GBM forecaster):
  F  fast simulator run: the cold-hit estimate kappa as PRISM sees it (clipped to [0.1, 1]), the share of epochs at
     the 0.1 floor, the same estimator without the floor, and the raw ratio cold starts / on-demand requests.
  O  the event-level simulator replaying F's own schedule (open loop): the same quantities from its telemetry. F and
     O share every decision, so any difference here is the simulators', not the controller's.
  C  the event-level closed loop: kappa as PRISM sees it, cost and violating windows against O.
Mechanism probes on one trace and one day (O's schedule): event-level runs with the keep-alive made unlimited, and
with initialisation made instantaneous, to see which part of the event model produces the extra cold starts; and
the fast simulator's own cold-start formula (D12-D13) evaluated on the event-level on-demand concurrency.

Usage: python kappa_gap.py <code_root> <out_dir> [--workers=N]  |  ... <out_dir> --analyse
"""
import dataclasses
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
SCEN = ("stationary", "new_spike")
SPEC = dict(family="PRISM", param=0.02)


def kappa_path(tel, cfg, pcfg, n_ep, clip):
    """PRISM's cold-hit update (policies.PRISM._update_kappa) over a telemetry, with a chosen clip."""
    kappa, cum, last, out = pcfg.kappa_prior, 0.0, -1, np.empty(n_ep)
    a = pcfg.kappa_alpha
    for k in range(n_ep):
        v = k * cfg.epoch_min - cfg.lag_min
        lo = last + 1
        if v >= lo and v >= 0:
            lo = max(lo, 0)
            od, cold = float(np.sum(tel.n_od[lo:v + 1])), float(np.sum(tel.cold[lo:v + 1]))
            cum += od
            if od > 0 and cum >= pcfg.kappa_min_overflow:
                kappa = float(np.clip((1 - a) * kappa + a * (cold / od), *clip))
            last = v
        out[k] = kappa
    return out


def stats_of(tel, cfg, pcfg, n_ep):
    k_clip = kappa_path(tel, cfg, pcfg, n_ep, pcfg.kappa_clip)
    k_free = kappa_path(tel, cfg, pcfg, n_ep, (0.0, 1.0))
    od, cold = np.asarray(tel.n_od, float), np.asarray(tel.cold, float)
    return dict(kappa_mean=float(k_clip.mean()), floor_share=float(np.mean(np.isclose(k_clip, pcfg.kappa_clip[0]))),
                kappa_unclipped_mean=float(k_free.mean()), od_total=float(od.sum()), cold_total=float(cold.sum()),
                ratio=float(cold.sum() / max(od.sum(), 1.0)),
                ratio_stage=[float(cold[:, s].sum() / max(od[:, s].sum(), 1.0)) for s in range(od.shape[1])],
                od_stage=[float(od[:, s].sum()) for s in range(od.shape[1])],
                cold_stage=[float(cold[:, s].sum()) for s in range(od.shape[1])])


def job(seed):
    from prism_repro.closed_loop import PolicyController
    from prism_repro.config import PipelineConfig, PrismConfig
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import WEEK_START, TraceBundle, make_policy
    from prism_repro.simulator import simulate
    cfg, pcfg = PipelineConfig(), PrismConfig()
    b = TraceBundle(seed, cfg, scenarios=SCEN)
    rows = []
    for sc in SCEN:
        t0 = time.time()
        fast = simulate(b.context(sc, "test"), make_policy(SPEC))
        n_ep = len(fast["raw"]["P_epoch"])
        counts = b.traces[sc]["counts"][WEEK_START["test"]:WEEK_START["test"] + 7 * 1440]
        dr = EventDraws(cfg, counts, seed, 3)
        op = simulate_events(cfg, dr, fast["raw"]["P_epoch"], fast["raw"]["mem_epoch"], want_telemetry=True)
        pol = make_policy(SPEC)
        cl = simulate_events(cfg, dr, controller=PolicyController(pol, b, sc), want_telemetry=True)
        row = dict(seed=seed, scenario=sc, n_requests=int(dr.n), n_epochs=n_ep,
                   F=stats_of(fast["telemetry"], cfg, pcfg, n_ep), O=stats_of(op["raw"]["telemetry"], cfg, pcfg, n_ep),
                   C=stats_of(cl["raw"]["telemetry"], cfg, pcfg, n_ep),
                   F_rec_floor_share=float(np.mean(np.isclose(fast["raw"]["kappa_epoch"], 0.1))),
                   C_rec_kappa_mean=float(pol.rec["kappa"].mean()),
                   cost=dict(F=float(fast["summary"]["cost"]), O=float(op["summary"]["cost"]), C=float(cl["summary"]["cost"])),
                   viol=dict(F=float(fast["summary"]["violating_window_rate"]),
                             O=float(op["summary"]["violating_window_rate"]),
                             C=float(cl["summary"]["violating_window_rate"])),
                   cold_start_ratio=dict(F=float(fast["summary"]["cold_start_ratio"]),
                                         O=float(op["summary"]["cold_start_ratio"]),
                                         C=float(cl["summary"]["cold_start_ratio"])),
                   overflow_share=dict(F=float(fast["summary"]["overflow_share"]),
                                       O=float(op["summary"]["overflow_share"]),
                                       C=float(cl["summary"]["overflow_share"])),
                   runtime_s=round(time.time() - t0, 1))
        if seed == SEEDS[0] and sc == "stationary":
            row["probes"] = probes(cfg, pcfg, b, counts, seed, fast)
        rows.append(row)
    return rows


def probes(cfg, pcfg, b, counts, seed, fast):
    """One day of O's schedule under variants of the event model, plus the fast formula on event concurrency."""
    from prism_repro.des import EventDraws, simulate_events
    D = 1440
    P, m = fast["raw"]["P_epoch"][:D // 5], fast["raw"]["mem_epoch"][:D // 5]
    out = {}
    for name, c in (("event model", cfg), ("keep-alive unlimited", cfg.with_(keepalive_min=10 ** 6)),
                    ("initialisation instantaneous", cfg.with_(init_mean_1024=1e-9))):
        dr = EventDraws(c, counts[:D], seed, 3)
        tel = simulate_events(c, dr, P, m, want_telemetry=True)["raw"]["telemetry"]
        out[name] = dict(od=float(tel.n_od.sum()), cold=float(tel.cold.sum()),
                         ratio=float(tel.cold.sum() / max(tel.n_od.sum(), 1.0)))
        if name == "event model":
            # the fast simulator's cold-start formula (D12-D13) on the event-level on-demand concurrency:
            # on-demand concurrency OD = (K - P)+, new environments = (OD - max OD of the previous keep-alive minutes)+
            OD = np.maximum(tel.K - tel.P, 0.0)
            ka = cfg.keepalive_min
            new = np.zeros_like(OD)
            for t in range(len(OD)):
                pool = OD[max(0, t - ka):t].max(0) if t > 0 else np.zeros(OD.shape[1])
                new[t] = np.maximum(OD[t] - pool, 0.0)
            cold_formula = np.minimum(new, tel.n_od)
            out["fast formula on event concurrency"] = dict(od=float(tel.n_od.sum()), cold=float(cold_formula.sum()),
                                                            ratio=float(cold_formula.sum() / max(tel.n_od.sum(), 1.0)))
    ft = fast["telemetry"]
    out["fast simulator (same day)"] = dict(od=float(ft.n_od[:D].sum()), cold=float(ft.cold[:D].sum()),
                                            ratio=float(ft.cold[:D].sum() / max(ft.n_od[:D].sum(), 1.0)))
    return out


def run(out, workers):
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows in ex.map(job, SEEDS):
            for r in rows:
                with open(os.path.join(out, f"rows_{r['seed']}_{r['scenario']}.json"), "w") as fh:
                    json.dump(r, fh, indent=1)
                print(r["seed"], r["scenario"], "done", r["runtime_s"], "s", flush=True)
    import scipy
    import sklearn
    json.dump(dict(platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                   scipy=scipy.__version__, sklearn=sklearn.__version__), open(os.path.join(out, "environment.json"), "w"))


def analyse(out):
    rows = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "rows_*.json")))]
    env = json.load(open(os.path.join(out, "environment.json"))) if os.path.exists(os.path.join(out, "environment.json")) else {}
    print(f"DIAGNOSTIC, pre-calibration. {len(rows)} traces (held-out test weeks), PRISM eps 0.02, GBM. Environment: {env}")
    print("\nkappa as PRISM sees it (clipped [0.1, 1]) | share of epochs at the floor | same estimator unclipped | "
          "raw cold starts / on-demand requests (whole week, all stages)")
    for key, lab in (("F", "fast simulator"), ("O", "event level, F's schedule"), ("C", "event level, closed loop")):
        g = lambda f: np.array([r[key][f] for r in rows])  # noqa: E731
        print(f"  {lab:27s} kappa {g('kappa_mean').mean():.3f} [{g('kappa_mean').min():.3f}-{g('kappa_mean').max():.3f}] | "
              f"floor {100 * g('floor_share').mean():5.1f}% | unclipped {g('kappa_unclipped_mean').mean():.3f} "
              f"[{g('kappa_unclipped_mean').min():.3f}-{g('kappa_unclipped_mean').max():.3f}] | raw ratio "
              f"{g('ratio').mean():.4f} [{g('ratio').min():.4f}-{g('ratio').max():.4f}]")
    print("\nSame schedule, fast vs event level (O / F), mean over traces [range]:")
    for f, lab in (("od_total", "on-demand requests"), ("cold_total", "cold starts"), ("ratio", "cold per on-demand request")):
        q = np.array([r["O"][f] / max(r["F"][f], 1e-12) for r in rows])
        print(f"  {lab:28s} x{q.mean():.2f} [{q.min():.2f}-{q.max():.2f}]   (sample: F {np.mean([r['F'][f] for r in rows]):.4g}, "
              f"O {np.mean([r['O'][f] for r in rows]):.4g} per trace-week)")
    S = len(rows[0]["F"]["ratio_stage"])
    for s in range(S):
        qf = np.mean([r["F"]["ratio_stage"][s] for r in rows])
        qo = np.mean([r["O"]["ratio_stage"][s] for r in rows])
        print(f"  stage {s + 1}: cold per on-demand request F {qf:.4f}, O {qo:.4f} (x{qo / max(qf, 1e-12):.1f})")
    print("\nWhole-week cold-start ratio (cold starts / stage executions), violating windows, cost:")
    for key, lab in (("F", "fast"), ("O", "event, F's schedule"), ("C", "event, closed loop")):
        print(f"  {lab:20s} cold-start ratio {np.mean([r['cold_start_ratio'][key] for r in rows]):.5f} | overflow share "
              f"{np.mean([r['overflow_share'][key] for r in rows]):.4f} | violating windows "
              f"{100 * np.mean([r['viol'][key] for r in rows]):.2f}% | cost {np.mean([r['cost'][key] for r in rows]):.1f}")
    d = np.array([100 * (r["cost"]["C"] / r["cost"]["O"] - 1) for r in rows])
    dv = np.array([100 * (r["viol"]["C"] - r["viol"]["O"]) for r in rows])
    print(f"  closed loop vs open-loop replay: cost {d.mean():+.1f}% [{d.min():+.1f}, {d.max():+.1f}], "
          f"violating windows {dv.mean():+.2f} points [{dv.min():+.2f}, {dv.max():+.2f}]")
    print("  check (a): closed-loop kappa recorded by PRISM equals the update recomputed from the final event telemetry:",
          all(abs(r["C_rec_kappa_mean"] - r["C"]["kappa_mean"]) < 1e-12 for r in rows))
    pr = [r["probes"] for r in rows if "probes" in r]
    if pr:
        print("\nMechanism probes (seed 101, stationary, first day of the test week, F's schedule):")
        for k, v in pr[0].items():
            print(f"  {k:36s} on-demand {v['od']:9.0f} | cold {v['cold']:8.0f} | cold per on-demand {v['ratio']:.4f}")


if __name__ == "__main__":
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if "--analyse" in sys.argv:
        analyse(out)
    else:
        w = [int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")]
        run(out, w[0] if w else 3)
