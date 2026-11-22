"""Command line. Run from prism-repro/aws_pipeline:  python -m prism_pipeline <command> ...

Local (no AWS):  plan, estimate, asl, selftest, analyse
AWS (plan only unless --execute AND PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES):  preflight, live-test, teardown
"""
from __future__ import annotations

import argparse
import json
import os


def _spec(a):
    from .livetest import TestSpec
    return TestSpec(seed=a.seed, n_records=a.records, rate_per_min=a.rate, bin_s=a.bin_s,
                    schedule_mb=[int(x) for x in a.schedule.split(",")])


def main(argv=None) -> int:
    from . import aws
    p = argparse.ArgumentParser(prog="prism_pipeline")
    p.add_argument("--region", default=aws.DEFAULT_REGION)
    p.add_argument("--seed", type=int, default=20261122)
    p.add_argument("--records", type=int, default=40, help="records per arm")
    p.add_argument("--rate", type=float, default=12.0, help="arrivals per minute")
    p.add_argument("--bin-s", type=float, default=12.0, help="seconds per controller bin (60 = paper time)")
    p.add_argument("--schedule", default="1024,512,2048,1024,1024", help="adapter arm memory per epoch")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    s = sub.add_parser("estimate"); s.add_argument("--out")
    s.add_argument("--price-lambda-gb-s", type=float); s.add_argument("--price-sfn-gb-s", type=float)
    sub.add_parser("asl")
    s = sub.add_parser("selftest"); s.add_argument("--out", required=True)
    s = sub.add_parser("analyse"); s.add_argument("--run", required=True); s.add_argument("--out", required=True)
    s.add_argument("--arms", default="baseline_ondemand,adapter_schedule")
    s = sub.add_parser("preflight"); s.add_argument("--execute", action="store_true")
    s = sub.add_parser("live-test"); s.add_argument("--out", required=True); s.add_argument("--execute", action="store_true")
    s.add_argument("--keep", action="store_true", help="do NOT tear down at the end (then run teardown yourself)")
    s.add_argument("--host-note", default="")
    s = sub.add_parser("teardown"); s.add_argument("--manifest"); s.add_argument("--execute", action="store_true")
    s = sub.add_parser("verify"); s.add_argument("--execute", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "plan":
        from .livetest import plan
        print("\n".join(plan(_spec(a), a.region)))
    elif a.cmd == "estimate":
        from .estimate import estimate
        sp = _spec(a)
        pr = {k: v for k, v in (("lambda_gb_s", a.price_lambda_gb_s), ("sfn_gb_s", a.price_sfn_gb_s)) if v}
        e = estimate(sp.n_records, sp.schedule_mb, smoke=sp.smoke, prices=pr)
        txt = json.dumps(e, indent=1)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(txt)
        print(txt)
    elif a.cmd == "asl":
        from .asl import definition_json
        print(definition_json({s: f"arn:aws:lambda:{a.region}:<account>:function:{aws.function_name(s)}"
                               for s in aws.STAGES}))
    elif a.cmd == "selftest":
        from .selftest import run_selftest
        r = run_selftest(a.out)
        print(json.dumps(r, indent=1, default=float))
        return 0 if r["ok"] else 1
    elif a.cmd == "analyse":
        from .analyse import analyse, write_tables
        from .estimate import PRICES_UNVERIFIED
        cw = os.path.join(a.run, "cloudwatch_reports.jsonl")
        res = analyse(a.run, a.arms.split(","), a.bin_s, cw, prices=PRICES_UNVERIFIED)
        write_tables(res, a.out)
        print(json.dumps({k: res[k] for k in ("integrity",)}, indent=1))
    elif a.cmd == "preflight":
        print("\n".join(aws.preflight(a.region, execute=a.execute)))
    elif a.cmd == "live-test":
        from .livetest import run
        r = run(a.out, _spec(a), a.region, execute=a.execute, keep=a.keep, host_note=a.host_note)
        if "plan" in r:
            print("PLAN ONLY (nothing called):\n" + "\n".join(r["plan"]))
        else:
            print(json.dumps({k: r.get(k) for k in ("error", "smoke", "teardown", "stopped")}, indent=1,
                             default=float))
            return 1 if r.get("error") or r.get("stopped") else 0
    elif a.cmd == "verify":
        print("\n".join(aws.verify(a.region, execute=a.execute)))
    elif a.cmd == "teardown":
        print("\n".join(aws.teardown(a.manifest, a.region, execute=a.execute)))
    return 0
