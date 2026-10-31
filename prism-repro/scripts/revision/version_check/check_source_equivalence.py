#!/usr/bin/env python3
"""Check that two copies of the package source differ only in comments and docstrings.

The stored runs record the hash of the code that produced them (`source_sha256`; the final
code of the release has 8c1710f74c3d...). The Stage 2 correction M15 changed comments and
docstrings in src/prism_repro, which changes that hash but not the program. This script shows
it: for every module, the syntax tree with docstrings removed must be identical.

Usage: python check_source_equivalence.py <package root A> <package root B>
"""
import ast, glob, hashlib, os, sys


def source_sha(root):  # same definition as experiments/run_experiments.py
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(root, "src", "prism_repro", "*.py"))):
        h.update(open(f, "rb").read())
    h.update(open(os.path.join(root, "experiments", "run_experiments.py"), "rb").read())
    return h.hexdigest()


def code_only(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


a, b = sys.argv[1], sys.argv[2]
mods = sorted({os.path.basename(p) for r in (a, b) for p in glob.glob(os.path.join(r, "src", "prism_repro", "*.py"))})
mods = [os.path.join("src", "prism_repro", m) for m in mods] + [os.path.join("experiments", "run_experiments.py")]
bad = 0
for m in mods:
    pa, pb = os.path.join(a, m), os.path.join(b, m)
    if not (os.path.exists(pa) and os.path.exists(pb)):
        print(f"MISSING in one copy: {m}"); bad += 1; continue
    same_bytes = open(pa, "rb").read() == open(pb, "rb").read()
    same_code = same_bytes or code_only(pa) == code_only(pb)
    bad += not same_code
    print(f"{m:40s} {'bytes identical' if same_bytes else ('code identical (comments/docstrings differ)' if same_code else 'CODE DIFFERS')}")
print(f"source_sha256 A: {source_sha(a)}\nsource_sha256 B: {source_sha(b)}")
print("RESULT:", "programs identical" if not bad else f"{bad} module(s) differ in code")
sys.exit(1 if bad else 0)
