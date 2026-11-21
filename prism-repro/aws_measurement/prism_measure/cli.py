"""Command line. Run from prism-repro/aws_measurement:  python -m prism_measure <command> ...

Local (no AWS):  design, estimate, dry-run, analyse
AWS (plan only unless --execute AND PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES):  deploy, calibrate, run, collect, teardown
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .design import CAP_MAX, build_design


def _design(a):
    return build_design(seed=a.seed, batch=a.batch, blocks=a.blocks)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="prism_measure")
    p.add_argument("--seed", type=int, default=20261121)
    p.add_argument("--batch", type=int, default=CAP_MAX, help=f"concurrency cap and batch size (max {CAP_MAX})")
    p.add_argument("--blocks", type=int, default=3)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("design"); s.add_argument("--out", required=True)
    s = sub.add_parser("estimate"); s.add_argument("--out", required=True)
    s.add_argument("--price-gb-s", type=float); s.add_argument("--price-request", type=float)
    s.add_argument("--platform-cold-s", type=float, default=1.0); s.add_argument("--update-wait-s", type=float, default=10.0)
    s.add_argument("--client-overhead-s", type=float, default=0.05)
    s = sub.add_parser("dry-run"); s.add_argument("--out", required=True)
    s.add_argument("--mode", choices=("full", "timed"), default="full"); s.add_argument("--time-scale", type=float, default=0.01)
    s = sub.add_parser("analyse"); s.add_argument("--records", required=True); s.add_argument("--cloudwatch")
    s.add_argument("--out", required=True); s.add_argument("--n-boot", type=int, default=2000)
    for name in ("preflight", "deploy", "calibrate", "run", "collect", "teardown"):
        s = sub.add_parser(name)
        s.add_argument("--region", required=name in ("preflight", "deploy", "teardown"))
        s.add_argument("--manifest", required=name not in ("teardown", "preflight"))
        s.add_argument("--execute", action="store_true", help="really call AWS (also needs PRISM_AWS_AUTHORIZED)")
        if name == "run":
            s.add_argument("--records", required=True); s.add_argument("--block", type=int, action="append")
            s.add_argument("--host-note", default="")
        if name == "collect":
            s.add_argument("--records", required=True); s.add_argument("--out", required=True)
    a = p.parse_args(argv)

    if a.cmd == "design":
        d = _design(a)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(d.to_json())
        print(json.dumps({"visits": len(d.visits), "counts": d.counts()}, indent=1))
    elif a.cmd == "estimate":
        from .estimate import estimate
        e = estimate(_design(a), platform_cold_s=a.platform_cold_s, update_wait_s=a.update_wait_s,
                     client_overhead_s=a.client_overhead_s, price_gb_s=a.price_gb_s, price_request=a.price_request)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(e, f, indent=1)
        print(json.dumps(e, indent=1))
    elif a.cmd == "dry-run":
        from .dryrun import run_dry
        c = run_dry(a.out, a.mode, a.time_scale, a.seed)
        c.pop("truth_comparison", None)
        print(json.dumps(c, indent=1))
    elif a.cmd == "analyse":
        from .analyse import analyse, load_jsonl, write_outputs
        cw = {}
        if a.cloudwatch and os.path.exists(a.cloudwatch):
            cw = {r["request_id"]: r for r in load_jsonl(a.cloudwatch)}
        res = analyse(load_jsonl(a.records), cw, n_boot=a.n_boot)
        write_outputs(res, a.out)
        print(json.dumps({"cells": len(res["cells"]), "issues": res["issues"]}, indent=1))
    else:
        from . import aws
        d = _design(a)
        if a.cmd == "preflight":
            plan = aws.preflight(a.region, a.execute)
        elif a.cmd == "deploy":
            plan = aws.deploy(d, a.region, a.manifest, a.execute)
        elif a.cmd == "calibrate":
            plan = aws.calibrate(d, a.manifest, a.execute)
        elif a.cmd == "collect":
            plan = aws.collect(a.records, a.manifest, a.out, a.execute)
        elif a.cmd == "teardown":
            plan = aws.teardown(a.manifest, a.region, a.execute)
        else:                                          # run
            plan = [f"run blocks {a.block or 'all'}: {len(d.visits)} visits, cap {a.batch}, records -> {a.records}"]
            if aws.authorised(a.execute):
                from .runner import Runner
                m = json.load(open(a.manifest, encoding="utf-8"))
                if "calibration" not in m:
                    print("refusing to run: the manifest has no calibration (run `calibrate` first)", file=sys.stderr)
                    return 2
                envs = {fn: v["env"] for fn, v in m["functions"].items()}
                Runner(aws.clients(m["region"])["lambda"], envs, a.records, cap=a.batch).run(
                    d, a.block, host_note=a.host_note)
        print(("EXECUTED:\n" if a.execute else "PLAN ONLY (no AWS call made):\n") + "\n".join(f"  {x}" for x in plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
