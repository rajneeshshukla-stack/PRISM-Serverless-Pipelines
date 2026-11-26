#!/usr/bin/env python3
"""R6.1 paired live replay (25 Nov 2026): run-sheet section 4 checks 1-5 and 7, from the raw run folder (kept private,
untracked). Writes aggregates only: no ARNs, account IDs, request IDs or execution IDs.
usage: python analyse_r61.py <run dir> <out json>
"""
import json
import math
import os
import sys
from collections import Counter

from scipy.stats import beta

RUN, OUT = sys.argv[1], sys.argv[2]
ARMS = ("baseline_ondemand", "adapter_prism")
DEADLINE = 14.5
PRED = {"independent_stages": 0.00216, "p2_shared_stage_rho_0.998": 0.03283}   # run sheet section 3a


def cp(k, n):
    """95% Clopper-Pearson interval."""
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else beta.ppf(0.025, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(0.975, k + 1, n - k)
    return [round(lo, 5), round(hi, 5)]


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


plan = jl(os.path.join(RUN, "records_plan.jsonl"))
key = lambda r: (r["record_id"], r["offset_s"], r["n_words"])  # noqa: E731
plan_keys = sorted(key(r) for r in plan)
L = json.load(open(os.path.join(RUN, "livetest.json"), encoding="utf-8"))
res = dict(run_folder=os.path.basename(os.path.normpath(RUN)),
           code=dict(git_head=L["code"]["git_head"][:7], uncommitted_paths=L["code"]["uncommitted_paths"]),
           spec={k: L["spec"][k] for k in ("mode", "pc_mode", "bin_s", "n_epochs", "thin", "prism_eps", "forecaster",
                                          "pc_cap", "trace_seed", "scenario", "week", "deadline_s", "cap", "alias",
                                          "seed")},
           calibration_k={s: v.get("k") if isinstance(v, dict) else v for s, v in (L.get("calibration") or {}).items()},
           smoke={k: L["smoke"][k] for k in ("n", "met", "missed", "failed", "shed_client_cap")},
           arms={})

for arm in ARMS:
    rows = jl(os.path.join(RUN, arm, "records.jsonl"))
    recs = [r for r in rows if r.get("type") == "record"]
    summ = next(r for r in rows if r.get("type") == "arm_summary")
    a = dict(input_coverage=dict(records=len(recs), planned=len(plan), identical_to_plan=sorted(map(key, recs)) == plan_keys),
             summary={k: summ[k] for k in ("n", "met", "missed", "failed", "shed_client_cap", "max_in_flight", "cap")},
             outcomes=dict(Counter(r["outcome"] for r in recs)))
    e2e = sorted(r["e2e_s"] for r in recs if r.get("e2e_s") is not None)
    q = lambda p: e2e[min(len(e2e) - 1, int(math.ceil(p * len(e2e))) - 1)]  # noqa: E731
    a["e2e_s"] = dict(p50=round(q(0.50), 3), p95=round(q(0.95), 3), p99=round(q(0.99), 3), max=round(e2e[-1], 3))
    # memory and cold-start composition
    full = [r for r in recs if r["status"] == "SUCCEEDED" and len(r.get("stages", [])) == 4]
    mem_sets = Counter(tuple(sorted({s["memory_mb"] for s in r["stages"]})) for r in full)
    a["memory_of_records"] = {"/".join(map(str, k)): v for k, v in mem_sets.items()}
    cold_n = Counter(sum(bool(s["cold"]) for s in r["stages"]) for r in full)
    a["cold_stages_per_record"] = dict(sorted(cold_n.items()))
    a["init_types"] = dict(Counter(s.get("init_type") for r in full for s in r["stages"] if s["cold"]))
    # check 7: fully warm 1024 MB records
    fw = [r for r in full if all((not s["cold"]) and s["memory_mb"] == 1024 for s in r["stages"])]
    excl = dict(shed_or_failed=len(recs) - len(full),
                at_least_one_cold_stage=sum(1 for r in full if any(s["cold"] for s in r["stages"])),
                other_memory_sizes=sum(1 for r in full if any(s["memory_mb"] != 1024 for s in r["stages"])
                                       and not any(s["cold"] for s in r["stages"])))
    m_e2e = sum(1 for r in fw if r["e2e_s"] > DEADLINE)
    bill = [r for r in fw if (r.get("billing") or {}).get("billedDurationInMilliseconds") is not None]
    m_bill = sum(1 for r in bill if r["billing"]["billedDurationInMilliseconds"] / 1000.0 > DEADLINE)
    span = lambda r: (max(s["end_wall_ns"] for s in r["stages"]) - min(s["start_wall_ns"] for s in r["stages"])) / 1e9  # noqa: E731
    m_span = sum(1 for r in fw if span(r) > DEADLINE)
    a["fully_warm_1024"] = dict(
        denominator=len(fw), excluded=excl,
        misses_e2e=m_e2e, rate_e2e=round(m_e2e / len(fw), 5) if fw else None, ci95_e2e=cp(m_e2e, len(fw)),
        misses_sfn_billed_duration=m_bill, denominator_billed=len(bill), ci95_sfn_billed=cp(m_bill, len(bill)),
        misses_stage_span=m_span, ci95_stage_span=cp(m_span, len(fw)),
        missed_words=sorted(r["n_words"] for r in fw if r["e2e_s"] > DEADLINE),
        words_quantiles=dict(median=sorted(r["n_words"] for r in fw)[len(fw) // 2], max=max(r["n_words"] for r in fw)))
    a["all_misses_fully_warm"] = sum(1 for r in recs if r["outcome"] == "missed") == m_e2e
    res["arms"][arm] = a

# check 2-3: decisions, actuation and readiness of the PRISM arm
dec = jl(os.path.join(RUN, "adapter_prism", "decisions.jsonl"))
res["prism_decisions"] = [dict(k=d["k"], observed_upto_bin=d.get("observed_upto_bin"),
                               decided_before_applied=d.get("decided_wall_ns", 0) <= d.get("applied_wall_ns", 0),
                               memory_requested=d["actuation"]["memory_requested"],
                               memory_applied=d["actuation"]["memory_applied"],
                               pc_requested=d["actuation"]["pc_requested"], pc_clipped_from=d["actuation"]["pc_clipped_from"],
                               pc_accepted=d["actuation"]["pc_accepted"], pc_refused=d["actuation"]["pc_refused"],
                               pc_status=d["actuation"]["pc_status"]) for d in dec]
rd = json.load(open(os.path.join(RUN, "adapter_prism", "pc_readiness.json"), encoding="utf-8"))
res["pc_readiness"] = [dict(k=x["k"], stage=x["stage"], requested=x["requested"], status=x["status"],
                            activation_lag_s=round(x["activation_lag_s"], 1) if x.get("activation_lag_s") else None)
                       for x in rd]
arm = json.load(open(os.path.join(RUN, "adapter_prism", "arm.json"), encoding="utf-8"))
res["pc_initial_wait"] = {k: v for k, v in (arm.get("pc_initial_wait") or {}).items() if "arn" not in k.lower()}
res["served_by_init_type"] = {a_: json.load(open(os.path.join(RUN, a_, "arm.json"), encoding="utf-8")).get("served_by_init_type")
                              for a_ in ARMS if os.path.exists(os.path.join(RUN, a_, "arm.json"))}
an = json.load(open(os.path.join(RUN, "analysis", "analysis.json"), encoding="utf-8"))
res["paired"] = an["paired"]
res["cost_usd_estimate_unverified_prices"] = an.get("cost_usd_arms_only")
cov = L["coverage"]
res["report_coverage"] = {k: cov.get(k) for k in ("expected_request_ids", "matched", "missing", "extra_reports",
                                                    "stage_rows_without_request_id", "collection_status", "complete")}
res["teardown_in_run"] = [l for l in L["teardown"] if l.startswith(("remaining", "NOT CLEAN", "CLEAN"))]
res["predictions_section_3a"] = PRED
json.dump(res, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
