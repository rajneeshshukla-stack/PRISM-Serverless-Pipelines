#!/usr/bin/env python3
"""Compute every table and figure of the reconstruction from the saved raw outputs in
results/raw/. Nothing here is copied from the manuscript.

Usage: python scripts/analyze.py
Outputs: results/tables/*.md|*.csv, results/figures/*.pdf|*.png, results/summary.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
RAW = os.environ.get("PRISM_RESULTS", os.path.join(ROOT, "results", "raw"))
TAB = os.path.join(ROOT, "results", "tables")
FIG = os.path.join(ROOT, "results", "figures")
os.makedirs(TAB, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

from prism_repro.experiment import select_by_rule  # noqa: E402

SCEN = ["stationary", "growth", "bursty", "new_spike"]
MAIN = ["OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PRISM"]
EXTRA = ["PredHead+hyst", "QuantProv_q90", "QuantProv_q99"]
SUMMARY: dict = {"_note": "All values are from SYNTHETIC simulations of this reimplementation."}
STATUS: dict = {}


def rows(exp):
    p = os.path.join(RAW, exp, "rows.jsonl")
    if not os.path.exists(p):
        STATUS[exp] = "not executed"
        return pd.DataFrame()
    df = pd.DataFrame([json.loads(l) for l in open(p)])
    # a chunk interrupted between writing rows and arrays is rerun: keep the last copy of each run.
    # Rows without a run_id (forecast-only rows) are keyed by (seed, scenario, forecaster).
    parts = []
    if "run_id" in df:
        has = df["run_id"].notna()
        parts.append(df[has].drop_duplicates("run_id", keep="last"))
        rest = df[~has]
    else:
        rest = df
    if len(rest):
        key = [c for c in ("seed", "scenario", "forecaster", "label", "tag") if c in rest]
        parts.append(rest.drop_duplicates(key, keep="last") if "forecaster" in rest or "label" in rest else rest)
    df = pd.concat(parts, ignore_index=True) if parts else df
    STATUS[exp] = f"{df['seed'].nunique()} seeds, {len(df)} rows, failed={int((df.get('status') == 'failed').sum())}"
    return df


def arrays(exp, seed):
    p = os.path.join(RAW, exp, f"arrays_seed{seed}.npz")
    return np.load(p) if os.path.exists(p) else None


def tci(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return np.nan, np.nan, 0
    if n == 1:
        return float(x[0]), np.nan, 1
    return float(x.mean()), float(stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)), n


def fmt(m, h, d=0, pct=False):
    k = 100 if pct else 1
    if not np.isfinite(m):
        return "n/a"
    s = f"{m * k:,.{d}f}"
    return s + (f" ± {h * k:,.{d}f}" if np.isfinite(h) else "")


def write(name, df, title, note=""):
    df.to_csv(os.path.join(TAB, name + ".csv"), index=False)
    with open(os.path.join(TAB, name + ".md"), "w") as f:
        f.write(f"# {title}\n\n{note}\n\n" if note else f"# {title}\n\n")
        f.write(df.to_markdown(index=False) if len(df) else "_no data (experiment not executed)_")
        f.write("\n")


def select(df_val, by="policy"):
    """seed -> variant -> selected row (validation rule)."""
    out = {}
    for (seed, v), g in df_val.groupby(["seed", by]):
        out.setdefault(seed, {})[v] = select_by_rule(g.to_dict("records"))
    return out


# ---------------------------------------------------------------- E1 main protocol
e1 = rows("E1")
SEL = {}
if len(e1):
    e1 = e1[e1.status == "ok"]
    val = e1[e1.week == "val"]
    test = e1[e1.week == "test"]
    SEL = select(val)
    seeds = sorted(SEL)
    SUMMARY["E1_seeds"] = seeds
    # selected parameters
    sp = pd.DataFrame([{"seed": s, **{v: SEL[s][v]["param"] for v in MAIN[1:] + EXTRA if v in SEL[s]}} for s in seeds])
    write("E1_selected_parameters", sp, "Validation-selected parameters per trace (§5.3 rule)")
    SUMMARY["selected"] = sp.to_dict("records")
    tkey = test.set_index(["seed", "scenario", "label"], drop=False)

    def test_row(seed, sc, variant):
        lab = SEL[seed][variant]["label"]
        return tkey.loc[(seed, sc, lab)]

    # Table 5 analogue
    t5, per = [], {}
    for sc in SCEN:
        for v in MAIN + EXTRA:
            rs = [test_row(s, sc, v) for s in seeds if v in SEL[s]]
            if not rs:
                continue
            r = pd.DataFrame(rs)
            per[(sc, v)] = r
            c, v_ = tci(r.cost), tci(r.violating_window_rate)
            t5.append({"Scenario": sc, "Policy": v, "Cost (USD)": fmt(c[0], c[1]),
                       "Violating windows (%)": fmt(v_[0], v_[1], 2, True),
                       "Record attainment (%)": f"{r.record_attainment.mean()*100:.2f}",
                       "p99 latency (s)": f"{r.p99_latency.mean():.2f}",
                       "Billing utilisation": f"{r.billing_utilisation.mean()*100:.0f}%",
                       "SLO met": f"{r.slo_met.mean()*100:.0f}%", "n": len(r)})
    write("T5_test_weeks", pd.DataFrame(t5), "Test weeks, validation-tuned parameters (mean ± 95% t half-width over traces)",
          "SYNTHETIC simulation (fast simulator). Violating window: 15-min window with record attainment < 99%.")
    SUMMARY["T5"] = {f"{sc}|{v}": {"cost": float(r.cost.mean()), "viol": float(r.violating_window_rate.mean()),
                                   "slo_met": float(r.slo_met.mean())} for (sc, v), r in per.items()}
    # 20-week aggregates
    agg = []
    for v in MAIN + EXTRA:
        rs = pd.concat([per[(sc, v)] for sc in SCEN if (sc, v) in per])
        agg.append({"Policy": v, "Mean cost (USD)": f"{rs.cost.mean():,.0f}",
                    "Mean violating windows (%)": f"{rs.violating_window_rate.mean()*100:.2f}",
                    "SLO met (share of test weeks)": f"{rs.slo_met.mean()*100:.0f}%", "test weeks": len(rs)})
        SUMMARY.setdefault("agg", {})[v] = dict(cost=float(rs.cost.mean()), viol=float(rs.violating_window_rate.mean()),
                                                slo=float(rs.slo_met.mean()), n=len(rs))
    write("E1_aggregate_all_test_weeks", pd.DataFrame(agg), "Aggregate over all test weeks (traces × scenarios)")

    # Table 6 analogue: paired differences
    def paired(a, b, label):
        out = []
        for sc in SCEN:
            # pair by trace (seed) key, not by row position (M16); keeps the seed order of `a`
            ra, rb = per[(sc, a)].set_index("seed"), per[(sc, b)].set_index("seed")
            common = [s for s in ra.index if s in rb.index]
            ra, rb = ra.loc[common], rb.loc[common]
            dc = ra.cost.values - rb.cost.values
            dp = 100 * dc / rb.cost.values
            dv = 100 * (ra.violating_window_rate.values - rb.violating_window_rate.values)
            m1, m2, m3 = tci(dc), tci(dp), tci(dv)
            out.append({"Scenario": sc, "Cost diff (USD)": fmt(*m1[:2]), "Cost diff (%)": fmt(m2[0], m2[1], 1),
                        "Violating-window diff (pp)": fmt(m3[0], m3[1], 2),
                        f"traces {a} cheaper": int((dc < 0).sum()), f"traces {a} fewer violations": int((dv < 0).sum()),
                        "n": len(dc)})
            SUMMARY.setdefault("paired", {})[f"{a}-{b}|{sc}"] = dict(cost_pct=m2[0], cost_pct_hw=m2[1], viol_pp=m3[0],
                                                                     viol_pp_hw=m3[1], n_cheaper=int((dc < 0).sum()),
                                                                     n_fewer=int((dv < 0).sum()))
        write(f"T6_paired_{label}", pd.DataFrame(out), f"Paired differences {a} minus {b} per trace (test weeks)")

    paired("PRISM", "PredHead", "PRISM_vs_PredHead")
    paired("PRISM", "PredHead+hyst", "PRISM_vs_PredHeadHyst")
    paired("PRISM", "QuantProv_q90", "PRISM_vs_QuantProvq90")

    # Table 7 analogue: frozen vs test-retuned (diagnostic)
    t7 = []
    for sc in SCEN:
        rec = {"Scenario": sc}
        for v in ("PredHead", "PRISM"):
            fz = per[(sc, v)]
            rt = []
            for s in seeds:
                g = test[(test.seed == s) & (test.scenario == sc) & (test.policy == v)]
                rt.append(select_by_rule(g.to_dict("records")))
            rt = pd.DataFrame(rt)
            rec[f"{v} frozen"] = f"{fz.cost.mean():,.0f} / {fz.violating_window_rate.mean()*100:.2f}%"
            rec[f"{v} retuned (diagnostic)"] = f"{rt.cost.mean():,.0f} / {rt.violating_window_rate.mean()*100:.2f}%"
        t7.append(rec)
    write("T7_frozen_vs_retuned", pd.DataFrame(t7), "Frozen (validation-tuned) vs test-retuned parameters (cost USD / violating windows); retuned uses test-week knowledge and is a diagnostic only")

    # validation frontier
    fr = val.groupby(["policy", "param"], dropna=False).agg(cost=("cost", "mean"),
                                                           viol=("violating_window_rate", "mean")).reset_index()
    fr.to_csv(os.path.join(TAB, "F3_validation_frontier.csv"), index=False)
    front = []
    for v in ["Static", "Scheduled", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]:
        g = fr[fr.policy == v]
        rec = {"Policy": v}
        for thr in (0.01, 0.02):
            ok = g[g.viol <= thr]
            rec[f"min mean cost with ≤{int(thr*100)}% viol"] = f"{ok.cost.min():,.0f}" if len(ok) else "none"
            SUMMARY.setdefault("frontier", {})[f"{v}|{thr}"] = float(ok.cost.min()) if len(ok) else None
        front.append(rec)
    write("F3_validation_frontier_summary", pd.DataFrame(front),
          "Validation week: cheapest grid point whose mean (over traces) violating-window rate is under a threshold")

    # severity (Tables 15/16 analogue)
    sev = []
    for v in MAIN:
        rs = pd.concat([per[(sc, v)] for sc in SCEN])
        sev.append({"Policy": v, "Late records/week": f"{rs.late_records.mean():,.0f}",
                    "Attainment in violating windows": f"{np.nanmean(rs.attain_in_violating)*100:.2f}%",
                    "Worst-window attainment": f"{rs.worst_window_attainment.mean()*100:.2f}%",
                    "Longest run (windows)": f"{rs.longest_run.mean():.1f}", "Mean run": f"{rs.mean_run.mean():.2f}",
                    "Runs/week": f"{rs.n_runs.mean():.1f}"})
    write("T15_severity", pd.DataFrame(sev), "Violation severity and persistence, mean over all test weeks (fast simulator)")

    # Table 13 analogue: infeasibility (needs per-epoch arrays)
    t13 = []
    for e in sorted(test[test.policy == "PRISM"].param.unique()):
        inf, exc, mx, flagged, vf, vo = [], [], [], 0, [], []
        for s in seeds:
            A = arrays("E1", s)
            for sc in SCEN:
                rid = f"E1|{s}|{sc}|test|PRISM-{e}|"
                fe, ex, wa = A[rid + "::feasible_epoch"], A[rid + "::excess_epoch"], A[rid + "::window_attainment"]
                inf.append(1 - fe.mean())
                exc.extend(ex[~fe].tolist())
                mx.append(ex.max())
                wflag = ~fe.reshape(-1, 3).all(1)
                flagged += int(wflag.sum())
                viol = wa < 0.99 - 1e-12
                vf.append((viol[wflag].sum(), wflag.sum()))
                vo.append((viol[~wflag].sum(), (~wflag).sum()))
        vfs = sum(a for a, _ in vf) / max(1, sum(b for _, b in vf))
        vos = sum(a for a, _ in vo) / max(1, sum(b for _, b in vo))
        t13.append({"eps": e, "Infeasible epochs": f"{np.mean(inf)*100:.2f}%",
                    "Mean excess over eps": f"{np.mean(exc):.4f}" if exc else "0",
                    "Largest excess": f"{np.max(mx):.4f}", "Windows flagged": flagged,
                    "Viol. windows: flagged": f"{vfs*100:.1f}%" if flagged else "n/a",
                    "Viol. windows: other": f"{vos*100:.1f}%", "test weeks": len(inf)})
        SUMMARY.setdefault("infeasible", {})[str(e)] = float(np.mean(inf))
    write("T13_infeasibility", pd.DataFrame(t13), "Infeasible PRISM epochs by operating point (all test weeks; δ = 0.1)")
    km = test[test.policy == "PRISM"].kappa_mean
    SUMMARY["kappa_mean_range"] = [float(km.min()), float(km.max())]

# ---------------------------------------------------------------- E2 forecast
e2 = rows("E2")
if len(e2):
    t4 = []
    for sc in SCEN:
        g = e2[e2.scenario == sc]
        rec = {"Scenario": sc}
        for k, lab in [("mape_median", "MAPE median (%)"), ("cov50", "q50"), ("cov90_raw", "q90 raw"),
                       ("cov99_raw", "q99 raw"), ("cov99_cal", "q99 + conformal"), ("cov90_cal", "q90 + conformal")]:
            m = tci(g[k])
            rec[lab] = fmt(m[0], m[1], 1) if k == "mape_median" else fmt(m[0], m[1], 3)
            SUMMARY.setdefault("E2", {})[f"{sc}|{k}"] = m[0]
        t4.append(rec)
    write("T4_forecast_coverage", pd.DataFrame(t4), "Forecast accuracy and empirical coverage on test weeks (mean ± 95% half-width over traces)")
    SUMMARY["E2_reversals"] = int(e2.reversals_val_test.sum())
    SUMMARY["E2_min_offset"] = float(e2.min_offset.min())

# ---------------------------------------------------------------- E3 ablations
e3 = rows("E3")
if len(e3) and SEL:
    e3 = e3[e3.status == "ok"]
    out = []
    for sc in SCEN:
        base = pd.DataFrame([tkey.loc[(s, sc, SEL[s]["PRISM"]["label"])] for s in SEL])
        rec = {"Scenario": sc, "PRISM": f"{base.cost.mean():,.0f} / {base.violating_window_rate.mean()*100:.2f}%"}
        for tag, name in [("noconf", "No conformal"), ("oracle", "Oracle")]:
            g = e3[(e3.scenario == sc) & (e3.tag == tag)]
            rec[name] = f"{g.cost.mean():,.0f} / {g.violating_window_rate.mean()*100:.2f}%"
            SUMMARY.setdefault("E3", {})[f"{sc}|{tag}"] = dict(cost=float(g.cost.mean()), viol=float(g.violating_window_rate.mean()))
        SUMMARY["E3"][f"{sc}|prism"] = dict(cost=float(base.cost.mean()), viol=float(base.violating_window_rate.mean()))
        g = e3[(e3.scenario == sc) & (e3.tag == "noconf")].sort_values("seed")
        b = base.sort_values("seed")
        rec["traces where removing conformal raised violations"] = f"{int((g.violating_window_rate.values > b.violating_window_rate.values).sum())}/{len(g)}"
        out.append(rec)
    write("E3_ablation_conformal_oracle", pd.DataFrame(out), "PRISM ablations at validation-chosen ε (cost USD / violating windows; mean over traces)")
    # quantile mode
    qm = []
    for sc in ("stationary", "new_spike"):
        same_P, same_m, dc, dv, tq, ts_ = [], [], [], [], [], []
        for s in SEL:
            lab = SEL[s]["PRISM"]["label"]
            A1, A3 = arrays("E1", s), arrays("E3", s)
            r1 = f"E1|{s}|{sc}|test|{lab}|"
            r3 = f"E3|{s}|{sc}|test|{lab.replace('PRISM', 'PRISM-qmode')}|qmode"
            same_P.append(np.mean(np.all(A1[r1 + "::P_epoch"] == A3[r3 + "::P_epoch"], 1)))
            same_m.append(np.mean(A1[r1 + "::mem_epoch"] == A3[r3 + "::mem_epoch"]))
            g = e3[(e3.seed == s) & (e3.scenario == sc) & (e3.tag == "qmode")].iloc[0]
            b = tkey.loc[(s, sc, lab)]
            dc.append(g.cost / b.cost - 1)
            dv.append(g.violating_window_rate - b.violating_window_rate)
            tq.append(g.decision_ms_median)
            ts_.append(b.decision_ms_median)
        qm.append({"Scenario": sc, "Identical P (share of epochs)": f"{np.mean(same_P)*100:.1f}%",
                   "Identical memory": f"{np.mean(same_m)*100:.1f}%", "Cost diff": f"{np.mean(dc)*100:+.2f}%",
                   "Viol diff (pp)": f"{np.mean(dv)*100:+.2f}", "Decision ms scenarios": f"{np.median(ts_):.2f}",
                   "Decision ms quantile": f"{np.median(tq):.2f}"})
        SUMMARY.setdefault("qmode", {})[sc] = dict(same_P=float(np.mean(same_P)), same_mem=float(np.mean(same_m)))
    write("E3_quantile_vs_scenario_feasibility", pd.DataFrame(qm), "Quantile-mode vs scenario-mode feasibility (§6.10 analogue)",
          "Decision time is the median per-epoch optimiser call measured inside the simulation loop on the reference sandbox (1 shared CPU core).")
    # hysteresis (Table 14)
    t14 = []
    for sc in ("stationary", "new_spike"):
        for e in sorted(e3[e3.tag == "nohyst"].param.unique()):
            w = test[(test.policy == "PRISM") & (test.scenario == sc) & (test.param == e)]
            wo = e3[(e3.tag == "nohyst") & (e3.scenario == sc) & (e3.param == e)]
            for name, g in (("with", w), ("without", wo)):
                t14.append({"Scenario": sc, "eps": e, "Hysteresis": name, "Cost": f"{g.cost.mean():,.0f}",
                            "Violating windows": f"{g.violating_window_rate.mean()*100:.2f}%",
                            "Minutes with a change": f"{g.minutes_with_change.mean():,.0f}",
                            "Environments added": f"{g.envs_added.mean():,.0f}",
                            "Mean provisioned": f"{g.mean_provisioned.mean():.0f}",
                            "Cold-start ratio": f"{g.cold_start_ratio.mean()*100:.3f}%", "p99 (s)": f"{g.p99_latency.mean():.2f}"})
    write("T14_hysteresis", pd.DataFrame(t14), "Scale-in hysteresis across operating points (mean over traces; test weeks)")

# ---------------------------------------------------------------- E4 memory
e4 = rows("E4")
if len(e4):
    t8 = []
    for tag in e4.tag.unique():
        g = e4[e4.tag == tag]
        ns, D = tag.replace("ns", "").split("_D")
        def cell(sub, mem=False):
            if not len(sub):
                return "n/a"
            s = f"{sub.cost.mean():,.0f} / {sub.violating_window_rate.mean()*100:.2f}%"
            return s + (f" / {sub.share_mem_ge_2048.mean()*100:.0f}%" if mem else "")
        for e in sorted(g[g.policy == "PRISM"].param.unique()):
            best = []
            for s in g.seed.unique():
                ph = g[(g.seed == s) & (g.policy == "PredHead")]
                best.append(select_by_rule(ph.to_dict("records")))
            best = pd.DataFrame(best)
            t8.append({"Non-scaling": ns, "Deadline D (s)": D, "eps": e,
                       "PRISM with memory (cost / viol / share ≥2048 MB)": cell(g[(g.policy == "PRISM") & (g.param == e)], True),
                       "PRISM, memory fixed": cell(g[(g.policy == "PRISM-fixedmem") & (g.param == e)]),
                       "Best PredHead (test-selected, 1024 MB)": cell(best),
                       "OnDemand": cell(g[g.policy == "OnDemand"]), "traces": g.seed.nunique()})
    write("T8_memory_regimes", pd.DataFrame(t8), "Memory regimes, stationary test week (mean over traces)")
    SUMMARY["E4"] = pd.DataFrame(t8).to_dict("records")

# ---------------------------------------------------------------- E5 sensitivity
e5 = rows("E5")
if len(e5):
    t9 = []
    for tag in ["default", "keepalive5", "keepalive30", "init3", "init9"]:
        g = e5[e5.tag == tag]
        if not len(g):
            continue
        sel = select(g[g.week == "val"])
        for sc in ("stationary", "growth"):
            rec = {"Setting": tag, "Test week": sc}
            for v in ["OnDemand", "Static", "Reactive", "PredHead", "PRISM"]:
                rs = [g[(g.seed == s) & (g.week == "test") & (g.scenario == sc) & (g.label == sel[s][v]["label"])].iloc[0]
                      for s in sel]
                rs = pd.DataFrame(rs)
                rec[v] = f"{rs.cost.mean():,.0f} / {rs.violating_window_rate.mean()*100:.2f}%"
                SUMMARY.setdefault("E5", {})[f"{tag}|{sc}|{v}"] = dict(cost=float(rs.cost.mean()), viol=float(rs.violating_window_rate.mean()))
            t9.append(rec)
    write("T9_sensitivity", pd.DataFrame(t9), "Simulator-assumption sensitivity (validation-tuned per setting; cost USD / violating windows; mean over traces)")

# ---------------------------------------------------------------- E6 caps
e6 = rows("E6")
if len(e6):
    out = []
    for sc in ("stationary", "new_spike"):
        for tag in ["capNone", "cap250", "cap60", "cap40"]:
            g = e6[(e6.scenario == sc) & (e6.tag == tag)]
            out.append({"Scenario": sc, "Cap": tag.replace("cap", ""), "Cost": f"{g.cost.mean():,.0f}",
                        "Violating windows": f"{g.violating_window_rate.mean()*100:.2f}%",
                        "Infeasible epochs": f"{g.infeasible_share.mean()*100:.2f}%",
                        "Mean provisioned": f"{g.mean_provisioned.mean():.0f}", "traces": len(g)})
    write("E6_caps", pd.DataFrame(out), "Per-stage provisioning caps, PRISM ε = 0.02 (mean over traces)")

# ---------------------------------------------------------------- E7 features
e7 = rows("E7")
if len(e7) and SEL:
    f7 = e7[e7.get("kind") == "forecast"]
    r7 = e7[(e7.get("kind") != "forecast") & (e7.status == "ok")]
    out = []
    for sc in SCEN + ["shifted_triggers"]:
        for name in ["gbm", "gbm_no_trigger", "gbm_no_prevday", "gbm_no_norm"]:
            f = f7[(f7.scenario == sc) & (f7.forecaster == name)]
            if name == "gbm" and sc != "shifted_triggers":
                p = pd.DataFrame([tkey.loc[(s, sc, SEL[s]["PRISM"]["label"])] for s in SEL])
            else:
                p = r7[(r7.scenario == sc) & (r7.tag == name)]
            out.append({"Scenario": sc, "Variant": name, "MAPE (%)": f"{f.mape_median.mean():.1f}",
                        "Pinball τ=0.9": f"{f.pinball_90.mean():.1f}", "Coverage q99 raw": f"{f.cov99_raw.mean()*100:.1f}%",
                        "PRISM cost": f"{p.cost.mean():,.0f}", "PRISM viol": f"{p.violating_window_rate.mean()*100:.2f}%"})
            SUMMARY.setdefault("E7", {})[f"{sc}|{name}"] = dict(mape=float(f.mape_median.mean()),
                                                                cost=float(p.cost.mean()), viol=float(p.violating_window_rate.mean()))
    write("T20_feature_ablation", pd.DataFrame(out), "Feature-group ablations (mean over traces; PRISM at the full model's validation-chosen ε)")

# ---------------------------------------------------------------- E8 reference forecasters
e8 = rows("E8")
E8_DONE = len(e8) and "status" in e8 and len(e8[(e8.get("kind") != "forecast")]) and \
    e8[(e8.get("kind") != "forecast")].seed.nunique() >= 3
if len(e8) and not E8_DONE:
    STATUS["E8"] += " (incomplete: tables not generated)"
if len(e8) and SEL and E8_DONE:
    f8 = e8[e8.get("kind") == "forecast"]
    # Gradient-boosting rows come from E2 (the main runs, original build environment), as in the paper.
    # E8 re-trained gbm under a newer scikit-learn release (1.9.1); those rows differ slightly
    # (|dMAPE| <= 0.09) and are kept in results/raw/E8 for reference only.
    e2g = rows("E2")
    e2g = e2g[e2g.forecaster == "gbm"]
    t18 = []
    for name in ["gbm", "seasonal_naive", "last5max", "ewma"]:
        f = e2g if name == "gbm" else f8[f8.forecaster == name]
        t18.append({"Forecaster": name, "MAPE median (%)": f"{f.mape_median.mean():.1f}",
                    "Pinball 0.5": f"{f.pinball_50.mean():.1f}", "Pinball 0.9": f"{f.pinball_90.mean():.1f}",
                    "Pinball 0.99": f"{f.pinball_99.mean():.1f}", "Cov q90": f"{f.cov90_raw.mean()*100:.1f}%",
                    "Cov q99": f"{f.cov99_raw.mean()*100:.1f}%"})
    write("T18_reference_forecasters", pd.DataFrame(t18), "Probabilistic accuracy of the window-peak forecast (raw quantiles; mean over traces and scenarios)")
    r8 = e8[(e8.get("kind") != "forecast") & (e8.status == "ok")]
    s8 = sorted(r8.seed.unique())
    t19 = []
    for name in ["gbm", "seasonal_naive", "last5max", "ewma"]:
        for meth, var in (("PRISM", "PRISM"), ("QuantProv q99", "QuantProv_q99")):
            rec = {"Forecaster + method": f"{name} + {meth}"}
            for sc in SCEN:
                cs = []
                for s in s8:
                    if name == "gbm":
                        cs.append(tkey.loc[(s, sc, SEL[s][var]["label"])])
                    else:
                        vv = f"{var}[{name}]"
                        sel = select_by_rule(r8[(r8.seed == s) & (r8.week == "val") & (r8.policy == vv)].to_dict("records"))
                        cs.append(r8[(r8.seed == s) & (r8.week == "test") & (r8.scenario == sc) & (r8.label == sel["label"])].iloc[0])
                cs = pd.DataFrame(cs)
                rec[sc] = f"{cs.cost.mean():,.0f} / {cs.violating_window_rate.mean()*100:.2f}%"
            t19.append(rec)
    write("T19_reference_downstream", pd.DataFrame(t19), "Downstream provisioning by forecaster (validation-tuned; cost USD / violating windows)")

# ---------------------------------------------------------------- E9 event-level
e9 = rows("E9")
if len(e9):
    t10 = []
    for v in MAIN:
        g = e9[e9.policy == v]
        t10.append({"Policy": v, "Cost fast": f"{g.fast_cost.mean():,.0f}", "Cost event": f"{g.event_cost.mean():,.0f}",
                    "Cost rel. diff": f"{(g.event_cost / g.fast_cost - 1).mean()*100:+.2f}%",
                    "Viol fast": f"{g.fast_violating_window_rate.mean()*100:.2f}%",
                    "Viol event": f"{g.event_violating_window_rate.mean()*100:.2f}%",
                    "Viol ratio event/fast": f"{g.event_violating_window_rate.mean()/max(g.fast_violating_window_rate.mean(),1e-9):.2f}",
                    "Record att. fast/event": f"{g.fast_record_attainment.mean()*100:.2f} / {g.event_record_attainment.mean()*100:.2f}",
                    "Cold-start ratio fast/event": f"{g.fast_cold_start_ratio.mean()*100:.3f}% / {g.event_cold_start_ratio.mean()*100:.3f}%",
                    "SLO met fast/event": f"{g.fast_slo_met.mean()*100:.0f}% / {g.event_slo_met.mean()*100:.0f}%",
                    "test weeks": len(g)})
        SUMMARY.setdefault("E9", {})[v] = dict(cost_rel=float((g.event_cost / g.fast_cost - 1).mean()),
                                               viol_fast=float(g.fast_violating_window_rate.mean()),
                                               viol_event=float(g.event_violating_window_rate.mean()),
                                               slo_fast=float(g.fast_slo_met.mean()), slo_event=float(g.event_slo_met.mean()))
    write("T10_fast_vs_event", pd.DataFrame(t10), "Fast vs event-level simulator for the same frozen schedules (open loop)")
    rc, rv = [], []
    for (s, sc), g in e9.groupby(["seed", "scenario"]):
        if len(g) >= 3:
            rc.append(stats.spearmanr(g.fast_cost, g.event_cost)[0])
            rv.append(stats.spearmanr(g.fast_violating_window_rate, g.event_violating_window_rate)[0])
    SUMMARY["E9_spearman"] = dict(cost_mean=float(np.mean(rc)), cost_min=float(np.min(rc)),
                                  viol_mean=float(np.nanmean(rv)), viol_min=float(np.nanmin(rv)), weeks=len(rc))
    dd = []
    for sc in SCEN:
        a = e9[(e9.scenario == sc) & (e9.policy == "PRISM")].sort_values("seed")
        b = e9[(e9.scenario == sc) & (e9.policy == "PredHead")].sort_values("seed")
        dd.append({"Scenario": sc,
                   "PRISM−PredHead viol (pp) fast": f"{(a.fast_violating_window_rate.values - b.fast_violating_window_rate.values).mean()*100:+.2f}",
                   "PRISM−PredHead viol (pp) event": f"{(a.event_violating_window_rate.values - b.event_violating_window_rate.values).mean()*100:+.2f}",
                   "PRISM−PredHead cost (USD) fast": f"{(a.fast_cost.values - b.fast_cost.values).mean():+,.0f}",
                   "PRISM−PredHead cost (USD) event": f"{(a.event_cost.values - b.event_cost.values).mean():+,.0f}"})
    write("T10b_prism_vs_predhead_fidelity", pd.DataFrame(dd), "PRISM minus PredHead under both simulators (same frozen schedules)")
    det = e9[e9.est_erlangb.notna()] if "est_erlangb" in e9 else pd.DataFrame()
    if len(det):
        t11 = []
        for sc in det.scenario.unique():
            g = det[(det.scenario == sc) & (det.policy != "OnDemand")]
            ev = g.event_overflow_share.mean()
            def rel(x):
                return f"{x*100:.2f}% ({(x/ev-1)*100:+.0f}%)"
            t11.append({"Scenario": sc, "Event-level": f"{ev*100:.2f}%", "Erlang-B (mean load)": rel(g.est_erlangb.mean()),
                        "Fast simulator": rel(g.fast_overflow_share.mean()), "o(P,c) mean load": rel(g.est_occ_mean.mean()),
                        "o(P,c_eff) (optimiser)": rel(g.est_occ_ceff.mean())})
        write("T11_overflow_estimates", pd.DataFrame(t11), "Share of stage executions served on demand: event-level vs analytic estimates (5 provisioned policies; detail trace)")
        p = det[det.policy == "PRISM"]
        SUMMARY["E9_inflight_ratio_prism"] = {q: float(p[f"inflight_ratio_q{q}"].mean()) for q in (10, 50, 90, 99)}
        SUMMARY["E9_sampling_flips"] = dict(min=float(det.sampling_flip_mean.min()), max=float(det.sampling_flip_mean.max()))
        fl = det[["scenario", "policy", "sampling_flip_mean", "inflight_ratio_q10", "inflight_ratio_q50",
                  "inflight_ratio_q90", "inflight_ratio_q99"]].copy()
        write("E9_inflight_and_sampling", fl.round(3), "Event-level max in-flight / fast-simulator peak draw (quantiles) and latency-sampling window flips (detail trace)")

# ---------------------------------------------------------------- E10, E11
e10 = rows("E10")
if len(e10):
    write("E10_overhead", e10.drop(columns=[c for c in e10.columns if c in ("source_sha256",)]).round(4),
          "Online controller overhead per epoch (one test week; measured on the reference sandbox, shared single core)")
    SUMMARY["E10"] = e10.iloc[0][[c for c in e10.columns if "ms" in c or "identical" in c or "diff" in c]].to_dict()
e11 = rows("E11")
if len(e11) and SEL:
    e11 = e11[e11.status == "ok"]
    sel11 = select(e11[e11.week == "val"])
    out = []
    for sc in SCEN:
        a, b = [], []
        for s in sel11:
            a.append(e11[(e11.seed == s) & (e11.week == "test") & (e11.scenario == sc) & (e11.label == sel11[s]["PRISM_EB"]["label"])].iloc[0])
            b.append(tkey.loc[(s, sc, SEL[s]["PRISM"]["label"])])
        a, b = pd.DataFrame(a), pd.DataFrame(b)
        out.append({"Scenario": sc, "PRISM": f"{b.cost.mean():,.0f} / {b.violating_window_rate.mean()*100:.2f}%",
                    "PRISM-EB": f"{a.cost.mean():,.0f} / {a.violating_window_rate.mean()*100:.2f}%",
                    "max |cost diff| (USD)": f"{np.max(np.abs(a.cost.values - b.cost.values)):,.0f}",
                    "viol diff range (pp)": f"{np.min(a.violating_window_rate.values - b.violating_window_rate.values)*100:+.2f} … {np.max(a.violating_window_rate.values - b.violating_window_rate.values)*100:+.2f}"})
    write("E11_erlangb", pd.DataFrame(out), "PRISM vs PRISM-EB, both validation-tuned under the fast simulator")
    SUMMARY["E11_selected_eps"] = {int(s): sel11[s]["PRISM_EB"]["param"] for s in sel11}

# ---------------------------------------------------------------- figures
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    if len(e1):
        fig, ax = plt.subplots(figsize=(6, 4))
        for v, mk in zip(["Static", "Scheduled", "Reactive", "PredHead", "QuantProv_q90", "PRISM"], "osd^vx"):
            g = fr[fr.policy == v].sort_values("viol")
            ax.plot(g.viol * 100, g.cost, marker=mk, ms=3, lw=1, label=v)
        ax.axvline(2, ls=":", c="k", lw=0.8)
        ax.set_xlabel("Violating windows on validation week (%)")
        ax.set_ylabel("Weekly cost (USD, simulated)")
        ax.set_xlim(0, 12)
        ax.legend(fontsize=7)
        ax.set_title("Validation frontiers (mean of traces; synthetic)", fontsize=9)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(FIG, f"fig_validation_frontier.{ext}"))
        plt.close(fig)
        fig, axs = plt.subplots(1, 2, figsize=(9, 3.4))
        pols = MAIN[1:] + ["QuantProv_q90"]
        w = 0.8 / len(pols)
        for i, v in enumerate(pols):
            m = [tci(per[(sc, v)].cost) for sc in SCEN]
            vv = [tci(per[(sc, v)].violating_window_rate * 100) for sc in SCEN]
            x = np.arange(len(SCEN)) + i * w
            axs[0].bar(x, [a[0] for a in m], w, yerr=[a[1] for a in m], label=v, capsize=1)
            axs[1].bar(x, [a[0] for a in vv], w, yerr=[a[1] for a in vv], capsize=1)
        for a in axs:
            a.set_xticks(np.arange(len(SCEN)) + 0.4 - w / 2)
            a.set_xticklabels(SCEN, fontsize=8)
        axs[1].axhline(2, ls=":", c="k", lw=0.8)
        axs[0].set_ylabel("Weekly cost (USD)")
        axs[1].set_ylabel("Violating windows (%)")
        axs[0].legend(fontsize=6, ncol=2)
        fig.suptitle("Test weeks, validation-tuned (mean ± 95% t half-width over traces; synthetic)", fontsize=9)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(FIG, f"fig_test_weeks.{ext}"))
        plt.close(fig)
    if len(e2):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        x = np.arange(len(SCEN))
        for i, (k, lab) in enumerate([("cov90_raw", "q90 raw"), ("cov90_cal", "q90 + conformal"),
                                      ("cov99_raw", "q99 raw"), ("cov99_cal", "q99 + conformal")]):
            ax.bar(x + i * 0.2, [e2[e2.scenario == sc][k].mean() for sc in SCEN], 0.2, label=lab)
        ax.axhline(0.99, ls="--", c="k", lw=0.8)
        ax.axhline(0.90, ls=":", c="k", lw=0.8)
        ax.set_ylim(0.75, 1.0)
        ax.set_xticks(x + 0.3)
        ax.set_xticklabels(SCEN)
        ax.set_ylabel("Empirical coverage (test week)")
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(FIG, f"fig_coverage.{ext}"))
        plt.close(fig)
    if len(e9):
        fig, ax = plt.subplots(figsize=(4.5, 4))
        for v, mk in zip(MAIN, "osd^vx"):
            g = e9[e9.policy == v]
            ax.scatter(g.fast_violating_window_rate * 100, g.event_violating_window_rate * 100, marker=mk, s=14, label=v)
        lim = max(1, e9.event_violating_window_rate.max() * 100 * 1.05)
        ax.plot([0, lim], [0, lim], "k:", lw=0.8)
        ax.set_xlabel("Violating windows, fast simulator (%)")
        ax.set_ylabel("Violating windows, event-level (%)")
        ax.set_xscale("symlog", linthresh=1)
        ax.set_yscale("symlog", linthresh=1)
        ax.legend(fontsize=7)
        ax.set_title("Same frozen schedules, two simulators", fontsize=9)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(FIG, f"fig_fast_vs_event.{ext}"))
        plt.close(fig)
except Exception as exc:  # figures are optional; record the failure
    STATUS["figures"] = f"failed: {exc}"

SUMMARY["status"] = STATUS
with open(os.path.join(ROOT, "results", "summary.json"), "w") as f:
    json.dump(SUMMARY, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps(STATUS, indent=1))
