#!/usr/bin/env python3
"""Independent verification of the C1-C3 run directory (read-only, except the optional determinism rerun's own files).

Checks:
  1. coverage: every (set, seed, family) group exists; its validation rows cover the whole initial grid plus exactly the
     recorded expansions; its test rows cover the set's scenarios at the selected value;
  2. selection: the selection and the expansion sequence replay from the validation rows alone, by the prespecified
     rule (experiment.select_by_rule and the GRIDS_WIDE expansion), so no test outcome entered a selection;
  3. failures and retries: every week the run log ever marked FAILED now has a valid saved row; failures.json empty;
  4. duplicates: one saved week file per task, one row per parameter in a group, no week file outside a group;
  5. provenance: every row carries the set's configuration hash; per seed, week and scenario every family saw the same
     request count and the same trace-counts hash, and that hash equals the hash of the manifest-verified trace;
     the environment of every run segment records the same commit, clean src/experiments/tests and no diff to a10efe6;
  6. determinism (optional, --rerun=N): N randomly chosen saved weeks are recomputed and must match in every field but
     wall time, process id and finish time.

usage (from prism-repro/): python docs/revision/confirmatory_20261122/verify_run.py <run dir> [--rerun=2]
"""
import glob
import hashlib
import json
import os
import random
import re
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "revision"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import closed_loop_confirmatory as D                                         # noqa: E402
from prism_repro.experiment import GRIDS, GRIDS_WIDE, WEEK_START, select_by_rule  # noqa: E402
from prism_repro.workload import generate_trace                              # noqa: E402

RUN = sys.argv[1]
rerun = int(next((a.split("=")[1] for a in sys.argv[2:] if a.startswith("--rerun=")), "0"))
rep, problems = {}, []
want = {s: D.cfg_sha(D.make_cfg(D.SETS[s]["cfg"])) for s in ("C1C2", "C3")}
G = {}
for s in ("C1C2", "C3"):
    for p in glob.glob(os.path.join(RUN, "groups", s, "group_*.json")):
        g = json.load(open(p, encoding="utf-8"))
        G[(s, g["seed"], g["family"])] = g
exp_groups = [(s, seed, f) for s in ("C1C2", "C3") for seed in D.SETS[s]["seeds"] for f in D.SETS[s]["families"]]
missing = [k for k in exp_groups if k not in G]
rep["groups"] = dict(expected=len(exp_groups), present=len(G), missing=missing)
if missing:
    problems.append(f"{len(missing)} groups missing")
# 1-2. coverage and selection replay
cov_bad, sel_bad = [], []
for (s, seed, fam), g in G.items():
    _, gname = D.FAMILIES[fam]
    grid, wide = list(GRIDS[gname]), list(GRIDS_WIDE[gname])
    vparams = [r["param"] for r in g["validation"]]
    if sorted(vparams) != sorted(set(grid) | set(g["expansions"])) or len(vparams) != len(set(vparams)):
        cov_bad.append((s, seed, fam, "validation grid"))
    if [t["scenario"] for t in g["tests"]] != list(D.SETS[s]["scenarios"]) or any(t["param"] != g["selected"] for t in g["tests"]):
        cov_bad.append((s, seed, fam, "test weeks"))
    # replay: the pilot's loop on the validation rows only
    val = {r["param"]: r for r in g["validation"] if r["param"] in grid}
    exps = []
    while True:
        rows = [dict(param=p, cost=r["cost"], violating_window_rate=r["violating_window_rate"]) for p, r in val.items()]
        sel = select_by_rule(rows)["param"]
        ps = sorted(val)
        nxt = None
        if sel == ps[0]:
            lower = [q for q in wide if q < ps[0]]
            nxt = max(lower) if lower else None
        elif sel == ps[-1]:
            upper = [q for q in wide if q > ps[-1]]
            nxt = min(upper) if upper else None
        if nxt is None:
            break
        exps.append(nxt)
        r = next((x for x in g["validation"] if x["param"] == nxt), None)
        if r is None:
            sel_bad.append((s, seed, fam, f"expansion {nxt} has no validation row"))
            break
        val[nxt] = r
    if sel != g["selected"] or exps != g["expansions"]:
        sel_bad.append((s, seed, fam, f"replayed {sel} {exps} vs recorded {g['selected']} {g['expansions']}"))
rep["coverage_problems"] = cov_bad
rep["selection_replay_problems"] = sel_bad
problems += [f"coverage: {x}" for x in cov_bad] + [f"selection: {x}" for x in sel_bad]
# 3. failures and retries
log = open(os.path.join(RUN, "run.log"), encoding="utf-8").read()
failed = set(re.findall(r"FAILED (\S+) (\d+) (\S+) (\S+) (\S+) (\S+)", log))
unresolved = []
for (s, seed, fam, week, sc, param) in failed:
    t = dict(out=RUN, set=s, seed=int(seed), family=fam, week=week, scenario=sc, param=float(param))
    if D.load_week(RUN, t, want[s]) is None:
        unresolved.append((s, seed, fam, week, sc, param))
fj = os.path.join(RUN, "failures.json")
fails_now = json.load(open(fj, encoding="utf-8")) if os.path.exists(fj) else []
rep["failures"] = dict(logged_failed_tasks=len(failed), retried_and_saved=len(failed) - len(unresolved),
                       unresolved=unresolved, failures_json_entries=len(fails_now),
                       run_segments=len(re.findall(r" start: ", log)), gaps=re.findall(r"GAP: [^\n]*", log))
if unresolved or fails_now:
    problems.append("unresolved failures")
# 4. duplicates and orphan week files
files = glob.glob(os.path.join(RUN, "weeks", "*", "*", "*", "*.json"))
in_groups = set()
for (s, seed, fam), g in G.items():
    for r in g["validation"]:
        in_groups.add(os.path.normpath(D.week_file(RUN, dict(set=s, seed=seed, family=fam, week="val", scenario="validation", param=r["param"]))))
    for t in g["tests"]:
        in_groups.add(os.path.normpath(D.week_file(RUN, dict(set=s, seed=seed, family=fam, week="test", scenario=t["scenario"], param=t["param"]))))
outside = sorted(os.path.relpath(f, RUN) for f in files if os.path.normpath(f) not in in_groups)
tmp = glob.glob(os.path.join(RUN, "weeks", "**", "*.tmp*"), recursive=True)
rep["duplicates"] = dict(week_files=len(files), weeks_in_groups=len(in_groups), files_outside_groups=outside, tmp_files=len(tmp))
if tmp:
    problems.append("temporary files left")
# 5. provenance
cfg_bad = [os.path.relpath(f, RUN) for f in files if json.load(open(f, encoding="utf-8")).get("cfg_sha") != want[json.load(open(f, encoding="utf-8"))["set"]]]
man = json.load(open(os.path.join(ROOT, "data", "trace_set_revision.json"), encoding="utf-8"))
h = lambda c: hashlib.sha256(np.ascontiguousarray(c, dtype="<i8").tobytes()).hexdigest()  # noqa: E731
prov_bad, checked = [], 0
for s in ("C1C2", "C3"):
    for seed in D.SETS[s]["seeds"]:
        traces = {}
        for (ss, sd, fam), g in G.items():
            if ss != s or sd != seed:
                continue
            for r in g["validation"] + g["tests"]:
                sc = "stationary" if r["week"] == "val" else r["scenario"]
                key = (r["week"], sc)
                if sc not in traces:
                    tr = generate_trace(seed, sc)["counts"]
                    assert h(tr) == man["counts_sha256"][str(seed)][sc]
                    traces[sc] = tr
                ws = WEEK_START[r["week"]]
                if r["counts_sha256"] != h(traces[sc][ws:ws + 7 * 1440]):
                    prov_bad.append((s, seed, fam, key))
                checked += 1
envs = json.load(open(os.path.join(RUN, "environment.json"), encoding="utf-8"))["runs"]
env_ok = all(e["commit"] == envs[0]["commit"] and not e["src_experiments_tests_dirty"] and not e["src_diff_vs_a10efe6"]
             and e["driver_sha256"] == envs[0]["driver_sha256"] for e in envs)
rep["provenance"] = dict(rows_with_wrong_cfg=cfg_bad, rows_checked_against_trace_hash=checked, trace_hash_mismatches=prov_bad,
                         run_segments=len(envs), segments_same_commit_clean_same_driver=env_ok,
                         commit=envs[0]["commit"], driver_sha256=envs[0]["driver_sha256"])
if cfg_bad or prov_bad or not env_ok:
    problems.append("provenance")
# 6. determinism
if rerun:
    random.seed(20261123)
    picks = random.sample(sorted(files), rerun)
    det = []
    for f in picks:
        r0 = json.load(open(f, encoding="utf-8"))
        t = dict(out=os.path.join(RUN, "determinism_check"), set=r0["set"], seed=r0["seed"], family=r0["family"],
                 week=r0["week"], scenario=r0["scenario"], param=r0["param"])
        D._BUNDLES.clear()
        p_b = D.bundle_file(RUN, r0["seed"], r0["cfg_sha"])
        os.makedirs(os.path.join(t["out"], "bundles"), exist_ok=True)
        dst = D.bundle_file(t["out"], r0["seed"], r0["cfg_sha"])
        if not os.path.exists(dst):
            import shutil
            shutil.copyfile(p_b, dst)
        r1 = D.week_task(t)
        skip = {"runtime_s", "pid", "finished_utc"}
        diff = {k: (r0.get(k), r1.get(k)) for k in set(r0) | set(r1) if k not in skip and r0.get(k) != r1.get(k)}
        det.append(dict(week=os.path.relpath(f, RUN), identical=not diff, differences=diff))
    rep["determinism_rerun"] = det
    if not all(d["identical"] for d in det):
        problems.append("determinism")
rep["problems"] = problems
rep["ok"] = not problems
json.dump(rep, open(os.path.join(RUN, "verification.json"), "w", encoding="utf-8", newline="\n"), indent=1, default=str)
print(json.dumps({k: v for k, v in rep.items() if k not in ("provenance",)}, indent=1, default=str)[:4000])
print("provenance:", {k: v for k, v in rep["provenance"].items() if k != "rows_with_wrong_cfg"}, "wrong cfg rows:", len(rep["provenance"]["rows_with_wrong_cfg"]))
sys.exit(0 if rep["ok"] else 1)
