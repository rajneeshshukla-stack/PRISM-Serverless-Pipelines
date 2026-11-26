#!/usr/bin/env python3
"""R3.6: correct the provenance labels that two revision scripts print, when they are run on the regenerated rows.

supplement_pertrace_tables.py and statistical_meaning.py were written for the stored submitted rows and print
"SUBMITTED rows" / "submitted code and values" in their headers. In the regeneration tree they read the regenerated
rows, so those words would be wrong. This rewrites exactly those header strings, nothing else, and records each
replacement with the file's SHA-256 before and after in results/tables/revision/relabel_manifest.json.
Idempotent: a file already relabelled is left as it is.

usage: python relabel_regenerated.py <tree prism-repro>
"""
import hashlib
import json
import os
import sys

TREE = os.path.abspath(sys.argv[1])
TAB = os.path.join(TREE, "results", "tables", "revision")
EDITS = {
    os.path.join("supplement_pertrace", "pertrace_tables.md"): [
        ("(SUBMITTED rows, test weeks;", "(REGENERATED rows at fd8b01a, test weeks;"),
        ("the variants use the same eps. Pre-calibration; values change at",
         "the variants use the same eps. Pre-calibration; regenerated at fd8b01a"),
        ("the regeneration. Built by scripts/revision/supplement_pertrace_tables.py",
         "(R3.6). Built by scripts/revision/supplement_pertrace_tables.py"),
        ("(SUBMITTED rows, stationary test week;", "(REGENERATED rows at fd8b01a, stationary test week;"),
    ],
    os.path.join("statistical_meaning", "summary.md"): [
        ("(submitted rows; n = 5 traces; 95% t intervals)", "(regenerated rows at fd8b01a; n = 5 traces; 95% t intervals)"),
        ("Pre-calibration, submitted code and values.", "Pre-calibration, regenerated at fd8b01a (current code)."),
    ],
}
man, bad, new_txt = [], [], {}
for rel, edits in EDITS.items():
    p = os.path.join(TAB, rel)
    txt = open(p, encoding="utf-8").read()
    before = hashlib.sha256(txt.encode("utf-8")).hexdigest()
    for old, new in edits:
        n_old, n_new = txt.count(old), txt.count(new)
        if n_old == 1:
            txt = txt.replace(old, new)
            man.append(dict(file=rel, old=old, new=new, applied=True))
        elif n_old == 0 and n_new == 1:
            man.append(dict(file=rel, old=old, new=new, applied=False, note="already relabelled"))
        else:
            bad.append(f"{rel}: '{old}' found {n_old} times")
    new_txt[p] = txt
    man.append(dict(file=rel, sha256_before=before, sha256_after=hashlib.sha256(txt.encode("utf-8")).hexdigest()))
if bad:                                    # nothing is written unless every replacement is unambiguous
    sys.exit("relabel refused: " + "; ".join(bad))
for p, txt in new_txt.items():
    open(p, "w", encoding="utf-8", newline="\n").write(txt)
json.dump(man, open(os.path.join(TAB, "relabel_manifest.json"), "w", encoding="utf-8", newline="\n"), indent=1)
print(f"{sum(1 for m in man if m.get('applied'))} replacements applied")
