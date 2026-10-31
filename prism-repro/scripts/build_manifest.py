#!/usr/bin/env python3
"""Build RUN_MANIFEST.json (environment, revisions, per-experiment provenance) and
CHECKSUMS.sha256 (every repository file except .git). `--verify` re-checks checksums."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
EXPERIMENT_KIND = {
    "E1": "scientific evaluation (simulation)", "E2": "scientific evaluation (forecast, no simulation)",
    "E3": "scientific evaluation (simulation, ablation)", "E4": "scientific evaluation (simulation)",
    "E5": "scientific evaluation (simulation, sensitivity)", "E6": "scientific evaluation (simulation)",
    "E7": "scientific evaluation (simulation, ablation)", "E8": "scientific evaluation (simulation)",
    "E9": "scientific evaluation (event-level simulation, open loop)", "E10": "timing measurement (sandbox)",
    "E11": "scientific evaluation (simulation)",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def files():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
        for f in fn:
            p = os.path.relpath(os.path.join(dp, f), ROOT)
            if p in ("CHECKSUMS.sha256",) or f.startswith(".tmp_") or p.startswith("results/logs/run_all.pid"):
                continue
            out.append(p)
    return sorted(out)


def git(*a):
    try:
        return subprocess.check_output(["git", "-C", ROOT, *a], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def env():
    pk = {}
    for m in ("numpy", "scipy", "pandas", "sklearn", "matplotlib"):
        try:
            pk[m] = __import__(m).__version__
        except Exception:
            pk[m] = None
    cpu = None
    try:
        cpu = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
    except Exception:
        pass
    mem = None
    try:
        mem = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal"))) // 1024
    except Exception:
        pass
    return dict(python=platform.python_version(), platform=platform.platform(), cpu_model=cpu,
                logical_cpus=os.cpu_count(), mem_total_mb=mem, packages=pk)


def experiments():
    out = {}
    for d in sorted(glob.glob(os.path.join(RAW, "E*"))):
        exp = os.path.basename(d)
        p = os.path.join(d, "rows.jsonl")
        rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
        ids = {}
        for r in rows:
            ids[r.get("run_id", json.dumps([r.get("seed"), r.get("scenario"), r.get("label"), r.get("forecaster")]))] = r
        rows = list(ids.values())
        out[exp] = dict(
            kind=EXPERIMENT_KIND.get(exp), executed=bool(rows), n_rows_unique=len(rows),
            seeds=sorted({r["seed"] for r in rows}),
            status_counts={s: sum(1 for r in rows if r.get("status") == s) for s in {r.get("status") for r in rows}},
            source_sha256_values=sorted({r.get("source_sha256") for r in rows if r.get("source_sha256")}),
            first_start_utc=min((r["started_utc"] for r in rows if "started_utc" in r), default=None),
            last_start_utc=max((r["started_utc"] for r in rows if "started_utc" in r), default=None),
            total_run_seconds=round(sum(r.get("runtime_s", 0) or 0 for r in rows), 1),
            files={os.path.basename(f): sha(f) for f in sorted(glob.glob(os.path.join(d, "*")))},
            command=f"python experiments/run_experiments.py --exp {exp} --seeds <seeds> (see scripts/run_all.sh)",
            synthetic_data=True, cloud_execution=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    ck = os.path.join(ROOT, "CHECKSUMS.sha256")
    if a.verify:
        bad = 0
        for line in open(ck):
            h, p = line.rstrip("\n").split("  ", 1)
            fp = os.path.join(ROOT, p)
            if not os.path.exists(fp) or sha(fp) != h:
                print("MISMATCH", p)
                bad += 1
        print(f"verified {sum(1 for _ in open(ck))} files, {bad} mismatches")
        sys.exit(1 if bad else 0)
    sys.path.insert(0, os.path.join(ROOT, "experiments"))
    from run_experiments import source_sha
    man = dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               note="Independent reimplementation. All data SYNTHETIC; all results are simulations on a local "
                    "sandbox; no cloud resources were used. Manuscript values are claims, not inputs.",
               manuscript=dict(file="Joint_Cost_SLA_Serverless_Pipelines_PRISM_REVISED__1_.docx",
                               sha256="473672fbac925414da43ec716b083fc46effe339f0095be221bd09beafa5269a",
                               redistributed=False),
               git_head=git("rev-parse", "HEAD"), git_dirty=bool(git("status", "--porcelain")),
               git_log=(git("log", "--format=%h %cI %s") or "").splitlines(),
               current_source_sha256=source_sha(), environment=env(), experiments=experiments(),
               evaluation_seeds=[101, 102, 103, 104, 105], development_seed=7)
    json.dump(man, open(os.path.join(ROOT, "RUN_MANIFEST.json"), "w"), indent=1)
    with open(ck, "w") as f:
        for p in files():
            f.write(f"{sha(os.path.join(ROOT, p))}  {p}\n")
    print("wrote RUN_MANIFEST.json and CHECKSUMS.sha256")


if __name__ == "__main__":
    main()
