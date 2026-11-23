#!/usr/bin/env python3
"""Compare the raw outputs and tables of two regeneration trees (read-only).

Rows are matched by run_id (else by seed, scenario, label, forecaster, tag). Values are equal when identical, or both
NaN. Fields that record provenance or wall-clock time are reported separately from simulated results. Arrays are
compared key by key, exactly. Tables are compared byte for byte after CRLF->LF normalisation; for differing tables
the differing lines are listed.

usage: python compare_trees.py <raw A> <raw B> <tables A> <tables B> <out.json> [EXP ...]
"""
import glob
import json
import math
import os
import sys

import numpy as np

RAW_A, RAW_B, TAB_A, TAB_B, OUT = sys.argv[1:6]
EXPS = sys.argv[6:] or ["E3", "E7", "E9"]
TIMING = {"source_sha256", "started_utc", "runtime_s", "sim_seconds", "decision_ms_median", "decision_ms_p99"}


def same(x, y):
    if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
        return True
    return x == y


def key(r):
    return r.get("run_id") or (r["seed"], r.get("scenario"), r.get("label"), r.get("forecaster"), r.get("tag"))


out = {"raw": {}, "tables": {}}
for e in EXPS:
    ld = lambda d: [json.loads(l) for l in open(os.path.join(d, e, "rows.jsonl"), encoding="utf-8") if l.strip()]  # noqa
    A, B = {key(r): r for r in ld(RAW_A)}, {key(r): r for r in ld(RAW_B)}
    res, tim = {}, {}
    for k in A.keys() & B.keys():
        for f in set(A[k]) | set(B[k]):
            if not same(A[k].get(f), B[k].get(f)):
                (tim if f in TIMING else res)[f] = (tim if f in TIMING else res).get(f, 0) + 1
    fa = sorted(os.path.basename(p) for p in glob.glob(os.path.join(RAW_A, e, "*.npz")))
    fb = sorted(os.path.basename(p) for p in glob.glob(os.path.join(RAW_B, e, "*.npz")))
    nk = nd = 0
    diff_keys = []
    for fn in sorted(set(fa) & set(fb)):
        za, zb = np.load(os.path.join(RAW_A, e, fn), allow_pickle=True), np.load(os.path.join(RAW_B, e, fn), allow_pickle=True)
        for k in sorted(set(za.files) | set(zb.files)):
            nk += 1
            if k not in za.files or k not in zb.files:
                nd += 1; diff_keys.append(f"{fn}:{k} (missing)"); continue
            x, y = za[k], zb[k]
            ok = x.tolist() == y.tolist() if x.dtype == object else (x.shape == y.shape and np.array_equal(x, y, equal_nan=True))
            if not ok:
                nd += 1; diff_keys.append(f"{fn}:{k}")
    out["raw"][e] = dict(rows=[len(A), len(B)], same_run_keys=set(A) == set(B), result_fields_differing=res,
                         provenance_or_timing_fields_differing=tim, array_files=[len(fa), len(fb)], array_keys=nk,
                         array_keys_differing=nd, first_differing_keys=diff_keys[:20])
files = sorted(os.path.relpath(p, TAB_B).replace(os.sep, "/") for p in glob.glob(os.path.join(TAB_B, "**", "*"), recursive=True)
               if os.path.isfile(p))
for f in files:
    pa = os.path.join(TAB_A, f)
    if not os.path.exists(pa):
        out["tables"][f] = "no counterpart"; continue
    a = open(pa, "rb").read().replace(b"\r\n", b"\n").decode("utf-8", "replace").split("\n")
    b = open(os.path.join(TAB_B, f), "rb").read().replace(b"\r\n", b"\n").decode("utf-8", "replace").split("\n")
    if a == b:
        out["tables"][f] = "identical"
    else:
        out["tables"][f] = dict(lines=[len(a), len(b)], differing=[(i + 1, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y][:12])
n_id = sum(v == "identical" for v in out["tables"].values())
out["summary"] = dict(tables=len(files), identical=n_id, differing=sorted(k for k, v in out["tables"].items() if isinstance(v, dict)),
                      no_counterpart=sorted(k for k, v in out["tables"].items() if v == "no counterpart"))
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
for e, r in out["raw"].items():
    print(e, "rows", r["rows"], "result fields differing:", r["result_fields_differing"], "| arrays differing:",
          r["array_keys_differing"], "of", r["array_keys"])
print("tables:", out["summary"])
