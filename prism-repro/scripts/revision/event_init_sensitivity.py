#!/usr/bin/env python3
"""How much does the event-level week's cold start matter? (R2.2 initialisation protocol). SENSITIVITY, pre-calibration.

The event-level simulator starts the week with provisioned capacity ready and no warm on-demand environment; the
fast simulator warms its on-demand pool from the ten pre-week minutes (D24). This check replays stored E1 test-week
schedules (open loop, as E9) over the first day of the week twice: as the simulator runs it (cold start), and after a
60-minute event-level warm-up in which the trace's own last pre-week hour is routed under the week's first-epoch
decision; the week's requests keep identical draws in both runs. Only the week's minutes are compared: violating 15-minute windows of the first day, cold starts and their
share in the first hour. Seeds 101-103 x {stationary, new_spike} x {PRISM-0.02, QuantProv_q90-1.0, Reactive-0.6}.

Usage: python event_init_sensitivity.py <code_root> <out.json>
"""
import json
import os
import sys

import numpy as np

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, simulate_events  # noqa: E402
from prism_repro.workload import generate_trace  # noqa: E402

LABELS = ("PRISM-0.02", "QuantProv_q90-1.0", "Reactive-0.6")
DAY, WARM, WS = 1440, 60, 21 * 1440


def paired_draws(cfg, c, seed, pre):
    """The week's requests keep exactly the draws of the cold-start run; the warm-up hour gets its own."""
    week = EventDraws(cfg, c[WS:WS + DAY], seed, 3)
    if not pre:
        return week
    warm = EventDraws(cfg, c[WS - pre:WS], seed, 30)
    dr = EventDraws.__new__(EventDraws)
    dr.counts = np.concatenate([warm.counts, week.counts])
    dr.minute = np.concatenate([warm.minute, week.minute + pre])
    dr.arrival = np.concatenate([warm.arrival, week.arrival + pre * 60.0])
    for f in ("ex", "ov", "init"):
        setattr(dr, f, np.concatenate([getattr(warm, f), getattr(week, f)], axis=1))
    dr.n, dr.n_min = len(dr.arrival), len(dr.counts)
    return dr


def main():
    cfg = PipelineConfig()
    E, w = cfg.epoch_min, cfg.window_min
    rows = []
    for seed in (101, 102, 103):
        z = np.load(os.path.join(ROOT, "results", "raw", "E1", f"arrays_seed{seed}.npz"))
        for sc in ("stationary", "new_spike"):
            c = generate_trace(seed, sc)["counts"]
            for lab in LABELS:
                key = f"E1|{seed}|{sc}|test|{lab}|"
                P, m = z[key + "::P_epoch"][:DAY // E], z[key + "::mem_epoch"][:DAY // E]
                res = {}
                for mode, pre in (("cold start", 0), ("60-minute warm-up", WARM)):
                    dr = paired_draws(cfg, c, seed, pre)
                    Pw = np.vstack([np.repeat(P[:1], pre // E, axis=0), P]) if pre else P
                    mw = np.concatenate([np.repeat(m[:1], pre // E), m]) if pre else m
                    out = simulate_events(cfg, dr, Pw, mw, want_telemetry=True)
                    att = out["raw"]["window_attainment"][pre // w:]          # the week's windows only
                    tel = out["raw"]["telemetry"]
                    cold = tel.cold[pre:]
                    res[mode] = dict(violating_windows=int(np.sum(att < 1 - cfg.sla_eps)), windows=int(len(att)),
                                     cold_day=float(cold.sum()), cold_first_hour=float(cold[:60].sum()))
                rows.append(dict(seed=seed, scenario=sc, label=lab, **res))
                print(seed, sc, lab, res, flush=True)
    json.dump(rows, open(OUT, "w"), indent=1)
    dv = [r["cold start"]["violating_windows"] - r["60-minute warm-up"]["violating_windows"] for r in rows]
    dc = [r["cold start"]["cold_first_hour"] - r["60-minute warm-up"]["cold_first_hour"] for r in rows]
    print(f"\nSUMMARY ({len(rows)} trace-policy days): cold start minus warm-up, violating windows in day 1: mean {np.mean(dv):+.2f} "
          f"[{min(dv):+d}, {max(dv):+d}] of 96; on a 672-window week {100 * np.mean(dv) / 672:+.3f} points; "
          f"cold starts in the first hour {np.mean(dc):+.0f} [{min(dc):+.0f}, {max(dc):+.0f}]")


if __name__ == "__main__":
    main()
