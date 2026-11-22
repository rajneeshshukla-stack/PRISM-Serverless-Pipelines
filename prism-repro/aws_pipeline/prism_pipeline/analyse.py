"""Analysis of a live (or fake) pipeline run: request-ID join, deadline outcomes, per-stage and end-to-end timing,
cold starts, orchestration gaps, decisions, paired arm comparison and billing.

Definitions
  e2e_s           client-measured: submission of the execution to its response (what the requester waits); the
                  deadline (14.5 s) is applied to it. Shed and failed records are reported separately, never as met.
  service_s       first stage's handler start to last stage's handler end (AWS clocks): e2e without the client's
                  round trip and the cold start of the first stage.
  gap_s[s]        start of stage s+1 minus end of stage s (handler clocks): orchestration transition plus, when
                  stage s+1 is cold, its environment creation and INIT. gap_minus_init_s subtracts the reported Init
                  Duration (cold) so it estimates the transition overhead alone (the simulator's 0.1 s per stage).
  cold            the handler's own first-call flag (new environment); cross-checked with Init Duration presence.
Windows: `window_bins` consecutive bins (15 one-minute bins = the paper's 15-minute window) of record submissions;
a window violates if attainment < 1 - sla_eps (0.99). A short live test has few records per window, so its window
figures check the computation, not the SLO.
"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from typing import Dict, List, Optional

STAGES = ("ingest", "transform", "aggregate", "load")


def _q(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    i = (len(xs) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _med(xs):
    return _q(xs, 0.5)


def load_jsonl(path) -> List[dict]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def join_reports(records: List[dict], cloudwatch: List[dict]) -> Dict[str, int]:
    """Attach a REPORT to every stage row by Lambda request ID: the log tail (chain mode) first, CloudWatch
    otherwise. Returns integrity counts."""
    cw = {}
    dup_cw = 0
    for r in cloudwatch:
        if r["request_id"] in cw:
            dup_cw += 1
        cw[r["request_id"]] = r
    c = Counter()
    seen = Counter()
    for rec in records:
        for st in rec.get("stages", []):
            rid = st.get("aws_request_id")
            c["stage_rows"] += 1
            if not rid:
                c["missing_request_id"] += 1
                continue
            seen[rid] += 1
            if st.get("request_id_header") and st["request_id_header"] != rid:
                c["request_id_header_mismatch"] += 1
            if st.get("report"):
                if st["report"].get("request_id") != rid:
                    c["tail_report_id_mismatch"] += 1
                c["report_from_tail"] += 1
            elif rid in cw:
                st["report"], st["report_source"] = cw[rid], "cloudwatch"
                c["report_from_cloudwatch"] += 1
            else:
                c["report_missing"] += 1
            rep = st.get("report") or {}
            if st.get("cold") and rep and rep.get("init_duration_ms") is None:
                c["cold_without_init_duration"] += 1
            if (st.get("cold") is False) and rep.get("init_duration_ms") is not None:
                c["warm_with_init_duration"] += 1
    c["duplicate_request_ids"] = sum(1 for v in seen.values() if v > 1)
    c["duplicate_cloudwatch_reports"] = dup_cw
    return dict(c)


def _gb_s(rep):
    if not rep or rep.get("billed_duration_ms") is None:
        return None
    return rep["billed_duration_ms"] / 1000.0 * rep["memory_size_mb"] / 1024.0


def arm_summary(records: List[dict], decisions: List[dict], bin_s: float, window_bins: int = 15,
                sla_eps: float = 0.01) -> dict:
    recs = [r for r in records if r.get("type") == "record"]
    out = {"n": len(recs), "outcomes": dict(Counter(r["outcome"] for r in recs))}
    ran = [r for r in recs if r["outcome"] in ("met", "missed")]
    e2e = [r["e2e_s"] for r in ran]
    out["attainment_of_run"] = (sum(r["outcome"] == "met" for r in ran) / len(ran)) if ran else None
    out["attainment_of_all"] = (sum(r["outcome"] == "met" for r in recs) / len(recs)) if recs else None
    out["e2e_s"] = {"p50": _med(e2e), "p95": _q(e2e, 0.95), "p99": _q(e2e, 0.99), "max": max(e2e) if e2e else None}
    serv = []
    for r in ran:
        st = sorted(r["stages"], key=lambda s: STAGES.index(s["stage"]))
        if len(st) == 4 and all(s.get("start_wall_ns") for s in st):
            serv.append((st[-1]["end_wall_ns"] - st[0]["start_wall_ns"]) / 1e9)
    out["service_s"] = {"p50": _med(serv), "p95": _q(serv, 0.95)}
    out["client_overhead_s_p50"] = (_med(e2e) - _med(serv)) if e2e and serv else None
    # client vs AWS clock: ingest's handler start minus the client's submission is the request's transit (plus a
    # cold start) and cannot be negative unless the client clock runs ahead; telemetry binning mixes the two clocks
    lead = [(s["start_wall_ns"] - r["submit_wall_ns"]) / 1e9 for r in ran for s in r["stages"]
            if s.get("stage") == "ingest" and s.get("start_wall_ns") and r.get("submit_wall_ns")]
    out["clock_check"] = {"ingest_start_minus_submit_s_min": min(lead) if lead else None,
                          "client_clock_ahead": bool(lead and min(lead) < 0)}
    # windows over submission time
    w = defaultdict(lambda: [0, 0])
    for r in recs:
        b = int((r.get("submit_rel_s") or r.get("offset_s") or 0) // bin_s) // window_bins
        w[b][1] += 1
        w[b][0] += r["outcome"] == "met"
    out["windows"] = [{"window": b, "n": n, "met": m, "attainment": m / n, "violating": m / n < 1 - sla_eps}
                      for b, (m, n) in sorted(w.items())]
    # per stage
    per = {}
    for s in STAGES:
        rows = [st for r in recs for st in r.get("stages", []) if st.get("stage") == s]
        cold = [x for x in rows if x.get("cold")]
        warm = [x for x in rows if x.get("cold") is False]
        rep = [x.get("report") or {} for x in rows]
        per[s] = {"n": len(rows), "cold": len(cold), "warm": len(warm),
                  "handler_s_warm_p50": _med([x.get("handler_s") for x in warm]),
                  "handler_s_cold_p50": _med([x.get("handler_s") for x in cold]),
                  "duration_ms_warm_p50": _med([(x.get("report") or {}).get("duration_ms") for x in warm]),
                  "init_duration_ms_p50": _med([(x.get("report") or {}).get("init_duration_ms") for x in cold]),
                  "module_init_s_p50": _med([x.get("module_init_s") for x in cold]),
                  "memory_mb": dict(Counter(x.get("memory_mb") for x in rows)),
                  "max_memory_used_mb": max([r_.get("max_memory_used_mb") or 0 for r_ in rep], default=None),
                  "billed_gb_s": sum(g for g in (_gb_s(r_) for r_ in rep) if g is not None),
                  "reports": sum(1 for r_ in rep if r_)}
    gaps = defaultdict(list)
    gaps_ex = defaultdict(list)
    for r in ran:
        st = {x["stage"]: x for x in r["stages"]}
        for a, b in zip(STAGES, STAGES[1:]):
            if a in st and b in st and st[a].get("end_wall_ns") and st[b].get("start_wall_ns"):
                g = (st[b]["start_wall_ns"] - st[a]["end_wall_ns"]) / 1e9
                gaps[f"{a}->{b}"].append(g)
                init = ((st[b].get("report") or {}).get("init_duration_ms") or 0.0) / 1000.0 if st[b].get("cold") else 0.0
                if st[b].get("cold") is False:
                    gaps_ex[f"{a}->{b}"].append(g)
                elif st[b].get("report"):
                    gaps_ex[f"{a}->{b}"].append(g - init)
    out["stages"] = per
    out["gap_s_p50"] = {k: _med(v) for k, v in gaps.items()}
    out["gap_minus_init_s_p50"] = {k: _med(v) for k, v in gaps_ex.items()}
    out["cold_by_memory"] = dict(Counter(f"{x.get('stage')}@{x.get('memory_mb')}" for r in recs
                                         for x in r.get("stages", []) if x.get("cold")))
    out["outcome_by_memory"] = {}
    for r in ran:
        ms = {x.get("memory_mb") for x in r["stages"]}
        key = str(ms.pop()) if len(ms) == 1 else "mixed"
        d = out["outcome_by_memory"].setdefault(key, {"met": 0, "missed": 0})
        d[r["outcome"]] += 1
    ds = [d for d in decisions if d.get("type") == "decision"]
    ch = [d["actuation"] for d in ds if d.get("actuation", {}).get("memory_changed")]
    out["decisions"] = {"n": len(ds), "memory_changes": len(ch),
                        "memory_update_s": [c["memory_update_s"] for c in ch],
                        "decision_s_max": max([d["decision_s"] for d in ds], default=None),
                        "records_running_at_decision_max": max([d["records_running_at_decision"] for d in ds],
                                                               default=None),
                        "applied_late_s_max": max([d.get("applied_late_s", 0.0) for d in ds], default=None),
                        "pc_requested_total_max": max([sum(d["actuation"]["pc_requested"]) for d in ds], default=None),
                        "errors": [d for d in decisions if d.get("type") == "adapter_error"]}
    sfn_bill = [r.get("billing") for r in recs if r.get("billing")]
    out["sfn"] = {"executions": sum(1 for r in recs if r.get("execution_arn")),
                  "billed_gb_s": sum(b["billedDurationInMilliseconds"] / 1000.0 * b["billedMemoryUsedInMB"] / 1024.0
                                     for b in sfn_bill)}
    out["lambda_requests"] = sum(per[s]["n"] for s in STAGES)
    out["lambda_billed_gb_s"] = sum(per[s]["billed_gb_s"] for s in STAGES)
    return out


def paired(a: List[dict], b: List[dict]) -> dict:
    """Same record IDs in two arms: outcome cross-table and e2e differences (b - a)."""
    A = {r["record_id"]: r for r in a if r.get("type") == "record"}
    B = {r["record_id"]: r for r in b if r.get("type") == "record"}
    common = sorted(set(A) & set(B))
    tab = Counter((A[k]["outcome"], B[k]["outcome"]) for k in common)
    d = [B[k]["e2e_s"] - A[k]["e2e_s"] for k in common if A[k].get("e2e_s") is not None and B[k].get("e2e_s") is not None]
    return {"common_records": len(common), "only_a": len(set(A) - set(B)), "only_b": len(set(B) - set(A)),
            "outcomes_a_b": {f"{x}|{y}": n for (x, y), n in sorted(tab.items())},
            "e2e_diff_s": {"p50": _med(d), "p05": _q(d, 0.05), "p95": _q(d, 0.95)},
            "same_documents": all(A[k]["n_words"] == B[k]["n_words"] for k in common)}


def analyse(run_dir: str, arms: List[str], bin_s: float, cloudwatch_path: Optional[str] = None,
            prices: Optional[dict] = None, window_bins: int = 15) -> dict:
    cw = load_jsonl(cloudwatch_path)
    res = {"arms": {}, "integrity": {}}
    data = {}
    for arm in arms:
        recs = load_jsonl(os.path.join(run_dir, arm, "records.jsonl"))
        dec = load_jsonl(os.path.join(run_dir, arm, "decisions.jsonl"))
        res["integrity"][arm] = join_reports([r for r in recs if r.get("type") == "record"], cw)
        res["arms"][arm] = arm_summary(recs, dec, bin_s, window_bins)
        data[arm] = recs
    if len(arms) >= 2:
        res["paired"] = {f"{arms[0]}|{x}": paired(data[arms[0]], data[x]) for x in arms[1:]}
    if prices:
        lam_gbs = sum(a["lambda_billed_gb_s"] for a in res["arms"].values())
        req = sum(a["lambda_requests"] for a in res["arms"].values())
        sfn_n = sum(a["sfn"]["executions"] for a in res["arms"].values())
        sfn_gbs = sum(a["sfn"]["billed_gb_s"] for a in res["arms"].values())
        res["cost_usd_arms_only"] = {"lambda_duration": lam_gbs * prices["lambda_gb_s"],
                                     "lambda_requests": req * prices["lambda_request"],
                                     "sfn_requests": sfn_n * prices["sfn_request"],
                                     "sfn_duration": sfn_gbs * prices["sfn_gb_s"]}
    return res


def write_tables(res: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    with open(os.path.join(out_dir, "stages.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["n", "cold", "warm", "handler_s_warm_p50", "handler_s_cold_p50", "duration_ms_warm_p50",
                "init_duration_ms_p50", "module_init_s_p50", "billed_gb_s", "reports"]
        w.writerow(["arm", "stage"] + cols)
        for arm, a in res["arms"].items():
            for s in STAGES:
                w.writerow([arm, s] + [a["stages"][s].get(c) for c in cols])
    with open(os.path.join(out_dir, "arms.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arm", "n", "met", "missed", "failed", "shed", "attainment_of_run", "e2e_p50", "e2e_p95",
                    "e2e_max", "service_p50", "memory_changes", "lambda_gb_s"])
        for arm, a in res["arms"].items():
            o = a["outcomes"]
            w.writerow([arm, a["n"], o.get("met", 0), o.get("missed", 0), o.get("failed", 0),
                        o.get("shed_client_cap", 0), a["attainment_of_run"], a["e2e_s"]["p50"], a["e2e_s"]["p95"],
                        a["e2e_s"]["max"], a["service_s"]["p50"], a["decisions"]["memory_changes"],
                        round(a["lambda_billed_gb_s"], 3)])
