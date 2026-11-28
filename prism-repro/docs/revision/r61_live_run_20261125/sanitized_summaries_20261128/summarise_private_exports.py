#!/usr/bin/env python3
"""Sanitized summaries of two PRIVATE sources of the R6.1 replay day (25 Nov 2026 UTC), for public review.

Reads the private replay folder (layout: run/, billing/r61_billing_*/, cloudtrail/r61_cloudtrail_*/) and the public
../r61_results.json, and writes aggregates only:
  billing_export_20261125.{csv,md}     Cost Explorer estimated export: Lambda usage in us-east-2 and Lambda cost by
                                       record type (account-wide), with the replay's REPORT populations beside it
  report_populations_20261125.csv      saved Lambda REPORT records of the replay day, by population
  cloudtrail_pc_20261125.{csv,md}      CloudTrail provisioned-concurrency configuration events (us-east-2)
  summary.json                         every value above, machine-readable
  sources.sha256                       SHA-256 of each private file read (contents not published)
No request ID, ARN, account number, execution name or record content is written; the script stops if any output
contains one. No AWS call is made.

usage (from prism-repro/):
  python -I docs/revision/r61_live_run_20261125/sanitized_summaries_20261128/summarise_private_exports.py \
      <private replay folder> <new output folder>
then compare the new folder with this one (every file except README.md, this script, SHA256SUMS and .gitattributes).
"""
import csv
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC, OUT = sys.argv[1], sys.argv[2]
assert not os.path.exists(OUT), f"output folder exists: {OUT}"
os.makedirs(OUT)
PRICE_GB_S = 0.0000166667        # aws_pipeline/prism_pipeline/estimate.py PRICES_UNVERIFIED["lambda_gb_s"]
PRICE_REQ = 0.20 / 1e6           # PRICES_UNVERIFIED["lambda_request"]
PRICE_SFN_REQ = 1.00 / 1e6       # PRICES_UNVERIFIED["sfn_request"]
STAGES = ("ingest", "transform", "aggregate", "load")
used = []                        # private files read, relative to SRC


def rel(p):
    return os.path.relpath(p, SRC).replace(os.sep, "/")


def load_json(p):
    used.append(p)
    return json.load(open(p, encoding="utf-8"))


def load_jsonl(p):
    used.append(p)
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def one(pattern):
    hits = sorted(glob.glob(os.path.join(SRC, pattern)))
    assert len(hits) == 1, (pattern, len(hits))
    return hits[0]


def scope_lines(p):
    used.append(p)
    return [line.strip() for line in open(p, encoding="utf-8") if line.strip()]


# ------------------------------------------------------------------ public replay aggregates (for cross-checks)
PUB = json.load(open(os.path.join(HERE, "..", "r61_results.json"), encoding="utf-8"))
est = PUB["cost_usd_estimate_unverified_prices"]
cov = PUB["report_coverage"]
assert (cov["expected_request_ids"], cov["matched"], cov["missing"], cov["extra_reports"]) == (2596, 2596, 0, 56), cov

# ------------------------------------------------------------------ REPORT populations
reports = load_jsonl(os.path.join(SRC, "run", "cloudwatch_reports.jsonl"))
rep = {r["request_id"]: r for r in reports}
assert len(rep) == len(reports) == 2652, (len(rep), len(reports))
assert {r["memory_size_mb"] for r in reports} == {1024}


def gbs(r):
    return r["billed_duration_ms"] / 1000.0 * r["memory_size_mb"] / 1024.0


pops, seen = {}, set()
for arm in ("adapter_prism", "baseline_ondemand", "smoke"):
    for r in load_jsonl(os.path.join(SRC, "run", arm, "records.jsonl")):
        if r.get("type") != "record":
            continue
        for s in r["stages"]:
            i = s["aws_request_id"]
            assert i in rep and i not in seen
            seen.add(i)
            key = (arm, s["init_type"])
            pops.setdefault(key, [0, 0.0])
            pops[key][0] += 1
            pops[key][1] += gbs(rep[i])
extras = [r for i, r in rep.items() if i not in seen]


def tot(keys):
    return sum(pops[k][0] for k in keys), sum(pops[k][1] for k in keys)


arm_keys = [k for k in pops if k[0] != "smoke"]
n_arms, g_arms = tot(arm_keys)
n_smoke, g_smoke = tot([k for k in pops if k[0] == "smoke"])
n_pc, g_pc = tot([k for k in pops if k[1] == "provisioned-concurrency"])
n_ext, g_ext = len(extras), sum(gbs(r) for r in extras)
g_all = sum(gbs(r) for r in reports)
assert (n_arms, n_smoke, n_ext) == (2584, 12, 56), (n_arms, n_smoke, n_ext)
assert n_arms + n_smoke == cov["matched"]
# the harness estimate (public) is arm-only Lambda duration and requests at the unverified list prices
assert abs(g_arms * PRICE_GB_S - est["lambda_duration"]) < 1e-9, (g_arms, est["lambda_duration"])
assert abs(n_arms * PRICE_REQ - est["lambda_requests"]) < 1e-12 and round(est["sfn_requests"] / PRICE_SFN_REQ) == 646
per_fn = {}
for r in reports:
    st = r["log_group"].rsplit("-", 1)[-1]
    assert st in STAGES, st
    per_fn[st] = per_fn.get(st, 0) + 1
assert per_fn == {s: 663 for s in STAGES}, per_fn   # 646 replay + 3 smoke + 14 calibration-probe REPORTs per stage

# ------------------------------------------------------------------ run phase window (UTC), from the harness log
import datetime                                                                   # noqa: E402
notes = load_jsonl(os.path.join(SRC, "run", "livetest.log"))
t = [datetime.datetime.fromtimestamp(n["wall_ns"] / 1e9, datetime.timezone.utc) for n in notes]
first, last = min(t).strftime("%Y-%m-%dT%H:%M:%SZ"), max(t).strftime("%Y-%m-%dT%H:%M:%SZ")
assert first.startswith("2026-11-25") and last.startswith("2026-11-25"), (first, last)

# ------------------------------------------------------------------ billing export (Cost Explorer, estimated)
bdir = os.path.dirname(one("billing/r61_billing_*/ohio_usage_and_cost.json"))
b_scope = scope_lines(os.path.join(bdir, "export_scope.txt"))
exported = re.search(r"Exported: (\d{8}T\d{6}Z)", "\n".join(b_scope)).group(1)
ohio = load_json(os.path.join(bdir, "ohio_usage_and_cost.json"))
acct = load_json(os.path.join(bdir, "account_cost_by_record_type.json"))
assert [g["Key"] for g in ohio["GroupDefinitions"]] == ["SERVICE", "USAGE_TYPE"]
assert [g["Key"] for g in acct["GroupDefinitions"]] == ["SERVICE", "RECORD_TYPE"]
(po,), (pa,) = ohio["ResultsByTime"], acct["ResultsByTime"]
assert po["TimePeriod"] == pa["TimePeriod"] == {"Start": "2026-11-25", "End": "2026-11-26"}
assert po["Estimated"] is True and pa["Estimated"] is True
lam = {g["Keys"][1]: g["Metrics"] for g in po["Groups"] if g["Keys"][0] == "AWS Lambda"}
assert set(lam) == {"USE2-Request", "USE2-Lambda-GB-Second", "USE2-Lambda-Provisioned-GB-Second"}, sorted(lam)
rec = {g["Keys"][1]: g["Metrics"] for g in pa["Groups"] if g["Keys"][0] == "AWS Lambda"}
assert set(rec) == {"Usage", "Credit"}, sorted(rec)
q = {k: float(v["UsageQuantity"]["Amount"]) for k, v in lam.items()}
c = {k: float(v["UnblendedCost"]["Amount"]) for k, v in lam.items()}
u = {k: v["UsageQuantity"]["Unit"] for k, v in lam.items()}
rc = {k: float(v["UnblendedCost"]["Amount"]) for k, v in rec.items()}
assert q["USE2-Request"] == 2568 and round(q["USE2-Lambda-GB-Second"], 3) == 3255.356
assert round(q["USE2-Lambda-Provisioned-GB-Second"], 3) == 2219.792 and all(v == 0 for v in c.values())
assert round(rc["Usage"], 6) == 0.021581 and round(rc["Credit"], 6) == -0.021581
billed_gbs = q["USE2-Lambda-GB-Second"] + q["USE2-Lambda-Provisioned-GB-Second"]

bill_rows = [
    ["regional (us-east-2)", "AWS Lambda", "usage type USE2-Request", f"{q['USE2-Request']:.0f}", u["USE2-Request"], f"{c['USE2-Request']:.6f}"],
    ["regional (us-east-2)", "AWS Lambda", "usage type USE2-Lambda-GB-Second (on-demand duration)", f"{q['USE2-Lambda-GB-Second']:.4f}", u["USE2-Lambda-GB-Second"], f"{c['USE2-Lambda-GB-Second']:.6f}"],
    ["regional (us-east-2)", "AWS Lambda", "usage type USE2-Lambda-Provisioned-GB-Second (duration on provisioned environments)", f"{q['USE2-Lambda-Provisioned-GB-Second']:.4f}", u["USE2-Lambda-Provisioned-GB-Second"], f"{c['USE2-Lambda-Provisioned-GB-Second']:.6f}"],
    ["account-wide (all regions)", "AWS Lambda", "record type Usage", "", "", f"{rc['Usage']:.6f}"],
    ["account-wide (all regions)", "AWS Lambda", "record type Credit", "", "", f"{rc['Credit']:.6f}"],
]
with open(os.path.join(OUT, "billing_export_20261125.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["scope", "service", "line", "quantity", "unit", "unblended_cost_usd"])
    w.writerows(bill_rows)

pop_rows = [
    ["replay arms (PRISM + OnDemand): stage executions", n_arms, f"{g_arms:.3f}", "matched to run records; the harness estimate's population (TR3, TR5)"],
    ["  of which served by provisioned concurrency (PRISM arm)", n_pc, f"{g_pc:.3f}", "init type provisioned-concurrency in the run records"],
    ["smoke run: stage executions", n_smoke, f"{g_smoke:.3f}", "matched to run records"],
    ["matched REPORT records (replay arms + smoke)", n_arms + n_smoke, f"{g_arms + g_smoke:.3f}", "report_coverage.matched in r61_results.json"],
    ["calibration-probe REPORTs (unmatched extras)", n_ext, f"{g_ext:.3f}", "report_coverage.extra_reports in r61_results.json"],
    ["all saved REPORT records of the replay", len(reports), f"{g_all:.3f}", f"every run phase {first} to {last}, inside the export's UTC day"],
]
with open(os.path.join(OUT, "report_populations_20261125.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["population", "report_records", "billed_gb_s", "definition"])
    w.writerows(pop_rows)

# ------------------------------------------------------------------ CloudTrail: provisioned-concurrency configuration
cdir = os.path.dirname(one("cloudtrail/r61_cloudtrail_*/ohio_management_events.json"))
c_scope = scope_lines(os.path.join(cdir, "export_scope.txt"))
c_exported = re.search(r"Exported: (\d{8}T\d{6}Z)", "\n".join(c_scope)).group(1)
window = re.search(r"CloudTrail lookup: (us-east-2), (\d\d:\d\d)\u2013(\d\d:\d\d) UTC", "\n".join(c_scope)).groups()
ev = [json.loads(e["CloudTrailEvent"]) for e in load_json(os.path.join(cdir, "ohio_management_events.json"))["Events"]]
assert {e["awsRegion"] for e in ev} == {"us-east-2"}
counts, rows_ct = {}, []
for e in ev:
    n = e["eventName"]
    if "ProvisionedConcurrency" not in n:
        continue
    k = (n, e.get("errorCode") or "none")
    counts[k] = counts.get(k, 0) + 1
    if n in ("PutProvisionedConcurrencyConfig", "DeleteProvisionedConcurrencyConfig"):
        rp = e.get("requestParameters") or {}
        stage = str(rp.get("functionName", "")).rsplit("-", 1)[-1]
        assert stage in STAGES, "unexpected function"
        rows_ct.append([e["eventTime"], n, stage, "" if rp.get("provisionedConcurrentExecutions") is None
                        else str(rp["provisionedConcurrentExecutions"]), e.get("errorCode") or "none"])
rows_ct.sort()
puts = [r for r in rows_ct if r[1].startswith("Put")]
dels = [r for r in rows_ct if r[1].startswith("Delete")]
assert len(puts) == 5 and all(r[4] == "none" for r in puts), puts
assert len(dels) == 12 and all(r[4] == "none" for r in dels), dels
# the public harness record of the same decisions: epoch 0 sets 1/2/2/1, epoch 1 lowers aggregate to 1
rd = PUB["pc_readiness"]
k0 = {q_["stage"]: q_["requested"] for q_ in rd if q_["k"] == 0}
k1 = {q_["stage"]: q_["requested"] for q_ in rd if q_["k"] == 1}
assert k0 == {"ingest": 1, "transform": 2, "aggregate": 2, "load": 1} and k1 == {"aggregate": 1}
t_put = sorted({r[0] for r in puts})
assert len(t_put) == 2 and {r[2]: int(r[3]) for r in puts if r[0] == t_put[0]} == k0
assert {r[2]: int(r[3]) for r in puts if r[0] == t_put[1]} == k1
lag0 = sorted({q_["activation_lag_s"] for q_ in rd if q_["k"] == 0})
lag1 = sorted({q_["activation_lag_s"] for q_ in rd if q_["k"] == 1})
assert lag0 == [82.8] and lag1 == [20.1]
t_del = sorted({r[0] for r in dels})
assert len(t_del) == 3 and all(sum(1 for r in dels if r[0] == x) == 4 for x in t_del)
phase = {t_del[0]: "reset before the OnDemand arm", t_del[1]: "reset before the PRISM arm",
         t_del[2]: "teardown", t_put[0]: "PRISM decision epoch 0: initial allocation",
         t_put[1]: "PRISM decision epoch 1: decrease (aggregate 2 -> 1)"}
for r in rows_ct:
    r.append(phase[r[0]])
with open(os.path.join(OUT, "cloudtrail_pc_20261125.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["event_time_utc", "event_name", "stage", "requested_units", "error_code", "phase"])
    w.writerows(rows_ct)
get_ok = counts.get(("GetProvisionedConcurrencyConfig", "none"), 0)
get_nf = counts.get(("GetProvisionedConcurrencyConfig", "ProvisionedConcurrencyConfigNotFoundException"), 0)
assert sum(v for (n, _), v in counts.items() if n.startswith("Get")) == get_ok + get_nf
gt = {k: sorted(e["eventTime"] for e in ev if e["eventName"] == "GetProvisionedConcurrencyConfig"
                and (e.get("errorCode") or "none") == k) for k in ("none", "ProvisionedConcurrencyConfigNotFoundException")}
# NotFound reads all fall in the OnDemand arm (before the PRISM arm's reset), successful reads in the PRISM arm
assert gt["ProvisionedConcurrencyConfigNotFoundException"][-1] < t_del[1] < t_put[0] <= gt["none"][0], gt
ev_t = sorted(e["eventTime"] for e in ev)

# ------------------------------------------------------------------ summary.json and the two summaries
summary = {
    "billing_export": {
        "source": "AWS Cost Explorer, estimated (private; SHA-256 in sources.sha256)", "exported_utc": exported,
        "period_utc": po["TimePeriod"], "estimated": True,
        "regional_us_east_2_lambda": {k: {"quantity": q[k], "unit": u[k], "unblended_cost_usd": c[k]} for k in sorted(q)},
        "account_wide_lambda_by_record_type_usd": rc,
        "provisioned_concurrency_capacity_line": False,
        "billed_gb_s_total_regional": round(billed_gbs, 4),
    },
    "report_populations": {r[0].strip(): {"report_records": r[1], "billed_gb_s": float(r[2])} for r in pop_rows},
    "harness_estimate_check": {"lambda_requests": n_arms, "lambda_billed_gb_s": round(g_arms, 3),
                               "price_lambda_gb_s_unverified": PRICE_GB_S, "lambda_duration_usd": est["lambda_duration"],
                               "sfn_executions": 646, "total_usd_unverified_prices": round(sum(est.values()), 4)},
    "comparison": {"saved_reports_minus_billed_requests": len(reports) - int(q["USE2-Request"]),
                   "saved_report_gb_s_minus_billed_gb_s": round(g_all - billed_gbs, 3),
                   "pc_served_report_gb_s_minus_provisioned_gb_s": round(g_pc - q["USE2-Lambda-Provisioned-GB-Second"], 3),
                   "status": "not reconciled: the populations have different scopes"},
    "cloudtrail": {"source": "CloudTrail management events (private; SHA-256 in sources.sha256)",
                   "exported_utc": c_exported, "lookup": {"region": window[0], "from_utc": window[1], "to_utc": window[2]},
                   "events_in_export": len(ev), "event_time_range_utc": [ev_t[0], ev_t[-1]],
                   "provisioned_concurrency_events": {f"{n} / {e_}": v for (n, e_), v in sorted(counts.items())},
                   "status_reads_utc": {k: [v[0], v[-1]] for k, v in gt.items()}},
    "readiness_from_harness_polling": {"source": "../r61_results.json pc_readiness (public)",
                                       "epoch0_initial_allocation_ready_after_s": lag0[0],
                                       "epoch1_decrease_ready_after_s": lag1[0]},
    "run_window_utc": [first, last],
}
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8", newline="\n"), indent=1, sort_keys=True)

md_b = [
    "# Estimated billing export of 25 Nov 2026 (UTC): sanitized summary",
    "",
    f"**Source.** AWS Cost Explorer export, taken {exported[:4]}-{exported[4:6]}-{exported[6:8]} {exported[9:11]}:{exported[11:13]} UTC;",
    "period 2026-11-25 00:00 to 2026-11-26 00:00 UTC (one full UTC day); **Estimated: true**. The export is private (it",
    "carries account data); its three files are identified by SHA-256 in `sources.sha256`. A checksum identifies the file;",
    "checking these numbers against it still needs access to the export. Built by `summarise_private_exports.py` (no AWS",
    "call).",
    "",
    "**Scope.** The usage lines are **regional**: all of the account's Lambda usage in us-east-2 on that UTC day, not only",
    "the replay. The record-type lines are **account-wide** (all regions). The export files do not store their query",
    "filters; these scopes follow the export's file names (`ohio_usage_and_cost.json`, `account_cost_by_record_type.json`)",
    "and the method documented for the 22 Nov export (`../../billing_reconciliation_20261124/README.md`).",
    "",
    "| Scope | Line | Quantity | Unit | Unblended cost (USD) |",
    "|---|---|---|---|---|",
] + [f"| {r[0]} | {r[2]} | {r[3] if r[3] else '-'} | {r[4] if r[4] else '-'} | {r[5]} |" for r in bill_rows] + [
    "",
    "There is no separate provisioned-concurrency capacity line. Every regional Lambda line is priced at USD 0; the",
    f"account-wide Lambda usage of USD {rc['Usage']:.6f} is offset by a credit of the same size. The export names only the",
    "record type `Credit`; it does not say what the credit is.",
    "",
    "**The replay's own REPORT records** (`report_populations_20261125.csv`; every run phase lies between "
    f"{first[11:19]} and",
    f"{last[11:19]} UTC on 25 Nov, inside the export's day):",
    "",
    "| Population | REPORT records | Billed GB-s |",
    "|---|---|---|",
] + [f"| {r[0].strip()} | {r[1]:,} | {float(r[2]):,.1f} |" for r in pop_rows] + [
    "",
    f"- **2,584** is the replay arms' Lambda requests (stage executions); with **5,560.3** billed GB-s it is the population",
    "  of the harness estimate: 5,560.316 GB-s x USD 0.0000166667 = USD 0.0926721 (`lambda_duration` in",
    "  `../r61_results.json`; price from `aws_pipeline/prism_pipeline/estimate.py`, `PRICES_UNVERIFIED`). The estimate is",
    "  at unverified list prices, counts all duration at the on-demand rate, adds 646 Step Functions executions and",
    "  excludes provisioned-concurrency capacity. It is not a bill.",
    "- **2,596** is the matched REPORT records: the replay arms plus 12 smoke-run stage executions.",
    "- **2,652** is every saved REPORT record: the 2,596 plus 56 calibration-probe REPORTs that match no run record.",
    f"- **2,568** is the export's us-east-2 Lambda requests. The saved REPORT records exceed it by {len(reports) - int(q['USE2-Request'])}",
    f"  (2,652 - 2,568), and their billed GB-s exceed the export's {billed_gbs:,.3f} by {g_all - billed_gbs:,.1f}. The populations",
    "  have different scopes (one account-region-day of billing against one run's saved logs), and the export is",
    "  provisional. **The difference is not reconciled.**",
    f"- Informational, not a reconciliation: the PRISM arm's stage executions served by provisioned concurrency bill",
    f"  {g_pc:,.1f} GB-s in their REPORT records; the export lists {q['USE2-Lambda-Provisioned-GB-Second']:,.3f} GB-s on provisioned environments.",
    "",
    "**Still open.** The final charges attributable to the replay (they need the final bill or a Cost and Usage Report),",
    "and what the credit is.",
]
open(os.path.join(OUT, "billing_export_20261125.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md_b) + "\n")

md_c = [
    "# Provisioned-concurrency configuration requests in CloudTrail, R6.1 replay (25 Nov 2026): sanitized summary",
    "",
    f"**Source.** CloudTrail management events of the account, {window[0]}, lookup {window[1]}-{window[2]} UTC on 25 Nov 2026,",
    f"exported {c_exported[9:11]}:{c_exported[11:13]} UTC: {len(ev):,} events between {ev_t[0][11:19]} and {ev_t[-1][11:19]} UTC, all in us-east-2. The export",
    "is private (it carries account data); its two files are identified by SHA-256 in `sources.sha256`. This summary keeps",
    "event times, stages, requested units and error codes only. Built by `summarise_private_exports.py` (no AWS call).",
    "",
    "**Configuration requests (`cloudtrail_pc_20261125.csv`):**",
    "",
    "| Time (UTC) | Event | Stage | Requested units | Error code | Phase |",
    "|---|---|---|---|---|---|",
] + [f"| {r[0][11:19]} | {r[1]} | {r[2]} | {r[3] or '-'} | {r[4]} | {r[5]} |" for r in rows_ct] + [
    "",
    f"- **{len(puts)} PutProvisionedConcurrencyConfig requests, none with an error code**: four at {t_put[0][11:19]} UTC (the initial",
    f"  allocation of 1/2/2/1 units at PRISM's first decision) and one at {t_put[1][11:19]} UTC (the next decision, lowering",
    "  aggregate from 2 to 1). They equal the PRISM arm's recorded requests (`pc_readiness` in `../r61_results.json`).",
    f"- {len(dels)} DeleteProvisionedConcurrencyConfig requests, none with an error code: the harness's reset of the four",
    "  aliases before each arm and at teardown (`clear_pc` in `aws_pipeline/prism_pipeline/adapter.py`).",
    f"- {get_ok + get_nf:,} GetProvisionedConcurrencyConfig calls are the harness's read-only status reads (`poll_pc`, same file),",
    f"  not configuration requests: {get_ok:,} during the PRISM arm ({gt['none'][0][11:19]}-{gt['none'][-1][11:19]} UTC) and {get_nf:,} during",
    f"  the OnDemand arm ({gt['ProvisionedConcurrencyConfigNotFoundException'][0][11:19]}-{gt['ProvisionedConcurrencyConfigNotFoundException'][-1][11:19]} UTC), "
    "which returned `ProvisionedConcurrencyConfigNotFoundException` because no configuration existed.",
    "",
    "**Acceptance is not readiness.** CloudTrail shows that AWS accepted each request. When the capacity became usable is",
    "measured separately, by the harness polling the configuration status every 10 s (`pc_readiness` in",
    f"`../r61_results.json`; TR3): READY was first observed {lag0[0]} s after the initial allocation and {lag1[0]} s after the",
    "later decrease. Two observations from one replay.",
]
open(os.path.join(OUT, "cloudtrail_pc_20261125.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md_c) + "\n")

# ------------------------------------------------------------------ sources.sha256 (private files read)
with open(os.path.join(OUT, "sources.sha256"), "w", encoding="utf-8", newline="\n") as f:
    for p in sorted(set(used)):
        f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {rel(p)}\n")

# ------------------------------------------------------------------ privacy check of every output
BAD = [re.compile(r"\b\d{12}\b"), re.compile(r"arn:aws", re.I),
       re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), re.compile(r"[A-Za-z]:[\\/]|/home/|/mnt/")]
for fn in os.listdir(OUT):
    text = open(os.path.join(OUT, fn), encoding="utf-8").read()
    for b in BAD:
        assert not b.search(text), (fn, b.pattern)
print(f"wrote {len(os.listdir(OUT))} files to {OUT}; all checks passed")
