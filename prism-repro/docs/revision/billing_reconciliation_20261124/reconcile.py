#!/usr/bin/env python3
"""R2.14(b), R2.8, R6.2: provisional reconciliation of the AWS Cost Explorer export (us-east-2, daily UTC) with the
saved Lambda REPORT records and run records of 22 Nov 2026 UTC. Reads private archives given as arguments and
writes AGGREGATES ONLY (no request IDs, account identifiers, paths or other services' charges). No AWS call.

usage: python reconcile.py <billing export folder> <memcal run folder> <live test 21 Nov 20:30 CST folder>
                           <live test 22 Nov 09:02 CST folder> <out dir>
"""
import csv
import hashlib
import json
import os
import sys

OD_GBS, REQ = 1.66667e-5, 2e-7          # manuscript list prices (prism_repro.config.Prices); not claimed current
EXP, MEM, LA, LB, OUT = sys.argv[1:6]


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---- the export: us-east-2, 22 Nov 2026 UTC, Lambda and Step Functions rows only
ohio = json.load(open(os.path.join(EXP, "ohio_usage_and_cost.json"), encoding="utf-8"))
day = {p["TimePeriod"]["Start"]: p for p in ohio["ResultsByTime"]}
rows22 = {tuple(g["Keys"]): g["Metrics"] for g in day["2026-11-22"]["Groups"]}
rows21 = {tuple(g["Keys"]): g["Metrics"] for g in day["2026-11-21"]["Groups"]}
q = lambda r, k: float(r[k]["UsageQuantity"]["Amount"])  # noqa: E731
lam_req = q(rows22, ("AWS Lambda", "USE2-Request"))
lam_gbs = q(rows22, ("AWS Lambda", "USE2-Lambda-GB-Second"))
lam_cost = sum(float(v["UnblendedCost"]["Amount"]) for k, v in rows22.items() if k[0] == "AWS Lambda")
sfn_req = q(rows22, ("AWS Step Functions", "USE2-StepFunctions-Request"))
sfn_gbs = q(rows22, ("AWS Step Functions", "USE2-StepFunctions-GB-Second"))
acct = json.load(open(os.path.join(EXP, "account_cost_by_record_type.json"), encoding="utf-8"))
acct22 = {tuple(g["Keys"]): float(g["Metrics"]["UnblendedCost"]["Amount"])
          for p in acct["ResultsByTime"] if p["TimePeriod"]["Start"] == "2026-11-22" for g in p["Groups"]}
lam_credit_rows = [k for k in acct22 if k[0] == "AWS Lambda" and k[1] != "Usage"]
export = dict(
    exported_utc="2026-11-24T06:39:28Z", periods_utc=["2026-11-21", "2026-11-22"], granularity="DAILY",
    region_ohio_file="us-east-2", grouping_ohio="SERVICE, USAGE_TYPE", grouping_account="SERVICE, RECORD_TYPE (all regions)",
    estimated={k: bool(v["Estimated"]) for k, v in day.items()},
    estimated_account={p["TimePeriod"]["Start"]: bool(p["Estimated"]) for p in acct["ResultsByTime"]},
    lambda_rows_on_2026_11_21=[k for k in rows21 if k[0] == "AWS Lambda"],
    lambda_requests=lam_req, lambda_gb_s=lam_gbs, lambda_unblended_usd=lam_cost,
    lambda_unblended_usd_account_wide=acct22.get(("AWS Lambda", "Usage")),
    lambda_non_usage_record_types_account_wide=[k[1] for k in lam_credit_rows],
    step_functions_requests=sfn_req, step_functions_gb_s=sfn_gbs,
    units={"lambda_requests": rows22[("AWS Lambda", "USE2-Request")]["UsageQuantity"]["Unit"],
           "lambda_gb_s": rows22[("AWS Lambda", "USE2-Lambda-GB-Second")]["UsageQuantity"]["Unit"],
           "cost": rows22[("AWS Lambda", "USE2-Request")]["UnblendedCost"]["Unit"]},
    source_sha256={f: sha(os.path.join(EXP, f)) for f in ("ohio_usage_and_cost.json", "account_cost_by_record_type.json",
                                                         "export_scope.txt")})

# ---- saved records (all inside 22 Nov 2026 UTC; see README for the time checks)
rep = {r["request_id"]: r for r in jl(os.path.join(MEM, "cloudwatch_reports.jsonl"))}
gbs = lambda ids, R: sum(R[i]["billed_duration_ms"] / 1000 * R[i]["memory_size_mb"] / 1024 for i in ids)  # noqa: E731
blk = {r["request_id"] for r in jl(os.path.join(MEM, "records.jsonl")) if r.get("type") == "invocation"}
smk = {r["request_id"] for r in jl(os.path.join(MEM, "smoke", "records.jsonl")) if r.get("type") == "invocation"}
assert blk <= set(rep) and smk <= set(rep) and not (blk & smk)
extra = set(rep) - blk - smk
repB = {r["request_id"]: r for r in jl(os.path.join(LB, "cloudwatch_reports.jsonl"))}
repA = jl(os.path.join(LA, "cloudwatch_reports.jsonl"))
idsA = {s["aws_request_id"] for arm in ("smoke", "baseline_ondemand", "adapter_schedule")
        for r in jl(os.path.join(LA, arm, "records.jsonl")) if r.get("type") == "record"
        for s in r.get("stages", []) if s.get("aws_request_id")}
assert not (set(repB) & set(rep)) and not (idsA & set(rep)) and not (idsA & set(repB))
sfn_exec = sum(1 for d in (LA, LB) for arm in ("smoke", "baseline_ondemand", "adapter_schedule")
               for r in jl(os.path.join(d, arm, "records.jsonl")) if r.get("type") == "record" and r.get("status") != "NOT_RUN")

lines = [
    ("memcal-1 calibration blocks 0-2 (17:17-19:51 UTC)", len(blk), gbs(blk, rep), "REPORT records"),
    ("memcal-1 smoke run (17:11-17:13 UTC)", len(smk), gbs(smk, rep), "REPORT records"),
    ("memcal-1 log groups, REPORTs without a campaign record (17:01-20:03 UTC)", len(extra), gbs(extra, rep), "REPORT records"),
    ("live test, 22 Nov 09:02 CST (15:02-15:08 UTC)", len(repB), gbs(repB, repB), "REPORT records"),
]
sub_req, sub_gbs = sum(x[1] for x in lines), sum(x[2] for x in lines)
res_req, res_gbs = lam_req - sub_req, lam_gbs - sub_gbs
table = [dict(line=n, requests=r, gb_s=round(g, 6), source=s) for n, r, g, s in lines]
table += [dict(line="subtotal with REPORT records", requests=sub_req, gb_s=round(sub_gbs, 6), source="sum"),
          dict(line="live test, 21 Nov 20:30 CST (02:30-02:55 UTC 22 Nov): stage invocations with saved request IDs",
               requests=len(idsA), gb_s=None, source=f"run records; REPORT lines not saved ({len(repA)} saved)"),
          dict(line="export: us-east-2 Lambda, 22 Nov 2026 UTC", requests=lam_req, gb_s=round(lam_gbs, 6),
               source="Cost Explorer, Estimated"),
          dict(line="residual after REPORT-attributed lines", requests=res_req, gb_s=round(res_gbs, 6), source="export - subtotal"),
          dict(line="residual after also counting the 21 Nov live test's saved request IDs", requests=res_req - len(idsA),
               gb_s=None, source="unattributed")]
calib = dict(requests=len(blk), gb_s=gbs(blk, rep), usd_list=gbs(blk, rep) * OD_GBS + len(blk) * REQ,
             usd_duration=gbs(blk, rep) * OD_GBS, usd_requests=len(blk) * REQ)
diff = dict(requests=lam_req - len(blk), gb_s=lam_gbs - gbs(blk, rep))
out = dict(export=export, calibration_blocks=calib, export_minus_blocks=diff, table=table,
           step_functions=dict(export_requests=sfn_req, saved_executions=sfn_exec,
                               scope="Step Functions only; not part of the Lambda calibration estimate"))
os.makedirs(OUT, exist_ok=True)
json.dump(out, open(os.path.join(OUT, "reconciliation.json"), "w", encoding="utf-8", newline="\n"), indent=1)
with open(os.path.join(OUT, "reconciliation.csv"), "w", encoding="utf-8", newline="\n") as f:
    w = csv.DictWriter(f, fieldnames=["line", "requests", "gb_s", "source"], lineterminator="\n")
    w.writeheader()
    w.writerows(table)
print(json.dumps(out, indent=1))
