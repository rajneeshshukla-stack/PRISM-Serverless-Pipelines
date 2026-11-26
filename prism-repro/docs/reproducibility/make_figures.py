"""Regenerate the revision figures from files committed in this repository (no simulation, no network).

- FR1 (planned Fig. S6): prespecified C1-C3 paired differences, from confirmatory_20261122/run/tables/.
- FR2 (planned Fig. S7): calibrated development runs, from calibrated_build_20261125/p3_results.json.
- REGEN-WIN paper figures (Fig. 2 and Figs. S2-S5), drawn by the unchanged scripts/revision/figures/make_figs.py on a
  temporary tree made of src/ and the published rows in docs/reproducibility/figure_inputs_regen_win/.

usage (from prism-repro/):  python docs/reproducibility/make_figures.py OUT_DIR      (OUT_DIR must not exist)

PNG and TIFF outputs are compared with the reference hashes below, which were produced on Windows 11 with the pinned
packages (docs/revision/label_fix_20261123/env/windows_venv_freeze.txt). The fonts fall back to DejaVu Serif when
Liberation Serif and TeX Gyre Termes are absent, so another font set changes the pixels but not the plotted values;
the table views are TR1, TR2 and the REGEN-WIN tables. PDFs embed their creation time and are not compared.
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PR = os.path.normpath(os.path.join(HERE, "..", ".."))          # prism-repro/
REV = os.path.join(PR, "docs", "revision")
OUT = os.path.abspath(sys.argv[1])
os.makedirs(OUT)
REFERENCE = {
    "FR1_confirmatory_C1_C3.png": "61bb22ee263440152cdb611dea4bfcb2a7a87b00c55d026754e62cc66b309100",
    "FR2_calibrated_development.png": "3a4a227263b6b3ca36b762838f202f99bfde5ceaca06e440b6a6b40636752df9",
    "regen_win/fig3_calibration.png": "cd8412dc6011f67711fabed01227c3306dd7729f2ed56077e9312bcd5bec3529",
    "regen_win/fig4_validation_frontier.png": "53e9691737736c80ae8bbe80175c51e488403d6b6c86e3fc7cc6e2bb828404c2",
    "regen_win/fig5_test_weeks.png": "3fd1d738fc0a8e356e102c041375845dbc5cdb347bb9b2f96bb34cd253917d3e",
    "regen_win/fig6_matched_compliance.png": "15172377caa37032a6670aa7a7380f81791845c7ad1c00336d69dc5e2d11adb9",
    "regen_win/fig7_fidelity.png": "a1e4ed1f41dd834a8d5e1e90b46189e796474d8ab68050b51408eba9ba90f53f",
    "regen_win/fig3_calibration.tif": "569a126e2262d5f2c353810580606531f42e212c53cb0e94bdc8f0d284499c4c",
    "regen_win/fig4_validation_frontier.tif": "c0cf2b5a405862070cad6fbb9b3785f8dbbe131d7b80b490c9e716e2b12b2859",
    "regen_win/fig5_test_weeks.tif": "28701c1113c00097d29af18ce882f8bd779683605de87993f881423b7ac0916f",
    "regen_win/fig6_matched_compliance.tif": "cae64f380cae6ffb5b107500b4cb9e3b200e6f77818855b229fac34ac2da1009",
    "regen_win/fig7_fidelity.tif": "932578e37c41bf876888b5f6ab9455e519d9223ab8cb6289e563de59a2e07950",
}
INK, INK2, GRID, SURF, BAND = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff", "#f0efec"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"     # paper family colours (make_figs STYLE)
PAPER = {"font.family": "serif", "font.serif": ["Liberation Serif", "TeX Gyre Termes", "DejaVu Serif"], "mathtext.fontset": "stix",
         "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
         "legend.fontsize": 7, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
         "pdf.fonttype": 42, "axes.edgecolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK,
         "text.color": INK}


def save(fig, folder, name, dpi=600):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(folder, f"{name}.{ext}"), dpi=dpi, bbox_inches="tight", pad_inches=0.03, facecolor=fig.get_facecolor())
    plt.close(fig)


# ============================================================== FR1: C1-C3 paired differences (forest plot)
plt.rcParams.update(PAPER)
rows = []
for f in ("C1C2_paired.csv", "C3_paired.csv"):
    for r in csv.DictReader(open(os.path.join(REV, "confirmatory_20261122", "run", "tables", f), encoding="utf-8")):
        if "EXPLORATORY" not in r["comparison"]:
            rows.append(r)
lab = {"C1": "C1  vs QuantProv-q90 (14.5 s)", "C2": "C2  vs Reactive (14.5 s)", "C3": "C3  vs MemAdapt-q90 (12 s)"}
rows.sort(key=lambda r: r["comparison"])
assert [r["comparison"] for r in rows] == ["C1", "C2", "C3"]
assert abs(float(rows[0]["cost_pct_hi"]) - 2.011) < 1e-3 and abs(float(rows[2]["cost_pct_mean"]) - 13.063) < 1e-3
fig, axes = plt.subplots(1, 2, figsize=(7.16, 1.85), gridspec_kw=dict(width_ratios=[1.15, 1]), facecolor=SURF)
y = [2, 1, 0]
spec = [("cost_pct", "PRISM minus comparator, weekly cost (%)", 2.0, "tie margin +/-2%", "{:+.2f}%"),
        ("violating_pts", "PRISM minus comparator, violating windows (points)", 0.5, "similar compliance +/-0.5 pt", "{:+.2f}")]
for ax, (key, xl, band, bandlab, fmt) in zip(axes, spec):
    ax.axvspan(-band, band, color=BAND, zorder=0, lw=0)
    ax.axvline(0, color=INK2, lw=0.6, zorder=1)
    for yy, r in zip(y, rows):
        m, lo, hi = float(r[key + "_mean"]), float(r[key + "_lo"]), float(r[key + "_hi"])
        ax.plot([lo, hi], [yy, yy], color=BLUE, lw=1.4, solid_capstyle="round", zorder=2)
        ax.plot([m], [yy], "o", ms=4.6, color=BLUE, mec=SURF, mew=0.8, zorder=3)
        txt = (f"{m:+.2f}% [{lo:+.2f}, {hi:+.2f}]" if key == "cost_pct" else f"{m:+.2f} [{lo:+.2f}, {hi:+.2f}] pt")
        ax.annotate(txt, (hi, yy), xytext=(4, 0), textcoords="offset points", va="center", ha="left", fontsize=6.6, color=INK)
    ax.set_yticks(y, [lab[r["comparison"]] for r in rows] if key == "cost_pct" else [""] * 3)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel(xl)
    ax.text(band, 2.55, bandlab, ha="right", va="bottom", fontsize=6.4, color=INK2)
    ax.set_ylim(-0.6, 2.95)
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
axes[0].set_xlim(-31, 27); axes[1].set_xlim(-1.15, 0.95)
axes[0].set_title("(a) Cost", loc="left"); axes[1].set_title("(b) Compliance", loc="left")
fig.tight_layout(w_pad=1.2)
save(fig, OUT, "FR1_confirmatory_C1_C3")

# ============================================================== FR2: calibrated development, paired per trace
p3 = json.load(open(os.path.join(REV, "calibrated_build_20261125", "p3_results.json")))
fig, axes = plt.subplots(2, 2, figsize=(7.16, 3.6), sharex=True, facecolor=SURF)
for c, (st, dl) in enumerate((("CAL145C", "14.5 s deadline"), ("CAL12C", "12 s deadline"))):
    P = {x["seed"]: x for x in p3[st]["paired"]}
    seeds = sorted(P)
    assert seeds == [101, 102, 103, 104, 105]
    xs = range(len(seeds))
    pc = [P[s]["prism"]["cost"] for s in seeds]; mc = [P[s]["memadapt"]["cost"] for s in seeds]
    pv = [P[s]["prism"]["viol"] for s in seeds]; mv = [P[s]["memadapt"]["viol"] for s in seeds]
    prem = [P[s]["premium_pct"] for s in seeds]
    a, b = axes[0][c], axes[1][c]
    dx = 0.1     # dodge: PRISM left, MemAdapt-q90 right, so equal values stay visible
    for ax, vals_p, vals_m in ((a, pc, mc), (b, pv, mv)):
        for i in xs:
            ax.plot([i - dx, i + dx], [vals_p[i], vals_m[i]], color=GRID, lw=1.2, zorder=1)
        ax.plot([i - dx for i in xs], vals_p, "o", ms=5.2, color=BLUE, mec=SURF, mew=0.8, zorder=3, label="PRISM")
        ax.plot([i + dx for i in xs], vals_m, "^", ms=5.6, color=YELLOW, mec=INK2, mew=0.5, zorder=3, label="MemAdapt-q90")
        ax.grid(axis="y", color=GRID, lw=0.5, zorder=0)
        ax.set_xlim(-0.6, len(seeds) - 0.4)
    for i in xs:
        a.annotate(f"{prem[i]:+.1f}%", (i - dx, pc[i]), xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", fontsize=6.4, color=INK)
    b.axhline(2.0, color=INK2, lw=0.7, ls=(0, (3, 2)), zorder=1)
    b.text(2.5, 2.05, "2% target", ha="center", va="bottom", fontsize=6.4, color=INK2)
    a.set_title(f"({'ab'[c]}) Weekly cost, {dl}", loc="left")
    b.set_title(f"({'cd'[c]}) Violating windows, {dl}", loc="left")
    b.set_xticks(list(xs), [str(s) for s in seeds]); b.set_xlabel("Development trace")
    a.set_ylim(880, 1340); b.set_ylim(-0.1, 3.0)
    if c == 0:
        a.set_ylabel("USD per week (simulated)"); b.set_ylabel("% of 15-min windows")
        b.text(0.0, 2.95, "QuantProv-q90 and Reactive at 1024 MB: 100% at every\nsetting tested (off scale)", ha="left", va="top", fontsize=6.2, color=INK2)
h, l = axes[0][0].get_legend_handles_labels()
fig.legend(h, l, ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.035))
fig.tight_layout(h_pad=0.8, w_pad=1.6)
save(fig, OUT, "FR2_calibrated_development")

# ============================================================== REGEN-WIN paper figures via the unchanged make_figs.py
tree = os.path.join(OUT, "regen_win_tree")
shutil.copytree(os.path.join(PR, "src"), os.path.join(tree, "src"))
shutil.copytree(os.path.join(HERE, "figure_inputs_regen_win", "results"), os.path.join(tree, "results"))
os.makedirs(os.path.join(tree, "results", "tables"), exist_ok=True)
shutil.copyfile(os.path.join(REV, "regeneration_20261122", "outputs", "tables", "F3_validation_frontier.csv"),
                os.path.join(tree, "results", "tables", "F3_validation_frontier.csv"))
subprocess.run([sys.executable, os.path.join(PR, "scripts", "revision", "figures", "make_figs.py"), tree, os.path.join(OUT, "regen_win")], check=True)

same = 0
for rel, ref in REFERENCE.items():
    got = hashlib.sha256(open(os.path.join(OUT, *rel.split("/")), "rb").read()).hexdigest()
    same += got == ref
    print(f"{'MATCH ' if got == ref else 'DIFFER'}  {rel}")
print(f"{same} of {len(REFERENCE)} PNG/TIFF files byte-identical to the reference (pixels depend on the installed fonts)")
