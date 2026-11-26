#!/usr/bin/env python3
"""Fixed-1024 MB equivalence check for the corrected start-up rerun (CONFIG_NOTE_STARTUP_20261125.md).
Compares group E weeks (set CAL145C, init_scaling "constant") with the saved Group A weeks (set CAL145, Eq. (3) start-up):
every JSON field except run bookkeeping, and every array in the .npz, must be exactly equal.
usage: python compare_equivalence_p3.py <old run dir> <new run dir> <out.txt>
"""
import glob
import json
import os
import sys

import numpy as np

OLD, NEW, OUTP = sys.argv[1:4]
SKIP = {"cfg_sha", "pid", "finished_utc", "runtime_s", "set"}
lines, n_ok, n_bad = [], 0, 0
new_files = sorted(glob.glob(os.path.join(NEW, "weeks", "CAL145C", "*", "*", "*.json")))
for p in new_files:
    rel = os.path.relpath(p, os.path.join(NEW, "weeks", "CAL145C"))
    q = os.path.join(OLD, "weeks", "CAL145", rel)
    a, b = json.load(open(q, encoding="utf-8")), json.load(open(p, encoding="utf-8"))
    keys = sorted((set(a) | set(b)) - SKIP)
    diff = [k for k in keys if a.get(k) != b.get(k)]
    za, zb = np.load(q[:-5] + ".npz"), np.load(p[:-5] + ".npz")
    arr_diff = sorted(set(za.files) ^ set(zb.files)) + [k for k in za.files if k in zb.files and not np.array_equal(za[k], zb[k])]
    ok = not diff and not arr_diff
    n_ok += ok
    n_bad += not ok
    lines.append(f"{rel}: {'IDENTICAL' if ok else 'DIFFERENT'} ({len(keys)} fields, {len(za.files)} arrays; cfg_sha "
                 f"{a['cfg_sha']} -> {b['cfg_sha']}; cost {a['cost']:.4f}; violating {100 * a['violating_window_rate']:.2f}%)"
                 + (f" fields {diff} arrays {arr_diff}" if not ok else ""))
lines.append(f"weeks compared {len(new_files)}: identical {n_ok}, different {n_bad}")
lines.append("VERDICT: " + ("fixed-1024 MB results are equivalent under the two start-up settings; the saved Group A "
                            "QuantProv-q90 and Reactive groups may be reused" if n_bad == 0 and len(new_files) == 20
                            else "NOT equivalent or incomplete: do not reuse"))
open(OUTP, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("\n".join(lines))
