#!/usr/bin/env python3
"""Architecture (Fig. 1) and evaluation-protocol (Fig. 2) diagrams, laid out in inches.
Usage: python make_diagrams.py <out_dir>"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Liberation Serif", "DejaVu Serif"],
                     "mathtext.fontset": "stix", "font.size": 7, "pdf.fonttype": 42})
INK, INK2 = "#0b0b0b", "#52514e"
FILL = {"data": "#eef4fc", "learn": "#e6f5ee", "opt": "#fdf0e9", "model": "#f3effb", "sys": "#f5f4f0"}
EDGE = {"data": "#2a78d6", "learn": "#1baf7a", "opt": "#eb6834", "model": "#6250d6", "sys": "#8a8984"}


def save(fig, name):
    for ext, kw in (("pdf", {}), ("png", {"dpi": 600}),
                    ("tif", {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}})):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), bbox_inches="tight", pad_inches=0.03, **kw)
    plt.close(fig)


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, lines, kind, fs=6.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.06",
                                fc=FILL[kind], ec=EDGE[kind], lw=0.9))
    ax.text(x + w / 2, y + h - 0.07, title, ha="center", va="top", fontsize=7.2, weight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.25, "\n".join(lines), ha="center", va="top", fontsize=fs, color=INK2,
            linespacing=1.3)


def arrow(ax, p, q, label=None, lpos=(0, 0), dashed=False, rad=0.0, ha="center"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, lw=0.8, color=INK2,
                                 connectionstyle=f"arc3,rad={rad}", ls=(0, (3, 2)) if dashed else "-",
                                 shrinkA=0, shrinkB=0))
    if label:
        ax.text((p[0] + q[0]) / 2 + lpos[0], (p[1] + q[1]) / 2 + lpos[1], label, ha=ha, va="bottom",
                fontsize=6.1, color=INK2, style="italic")


def fig_architecture():
    fig, ax = canvas(7.16, 3.75)
    W, H = 1.62, 0.74
    X = [0.04, 1.84, 3.64, 5.44]
    Y1, Y2, Y3 = 2.70, 1.50, 0.22
    box(ax, X[0], Y1, W, H, "Telemetry", ["arrivals per minute,", "overflow and cold-start", "counters, provisioned level"], "data")
    box(ax, X[1], Y1, W, H, "Feature builder", ["lags, rolling max and s.d.,", "previous-day window, time", "of day, trigger flag"], "data")
    box(ax, X[2], Y1, W, H, "Quantile forecaster", ["gradient boosting (pinball", r"loss): $q_{0.1}, q_{0.5}, q_{0.9}, q_{0.99}$",
                                                    r"of the window peak $Y_t$ (12)"], "learn")
    box(ax, X[3], Y1, W, H, "Online recalibration", [r"adaptive-conformal offset $s_k$", r"on $q_{0.9}, q_{0.99}$ (13);",
                                                     "reorder by cumulative max"], "learn")
    box(ax, X[3], Y2, W, H, "Scenario generator", ["monotone quantile function,", "exponential upper tail,",
                                                   "100 stratified demand levels"], "learn")
    box(ax, X[2], Y2, W, H, "Optimizer", [r"chance-constrained: min $E[C]$", r"s.t. $\Pr[v \leq \varepsilon] \geq 1-\delta$ (11);",
                                                   "21 levels × 4 memory sizes"], "opt")
    box(ax, X[1], Y2, W, H, "Actuation", [r"scale-in floor $\lfloor 0.85\,P_{\mathrm{prev}} \rfloor$;", "memory changed hourly;",
                                          "active after 2-min lag"], "opt")
    box(ax, X[0], Y2, W, H, "Serverless pipeline", ["ingest → transform →", "aggregate → load", "(provisioned / on-demand)"], "sys")
    box(ax, 0.94, Y3, W, H, "Operator inputs", [r"deadline $D$, SLA window,", r"risk budget $(\varepsilon, \delta)$,", "prices, platform caps"], "sys")
    box(ax, 2.74, Y3, W, H, "Cost model (8)–(9)", ["PC fee, discounted and", "on-demand duration,", "billed INIT, requests"], "model")
    box(ax, 4.54, Y3, W, H, "Risk model (4)–(7)", ["per-stage overflow, cold-hit", r"probability $\kappa$ (from telemetry),", r"record miss probability $v$"], "model")
    m1, m2 = Y1 + H / 2, Y2 + H / 2
    for i in range(3):
        arrow(ax, (X[i] + W, m1), (X[i + 1], m1))
    arrow(ax, (X[3] + W / 2, Y1), (X[3] + W / 2, Y2 + H))
    arrow(ax, (X[3], m2), (X[2] + W, m2))
    arrow(ax, (X[2], m2), (X[1] + W, m2))
    arrow(ax, (X[1], m2), (X[0] + W, m2))
    arrow(ax, (X[0] + W / 2, Y2 + H), (X[0] + W / 2, Y1), "metrics", (0.06, -0.05), ha="left")
    arrow(ax, (0.94 + W, Y3 + H - 0.1), (X[2] + 0.12, Y2))
    arrow(ax, (2.74 + W / 2 + 0.3, Y3 + H), (X[2] + W / 2, Y2))
    arrow(ax, (4.54 + W / 2 - 0.3, Y3 + H), (X[2] + W - 0.15, Y2))
    arrow(ax, (X[0] + 0.25, Y1 + H), (X[3] + 0.8, Y1 + H), "realised window peaks, 2-epoch delay (calibration feedback)",
          (0, 0.17), dashed=True, rad=-0.13)
    ax.text(0.04, 0.02, "Solid arrows: decision path, executed every 5 min. Dashed: online learning from telemetry.",
            fontsize=6.1, color=INK2, va="bottom")
    save(fig, "fig1_architecture")


def fig_protocol():
    fig, ax = canvas(7.16, 2.55)
    x0, x1 = 0.10, 7.06
    sc = (x1 - x0) / 28
    y0, h = 1.88, 0.40
    segs = [(0, 14, "Training (days 1–14): forecaster fitted once, then frozen", "#eef4fc", "#2a78d6"),
            (14, 21, "Validation (days 15–21):\nevery family tuned", "#e6f5ee", "#1baf7a"),
            (21, 28, "Test (days 22–28):\nnever used for tuning", "#fdf0e9", "#eb6834")]
    for a, b, lab, fc, ec in segs:
        ax.add_patch(Rectangle((x0 + a * sc, y0), (b - a) * sc, h, fc=fc, ec=ec, lw=0.9))
        ax.text(x0 + (a + b) / 2 * sc, y0 + h / 2, lab, ha="center", va="center", fontsize=6.6, color=INK)
    for d in (0, 7, 14, 21, 28):
        ax.plot([x0 + d * sc] * 2, [y0 - 0.04, y0], color=INK2, lw=0.6)
        ax.text(x0 + d * sc, y0 - 0.06, f"day {d}", ha="center", va="top", fontsize=5.8, color=INK2)
    ax.text(x0, 2.45, "Five synthetic four-week traces (seeds 101–105). Days 1–21 are identical in every scenario of a trace.",
            fontsize=6.8, color=INK, va="center")
    ax.text(x0, 1.58, "Test-week variants: stationary · growth (level +40% over 3 days) · bursty (2× random bursts) · "
            "new spike (+150% at :15 and :16, +20% level) · shifted triggers (feature ablation only)",
            fontsize=6.3, color=INK2, va="center", ha="left")
    ax.text(x0, 1.36, "Families (one tuning parameter each): On-demand, Static-p, Scheduled-h, Reactive-u, PredHead-h, "
            "PredHead+S-h, QuantProv-a (q90, q99), PRISM-ε (δ = 0.1)", fontsize=6.4, color=INK, va="center")
    steps = [("1  Tune on validation", ["cheapest configuration with", "≤ 2% violating windows,", "else the least violating"]),
             ("2  Freeze and test", ["frozen parameters, every", "test scenario, fast simulator;", "paired over 5 traces"]),
             ("3  Simulator fidelity", ["replay frozen schedules in the", "event-level simulator, then", "re-tune every family under it"]),
             ("4  Matched compliance", ["post hoc: interpolate each", "family's cost–violation", "frontier at 1.0/1.5/2.0%"])]
    bw, gap, bh = 1.62, 0.153, 0.95
    for i, (ti, lines) in enumerate(steps):
        bx = x0 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((bx, 0.12), bw, bh, boxstyle="round,pad=0.0,rounding_size=0.06",
                                    fc="#f5f4f0", ec="#8a8984", lw=0.8))
        ax.text(bx + 0.08, 0.12 + bh - 0.09, ti, fontsize=7.2, weight="bold", va="top", color=INK)
        ax.text(bx + 0.08, 0.12 + bh - 0.30, "\n".join(lines), fontsize=6.5, va="top", color=INK2, linespacing=1.35)
        if i < 3:
            arrow(ax, (bx + bw, 0.12 + bh / 2), (bx + bw + gap, 0.12 + bh / 2))
    save(fig, "fig2_protocol")


if __name__ == "__main__":
    fig_architecture()
    fig_protocol()
    print("ok")
