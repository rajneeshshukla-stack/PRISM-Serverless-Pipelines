#!/usr/bin/env python3
"""R3.6: rebuild the label-fix analysis outputs from completed experiment rows, into a fresh directory (no simulation).

Inputs: a checkout of the repository's prism-repro (6e0f05c or later; it provides src/, experiments/, scripts/ and the
stored results/tables/revision/pc_billing_runs.csv), and the stored rows of the completed experiments
(results/raw/<EXP>/rows.jsonl and arrays_*.npz) as the current code wrote them, i.e. with PRISM's main configuration
labelled 'PRISM_EB'. Supply E1 and any of E3, E7, E9; supply E11 and E11occ for the E11 table.

Steps (all into <out>, which must not exist):
  1. tree/      copy of src/, experiments/, scripts/ and the input rows; checks that E1 holds the main configuration as
                'PRISM_EB' (no 'PRISM' rows) and that run_experiments.selections() returns it under "PRISM";
  2. tree/      python scripts/analyze.py (the normal command; reads the 'PRISM_EB' rows directly); checks that every
                Table V scenario has a PRISM row over all traces and that E1_selected_parameters lists the same PRISM eps;
  3. analysis/  label normalisation (tools/normalize_labels.py, needed by the scripts/revision analyses, which select
                PRISM by the literal 'PRISM'), then scripts/revision/pc_billing_bounds.py and tools/r76_matched_1pct.py
                (R7.6, POST HOC), and the full-precision interval endpoints (r76_endpoints.json);
  4. analysis/  if E11 and E11occ are supplied: tools/e11_occupancy.py table (Eq. (5) against Erlang-B, with its
                risk-model assertions);
  5. MANIFEST.sha256 of every output (LF).

usage: python reproduce_analysis.py --code <prism-repro checkout> --out <new dir> --input EXP=<dir with EXP/> [...]
       [--python <interpreter>]   (default: this interpreter)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
ap = argparse.ArgumentParser()
ap.add_argument("--code", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--input", action="append", required=True, help="EXP=DIR, DIR containing EXP/rows.jsonl")
ap.add_argument("--python", default=sys.executable)
a = ap.parse_args()
CODE, OUT = os.path.abspath(a.code), os.path.abspath(a.out)
if os.path.exists(OUT):
    sys.exit(f"{OUT} exists; use a fresh output directory")
inputs = dict(x.split("=", 1) for x in a.input)
if "E1" not in inputs:
    sys.exit("E1 is required")
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
           OPENBLAS_NUM_THREADS="1")
ENV.pop("PRISM_RESULTS", None)
log = []


def say(msg):
    log.append(msg)
    print(msg, flush=True)


def run(args, cwd, stdout=None):
    say("$ " + " ".join(os.path.relpath(x, OUT) if os.path.isabs(x) and x.startswith(OUT) else x for x in args))
    r = subprocess.run(args, cwd=cwd, env=ENV, stdout=stdout or subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        sys.exit(f"failed ({r.returncode}): {' '.join(args)}\n{r.stderr[-2000:]}")
    return r


def make_tree(dst):
    for d in ("src", "experiments", "scripts"):
        shutil.copytree(os.path.join(CODE, d), os.path.join(dst, d), ignore=shutil.ignore_patterns("__pycache__"))
    for exp, src in inputs.items():
        shutil.copytree(os.path.join(src, exp), os.path.join(dst, "results", "raw", exp))
    os.makedirs(os.path.join(dst, "results", "tables", "revision"), exist_ok=True)


checks = {}
# 1. tree and input checks
TREE = os.path.join(OUT, "tree")
make_tree(TREE)
rows = [json.loads(l) for l in open(os.path.join(TREE, "results", "raw", "E1", "rows.jsonl"), encoding="utf-8")]
pol = {r["policy"] for r in rows}
n_eb = sum(r["policy"] == "PRISM_EB" for r in rows)
checks["E1 rows"] = len(rows)
checks["E1 main-configuration rows labelled PRISM_EB"] = n_eb
checks["E1 rows labelled PRISM (must be 0)"] = sum(r["policy"] == "PRISM" for r in rows)
assert n_eb > 0 and "PRISM" not in pol, "E1 must hold the main configuration as 'PRISM_EB' and no 'PRISM' rows"
probe = ("import sys, json; sys.path.insert(0, 'experiments'); import run_experiments as RX; "
         "print(json.dumps({s: RX.selections(s)['PRISM'] for s in sorted({r['seed'] for r in RX.load_rows('E1')})}))")
sel = json.loads(run([a.python, "-c", probe], TREE).stdout.strip().splitlines()[-1])
checks["selections()['PRISM'] (main configuration, from PRISM_EB rows)"] = {k: v["param"] for k, v in sel.items()}

# 2. normal-path analysis
with open(os.path.join(OUT, "analyze.stdout.txt"), "w", encoding="utf-8") as f:
    run([a.python, os.path.join("scripts", "analyze.py")], TREE, stdout=f)
t5 = open(os.path.join(TREE, "results", "tables", "T5_test_weeks.md"), encoding="utf-8").read()
prism_t5 = [l for l in t5.splitlines() if re.match(r"\|\s*\w+\s*\|\s*PRISM\s*\|", l)]
checks["Table V rows for PRISM (scenario, n)"] = [(l.split("|")[1].strip(), l.split("|")[-2].strip()) for l in prism_t5]
sp = open(os.path.join(TREE, "results", "tables", "E1_selected_parameters.csv"), encoding="utf-8").read().splitlines()
hdr = sp[0].split(",")
col = hdr.index("PRISM") if "PRISM" in hdr else None
sp_prism = {r.split(",")[0]: float(r.split(",")[col]) for r in sp[1:]} if col is not None else {}
checks["E1_selected_parameters PRISM column equals selections()"] = (
    col is not None and all(abs(sp_prism[str(k)] - v["param"]) < 1e-12 for k, v in sel.items()))
assert len(prism_t5) == 4 and checks["E1_selected_parameters PRISM column equals selections()"]

# 3. revision analyses on the normalised analysis copy (R7.6)
AN = os.path.join(OUT, "analysis")
make_tree(AN)
run([a.python, os.path.join(TOOLS, "normalize_labels.py"), AN], AN)
with open(os.path.join(AN, "results", "tables", "revision", "pc_billing_bounds.txt"), "w", encoding="utf-8",
          newline="\n") as f:
    run([a.python, os.path.join("scripts", "revision", "pc_billing_bounds.py"), "."], AN, stdout=f)
run([a.python, os.path.join(TOOLS, "r76_matched_1pct.py"), ".", CODE,
     os.path.join("results", "tables", "revision", "r76_matched_1pct.txt")], AN)
src = open(os.path.join(TOOLS, "r76_matched_1pct.py"), encoding="utf-8").read()
ns = {"__name__": "r76"}
argv, sys.argv = sys.argv, ["r76_matched_1pct.py", AN, CODE, os.devnull]
sys.path.insert(0, os.path.join(AN, "src"))
exec(compile(src[:src.index("regen = load(")], "r76_matched_1pct.py", "exec"), ns)
sys.argv = argv
import numpy as np  # noqa: E402

end = {}
for name, root in (("regenerated", AN), ("stored", CODE)):
    data = ns["load"](os.path.join(root, "results", "tables", "revision", "pc_billing_runs.csv"))
    end[name] = {}
    for T in (0.010, 0.015, 0.020):
        per = {f: [ns["at"](ns["envelope"](ns["points"](data, s, f)), T)[0] for s in ns["SEEDS"]] for f in ns["FAMS"]}
        ok = [np.isfinite(x) and np.isfinite(y) for x, y in zip(per["PRISM"], per["QuantProv_q90"])]
        d = [100 * (x / y - 1) for (x, y), o in zip(zip(per["PRISM"], per["QuantProv_q90"]), ok) if o]
        m, h = ns["tint"](d)
        end[name][f"{100 * T:.1f}%"] = dict(mean=m, lower=m - h, upper=m + h, n=len(d),
                                            not_bracketed=[s for s, o in zip(ns["SEEDS"], ok) if not o])
json.dump(end, open(os.path.join(OUT, "r76_endpoints.json"), "w", encoding="utf-8", newline="\n"), indent=1)

# 4. E11: Eq. (5) against Erlang-B
if {"E11", "E11occ"} <= set(inputs):
    with open(os.path.join(OUT, "e11_table.stdout.txt"), "w", encoding="utf-8") as f:
        run([a.python, os.path.join(TOOLS, "e11_occupancy.py"), AN, "table"], AN, stdout=f)
    e11 = open(os.path.join(AN, "results", "tables", "revision", "E11_erlangb_regenerated.md"), encoding="utf-8").read()
    checks["E11 table: explicit Erlang-B rows equal E1 main configuration"] = "run for run: True" in e11
    checks["E11 table compares Eq. (5) with Erlang-B"] = "| PRISM, Eq. (5)" in e11 and "| PRISM, Erlang-B" in e11
    assert all(checks[k] for k in checks if k.startswith("E11 table"))

# 5. manifest
json.dump(dict(checks=checks, log=log), open(os.path.join(OUT, "checks.json"), "w", encoding="utf-8", newline="\n"),
          indent=1, default=str)
lines = []
for d in ("tree/results/tables", "analysis/results/tables", "."):
    base = os.path.join(OUT, d)
    for root, _, files in os.walk(base):
        if d == "." and root != OUT:
            continue
        for fn in sorted(files):
            p = os.path.join(root, fn)
            lines.append(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {os.path.relpath(p, OUT).replace(os.sep, '/')}")
open(os.path.join(OUT, "MANIFEST.sha256"), "w", encoding="utf-8", newline="\n").write("\n".join(sorted(set(lines),
                                                                                         key=lambda s: s[66:])) + "\n")
for k, v in checks.items():
    print(f"CHECK {k}: {v}")
print("done:", OUT)
