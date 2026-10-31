#!/usr/bin/env python3
"""Revision manifest. Writes RUN_MANIFEST_REVISION.json (provenance of the experiments added or completed
during the manuscript revision: E8 and E12, plus the post hoc analysis outputs) and regenerates
CHECKSUMS.sha256 over every repository file. RUN_MANIFEST.json is left untouched: it records the
environment of the original runs (E1-E11), which differs from the revision environment.
Usage: python scripts/revision/build_revision_manifest.py   (then: python scripts/build_manifest.py --verify)"""
import glob
import json
import os
import platform
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_manifest import files, sha  # noqa: E402

RAW = os.path.join(ROOT, "results", "raw")


def jsonl_rows(paths):
    out = []
    for p in paths:
        out += [json.loads(l) for l in open(p)]
    return out


def provenance(exp, pattern, kind, command):
    d = os.path.join(RAW, exp)
    rows = jsonl_rows(sorted(glob.glob(os.path.join(d, pattern))))
    starts = [r["started_utc"] for r in rows if r.get("started_utc")]
    return dict(kind=kind, n_rows=len(rows), seeds=sorted({r["seed"] for r in rows if "seed" in r}),
                status_counts={s: sum(1 for r in rows if r.get("status") == s) for s in {r.get("status") for r in rows}},
                first_start_utc=min(starts, default=None), last_start_utc=max(starts, default=None),
                files={os.path.basename(f): sha(f) for f in sorted(glob.glob(os.path.join(d, "*")))},
                command=command, synthetic_data=True, cloud_execution=False)


def env():
    pk = {}
    for m in ("numpy", "scipy", "pandas", "sklearn", "matplotlib"):
        try:
            pk[m] = __import__(m).__version__
        except Exception:
            pk[m] = None
    return dict(python=platform.python_version(), platform=platform.platform(), packages=pk)


man = dict(
    generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    note=("Experiments added or completed during the manuscript revision, after E1-E11 outputs had been "
          "inspected (post hoc). All data synthetic; simulations on a local sandbox; no cloud resources."),
    environment_of_revision_runs=env(),
    experiments=dict(
        E8=provenance("E8", "rows.jsonl", "reference forecasters (simulation); seeds 101-105, completed in revision",
                      "python experiments/run_experiments.py --exp E8 --seeds <seeds>; "
                      "analysis: python scripts/revision/analyze_e8.py . results/raw/E8/rows.jsonl"),
        E12=provenance("E12", "E12_seed*.jsonl",
                       "event-level re-tuning by open-loop replay of stored E1 schedules (added in revision)",
                       "python scripts/revision/e12_event_retune.py . results/raw/E12 <seeds>; "
                       "analysis: python scripts/revision/analyze_e12.py results/raw/E12")),
    post_hoc_outputs={os.path.relpath(f, ROOT): sha(f)
                      for f in sorted(glob.glob(os.path.join(ROOT, "results", "tables", "revision", "*")))},
)
json.dump(man, open(os.path.join(ROOT, "RUN_MANIFEST_REVISION.json"), "w"), indent=1)
with open(os.path.join(ROOT, "CHECKSUMS.sha256"), "w") as f:
    for p in files():
        f.write(f"{sha(os.path.join(ROOT, p))}  {p}\n")
print("wrote RUN_MANIFEST_REVISION.json and CHECKSUMS.sha256")
