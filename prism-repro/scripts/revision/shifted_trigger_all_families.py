#!/usr/bin/env python3
"""All families under the shifted-trigger scenario (R5.M4(b)).

EXPLORATORY, PRE-CALIBRATION (assumed constants, Table S1), fast simulator, current code, development traces 101-105
only (confirmatory seeds 106-130 unused). Not prespecified: `docs/revision/PRESPECIFICATION.md` names stationary,
growth, bursty and new_spike as the confirmatory scenarios and excludes the fast simulator from confirmatory
comparisons. The protocol is the paper's E1 rule (Table V): every family is tuned on the stationary validation week
(days 14-20) over `experiment.GRIDS` with `experiment.select_by_rule` (cheapest with at most 2% violating windows, else
the least violating), and the selected setting runs on the held-out test week (days 21-27) of the shifted-trigger
scenario, whose spike schedule changes in the test week without notice to the forecaster. The stationary test week is
run at the same selections as a reference. The paper's E7 ran PRISM alone in this scenario.

usage: python shifted_trigger_all_families.py <code_root> <out_dir> [--workers=N]
       python shifted_trigger_all_families.py <code_root> <out_dir> --analyse      (writes <out_dir>/summary.txt)
Rows are written and flushed one at a time; an existing (seed, week, scenario, spec) row is skipped."""
import json, os, platform, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(ROOT, "src"))
SEEDS = (101, 102, 103, 104, 105)
TEST_SCEN = ("shifted_triggers", "stationary")
FAMILIES = ("OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90",
            "QuantProv_q99", "PRISM")
TARGET = 0.02


def specs():
    from prism_repro.experiment import GRIDS
    out = [("OnDemand", dict(family="OnDemand"))]
    for fam in FAMILIES[1:]:
        if fam == "PredHead+hyst":
            out += [(fam, dict(family="PredHead", param=p, hyst=True)) for p in GRIDS["PredHead"]]
        elif fam.startswith("QuantProv"):
            out += [(fam, dict(family="QuantProv", tau_idx=2 if fam.endswith("q90") else 3, param=p)) for p in GRIDS["QuantProv"]]
        else:
            out += [(fam, dict(family=fam, param=p)) for p in GRIDS[fam]]
    return out


def key(r):
    return (r["seed"], r["week"], r["scenario"], json.dumps(r["spec"], sort_keys=True))


def task(seed, out_dir):
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, run_policy, select_by_rule
    path = os.path.join(out_dir, f"rows_{seed}.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []
    done = {key(r) for r in rows}
    b = TraceBundle(seed, PipelineConfig(), scenarios=("stationary", "shifted_triggers"))

    def run(fam, spec, week, sc, f):
        r0 = dict(seed=seed, week=week, scenario=sc, spec=spec)
        if key(r0) in done:
            return next(r for r in rows if key(r) == key(r0))
        t0 = time.perf_counter()
        s = run_policy(b, sc, week, spec)["summary"]
        r = dict(r0, family=fam, param=spec.get("param"), cost=float(s["cost"]),
                 violating_window_rate=float(s["violating_window_rate"]), slo_met=bool(s["slo_met"]),
                 data_sha256=s.get("data_sha256"), runtime_s=time.perf_counter() - t0)
        f.write(json.dumps(r) + "\n"); f.flush(); rows.append(r); done.add(key(r))
        return r

    with open(path, "a", encoding="utf-8", newline="\n") as f:
        val = {}
        for fam, spec in specs():
            val.setdefault(fam, []).append(run(fam, spec, "val", "stationary", f))
        for fam in FAMILIES:
            sel = select_by_rule(val[fam]) if fam != "OnDemand" else val[fam][0]
            for sc in TEST_SCEN:
                run(fam, sel["spec"], "test", sc, f)
    return seed


def environment():
    import numpy, scipy, sklearn
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "src", "experiments"],
                           capture_output=True, text=True).stdout.strip()
    return dict(platform=platform.platform(), python=platform.python_version(), numpy=numpy.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__, git_head=head, src_and_experiments_clean=dirty == "")


def analyse(out_dir):
    from scipy import stats
    from prism_repro.experiment import GRIDS, select_by_rule
    rows = []
    for s in SEEDS:
        p = os.path.join(out_dir, f"rows_{s}.jsonl")
        if os.path.exists(p):
            rows += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    gk = {"PredHead+hyst": "PredHead", "QuantProv_q90": "QuantProv", "QuantProv_q99": "QuantProv"}
    L = ["ALL FAMILIES UNDER THE SHIFTED-TRIGGER SCENARIO (R5.M4(b)); EXPLORATORY, PRE-CALIBRATION, fast simulator,",
         "current code, development traces 101-105; validation-selected on the stationary validation week (E1 rule).", ""]
    sel, res = {}, {}
    for s in SEEDS:
        for fam in FAMILIES:
            v = [r for r in rows if r["seed"] == s and r["week"] == "val" and r["family"] == fam]
            if not v:
                continue
            sp = select_by_rule(v)["spec"] if fam != "OnDemand" else v[0]["spec"]
            sel[(s, fam)] = sp
            for sc in TEST_SCEN:
                t = [r for r in rows if r["seed"] == s and r["week"] == "test" and r["scenario"] == sc and r["spec"] == sp]
                if t:
                    res[(s, fam, sc)] = t[0]
    n = len({s for s, _ in sel})
    L.append(f"Traces complete: {n} of {len(SEEDS)}")
    L.append("Selections (validation week): " + "; ".join(
        f"{s}: " + ", ".join(f"{fam} {sel[(s, fam)].get('param', '-')}" for fam in FAMILIES if (s, fam) in sel) for s in SEEDS if (s, "PRISM") in sel))
    edges = [(s, fam, sel[(s, fam)]["param"]) for (s, fam) in sel if fam != "OnDemand"
             and sel[(s, fam)]["param"] in (min(GRIDS[gk.get(fam, fam)]), max(GRIDS[gk.get(fam, fam)]))]
    L.append(f"Selections at a grid edge: {len(edges)} of {sum(1 for k in sel if k[1] != 'OnDemand')}: " + ", ".join(f"{s} {f} {p:g}" for s, f, p in edges))
    L.append("")
    for sc in TEST_SCEN:
        L.append(f"## Test week: {sc} (selected settings); mean over traces")
        L.append(f"  {'family':14s} {'cost USD':>9s} {'viol %':>7s} {'weeks <=2%':>10s}")
        for fam in FAMILIES:
            rr = [res[(s, fam, sc)] for s in SEEDS if (s, fam, sc) in res]
            if rr:
                L.append(f"  {fam:14s} {np.mean([r['cost'] for r in rr]):9,.0f} {100*np.mean([r['violating_window_rate'] for r in rr]):7.2f} "
                         f"{sum(r['violating_window_rate'] <= TARGET + 1e-12 for r in rr):>5d}/{len(rr)}")
        L.append("  Paired PRISM minus comparator (per trace; mean +/- 95% t half-width, df = n-1):")
        for fam in FAMILIES[:-1]:
            ks = [s for s in SEEDS if (s, "PRISM", sc) in res and (s, fam, sc) in res]
            if len(ks) < 2:
                continue
            dc = np.array([100 * (res[(s, "PRISM", sc)]["cost"] / res[(s, fam, sc)]["cost"] - 1) for s in ks])
            dv = np.array([100 * (res[(s, "PRISM", sc)]["violating_window_rate"] - res[(s, fam, sc)]["violating_window_rate"]) for s in ks])
            hw = lambda x: stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
            inc = lambda x: "includes 0" if abs(x.mean()) <= hw(x) else "excludes 0"
            L.append(f"    vs {fam:14s} cost {dc.mean():+6.1f} +/- {hw(dc):4.1f}% ({inc(dc)}); viol {dv.mean():+5.2f} +/- {hw(dv):4.2f} pts ({inc(dv)}) n={len(ks)}")
        L.append("")
    txt = "\n".join(L) + "\n"
    open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8", newline="\n").write(txt)
    print(txt)


def main():
    out_dir = os.path.abspath(sys.argv[2]); args = sys.argv[3:]
    os.makedirs(out_dir, exist_ok=True)
    if "--analyse" in args:
        return analyse(out_dir)
    workers = int(next((a.split("=")[1] for a in args if a.startswith("--workers=")), "4"))
    env = environment()
    with open(os.path.join(out_dir, "environment.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(env, f, indent=1)
    print(f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} workers={workers} env={json.dumps(env)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for fu in as_completed([ex.submit(task, s, out_dir) for s in SEEDS]):
            print(f"task done {fu.result()} {time.strftime('%H:%M:%SZ', time.gmtime())}", flush=True)
    print(f"end {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)


if __name__ == "__main__":
    main()
