#!/usr/bin/env python3
"""Checkpoint check before resuming the C1-C3 run (no simulation; reads files only).

Checks the saved weeks (parse, required fields, path/field agreement, duplicates, one cfg_sha per set, one
counts_sha256 per trace week), the trace bundles (bytes and SHA-256 against bundles.json), leftover temporary
files, and the FAILED lines of run.log (whether each interrupted week has since been saved or is still to run).

usage: python checkpoint_check.py <run dir> <output json>
"""
import collections
import hashlib
import json
import os
import re
import sys

RUN, OUT = sys.argv[1], sys.argv[2]
KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "overflow_share", "p99_latency")
REQ = ("week", "param", "scenario", "seed", "family", "set", "cfg_sha", "counts_sha256", "finished_utc") + KEYS
problems, weeks = [], {}
for root, _, files in os.walk(os.path.join(RUN, "weeks")):
    for fn in files:
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, RUN).replace(os.sep, "/")
        if not fn.endswith(".json"):
            problems.append(f"unexpected file {rel}")
            continue
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception as e:                                   # noqa: BLE001
            problems.append(f"unreadable {rel}: {e}")
            continue
        miss = [k for k in REQ if k not in r]
        if miss:
            problems.append(f"{rel} missing {miss}")
            continue
        _, st, seed, fam, name = rel.split("/")
        wk, rest = name[:-5].split("_", 1)
        sc, par = rest.rsplit("_", 1)
        if (st, int(seed), fam, wk, sc, float(par)) != (r["set"], r["seed"], r["family"], r["week"], r["scenario"],
                                                       float(r["param"])):
            problems.append(f"{rel} path and fields disagree")
        key = (r["set"], r["seed"], r["family"], r["week"], r["scenario"], float(r["param"]))
        if key in weeks:
            problems.append(f"duplicate {key}")
        weeks[key] = r
cfg = collections.defaultdict(set)
cnt = collections.defaultdict(set)
for (st, seed, fam, wk, sc, par), r in weeks.items():
    cfg[st].add(r["cfg_sha"])
    cnt[(seed, wk, sc)].add(r["counts_sha256"])
for st, v in cfg.items():
    if len(v) != 1:
        problems.append(f"set {st} has {len(v)} cfg_sha values")
for k, v in cnt.items():
    if len(v) != 1:
        problems.append(f"trace week {k} has {len(v)} counts hashes")
man = json.load(open(os.path.join(RUN, "bundles.json"), encoding="utf-8"))
bundles_ok = 0
for k, m in man.items():
    p = os.path.join(RUN, "bundles", f"bundle_{m['seed']}_{m['cfg_sha']}.pkl")
    if not os.path.exists(p):
        problems.append(f"bundle missing {os.path.basename(p)}")
        continue
    b = open(p, "rb").read()
    if len(b) != m["bytes"] or hashlib.sha256(b).hexdigest() != m["sha256"]:
        problems.append(f"bundle mismatch {os.path.basename(p)}")
    else:
        bundles_ok += 1
tmp = [os.path.relpath(os.path.join(rt, f), RUN) for rt, _, fs in os.walk(RUN) for f in fs if ".tmp" in f]
problems += [f"temporary file {t}" for t in tmp]
failed = []
pat = re.compile(r"^(\S+) FAILED (\S+) (\d+) (\S+) (\S+) (\S+) (\S+)$")
for line in open(os.path.join(RUN, "run.log"), encoding="utf-8"):
    m = pat.match(line.strip())
    if m:
        t, st, seed, fam, wk, sc, par = m.groups()
        failed.append(dict(logged_utc=t, set=st, seed=int(seed), family=fam, week=wk, scenario=sc, param=float(par),
                           saved_since=(st, int(seed), fam, wk, sc, float(par)) in weeks))
per = collections.Counter((k[0], k[2]) for k in weeks)
res = dict(run_dir=os.path.basename(os.path.abspath(RUN)), weeks_saved=len(weeks),
           weeks_by_set_family={f"{a}/{b}": n for (a, b), n in sorted(per.items())},
           seeds_with_weeks={st: sorted({k[1] for k in weeks if k[0] == st}) for st in sorted(cfg)},
           cfg_sha=({st: sorted(v) for st, v in cfg.items()}), bundles_in_manifest=len(man), bundles_verified=bundles_ok,
           temporary_files=len(tmp), failed_lines=failed,
           failed_saved_since=sum(f["saved_since"] for f in failed), problems=problems, ok=not problems)
json.dump(res, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "failed_lines"}, indent=1))
for f in failed:
    print("FAILED line:", f["set"], f["seed"], f["family"], f["week"], f["param"], "saved since" if f["saved_since"] else "still to run")
