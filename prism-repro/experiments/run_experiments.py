#!/usr/bin/env python3
"""Run the pre-registered experiments (EVALUATION_PROTOCOL.md). SIMULATION ONLY.

Usage:
  python experiments/run_experiments.py --exp E1 --seeds 101 102 103 104 105
  python experiments/run_experiments.py --exp E1 --seeds 7 --quick   # smoke test

Outputs: results/raw/<EXP>/rows.jsonl (one JSON row per run, with provenance) and
results/raw/<EXP>/arrays_seed<seed>.npz (window attainment, schedules, ...).
Resumable at seed granularity: a seed whose arrays file exists is skipped.
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from prism_repro.config import PipelineConfig, PrismConfig  # noqa: E402
from prism_repro.experiment import GRIDS, TraceBundle, make_policy, select_by_rule  # noqa: E402
from prism_repro.metrics import coverage, mape, pinball  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS  # noqa: E402

RESULTS = os.environ.get("PRISM_RESULTS", os.path.join(ROOT, "results", "raw"))
DRAW_FIELDS = ("warm_mean_1024", "exec_shape", "overhead_mean", "overhead_shape", "init_shape",
               "nonscaling", "intensity_sigma", "peak_upper_frac", "latency_samples", "mem_options")


def source_sha() -> str:
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(ROOT, "src", "prism_repro", "*.py"))):
        h.update(open(f, "rb").read())
    h.update(open(os.path.abspath(__file__), "rb").read())
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, exp):
        self.dir = os.path.join(RESULTS, exp)
        os.makedirs(self.dir, exist_ok=True)
        self.exp = exp
        self.src = source_sha()

    def done(self, seed, chunk=""):
        return os.path.exists(os.path.join(self.dir, f"arrays_seed{seed}{chunk}.npz"))

    def save(self, seed, rows, arrays, chunk=""):
        # rows first, then the arrays file that marks the chunk as complete; a crash in
        # between leaves duplicate rows on rerun, which scripts/analyze.py de-duplicates.
        with open(os.path.join(self.dir, "rows.jsonl"), "a") as f:
            for r in rows:
                f.write(json.dumps(r, default=_json_default) + "\n")
        tmp = os.path.join(self.dir, f".tmp_seed{seed}{chunk}.npz")
        np.savez_compressed(tmp, **arrays)
        os.replace(tmp, os.path.join(self.dir, f"arrays_seed{seed}{chunk}.npz"))


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def load_rows(exp):
    p = os.path.join(RESULTS, exp, "rows.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p)]


def run_one(store, bundle, scenario, week, spec, rows, arrays, cfg_override=None, pbase=None,
            bill_init=True, tag=""):
    ctx = bundle.context(scenario, week, bill_init)
    if cfg_override is not None:
        for f in DRAW_FIELDS:
            if getattr(cfg_override, f) != getattr(ctx.cfg, f):
                raise ValueError(f"cfg override changes draw field {f}; build a new bundle")
        ctx = dataclasses.replace(ctx, cfg=cfg_override, _Kweek={})
    pol = make_policy(spec, pbase)
    run_id = f"{store.exp}|{bundle.seed}|{scenario}|{week}|{pol.label}|{tag}"
    t0, ts = time.perf_counter(), now()
    try:
        res = simulate(ctx, pol)
        s = res["summary"]
        status = "ok"
    except Exception:  # record failures, never hide them
        s, res, status = {"error": traceback.format_exc()}, None, "failed"
    row = dict(run_id=run_id, exp=store.exp, seed=bundle.seed, scenario=scenario, week=week, tag=tag,
               spec=spec, status=status, started_utc=ts, runtime_s=time.perf_counter() - t0,
               source_sha256=store.src, data_sha256=bundle.data_checksum(
                   bundle.scenarios[0] if week == "val" else scenario),
               cfg=(cfg_override or bundle.cfg).to_dict(), synthetic=True, **s)
    rows.append(row)
    if res is not None and res["raw"] is not None:
        for k, v in res["raw"].items():
            arrays[f"{run_id}::{k}"] = v
    return row


def grid_specs(families=("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst",
                         "QuantProv_q90", "QuantProv_q99", "PRISM"), quick=False):
    out = []
    for fam in families:
        if fam == "OnDemand":
            out.append(dict(family="OnDemand"))
        elif fam == "PredHead+hyst":
            out += [dict(family="PredHead", param=p, hyst=True) for p in GRIDS["PredHead"]]
        elif fam.startswith("QuantProv"):
            ti = 2 if fam.endswith("q90") else 3
            out += [dict(family="QuantProv", tau_idx=ti, param=p) for p in GRIDS["QuantProv"]]
        else:
            out += [dict(family=fam, param=p) for p in GRIDS[fam]]
    if quick:
        seen, q = set(), []
        for s in out:  # first two grid values per family
            key = (s["family"], s.get("hyst"), s.get("tau_idx"))
            if sum(1 for x in q if (x["family"], x.get("hyst"), x.get("tau_idx")) == key) < 2:
                q.append(s)
        out = q
    return out


def variant_of(row):
    return row["policy"]


def selections(seed, exp="E1"):
    """Validation-selected spec per variant for one seed (§5.3 rule)."""
    rows = [r for r in load_rows(exp) if r["seed"] == seed and r["week"] == "val" and r["status"] == "ok"]
    out = {}
    for v in sorted(set(variant_of(r) for r in rows)):
        sel = select_by_rule([r for r in rows if variant_of(r) == v])
        out[v] = sel["spec"]
    return out


# ------------------------------------------------------------------ experiments
def exp_E1(seeds, quick=False):
    st = Store("E1")
    for seed in seeds:
        if st.done(seed):
            print(f"[E1] seed {seed} done, skipping", flush=True)
            continue
        t = time.time()
        b = TraceBundle(seed, PipelineConfig())
        rows, arrays = [], {}
        specs = grid_specs(quick=quick)
        for wk, sc in [("val", "stationary")] + [("test", s) for s in MAIN_SCENARIOS]:
            for spec in specs:
                run_one(st, b, sc, wk, spec, rows, arrays)
            print(f"[E1] seed {seed} {wk}/{sc}: {len(rows)} runs, {time.time()-t:.0f}s", flush=True)
        st.save(seed, rows, arrays)


def exp_E2(seeds, quick=False):
    st = Store("E2")
    fcs = ("gbm",)
    for seed in seeds:
        if st.done(seed):
            continue
        b = TraceBundle(seed, PipelineConfig(), forecasters=fcs)
        rows, arrays = [], {}
        for sc in MAIN_SCENARIOS:
            for name in fcs:
                f = b.forecasts[(sc, "test", name)]
                rows.append(forecast_row(st, seed, sc, name, f))
                arrays[f"{seed}|{sc}|{name}::s"] = f["s"].astype(np.float32)
                arrays[f"{seed}|{sc}|{name}::y"] = f["y"].astype(np.float32)
                arrays[f"{seed}|{sc}|{name}::q_raw"] = f["q_raw"].astype(np.float32)
        st.save(seed, rows, arrays)


def forecast_row(st, seed, sc, name, f):
    y, qr, qc = f["y"], f["q_raw"], f["q_cal"]
    return dict(exp=st.exp, seed=seed, scenario=sc, forecaster=name, status="ok", synthetic=True,
                source_sha256=st.src, started_utc=now(),
                mape_median=mape(y, qr[:, 1]), pinball_50=pinball(y, qr[:, 1], 0.5),
                pinball_90=pinball(y, qr[:, 2], 0.9), pinball_99=pinball(y, qr[:, 3], 0.99),
                cov50=coverage(y, qr[:, 1]), cov90_raw=coverage(y, qr[:, 2]), cov99_raw=coverage(y, qr[:, 3]),
                cov90_cal=coverage(y, qc[:, 2]), cov99_cal=coverage(y, qc[:, 3]),
                min_offset=float(f["s"].min()), max_offset=float(f["s"].max()),
                reversals_val_test=int(f["reversals"]))


def exp_E3(seeds, quick=False):
    st = Store("E3")
    for seed in seeds:
        if st.done(seed):
            continue
        sel = selections(seed)
        eps = sel["PRISM"]["param"]
        b = TraceBundle(seed, PipelineConfig())
        rows, arrays = [], {}
        for sc in MAIN_SCENARIOS:
            run_one(st, b, sc, "test", dict(family="PRISM", param=eps, tag="-noconf",
                                            prism=dict(use_conformal=False)), rows, arrays, tag="noconf")
            run_one(st, b, sc, "test", dict(family="Oracle", param=eps), rows, arrays, tag="oracle")
        for sc in ("stationary", "new_spike"):
            run_one(st, b, sc, "test", dict(family="PRISM", param=eps, tag="-qmode",
                                            prism=dict(feasibility_mode="quantile")), rows, arrays, tag="qmode")
            for e in GRIDS["PRISM"]:
                run_one(st, b, sc, "test", dict(family="PRISM", param=e, tag="-nohyst",
                                                prism=dict(use_hysteresis=False)), rows, arrays, tag="nohyst")
        st.save(seed, rows, arrays)
        print(f"[E3] seed {seed} done", flush=True)


def exp_E4(seeds, quick=False):
    st = Store("E4")
    regimes = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
    for seed in seeds:
        if st.done(seed):
            continue
        rows, arrays = [], {}
        bundles = {}
        for ns, D in regimes:
            if ns not in bundles:
                bundles[ns] = TraceBundle(seed, PipelineConfig().with_(nonscaling=ns), scenarios=("stationary",))
            b = bundles[ns]
            cfg = b.cfg.with_(deadline=D)
            tag = f"ns{ns}_D{D}"
            eps_list = [0.02] + ([0.01] if D == 13.0 else [])
            for e in eps_list:
                run_one(st, b, "stationary", "test", dict(family="PRISM", param=e), rows, arrays, cfg, tag=tag)
                run_one(st, b, "stationary", "test", dict(family="PRISM", param=e, tag="-fixedmem",
                                                          prism=dict(optimise_memory=False)), rows, arrays, cfg, tag=tag)
            run_one(st, b, "stationary", "test", dict(family="OnDemand"), rows, arrays, cfg, tag=tag)
            for h in GRIDS["PredHead"]:
                run_one(st, b, "stationary", "test", dict(family="PredHead", param=h), rows, arrays, cfg, tag=tag)
            print(f"[E4] seed {seed} {tag} done", flush=True)
        st.save(seed, rows, arrays)


E5_GRIDS = {"Static": [80, 90, 95, 99], "Reactive": [0.5, 0.6, 0.7, 0.8],
            "PredHead": [1.0, 1.2, 1.4, 1.6, 1.8, 2.0], "PRISM": [0.01, 0.02, 0.05]}


def exp_E5(seeds, quick=False):
    st = Store("E5")
    settings = {"default": {}, "keepalive5": dict(keepalive_min=5), "keepalive30": dict(keepalive_min=30),
                "init3": dict(init_mean_1024=3.0), "init9": dict(init_mean_1024=9.0)}
    for seed in seeds:
        if all(st.done(seed, "_" + n) for n in settings):
            continue
        b = TraceBundle(seed, PipelineConfig(), scenarios=("stationary", "growth"))
        for name, kw in settings.items():
            if st.done(seed, "_" + name):
                continue
            rows, arrays = [], {}
            cfg = b.cfg.with_(**kw)
            specs = [dict(family="OnDemand")] + [dict(family=f, param=p) for f, g in E5_GRIDS.items() for p in g]
            for wk, sc in [("val", "stationary"), ("test", "stationary"), ("test", "growth")]:
                for spec in specs:
                    run_one(st, b, sc, wk, spec, rows, arrays, cfg, tag=name)
            st.save(seed, rows, arrays, "_" + name)
            print(f"[E5] seed {seed} {name} done", flush=True)


def exp_E6(seeds, quick=False):
    st = Store("E6")
    for seed in seeds:
        if st.done(seed):
            continue
        b = TraceBundle(seed, PipelineConfig(), scenarios=("stationary", "new_spike"))
        rows, arrays = [], {}
        for sc in ("stationary", "new_spike"):
            for cap in (None, 250, 60, 40):
                spec = dict(family="PRISM", param=0.02, tag=f"-cap{cap}", prism=dict(cap=cap))
                run_one(st, b, sc, "test", spec, rows, arrays, tag=f"cap{cap}")
        st.save(seed, rows, arrays)
        print(f"[E6] seed {seed} done", flush=True)


def exp_E7(seeds, quick=False):
    st = Store("E7")
    fcs = ("gbm", "gbm_no_trigger", "gbm_no_prevday", "gbm_no_norm")
    scen = MAIN_SCENARIOS + ("shifted_triggers",)
    for seed in seeds:
        if st.done(seed):
            continue
        eps = selections(seed)["PRISM"]["param"]
        b = TraceBundle(seed, PipelineConfig(), scenarios=scen, forecasters=fcs)
        rows, arrays = [], {}
        for sc in scen:
            for name in fcs:
                fr = forecast_row(st, seed, sc, name, b.forecasts[(sc, "test", name)])
                fr["kind"] = "forecast"
                rows.append(fr)
                if sc == "shifted_triggers" or name != "gbm":
                    run_one(st, b, sc, "test", dict(family="PRISM", param=eps, fc=name), rows, arrays, tag=name)
        st.save(seed, rows, arrays)
        print(f"[E7] seed {seed} done", flush=True)


def exp_E8(seeds, quick=False):
    st = Store("E8")
    fcs = ("gbm", "seasonal_naive", "last5max", "ewma")
    for seed in seeds:
        if all(st.done(seed, "_" + n) for n in fcs[1:]):
            continue
        b = TraceBundle(seed, PipelineConfig(), forecasters=fcs)
        rows, arrays = [], {}
        if not st.done(seed, "_forecast"):
            for sc in MAIN_SCENARIOS:
                for name in fcs:
                    fr = forecast_row(st, seed, sc, name, b.forecasts[(sc, "test", name)])
                    fr["kind"] = "forecast"
                    rows.append(fr)
            st.save(seed, rows, {"placeholder": np.zeros(1)}, "_forecast")
        for name in fcs[1:]:  # gbm results come from E1
            if st.done(seed, "_" + name):
                continue
            rows, arrays = [], {}
            specs = [dict(family="PRISM", param=e, fc=name) for e in GRIDS["PRISM"]] + \
                    [dict(family="QuantProv", tau_idx=3, param=a, fc=name) for a in GRIDS["QuantProv"]]
            for wk, sc in [("val", "stationary")] + [("test", s) for s in MAIN_SCENARIOS]:
                for spec in specs:
                    run_one(st, b, sc, wk, spec, rows, arrays, tag=name)
            st.save(seed, rows, arrays, "_" + name)
            print(f"[E8] seed {seed} {name} done", flush=True)


def exp_E10(seeds, quick=False):
    from prism_repro.overhead import measure_overhead
    st = Store("E10")
    for seed in seeds:
        if st.done(seed):
            continue
        row, arrays = measure_overhead(seed)
        row.update(exp="E10", status="ok", source_sha256=st.src, started_utc=now(),
                   platform=platform.platform(), processor=platform.processor(),
                   python=platform.python_version())
        st.save(seed, [row], arrays)
        print("[E10]", json.dumps({k: row[k] for k in row if "ms" in k or "identical" in k}), flush=True)


def exp_E11(seeds, quick=False):
    st = Store("E11")
    for seed in seeds:
        if st.done(seed):
            continue
        b = TraceBundle(seed, PipelineConfig())
        rows, arrays = [], {}
        for wk, sc in [("val", "stationary")] + [("test", s) for s in MAIN_SCENARIOS]:
            for e in GRIDS["PRISM"]:
                run_one(st, b, sc, wk, dict(family="PRISM", param=e, prism=dict(risk_model="erlangb")),
                        rows, arrays, tag="EB")
        st.save(seed, rows, arrays)
        print(f"[E11] seed {seed} done", flush=True)


E9_FAMILIES = ("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PRISM")


def exp_E9(seeds, quick=False):
    """Event-level re-evaluation of frozen, validation-tuned E1 schedules (open loop, §6.8)."""
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import KDraws
    from prism_repro.latency import stage_means
    from prism_repro.risk import c_eff, erlang_b, occupancy_overflow
    from prism_repro.workload import generate_trace
    st = Store("E9")
    cfg = PipelineConfig()
    e1 = {(r["seed"], r["scenario"], r["week"], r["label"]): r for r in load_rows("E1")}
    for seed in seeds:
        sel = selections(seed)
        arr1 = np.load(os.path.join(RESULTS, "E1", f"arrays_seed{seed}.npz"))
        detail = seed == seeds[0]
        for sc in MAIN_SCENARIOS:
            if st.done(seed, "_" + sc):
                continue
            rows, arrays = [], {}
            counts = generate_trace(seed, sc)["counts"][21 * 1440:28 * 1440]
            dr = EventDraws(cfg, counts, seed, 3)
            Kfast = KDraws(cfg, seed, 3).peak_concurrency(counts.astype(float), 1024)
            for fam in E9_FAMILIES:
                spec = sel[fam]
                label = make_policy(spec).label
                key = f"E1|{seed}|{sc}|test|{label}|"
                P_ep, m_ep = arr1[key + "::P_epoch"], arr1[key + "::mem_epoch"]
                want = detail and sc in ("stationary", "new_spike")
                t0, ts = time.perf_counter(), now()
                res = simulate_events(cfg, dr, P_ep, m_ep, want_inflight=want,
                                      sample_seed=1000 + seed if want else None)
                fast = e1[(seed, sc, "test", label)]
                row = dict(exp="E9", seed=seed, scenario=sc, week="test", label=label, policy=fam, spec=spec,
                           status="ok", started_utc=ts, runtime_s=time.perf_counter() - t0,
                           source_sha256=st.src, data_sha256=hashlib.sha256(counts.tobytes()).hexdigest(),
                           synthetic=True, open_loop=True, n_requests=int(dr.n),
                           **{f"event_{k}": v for k, v in res["summary"].items()},
                           **{f"fast_{k}": fast[k] for k in ("cost", "violating_window_rate", "record_attainment",
                                                            "cold_start_ratio", "overflow_share", "slo_met",
                                                            "late_records", "worst_window_attainment",
                                                            "longest_run", "mean_run", "attain_in_violating")})
                if want:
                    P_min = np.repeat(P_ep, cfg.epoch_min, axis=0)[:len(counts)]
                    d = stage_means(cfg, 1024)
                    c = counts[:, None] * d[None, :] / 60.0
                    w = counts[:, None].astype(float)
                    def share(f):
                        return float((w * f).sum() / (w.sum() * cfg.n_stages))
                    row.update(est_erlangb=share(erlang_b(P_min, c)), est_occ_mean=share(occupancy_overflow(P_min, c)),
                               est_occ_ceff=share(occupancy_overflow(P_min, c_eff(c))))
                    infl = res["raw"]["inflight_max"]
                    msk = Kfast > 0
                    ratio = infl[msk] / Kfast[msk]
                    row.update({f"inflight_ratio_q{int(q*100)}": float(np.quantile(ratio, q)) for q in (0.1, 0.5, 0.9, 0.99)})
                    fl = res["raw"]["sampling_flip_share"]
                    row.update(sampling_flip_mean=float(fl.mean()), sampling_flip_min=float(fl.min()),
                               sampling_flip_max=float(fl.max()))
                rows.append(row)
                for k, v in res["raw"].items():
                    if k != "inflight_max":
                        arrays[f"{seed}|{sc}|{label}::{k}"] = v
                print(f"[E9] seed {seed} {sc} {label}: {row['runtime_s']:.0f}s", flush=True)
            st.save(seed, rows, arrays, "_" + sc)


EXPS = {"E1": exp_E1, "E9": exp_E9, "E2": exp_E2, "E3": exp_E3, "E4": exp_E4, "E5": exp_E5, "E6": exp_E6,
        "E7": exp_E7, "E8": exp_E8, "E10": exp_E10, "E11": exp_E11}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True, choices=sorted(EXPS))
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--quick", action="store_true", help="reduced grids (smoke test only)")
    a = ap.parse_args()
    t = time.time()
    print(f"[{a.exp}] start {now()} seeds={a.seeds} python={platform.python_version()} "
          f"numpy={np.__version__}", flush=True)
    EXPS[a.exp](a.seeds, a.quick)
    print(f"[{a.exp}] finished {now()} in {time.time()-t:.0f}s", flush=True)
