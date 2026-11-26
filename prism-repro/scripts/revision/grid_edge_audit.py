#!/usr/bin/env python3
"""Grid-edge audit of selected configurations (R5.M4; also R4.7).

Reviewer 5 asks to "widen every grid whose edge is selected". This applies the paper's selection
rule (experiment.select_by_rule, Section V-C) per trace and family to a set of stored rows and
reports, for every selection, the grid actually run for that family on that trace and whether the
selected value sits at its lower or upper edge. The grid is taken from the rows, so reduced grids
(E12) are audited as run. It reads stored rows only and writes nothing unless --out is given.

--week val  (default) audits the validation selections that the paper reports.
--week test applies the same rule to test-week rows: a POST HOC selection with test-week knowledge
            (e.g. the best unsmoothed headroom in Supplement S3), labelled as such in the output.

Usage: python grid_edge_audit.py <code_root> <rows.jsonl | dir> [...] [--week val|test] [--out f.json]
"""
import glob
import json
import os
import sys
from collections import defaultdict

if __name__ == '__main__':  # importable; argv only read when run directly
    sys.path.insert(0, os.path.join(sys.argv[1], 'src'))
from prism_repro.experiment import select_by_rule  # noqa: E402


def family_key(spec: dict) -> str:
    fam = spec.get("family", "?")
    if fam == "QuantProv":
        fam += {2: "_q90", 3: "_q99"}.get(spec.get("tau_idx"), f"_tau{spec.get('tau_idx')}")
    if spec.get("hyst"):
        fam += "+hyst"
    return fam


def audit(rows, week="val"):
    """Rows: dicts with seed, week, spec{family, param, ...}, cost, violating_window_rate. Rows with
    a non-empty tag (ablations) are ignored. Returns one record per (seed, scenario, family) with
    at least two grid points."""
    groups = defaultdict(list)
    for r in rows:
        if r.get("week") != week or r.get("tag") or "spec" not in r:
            continue
        p = r["spec"].get("param")
        if p is None:
            continue
        sc = r.get("scenario") if week == "test" else None   # validation has one week per trace
        groups[(r["seed"], sc, family_key(r["spec"]))].append(r)
    out = []
    for (seed, sc, fam), g in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        grid = sorted({float(r["spec"]["param"]) for r in g})
        if len(grid) < 2:
            continue
        sel = select_by_rule(g)
        v = float(sel["spec"]["param"])
        side = "low" if v == grid[0] else "high" if v == grid[-1] else ""
        out.append(dict(seed=seed, scenario=sc, family=fam, selected=v, grid_lo=grid[0], grid_hi=grid[-1],
                        n_points=len(grid), edge=bool(side), side=side,
                        met_threshold=bool(sel["violating_window_rate"] <= 0.02 + 1e-12),
                        post_hoc=(week == "test")))
    return out


def load_rows(paths):
    rows = []
    for p in paths:
        files = sorted(glob.glob(os.path.join(p, "*.jsonl"))) if os.path.isdir(p) else [p]
        for f in files:
            with open(f, encoding="utf-8") as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
    return rows


def main():
    args = sys.argv[2:]
    week, out_path = "val", None
    if "--week" in args:
        i = args.index("--week"); week = args[i + 1]; del args[i:i + 2]
    if "--out" in args:
        i = args.index("--out"); out_path = args[i + 1]; del args[i:i + 2]
    res = audit(load_rows(args), week)
    label = "POST HOC (selected with test-week knowledge)" if week == "test" else "validation selections"
    edges = [r for r in res if r["edge"]]
    print(f"{label}: {len(edges)} of {len(res)} selections at a grid edge")
    for r in edges:
        sc = f" {r['scenario']}" if r["scenario"] else ""
        print(f"  seed {r['seed']}{sc} {r['family']}: {r['selected']:g} at {r['side']} edge of "
              f"[{r['grid_lo']:g}, {r['grid_hi']:g}] ({r['n_points']} points)"
              f"{'' if r['met_threshold'] else '; no grid point met the 2% threshold'}")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)


if __name__ == '__main__':
    main()
