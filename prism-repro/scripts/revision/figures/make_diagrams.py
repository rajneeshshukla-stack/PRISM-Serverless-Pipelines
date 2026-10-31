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


def box(ax, x, y, w, h, title, lines, kind, fs=6.4, tfs=7.2, top=0.07, gap=0.25, ls=1.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.06",
                                fc=FILL[kind], ec=EDGE[kind], lw=0.9))
    t1 = ax.text(x + w / 2, y + h - top, title, ha="center", va="top", fontsize=tfs, weight="bold", color=INK)
    t2 = ax.text(x + w / 2, y + h - gap, "\n".join(lines), ha="center", va="top", fontsize=fs, color=INK2,
                 linespacing=ls)
    return (x, y, w, h), (t1, t2)


def arrow(ax, p, q, label=None, lpos=(0, 0), dashed=False, rad=0.0, ha="center", lfs=6.1, ms=7, lw=0.8):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms, lw=lw, color=INK2,
                                 connectionstyle=f"arc3,rad={rad}", ls=(0, (3, 2)) if dashed else "-",
                                 shrinkA=0, shrinkB=0))
    if label:
        return ax.text((p[0] + q[0]) / 2 + lpos[0], (p[1] + q[1]) / 2 + lpos[1], label, ha=ha, va="bottom",
                       fontsize=lfs, color=INK2, style="italic")
    return None


def fig_architecture():
    # V13-V2 (review SET-2, comment 3): the same boxes, texts, arrows, and directions as V13, laid out for printing
    # at the full text width (177.5 mm = 6.99 in, scale about 1:1), so that box titles print at 9 pt and every
    # explanatory label at 8 pt (V13: 7.16-in canvas printed at 78% width, about 4.6-5.4 pt). The one-line legend
    # (solid arrows: decision path every 5 min; dashed: online learning from telemetry) moved to the caption.
    CW, CH = 6.93, 2.51  # with the 0.03-in save padding the PNG is 6.99 in wide, i.e. printed at 1:1
    fig, ax = canvas(CW, CH)
    W, H = 1.585, 0.66
    W3, H3 = 2.24, 0.52  # bottom row: wider boxes, two-line texts (same wording as V13)
    X = [0.005, 1.7805, 3.556, 5.34]
    Y3 = 0.005
    Y2 = Y3 + H3 + 0.20
    Y1 = Y2 + H + 0.20
    TFS, FS, LFS = 9.0, 8.0, 8.0
    kw = dict(fs=FS, tfs=TFS, top=0.055, gap=0.215, ls=1.22)
    paths = []

    def A(p, q, label=None, lpos=(0, 0), dashed=False, rad=0.0, ha="center"):
        paths.append((p, q, rad))
        return arrow(ax, p, q, label, lpos, dashed, rad, ha, lfs=LFS, ms=9, lw=0.9)

    boxes = []
    boxes.append(box(ax, X[0], Y1, W, H, "Telemetry", ["arrivals per minute,", "overflow and cold-start", "counters, provisioned level"], "data", **kw))
    boxes.append(box(ax, X[1], Y1, W, H, "Feature builder", ["lags, rolling max and s.d.,", "previous-day window, time", "of day, trigger flag"], "data", **kw))
    boxes.append(box(ax, X[2], Y1, W, H, "Quantile forecaster", ["gradient boosting (pinball", r"loss): $q_{0.1}, q_{0.5}, q_{0.9}, q_{0.99}$",
                                                                 r"of the window peak $Y_t$ (12)"], "learn", **kw))
    boxes.append(box(ax, X[3], Y1, W, H, "Online recalibration", [r"adaptive-conformal offset $s_k$", r"on $q_{0.9}, q_{0.99}$ (13);",
                                                                  "reorder by cumulative max"], "learn", **kw))
    boxes.append(box(ax, X[3], Y2, W, H, "Scenario generator", ["monotone quantile function,", "exponential upper tail,",
                                                                "100 stratified demand levels"], "learn", **kw))
    boxes.append(box(ax, X[2], Y2, W, H, "Optimizer", [r"chance-constrained: min $E[C]$", r"s.t. $\Pr[v \leq \varepsilon] \geq 1-\delta$ (11);",
                                                       "21 levels × 4 memory sizes"], "opt", **kw))
    boxes.append(box(ax, X[1], Y2, W, H, "Actuation", [r"scale-in floor $\lfloor 0.85\,P_{\mathrm{prev}} \rfloor$;", "memory changed hourly;",
                                                       "active after 2-min lag"], "opt", **kw))
    boxes.append(box(ax, X[0], Y2, W, H, "Serverless pipeline", ["ingest → transform →", "aggregate → load", "(provisioned / on-demand)"], "sys", **kw))
    B3 = [0.005, 2.3475, 4.69]  # bottom row spans the width; each box feeds the optimizer above, as in V13
    boxes.append(box(ax, B3[0], Y3, W3, H3, "Operator inputs", [r"deadline $D$, SLA window, risk budget $(\varepsilon, \delta)$,", "prices, platform caps"], "sys", **kw))
    boxes.append(box(ax, B3[1], Y3, W3, H3, "Cost model (8)–(9)", ["PC fee, discounted and on-demand duration,", "billed INIT, requests"], "model", **kw))
    boxes.append(box(ax, B3[2], Y3, W3, H3, "Risk model (4)–(7)", [r"per-stage overflow, cold-hit probability $\kappa$", r"(from telemetry), record miss probability $v$"], "model", **kw))
    m1, m2 = Y1 + H / 2, Y2 + H / 2
    for i in range(3):
        A((X[i] + W, m1), (X[i + 1], m1))
    A((X[3] + W / 2, Y1), (X[3] + W / 2, Y2 + H))
    A((X[3], m2), (X[2] + W, m2))
    A((X[2], m2), (X[1] + W, m2))
    A((X[1], m2), (X[0] + W, m2))
    labels = [A((X[0] + W / 2, Y2 + H), (X[0] + W / 2, Y1), "metrics", (0.07, -0.06), ha="left")]
    A((B3[0] + W3 - 0.30, Y3 + H3), (X[2] + 0.12, Y2))
    A((B3[1] + W3 / 2 + 0.25, Y3 + H3), (X[2] + W / 2, Y2))
    A((B3[2] + 0.40, Y3 + H3), (X[2] + W - 0.15, Y2))
    rad, p0, p1 = -0.04, (X[0] + 0.25, Y1 + H), (X[3] + 0.8, Y1 + H)
    apex = -rad * (p1[0] - p0[0]) / 2  # height of the quadratic arc above its chord
    labels.append(A(p0, p1, "realized window peaks, 2-epoch delay (calibration feedback)", (0, apex + 0.03),
                    dashed=True, rad=rad))
    check_layout(fig, ax, boxes, [lb for lb in labels if lb is not None], paths, CW, CH)
    save(fig, "fig1_architecture")


def _arc_points(p, q, rad, n=200):
    """Points on matplotlib's arc3 connection (quadratic Bezier; control point as in ConnectionStyle.Arc3)."""
    (x1, y1), (x2, y2) = p, q
    cx, cy = (x1 + x2) / 2 + rad * (y2 - y1), (y1 + y2) / 2 - rad * (x2 - x1)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(((1 - t) ** 2 * x1 + 2 * t * (1 - t) * cx + t ** 2 * x2,
                    (1 - t) ** 2 * y1 + 2 * t * (1 - t) * cy + t ** 2 * y2))
    return pts


def check_layout(fig, ax, boxes, labels, paths, cw, ch, pad=0.03):
    """Fail loudly if any box text leaves its box, if texts overlap, if an arrow crosses a box or a label,
    or if anything leaves the canvas."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    def ext(t):
        bb = t.get_window_extent(renderer=r)
        (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        return x0, y0, x1, y1

    texts = []
    for (x, y, w, h), ts in boxes:
        for t in ts:
            x0, y0, x1, y1 = ext(t)
            assert x0 >= x + pad and x1 <= x + w - pad and y0 >= y + 0.02 and y1 <= y + h - 0.02, \
                f"text '{t.get_text()[:30]}' leaves its box: {(x0, y0, x1, y1)} vs {(x, y, w, h)}"
            texts.append((x0, y0, x1, y1, t.get_text()[:20]))
    for t in labels:
        x0, y0, x1, y1 = ext(t)
        assert 0 <= x0 and x1 <= cw and 0 <= y0 and y1 <= ch, f"label '{t.get_text()[:30]}' leaves the canvas"
        for (x, y, w, h), _ in boxes:
            assert x1 <= x or x0 >= x + w or y1 <= y or y0 >= y + h, f"label '{t.get_text()[:30]}' overlaps a box"
        texts.append((x0, y0, x1, y1, t.get_text()[:20]))
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], f"texts overlap: {a[4]} / {b[4]}"
    eps = 0.015
    for p, q, rad in paths:
        pts = _arc_points(p, q, rad)
        inner = [(x, y) for x, y in pts if min(abs(x - p[0]) + abs(y - p[1]), abs(x - q[0]) + abs(y - q[1])) > 0.03]
        for x, y in inner:
            assert 0 <= x <= cw and 0 <= y <= ch, f"arrow {p}->{q} leaves the canvas"
            for (bx, by, bw, bh), _ in boxes:
                assert not (bx + eps < x < bx + bw - eps and by + eps < y < by + bh - eps), \
                    f"arrow {p}->{q} crosses box at {(round(x, 3), round(y, 3))}"
            for x0, y0, x1, y1, name in texts:
                assert not (x0 - eps < x < x1 + eps and y0 - eps < y < y1 + eps), \
                    f"arrow {p}->{q} crosses text '{name}' at {(round(x, 3), round(y, 3))}"
    print(f"layout check passed: {len(texts)} text blocks inside their boxes, no text overlaps, "
          f"{len(paths)} arrows clear of boxes and texts")


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
