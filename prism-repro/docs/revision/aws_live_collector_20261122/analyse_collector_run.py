#!/usr/bin/env python3
"""Small live collector verification, run AWS_livetest_20261122-090236 (us-east-2, fixed 1024 MB, proposed synthetic
document-ingestion workload, fixed schedule; not PRISM's controller). Reads the saved run folder and its sibling
CloudTrail export only (no AWS call) and writes SANITIZED aggregates: no request ID, account number or ARN.

usage (from the repository root):
  python prism-repro/docs/revision/aws_live_collector_20261122/analyse_collector_run.py \
      --run "AWS Live Implementation Log/AWS_livetest_20261122-090236" \
      --cloudtrail "AWS Live Implementation Log/AWS_livetest_20261122-090236_cloudtrail" \
      --out prism-repro/docs/revision/aws_live_collector_20261122
"""
import argparse, collections, csv, hashlib, json, os, re, statistics

ARMS = ("smoke", "baseline_ondemand", "adapter_schedule")
STAGES = ("ingest", "transform", "aggregate", "load")
REQUIRED = ("duration_ms", "billed_duration_ms", "memory_size_mb", "max_memory_used_mb")


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def q(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return dict(n=0)
    return dict(n=len(xs), min=round(xs[0], 2), median=round(statistics.median(xs), 2), max=round(xs[-1], 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True); ap.add_argument("--cloudtrail", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "tables"), exist_ok=True)
    L = []; P = L.append

    # ---- expected request IDs, from the arms' stage rows
    exp = {}
    for arm in ARMS:
        for rec in jl(os.path.join(a.run, arm, "records.jsonl")):
            if rec.get("type") != "record":
                continue
            for st in rec.get("stages", []):
                if st.get("aws_request_id"):
                    exp[st["aws_request_id"]] = dict(arm=arm, stage=st.get("stage"), cold=st.get("cold"),
                                                     memory_mb=st.get("memory_mb"), handler_s=st.get("handler_s"))
    reps = jl(os.path.join(a.run, "cloudwatch_reports.jsonl"))
    ids = [r["request_id"] for r in reps]
    byid = {r["request_id"]: r for r in reps}
    matched = [rid for rid in exp if rid in byid]
    missing = [rid for rid in exp if rid not in byid]
    extra = [rid for rid in byid if rid not in exp]
    saved_cov = json.load(open(os.path.join(a.run, "cloudwatch_coverage.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(a.run, "cloudwatch_collect_state.json"), encoding="utf-8"))
    lt = json.load(open(os.path.join(a.run, "livetest.json"), encoding="utf-8"))
    P("SMALL LIVE COLLECTOR VERIFICATION (run AWS_livetest_20261122-090236; us-east-2; fixed 1024 MB; proposed synthetic")
    P("workload; fixed schedule, NOT PRISM's adaptive controller). Recomputed from the saved files; sanitized aggregates only.")
    P("")
    P("## Coverage (recomputed independently of cloudwatch_coverage.json)")
    P(f"  expected stage request IDs (smoke {sum(1 for v in exp.values() if v['arm']=='smoke')}, baseline "
      f"{sum(1 for v in exp.values() if v['arm']=='baseline_ondemand')}, adapter {sum(1 for v in exp.values() if v['arm']=='adapter_schedule')}): {len(exp)}")
    P(f"  REPORT records saved: {len(reps)}; unique request IDs: {len(set(ids))}; duplicates: {len(ids) - len(set(ids))}")
    P(f"  matched: {len(matched)}; missing: {len(missing)}; extra (not a recorded stage invocation): {len(extra)}")
    P(f"  saved coverage file agrees: {saved_cov['expected_request_ids'] == len(exp) and saved_cov['matched'] == len(matched) and saved_cov['missing'] == len(missing) and saved_cov['extra_reports'] == len(extra)}"
      f" (file: expected {saved_cov['expected_request_ids']}, matched {saved_cov['matched']}, missing {saved_cov['missing']}, extra {saved_cov['extra_reports']}, complete {saved_cov['complete']})")
    P(f"  collection state: {state.get('status')}, {state.get('calls')} call(s), pages per group "
      f"{[g['pages'] for g in state['groups'].values()]}, retries {sum(g['retries'] for g in state['groups'].values())}, "
      f"duplicates skipped {sum(g['skipped_duplicates'] for g in state['groups'].values())}; livetest.json verified: {lt.get('verified')}")
    ex_by_group = collections.Counter(byid[r]["log_group"].split("prism-pipe-")[-1] for r in extra)
    cal = lt.get("calibration") or {}
    P(f"  extras by stage log group: {dict(ex_by_group)}. They are not used in the analysis below. The run's calibration "
      f"step invokes each function directly before the arms (livetest.json 'calibration'; probes per stage are not "
      f"recorded as stage rows), which is the expected source; this is not verified per request ID.")
    P("")

    # ---- matched reports by stage
    rows = []
    P("## Matched REPORT records by stage (44; extras excluded)")
    hdr = ["stage", "n", "cold_n", "warm_n", "duration_ms_cold", "duration_ms_warm", "init_duration_n", "init_duration_ms",
           "billed_ms_cold", "billed_ms_warm", "memory_size_mb", "max_memory_used_mb", "missing_required_fields",
           "cold_without_init", "warm_with_init"]
    for s in STAGES:
        R = [(exp[rid], byid[rid]) for rid in matched if exp[rid]["stage"] == s]
        cold = [r for e, r in R if e["cold"]]; warm = [r for e, r in R if e["cold"] is False]
        miss = sum(1 for _, r in R for k in REQUIRED if r.get(k) is None)
        row = dict(stage=s, n=len(R), cold_n=len(cold), warm_n=len(warm),
                   duration_ms_cold=q([r["duration_ms"] for r in cold]), duration_ms_warm=q([r["duration_ms"] for r in warm]),
                   init_duration_n=sum(1 for _, r in R if r.get("init_duration_ms") is not None),
                   init_duration_ms=q([r.get("init_duration_ms") for _, r in R]),
                   billed_ms_cold=q([r["billed_duration_ms"] for r in cold]), billed_ms_warm=q([r["billed_duration_ms"] for r in warm]),
                   memory_size_mb=sorted({r["memory_size_mb"] for _, r in R}),
                   max_memory_used_mb=q([r["max_memory_used_mb"] for _, r in R]), missing_required_fields=miss,
                   cold_without_init=sum(1 for r in cold if r.get("init_duration_ms") is None),
                   warm_with_init=sum(1 for r in warm if r.get("init_duration_ms") is not None))
        rows.append(row)
        P(f"  {s:9s} n={row['n']:2d} (cold {row['cold_n']}, warm {row['warm_n']}); Duration ms cold {row['duration_ms_cold']}, "
          f"warm {row['duration_ms_warm']}; Init Duration present {row['init_duration_n']} {row['init_duration_ms']}; "
          f"Billed ms cold {row['billed_ms_cold']}, warm {row['billed_ms_warm']}; Memory Size {row['memory_size_mb']}; "
          f"Max Memory Used {row['max_memory_used_mb']}; missing required fields {miss}; cold without Init {row['cold_without_init']}; "
          f"warm with Init {row['warm_with_init']}")
    with open(os.path.join(a.out, "tables", "stage_reports.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(hdr)
        for r in rows:
            w.writerow([json.dumps(r[h]) if isinstance(r[h], (dict, list)) else r[h] for h in hdr])
    # billed against duration (+ init)
    M = [(exp[rid], byid[rid]) for rid in matched]
    import math
    warm_ok = sum(1 for e, r in M if e["cold"] is False and r["billed_duration_ms"] == math.ceil(r["duration_ms"]))
    cold_ok = sum(1 for e, r in M if e["cold"] and r.get("init_duration_ms") is not None
                  and r["billed_duration_ms"] == math.ceil(r["duration_ms"] + r["init_duration_ms"]))
    n_w = sum(1 for e, _ in M if e["cold"] is False); n_c = sum(1 for e, _ in M if e["cold"])
    P("")
    P(f"## Billed Duration against Duration (matched reports)")
    P(f"  warm: Billed = ceil(Duration) in {warm_ok} of {n_w}; cold: Billed = ceil(Duration + Init Duration) in {cold_ok} of {n_c}")
    hd = [(e["handler_s"] * 1000, r["duration_ms"]) for e, r in M if e.get("handler_s") is not None]
    P(f"  in-function handler time vs Lambda Duration: n={len(hd)}, median Duration - handler = "
      f"{round(statistics.median(d - h for h, d in hd), 2) if hd else 'n/a'} ms")
    P("")

    # ---- cleanup evidence
    td = lt.get("teardown") or []
    rem = next((x for x in td if x.startswith("remaining after teardown")), "")
    rem = re.sub(r"\b\d{12}\b", "<acct>", rem)
    P("## Cleanup evidence")
    P(f"  saved teardown result (livetest.json): {rem}; last line: {td[-1][:60] if td else 'none'}")
    ct = collections.Counter(); err = collections.Counter()
    for f in ("lambda.json", "logs.json", "states.json"):
        for e in json.load(open(os.path.join(a.cloudtrail, f), encoding="utf-8")):
            n = e["EventName"]
            if n.startswith(("Delete", "Create", "PutRetention")):
                ct[n] += 1
            ce = json.loads(e["CloudTrailEvent"]) if isinstance(e.get("CloudTrailEvent"), str) else {}
            if ce.get("errorCode") and n.startswith("Delete"):
                err[(n, ce["errorCode"])] += 1
    P(f"  CloudTrail export (lambda, logs, states; no IAM file): {dict(sorted(ct.items()))}")
    P(f"  errors on Delete calls: {dict(err) or 'none'} (the second DeleteLogGroup per group is the manifest pass after "
      f"the per-function pass already deleted it)")
    P("  A later CLEAN from `verify` is not in the saved files: if reported, it is terminal-reported. IAM role deletion "
      "is shown only by the saved teardown listing (roles: []), not by the CloudTrail export.")
    txt = "\n".join(L) + "\n"
    open(os.path.join(a.out, "summary.txt"), "w", encoding="utf-8", newline="\n").write(txt)
    print(txt)
    # hashes of the private source files (names and hashes only)
    with open(os.path.join(a.out, "sources.sha256"), "w", encoding="utf-8", newline="\n") as f:
        for base in (a.run, a.cloudtrail):
            top = os.path.basename(os.path.normpath(base))
            for d, _, fs in os.walk(base):
                for fn in sorted(fs):
                    p = os.path.join(d, fn)
                    rel = top + "/" + os.path.relpath(p, base).replace(os.sep, "/")
                    f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {rel}\n")


if __name__ == "__main__":
    main()
