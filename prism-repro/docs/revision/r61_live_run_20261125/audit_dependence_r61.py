#!/usr/bin/env python3
# COPY for the R6.1 live run (25 Nov 2026): arm "adapter_schedule" renamed to "adapter_prism"; otherwise identical to ../p2_dependence_20261124/audit_dependence.py.
"""P2 data audit and dependence estimate from the archived live integration run (24 Nov 2026). Read-only on the raw
archive; writes aggregates only (no request IDs, ARNs or account data).

Sources: <archive>/records_plan.jsonl, baseline_ondemand/records.jsonl, adapter_prism/records.jsonl
(AWS_livetest_20261121-203051; SHA-256 listed in docs/revision/aws_live_integration/sources.sha256).
The direct per-stage invocations of memcal-1 (one document, no cross-stage pairing) are kept out: they cannot identify
cross-stage dependence.

For warm stage executions at a single memory size:
  (1) handler time against document size: log(handler_s) = a_s + b_s log(n_words), per stage (b_s = 1 if proportional);
  (2) the share of each stage's log-time variance explained by document size (R^2);
  (3) residual dependence across stages within a record: correlation of the stage residuals from (1);
  (4) the implied correlation of log stage times across stages, total (size + residual), which is what the simulator's
      execution multipliers would need: the independent model assumes 0, the common-factor scenario assumes 1.
Uncertainty: bootstrap over records (documents), 2,000 resamples, so the shared documents and the four stages of a record
move together. Validation: the coefficients are fitted on the baseline arm (1024 MB) and checked on the 1024 MB records
of the schedule arm (other executions of the same documents), stated as such.
Independent check (optional third argument): the 22 Nov run (AWS_livetest_20261122-090236; other deployment, other day,
work units K within 2.5% of the 21 Nov run, 4 documents of 3,159-3,565 words per arm). Predictions use the 21 Nov fit
shifted by log(K_22/K_21) per stage, i.e. ASSUMING handler time proportional to K (the handler's design: work ~ K x length).
usage: python audit_dependence.py <archive dir> <out dir> [<22 Nov archive dir>]
"""
import json
import os
import sys
from collections import Counter

import numpy as np

A, OUT = sys.argv[1], sys.argv[2]
A2 = sys.argv[3] if len(sys.argv) > 3 else None
STAGES = ("ingest", "transform", "aggregate", "load")
rng = np.random.default_rng(20261124)


def records(arm, base=None):
    rs = [json.loads(l) for l in open(os.path.join(base or A, arm, "records.jsonl"))]
    return [r for r in rs if r.get("type") == "record"]


plan = [json.loads(l) for l in open(os.path.join(A, "records_plan.jsonl"))]
audit = dict(plan_records=len(plan), plan_distinct_n_words=len({p["n_words"] for p in plan}))
nw = np.array([p["n_words"] for p in plan], float)
audit["plan_n_words"] = dict(min=int(nw.min()), max=int(nw.max()), mean=float(nw.mean()), median=float(np.median(nw)),
                             sd_log=float(np.std(np.log(nw), ddof=1)))
arms = {}
for arm in ("baseline_ondemand", "adapter_prism"):
    rs = records(arm)
    complete = [r for r in rs if r.get("status") == "SUCCEEDED" and len(r.get("stages", [])) == 4
                and all(s.get("handler_s") is not None for s in r["stages"])]
    mem_sets = Counter(tuple(s["memory_mb"] for s in r["stages"]) for r in complete)
    cold = Counter(sum(bool(s["cold"]) for s in r["stages"]) for r in complete)
    arms[arm] = dict(records=len(rs), complete_4_stage=len(complete),
                     distinct_n_words=len({r["n_words"] for r in complete}),
                     records_all_stages_same_memory={str(k[0]): v for k, v in mem_sets.items() if len(set(k)) == 1},
                     records_mixed_memory=sum(v for k, v in mem_sets.items() if len(set(k)) > 1),
                     cold_stages_per_record=dict(sorted(cold.items())),
                     fields=sorted(complete[0]["stages"][0].keys()) if complete else [])
    arms[arm]["_rows"] = complete
audit["arms"] = {k: {kk: vv for kk, vv in v.items() if kk != "_rows"} for k, v in arms.items()}


def warm_matrix(rows, mem):
    """Records whose four stages all ran warm at memory `mem`: (log n_words, log handler_s per stage, record ids)."""
    sel = [r for r in rows if all((not s["cold"]) and s["memory_mb"] == mem for s in r["stages"])]
    x = np.log(np.array([r["n_words"] for r in sel], float))
    Y = np.log(np.array([[next(s for s in r["stages"] if s["stage"] == st)["handler_s"] for st in STAGES] for r in sel]))
    return x, Y, [r["record_id"] for r in sel]


def fit(x, Y):
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    R = Y - X @ coef
    r2 = 1 - R.var(0) / Y.var(0)
    corr_res = np.corrcoef(R.T)
    corr_tot = np.corrcoef(Y.T)
    off = lambda C: C[np.triu_indices(4, 1)]
    return dict(intercept=coef[0].tolist(), slope=coef[1].tolist(), r2_size=r2.tolist(),
                residual_sd_log=R.std(0, ddof=2).tolist(), total_sd_log=Y.std(0, ddof=1).tolist(),
                residual_corr_mean=float(off(corr_res).mean()), residual_corr_pairs=off(corr_res).tolist(),
                total_corr_mean=float(off(corr_tot).mean()), total_corr_pairs=off(corr_tot).tolist()), coef


def boot(x, Y, n=2000):
    out = dict(slope=[], residual_corr_mean=[], total_corr_mean=[], r2_size=[])
    for _ in range(n):
        i = rng.integers(0, len(x), len(x))
        f, _ = fit(x[i], Y[i])
        out["slope"].append(f["slope"]); out["residual_corr_mean"].append(f["residual_corr_mean"])
        out["total_corr_mean"].append(f["total_corr_mean"]); out["r2_size"].append(f["r2_size"])
    q = lambda a: np.percentile(np.asarray(a), [2.5, 97.5], axis=0).tolist()
    return {k: q(v) for k, v in out.items()}


res = dict(audit=audit)
x, Y, ids = warm_matrix(arms["baseline_ondemand"]["_rows"], 1024)
f, coef = fit(x, Y)
res["fit_baseline_1024"] = dict(n_records=len(x), distinct_n_words=len(set(np.round(np.exp(x)).astype(int))), **f,
                               bootstrap_95=boot(x, Y))
# check on the schedule arm's all-warm 1024 MB records (different executions; same documents)
xc, Yc, idc = warm_matrix(arms["adapter_prism"]["_rows"], 1024)
if len(xc) >= 3:
    pred = np.column_stack([np.ones_like(xc), xc]) @ coef
    res["check_schedule_1024"] = dict(n_records=len(xc), shared_documents_with_fit=len(set(idc) & set(ids)),
                                      mean_abs_log_error=float(np.abs(Yc - pred).mean()),
                                      per_stage_mean_log_error=(Yc - pred).mean(0).tolist())
for mem in (512, 2048):
    xm, Ym, _ = warm_matrix(arms["adapter_prism"]["_rows"], mem)
    if len(xm) >= 4:
        fm, _ = fit(xm, Ym)
        res[f"schedule_{mem}"] = dict(n_records=len(xm), slope=fm["slope"], r2_size=fm["r2_size"],
                                      residual_corr_mean=fm["residual_corr_mean"], total_corr_mean=fm["total_corr_mean"])
if A2:
    K21 = {s["stage"]: s["k"] for s in arms["baseline_ondemand"]["_rows"][0]["stages"]}
    rows2 = [r for arm in ("baseline_ondemand", "adapter_prism") for r in records(arm, A2)
             if r.get("status") == "SUCCEEDED" and len(r.get("stages", [])) == 4]
    K22 = {s["stage"]: s["k"] for s in rows2[0]["stages"]}
    x2, Y2, id2 = warm_matrix(rows2, 1024)
    shift = np.log(np.array([K22[st] / K21[st] for st in STAGES]))
    R2 = Y2 - (np.column_stack([np.ones_like(x2), x2]) @ coef + shift)
    res["check_22nov_1024"] = dict(n_records=len(x2), distinct_n_words=len(set(np.round(np.exp(x2)).astype(int))),
                                   n_words_range=[int(round(np.exp(x2.min()))), int(round(np.exp(x2.max())))],
                                   k_ratio=dict(zip(STAGES, np.exp(shift).round(4).tolist())),
                                   per_stage_mean_log_error=R2.mean(0).tolist(), per_stage_sd_log_error=R2.std(0, ddof=1).tolist(),
                                   mean_abs_log_error=float(np.abs(R2).mean()),
                                   residual_corr_mean=(float(np.corrcoef((R2 - R2.mean(0)).T)[np.triu_indices(4, 1)].mean())
                                                       if len(x2) >= 4 else None),
                                   note="all-warm 1024 MB records only; too few and too narrow in size to test the slope or the "
                                        "residual correlation, so this checks the level on another day and deployment only")
os.makedirs(OUT, exist_ok=True)
json.dump(res, open(os.path.join(OUT, "dependence_audit.json"), "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps(res, indent=1)[:6000])
