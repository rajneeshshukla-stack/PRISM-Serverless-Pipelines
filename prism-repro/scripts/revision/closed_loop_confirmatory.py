#!/usr/bin/env python3
"""Confirmatory comparisons C1-C3 under the frozen docs/revision/PRESPECIFICATION.md (d16fbea), and the trace-101
reproduction of the exploratory pilot that checks this driver (R2.1, R2.18, R3.3, R4.2, R6.4, R6.5, R7.6).

PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION: the constants are the PipelineConfig()/PrismConfig() defaults at a10efe6
(src/ is unchanged since), not measured values. The prespecification reruns the same comparisons unchanged when
measured constants replace them.

Design (PRESPECIFICATION.md sections 1-6), unchanged from scripts/revision/closed_loop_pilot.py:
  - event-level simulator in closed loop: des.simulate_events(cfg, draws, controller=closed_loop.PolicyController(...));
  - validation week days 14-20 (event draw key 2, scenario-independent), test weeks days 21-27 per scenario (key 3);
  - per policy and trace: every value of experiment.GRIDS on the validation week, experiment.select_by_rule, and the
    prespecified edge expansion over experiment.GRIDS_WIDE (the selection and expansion code is the pilot's, verbatim);
  - the selected setting then runs on the held-out test weeks; test outcomes never enter a selection.
Sets: C1C2 (PRISM, QuantProv_q90, Reactive; default deadline 14.5 s; stationary, growth, bursty, new_spike),
      C3 (PRISM, MemAdapt_q90; deadline 12 s, non-scaling 0.5; stationary), on confirmatory seeds 106-130;
      pilot101 (all four families, seed 101, stationary, defaults): the driver check against the saved pilot.

Every closed-loop week is one task whose result is saved atomically as it completes (weeks/...json), so a stopped run
resumes where it stopped. Groups are written when their test weeks are done. run.log records every completion and a
heartbeat each minute (a gap marks a suspension). On Windows the run asks the OS not to idle-sleep while it runs.

Usage (from prism-repro/):
  python scripts/revision/closed_loop_confirmatory.py run <out> --sets=C1C2,C3 [--workers=6] [--seeds=106-130]
  python scripts/revision/closed_loop_confirmatory.py analyse <out>
  python scripts/revision/closed_loop_confirmatory.py verify-traces <out> [--seeds=106-130]
"""
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")          # one thread per worker process: no oversubscription (inherited by workers)

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

FAMILIES = {"PRISM": (dict(family="PRISM"), "PRISM"),
            "QuantProv_q90": (dict(family="QuantProv", tau_idx=2), "QuantProv"),
            "Reactive": (dict(family="Reactive"), "Reactive"),
            "MemAdapt_q90": (dict(family="MemAdapt", tau_idx=2), "QuantProv")}
KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "overflow_share", "p99_latency")
MAIN = ("stationary", "growth", "bursty", "new_spike")
CONF_SEEDS = tuple(range(106, 131))
SETS = {
    "C1C2": dict(seeds=CONF_SEEDS, scenarios=MAIN, families=("PRISM", "QuantProv_q90", "Reactive"), cfg={}),
    "C3": dict(seeds=CONF_SEEDS, scenarios=("stationary",), families=("PRISM", "MemAdapt_q90"),
               cfg=dict(deadline=12.0, nonscaling=0.5)),
    "pilot101": dict(seeds=(101,), scenarios=("stationary",), families=tuple(FAMILIES), cfg={}),
}
LABEL = ("PRE-CALIBRATION, SUPERSEDES AT RECALIBRATION: PipelineConfig()/PrismConfig() defaults at a10efe6 (assumed, "
         "not measured); docs/revision/PRESPECIFICATION.md (d16fbea)")


def make_cfg(overrides):
    from prism_repro.config import PipelineConfig
    return PipelineConfig().with_(**overrides) if overrides else PipelineConfig()


def cfg_sha(cfg):
    return hashlib.sha256(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:16]


# ------------------------------------------------------------------ worker side
_BUNDLES = {}


def bundle_file(out, seed, sha):
    return os.path.join(out, "bundles", f"bundle_{seed}_{sha}.pkl")


def build_bundle(seed, overrides):
    """The trace bundle of one seed and configuration (all four main scenarios), with the pre-week history concurrency
    of every scenario computed, exactly as a worker would compute it lazily."""
    from prism_repro.experiment import TraceBundle
    cfg = make_cfg(overrides)
    b = TraceBundle(seed, cfg, scenarios=MAIN)
    for sc in MAIN:
        b.K_hist(sc)
    return cfg, b


def bundle_task(task):
    """Build one bundle once and save it, so every worker loads the same object instead of retraining it."""
    import pickle
    t0 = time.time()
    cfg, b = build_bundle(task["seed"], task["cfg"])
    p = bundle_file(task["out"], task["seed"], cfg_sha(cfg))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + f".tmp{os.getpid()}"
    with open(tmp, "wb") as fh:
        pickle.dump(b, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, p)
    return dict(seed=task["seed"], cfg_sha=cfg_sha(cfg), build_s=round(time.time() - t0, 1), bytes=os.path.getsize(p),
                sha256=_sha(p))


def _bundle(seed, overrides, out):
    import pickle
    cfg = make_cfg(overrides)
    key = (seed, cfg_sha(cfg))
    if key not in _BUNDLES:
        if len(_BUNDLES) >= 3:
            _BUNDLES.pop(next(iter(_BUNDLES)))
        p = bundle_file(out, seed, key[1])
        if os.path.exists(p):
            with open(p, "rb") as fh:
                _BUNDLES[key] = (cfg, pickle.load(fh))
        else:
            _BUNDLES[key] = build_bundle(seed, overrides)
    return _BUNDLES[key]


def week_file(out, t):
    return os.path.join(out, "weeks", t["set"], str(t["seed"]), t["family"], f"{t['week']}_{t['scenario']}_{t['param']}.json")


def week_task(t):
    """One closed-loop week: the pilot's week_run, generalised to any scenario and configuration."""
    from prism_repro.closed_loop import PolicyController
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import WEEK_START, make_policy
    S = SETS[t["set"]]
    cfg, b = _bundle(t["seed"], S["cfg"], t["out"])    # all four main scenarios; the first 21 days are identical
    sc = b.scenarios[0] if t["week"] == "val" else t["scenario"]
    ws = WEEK_START[t["week"]]
    counts = b.traces[sc]["counts"][ws:ws + 7 * 1440]
    dr = EventDraws(cfg, counts, b.seed, 2 if t["week"] == "val" else 3)
    spec, _ = FAMILIES[t["family"]]
    pol = make_policy(dict(spec, param=t["param"]))
    t0 = time.time()
    res = simulate_events(cfg, dr, controller=PolicyController(pol, b, sc, week=t["week"]))
    s = res["summary"]
    me = res["raw"]["mem_epoch"]
    row = dict(week=t["week"], param=t["param"], runtime_s=round(time.time() - t0, 1), n_requests=int(dr.n),
               share_mem_ge_2048=float(np.mean(me >= 2048)), **{k: float(s[k]) for k in KEYS})
    if hasattr(pol, "rec"):
        row["kappa_mean"] = float(pol.rec["kappa"].mean())
        row["infeasible_share"] = float(1 - pol.rec["feasible"].mean())
    row.update(scenario=t["scenario"], seed=t["seed"], family=t["family"], set=t["set"], cfg_sha=cfg_sha(cfg),
               counts_sha256=hashlib.sha256(np.ascontiguousarray(counts, dtype="<i8").tobytes()).hexdigest(),
               pid=os.getpid(), finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    p = week_file(t["out"], t)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + f".tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(row, fh, indent=1)
    os.replace(tmp, p)
    return row


def load_week(out, t, want_sha):
    p = week_file(out, t)
    if not os.path.exists(p):
        return None
    try:
        r = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    ok = (r.get("cfg_sha") == want_sha and r.get("param") == t["param"] and r.get("week") == t["week"]
          and r.get("scenario") == t["scenario"] and all(k in r for k in KEYS))
    return r if ok else None


# ------------------------------------------------------------------ parent side: groups, selection, expansion
class Group:
    """One (set, seed, family): validation grid -> selection with the prespecified edge expansion -> test weeks.
    select() is the pilot's loop body, verbatim, applied whenever the validation rows it needs are present."""

    def __init__(self, set_name, seed, fam, scenarios):
        from prism_repro.experiment import GRIDS, GRIDS_WIDE
        self.set, self.seed, self.fam, self.scenarios = set_name, seed, fam, scenarios
        spec, gname = FAMILIES[fam]
        self.grid, self.wide = list(GRIDS[gname]), list(GRIDS_WIDE[gname])
        self.val, self.expansions, self.sel, self.tests, self.state = {}, [], None, {}, "val"

    def tasks_val(self, out):
        return [dict(out=out, set=self.set, seed=self.seed, family=self.fam, param=p, week="val", scenario="validation")
                for p in self.grid]

    def select(self):
        """Returns ('expand', nxt) or ('final', sel), as the pilot's while-loop does one iteration at a time."""
        from prism_repro.experiment import select_by_rule
        rows = [dict(param=p, cost=r["cost"], violating_window_rate=r["violating_window_rate"]) for p, r in self.val.items()]
        sel = select_by_rule(rows)["param"]
        ps = sorted(self.val)
        nxt = None
        if sel == ps[0]:
            lower = [q for q in self.wide if q < ps[0]]
            nxt = max(lower) if lower else None
        elif sel == ps[-1]:
            upper = [q for q in self.wide if q > ps[-1]]
            nxt = min(upper) if upper else None
        if nxt is None:
            return "final", sel
        return "expand", nxt

    def record(self, commit):
        ps = sorted(self.val)
        return dict(set=self.set, seed=self.seed, family=self.fam, scenarios=list(self.scenarios), grid=self.grid,
                    expansions=self.expansions, selected=self.sel, edge_hit=bool(self.sel in (ps[0], ps[-1])),
                    validation=[self.val[p] for p in ps], tests=[self.tests[sc] for sc in self.scenarios],
                    test=self.tests.get("stationary"), commit=commit)


def _git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout.strip()


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def environment(sets, workers):
    import scipy
    import sklearn
    from prism_repro.config import PrismConfig
    from prism_repro.experiment import GRIDS, GRIDS_WIDE
    return dict(label=LABEL, commit=_git("rev-parse", "HEAD"),
                src_experiments_tests_dirty=_git("status", "--porcelain", "--", "src", "experiments", "tests") or "",
                src_diff_vs_a10efe6=_git("diff", "--stat", "a10efe6", "HEAD", "--", "src", "experiments", "tests") or "",
                driver=os.path.relpath(os.path.abspath(__file__), ROOT), driver_sha256=_sha(os.path.abspath(__file__)),
                platform=platform.platform(), python=sys.version.split()[0], numpy=np.__version__,
                scipy=scipy.__version__, sklearn=sklearn.__version__, workers=workers,
                threads={v: os.environ.get(v) for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
                sets={s: dict(seeds=list(SETS[s]["seeds"]), scenarios=list(SETS[s]["scenarios"]),
                              families=list(SETS[s]["families"]), cfg_overrides=SETS[s]["cfg"],
                              pipeline_config=make_cfg(SETS[s]["cfg"]).to_dict(), cfg_sha=cfg_sha(make_cfg(SETS[s]["cfg"])))
                      for s in sets},
                prism_config=str(PrismConfig()), grids=GRIDS, grids_wide=GRIDS_WIDE,
                started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def _keep_awake(on):
    if os.name != "nt":
        return
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def run(out, set_names, workers, seeds_override=None):
    os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(out, "run.log"), "a", encoding="utf-8", newline="\n")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
        logf.write(line + "\n")
        logf.flush()
        print(line, flush=True)

    env = environment(set_names, workers)
    envs = []
    ep = os.path.join(out, "environment.json")
    if os.path.exists(ep):
        envs = json.load(open(ep, encoding="utf-8")).get("runs", [])
    envs.append(env)
    json.dump(dict(runs=envs), open(ep, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
    if env["src_experiments_tests_dirty"]:
        log("STOP: src/, experiments/ or tests/ has local changes; the frozen code must be clean")
        return 1
    commit = env["commit"][:7]
    groups, want = [], {}
    for sn in set_names:
        S = SETS[sn]
        want[sn] = cfg_sha(make_cfg(S["cfg"]))
        for seed in (seeds_override or S["seeds"]):
            for fam in S["families"]:
                groups.append(Group(sn, seed, fam, S["scenarios"]))
    G = {(g.set, g.seed, g.fam): g for g in groups}
    log(f"start: sets {set_names}, {len(groups)} groups, workers {workers}, commit {commit}, driver {env['driver_sha256'][:12]}")
    _keep_awake(True)
    pending, inflight, failures, reused, ran = {}, set(), [], 0, 0
    os.makedirs(os.path.join(out, "groups"), exist_ok=True)

    def advance(g, ex):
        """Move a group forward with the rows already present; submit what it still needs."""
        nonlocal reused
        while True:
            if g.state == "val":
                need = [p for p in g.grid + g.expansions if p not in g.val]
                if need:
                    return [dict(out=out, set=g.set, seed=g.seed, family=g.fam, param=p, week="val",
                                 scenario="validation") for p in need]
                kind, v = g.select()
                if kind == "expand":
                    g.expansions.append(v)
                    continue
                g.sel, g.state = v, "test"
            if g.state == "test":
                need = [sc for sc in g.scenarios if sc not in g.tests]
                if need:
                    return [dict(out=out, set=g.set, seed=g.seed, family=g.fam, param=g.sel, week="test", scenario=sc)
                            for sc in need]
                gp = os.path.join(out, "groups", g.set, f"group_{g.seed}_{g.fam}.json")
                os.makedirs(os.path.dirname(gp), exist_ok=True)
                with open(gp, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(g.record(commit), fh, indent=1)
                g.state = "done"
                log(f"group done {g.set} {g.seed} {g.fam}: selected {g.sel} expansions {g.expansions or '-'}")
            return []

    def place(g, t, row):
        if t["week"] == "val":
            g.val[t["param"]] = row
        else:
            g.tests[t["scenario"]] = row

    bkey = {id(g): (g.seed, want[g.set]) for g in groups}
    bover = {(g.seed, want[g.set]): SETS[g.set]["cfg"] for g in groups}
    ready = {k for k in bover if os.path.exists(bundle_file(out, *k))}
    bman_p = os.path.join(out, "bundles.json")
    bman = json.load(open(bman_p, encoding="utf-8")) if os.path.exists(bman_p) else {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for k in sorted(set(bover) - ready):
            pending[ex.submit(bundle_task, dict(out=out, seed=k[0], cfg=bover[k]))] = ("B", k)
        queue = []
        for g in groups:
            if bkey[id(g)] in ready:
                queue += [(g, t) for t in g.tasks_val(out)]
        last_beat = time.time()
        while True:
            # resolve every queued task from the cache if possible, submit the rest
            nq = []
            for g, t in queue:
                r = load_week(out, t, want[g.set])
                if r is not None:
                    place(g, t, r)
                    reused += 1
                    continue
                nq.append((g, t))
            queue = []
            for g, t in nq:
                key = (t["set"], t["seed"], t["family"], t["week"], t["scenario"], t["param"])
                if key in inflight:
                    continue
                inflight.add(key)
                pending[ex.submit(week_task, t)] = (g, t)
            for g in groups:
                if bkey[id(g)] not in ready:
                    continue
                if g.state != "done" and not any(v[0] is g for v in pending.values()):
                    queue += [(g, t) for t in advance(g, ex)]
            if not queue and not pending:
                break
            if not pending:
                continue
            done, _ = wait(list(pending), timeout=60, return_when=FIRST_COMPLETED)
            now = time.time()
            if now - last_beat > 300:
                log(f"GAP: {now - last_beat:.0f} s since the last heartbeat (suspension or stall)")
            last_beat = now
            if not done:
                log(f"heartbeat: {len(pending)} running/queued, {ran} weeks run, {reused} reused, "
                    f"{sum(g.state == 'done' for g in groups)}/{len(groups)} groups done")
                continue
            for f in done:
                entry = pending.pop(f)
                if entry[0] == "B":
                    try:
                        info = f.result()
                    except Exception:
                        failures.append(dict(task=dict(bundle=entry[1]), error=traceback.format_exc()))
                        log(f"FAILED bundle {entry[1]}")
                        continue
                    ready.add(entry[1])
                    bman[f"{info['seed']}_{info['cfg_sha']}"] = info
                    json.dump(bman, open(bman_p, "w", encoding="utf-8", newline=chr(10)), indent=1)
                    log(f"bundle {info['seed']} {info['cfg_sha']}: built in {info['build_s']} s, {info['bytes']} bytes")
                    continue
                g, t = entry
                inflight.discard((t["set"], t["seed"], t["family"], t["week"], t["scenario"], t["param"]))
                try:
                    row = f.result()
                except Exception:
                    failures.append(dict(task={k: v for k, v in t.items() if k != "out"}, error=traceback.format_exc()))
                    log(f"FAILED {t['set']} {t['seed']} {t['family']} {t['week']} {t['scenario']} {t['param']}")
                    g.state = "failed"
                    continue
                ran += 1
                place(g, t, row)
                log(f"week {t['set']} {t['seed']} {t['family']} {t['week']} {t['scenario']} {t['param']}: "
                    f"{row['runtime_s']} s, cost {row['cost']:.1f}, violating {100 * row['violating_window_rate']:.2f}%")
    _keep_awake(False)
    json.dump(failures, open(os.path.join(out, "failures.json"), "w", encoding="utf-8", newline="\n"), indent=1)
    log(f"end: {ran} weeks run, {reused} reused from cache, {len(failures)} failures, "
        f"{sum(g.state == 'done' for g in groups)}/{len(groups)} groups done")
    return 0 if not failures else 1


# ------------------------------------------------------------------ trace provenance
def verify_traces(out, seeds):
    from dataclasses import asdict
    from prism_repro.workload import SCENARIOS, WorkloadParams, generate_trace
    man = json.load(open(os.path.join(ROOT, "data", "trace_set_revision.json"), encoding="utf-8"))
    h = lambda c: hashlib.sha256(np.ascontiguousarray(c, dtype="<i8").tobytes()).hexdigest()  # noqa: E731
    rows, bad = [], []
    for s in seeds:
        for sc in SCENARIOS:
            tr = generate_trace(s, sc)
            got = h(tr["counts"])
            ok = got == man["counts_sha256"][str(s)][sc]
            rows.append(dict(seed=s, scenario=sc, sha256=got, matches_manifest=ok, minutes=int(len(tr["counts"])),
                             total=int(tr["counts"].sum())))
            if not ok:
                bad.append((s, sc))
        base = generate_trace(s, "stationary")["counts"][:21 * 1440]
        for sc in SCENARIOS[1:]:
            if not np.array_equal(generate_trace(s, sc)["counts"][:21 * 1440], base):
                bad.append((s, sc, "first 21 days differ"))
    wp_ok = json.loads(json.dumps(asdict(WorkloadParams()))) == man["workload_params"]   # tuples vs JSON lists
    rep = dict(manifest_commit=_git("log", "-1", "--format=%h %cd", "--date=iso", "--", "data/trace_set_revision.json"),
               manifest_unchanged_since_4c43769=subprocess.run(["git", "-C", ROOT, "diff", "--quiet", "4c43769", "--",
                                                               "data/trace_set_revision.json"]).returncode == 0,
               prespecification_commit=_git("log", "-1", "--format=%h %cd", "--date=iso", "--", "docs/revision/PRESPECIFICATION.md"),
               seed_roles=dict(original=man["original_seeds"], confirmatory=man["new_seeds"]),
               workload_params_equal_manifest=wp_ok, checked=len(rows), mismatches=bad, rows=rows)
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "trace_verification.json"), "w", encoding="utf-8", newline="\n"), indent=1)
    print(f"traces: {len(rows)} seed-scenario counts checked, {len(rows) - len([b for b in bad if len(b) == 2])} match "
          f"the manifest; mismatches {bad or 'none'}; workload params equal manifest: {wp_ok}")
    return 0 if not bad and wp_ok else 1


# ------------------------------------------------------------------ analysis (PRESPECIFICATION.md section 5)
def _t(x):
    from scipy import stats
    x = np.asarray(x, float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean()), float(h)


def analyse(out):
    import csv
    lines, checks, tables = [], {}, {}
    P = lines.append
    envs = json.load(open(os.path.join(out, "environment.json"), encoding="utf-8"))["runs"]
    P(LABEL)
    P(f"runs: {len(envs)}; commits {sorted({e['commit'][:7] for e in envs})}; drivers {sorted({e['driver_sha256'][:12] for e in envs})}; "
      f"{envs[0]['platform']}; Python {envs[0]['python']}, numpy {envs[0]['numpy']}, scipy {envs[0]['scipy']}, "
      f"scikit-learn {envs[0]['sklearn']}")
    comps = {"C1C2": (("C1", "QuantProv_q90"), ("C2", "Reactive")), "C3": (("C3", "MemAdapt_q90"),)}
    for sn in ("C1C2", "C3"):
        gdir = os.path.join(out, "groups", sn)
        if not os.path.isdir(gdir):
            continue
        S = SETS[sn]
        G = {(g["seed"], g["family"]): g for g in (json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(gdir, "group_*.json")))}
        exp_groups = len(S["seeds"]) * len(S["families"])
        checks[f"{sn}: groups complete"] = (len(G), exp_groups)
        dup = []
        for (s, f), g in G.items():
            ps = [r["param"] for r in g["validation"]]
            if len(ps) != len(set(ps)):
                dup.append((s, f))
            if sorted(set(g["grid"]) - set(ps)):
                dup.append((s, f, "grid incomplete"))
            if [t["scenario"] for t in g["tests"]] != list(S["scenarios"]):
                dup.append((s, f, "tests incomplete"))
            if any(s < 106 for s in [g["seed"]]):
                dup.append((s, f, "development seed in a confirmatory set"))
        checks[f"{sn}: duplicate or incomplete groups"] = dup
        # identical workloads: every family saw the same request counts per seed, week and scenario
        same = True
        for s in S["seeds"]:
            fams = [f for f in S["families"] if (s, f) in G]
            for sc in S["scenarios"]:
                ns = {G[(s, f)]["tests"][S["scenarios"].index(sc)]["n_requests"] for f in fams}
                same &= len(ns) <= 1
            nv = {r["n_requests"] for f in fams for r in G[(s, f)]["validation"]}
            same &= len(nv) <= 1
        checks[f"{sn}: identical request counts across families per seed and week"] = same
        P(f"\n## {sn}: deadline {make_cfg(S['cfg']).deadline} s, non-scaling {make_cfg(S['cfg']).nonscaling}; "
          f"scenarios {', '.join(S['scenarios'])}; seeds {S['seeds'][0]}-{S['seeds'][-1]}")
        sel_rows = []
        for f in S["families"]:
            gs = [G[(s, f)] for s in S["seeds"] if (s, f) in G]
            edges = [g["seed"] for g in gs if g["edge_hit"]]
            exps = [g["seed"] for g in gs if g["expansions"]]
            vals = sorted({g["selected"] for g in gs})
            P(f"  {f:14s} selected values {vals}; expansions on {len(exps)} traces; edge hits after expansion "
              f"{len(edges)} {edges if edges else ''}")
            for g in gs:
                v = next(r for r in g["validation"] if r["param"] == g["selected"])
                sel_rows.append(dict(set=sn, family=f, seed=g["seed"], selected=g["selected"],
                                     expansions=";".join(map(str, g["expansions"])), edge_hit=g["edge_hit"],
                                     val_cost=round(v["cost"], 2), val_violating_pct=round(100 * v["violating_window_rate"], 3)))
        tables[f"{sn}_selections.csv"] = sel_rows
        per_trace = []
        for s in S["seeds"]:
            for f in S["families"]:
                g = G.get((s, f))
                if not g:
                    continue
                c = [t["cost"] for t in g["tests"]]
                v = [t["violating_window_rate"] for t in g["tests"]]
                per_trace.append(dict(set=sn, seed=s, family=f, selected=g["selected"], weekly_cost=round(float(np.mean(c)), 3),
                                      violating_pct=round(100 * float(np.mean(v)), 4),
                                      weeks_meeting_2pct=int(sum(x <= 0.02 + 1e-12 for x in v)), test_weeks=len(v),
                                      **{f"cost_{t['scenario']}": round(t["cost"], 3) for t in g["tests"]},
                                      **{f"violating_pct_{t['scenario']}": round(100 * t["violating_window_rate"], 4) for t in g["tests"]}))
        tables[f"{sn}_per_trace.csv"] = per_trace
        PT = {(r["seed"], r["family"]): r for r in per_trace}
        for f in S["families"]:
            rs = [PT[(s, f)] for s in S["seeds"] if (s, f) in PT]
            if rs:
                P(f"  {f:14s} mean weekly cost {np.mean([r['weekly_cost'] for r in rs]):8.1f} USD; pooled violating "
                  f"{np.mean([r['violating_pct'] for r in rs]):5.2f}%; weeks meeting 2%: "
                  f"{sum(r['weeks_meeting_2pct'] for r in rs)} of {sum(r['test_weeks'] for r in rs)}")
        paired = []
        for cname, comp in comps[sn]:
            ok = [s for s in S["seeds"] if (s, "PRISM") in PT and (s, comp) in PT]
            if len(ok) < 2:
                continue
            dc = [100 * (PT[(s, "PRISM")]["weekly_cost"] / PT[(s, comp)]["weekly_cost"] - 1) for s in ok]
            dv = [PT[(s, "PRISM")]["violating_pct"] - PT[(s, comp)]["violating_pct"] for s in ok]
            (mc, hc), (mv, hv) = _t(dc), _t(dv)
            lo, hi = mc - hc, mc + hc
            cost_call = ("difference: PRISM cheaper" if hi < 0 else "difference: PRISM costlier" if lo > 0 else
                         "tie (interval within +/-2%)" if lo >= -2 and hi <= 2 else "not distinguishable (includes 0, exceeds +/-2%)")
            similar = (mv - hv) >= -0.5 and (mv + hv) <= 0.5
            comp_call = "similar compliance (within +/-0.5 points)" if similar else "cost comparison confounded by compliance"
            P(f"  {cname}: PRISM minus {comp}, n = {len(ok)} traces (df {len(ok) - 1}): cost {mc:+.2f}% "
              f"[{lo:+.2f}, {hi:+.2f}] -> {cost_call}; violating windows {mv:+.3f} points [{mv - hv:+.3f}, {mv + hv:+.3f}] "
              f"-> {comp_call}. Traces: PRISM cheaper {sum(x < 0 for x in dc)}, costlier {sum(x > 0 for x in dc)}; "
              f"fewer violating {sum(x < 0 for x in dv)}, more {sum(x > 0 for x in dv)}, equal {sum(x == 0 for x in dv)}")
            paired.append(dict(comparison=cname, comparator=comp, n_traces=len(ok), cost_pct_mean=round(mc, 3),
                               cost_pct_lo=round(lo, 3), cost_pct_hi=round(hi, 3), cost_call=cost_call,
                               violating_pts_mean=round(mv, 4), violating_pts_lo=round(mv - hv, 4),
                               violating_pts_hi=round(mv + hv, 4), compliance_call=comp_call,
                               traces_prism_cheaper=sum(x < 0 for x in dc), traces_prism_costlier=sum(x > 0 for x in dc),
                               traces_prism_fewer_violating=sum(x < 0 for x in dv), traces_prism_more_violating=sum(x > 0 for x in dv)))
            # exploratory: per-scenario breakdown (PRESPECIFICATION.md section 6, last paragraph)
            for sc in S["scenarios"]:
                dcs = [100 * (PT[(s, "PRISM")][f"cost_{sc}"] / PT[(s, comp)][f"cost_{sc}"] - 1) for s in ok]
                dvs = [PT[(s, "PRISM")][f"violating_pct_{sc}"] - PT[(s, comp)][f"violating_pct_{sc}"] for s in ok]
                (a, ha), (bm, hb) = _t(dcs), _t(dvs)
                paired.append(dict(comparison=f"{cname} [{sc}, EXPLORATORY]", comparator=comp, n_traces=len(ok),
                                   cost_pct_mean=round(a, 3), cost_pct_lo=round(a - ha, 3), cost_pct_hi=round(a + ha, 3),
                                   cost_call="", violating_pts_mean=round(bm, 4), violating_pts_lo=round(bm - hb, 4),
                                   violating_pts_hi=round(bm + hb, 4), compliance_call="",
                                   traces_prism_cheaper=sum(x < 0 for x in dcs), traces_prism_costlier=sum(x > 0 for x in dcs),
                                   traces_prism_fewer_violating=sum(x < 0 for x in dvs), traces_prism_more_violating=sum(x > 0 for x in dvs)))
        tables[f"{sn}_paired.csv"] = paired
        rt = [r["runtime_s"] for g in G.values() for r in g["validation"] + g["tests"]]
        if rt:
            P(f"  runtime: {len(rt)} closed-loop weeks, median {np.median(rt):.0f} s, total {sum(rt) / 3600:.1f} CPU-h")
    P("\n## Checks")
    for k, v in checks.items():
        P(f"  {k}: {v}")
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    for name, rows in tables.items():
        if rows:
            keys = list(dict.fromkeys(k for r in rows for k in r))
            with open(os.path.join(out, "tables", name), "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
    open(os.path.join(out, "summary.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    json.dump(checks, open(os.path.join(out, "analysis_checks.json"), "w", encoding="utf-8", newline="\n"), indent=1, default=str)
    print("\n".join(lines))
    return 0


def _seeds(arg):
    a, _, b = arg.partition("-")
    return tuple(range(int(a), int(b) + 1)) if b else tuple(int(x) for x in a.split(","))


if __name__ == "__main__":
    cmd, out = sys.argv[1], sys.argv[2]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[3:] if a.startswith("--") and "=" in a)
    seeds = _seeds(opts["seeds"]) if "seeds" in opts else None
    if cmd == "run":
        sys.exit(run(out, opts.get("sets", "C1C2,C3").split(","), int(opts.get("workers", 6)), seeds))
    if cmd == "analyse":
        sys.exit(analyse(out))
    if cmd == "verify-traces":
        sys.exit(verify_traces(out, seeds or CONF_SEEDS))
    raise SystemExit(__doc__)
