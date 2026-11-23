#!/usr/bin/env python3
"""memcal-1 multi-memory Lambda calibration, run AWS_memcal_20261122-110627 (us-east-2; docpipe-1 workload with K
frozen; 512/1024/2048/3008 MB; on demand; cap 8; laptop client; three blocks on one afternoon). Reads the ORIGINAL
files of the saved run folder only (never its cloudtrail/ sibling, never the derived block folders), makes no AWS
call, and writes SANITIZED aggregates: no request ID, account number, ARN or raw record.

usage (from the repository root; the run folder is private and stays outside Git):
  prism-repro/venv/Scripts/python prism-repro/docs/revision/aws_memcal_20261122/analyse_memcal_run.py \
      --run "AWS Live Implementation Log/AWS_memcal_20261122-110627/run" \
      --out prism-repro/docs/revision/aws_memcal_20261122

It needs numpy, and imports the repository's own analysis (prism_measure.analyse, prism_pipeline.memcal). The
prespecified analysis (MEMCAL_PLAN.md section 5) is memcal.analyse(run, tmp, n_boot=2000, seed=1); it is run on the
run folder read-only, into a temporary directory, and only its aggregate tables are copied. Exit status 1 if any
integrity check fails or the sanitization scan finds anything.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path[:0] = [os.path.join(REPRO, "aws_pipeline"), os.path.join(REPRO, "aws_measurement"), os.path.join(REPRO, "src")]
from prism_measure import analyse as A          # noqa: E402
from prism_pipeline import memcal as M          # noqa: E402
from prism_repro.config import PipelineConfig   # noqa: E402
from prism_repro.latency import init_factor     # noqa: E402

SOURCES = ("records.jsonl", "smoke/records.jsonl", "cloudwatch_reports.jsonl", "cloudwatch_coverage.json",
           "final_coverage.json", "cloudwatch_collect_state.json", "design.json", "workload_spec.json",
           "manifest.json", "estimate.json")
EXPECTED_BLOCKS = {0: 6968, 1: 7064, 2: 6960}
FIELDS = ("duration_ms", "billed_duration_ms", "memory_size_mb", "max_memory_used_mb", "init_duration_ms",
          "restore_duration_ms", "complete")
STAGES, SIZES = M.STAGES, M.SIZES


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def q(v, p):
    return round(float(np.quantile(v, p)), 3) if len(v) else ""


def med(v):
    return round(float(np.median(v)), 3) if len(v) else ""


def write(out, name, rows):
    with open(os.path.join(out, "tables", name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def billed_ok(c):
    x = round(c["duration_ms"] + (c["init_duration_ms"] or 0), 6)
    return "ceil" if c["billed_duration_ms"] == math.ceil(x) else \
        "ceil+1 at whole-ms sum" if x == int(x) and c["billed_duration_ms"] == x + 1 else "unexplained"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    run, out = a.run, a.out
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    log, checks = [], collections.OrderedDict()
    P = log.append

    # ------------------------------------------------------------ load the original files
    recs = jl(os.path.join(run, "records.jsonl"))
    smoke = jl(os.path.join(run, "smoke", "records.jsonl"))
    cw_rows = jl(os.path.join(run, "cloudwatch_reports.jsonl"))
    design, spec, man = (jload(os.path.join(run, f)) for f in ("design.json", "workload_spec.json", "manifest.json"))
    cov_saved, cov_final = (jload(os.path.join(run, f)) for f in ("cloudwatch_coverage.json", "final_coverage.json"))
    inv = [r for r in recs if r["type"] == "invocation"]
    sinv = [r for r in smoke if r["type"] == "invocation"]
    metas = [r for r in recs if r["type"] == "run_meta"]
    summs = [r for r in recs if r["type"] == "run_summary"]
    allinv = inv + sinv
    cw = {r["request_id"]: r for r in cw_rows}

    # ------------------------------------------------------------ identity and design
    full = M.build()
    split = M.split_of(full)
    exp_block = collections.Counter()
    for v in full.visits:
        exp_block[v.block] += v.cold + sum(v.warm_batches)
    checks["design hash = manifest = every run_meta"] = M._sha(design) == man["design_sha256"] and all(
        m["design_sha256"] == man["design_sha256"] for m in metas + [r for r in smoke if r["type"] == "run_meta"])
    checks["design and FIT/CHECK split = current code"] = design["design"] == json.loads(full.to_json()) and design["split"] == split
    checks["workload_spec hash = manifest = every run_meta"] = M._sha(spec) == man["workload_spec_sha256"] and all(
        m["workload_spec_sha256"] == man["workload_spec_sha256"] for m in metas)
    by_block = collections.defaultdict(list)
    for r in inv:
        by_block[r["block"]].append(r)
    checks["block invocations 6968/7064/6960 = design"] = {b: len(v) for b, v in by_block.items()} == EXPECTED_BLOCKS == dict(exp_block)
    checks["smoke invocations = 256"] = len(sinv) == 256
    checks["each run_meta covers one block, in order 0, 1, 2"] = [m["blocks"] for m in metas] == [[0], [1], [2]]
    done = {(v["visit_id"], v["attempt"]) for v in recs if v["type"] == "visit_done"}
    checks["every invocation in a completed visit, attempt 0"] = all((r["visit_id"], r["attempt"]) in done and r["attempt"] == 0 for r in inv)
    checks["max in flight <= cap 8 in every block"] = all(s["max_in_flight"] <= s["cap"] == M.CAP for s in summs)

    # ------------------------------------------------------------ coverage
    ids = collections.Counter(r.get("request_id") for r in allinv)
    checks["every invocation has a unique request ID"] = all(r.get("request_id") for r in allinv) and max(ids.values()) == 1
    checks["no duplicate REPORT request IDs"] = len(cw) == len(cw_rows)
    missing = [r for r in allinv if r["request_id"] not in cw]
    differ = [r for r in allinv if r.get("report") is None or any(r["report"].get(k) != cw[r["request_id"]].get(k) for k in FIELDS)]
    extras = sorted(set(cw) - set(ids))
    checks["21,248 REPORTs matched by request ID, 0 missing"] = len(allinv) == 21248 and not missing
    checks["log tail = CloudWatch on 7 fields for every invocation"] = not differ
    checks["REPORT log group = invoked function"] = all(cw[r["request_id"]]["log_group"] == "/aws/lambda/" + r["function"] for r in allinv)
    checks["saved coverage files agree and are complete"] = all(
        c["expected_request_ids"] == 21248 and c["matched"] == 21248 and c["missing"] == 0 and c["extra_reports"] == len(extras)
        and c["tail_and_cloudwatch_differ"] == 0 and c["complete"] is True for c in (cov_saved, cov_final))
    cov_rows = []
    for scope, rs in [(f"block {b}", by_block[b]) for b in sorted(by_block)] + [("smoke", sinv), ("total", allinv)]:
        cov_rows.append({"scope": scope, "invocations": len(rs),
                         "expected_from_design": exp_block[int(scope[-1])] if scope.startswith("block") else (256 if scope == "smoke" else 21248),
                         "unique_request_ids": len({r["request_id"] for r in rs}),
                         "reports_matched": sum(r["request_id"] in cw for r in rs),
                         "reports_missing": sum(r["request_id"] not in cw for r in rs),
                         "tail_vs_cloudwatch_differ": sum(r in differ for r in rs),
                         "log_group_mismatch": sum(cw[r["request_id"]]["log_group"] != "/aws/lambda/" + r["function"] for r in rs),
                         "billed_ceil_duration_plus_init": sum(billed_ok(cw[r["request_id"]]) == "ceil" for r in rs),
                         "billed_ceil_plus_1ms_at_whole_ms_sum": sum(billed_ok(cw[r["request_id"]]) == "ceil+1 at whole-ms sum" for r in rs),
                         "billed_unexplained": sum(billed_ok(cw[r["request_id"]]) == "unexplained" for r in rs)})
    cov_rows.append({"scope": "unmatched CloudWatch REPORTs (kept in archive, excluded)", "invocations": "",
                     "expected_from_design": "", "unique_request_ids": len(extras), "reports_matched": "",
                     "reports_missing": "", "tail_vs_cloudwatch_differ": "", "log_group_mismatch": "",
                     "billed_ceil_duration_plus_init": "", "billed_ceil_plus_1ms_at_whole_ms_sum": "", "billed_unexplained": ""})
    write(out, "coverage.csv", cov_rows)
    checks["no unexplained Billed Duration"] = cov_rows[4]["billed_unexplained"] == 0
    ex = collections.Counter((cw[x]["log_group"].rsplit("/", 1)[1], cw[x]["init_duration_ms"] is not None) for x in extras)
    write(out, "unmatched_reports.csv", [{"function": f, "with_init_duration": i, "reports": n} for (f, i), n in sorted(ex.items())])

    # ------------------------------------------------------------ payload / configuration
    bad = collections.Counter()
    for r in allinv:
        p = r.get("payload") or {}
        bad["payload request ID"] += p.get("aws_request_id") != r["request_id"]
        bad["payload memory"] += p.get("memory_mb") != r["memory_mb"] or cw[r["request_id"]]["memory_size_mb"] != r["memory_mb"]
        bad["stage/function"] += p.get("stage") != r["variant"] or r["function"] != f"prism-mcal-{r['variant']}-{r['memory_mb']}"
        bad["K not frozen"] += p.get("k") != M.FROZEN_K.get(p.get("stage"))
        bad["INIT_ROWS != 0"] += p.get("init_rows") != 0
        bad["REPORT incomplete"] += cw[r["request_id"]].get("complete") is not True
    checks["payload, memory, stage, frozen K, INIT_ROWS=0, REPORT complete"] = not any(bad.values())
    runtime_recorded = sum(1 for r in allinv if (r.get("tail_extra") or {}).get("runtime_version"))

    # ------------------------------------------------------------ join (repo logic), REPORT values from CloudWatch
    rows, issues = A.join(recs, {k: v for k, v in cw.items() if k not in {r["request_id"] for r in sinv}})
    for r in rows:
        r["report"] = cw[r["request_id"]]
    flags = collections.Counter(f for r in rows for f in r["flags"])
    checks["no error, throttle, function error or REPORT flag"] = not flags and all(r["status_code"] == 200 for r in rows)
    checks["cold batches all cold (with Init), warm batches all warm (no Init)"] = all(r["observed"] == r["batch_kind"] for r in rows)
    sm = M.smoke_check(os.path.join(run, "smoke", "records.jsonl"))
    checks["smoke check (repo) OK"] = sm["ok"]

    def pick(b, st, m):
        return [r for r in rows if (b == "all" or r["block"] == b) and r["variant"] == st and r["memory_mb"] == m]

    err_rows, tim_rows = [], []
    for b in (0, 1, 2, "all"):
        for st in STAGES:
            for m in SIZES:
                rs = pick(b, st, m)
                fl = collections.Counter(f for r in rs for f in r["flags"])
                err_rows.append({"block": b, "stage": st, "memory_mb": m, "invocations": len(rs),
                                 "status_not_200": sum(r["status_code"] != 200 for r in rs),
                                 "invocation_error": fl["error"], "throttled": fl["throttled"],
                                 "function_error": fl["function_error"], "no_report": fl["no_report"],
                                 "report_incomplete": fl["report_incomplete"], "cold_without_init": fl["cold_without_init"],
                                 "warm_with_init": fl["warm_with_init"],
                                 "unexpected_kind_in_batch": fl["unexpected_warm_in_cold_batch"] + fl["unexpected_cold_in_warm_batch"]})
                c = [r for r in rs if A.usable(r, "cold")]
                w = [r for r in rs if A.usable(r, "warm")]
                ci = np.array([r["report"]["init_duration_ms"] for r in c], float)
                cd = np.array([r["report"]["duration_ms"] for r in c], float)
                wd = np.array([r["report"]["duration_ms"] for r in w], float)
                ce = np.array([r["e2e_s"] * 1000 for r in c], float)
                we = np.array([r["e2e_s"] * 1000 for r in w], float)
                tim_rows.append({"block": b, "stage": st, "memory_mb": m, "n_cold": len(c), "n_warm": len(w),
                                 "cold_batches": len({r["batch_id"] for r in c}), "warm_batches": len({r["batch_id"] for r in w}),
                                 "init_median_ms": med(ci), "init_p05_ms": q(ci, .05), "init_p95_ms": q(ci, .95),
                                 "cold_duration_median_ms": med(cd), "warm_duration_median_ms": med(wd),
                                 "warm_duration_p05_ms": q(wd, .05), "warm_duration_p95_ms": q(wd, .95),
                                 "cold_billed_median_ms": med([r["report"]["billed_duration_ms"] for r in c]),
                                 "warm_billed_median_ms": med([r["report"]["billed_duration_ms"] for r in w]),
                                 "cold_e2e_median_ms": med(ce), "warm_e2e_median_ms": med(we),
                                 "P_median_ms": round(med(ce) - med(we), 3),
                                 "max_memory_used_mb": int(max(r["report"]["max_memory_used_mb"] for r in rs))})
    write(out, "errors_throttling.csv", err_rows)
    write(out, "timings.csv", tim_rows)

    # ------------------------------------------------------------ within-day repeatability (descriptive, post hoc)
    rep_rows = []
    T = {(t["block"], t["stage"], t["memory_mb"]): t for t in tim_rows}
    for st in STAGES:
        for m in SIZES:
            row = {"stage": st, "memory_mb": m}
            for key, name in (("warm_duration_median_ms", "warm_duration"), ("init_median_ms", "init"), ("P_median_ms", "P")):
                v = [T[(b, st, m)][key] for b in (0, 1, 2)]
                for b in (0, 1, 2):
                    row[f"{name}_b{b}_ms"] = v[b]
                row[f"{name}_range_ms"] = round(max(v) - min(v), 3)
                row[f"{name}_max_over_min"] = round(max(v) / min(v), 4)
            rep_rows.append(row)
    write(out, "repeatability.csv", rep_rows)

    # ------------------------------------------------------------ calibration / held-out split
    split_rows = []
    for b in (0, 1, 2):
        for name in ("fit", "check"):
            rs = [r for r in by_block[b] if split[r["visit_id"]] == name]
            per_cell = collections.Counter((r["variant"], r["memory_mb"]) for r in {r["visit_id"]: r for r in rs}.values())
            split_rows.append({"block": b, "split": name, "visits": len({r["visit_id"] for r in rs}),
                               "invocations": len(rs), "cold": sum(r["batch_kind"] == "cold" for r in rs),
                               "warm": sum(r["batch_kind"] == "warm" for r in rs),
                               "visits_per_cell_min": min(per_cell.values()), "visits_per_cell_max": max(per_cell.values())})
    write(out, "split.csv", split_rows)
    cell_split = collections.defaultdict(collections.Counter)
    for r in {r["visit_id"]: r for r in inv}.values():
        cell_split[(r["variant"], r["memory_mb"])][(split[r["visit_id"]], r["block"])] += 1
    checks["split: per cell 29 FIT + 10 CHECK visits, CHECK 4/3/3 over the blocks (block order random per cell)"] = (
        len(cell_split) == 16 and all(
            sum(c[("fit", b)] for b in (0, 1, 2)) == 29 and sorted(c[("check", b)] for b in (0, 1, 2)) == [3, 3, 4]
            for c in cell_split.values()))
    checks["no invocation used in both FIT and CHECK (split is by visit)"] = all(
        split[r["visit_id"]] in ("fit", "check") for r in inv)

    # ------------------------------------------------------------ configuration-update waits (one per visit)
    # update_wait_s: from the UpdateFunctionConfiguration call (environment variables only, to force cold starts;
    # memory is never changed) until GetFunctionConfiguration reports LastUpdateStatus Successful, polled every 1 s
    # from the client, so the resolution is about 1 s and the API round trips are included.
    vrows = [r for r in recs if r["type"] == "visit_done"]
    vcell = {r["visit_id"]: (r["block"], r["variant"], r["memory_mb"]) for r in inv}
    checks["one configuration update per visit, 624 with a wait time"] = (
        len(vrows) == 624 and all(isinstance(v.get("update_wait_s"), (int, float)) for v in vrows)
        and {v["visit_id"] for v in vrows} == set(vcell))
    cu_rows = []
    for b in (0, 1, 2, "all"):
        for m in SIZES + ("all",):
            w = np.array([v["update_wait_s"] for v in vrows if (b == "all" or vcell[v["visit_id"]][0] == b)
                          and (m == "all" or vcell[v["visit_id"]][2] == m)], float)
            cu_rows.append({"block": b, "memory_mb": m, "updates": len(w), "median_s": round(float(np.median(w)), 3),
                            "p95_s": round(float(np.quantile(w, .95)), 3), "min_s": round(float(w.min()), 3),
                            "max_s": round(float(w.max()), 3)})
    write(out, "config_updates.csv", cu_rows)

    # ------------------------------------------------------------ billing (list price, not the bill)
    bill_rows = []
    for scope, rs in [(f"block {b}", by_block[b]) for b in (0, 1, 2)] + [("campaign", inv), ("smoke", sinv)]:
        gbs = sum(cw[r["request_id"]]["billed_duration_ms"] / 1000 * r["memory_mb"] / 1024 for r in rs)
        bill_rows.append({"scope": scope, "requests": len(rs), "billed_gb_s": round(gbs, 2),
                          "usd_lambda_list_price": round(gbs * M.PRICES["lambda_gb_s_x86_tier1"] + len(rs) * M.PRICES["lambda_request"], 4)})
    write(out, "billing.csv", bill_rows)

    # ------------------------------------------------------------ client stalls
    st_rows = collections.OrderedDict()
    ov = []
    for r in rows:
        o = r["e2e_s"] - r["report"]["duration_ms"] / 1000 - (r["report"]["init_duration_ms"] or 0) / 1000
        ov.append(o)
        if o > 5:
            e = st_rows.setdefault(r["batch_id"], {"block": r["block"], "stage": r["variant"], "memory_mb": r["memory_mb"],
                                                   "batch_kind": r["batch_kind"], "split": split[r["visit_id"]],
                                                   "invocations_over_5s": 0, "max_e2e_s": 0.0, "max_lambda_duration_s": 0.0})
            e["invocations_over_5s"] += 1
            e["max_e2e_s"] = round(max(e["max_e2e_s"], r["e2e_s"]), 2)
            e["max_lambda_duration_s"] = round(max(e["max_lambda_duration_s"], r["report"]["duration_ms"] / 1000), 3)
    write(out, "client_stalls.csv", list(st_rows.values()))

    # ------------------------------------------------------------ prespecified analysis (repo), read-only on the run
    tmp = tempfile.mkdtemp(prefix="memcal_analyse_")
    try:
        res = M.analyse(run, tmp, n_boot=a.boot, seed=1)
        for src, dst in (("calibration_check.csv", "heldout_check.csv"), ("trend_compare.csv", "trend_compare.csv"),
                         ("calibration.json", "fits.json"), ("fit/cells.csv", "decomposition_fit.csv"),
                         ("check/cells.csv", "decomposition_check.csv")):
            shutil.copyfile(os.path.join(tmp, src), os.path.join(out, "tables", dst))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    summ = res["summary"]
    checks["prespecified analysis: FIT 15,592 / CHECK 5,400 invocations"] = summ["invocations"] == {"fit": 15592, "check": 5400}

    # ------------------------------------------------------------ Eq. (3) shape comparison (factor relative to 1024 MB)
    cells = {}
    with open(os.path.join(out, "tables", "decomposition_fit.csv"), encoding="utf-8") as f:
        for c in csv.DictReader(f):
            cells[(c["variant"], int(c["memory_mb"]))] = c
    cfg = PipelineConfig()
    eq_rows = []
    for st in STAGES + ("POOLED",):
        mem = STAGES if st == "POOLED" else (st,)
        for qn, label in (("I", "Lambda Init Duration (median)"), ("P", "client first-call penalty P (median)"),
                          ("P_mean", "client first-call penalty P_mean (mean)")):
            v = {m: float(np.mean([float(cells[(s, m)][f"{qn}_s"]) for s in mem])) for m in SIZES}
            for m in SIZES:
                ok = v[1024] > 0 and v[m] > 0
                eq_rows.append({"stage": st, "quantity": label, "memory_mb": m, "measured_s": round(v[m], 4),
                                "measured_factor_vs_1024": round(v[m] / v[1024], 4) if ok else "not estimable",
                                "eq3_factor_vs_1024": round(init_factor(cfg, m), 4),
                                "eq3_model_mean_s_submitted": round(cfg.init_mean_1024 * init_factor(cfg, m), 3)})
    write(out, "eq3_comparison.csv", eq_rows)

    # ------------------------------------------------------------ log
    P("memcal-1 MULTI-MEMORY CALIBRATION (run AWS_memcal_20261122-110627; us-east-2; docpipe-1, K frozen; 512/1024/2048/3008 MB;")
    P("on demand, cap 8, laptop client; three blocks on ONE afternoon). Rebuilt from the saved run folder; sanitized aggregates only.")
    P("")
    P("## Integrity checks")
    for k, v in checks.items():
        P(f"  {'PASS' if v else 'FAIL'}  {k}")
    P(f"  flagged (not a pass/fail check): runtime version recorded in {runtime_recorded} of {len(allinv)} invocations")
    P(f"  unmatched CloudWatch REPORTs kept and excluded: {len(extras)} ({dict((f, n) for (f, i), n in ex.items())}; all without Init: {not any(i for _, i in ex)})")
    P(f"  client overhead s: median {np.median(ov):.3f}, p99 {np.quantile(ov, .99):.3f}, max {max(ov):.1f}; "
      f"{sum(o > 5 for o in ov)} invocations over 5 s in {len(st_rows)} batches")
    ca = next(r for r in cu_rows if r["block"] == "all" and r["memory_mb"] == "all")
    P(f"  configuration updates (environment only, 1-s polling): {ca['updates']}; median {ca['median_s']} s, "
      f"p95 {ca['p95_s']} s, range {ca['min_s']}-{ca['max_s']} s")
    P("")
    P("## Blocks (CST, UTC-6)")
    import datetime as dt
    cst = dt.timezone(dt.timedelta(hours=-6))
    for b in (0, 1, 2):
        rs = by_block[b]
        t0 = min(r["wall_start_ns"] for r in rs)
        t1 = max(r["wall_start_ns"] + r["t1_ns"] - r["t0_ns"] for r in rs)
        f = lambda ns: dt.datetime.fromtimestamp(ns / 1e9, cst).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
        P(f"  block {b}: {f(t0)} to {f(t1)}, {len(rs)} invocations, 208 visits")
    P("")
    P("## Prespecified analysis summary")
    P(f"  FIT/CHECK invocations {summ['invocations']}; held-out predictions inside CHECK interval {summ['check_inside_interval']} of {summ['check_rows']}")
    P(f"  runtime versions by block {summ['runtime_versions_by_block']}")
    for t in summ["trend"]:
        P(f"  {t['stage']:9s} I slope {t['I_slope']} [{t['I_slope_lo']}, {t['I_slope_hi']}]; P slope {t['P_slope']} "
          f"[{t['P_slope_lo']}, {t['P_slope_hi']}]; P-I [{t['P_minus_I_slope_lo']}, {t['P_minus_I_slope_hi']}]; {t['decision_on_P']}")

    # ------------------------------------------------------------ source hashes (private files stay outside Git)
    base = os.path.basename(os.path.dirname(os.path.abspath(run)))
    with open(os.path.join(out, "sources.sha256"), "w", encoding="utf-8", newline="\n") as f:
        for s in SOURCES:
            f.write(f"{sha(os.path.join(run, s))}  {base}/run/{s}\n")
    P("")
    P(f"hashed {len(SOURCES)} private source files")
    ok_scan = scan(out, log)
    with open(os.path.join(out, "build_output.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))
    return 0 if all(checks.values()) and ok_scan else 1


FORBIDDEN = [
    ("12-digit account ID", re.compile(r"(?<!\d)\d{12}(?!\d)")),
    ("ARN", re.compile(r"arn:aws", re.I)),
    ("access-key ID", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b")),
    ("secret key field", re.compile(r"aws_secret_access_key|SecretAccessKey|aws_session_token", re.I)),
    ("IPv4 address", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")),
    ("UUID (request or event ID)", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("CloudTrail event field", re.compile(r"\"(?:eventID|eventName|requestID|userIdentity|sourceIPAddress|accessKeyId)\"", re.I)),
    ("raw record field", re.compile(r"\"(?:request_id|aws_request_id|nonce|env_id|wall_start_ns)\"\s*:")),
    ("private Windows path", re.compile(r"[A-Za-z]:\\\\?Users", re.I)),
]


def scan(out, log):
    bad = []
    for root, _, files in os.walk(out):
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(root, fn)
            if os.path.getsize(p) > 5_000_000:
                bad.append(f"{os.path.relpath(p, out)}: file over 5 MB")
            text = open(p, encoding="utf-8", errors="replace").read()
            for label, rx in FORBIDDEN:
                for m in rx.finditer(text):
                    if fn == "sources.sha256" and label == "12-digit account ID":
                        continue                       # hex digests can contain 12-digit runs
                    if fn == os.path.basename(__file__) and label in ("ARN", "access-key ID", "secret key field",
                                                                      "CloudTrail event field", "raw record field",
                                                                      "private Windows path"):
                        continue                       # the patterns themselves
                    bad.append(f"{os.path.relpath(p, out)}: {label}")
    log.append("sanitization scan: " + ("clean" if not bad else f"FOUND {sorted(set(bad))}"))
    return not bad


if __name__ == "__main__":
    raise SystemExit(main())
