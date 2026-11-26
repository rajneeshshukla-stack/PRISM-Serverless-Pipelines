#!/usr/bin/env python3
"""R3.6: the analysis copy of the regenerated raw outputs, with PRISM's label normalised.

Why: on the current code PRISM's risk model defaults to Erlang-B (f119bee), so policies.PRISM labels its runs
'PRISM_EB...' where the submitted runs (Eq. (5) default) read 'PRISM...'. scripts/analyze.py and the revision analyses
select PRISM by the literal 'PRISM', so run unchanged they would drop PRISM from the regenerated tables. The regenerated
PRISM rows *are* PRISM in its revised main configuration, so the analysis copy relabels them.

What it does (idempotent):
  1. results/raw is moved, once, to results/raw_regenerated: the regenerated outputs, never modified afterwards;
  2. results/raw is rebuilt from it. In every experiment except E11 (and E11occ), every string 'PRISM_EB' in the rows
     (any .jsonl, every string field) and in the .npz array keys becomes 'PRISM'. E11 and E11occ, which compare risk
     models explicitly, are copied byte for byte. Every other file is copied byte for byte;
  3. results/raw_normalization_manifest.json lists every file with its SHA-256 before and after and the count of
     relabelled strings.

usage: python normalize_labels.py <regenerated tree prism-repro>
"""
import hashlib
import json
import os
import shutil
import sys

import numpy as np

TREE = sys.argv[1]
RAW, ORIG = os.path.join(TREE, "results", "raw"), os.path.join(TREE, "results", "raw_regenerated")
KEEP = {"E11", "E11occ"}
if not os.path.isdir(ORIG):
    os.replace(RAW, ORIG)
elif os.path.isdir(RAW):
    shutil.rmtree(RAW)
os.makedirs(RAW)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fix(o, n):
    if isinstance(o, str):
        if "PRISM_EB" in o:
            n[0] += 1
            return o.replace("PRISM_EB", "PRISM")
        return o
    if isinstance(o, list):
        return [fix(x, n) for x in o]
    if isinstance(o, dict):
        return {k: fix(v, n) for k, v in o.items()}
    return o


man = []
for exp in sorted(os.listdir(ORIG)):
    src_d, dst_d = os.path.join(ORIG, exp), os.path.join(RAW, exp)
    if not os.path.isdir(src_d):
        continue
    os.makedirs(dst_d)
    for fn in sorted(os.listdir(src_d)):
        s, d = os.path.join(src_d, fn), os.path.join(dst_d, fn)
        n = [0]
        if exp in KEEP or not (fn.endswith(".jsonl") or fn.endswith(".npz")):
            shutil.copyfile(s, d)
        elif fn.endswith(".jsonl"):
            with open(s, encoding="utf-8") as fi, open(d, "w", encoding="utf-8", newline="\n") as fo:
                for line in fi:
                    if line.strip():
                        fo.write(json.dumps(fix(json.loads(line), n)) + "\n")
        else:
            # allow_pickle: on the current code E9 also saves '...::sampling_flip_direction' as a 0-d object array
            # (a dict of three floats); the file is this run's own output, written by the tree's code.
            z = np.load(s, allow_pickle=True)
            arrs = {}
            for k in z.files:
                k2 = fix(k, n)
                assert k2 not in arrs, f"key collision {k2} in {s}"
                a = z[k]
                if a.dtype == object:               # relabel inside object elements too, keeping shape and dtype
                    b = np.empty(a.size, dtype=object)
                    for i, x in enumerate(a.ravel().tolist()):
                        b[i] = fix(x, n)
                    a = b.reshape(a.shape)
                arrs[k2] = a
            z.close()
            np.savez_compressed(d, **arrs)
        man.append(dict(experiment=exp, file=fn, copied_verbatim=exp in KEEP or not (fn.endswith(".jsonl") or fn.endswith(".npz")),
                        relabelled_strings=n[0], sha256_regenerated=sha(s), sha256_analysis_copy=sha(d)))
json.dump(dict(note=__doc__.split("\n\n")[1], files=man), open(os.path.join(TREE, "results", "raw_normalization_manifest.json"),
                                                               "w", encoding="utf-8", newline="\n"), indent=1)
tot = sum(m["relabelled_strings"] for m in man)
print(f"{len(man)} files; {tot} strings relabelled; verbatim copies {sum(m['copied_verbatim'] for m in man)}")
