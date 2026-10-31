#!/usr/bin/env python3
"""Publication figures for the PRISM V2 manuscript. Every value is read from the stored raw
results of the released implementation (prism-repro); nothing is typed in by hand.
Usage: python make_figs.py <repo_root> <out_dir>"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif", "TeX Gyre Termes", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 600,
    "axes.edgecolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b",
})
INK2 = "#52514e"
GRID = "#e4e3df"
# One fixed colour (and hatch, for grayscale print) per policy family, used in every figure.
STYLE = {
    "PRISM": ("#2a78d6", "", "o"),
    "PredHead": ("#eb6834", "////", "s"),
    "PredHead+hyst": ("#1baf7a", "\\\\\\\\", "D"),
    "QuantProv_q90": ("#eda100", "....", "^"),
    "QuantProv_q99": ("#e87ba4", "xxxx", "v"),
    "Static": ("#008300", "----", "P"),
    "Reactive": ("#6250d6", "||||", "X"),
    "Scheduled": ("#e34948", "++++", "*"),
    "OnDemand": ("#8a8984", "", "."),
}
NAME = {"PRISM": "PRISM", "PredHead": "PredHead", "PredHead+hyst": "PredHead+S",
        "QuantProv_q90": "QuantProv-q90", "QuantProv_q99": "QuantProv-q99", "Static": "Static",
        "Reactive": "Reactive", "Scheduled": "Scheduled", "OnDemand": "On-demand"}
SC = ["stationary", "growth", "bursty", "new_spike"]
SCN = {"stationary": "Stationary", "growth": "Growth", "bursty": "Bursty", "new_spike": "New spike"}


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(os.path.join(OUT, name + ".png"), bbox_inches="tight", pad_inches=0.02, dpi=600)
    fig.savefig(os.path.join(OUT, name + ".tif"), bbox_inches="tight", pad_inches=0.02, dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def rows(e):
    df = pd.DataFrame([json.loads(l) for l in open(os.path.join(ROOT, "results", "raw", e, "rows.jsonl"))])
    if "run_id" in df:
        df = df.drop_duplicates("run_id", keep="last")
    return df


def hw(x):
    x = np.asarray(x, float)
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def style_ax(ax):
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- Fig. 3 calibration
def fig_calibration():
    e2 = rows("E2")
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.16, 2.35), gridspec_kw=dict(width_ratios=[1.15, 1]))
    x = np.arange(4)
    series = [("cov90_raw", "q90 raw", "#eda100", "...."), ("cov90_cal", "q90 recalibrated", "#eb6834", ""),
              ("cov99_raw", "q99 raw", "#8fbbea", "////"), ("cov99_cal", "q99 recalibrated", "#2a78d6", "")]
    w = 0.2
    for i, (k, lab, c, h) in enumerate(series):
        m = [e2[e2.scenario == s][k].mean() for s in SC]
        e = [hw(e2[e2.scenario == s][k]) for s in SC]
        a.bar(x + (i - 1.5) * w, m, w * 0.9, yerr=e, color=c, hatch=h, edgecolor="white", lw=0.3,
              error_kw=dict(lw=0.6, capsize=1.5, ecolor=INK2), label=lab)
    a.axhline(0.99, ls="--", lw=0.6, color=INK2)
    a.axhline(0.90, ls=":", lw=0.7, color=INK2)
    a.set_ylim(0.78, 1.0)
    a.set_xticks(x, [SCN[s] for s in SC])
    a.set_ylabel("Empirical coverage (test week)")
    a.set_title("(a) Coverage of upper quantiles, mean ± 95% CI (5 traces)", loc="left", pad=20)
    a.legend(ncol=4, frameon=False, loc="lower left", bbox_to_anchor=(0.0, 1.0), handlelength=1.2,
             columnspacing=0.8, borderaxespad=0)
    style_ax(a)
    arr = np.load(os.path.join(ROOT, "results", "raw", "E2", "arrays_seed101.npz"))
    y, s, q = arr["101|growth|gbm::y"], arr["101|growth|gbm::s"], arr["101|growth|gbm::q_raw"]
    raw = (y <= q[:, 3]).astype(float)
    cal = (y <= q[:, 3] * np.exp(s)).astype(float)
    k = 288  # one day of 5-min epochs
    rr = pd.Series(raw).rolling(k).mean()
    rc = pd.Series(cal).rolling(k).mean()
    days = np.arange(len(y)) / 288.0
    b.plot(days, rr, color="#8fbbea", lw=1.0, label="q99 raw")
    b.plot(days, rc, color="#2a78d6", lw=1.2, label="q99 recalibrated")
    b.axhline(0.99, ls="--", lw=0.6, color=INK2)
    b.axvspan(0, 3, color="#f1f0ec", lw=0)
    b.text(2.0, 0.943, "level ramps to +40%", ha="center", fontsize=6.5, color=INK2)
    b.set_xlim(1, 7)
    b.set_ylim(0.94, 1.0)
    b.set_xlabel("Day of test week (growth scenario, trace 101)")
    b.set_ylabel("Rolling one-day coverage")
    b.set_title("(b) Coverage over time under growth", loc="left", pad=20)
    b.legend(frameon=False, loc="lower right")
    style_ax(b)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig3_calibration")


# ---------------------------------------------------------------- Fig. 4 validation frontier
def fig_validation_frontier():
    f = pd.read_csv(os.path.join(ROOT, "results", "tables", "F3_validation_frontier.csv"))
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    order = ["Static", "Reactive", "Scheduled", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]
    for p in order:
        g = f[f.policy == p].sort_values("viol")
        c, _, mk = STYLE[p]
        ax.plot(g.viol * 100, g.cost, color=c, lw=1.1 if p != "PRISM" else 1.6, marker=mk, ms=3.2,
                label=NAME[p], zorder=3 if p == "PRISM" else 2)
    ax.axvline(2.0, ls=":", lw=0.8, color=INK2)
    ax.text(2.07, 1560, "2% selection threshold", fontsize=6.3, color=INK2, va="bottom")
    ax.set_xlim(0, 6)
    ax.set_ylim(800, 2100)
    ax.set_xlabel("Violating windows, validation week (%)")
    ax.set_ylabel("Weekly cost (USD, simulated)")
    ax.legend(frameon=False, fontsize=6.2, ncol=2, loc="upper right", handlelength=1.6, columnspacing=0.7)
    style_ax(ax)
    ax.grid(axis="x", color=GRID, lw=0.5)
    fig.tight_layout()
    save(fig, "fig4_validation_frontier")


# ---------------------------------------------------------------- Fig. 5 test weeks
def selected_test():
    e1 = rows("E1")
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from prism_repro.experiment import select_by_rule
    val, test = e1[e1.week == "val"], e1[e1.week == "test"]
    out = []
    for (seed, pol), g in val.groupby(["seed", "policy"]):
        sel = select_by_rule(g.to_dict("records"))
        t = test[(test.seed == seed) & (test.label == sel["label"])]
        out.append(t)
    return pd.concat(out), e1


def fig_test_weeks(sel):
    pols = ["Static", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.5))
    x = np.arange(4)
    w = 0.86 / len(pols)
    for j, (key, lab, scale) in enumerate([("cost", "Weekly cost (USD, simulated)", 1.0),
                                           ("violating_window_rate", "Violating windows (%)", 100.0)]):
        ax = axes[j]
        for i, p in enumerate(pols):
            c, h, _ = STYLE[p]
            m = [sel[(sel.policy == p) & (sel.scenario == s)][key].mean() * scale for s in SC]
            e = [hw(sel[(sel.policy == p) & (sel.scenario == s)][key] * scale) for s in SC]
            ax.bar(x + (i - (len(pols) - 1) / 2) * w, m, w * 0.92, yerr=e, color=c, hatch=h,
                   edgecolor="white", lw=0.3, error_kw=dict(lw=0.5, capsize=1.2, ecolor=INK2), label=NAME[p])
        ax.set_xticks(x, [SCN[s] for s in SC])
        ax.set_ylabel(lab)
        style_ax(ax)
    axes[1].axhline(2.0, ls=":", lw=0.8, color=INK2)
    axes[0].set_ylim(0, 2100)
    axes[0].set_title("(a) Cost", loc="left")
    axes[1].set_title("(b) Violating 15-min windows (dotted: 2% target)", loc="left")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.07),
               handlelength=1.4, columnspacing=1.0)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig5_test_weeks")


# ---------------------------------------------------------------- Fig. 6 matched compliance
def envelope(g):
    g = g.sort_values(["viol", "cost"])
    keep, best = [], np.inf
    for _, r in g.iterrows():
        if r.cost < best - 1e-9:
            keep.append((r.viol, r.cost))
            best = r.cost
    return np.array(keep)


def fig_matched(e1):
    test = e1[e1.week == "test"]
    fams = ["Static", "Reactive", "PredHead", "PredHead+hyst", "QuantProv_q90", "QuantProv_q99", "PRISM"]
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.7))
    for ax, (title, df) in zip(axes, [("(a) Pooled over all 20 test weeks", test),
                                      ("(b) New-spike test weeks (5 traces)", test[test.scenario == "new_spike"])]):
        for p in fams:
            g = df[df.policy == p].groupby("param").agg(cost=("cost", "mean"),
                                                        viol=("violating_window_rate", "mean")).reset_index()
            g["viol"] *= 100
            env = envelope(g)
            c, _, mk = STYLE[p]
            ax.scatter(g.viol, g.cost, s=6, color=c, alpha=0.35, lw=0, zorder=1)
            ax.plot(env[:, 0], env[:, 1], color=c, lw=1.1 if p != "PRISM" else 1.7, marker=mk, ms=3,
                    label=NAME[p], zorder=3 if p == "PRISM" else 2)
        for t in (1.0, 1.5, 2.0):
            ax.axvline(t, ls=":", lw=0.6, color=INK2)
        ax.set_xlim(0, 4.0)
        ax.set_ylim(900, 2100)
        ax.set_xlabel("Mean violating windows (%)")
        ax.set_title(title, loc="left")
        style_ax(ax)
        ax.grid(axis="x", color=GRID, lw=0.5)
    axes[0].set_ylabel("Mean weekly cost (USD, simulated)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.07),
               handlelength=1.6, columnspacing=1.0)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig6_matched_compliance")


# ---------------------------------------------------------------- Fig. 7 fast vs event level
def fig_fidelity():
    e9 = rows("E9")
    pols = ["OnDemand", "Static", "Scheduled", "Reactive", "PredHead", "PRISM"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.16, 2.4), gridspec_kw=dict(width_ratios=[1.25, 1]))
    x = np.arange(len(pols))
    fast = [e9[e9.policy == p].fast_violating_window_rate.mean() * 100 for p in pols]
    ev = [e9[e9.policy == p].event_violating_window_rate.mean() * 100 for p in pols]
    a.bar(x - 0.19, fast, 0.36, color="#8fbbea", hatch="////", edgecolor="white", lw=0.3, label="Fast simulator")
    a.bar(x + 0.19, ev, 0.36, color="#2a78d6", edgecolor="white", lw=0.3, label="Event-level simulator")
    for i in range(len(pols)):
        a.text(x[i] + 0.19, ev[i] + 0.6, f"×{ev[i] / fast[i]:.1f}", ha="center", fontsize=6.3, color=INK2)
    a.set_xticks(x, [NAME[p] for p in pols])
    a.set_yscale("log")
    a.set_ylim(0.8, 80)
    a.set_yticks([1, 2, 5, 10, 20, 50], ["1", "2", "5", "10", "20", "50"])
    a.axhline(2.0, ls=":", lw=0.8, color=INK2)
    a.set_ylabel("Violating windows (%, log scale)")
    a.set_title("(a) Same frozen schedules, 12 test weeks per policy", loc="left")
    a.legend(frameon=False, loc="upper right")
    style_ax(a)
    d = []
    for s in SC:
        g = e9[e9.scenario == s]
        def m(p, col):
            return g[g.policy == p][col].mean() * 100
        d.append((m("PRISM", "fast_violating_window_rate") - m("PredHead", "fast_violating_window_rate"),
                  m("PRISM", "event_violating_window_rate") - m("PredHead", "event_violating_window_rate")))
    d = np.array(d)
    xx = np.arange(4)
    b.bar(xx - 0.19, d[:, 0], 0.36, color="#8fbbea", hatch="////", edgecolor="white", lw=0.3, label="Fast")
    b.bar(xx + 0.19, d[:, 1], 0.36, color="#2a78d6", edgecolor="white", lw=0.3, label="Event-level")
    b.axhline(0, color=INK2, lw=0.6)
    b.set_xticks(xx, [SCN[s] for s in SC])
    b.set_ylabel("PRISM − PredHead (pp)")
    b.set_title("(b) Difference in violating windows", loc="left")
    b.legend(frameon=False, loc="lower left")
    style_ax(b)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig7_fidelity")


if __name__ == "__main__":
    fig_calibration()
    fig_validation_frontier()
    sel, e1 = selected_test()
    fig_test_weeks(sel)
    fig_matched(e1)
    fig_fidelity()
    print("ok")
