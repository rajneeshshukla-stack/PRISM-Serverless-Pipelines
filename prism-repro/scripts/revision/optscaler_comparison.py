#!/usr/bin/env python3
"""R3.2: OptScaler [16] against PRISM under the Table V protocol (docs/revision/optscaler_r32_20261124/PLAN.md).
EXPLORATORY, PRE-CALIBRATION, fast simulator, development traces 101-105. No AWS.

usage (from prism-repro/; one thread per BLAS library, PYTHONUTF8=1):
  venv/Scripts/python scripts/revision/optscaler_comparison.py <out> d1            # determinism check D1
  venv/Scripts/python scripts/revision/optscaler_comparison.py <out> run 101 ...   # validation tuning + test weeks
  venv/Scripts/python scripts/revision/optscaler_comparison.py <out> analyse
The comparator rows are the regenerated E1 rows (fd8b01a, Windows), path in REGEN_E1 or $PRISM_REGEN_E1.
"""
import json
import math
import os
import sys
import time

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy, select_by_rule  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS  # noqa: E402
import optscaler_policy as op  # noqa: E402

REGEN_E1 = os.environ.get("PRISM_REGEN_E1", os.path.join(
    ROOT, "private", "regen_20261122", "prism-repro", "results", "raw_regenerated", "E1", "rows.jsonl"))
C_GRID = [round(0.30 + 0.05 * i, 2) for i in range(15)]
SEEDS = (101, 102, 103, 104, 105)
KEEP = ("cost", "violating_window_rate", "slo_met", "record_attainment", "p99_latency", "mean_provisioned",
        "cold_start_ratio", "overflow_share", "billing_utilisation", "cost_pc", "cost_od", "cost_init")


def regen_rows():
    return [json.loads(l) for l in open(REGEN_E1)]


def regen_selected(rows, seed, policy):
    """Validation-selected spec of one regenerated E1 variant and its test rows, by the Section V-C rule."""
    val = [r for r in rows if r["seed"] == seed and r["week"] == "val" and r["status"] == "ok" and r["policy"] == policy]
    sel = select_by_rule(val)
    test = {r["scenario"]: r for r in rows if r["seed"] == seed and r["week"] == "test" and r["policy"] == policy
            and json.dumps(r["spec"], sort_keys=True) == json.dumps(sel["spec"], sort_keys=True)}
    return sel, test


def summ(res, **extra):
    s = res["summary"]
    d = {k: (float(s[k]) if not isinstance(s[k], bool) else s[k]) for k in KEEP}
    d.update({k: s[k] for k in ("eta", "w0_mean", "sigma_mean", "w_final_mean") if k in s})
    d.update(extra)
    return d


def cmd_d1(out):
    rows = regen_rows()
    b = TraceBundle(101, PipelineConfig())
    res = {}
    for pol_name in ("PRISM_EB", "OnDemand"):
        sel, test = regen_selected(rows, 101, pol_name)
        r = simulate(b.context("stationary", "test"), make_policy(sel["spec"]))["summary"]
        ref = test["stationary"]
        res[pol_name] = dict(spec=sel["spec"], cost=r["cost"], ref_cost=ref["cost"],
                             viol=r["violating_window_rate"], ref_viol=ref["violating_window_rate"],
                             ok=abs(r["cost"] - ref["cost"]) <= 1e-9 * max(1, ref["cost"])
                             and abs(r["violating_window_rate"] - ref["violating_window_rate"]) <= 1e-9)
    res["pass"] = all(v["ok"] for v in res.values())
    json.dump(res, open(os.path.join(out, "d1_determinism.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def coverage(K, y, w, sig, z):
    sel = y > 0
    return float(np.mean(K[sel] <= (w + z * sig) * y[sel]))


def cmd_run(out, seeds, eta=None, fname="rows.jsonl"):
    """eta=None: prespecified (A11 selects eta). eta=0.0: POST HOC diagnostic, reactive module closed."""
    path = os.path.join(out, fname)
    done = {json.loads(l)["seed"] for l in open(path)} if os.path.exists(path) else set()
    for seed in seeds:
        if seed in done:
            print(f"seed {seed} done, skipping", flush=True)
            continue
        t0 = time.time()
        b = TraceBundle(seed, PipelineConfig())
        recs = []
        val = []
        for c in C_GRID:
            pol = op.OptScaler(c, eta=eta)
            r = simulate(b.context("stationary", "val"), pol)
            val.append(dict(c_star=c, **summ(r)))
        sel = select_by_rule(val)
        # V2: coverage of the fitted estimator (in sample: the fitting minutes; out of sample: validation week)
        ctx = b.context("stationary", "val")
        pol = op.OptScaler(sel["c_star"], eta=eta); pol.prepare(ctx)
        ws = ctx.week_start
        y_in, y_out = ctx.counts[:ws].astype(float), ctx.counts[ws:ws + 7 * 1440].astype(float)
        K_out = ctx.K_week(ctx.cfg.default_mem)
        v2 = [dict(stage=s, cov_in=coverage(ctx.K_hist_default[:ws, s], y_in, pol.w0[s], pol.sig[s], pol.z),
                   cov_out=coverage(K_out[:, s], y_out, pol.w0[s], pol.sig[s], pol.z),
                   w0=float(pol.w0[s]), sigma=float(pol.sig[s])) for s in range(ctx.cfg.n_stages)]
        test = {}
        for label, c in (("selected", sel["c_star"]), ("published", op.C_STAR_PUBLISHED)):
            for sc in MAIN_SCENARIOS:
                r = simulate(b.context(sc, "test"), op.OptScaler(c, eta=eta))
                test[f"{label}|{sc}"] = dict(c_star=c, **summ(r))
        rec = dict(seed=seed, c_selected=sel["c_star"], val=val, test=test, v2=v2, eta_losses={
            str(k): v for k, v in pol.eta_losses.items()}, runtime_s=time.time() - t0)
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"seed {seed}: c* {sel['c_star']}, eta {val[0].get('eta')}, {time.time() - t0:.0f}s", flush=True)


def hw(x):
    x = np.asarray(x, float)
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def cmd_analyse(out, fname="rows.jsonl", tag=""):
    recs = sorted((json.loads(l) for l in open(os.path.join(out, fname))), key=lambda r: r["seed"])
    assert [r["seed"] for r in recs] == list(SEEDS), [r["seed"] for r in recs]
    rows = regen_rows()
    comp = {}
    for pname in ("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90",
                  "QuantProv_q99", "PRISM_EB"):
        comp[pname] = {s: regen_selected(rows, s, pname)[1] for s in SEEDS}
    res = dict(selected_c={r["seed"]: r["c_selected"] for r in recs},
               eta={r["seed"]: r["val"][0].get("eta") for r in recs},
               prism_eps={s: regen_selected(rows, s, "PRISM_EB")[0]["spec"]["param"] for s in SEEDS},
               v2=[dict(seed=r["seed"], **v) for r in recs for v in r["v2"]], table={}, paired={})
    lines = ["| Policy | " + " | ".join(f"{sc}: cost (USD) | {sc}: violating (%)" for sc in MAIN_SCENARIOS) + " |",
             "|---" * (1 + 2 * len(MAIN_SCENARIOS)) + "|"]

    def cells(get):
        out_c = []
        for sc in MAIN_SCENARIOS:
            c = [get(s, sc)["cost"] for s in SEEDS]
            v = [100 * get(s, sc)["violating_window_rate"] for s in SEEDS]
            met = sum(1 for s in SEEDS if get(s, sc)["violating_window_rate"] <= 0.02 + 1e-12)
            out_c.append(dict(cost=float(np.mean(c)), cost_hw=hw(c), viol=float(np.mean(v)), viol_hw=hw(v), met=met))
        return out_c

    variants = {f"OptScaler (c* validation-tuned)": lambda s, sc: next(r for r in recs if r["seed"] == s)["test"][f"selected|{sc}"],
                f"OptScaler (published c* = 0.5)": lambda s, sc: next(r for r in recs if r["seed"] == s)["test"][f"published|{sc}"]}
    for pname, d in comp.items():
        variants[pname.replace("PRISM_EB", "PRISM")] = (lambda d: lambda s, sc: d[s][sc])(d)
    for name, get in variants.items():
        cs = cells(get)
        res["table"][name] = cs
        lines.append(f"| {name} | " + " | ".join(
            f"{c['cost']:,.0f} ± {c['cost_hw']:,.0f} | {c['viol']:.2f} ± {c['viol_hw']:.2f} [{c['met']}]" for c in cs) + " |")
    plines = ["| Scenario | PRISM minus OptScaler: cost (%) | violating windows (points) | PRISM cheaper / fewer violating (of 5) |",
              "|---|---|---|---|"]
    for label in ("selected", "published"):
        res["paired"][label] = {}
        for sc in MAIN_SCENARIOS:
            dc, dv = [], []
            for s in SEEDS:
                o = next(r for r in recs if r["seed"] == s)["test"][f"{label}|{sc}"]
                p = comp["PRISM_EB"][s][sc]
                dc.append(100 * (p["cost"] - o["cost"]) / o["cost"])
                dv.append(100 * (p["violating_window_rate"] - o["violating_window_rate"]))
            e = dict(cost_pct=float(np.mean(dc)), cost_hw=hw(dc), viol_pp=float(np.mean(dv)), viol_hw=hw(dv),
                     cheaper=sum(x < 0 for x in dc), fewer_viol=sum(x < 0 for x in dv), per_trace_cost=dc, per_trace_viol=dv)
            res["paired"][label][sc] = e
            plines.append(f"| {sc} ({label} c*) | {e['cost_pct']:+.1f} ± {e['cost_hw']:.1f} | {e['viol_pp']:+.2f} ± "
                          f"{e['viol_hw']:.2f} | {e['cheaper']} / {e['fewer_viol']} |")
    json.dump(res, open(os.path.join(out, f"analysis{tag}.json"), "w"), indent=1)
    open(os.path.join(out, f"table_v_with_optscaler{tag}.md"), "w", encoding="utf-8").write("\n".join(lines + [""] + plines) + "\n")
    print("\n".join(lines + [""] + plines))
    print("selected c*:", res["selected_c"], "eta:", res["eta"], "PRISM eps:", res["prism_eps"])


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    cmd = sys.argv[2]
    if cmd == "d1":
        cmd_d1(out)
    elif cmd == "run":
        cmd_run(out, [int(s) for s in sys.argv[3:]] or list(SEEDS))
    elif cmd == "analyse":
        cmd_analyse(out)
    elif cmd == "run_posthoc_eta0":   # POST HOC (after the prespecified run): eta fixed at 0
        cmd_run(out, [int(s) for s in sys.argv[3:]] or list(SEEDS), eta=0.0, fname="rows_posthoc_eta0.jsonl")
    elif cmd == "analyse_posthoc_eta0":
        cmd_analyse(out, "rows_posthoc_eta0.jsonl", "_posthoc_eta0")
    else:
        raise SystemExit(__doc__)
