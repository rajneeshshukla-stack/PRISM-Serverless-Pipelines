"""Join, missingness and the I / P / X / R decomposition per cell (docs/revision/init_vs_memory/MEASUREMENT_PLAN.md).

Per cell (group, variant, memory):
  I = median Lambda-reported Init Duration of observed-cold invocations (s)
  P = median cold end-to-end client time - median warm end-to-end client time (the full first-call penalty)
  X = median cold Duration - median warm Duration (first-invocation excess inside the handler)
  R = P - I - X (environment creation and anything else Lambda does not report)
  P_mean = mean cold - mean warm end-to-end (the model uses means: candidate for init_mean_measured)
Cold/warm is OBSERVED, not assumed: an invocation is cold if the handler reports first_call (a new environment),
cross-checked against the presence of Init Duration. Uncertainty: bootstrap over batches (cold and warm batches
resampled independently; I, X's cold part and P's cold part from the same resample). Trends: OLS slope of
log(quantity) on log(memory) where every replicate is positive; compared with Eq. (3)'s slope over the same sizes,
read from prism_repro.latency (not re-implemented). The decision rule is the plan's, applied to P.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
from prism_repro.config import PipelineConfig, Prices  # noqa: E402
from prism_repro.latency import init_factor  # noqa: E402  (Eq. (3) as implemented; read only)


# ------------------------------------------------------------------ loading and joining
def load_jsonl(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def join(records: List[dict], cloudwatch: Optional[Dict[str, dict]] = None) -> Tuple[List[dict], Dict]:
    """Keep invocations of completed visit attempts; attach the REPORT by request ID (tail first, CloudWatch
    fallback); flag every inconsistency. Returns (rows, issues)."""
    cloudwatch = cloudwatch or {}
    done = {(r["visit_id"], r["attempt"]) for r in records if r.get("type") == "visit_done"}
    inv = [r for r in records if r.get("type") == "invocation"]
    incomplete = sum((r["visit_id"], r["attempt"]) not in done for r in inv)
    inv = [r for r in inv if (r["visit_id"], r["attempt"]) in done]
    ids = Counter(r["request_id"] for r in inv if r.get("request_id"))
    seen_ids = set(ids)
    rows = []
    for r in inv:
        row = dict(r, flags=[])
        rid = r.get("request_id")
        if r.get("error"):
            row["flags"].append("throttled" if "Throttl" in r["error"] or "TooManyRequests" in r["error"]
                                or "Rate Exceeded" in r["error"] else "error")
        if r.get("function_error"):
            row["flags"].append("function_error")
        if not rid:
            row["flags"].append("no_request_id")
        elif ids[rid] > 1:
            row["flags"].append("duplicate_request_id")
        rep = r.get("report")
        if rep is None and rid in cloudwatch:
            rep, row["report_source"] = cloudwatch[rid], "cloudwatch"
        row["report"] = rep
        if rid and rep is None and not r.get("error"):
            row["flags"].append("no_report")
        if rep is not None:
            if rep.get("request_id") != rid:
                row["flags"].append("report_id_mismatch")
            if not rep.get("complete", False):
                row["flags"].append("report_incomplete")
        p = r.get("payload")
        if p is not None and p.get("aws_request_id") not in (None, rid):
            row["flags"].append("payload_id_mismatch")
        first = p.get("first_call") if p else None
        has_init = bool(rep and rep.get("init_duration_ms") is not None)
        row["observed"] = "cold" if first is True else "warm" if first is False else ("cold" if has_init else None)
        if row["observed"] == "cold" and rep is not None and not has_init:
            row["flags"].append("cold_without_init")
        if row["observed"] == "warm" and has_init:
            row["flags"].append("warm_with_init")
        if r.get("batch_kind") == "cold" and row["observed"] == "warm":
            row["flags"].append("unexpected_warm_in_cold_batch")
        if r.get("batch_kind") == "warm" and row["observed"] == "cold":
            row["flags"].append("unexpected_cold_in_warm_batch")
        rows.append(row)
    orphans = sorted(set(cloudwatch) - seen_ids)
    issues = {"incomplete_visit_invocations_dropped": incomplete, "orphan_cloudwatch_reports": len(orphans)}
    return rows, issues


MIN_BATCHES = 25             # MEASUREMENT_PLAN.md: at least 25 batches per stage and size
MIN_COLD_WITH_INIT = 200     # MEASUREMENT_PLAN.md: at least 200 cold invocations with a reported Init Duration

EXCLUDE = {"throttled", "error", "function_error", "no_request_id", "duplicate_request_id", "report_id_mismatch",
           "payload_id_mismatch"}


def usable(row: dict, kind: str) -> bool:
    """A clean invocation of the given observed kind (an unexpected warm in a cold batch counts as warm, but only
    warm batches supply the warm baseline, so the baseline is never built from post-cold reuse noise)."""
    if row.get("observed") != kind or EXCLUDE & set(row["flags"]):
        return False
    return row.get("batch_kind") == kind


# ------------------------------------------------------------------ statistics
def _ci(a) -> Tuple[float, float]:
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return (float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))) if len(a) else (math.nan, math.nan)


def _e2e(r):
    return r.get("e2e_s")


def _dur(r):
    rep = r.get("report")
    return rep["duration_ms"] / 1000 if rep and rep.get("duration_ms") is not None else None


def _init(r):
    rep = r.get("report")
    return rep["init_duration_ms"] / 1000 if rep and rep.get("init_duration_ms") is not None else None


def cell_stats(cold: List[dict], warm: List[dict], n_boot: int, rng) -> Dict:
    """Point values and bootstrap replicates of I, P, X, R, P_mean for one cell. Cold batches are resampled once per
    replicate and used for every cold median, so R = P - I - X is coherent within a replicate."""
    cb = sorted({r["batch_id"] for r in cold})
    wb = sorted({r["batch_id"] for r in warm})
    cg = {b: [r for r in cold if r["batch_id"] == b] for b in cb}
    wg = {b: [r for r in warm if r["batch_id"] == b] for b in wb}

    def stats(cold_rows, warm_rows):
        def med(rows, f, agg=np.median):
            v = [f(r) for r in rows if f(r) is not None]
            return float(agg(v)) if v else math.nan
        I = med(cold_rows, _init)
        P = med(cold_rows, _e2e) - med(warm_rows, _e2e)
        X = med(cold_rows, _dur) - med(warm_rows, _dur)
        Pm = med(cold_rows, _e2e, np.mean) - med(warm_rows, _e2e, np.mean)
        return {"I": I, "P": P, "X": X, "R": P - I - X, "P_mean": Pm}

    point = stats(cold, warm)
    reps = {k: np.full(n_boot, np.nan) for k in point}
    if cb and wb:
        for i in range(n_boot):
            cs = [r for k in rng.integers(0, len(cb), len(cb)) for r in cg[cb[k]]]
            ws = [r for k in rng.integers(0, len(wb), len(wb)) for r in wg[wb[k]]]
            s = stats(cs, ws)
            for k in point:
                reps[k][i] = s[k]
    return {"point": point, "reps": reps, "n_cold": len(cold), "n_warm": len(warm),
            "n_cold_with_init": sum(_init(r) is not None for r in cold), "cold_batches": len(cb),
            "warm_batches": len(wb)}


def eq3_slope(sizes: Iterable[int]) -> float:
    cfg = PipelineConfig()               # init_scaling="eq3" by default; nothing is modified
    x = np.log(np.asarray(list(sizes), float))
    y = np.log([init_factor(cfg, float(m)) for m in sizes])
    return float(np.polyfit(x, y, 1)[0])


def _slope(sizes, values) -> float:
    v = np.asarray(values, float)
    if len(sizes) < 3 or not np.all(np.isfinite(v)) or np.any(v <= 0):
        return math.nan
    return float(np.polyfit(np.log(np.asarray(sizes, float)), np.log(v), 1)[0])


def decision(lo: float, hi: float, s_eq: float, tol: float = 1e-9) -> str:
    """The plan's rule for P, stated before any data. `tol` only absorbs floating-point error at the interval ends
    (a zero-width interval at exactly Eq. (3)'s slope must count as containing it)."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "not estimable (non-positive or missing P in some size or replicate)"
    lo, hi = lo - tol, hi + tol
    if lo <= s_eq <= hi:
        tail = "; the interval also contains 0, so 'constant' is not excluded" if lo <= 0 <= hi else ""
        return "keep Eq. (3); refit init_mean_1024 and init_nonscaling" + tail
    if hi < 0:
        return "keep the direction; refit the non-scaling share (Eq. (3)'s shape changes)"
    if lo <= 0 <= hi:
        return "init_scaling = 'constant' (or 'measured')"
    return "init_scaling = 'inverted' or 'measured'; narrow the RQ4 memory claims"


# ------------------------------------------------------------------ main analysis
def analyse(records: List[dict], cloudwatch: Optional[Dict[str, dict]] = None, n_boot: int = 2000, seed: int = 1,
            prices: Optional[Prices] = None) -> Dict:
    rng = np.random.default_rng(seed)
    prices = prices or Prices()
    rows, issues = join(records, cloudwatch)
    cells = defaultdict(list)
    for r in rows:
        cells[(r["group"], r["variant"], r["memory_mb"])].append(r)
    out_cells, missing, billing, stats = [], [], [], {}
    for key in sorted(cells):
        rs = cells[key]
        fl = Counter(f for r in rs for f in r["flags"])
        missing.append({"group": key[0], "variant": key[1], "memory_mb": key[2], "invocations": len(rs),
                        "report_from_cloudwatch": sum(r.get("report_source") == "cloudwatch" for r in rs),
                        **{k: fl.get(k, 0) for k in ("throttled", "error", "function_error", "no_request_id",
                                                     "duplicate_request_id", "no_report", "report_incomplete",
                                                     "report_id_mismatch", "payload_id_mismatch",
                                                     "cold_without_init", "warm_with_init",
                                                     "unexpected_warm_in_cold_batch",
                                                     "unexpected_cold_in_warm_batch")}})
        cold = [r for r in rs if usable(r, "cold")]
        warm = [r for r in rs if usable(r, "warm")]
        s = cell_stats(cold, warm, n_boot, rng)
        stats[key] = s
        row = {"group": key[0], "variant": key[1], "memory_mb": key[2], "n_cold": s["n_cold"],
               "n_cold_with_init": s["n_cold_with_init"], "n_warm": s["n_warm"],
               "cold_batches": s["cold_batches"], "warm_batches": s["warm_batches"]}
        for q in ("I", "P", "X", "R", "P_mean"):
            lo, hi = _ci(s["reps"][q])
            row.update({f"{q}_s": round(s["point"][q], 6), f"{q}_lo": round(lo, 6), f"{q}_hi": round(hi, 6)})
        out_cells.append(row)
        billed = [r["report"] for r in rs if r.get("report") and r["report"].get("billed_duration_ms") is not None]
        gbs = sum(b["billed_duration_ms"] / 1000 * b["memory_size_mb"] / 1024 for b in billed)
        init_gbs = sum((b.get("init_duration_ms") or 0) / 1000 * b["memory_size_mb"] / 1024 for b in billed)
        billing.append({"group": key[0], "variant": key[1], "memory_mb": key[2], "requests": len(rs),
                        "reports_with_billing": len(billed), "billed_gb_s": round(gbs, 6),
                        "init_gb_s_if_billed": round(init_gbs, 6),
                        "cost_usd_at_model_prices": round(gbs * prices.od + len(rs) * prices.req, 6),
                        "cost_usd_if_init_billed": round((gbs + init_gbs) * prices.od + len(rs) * prices.req, 6)})
    # trends per variant, then pooled per group (mean over variants of the per-variant replicate)
    trends = []
    variants = sorted({(k[0], k[1]) for k in stats})
    for grp, var in variants + [(g, "POOLED") for g in sorted({k[0] for k in stats})]:
        if var == "POOLED":
            members = [v for g2, v in variants if g2 == grp]
            sizes = sorted({k[2] for k in stats if k[0] == grp
                            and all((grp, v, k[2]) in stats for v in members)})
        else:
            members = [var]
            sizes = sorted(k[2] for k in stats if k[:2] == (grp, var))
        if len(sizes) < 3:
            continue
        s_eq = eq3_slope(sizes)
        t = {"group": grp, "variant": var, "sizes": "/".join(map(str, sizes)), "eq3_slope": round(s_eq, 4)}
        p_lo = p_hi = math.nan
        for q in ("I", "P", "X", "R"):
            pt = [np.mean([stats[(grp, v, m)]["point"][q] for v in members]) for m in sizes]
            reps = np.array([[np.mean([stats[(grp, v, m)]["reps"][q][i] for v in members]) for m in sizes]
                             for i in range(n_boot)])
            sl = np.array([_slope(sizes, reps[i]) for i in range(n_boot)])
            lo, hi = _ci(sl) if np.all(np.isfinite(sl)) else (math.nan, math.nan)
            if q == "P":
                p_lo, p_hi = lo, hi          # the decision uses the unrounded bounds (rounding moved a boundary)
            t.update({f"{q}_slope": round(_slope(sizes, pt), 4) if math.isfinite(_slope(sizes, pt)) else math.nan,
                      f"{q}_slope_lo": round(lo, 4) if math.isfinite(lo) else math.nan,
                      f"{q}_slope_hi": round(hi, 4) if math.isfinite(hi) else math.nan})
        cells_in = [stats[(grp, v, m)] for v in members for m in sizes]
        t["min_cold_batches"] = min(c["cold_batches"] for c in cells_in)
        t["min_warm_batches"] = min(c["warm_batches"] for c in cells_in)
        t["min_cold_with_init"] = min(c["n_cold_with_init"] for c in cells_in)
        t["meets_init_sample_target"] = t["min_cold_with_init"] >= MIN_COLD_WITH_INIT
        if min(t["min_cold_batches"], t["min_warm_batches"]) < MIN_BATCHES:
            # the plan requires >= 25 batches per cell; with fewer, a batch bootstrap is overconfident (the timed
            # dry run, 3 cold batches per cell, produced a spurious 'inverted' call on a constant true penalty)
            t["decision_on_P"] = f"no decision: fewer than {MIN_BATCHES} cold or warm batches in some cell"
        else:
            t["decision_on_P"] = decision(p_lo, p_hi, s_eq)
        t["init_mean_measured_candidate"] = json.dumps(
            [[m, round(float(np.mean([stats[(grp, v, m)]["point"]["P_mean"] for v in members])), 4)] for m in sizes])
        trends.append(t)
    return {"cells": out_cells, "trends": trends, "missing": missing, "billing": billing, "issues": issues,
            "rows": rows}


def write_outputs(res: Dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name in ("cells", "trends", "missing", "billing"):
        rows = res[name]
        if not rows:
            continue
        with open(os.path.join(out_dir, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    with open(os.path.join(out_dir, "issues.json"), "w", encoding="utf-8") as f:
        json.dump(res["issues"], f, indent=1)
