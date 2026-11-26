"""Checksum mismatch counts for one checkout by three methods. Usage: python ck_counts.py <checkout_root> <branch_scripts_dir>"""
import hashlib, os, subprocess, sys, io, contextlib
root = sys.argv[1]; pr = os.path.join(root, "prism-repro")
sys.path.insert(0, sys.argv[2]); import build_manifest as bm
man = [l.rstrip("\r\n").split("  ", 1) for l in open(os.path.join(pr, "CHECKSUMS.sha256"), encoding="utf-8") if l.strip()]
# (1) committed blobs (LF contents as stored in git) at this checkout's HEAD
spec = "".join(f"HEAD:prism-repro/{p}\n" for _, p in man).encode()
out = subprocess.run(["git", "-C", root, "cat-file", "--batch"], input=spec, capture_output=True).stdout
blobs, i = [], 0
while i < len(out):
    nl = out.index(b"\n", i); hdr = out[i:nl].split()
    if hdr[-1] == b"missing": blobs.append(None); i = nl + 1; continue
    size = int(hdr[2]); blobs.append(out[nl + 1:nl + 1 + size]); i = nl + 1 + size + 1
committed = [p for (h, p), b in zip(man, blobs) if b is None or hashlib.sha256(b).hexdigest() != h]
# (2) raw working-copy bytes (the pre-fix verifier)
raw = [p for h, p in man if not os.path.isfile(os.path.join(pr, p)) or bm.sha(os.path.join(pr, p)) != h]
# (3) the fixed verifier
buf = io.StringIO()
n = bm.verify(pr, report=lambda m: buf.write(m + "\n"))
new = [l.split(" ", 1)[1] for l in buf.getvalue().splitlines() if l.startswith(("MISMATCH", "MISSING"))]
head = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"{head}: entries {len(man)} | committed-blob mismatches {len(committed)} | raw working-copy mismatches {len(raw)} | "
      f"fixed verifier: {n['exact']} exact, {n['eol_normalised']} eol-normalised, {n['mismatch']} mismatch, {n['missing']} missing")
print("   fixed-verifier flags == committed-blob mismatches:", sorted(new) == sorted(committed))
print("   files:", " ".join(sorted(committed)))
