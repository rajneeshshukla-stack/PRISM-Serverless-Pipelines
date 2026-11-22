"""Follow-up analysis of the saved live run livetest_20261121-203051 (R3.1, R2.8, R6.2, R2.14). Read only.

Uses only the private saved records (not in Git); writes sanitized aggregate tables to <out>/tables/ and the console
summary to <out>/build_output.txt. No account ID, ARN, request ID, environment ID or invocation record is written;
the last step scans the outputs for such patterns and exits non-zero if it finds one.

The run is a live FIXED-SCHEDULE integration test on the PROPOSED synthetic document-ingestion workload with no
start-up work in the handlers (aws_pipeline/SPEC.md decision P3, PRISM_INIT_ROWS = 0). PRISM's adaptive controller
was not evaluated live. CloudWatch REPORT collection saved zero entries, so nothing here is a Lambda Init Duration,
Billed Duration or bill: the cold-start figures are client-visible latencies measured on the Lambda hosts' clocks.

Usage (repository root, standard library only):
    python prism-repro/docs/revision/aws_live_followup/analyse_saved_run.py \
        --run "AWS Live Implementation Log/AWS_livetest_20261121-203051" \
        --out prism-repro/docs/revision/aws_live_followup
"""
import argparse
import csv
import json
import os
import re
import statistics as st
import sys
from collections import defaultdict

ARMS = ("baseline_ondemand", "adapter_schedule")
PRICE_GB_S_UNVERIFIED = 0.0000166667      # x86 Lambda list price used by aws_pipeline/prism_pipeline/estimate.py


def records(run, arm):
    with open(os.path.join(run, arm, "records.jsonl"), encoding="utf-8") as f:
        return [r for r in map(json.loads, f) if r["type"] == "record"]


def q(xs, p):
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    return st.quantiles(xs, n=100, method="inclusive")[p - 1]


def write(out, name, header, rows):
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    with open(os.path.join(out, "tables", name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    log = []
    R = {arm: records(a.run, arm) for arm in ARMS}

    # 1. cold-start latency by memory size: gap between the previous stage's end and this stage's start (both Lambda
    #    host clocks), for stages 2-4; cold stage versus warm stage at the same memory size
    gaps = defaultdict(list)
    for arm in ARMS:
        for r in R[arm]:
            s = r["stages"]
            for prev, cur in zip(s, s[1:]):
                g = (cur["start_wall_ns"] - prev["end_wall_ns"]) / 1e9
                gaps[(cur["memory_mb"], bool(cur["cold"]))].append(g)
    rows = []
    for mem in (512, 1024, 2048):
        c, w = gaps.get((mem, True), []), gaps.get((mem, False), [])
        if not c or not w:
            continue
        rows.append([mem, len(c), round(st.median(c), 4), round(min(c), 4), round(max(c), 4), len(w),
                     round(st.median(w), 4), round(st.median(c) - st.median(w), 4)])
        log.append(f"cold gap at {mem} MB: n={len(c)} median {st.median(c):.3f} s (range {min(c):.3f}-{max(c):.3f}); "
                   f"warm n={len(w)} median {st.median(w):.3f} s; added latency {st.median(c) - st.median(w):.3f} s")
    write(a.out, "cold_gap_by_memory.csv", ["memory_mb", "n_cold", "cold_gap_median_s", "cold_gap_min_s",
                                            "cold_gap_max_s", "n_warm", "warm_gap_median_s",
                                            "added_latency_median_s"], rows)

    # 2. warm execution-time variability per stage and size: coefficient of variation of handler time, and of handler
    #    time per 1,000 words (removes the document-size variation the workload draws on purpose)
    acc = defaultdict(list)
    for arm in ARMS:
        for r in R[arm]:
            for x in r["stages"]:
                if not x["cold"]:
                    acc[(x["stage"], x["memory_mb"])].append((x["handler_s"], 1000 * x["handler_s"] / r["n_words"]))
    cv = lambda v: st.pstdev(v) / st.mean(v)  # noqa: E731
    rows = []
    for stage in ("ingest", "transform", "aggregate", "load"):
        for mem in (512, 1024, 2048):
            v = acc.get((stage, mem), [])
            if len(v) < 5:
                continue
            rows.append([stage, mem, len(v), round(cv([h for h, _ in v]), 3), round(cv([p for _, p in v]), 3)])
    write(a.out, "warm_variability.csv", ["stage", "memory_mb", "n_warm", "cv_handler_s", "cv_handler_s_per_1000_words"],
          rows)
    per_word = [r[4] for r in rows]
    log.append(f"warm CV per 1,000 words: {min(per_word):.3f}-{max(per_word):.3f} over {len(rows)} stage-size cells; "
               f"CV of raw handler time {min(r[3] for r in rows):.3f}-{max(r[3] for r in rows):.3f}")

    # 3. concurrency: peak number of overlapping executions per function and in total (Lambda host clocks)
    rows = []
    for arm in ARMS:
        ev = defaultdict(list)
        for r in R[arm]:
            for x in r["stages"]:
                ev[x["stage"]] += [(x["start_wall_ns"], 1), (x["end_wall_ns"], -1)]
                ev["all"] += [(x["start_wall_ns"], 1), (x["end_wall_ns"], -1)]
        peaks = {}
        for k, e in ev.items():
            cur = mx = 0
            for _, d in sorted(e, key=lambda t: (t[0], t[1])):
                cur += d
                mx = max(mx, cur)
            peaks[k] = mx
        errors = sum(1 for r in R[arm] if r["status"] != "SUCCEEDED" or r["error"])
        rows.append([arm, peaks["ingest"], peaks["transform"], peaks["aggregate"], peaks["load"], peaks["all"], errors])
        log.append(f"{arm}: peak concurrent executions per function {[peaks[s] for s in ('ingest', 'transform', 'aggregate', 'load')]}, "
                   f"all functions {peaks['all']}; failed or errored records {errors}")
    write(a.out, "concurrency.csv", ["arm", "peak_ingest", "peak_transform", "peak_aggregate", "peak_load",
                                     "peak_all_functions", "failed_records"], rows)

    # 4. Lambda GB-s lower bound from in-function handler time (no init, no rounding, no billing record)
    rows = []
    for arm in ARMS:
        gbs = sum(x["handler_s"] * x["memory_mb"] / 1024 for r in R[arm] for x in r["stages"])
        sfn = sum(r["billing"]["billedDurationInMilliseconds"] / 1000 * r["billing"]["billedMemoryUsedInMB"] / 1024
                  for r in R[arm])
        rows.append([arm, round(gbs, 1), round(gbs * PRICE_GB_S_UNVERIFIED, 4), round(sfn, 2)])
        log.append(f"{arm}: Lambda GB-s lower bound {gbs:.1f} (about USD {gbs * PRICE_GB_S_UNVERIFIED:.4f} at the "
                   f"unverified list price); Step Functions billed GB-s from the execution responses {sfn:.2f}")
    write(a.out, "lambda_gbs_lower_bound.csv", ["arm", "lambda_gb_s_lower_bound", "usd_at_unverified_list_price",
                                                "sfn_billed_gb_s_reported"], rows)

    # sanitization scan of everything written
    bad = []
    pats = [re.compile(r"(?<!\d)\d{12}(?!\d)"), re.compile(r"arn:aws", re.I),
            re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
            re.compile(r"\b[0-9a-f]{32}\b"), re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")]
    for root, _, files in os.walk(os.path.join(a.out, "tables")):
        for fn in files:
            t = open(os.path.join(root, fn), encoding="utf-8").read() + "\n".join(log)
            bad += [f"{fn}: {p.pattern}" for p in pats if p.search(t)]
    log.append("sanitization scan: " + ("clean" if not bad else f"FOUND {sorted(set(bad))}"))
    with open(os.path.join(a.out, "build_output.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
