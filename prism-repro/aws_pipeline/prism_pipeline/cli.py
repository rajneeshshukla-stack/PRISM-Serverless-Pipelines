"""Command line. Run from prism-repro/aws_pipeline:  python -m prism_pipeline <command> ...

Local (no AWS):  plan, estimate, asl, selftest, analyse, coverage
AWS (plan only unless --execute AND PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES):  preflight, live-test, collect, teardown,
  cleanup-logs, verify
"""
from __future__ import annotations

import argparse
import json
import os


def _spec(a):
    from .livetest import TestSpec
    return TestSpec(seed=a.seed, n_records=a.records, rate_per_min=a.rate, bin_s=a.bin_s,
                    schedule_mb=[int(x) for x in a.schedule.split(",")], mode=a.mode, trace_seed=a.trace_seed,
                    scenario=a.scenario, n_epochs=a.epochs, thin=a.thin, prism_eps=a.eps, forecaster=a.forecaster,
                    pc_mode=a.pc_mode, pc_cap=a.pc_cap)


def main(argv=None) -> int:
    from . import aws
    p = argparse.ArgumentParser(prog="prism_pipeline")
    p.add_argument("--region", default=aws.DEFAULT_REGION)
    p.add_argument("--seed", type=int, default=20261122)
    p.add_argument("--records", type=int, default=40, help="records per arm")
    p.add_argument("--rate", type=float, default=12.0, help="arrivals per minute")
    p.add_argument("--bin-s", type=float, default=12.0, help="seconds per controller bin (60 = paper time)")
    p.add_argument("--schedule", default="1024,512,2048,1024,1024", help="adapter arm memory per epoch")
    p.add_argument("--mode", choices=("schedule", "prism_replay"), default="schedule",
                   help="prism_replay (R6.1): PRISM's controller vs OnDemand on the same thinned trace replay")
    p.add_argument("--trace-seed", type=int, default=101)
    p.add_argument("--scenario", default="stationary")
    p.add_argument("--epochs", type=int, default=8, help="prism_replay: decision epochs replayed (5 minutes each)")
    p.add_argument("--thin", type=float, default=1 / 60, help="prism_replay: fraction of trace requests kept")
    p.add_argument("--eps", type=float, default=0.02, help="prism_replay: PRISM risk budget")
    p.add_argument("--forecaster", default="gbm", help="prism_replay: PRISM's forecaster")
    p.add_argument("--pc-mode", choices=("record", "apply"), default="record",
                   help="prism_replay: 'apply' configures PRISM's provisioned concurrency through a published alias")
    p.add_argument("--pc-cap", type=int, default=4, help="apply: provisioned concurrency cap per stage (cost bound)")
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
    s.add_argument("--delete-log-groups", choices=("auto", "always", "never"), default="auto",
                   help="auto: delete them only if REPORT coverage is complete (default)")
    s = sub.add_parser("verify"); s.add_argument("--execute", action="store_true")
    s = sub.add_parser("collect", help="resume (or start) REPORT collection for a run, then check coverage")
    s.add_argument("--manifest", required=True); s.add_argument("--execute", action="store_true")
    s.add_argument("--start-ms", type=int); s.add_argument("--end-ms", type=int)
    s.add_argument("--rescan", action="store_true", help="re-read every group from the start (late REPORT lines)")
    s = sub.add_parser("coverage", help="local: recorded request IDs against saved REPORT records")
    s.add_argument("--run", required=True)
    s = sub.add_parser("cleanup-logs", help="delete this run's retained log groups once coverage is complete")
    s.add_argument("--manifest", required=True); s.add_argument("--execute", action="store_true")
    s.add_argument("--force-delete-incomplete", action="store_true")
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
            print(json.dumps({k: r.get(k) for k in ("verified", "coverage", "error", "smoke", "teardown", "stopped")},
                             indent=1, default=float))
            return 0 if r.get("verified") else 1
    elif a.cmd == "verify":
        print("\n".join(aws.verify(a.region, execute=a.execute)))
    elif a.cmd == "teardown":
        print("\n".join(aws.teardown(a.manifest, a.region, execute=a.execute, delete_log_groups=a.delete_log_groups)))
    elif a.cmd == "collect":
        out = aws.collect_reports(a.manifest, a.start_ms, a.end_ms, execute=a.execute, rescan=a.rescan)
        print("\n".join(out))
        if a.execute:
            cov = aws.report_coverage(os.path.dirname(os.path.abspath(a.manifest)))
            print(json.dumps({k: v for k, v in cov.items() if k != "missing_ids"}, indent=1))
            return 0 if cov["complete"] else 1
    elif a.cmd == "coverage":
        cov = aws.report_coverage(a.run)
        print(json.dumps(cov, indent=1))
        return 0 if cov["complete"] else 1
    elif a.cmd == "cleanup-logs":
        out = aws.cleanup_log_groups(a.manifest, a.region, execute=a.execute, force=a.force_delete_incomplete)
        print("\n".join(out))
        return 1 if any(x.startswith(("REFUSED", "NOT CLEAN")) for x in out) else 0
    return 0
