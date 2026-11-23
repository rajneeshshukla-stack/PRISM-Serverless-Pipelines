#!/usr/bin/env python3
"""R3.6: compare every regenerated table with the stored (submitted) table of the same name. Read-only.

For each file under results/tables/ (and results/tables/revision/) of the repository, reports whether the regenerated
file (same relative path in the regeneration tree) is identical after CRLF->LF normalisation, how many lines differ,
and up to three example line pairs; lists files present on only one side. Writes a CSV and a text report.

usage: python compare_tables.py <repo prism-repro> <tree prism-repro> <out_dir>
"""
import csv
import difflib
import hashlib
import os
import sys

REPO, TREE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)


def files(root):
    base = os.path.join(root, "results", "tables")
    out = {}
    for d, _, fs in os.walk(base):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, base).replace("\\", "/")] = p
    return out


A, B = files(REPO), files(TREE)
rows, lines = [], []
for rel in sorted(set(A) | set(B)):
    if rel not in B:
        rows.append(dict(table=rel, status="not regenerated", lines_stored="", lines_regenerated="", lines_differing="",
                         sha256_regenerated=""))
        continue
    if rel not in A:
        rb = open(B[rel], "rb").read().replace(b"\r\n", b"\n")
        rows.append(dict(table=rel, status="new (no stored file)", lines_stored="", lines_regenerated=rb.count(b"\n"),
                         lines_differing="", sha256_regenerated=hashlib.sha256(rb).hexdigest()))
        continue
    ra = open(A[rel], "rb").read().replace(b"\r\n", b"\n")
    rb = open(B[rel], "rb").read().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(rb).hexdigest()
    if ra == rb:
        rows.append(dict(table=rel, status="identical", lines_stored=ra.count(b"\n"), lines_regenerated=rb.count(b"\n"),
                         lines_differing=0, sha256_regenerated=sha))
        continue
    la = ra.decode("utf-8", "replace").split("\n")
    lb = rb.decode("utf-8", "replace").split("\n")
    sm = difflib.SequenceMatcher(None, la, lb, autojunk=False)
    nd = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    rows.append(dict(table=rel, status="differs", lines_stored=len(la), lines_regenerated=len(lb), lines_differing=nd,
                     sha256_regenerated=sha))
    ex = [(la[i1:i2], lb[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"][:3]
    lines.append(f"## {rel}: {nd} of {len(la)} lines differ")
    for a, b in ex:
        for x in a[:2]:
            lines.append(f"  stored:      {x[:200]}")
        for x in b[:2]:
            lines.append(f"  regenerated: {x[:200]}")
with open(os.path.join(OUT, "table_comparison.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {}
for r in rows:
    summary[r["status"]] = summary.get(r["status"], 0) + 1
head = [f"Stored results/tables versus regenerated tree: {len(rows)} files; " +
        ", ".join(f"{k} {v}" for k, v in sorted(summary.items()))]
open(os.path.join(OUT, "table_comparison.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(head + [""] + lines) + "\n")
print("\n".join(head))
