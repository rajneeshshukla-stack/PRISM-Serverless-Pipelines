#!/usr/bin/env python3
"""Check the revision trace inventory (R2.18, R5.M4, R6.5) without touching the confirmatory seeds.

Regenerates the counts of the development traces 101-105 in all five scenarios and compares them with
data/trace_set_revision.json (the hashing of scripts/revision/trace_set.py). For seeds 106-130 it only checks that the
manifest lists them and that the file is unchanged since its commit (4c43769). No confirmatory trace is generated and
no policy runs.
usage: python verify_trace_inventory.py <prism-repro root>   (prints the report)"""
import hashlib, json, os, subprocess, sys
import numpy as np
ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.workload import SCENARIOS, generate_trace
man = json.load(open(os.path.join(ROOT, "data/trace_set_revision.json"), encoding="utf-8"))
h = lambda c: hashlib.sha256(np.ascontiguousarray(c, dtype="<i8").tobytes()).hexdigest()
ok = 0; bad = []
for s in (101, 102, 103, 104, 105):
    for sc in SCENARIOS:
        if h(generate_trace(s, sc)["counts"]) == man["counts_sha256"][str(s)][sc]:
            ok += 1
        else:
            bad.append((s, sc))
print(f"development traces 101-105 x {len(SCENARIOS)} scenarios: {ok} of {5 * len(SCENARIOS)} counts match the manifest; mismatches {bad or 'none'}")
print(f"manifest: {len(man['seeds'])} seeds; original {man['original_seeds']}; new (confirmatory) {man['new_seeds'][0]}-{man['new_seeds'][-1]} "
      f"({len(man['new_seeds'])}); scenarios {man['scenarios']}; checksums for {len(man['counts_sha256'])} seeds")
d = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", "4c43769", "--", "data/trace_set_revision.json"]).returncode
print("data/trace_set_revision.json unchanged since 4c43769:", d == 0)
print("seeds 106-130: not generated here; no policy run")
