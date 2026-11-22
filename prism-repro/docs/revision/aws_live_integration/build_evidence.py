"""Build the sanitized aggregate tables of the live integration run livetest_20261121-203051.

Reads the private run folder and the private CloudTrail lookup-events exports (neither is in Git) and writes only
aggregate tables to <out>/tables/ plus SHA-256 hashes of the inputs to <out>/sources.sha256. No account ID, ARN,
access-key ID, IP address, request ID, full CloudTrail event or invocation record is written; the last step scans
every output file for such patterns and exits non-zero if it finds one.

Usage (from the repository root, standard library only):
    python prism-repro/docs/revision/aws_live_integration/build_evidence.py \
        --run "AWS Live Implementation Log/AWS_livetest_20261121-203051" \
        --cloudtrail "../PRISM_tracker_backups/AWS_livetest_20261121-203051_cloudtrail_KD9ijx" \
        --out prism-repro/docs/revision/aws_live_integration
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import statistics as st
import sys
from collections import Counter, defaultdict

ARMS = ("baseline_ondemand", "adapter_schedule")
STAGES = ("ingest", "transform", "aggregate", "load")


def jl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def records(run, arm):
    return [r for r in jl(os.path.join(run, arm, "records.jsonl")) if r["type"] == "record"]


def q(xs, p):
    """Linear-interpolation percentile (numpy's default), p in [0, 100]."""
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    return st.quantiles(xs, n=100, method="inclusive")[p - 1] if 0 < p < 100 else (xs[0] if p == 0 else xs[-1])


def r3(x):
    return None if x is None else round(x, 3)


def write(out, name, header, rows):
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    with open(os.path.join(out, "tables", name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def group_of(rec):
    mems = [s["memory_mb"] for s in rec["stages"]]
    if len(set(mems)) == 1:
        return f"all stages {mems[0]} MB"
    return f"crossed {mems[0]} to {mems[-1]} MB"


def e2e_service(rec):
    s = rec["stages"]
    return rec["e2e_s"] - (s[-1]["end_wall_ns"] - s[0]["start_wall_ns"]) / 1e9


def build_run_tables(run, out, log):
    recs = {a: records(run, a) for a in ARMS}
    plan = jl(os.path.join(run, "records_plan.jsonl"))
    # ---------------------------------------------------------------- arms and pairing
    rows = []
    for a in ARMS:
        rs = recs[a]
        e = [r["e2e_s"] for r in rs]
        oc = Counter(r["outcome"] for r in rs)
        summ = [x for x in jl(os.path.join(run, a, "records.jsonl")) if x["type"] == "arm_summary"][0]
        sfn_gbs = sum(r["billing"]["billedDurationInMilliseconds"] / 1000 * r["billing"]["billedMemoryUsedInMB"] / 1024
                      for r in rs)
        rows.append([a, len(rs), oc["met"], oc["missed"], sum(r["status"] != "SUCCEEDED" for r in rs),
                     oc.get("shed_client_cap", 0), summ["max_in_flight"], r3(q(e, 50)), r3(q(e, 95)), r3(max(e)),
                     round(sfn_gbs, 2)])
        log.append(f"{a}: n={len(rs)} met={oc['met']} missed={oc['missed']} statuses={dict(Counter(r['status'] for r in rs))}")
    write(out, "arms.csv", ["arm", "records", "met", "missed", "execution_failures", "shed_client_cap",
                            "max_in_flight", "e2e_p50_s", "e2e_p95_s", "e2e_max_s", "sfn_billed_gb_s"], rows)
    b = {r["record_id"]: r for r in recs["baseline_ondemand"]}
    s = {r["record_id"]: r for r in recs["adapter_schedule"]}
    same_ids = set(b) == set(s) == {p["record_id"] for p in plan}
    same_docs = all(b[k]["result"]["ingest"]["sha256"] == s[k]["result"]["ingest"]["sha256"] for k in b)
    log.append(f"paired: same record IDs as plan={same_ids}; identical ingest digests={same_docs}")
    pairs = Counter((b[k]["outcome"], s[k]["outcome"]) for k in b)
    write(out, "paired_deadlines.csv", ["baseline_ondemand_outcome", "adapter_schedule_outcome", "records"],
          [[x, y, pairs[(x, y)]] for x, y in (("met", "met"), ("met", "missed"), ("missed", "met"), ("missed", "missed"))])
    # ---------------------------------------------------------------- observed memory groups
    rows = []
    for a in ARMS:
        g = defaultdict(list)
        for r in recs[a]:
            g[group_of(r)].append(r)
        order = sorted(g, key=lambda k: (k.startswith("crossed"), k))
        for k in order:
            e = [r["e2e_s"] for r in g[k]]
            rows.append([a, k, len(g[k]), sum(r["outcome"] == "met" for r in g[k]),
                         sum(r["outcome"] == "missed" for r in g[k]), r3(st.median(e)), r3(min(e)), r3(max(e)),
                         sum(any(x["cold"] for x in r["stages"]) for r in g[k])])
    write(out, "memory_groups.csv", ["arm", "observed_memory", "records", "met", "missed", "e2e_median_s", "e2e_min_s",
                                     "e2e_max_s", "records_with_a_cold_stage"], rows)
    # ---------------------------------------------------------------- warm handler time per 1000 words, by memory
    w = defaultdict(list)
    for a in ARMS:
        for r in recs[a]:
            for x in r["stages"]:
                if not x["cold"]:
                    w[(x["stage"], x["memory_mb"])].append(1000 * x["handler_s"] / r["n_words"])
    rows = []
    for stg in STAGES:
        m = {mem: st.median(w[(stg, mem)]) for mem in (512, 1024, 2048)}
        rows.append([stg] + [x for mem in (512, 1024, 2048) for x in (len(w[(stg, mem)]), r3(m[mem]))]
                    + [round(m[512] / m[1024], 2), round(m[1024] / m[2048], 2)])
    write(out, "memory_scaling.csv", ["stage", "n_warm_512", "s_per_1000_words_512", "n_warm_1024",
                                      "s_per_1000_words_1024", "n_warm_2048", "s_per_1000_words_2048",
                                      "ratio_512_over_1024", "ratio_1024_over_2048"], rows)
    # ---------------------------------------------------------------- memory updates
    dec = jl(os.path.join(run, "adapter_schedule", "decisions.jsonl"))
    t0 = json.load(open(os.path.join(run, "adapter_schedule", "arm.json"), encoding="utf-8"))["t0_wall_ns"]
    last_submit = max(r["submit_wall_ns"] for r in recs["adapter_schedule"])
    last_done = max(r["done_wall_ns"] for r in recs["adapter_schedule"])
    seen = Counter((x["memory_mb"]) for r in recs["adapter_schedule"] for x in r["stages"])
    changes = []
    for d in dec:
        a_ = d["actuation"]
        if a_["memory_changed"]:
            start_ns = d["applied_wall_ns"] - int(a_["memory_update_s"] * 1e9)
            changes.append(dict(k=d["k"], frm=a_["memory_from"], to=d["memory"], upd=a_["memory_update_s"],
                                late=d["applied_late_s"], start_ns=start_ns, applied_ns=d["applied_wall_ns"],
                                running=d["records_running_at_decision"],
                                observed="no record ran after it" if d["applied_wall_ns"] > last_done else
                                ("yes" if seen[d["memory"]] else "no")))
    log.append(f"adapter decisions={len(dec)} memory changes={len(changes)}; pc_requested all zero="
               f"{all(not any(x['actuation']['pc_requested']) for x in dec)}; pc_applied all null="
               f"{all(x['actuation']['pc_applied'] is None for x in dec)}; last submit at "
               f"{(last_submit - t0) / 1e9:.1f} s, last completion at {(last_done - t0) / 1e9:.1f} s")
    # ---------------------------------------------------------------- overhead
    rows = []
    for a in ARMS:
        rs = recs[a]
        ov = [e2e_service(r) for r in rs]
        rows.append([a, "client overhead: end-to-end minus service span", "all records", len(ov), r3(q(ov, 50)),
                     r3(q(ov, 95)), r3(max(ov)), "client monotonic e2e minus Lambda host-clock span"])
        for i, name in enumerate(("ingest->transform", "transform->aggregate", "aggregate->load")):
            for cold in (False, True):
                g = [(r["stages"][i + 1]["start_wall_ns"] - r["stages"][i]["end_wall_ns"]) / 1e9 for r in rs
                     if bool(r["stages"][i + 1]["cold"]) == cold]
                if g:
                    rows.append([a, f"stage transition {name}", "cold next stage" if cold else "warm next stage",
                                 len(g), r3(q(g, 50)), r3(q(g, 95)) if len(g) > 1 else None, r3(max(g)),
                                 "Lambda host clocks of two environments"])
        mi = [x["module_init_s"] for r in rs for x in r["stages"] if x["cold"]]
        rows.append([a, "module initialisation (handler module only)", "cold stage rows", len(mi), r3(q(mi, 50)),
                     r3(q(mi, 95)), r3(max(mi)), "Lambda host clock; not Lambda Init Duration"])
        ld = [r["late_dispatch_s"] for r in rs]
        rows.append([a, "client dispatch lateness", "all records", len(ld), r3(q(ld, 50)), r3(q(ld, 95)), r3(max(ld)),
                     "client clock"])
        ds = [x["decision_s"] for x in jl(os.path.join(run, a, "decisions.jsonl"))]
        rows.append([a, "decision time (fixed schedule or OnDemand, not PRISM)", "decisions", len(ds), None, None,
                     max(ds), "client clock"])
    write(out, "overhead.csv", ["arm", "quantity", "subset", "n", "p50_s", "p95_s", "max_s", "clock_basis"], rows)
    # ---------------------------------------------------------------- integrity
    rows = []
    for a in ARMS:
        stg = [x for r in recs[a] for x in r["stages"]]
        rows.append([a, len(stg), sum(bool(x["aws_request_id"]) for x in stg), len({x["aws_request_id"] for x in stg}),
                     sum(x["cold"] for x in stg), len({x["env_id"] for x in stg}), 0, len(stg)])
    cw = os.path.join(run, "cloudwatch_reports.jsonl")
    n_cw = len(jl(cw)) if os.path.getsize(cw) else 0
    log.append(f"cloudwatch_reports.jsonl: {os.path.getsize(cw)} bytes, {n_cw} REPORT entries")
    write(out, "integrity.csv", ["arm", "stage_rows", "with_request_id", "distinct_request_ids", "cold_stage_rows",
                                 "distinct_environments", "report_lines_joined", "report_lines_missing"], rows)
    return changes, t0


def ct_load(ct, name):
    with open(os.path.join(ct, name), encoding="utf-8-sig") as f:
        return [json.loads(e["CloudTrailEvent"]) for e in json.load(f)]


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def hhmmss(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%H:%M:%S")


def caller(e):
    ua = (e.get("userAgent") or "").lower()
    if "boto3" in ua or "botocore" in ua:
        return "run client (boto3)"
    if "resource-explorer" in ua:
        return "AWS Resource Explorer (service)"
    if "awslambda-worker" in ua:
        return "Lambda service"
    return "other"


def resource(e):
    p = e.get("requestParameters") or {}
    x = p.get("functionName") or p.get("logGroupName") or p.get("name") or p.get("stateMachineArn") or \
        p.get("resourceArn") or p.get("resource") or p.get("resourceIdentifier") or ""
    m = re.search(r"(prism-pipe-[\w-]+)", str(x))
    return m.group(1) if m else ("(none)" if not x else "(other)")


def build_cloudtrail_tables(ct, run, out, changes, log):
    L, G, S = ct_load(ct, "lambda.json"), ct_load(ct, "logs.json"), ct_load(ct, "states.json")
    man = json.load(open(os.path.join(run, "manifest.json"), encoding="utf-8"))
    allev = [("lambda", e) for e in L] + [("logs", e) for e in G] + [("states", e) for e in S]
    log.append(f"CloudTrail events: lambda={len(L)} logs={len(G)} states={len(S)}; regions="
               f"{dict(Counter(e['awsRegion'] for _, e in allev))}; window {hhmmss(min(ts(e['eventTime']) for _, e in allev))}"
               f"-{hhmmss(max(ts(e['eventTime']) for _, e in allev))} UTC")
    # ---------------------------------------------------------------- aggregate counts
    agg = Counter()
    res_set = defaultdict(set)
    for src, e in allev:
        name = re.sub(r"20\d{6}(v\d)?$", "", e["eventName"])
        key = (src, name, caller(e), e.get("errorCode") or "")
        agg[key] += 1
        res_set[key].add(resource(e))
    rows = [[*k, n, ";".join(sorted(res_set[k]))] for k, n in sorted(agg.items())]
    write(out, "cloudtrail_events.csv", ["service", "event", "caller", "error_code", "events", "resources"], rows)
    # ---------------------------------------------------------------- lifecycle checks
    cr = [e for e in S if e["eventName"] == "CreateStateMachine"]
    de = [e for e in S if e["eventName"] == "DeleteStateMachine"]
    fn_ok = [e for e in L if e["eventName"].startswith("CreateFunction") and not e.get("errorCode")]
    fn_err = [e for e in L if e["eventName"].startswith("CreateFunction") and e.get("errorCode")]
    fdel = [e for e in L if e["eventName"].startswith("DeleteFunction")]
    lg_cr = [e for e in G if e["eventName"] == "CreateLogGroup"]
    lg_de = [e for e in G if e["eventName"] == "DeleteLogGroup"]
    upd = [e for e in L if e["eventName"].startswith("UpdateFunctionConfiguration")]
    mem_upd = [e for e in upd if (e.get("requestParameters") or {}).get("memorySize")]
    env_upd = [e for e in upd if not (e.get("requestParameters") or {}).get("memorySize")]
    pipe = set(man["functions"])
    checks = [
        ("Step Functions state machine created", f"{len(cr)} CreateStateMachine for {sorted({resource(e) for e in cr})}, "
         f"type {sorted({e['requestParameters'].get('type') for e in cr})}, logging "
         f"{sorted({e['requestParameters'].get('loggingConfiguration', {}).get('level') for e in cr})}, errors "
         f"{sum(bool(e.get('errorCode')) for e in cr)}", hhmmss(ts(cr[0]["eventTime"]))),
        ("Step Functions state machine deleted", f"{len(de)} DeleteStateMachine for {sorted({resource(e) for e in de})}, "
         f"errors {sum(bool(e.get('errorCode')) for e in de)}; deleted ARN equals created ARN and manifest: "
         f"{de[0]['requestParameters']['stateMachineArn'] == cr[0]['responseElements']['stateMachineArn'] == man['state_machine']}",
         hhmmss(ts(de[0]["eventTime"]))),
        ("Lambda functions created", f"{len(fn_ok)} successful CreateFunction for {sorted(resource(e) for e in fn_ok)}; "
         f"memory {sorted({e['requestParameters']['memorySize'] for e in fn_ok})} MB, runtime "
         f"{sorted({e['requestParameters']['runtime'] for e in fn_ok})}, tagged {all(e['requestParameters'].get('tags') for e in fn_ok)}, "
         f"publish {sorted({str(e['requestParameters'].get('publish')) for e in fn_ok})}; ARNs equal manifest: "
         f"{all(man['functions'][resource(e)]['arn'] == e['responseElements']['functionArn'] for e in fn_ok)}; "
         f"{len(fn_err)} earlier attempt failed ({sorted({e['errorCode'] for e in fn_err})}, role not yet assumable) and was retried",
         f"{hhmmss(min(ts(e['eventTime']) for e in fn_ok + fn_err))}-{hhmmss(max(ts(e['eventTime']) for e in fn_ok))}"),
        ("Lambda environment updates (calibrated K, forced-cold nonces)", f"{len(env_upd)} UpdateFunctionConfiguration "
         f"without a memory change, in {len({hhmmss(ts(e['eventTime']))[:5] for e in env_upd})} batches of 4, errors "
         f"{sum(bool(e.get('errorCode')) for e in env_upd)}",
         ", ".join(sorted({hhmmss(ts(e['eventTime'])) [:5] for e in env_upd}))),
        ("Lambda memory updates", f"{len(mem_upd)} UpdateFunctionConfiguration with MemorySize, "
         f"{sorted(Counter(e['requestParameters']['memorySize'] for e in mem_upd).items())} (MB, requests); response "
         f"memory equals request for all: {all(e['responseElements']['memorySize'] == e['requestParameters']['memorySize'] for e in mem_upd)}; "
         f"errors {sum(bool(e.get('errorCode')) for e in mem_upd)}",
         ", ".join(sorted({hhmmss(ts(e['eventTime'])) for e in mem_upd}))),
        ("Lambda functions deleted", f"{len(fdel)} DeleteFunction for {sorted(resource(e) for e in fdel)}, errors "
         f"{sum(bool(e.get('errorCode')) for e in fdel)}; all pipeline functions: {sorted(resource(e) for e in fdel) == sorted(pipe)}",
         f"{hhmmss(min(ts(e['eventTime']) for e in fdel))}-{hhmmss(max(ts(e['eventTime']) for e in fdel))}"),
        ("Log groups created", f"{len(lg_cr)} CreateLogGroup for {sorted(resource(e) for e in lg_cr)}, errors "
         f"{sum(bool(e.get('errorCode')) for e in lg_cr)}", f"{hhmmss(min(ts(e['eventTime']) for e in lg_cr))}-"
         f"{hhmmss(max(ts(e['eventTime']) for e in lg_cr))}"),
        ("Log groups deleted", f"{sum(not e.get('errorCode') for e in lg_de)} DeleteLogGroup succeeded for "
         f"{sorted(resource(e) for e in lg_de if not e.get('errorCode'))}; {sum(bool(e.get('errorCode')) for e in lg_de)} "
         f"repeat deletions returned {sorted({e['errorCode'] for e in lg_de if e.get('errorCode')})} (teardown's second pass)",
         f"{hhmmss(min(ts(e['eventTime']) for e in lg_de))}-{hhmmss(max(ts(e['eventTime']) for e in lg_de))}"),
        ("Provisioned concurrency, versions, aliases", f"{sum(any(k in e['eventName'] for k in ('Provisioned', 'PublishVersion', 'Alias')) for e in L)} events",
         ""),
    ]
    write(out, "cloudtrail_lifecycle.csv", ["check", "finding", "time_utc_22_nov"], checks)
    # ---------------------------------------------------------------- memory updates joined with CloudTrail
    rows = []
    for c in changes:
        s0 = c["start_ns"] / 1e9
        ev = [e for e in mem_upd if e["requestParameters"]["memorySize"] == c["to"] and abs(ts(e["eventTime"]) - s0) < 30]
        rows.append([c["k"], c["frm"], c["to"], round(c["upd"], 3), round(c["late"], 3), c["running"],
                     len(ev), len({resource(e) for e in ev}), sum(bool(e.get("errorCode")) for e in ev),
                     hhmmss(min(ts(e["eventTime"]) for e in ev)), round(min(ts(e["eventTime"]) for e in ev) - s0, 2),
                     c["observed"]])
    write(out, "memory_updates.csv", ["epoch", "from_mb", "to_mb", "update_duration_s", "in_effect_after_epoch_start_s",
                                      "records_running_at_decision", "cloudtrail_requests", "functions",
                                      "cloudtrail_errors", "cloudtrail_first_request_utc",
                                      "cloudtrail_first_minus_client_start_s", "seen_in_stage_records"], rows)
    # ---------------------------------------------------------------- log streams vs environments
    a0 = json.load(open(os.path.join(run, "baseline_ondemand", "arm.json"), encoding="utf-8"))["t0_wall_ns"] / 1e9
    a1 = json.load(open(os.path.join(run, "adapter_schedule", "arm.json"), encoding="utf-8"))["t0_wall_ns"] / 1e9
    lt = jl(os.path.join(run, "livetest.log"))
    e0 = [x["wall_ns"] for x in lt if x["msg"] == "arm baseline_ondemand done"][0] / 1e9
    e1 = [x["wall_ns"] for x in lt if x["msg"] == "arm adapter_schedule done"][0] / 1e9
    nonce = sorted({ts(e["eventTime"]) for e in env_upd})
    w0 = (min(t for t in nonce if t >= a0 - 60), e0 + 5)
    w1 = (min(t for t in nonce if t >= a1 - 60), e1 + 5)
    cls = [ts(e["eventTime"]) for e in G if e["eventName"] == "CreateLogStream"]
    envs = {a: len({x["env_id"] for r in records(run, a) for x in r["stages"]}) for a in ARMS}
    rows = [["baseline_ondemand", sum(w0[0] <= t < w0[1] for t in cls), envs["baseline_ondemand"]],
            ["adapter_schedule", sum(w1[0] <= t < w1[1] for t in cls), envs["adapter_schedule"]],
            ["before the arms (calibration and smoke)", sum(t < w0[0] for t in cls), None],
            ["total", len(cls), None]]
    write(out, "log_streams.csv", ["window", "cloudtrail_create_log_stream", "distinct_environments_in_records"], rows)


def hash_sources(run, ct, out, log):
    lines = []
    for base, label in ((run, os.path.basename(os.path.normpath(run))), (ct, os.path.basename(os.path.normpath(ct)))):
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                with open(p, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                lines.append(f"{h}  {label}/{os.path.relpath(p, base).replace(os.sep, '/')}")
    with open(os.path.join(out, "sources.sha256"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sorted(lines, key=lambda x: x.split("  ", 1)[1])) + "\n")
    log.append(f"hashed {len(lines)} private source files")


FORBIDDEN = [
    ("12-digit account ID", re.compile(r"(?<!\d)\d{12}(?!\d)")),
    ("ARN", re.compile(r"arn:aws", re.I)),
    ("access-key ID", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b")),
    ("IPv4 address", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")),
    ("UUID (request or event ID)", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("CloudTrail event field", re.compile(r"\"(?:eventID|requestID|userIdentity|sourceIPAddress|accessKeyId)\"", re.I)),
]


def scan(out, log):
    bad = []
    for root, _, files in os.walk(out):
        for fn in files:
            if fn.endswith((".pyc",)):
                continue
            p = os.path.join(root, fn)
            text = open(p, encoding="utf-8", errors="replace").read()
            for label, rx in FORBIDDEN:
                for m in rx.finditer(text):
                    if fn == "sources.sha256" and label == "12-digit account ID":
                        continue                                   # hex digests can contain 12-digit runs
                    if fn == "build_evidence.py" and label in ("ARN", "CloudTrail event field", "access-key ID"):
                        continue                                   # the patterns themselves
                    bad.append(f"{os.path.relpath(p, out)}: {label}")
    log.append("sanitization scan: " + ("clean" if not bad else f"FOUND {sorted(set(bad))}"))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cloudtrail", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    log = []
    changes, _ = build_run_tables(a.run, a.out, log)
    build_cloudtrail_tables(a.cloudtrail, a.run, a.out, changes, log)
    hash_sources(a.run, a.cloudtrail, a.out, log)
    ok = scan(a.out, log)
    with open(os.path.join(a.out, "build_output.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
