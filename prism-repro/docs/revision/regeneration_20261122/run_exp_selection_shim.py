#!/usr/bin/env python3
"""R3.6: run E3, E7 or E9 of experiments/run_experiments.py on the current code, with one documented lookup fix.

Why: at fd8b01a these three experiments fail on a freshly regenerated E1 with KeyError: 'PRISM' (observed for E9 in
the regeneration tree, 23 Nov 2026 00:03 UTC, results/logs/E9_unshimmed_failure.err). Each takes PRISM's
validation-selected setting from selections(seed), which keys E1's rows by their 'policy' field. Since f119bee made
Erlang-B PRISM's default risk model, policies.PRISM names its runs 'PRISM_EB', so the key 'PRISM' is absent. The
submitted E3, E7 and E9 rows predate f119bee and never met this.

What it does: imports experiments/run_experiments.py unchanged and wraps variant_of(row), which only selections()
uses, so that the policy name 'PRISM_EB' is read as 'PRISM'. It refuses to run if E1 holds rows of both names, where
the mapping would merge two policies. Nothing else changes: the same simulations, specs, labels, run ids and Store,
and the same source_sha256, which hashes the unchanged run_experiments.py and src/.

usage: python run_exp_selection_shim.py <tree prism-repro> --exp E3|E7|E9 --seeds <seed> [...] [--check]
       --check only resolves every lookup the experiment makes and runs no simulation.
"""
import argparse
import os
import platform
import sys
import time

TREE = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(TREE, "experiments"))
import numpy as np                     # noqa: E402
import run_experiments as RX           # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--exp", required=True, choices=("E3", "E7", "E9"))
ap.add_argument("--seeds", type=int, nargs="+", required=True)
ap.add_argument("--check", action="store_true")
a = ap.parse_args(sys.argv[2:])

names = {r["policy"] for r in RX.load_rows("E1")}
if {"PRISM", "PRISM_EB"} <= names:
    sys.exit("E1 holds rows named both PRISM and PRISM_EB; the shim would merge them")
_variant_of = RX.variant_of


def variant_of(row):
    v = _variant_of(row)
    return "PRISM" if v == "PRISM_EB" else v


RX.variant_of = variant_of

if a.check:
    from prism_repro.experiment import make_policy
    e1 = {(r["seed"], r["scenario"], r["week"], r["label"]) for r in RX.load_rows("E1")}
    for seed in a.seeds:
        sel = RX.selections(seed)
        arr = np.load(os.path.join(RX.RESULTS, "E1", f"arrays_seed{seed}.npz"))
        files = set(arr.files)
        fams = RX.E9_FAMILIES if a.exp == "E9" else ("PRISM",)
        out = []
        for fam in fams:
            spec = sel[fam]
            label = make_policy(spec).label
            ok = all((seed, sc, "test", label) in e1 and f"E1|{seed}|{sc}|test|{label}|::P_epoch" in files
                     for sc in RX.MAIN_SCENARIOS)
            out.append(f"{fam}->{label}{'' if ok else ' MISSING'}")
        print(f"[{a.exp} check] seed {seed}: " + ", ".join(out), flush=True)
    sys.exit(0)

t = time.time()
print(f"[{a.exp}] start {RX.now()} seeds={a.seeds} python={platform.python_version()} numpy={np.__version__} "
      f"(selection shim: policy PRISM_EB read as PRISM)", flush=True)
RX.EXPS[a.exp](a.seeds, False)
print(f"[{a.exp}] finished {RX.now()} in {time.time() - t:.0f}s", flush=True)
