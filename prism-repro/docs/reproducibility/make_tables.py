"""Regenerate the revision summary tables from evidence committed in this repository (no simulation, no network).

Writes TR1-TR6, the graphical-abstract input table and the REGEN-WIN table map. Every value is asserted against the
value verified when the tables were first built (25 Nov 2026), so a changed source stops the script instead of
changing a number silently. The committed copies are in docs/reproducibility/tables/.

usage (from prism-repro/):  python docs/reproducibility/make_tables.py OUT_DIR
then compare:               diff -r docs/reproducibility/tables OUT_DIR      (Windows: fc /b, file by file)
"""
import csv
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PR = os.path.normpath(os.path.join(HERE, "..", ".."))          # prism-repro/
REV = os.path.join(PR, "docs", "revision")
REGEN = os.path.join(REV, "regeneration_20261122", "outputs", "tables")
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
INDEX = []


def lf_sha(p):
    """SHA-256 of a file's LF form, so a Windows checkout with core.autocrlf=true gives the same value."""
    return hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def write(name, md_lines, rows=None, header=None):
    open(os.path.join(OUT, name + ".md"), "w", encoding="utf-8", newline="\n").write("\n".join(md_lines) + "\n")
    if rows is not None:
        with open(os.path.join(OUT, name + ".csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    INDEX.append(name)


def close(a, b, tol=0.051):
    assert abs(float(a) - float(b)) <= tol, (a, b)


# ---------------------------------------------------------------- REGEN-WIN table map (which file backs which table)
# (submitted table, file under regeneration_20261122/outputs/tables/, content). Revised numbers are the planned
# renumbering of the revision; confirm them against the final manuscript.
MAP = [
    ("Table IV", "T4_forecast_coverage.md", "Forecast accuracy and coverage"),
    ("Table V", "T5_test_weeks.md", "Test weeks, validation-tuned (fast simulator)"),
    ("Table VI", "T6_paired_PRISM_vs_QuantProvq90.md", "Paired differences per trace"),
    ("Table VI", "T6_paired_PRISM_vs_PredHead.md", "Paired differences per trace"),
    ("Table VI", "T6_paired_PRISM_vs_PredHeadHyst.md", "Paired differences per trace"),
    ("Table VII", "revision/posthoc_matched_compliance.txt", "Interpolated cost at matched compliance (post hoc)"),
    ("Table VII", "revision/matched_compliance_pertrace.txt", "Interpolated cost at matched compliance (post hoc)"),
    ("Table VII", "revision/r76_matched_1pct.txt", "Interpolated cost at matched compliance (post hoc)"),
    ("Table VIII", "E3_ablation_conformal_oracle.md", "PRISM ablations"),
    ("Table VIII", "E3_quantile_vs_scenario_feasibility.md", "PRISM ablations"),
    ("Table IX", "T8_memory_regimes.md", "Memory regimes (two traces)"),
    ("Table X", "T10_fast_vs_event.md", "Fast vs event-level, frozen schedules (open loop)"),
    ("Table X", "T10b_prism_vs_predhead_fidelity.md", "Fast vs event-level, frozen schedules (open loop)"),
    ("Table XI", "revision/E12_event_level_retuning_analysis.txt", "Event-level retuning (post hoc, open-loop replay)"),
    ("Table XII", "R1_real_traces.md", "Huawei real-arrival replay (post hoc)"),
    ("Table S2", "E1_selected_parameters.md", "Selected parameter per trace"),
    ("Table S3", "T5_test_weeks.md", "Test weeks incl. secondary metrics"),
    ("Table S4", "E1_aggregate_all_test_weeks.md", "Aggregate over all 20 test weeks"),
    ("Table S5", "E6_caps.md", "Per-stage provisioning caps"),
    ("Table S6", "T7_frozen_vs_retuned.md", "Frozen vs test-retuned parameters"),
    ("Table S7", "T11_overflow_estimates.md", "Overflow-model accuracy"),
    ("Table S8", "T9_sensitivity.md", "Robustness to simulator assumptions"),
    ("Table S9", "T18_reference_forecasters.md", "Reference forecasters"),
    ("Table S9", "T19_reference_downstream.md", "Reference forecasters"),
    ("Table S9", "revision/E8_reference_forecasters_analysis.txt", "Reference forecasters"),
    ("Table S10", "T20_feature_ablation.md", "Feature-group ablations"),
    ("Table S11", "T13_infeasibility.md", "Epochs without a feasible level"),
    ("Table S12", "T14_hysteresis.md", "Scale-in smoothing"),
    ("Table S13", "revision/supplement_pertrace/pertrace_tables.md", "Per-trace results"),
    ("Table S14", "revision/E4b_fixed_memory_summary.json", "Fixed larger memory sizes (post hoc)"),
    ("Table S15", "revision/statistical_meaning/summary.md", "Protocol hypotheses and outcomes"),
]
RENUMBER = {"Table IV": "Table V", "Table V": "Table VI", "Table VI": "Table VIII", "Table VII": "Table IX", "Table VIII": "Table X",
            "Table IX": "Table XI", "Table X": "Table VII", "Table XI": "Table XII", "Table XII": "Table XIII"}
lf_list = os.path.join(REV, "regeneration_20261122", "SHA256SUMS.lf")
listed = {line.split(None, 1)[1].lstrip("*").replace("./", "", 1): line.split()[0]
          for line in open(lf_list, encoding="utf-8").read().splitlines() if line.strip()}
md = ["# REGEN-WIN: the regenerated file behind each results table", "",
      "**Set:** every stored table regenerated at commit fd8b01a on Windows 11 (Python 3.12.9, numpy 2.4.4, scipy 1.17.1,",
      "pandas 3.0.2, scikit-learn 1.8.0, matplotlib 3.10.8) with assumed platform constants (**PRE-CALIBRATION**); fast",
      "simulator unless stated; development traces 101-105 (the Huawei replay: traces 201-205). Files are under",
      "`prism-repro/docs/revision/regeneration_20261122/outputs/tables/`. **Revised numbers** are the planned renumbering",
      "of the revision; check them against the final manuscript. Supplementary table numbers are unchanged.", "",
      "| Submitted | Revised (planned) | Content | File | SHA-256 (LF form) |", "|---|---|---|---|---|"]
for paper, f, title in MAP:
    p = os.path.join(REGEN, *f.split("/"))
    h = lf_sha(p)
    assert listed.get(f"outputs/tables/{f}") == h, (f, "not as listed in regeneration_20261122/SHA256SUMS.lf")
    md.append(f"| {paper} | {RENUMBER.get(paper, paper)} | {title} | `{f}` | `{h}` |")
write("REGEN-WIN_table_map", md)

# ---------------------------------------------------------------- TR1 confirmatory C1-C3
cdir1 = os.path.join(REV, "confirmatory_20261122", "run", "tables")
paired = list(csv.DictReader(open(os.path.join(cdir1, "C1C2_paired.csv"), encoding="utf-8"))) + \
    list(csv.DictReader(open(os.path.join(cdir1, "C3_paired.csv"), encoding="utf-8")))
pt = list(csv.DictReader(open(os.path.join(cdir1, "C1C2_per_trace.csv"), encoding="utf-8"))) + \
    list(csv.DictReader(open(os.path.join(cdir1, "C3_per_trace.csv"), encoding="utf-8")))
expect = {("C1", "QuantProv_q90"): (0.297, -1.417, 2.011, -0.1057), ("C2", "Reactive"): (-26.49, -28.76, -24.23, 0.018),
          ("C3", "MemAdapt_q90"): (13.063, 8.496, 17.63, -0.6548)}
rows1 = []
for r in paired:
    key = (r["comparison"], r["comparator"])
    if key not in expect:
        continue
    e = expect[key]
    close(r["cost_pct_mean"], e[0], 0.01); close(r["cost_pct_lo"], e[1], 0.01); close(r["cost_pct_hi"], e[2], 0.01)
    close(r["violating_pts_mean"], e[3], 0.001)
    rows1.append([r["comparison"], "PRISM vs " + r["comparator"], r["n_traces"], f"{float(r['cost_pct_mean']):+.2f}",
                  f"[{float(r['cost_pct_lo']):+.2f}, {float(r['cost_pct_hi']):+.2f}]", r["cost_call"],
                  f"{float(r['violating_pts_mean']):+.3f}", f"[{float(r['violating_pts_lo']):+.3f}, {float(r['violating_pts_hi']):+.3f}]",
                  r["compliance_call"], f"{r['traces_prism_cheaper']} / {r['traces_prism_costlier']}"])
assert len(rows1) == 3, rows1
fam = {}
for r in pt:
    k = (r["set"], r["family"])
    f = fam.setdefault(k, dict(cost=[], viol=[], met=0, weeks=0, above=0))
    f["cost"].append(float(r["weekly_cost"])); f["viol"].append(float(r["violating_pct"]))
    f["met"] += int(r["weeks_meeting_2pct"]); f["weeks"] += int(r["test_weeks"]); f["above"] += float(r["violating_pct"]) > 2.0
exp_pool = {("C1C2", "PRISM"): (1456.5, 1.58, 81, 100, 5), ("C1C2", "QuantProv_q90"): (1454.6, 1.69, 72, 100, 7),
            ("C1C2", "Reactive"): (1982.9, 1.56, 75, 100, 5), ("C3", "PRISM"): (1672.8, 1.17, 24, 25, 1), ("C3", "MemAdapt_q90"): (1487.6, 1.83, 17, 25, 8)}
rows1b = []
for k, e in exp_pool.items():
    f = fam[k]
    mc, mv = sum(f["cost"]) / len(f["cost"]), sum(f["viol"]) / len(f["viol"])
    close(mc, e[0], 0.06); close(mv, e[1], 0.006); assert (f["met"], f["weeks"], f["above"]) == e[2:], (k, f["met"], f["weeks"], f["above"])
    rows1b.append([k[0], k[1], len(f["cost"]), f"{mc:,.1f}", f"{mv:.2f}", f"{f['met']} of {f['weeks']}", f"{f['above']} of {len(f['cost'])}"])
md = ["# TR1. Prespecified confirmatory comparisons C1-C3 (held-out traces 106-130)", "",
      "**Source:** `prism-repro/docs/revision/confirmatory_20261122/run/tables/` (C1C2_paired.csv, C3_paired.csv, *_per_trace.csv);",
      "analysis frozen in `prism-repro/docs/revision/PRESPECIFICATION.md` (d16fbea) before the first held-out week.",
      "**Configuration:** closed-loop event-level simulator, commit fd8b01a, `PipelineConfig()`/`PrismConfig()` defaults",
      "(assumed constants: Eq. (2) memory scaling, independent stage spread, Eq. (3) start-up 6 s, lag 2 min), Windows 11, the",
      "REGEN-WIN package set. **PRE-CALIBRATION.** C1/C2: 14.5 s, four scenarios (stationary, growth, bursty, new spike);",
      "C3: 12 s, stationary. **Metric:** PRISM minus comparator; cost in % of the comparator's weekly cost (mean over 25",
      "traces, 95% t interval, df 24); violating windows in percentage points (window = 15 min; violating when fewer than",
      "99% of its records meet the deadline). **Decision rules** (frozen): difference = interval excludes 0; tie = interval",
      "within +/-2%; similar compliance = violating-window interval within +/-0.5 points, otherwise the cost comparison is",
      "confounded.", "",
      "| Comparison | Pair | Traces | Cost diff (%) | 95% CI | Cost call | Violating windows diff (pts) | 95% CI | Compliance call | Traces PRISM cheaper / costlier |",
      "|---|---|---|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(map(str, r)) + " |" for r in rows1]
md += ["", "**Per family (test weeks; scenarios averaged per trace; then mean over traces):**", "",
       "| Set | Family | Traces | Mean weekly cost (USD) | Mean violating windows (%) | Weeks meeting 2% | Traces above 2% |", "|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(map(str, r)) + " |" for r in rows1b]
md += ["", "Reading: C1 is not distinguishable and not a tie (upper end +2.011% exceeds +2% by 0.011 points; platform-fragile).",
       "C2: PRISM cheaper at similar compliance. C3: PRISM costlier but violates fewer windows, outside the band, so the",
       "cost comparison is confounded and supports no cost ranking. These are frozen-configuration results with assumed",
       "constants; a calibrated held-out run is not part of this revision (TR2, readiness)."]
write("TR1_confirmatory_C1_C3", md, rows1, ["comparison", "pair", "traces", "cost_diff_pct", "cost_ci95", "cost_call", "viol_diff_pts", "viol_ci95", "compliance_call", "traces_cheaper_costlier"])

# ---------------------------------------------------------------- TR2 calibrated development (corrected start-up)
CAL = os.path.join(REV, "calibrated_build_20261125")
p3 = json.load(open(os.path.join(CAL, "p3_results.json")))
gA = json.load(open(os.path.join(CAL, "group_A_results.json")))
eqv = open(os.path.join(CAL, "equivalence_p3.txt"), encoding="utf-8").read()
assert "weeks compared 20: identical 20, different 0" in eqv
rows2 = []
for st, dl in (("CAL145C", "14.5"), ("CAL12C", "12")):
    for x in p3[st]["paired"]:
        p, m = x["prism"], x["memadapt"]
        sel = {r["family"]: r for r in p3[st]["rows"] if r["seed"] == x["seed"]}
        rows2.append([dl, x["seed"], sel["PRISM"]["selected"], sel["MemAdapt_q90"]["selected"] if not sel["MemAdapt_q90"]["unresolved_edge"] else f"{sel['MemAdapt_q90']['selected']} (edge)",
                      f"{p['cost']:,.1f}", f"{m['cost']:,.1f}", f"{x['premium_pct']:+.1f}", f"{p['viol']:.2f}", f"{m['viol']:.2f}",
                      f"{p['attain']:.2f}", f"{m['attain']:.2f}", "yes" if p["viol"] <= 2 else "no", "yes" if m["viol"] <= 2 else "no"])
prem145 = [float(r[6]) for r in rows2 if r[0] == "14.5"]; prem12 = [float(r[6]) for r in rows2 if r[0] == "12"]
assert (min(prem145), max(prem145)) == (18.6, 19.2) and (min(prem12), max(prem12)) == (10.7, 18.6), (prem145, prem12)
assert [r[11] for r in rows2 if r[0] == "12"].count("yes") == 4 and [r[12] for r in rows2 if r[0] == "12"].count("yes") == 2
assert all(r[11] == "yes" and r[12] == "yes" for r in rows2 if r[0] == "14.5")
fixed = []
for r in gA["rows"]:
    if r["family"] in ("QuantProv_q90", "Reactive"):
        t = r["test"]
        fixed.append([r["seed"], r["family"], r["selected"], "yes" if r["unresolved_edge"] else "no", "none" if not r["any_val_compliant"] else "some",
                      f"{t['cost']:,.1f}", f"{t['viol']:.2f}", f"{t['attain']:.2f}", f"{t['ge2048']:.1f}"])
assert len(fixed) == 10 and all(f[4] == "none" and f[6] == "100.00" and f[8] == "0.0" for f in fixed)
rd = p3["readiness"]
md = ["# TR2. Calibrated development evidence (corrected start-up), traces 101-105", "",
      "**CALIBRATED DEVELOPMENT EVIDENCE, not confirmatory; development traces 101-105 only; held-out seeds 106-130 untouched.**",
      "**Source:** `prism-repro/docs/revision/calibrated_build_20261125/p3_results.json` (PRISM, MemAdapt-q90) and",
      "`group_A_results.json` (fixed-1024 MB QuantProv-q90 and Reactive, reused after `equivalence_p3.txt`: 20 of 20 weeks",
      "bit-identical under both start-up forms). **Configuration:** event-level closed loop, Linux, isolated build 92e3e68 +",
      "`candidate_exec_p2.patch`; per-size execution factors (memcal-1 FIT), cross-stage dependence rho 0.998, start-up 6 s",
      "memory-independent (adopted P3, `init_scaling` constant) truncated at 10 s (mean 5.82 s at every size), lag 2 min;",
      "prespecified tuning with edge expansion; stationary test week. **Metric:** weekly cost (simulated USD); violating",
      "windows (% of 15-min windows; window violates below 99% record attainment); record attainment (% of records within",
      "the deadline); premium = PRISM / MemAdapt-q90 - 1. **Denominator:** one test week per trace and policy (672 windows).", "",
      "| Deadline (s) | Trace | PRISM eps | MemAdapt a | PRISM cost | MemAdapt cost | PRISM premium (%) | PRISM viol. (%) | MemAdapt viol. (%) | PRISM attain. (%) | MemAdapt attain. (%) | PRISM meets 2% | MemAdapt meets 2% |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(map(str, r)) + " |" for r in rows2]
md += ["", "Both policies use >= 2048 MB in 100% of epochs on every trace and deadline. At 12 s compliance differs (PRISM meets",
       "2% in 4 of 5 test weeks, MemAdapt-q90 in 2 of 5), so the 10.7-18.6% cost difference is not a matched-compliance premium.",
       "PRISM at eps 0.05-0.08 stays at 1024 MB at 14.5 s and violates 97-100% of windows (validation grid; `p3_results.txt`).", "",
       "**Fixed-1024 MB comparators at 14.5 s (Group A, reused):** every validation setting violated 100% of windows; the",
       "prespecified rule (least violating, ties to the cheaper) therefore selected the cheapest end of the wide grid.", "",
       "| Trace | Family | Selected | Unresolved edge | Compliant validation setting | Test cost | Viol. (%) | Attain. (%) | >= 2048 MB (% epochs) |",
       "|---|---|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(map(str, r)) + " |" for r in fixed]
md += ["", f"**Week counts:** 14.5 s {p3['CAL145C']['weeks']['week_files']} of {p3['CAL145C']['weeks']['planned_total']} planned; 12 s "
       f"{p3['CAL12C']['weeks']['week_files']} of {p3['CAL12C']['weeks']['planned_total']}; 0 failed, duplicate or orphaned; identical request streams.",
       f"**Readiness (run-plan rule 3):** C1-C2 NOT READY (QuantProv-q90 and Reactive at unresolved edges on 5 of 5 traces);",
       f"C3 edge condition met (MemAdapt-q90 at the edge on {len(p3['CAL12C']['edges']['MemAdapt_q90'])} of 5 traces); the combined calibrated",
       "held-out run is therefore not launched for this revision (rule 3 needs every condition)."]
assert rd["c1c2_ready"] is False and rd["c3_ready"] is True
write("TR2_calibrated_development", md, rows2, ["deadline_s", "trace", "prism_eps", "memadapt_a", "prism_cost", "memadapt_cost", "prism_premium_pct", "prism_viol_pct", "memadapt_viol_pct", "prism_attain_pct", "memadapt_attain_pct", "prism_meets_2pct", "memadapt_meets_2pct"])

# ---------------------------------------------------------------- TR3 R6.1 live replay
R = json.load(open(os.path.join(REV, "r61_live_run_20261125", "r61_results.json"), encoding="utf-8"))
A, B = R["arms"]["adapter_prism"], R["arms"]["baseline_ondemand"]
assert (A["summary"]["met"], B["summary"]["met"], A["summary"]["n"], B["summary"]["n"]) == (313, 314, 323, 323)
cov = R["report_coverage"]
assert (cov["expected_request_ids"], cov["matched"], cov["missing"]) == (2596, 2596, 0) and R["smoke"]["n"] == 3
lags = sorted({round(q["activation_lag_s"], 1) for q in R["pc_readiness"]})
assert lags == [20.1, 82.8], lags
fw = {k: v["fully_warm_1024"] for k, v in (("PRISM", A), ("OnDemand", B))}
assert (fw["PRISM"]["misses_e2e"], fw["PRISM"]["denominator"], fw["OnDemand"]["misses_e2e"], fw["OnDemand"]["denominator"]) == (9, 313, 8, 314)
po = R["paired"]["baseline_ondemand|adapter_prism"]["outcomes_a_b"]
est = R["cost_usd_estimate_unverified_prices"]
srv = R["served_by_init_type"]["adapter_prism"]
pc_share = {s: srv[f"{s}:provisioned-concurrency"] for s in ("ingest", "transform", "aggregate", "load")}
rows3 = [["Records per arm (identical inputs)", "323", "323", "records"],
         ["Met the 14.5 s per-record deadline", f"{A['summary']['met']} of 323", f"{B['summary']['met']} of 323", "records (end to end, client clock)"],
         ["Paired: met in both / missed only under PRISM / missed in both", f"{po['met|met']} / {po['met|missed']} / {po['missed|missed']}", "(same)", "records"],
         ["Fully warm 1024 MB records missing the deadline", f"{fw['PRISM']['misses_e2e']} of {fw['PRISM']['denominator']} ({100*fw['PRISM']['rate_e2e']:.2f}%, 95% CI {100*fw['PRISM']['ci95_e2e'][0]:.2f}-{100*fw['PRISM']['ci95_e2e'][1]:.2f})",
          f"{fw['OnDemand']['misses_e2e']} of {fw['OnDemand']['denominator']} ({100*fw['OnDemand']['rate_e2e']:.2f}%, 95% CI {100*fw['OnDemand']['ci95_e2e'][0]:.2f}-{100*fw['OnDemand']['ci95_e2e'][1]:.2f})",
          "records with 4 warm stages at 1024 MB (denominator)"],
         ["End-to-end p50 / p95 / p99 / max", "{p50} / {p95} / {p99} / {max}".format(**A["e2e_s"]), "{p50} / {p95} / {p99} / {max}".format(**B["e2e_s"]), "s"],
         ["Records with >= 1 cold stage", str(323 - A["cold_stages_per_record"]["0"]), str(323 - B["cold_stages_per_record"]["0"]), "records"],
         ["Stage executions served by provisioned concurrency (ingest/transform/aggregate/load)", " / ".join(str(pc_share[s]) for s in ("ingest", "transform", "aggregate", "load")), "0 (on demand)", "of 323 per stage"],
         ["Memory applied = requested", "1024 MB in 8 of 8 decisions", "1024 MB (fixed)", "decision epochs (5 min)"],
         ["Provisioned-concurrency READY first observed (polling every 10 s)", "82.8 s after the initial allocation (1/2/2/1 units); 20.1 s after a later change", "n/a", "two observations from one replay"],
         ["Lambda REPORT records matched to stage executions", f"{cov['matched']} of {cov['expected_request_ids']} (2,584 replay + 12 smoke), {cov['missing']} missing", "(shared)", "REPORT records"],
         ["Harness cost estimate (UNVERIFIED list prices; excludes provisioned concurrency)", f"USD {sum(est.values()):.3f} for both arms", "(shared)", "USD, not a bill"]]
md = ["# TR3. R6.1 paired live replay on AWS (25 Nov 2026, us-east-2): record-level outcomes and actuation", "",
      "**Source:** `prism-repro/docs/revision/r61_live_run_20261125/r61_results.json` (aggregates; raw run folder private, hashes in",
      "`raw_sources.sha256`); final cleanup `final_verify_CLEAN_20261125T050534Z.txt`. **Configuration:** PRISM's frozen",
      "controller (checkout 92e3e68, eps 0.02, gbm forecaster) against OnDemand, one thinned trace-week (trace 101, stationary,",
      "test week; 323 records per arm; 8 five-minute epochs); synthetic four-stage document pipeline on AWS Lambda and Step",
      "Functions Express. **Metric:** RECORD-LEVEL deadline outcomes at 14.5 s (not the simulator's window-level SLA: 2",
      "fifteen-minute windows per arm, too few to estimate it).", "",
      "| Quantity | PRISM arm | OnDemand arm | Unit / denominator |", "|---|---|---|---|"]
md += ["| " + " | ".join(r) + " |" for r in rows3]
md += ["", "Not measured: burst overflow, application start-up, memory sizes other than 1024 MB, the window-level SLA, actual",
       "charges (TR5). The fully warm miss rates contradict the frozen model's 0.22% prediction and fit the shared-stage model",
       "(about 3.3%); cross-stage dependence re-estimated on 314 new documents: total correlation 0.996 [0.995, 0.997]."]
write("TR3_r61_live_replay", md, rows3, ["quantity", "prism_arm", "ondemand_arm", "unit"])

# ---------------------------------------------------------------- TR4 AWS measurements (memcal-1, live integration)
tm = [r for r in csv.DictReader(open(os.path.join(REV, "aws_memcal_20261122", "tables", "timings.csv"), encoding="utf-8")) if r["block"] == "all"]
rows4 = []
for st in ("ingest", "transform", "aggregate", "load"):
    rr = {int(r["memory_mb"]): r for r in tm if r["stage"] == st}
    rows4.append([st] + [f"{float(rr[m]['warm_duration_median_ms']):,.1f}" for m in (512, 1024, 2048, 3008)] +
                 [f"{min(float(rr[m]['init_median_ms']) for m in rr):.1f}-{max(float(rr[m]['init_median_ms']) for m in rr):.1f}",
                  f"{min(float(rr[m]['P_median_ms']) for m in rr):.0f}-{max(float(rr[m]['P_median_ms']) for m in rr):.0f}"])
im = [float(r["init_median_ms"]) for r in tm]; ip05 = [float(r["init_p05_ms"]) for r in tm]; ip95 = [float(r["init_p95_ms"]) for r in tm]
assert (round(min(im), 1), round(max(im), 1), round(min(ip05), 1), round(max(ip95), 1)) == (113.7, 116.0, 94.7, 136.6)
arms = {r["arm"]: r for r in csv.DictReader(open(os.path.join(REV, "aws_live_integration", "tables", "arms.csv"), encoding="utf-8"))}
assert (arms["baseline_ondemand"]["met"], arms["adapter_schedule"]["met"], arms["baseline_ondemand"]["max_in_flight"], arms["adapter_schedule"]["max_in_flight"]) == ("39", "29", "5", "8")
ov = list(csv.DictReader(open(os.path.join(REV, "aws_live_integration", "tables", "overhead.csv"), encoding="utf-8")))
warm = [float(r["p50_s"]) * 1000 for r in ov if r["subset"] == "warm next stage"]; cold = [float(r["p50_s"]) * 1000 for r in ov if r["subset"] == "cold next stage"]
assert (round(min(warm)), round(max(warm))) == (23, 27), warm
mu = [float(r["update_duration_s"]) for r in csv.DictReader(open(os.path.join(REV, "aws_live_integration", "tables", "memory_updates.csv"), encoding="utf-8"))]
cu = list(csv.DictReader(open(os.path.join(REV, "aws_memcal_20261122", "tables", "config_updates.csv"), encoding="utf-8")))
md = ["# TR4. AWS Lambda measurements used in the replies (21-22 Nov 2026, us-east-2)", "",
      "**Sources:** memcal-1 `prism-repro/docs/revision/aws_memcal_20261122/` (RESULTS.md; tables/timings.csv, block = all) and the",
      "live integration run `prism-repro/docs/revision/aws_live_integration/` (tables/arms.csv, overhead.csv, memory_updates.csv).",
      "**Scope:** synthetic four-stage document pipeline; functions do no application start-up work; on demand; at most 8 in",
      "flight; laptop client; memcal-1 = 20,992 calibration invocations (1,312 per stage and size; 4,992 forced cold starts)",
      "plus a 256-invocation smoke run, three blocks on one afternoon (day-to-day variation not measured).", "",
      "**Warm Lambda Duration, median (ms), and cold-start quantities per stage:**", "",
      "| Stage | 512 MB | 1024 MB | 2048 MB | 3008 MB | Init Duration median, range over sizes (ms) | Client first-call penalty median, range (ms) |",
      "|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(r) + " |" for r in rows4]
md += ["", f"Init Duration 5th-95th percentiles across the 16 cells: {min(ip05):.1f}-{max(ip95):.1f} ms. The client penalty adds",
       "environment creation, the network and first-call execution to the platform's Init Duration.", "",
       "**Live integration run (21 Nov 2026; 40 records per arm; 14.5 s per-record deadline):**", "",
       "| Quantity | Value |", "|---|---|",
       f"| Records meeting 14.5 s: OnDemand at fixed 1024 MB / fixed memory schedule incl. 512 MB | {arms['baseline_ondemand']['met']} of 40 / {arms['adapter_schedule']['met']} of 40 |",
       f"| Peak pipelines in flight (client cap 8): OnDemand / schedule arm | {arms['baseline_ondemand']['max_in_flight']} / {arms['adapter_schedule']['max_in_flight']} |",
       f"| End-to-end p50 / p95, OnDemand arm (s) | {float(arms['baseline_ondemand']['e2e_p50_s']):.2f} / {float(arms['baseline_ondemand']['e2e_p95_s']):.2f} |",
       f"| Shared memory-size change across four functions (s), three changes | {min(mu):.2f}-{max(mu):.2f} |",
       f"| Stage transition, warm next stage, median (ms) | {min(warm):.0f}-{max(warm):.0f} |",
       f"| Stage transition, cold next stage, median (ms) | {min(cold):.0f}-{max(cold):.0f} |",
       f"| Configuration updates (memcal-1, environment variable only; 1 s polling) | {len(cu)} rows of block x memory summaries |"]
write("TR4_aws_measurements", md, rows4, ["stage", "warm_ms_512", "warm_ms_1024", "warm_ms_2048", "warm_ms_3008", "init_median_ms_range", "client_penalty_median_ms_range"])

# ---------------------------------------------------------------- TR5 billing categories (kept distinct)
rec = list(csv.DictReader(open(os.path.join(REV, "billing_reconciliation_20261124", "reconciliation.csv"), encoding="utf-8")))
rl = {r["line"]: r for r in rec}
x22 = dict(req=float(rl["export: us-east-2 Lambda, 22 Nov 2026 UTC"]["requests"]), gbs=float(rl["export: us-east-2 Lambda, 22 Nov 2026 UTC"]["gb_s"]))
sub = dict(req=float(rl["subtotal with REPORT records"]["requests"]), gbs=float(rl["subtotal with REPORT records"]["gb_s"]))
res_gbs = float(rl["residual after REPORT-attributed lines"]["gb_s"])
res412 = float(rl["residual after REPORT-attributed lines"]["requests"])
ids332 = float(rl["live test, 21 Nov 20:30 CST (02:30-02:55 UTC 22 Nov): stage invocations with saved request IDs"]["requests"])
res80 = float(rl["residual after also counting the 21 Nov live test's saved request IDs"]["requests"])
assert (x22["req"], round(x22["gbs"], 1), sub["req"], round(sub["gbs"], 1), res80, round(res_gbs, 1)) == (21784, 57005.6, 21372, 56167.1, 80, 838.4)
assert (res412, ids332) == (412, 332) and sub["req"] + ids332 + res80 == x22["req"]
mb = {r["scope"]: r for r in csv.DictReader(open(os.path.join(REV, "aws_memcal_20261122", "tables", "billing.csv"), encoding="utf-8"))}
cal_req = sum(int(mb[k]["requests"]) for k in ("block 0", "block 1", "block 2"))
cal_gbs = sum(float(mb[k]["billed_gb_s"]) for k in ("block 0", "block 1", "block 2"))
cal_usd = sum(float(mb[k]["usd_lambda_list_price"]) for k in ("block 0", "block 1", "block 2"))
assert cal_req == 20992 and abs(cal_gbs - 55234.5) < 0.05 and abs(cal_usd - 0.92) < 0.01, (cal_req, cal_gbs, cal_usd)
# The 25 Nov 2026 row: the export itself is PRIVATE (Cost Explorer; it carries account data). Its aggregates and the
# replay's REPORT populations are published as a sanitized summary (28 Nov 2026), with the export's SHA-256 in
# sources.sha256 there; this row is read from that summary. (Until 28 Nov the row was fixed text, and it compared the
# export with the 2,596 matched REPORT records instead of all 2,652 saved ones; corrected here.)
S25 = os.path.join(REV, "r61_live_run_20261125", "sanitized_summaries_20261128")
SM = json.load(open(os.path.join(S25, "summary.json"), encoding="utf-8"))
reg = SM["billing_export"]["regional_us_east_2_lambda"]
req25 = reg["USE2-Request"]["quantity"]
od25 = reg["USE2-Lambda-GB-Second"]["quantity"]
pc25 = reg["USE2-Lambda-Provisioned-GB-Second"]["quantity"]
lam_use = SM["billing_export"]["account_wide_lambda_by_record_type_usd"]["Usage"]
lam_cred = SM["billing_export"]["account_wide_lambda_by_record_type_usd"]["Credit"]
assert SM["billing_export"]["estimated"] is True and SM["billing_export"]["period_utc"] == {"Start": "2026-11-25", "End": "2026-11-26"}
assert (req25, round(od25, 3), round(pc25, 3), round(lam_use, 6), round(lam_cred, 6)) == (2568, 3255.356, 2219.792, 0.021581, -0.021581)
assert all(v["unblended_cost_usd"] == 0 for v in reg.values()) and SM["billing_export"]["provisioned_concurrency_capacity_line"] is False
pops = SM["report_populations"]
n_arms, g_arms = pops["replay arms (PRISM + OnDemand): stage executions"]["report_records"], pops["replay arms (PRISM + OnDemand): stage executions"]["billed_gb_s"]
n_match = pops["matched REPORT records (replay arms + smoke)"]["report_records"]
n_probe = pops["calibration-probe REPORTs (unmatched extras)"]["report_records"]
n_all = pops["all saved REPORT records of the replay"]["report_records"]
assert (n_arms, n_match, n_probe, n_all) == (2584, 2596, 56, 2652) and n_match + n_probe == n_all
assert (n_match, n_probe) == (cov["matched"], cov["extra_reports"])
# the harness estimate is arm-only: its request and duration costs give back 2,584 requests and 5,560.3 GB-s
assert round(est["lambda_requests"] / (0.20 / 1e6)) == n_arms and abs(g_arms * 0.0000166667 - est["lambda_duration"]) < 1e-9
assert round(g_arms, 1) == 5560.3 and round(est["sfn_requests"] / 1e-6) == 646
md = ["# TR5. Cost evidence, by kind (kept distinct; no figure here is a final replay-attributable charge)", "",
      "| Kind | Scope | Requests | GB-s | Amount | Status | Source |", "|---|---|---|---|---|---|---|",
      f"| Usage-based estimate at public list price | memcal-1 calibration blocks (22 Nov 2026 UTC), Lambda duration + requests, free tier not assumed | {cal_req:,} | {cal_gbs:,.1f} | USD {cal_usd:.2f} | estimate from REPORT records, not a bill | `aws_memcal_20261122/tables/billing.csv` |",
      f"| Harness estimate at UNVERIFIED list prices | R6.1 replay, both arms: Lambda (all duration at the on-demand rate) + {round(est['sfn_requests'] / 1e-6)} Step Functions executions; excludes provisioned-concurrency capacity | {n_arms:,} | {g_arms:,.1f} | USD {sum(est.values()):.2f} | estimate, not a bill | `r61_live_run_20261125/r61_results.json`; counts in `r61_live_run_20261125/sanitized_summaries_20261128/report_populations_20261125.csv` |",
      f"| AWS estimated billing export (Cost Explorer) | us-east-2, 22 Nov 2026 UTC, full day, all resources | {x22['req']:,.0f} | {x22['gbs']:,.1f} | USD 0 (no reason stated) | ESTIMATED, provisional; of {x22['req']:,.0f} requests, {sub['req']:,.0f} ({sub['gbs']:,.1f} GB-s) matched to saved REPORT records, {ids332:,.0f} to saved request IDs only (21 Nov live test), {res80:,.0f} unattributed; the other {res_gbs:,.1f} GB-s belong to these {res412:,.0f} requests | `billing_reconciliation_20261124/reconciliation.csv` |",
      f"| AWS estimated billing export (Cost Explorer) | us-east-2, 25 Nov 2026 UTC (R6.1 replay day), full day, all resources | {req25:,.0f} | {od25:,.1f} on demand + {pc25:,.1f} on provisioned environments | USD 0 by usage type; account-wide Lambda usage USD {lam_use:.4f} offset by an equal credit | ESTIMATED, provisional; no separate provisioned-concurrency capacity line; {req25:,.0f} requests against the replay's {n_all:,} saved REPORT records ({n_match:,} stage executions + {n_probe} calibration probes): {n_all - req25:,.0f} fewer, NOT RECONCILED | `r61_live_run_20261125/sanitized_summaries_20261128/billing_export_20261125.csv` (sanitized summary; the export is private, its SHA-256 in `r61_live_run_20261125/sanitized_summaries_20261128/sources.sha256`) |",
      "| Final charges attributable to the runs | memcal-1 and the R6.1 replay | - | - | open | requires the final bill / Cost and Usage Report | pending |"]
write("TR5_cost_evidence_by_kind", md, None, None)

# ---------------------------------------------------------------- TR6 platform sensitivity (stored v1 / REGEN-WIN / REGEN-LINUX)
SETS = [("Submitted v1 (submitted code, Linux)", os.path.join(PR, "results", "tables")), ("REGEN-WIN (reporting set)", REGEN),
        ("REGEN-LINUX (current code, Linux)", os.path.join(REV, "label_fix_20261123", "outputs", "linux_tables"))]


def rd_csv(d, f):
    return list(csv.DictReader(io.StringIO(open(os.path.join(d, f), encoding="utf-8").read())))


rows6 = []
for lab, d in SETS:
    t5 = {(r["Scenario"], r["Policy"]): r for r in rd_csv(d, "T5_test_weeks.csv")}
    s4 = {r["Policy"]: r for r in rd_csv(d, "E1_aggregate_all_test_weeks.csv")}
    t10 = {r["Policy"]: r for r in rd_csv(d, "T10_fast_vs_event.csv")}
    sel = rd_csv(d, "E1_selected_parameters.csv")
    ns = lambda p: t5[("new_spike", p)]
    rows6.append([lab, ", ".join(str(r["PRISM"]) for r in sel),
                  f"{ns('PRISM')['Violating windows (%)'].split(' ')[0]} ({ns('PRISM')['SLO met']})", ns("PredHead+hyst")["Violating windows (%)"].split(" ")[0],
                  ns("PredHead")["Violating windows (%)"].split(" ")[0], f"{s4['PRISM']['Mean cost (USD)']} / {s4['QuantProv_q90']['Mean cost (USD)']}",
                  f"{s4['PRISM']['Mean violating windows (%)']} / {s4['QuantProv_q90']['Mean violating windows (%)']}",
                  f"{t10['PRISM']['Viol fast']} / {t10['PRISM']['Viol event']}"])
assert rows6[1][2].startswith("2.11") and rows6[2][2].startswith("2.62") and rows6[0][2].startswith("1.55"), rows6
md = ["# TR6. Platform and code-version sensitivity of the headline values (fast simulator, assumed constants)", "",
      "Same seeds and protocol. Forecast-driven policies (PredHead, PredHead+hyst, QuantProv, PRISM) differ between Windows and",
      "Linux even with identical code and packages; policies without a forecast are identical. Sources: `prism-repro/results/tables/`",
      "(submitted v1), `regeneration_20261122/outputs/tables/` (REGEN-WIN), `label_fix_20261123/outputs/linux_tables/` (REGEN-LINUX).", "",
      "| Set | PRISM eps selected, traces 101-105 | Table V new spike: PRISM viol. % (SLO met) | smoothed headroom viol. % | unsmoothed headroom viol. % | Table S4 cost PRISM / QuantProv-q90 (USD) | Table S4 viol. PRISM / QuantProv-q90 (%) | Table X PRISM viol. fast / event |",
      "|---|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(map(str, r)) + " |" for r in rows6]
md += ["", "Reading: the ordering 'both headroom rules cheaper, PRISM least violating under the new spike' holds in all three",
       "sets, but PRISM is above the 2% target on average in both regenerations (it was below in v1), and the Table S4",
       "ordering of PRISM against QuantProv-q90 reverses between Windows and Linux."]
write("TR6_platform_sensitivity", md, rows6, ["set", "prism_eps_101_105", "t5_newspike_prism_viol_slo", "t5_newspike_predheadhyst_viol", "t5_newspike_predhead_viol", "s4_cost_prism_quantprov", "s4_viol_prism_quantprov", "t10_prism_viol_fast_event"])

# ---------------------------------------------------------------- graphical abstract: every plotted value and its source
T5 = os.path.join(REGEN, "T5_test_weeks.md")
E4B = os.path.join(REGEN, "revision", "E4b_fixed_memory_summary.json")


def pm(s):
    q = re.match(r"\s*([\d,.]+)\s*±\s*([\d,.]+)", s)
    return float(q.group(1).replace(",", "")), float(q.group(2).replace(",", ""))


BARS = ("PRISM", "PredHead+hyst", "PredHead")
vals = {}
for line in open(T5, encoding="utf-8"):
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) >= 9 and c[0] == "new_spike" and c[1] in BARS:
        cost, viol = pm(c[2]), pm(c[3])
        vals[c[1]] = dict(cost=cost[0], cost_h=cost[1], viol=viol[0], viol_h=viol[1], slo_met=c[7], n=int(c[8]))
assert {k: (v["viol"], v["cost"]) for k, v in vals.items()} == {"PRISM": (2.11, 1270.0), "PredHead+hyst": (4.11, 1150.0), "PredHead": (7.92, 1077.0)}, vals
assert vals["PRISM"]["slo_met"] == "40%" and all(v["n"] == 5 for v in vals.values())
short = [r for r in json.load(open(E4B, encoding="utf-8"))["regimes"] if r["deadline"] < 14.5 and r["eps"] == 0.02]
rng = sorted(r["best_PredHead_2048_vs_best_PRISM_pct"] for r in short)
assert len(short) == 4 and round(rng[0], 1) == 12.9 and round(rng[-1], 1) == 27.3
with open(os.path.join(OUT, "GA_inputs.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["quantity", "policy", "value", "half_width_95", "unit", "n_traces", "source"])
    for p in BARS:
        v = vals[p]
        w.writerow(["violating windows", p, v["viol"], v["viol_h"], "% of 15-min windows", v["n"], "regeneration_20261122/outputs/tables/T5_test_weeks.md new_spike"])
        w.writerow(["weekly cost", p, v["cost"], v["cost_h"], "USD/week (simulated)", v["n"], "same"])
    w.writerow(["PRISM traces meeting 2%", "PRISM", vals["PRISM"]["slo_met"], "", "share of 5 traces", 5, "same, SLO met"])
    for r in short:
        w.writerow(["2048 MB headroom cheaper than best PRISM", f"ns{r['nonscaling']} D{r['deadline']}", round(r["best_PredHead_2048_vs_best_PRISM_pct"], 2), "", "%", 2,
                    "regeneration_20261122/outputs/tables/revision/E4b_fixed_memory_summary.json"])
INDEX.append("GA_inputs")

open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join([
    "# Revision summary tables", "",
    "Generated by `docs/reproducibility/make_tables.py` from evidence committed in this repository (no simulation).",
    "Each table states its source, configuration, metric, units and denominator.", "",
    "- `REGEN-WIN_table_map.md`: the regenerated file behind each results table (submitted and planned revised numbers).",
    "- `TR1_confirmatory_C1_C3`: prespecified held-out comparisons C1-C3 (frozen configuration, assumed constants).",
    "- `TR2_calibrated_development`: calibrated development evidence, corrected start-up (traces 101-105; not confirmatory).",
    "- `TR3_r61_live_replay`: R6.1 paired live replay on AWS Lambda, record-level outcomes and actuation.",
    "- `TR4_aws_measurements`: memcal-1 and the live integration run.",
    "- `TR5_cost_evidence_by_kind`: list-price estimates, provisional billing exports and the open final charges, kept apart.",
    "- `TR6_platform_sensitivity`: submitted v1 against REGEN-WIN and REGEN-LINUX headline values.",
    "- `GA_inputs.csv`: every value plotted in the graphical abstract, with its source file."]) + "\n")
print("written:", ", ".join(INDEX))
