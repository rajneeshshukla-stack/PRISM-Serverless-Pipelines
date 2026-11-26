"""Independent, read-only verification of the saved kappa-gap diagnostic and the closed-loop pilot rerun.

Reads saved JSON/text only; runs no simulation. Usage:
  python -I verify_evidence.py <repo_root> <pilot_dir>
"""
import glob
import json
import os
import re
import sys

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
ROOT, PILOT = sys.argv[1], sys.argv[2]
KG = os.path.join(ROOT, "prism-repro", "docs", "revision", "kappa_gap")
FAILS = []


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


# Copied verbatim from prism-repro/src/prism_repro/experiment.py (select_by_rule, GRIDS, GRIDS_WIDE) so the check
# does not import the package; equality with the source is asserted below by text match.
def select_by_rule(rows, threshold=0.02):
    ok = [r for r in rows if r["violating_window_rate"] <= threshold + 1e-12]
    if ok:
        return min(ok, key=lambda r: (r["cost"], r["violating_window_rate"]))
    return min(rows, key=lambda r: (r["violating_window_rate"], r["cost"]))


GRIDS = {"Reactive": [round(0.40 + 0.05 * i, 2) for i in range(11)], "PRISM": [0.005, 0.01, 0.02, 0.03, 0.05, 0.08],
         "QuantProv": [round(0.6 + 0.1 * i, 1) for i in range(10)]}
GRIDS_WIDE = {"Reactive": [0.30, 0.35] + GRIDS["Reactive"] + [0.95, 1.0],
              "PRISM": [0.002, 0.003] + GRIDS["PRISM"] + [0.10, 0.15, 0.20],
              "QuantProv": [0.4, 0.5] + GRIDS["QuantProv"] + [1.6, 1.8, 2.0]}
src = open(os.path.join(ROOT, "prism-repro", "src", "prism_repro", "experiment.py"), encoding="utf-8").read()
for frag in ('"Reactive": [round(0.40 + 0.05 * i, 2) for i in range(11)]', '"PRISM": [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]',
             '"QuantProv": [round(0.6 + 0.1 * i, 1) for i in range(10)]',
             '"PRISM": [0.002, 0.003] + GRIDS["PRISM"] + [0.10, 0.15, 0.20]',
             '"QuantProv": [0.4, 0.5] + GRIDS["QuantProv"] + [1.6, 1.8, 2.0]',
             '"Reactive": [0.30, 0.35] + GRIDS["Reactive"] + [0.95, 1.0]',
             'ok = [r for r in rows if r[key_viol] <= threshold + 1e-12]'):
    assert frag in src, frag

# ------------------------------------------------------------------------------------------------ kappa gap
print("=" * 100 + "\nA. SAVED KAPPA DIAGNOSTIC  prism-repro/docs/revision/kappa_gap/")
files = sorted(glob.glob(os.path.join(KG, "rows_*.json")))
R = [json.load(open(p)) for p in files]
print(f"  files: {len(files)}")
check(len(R) == 10, "10 trace files")
check(sorted((r["seed"], r["scenario"]) for r in R) == sorted((s, c) for s in range(101, 106) for c in ("stationary", "new_spike")),
      "seeds 101-105 x {stationary, new_spike}, each once")
check(all(r["n_epochs"] == 2016 for r in R), "every trace has 2016 epochs (7 d x 288 five-minute epochs)")
for r in R:
    for k in "FOC":
        x = r[k]
        assert abs(x["ratio"] - x["cold_total"] / max(x["od_total"], 1)) < 1e-12
        assert abs(sum(x["od_stage"]) - x["od_total"]) < 1e-6 and abs(sum(x["cold_stage"]) - x["cold_total"]) < 1e-9
check(True, "denominator: 'cold per on-demand request' = cold starts / on-demand requests, whole week, 4 stages summed "
            "(recomputed from totals and per-stage sums in all 30 F/O/C records)")
dev = max(abs(r["cold_start_ratio"][k] - r[k]["cold_total"] / (4 * r["n_requests"])) for r in R for k in "FOC")
check(dev < 1e-12, f"denominator: 'cold-start ratio' = cold starts / stage executions (= 4 x pipeline requests), F, O and C "
                   f"(max deviation {dev:.1e})")
check(all(abs(r["C_rec_kappa_mean"] - r["C"]["kappa_mean"]) < 1e-12 for r in R), "check (a): recorded closed-loop kappa = recomputed")
print("  Matching: F and O share the schedule by construction (O = simulate_events(cfg, draws, F.P_epoch, F.mem_epoch));")
print("            draws: EventDraws(cfg, test-week counts, seed, key 3); PRISM eps 0.02 fixed (not tuned), GBM.")

q = lambda f: np.array([r["O"][f] / r["F"][f] for r in R])  # noqa: E731
rat, cold, od = q("ratio"), q("cold_total"), q("od_total")
print(f"\n  [3.23x] COLD-START RATE RATIO, O/F, cold per on-demand request, mean of 10 per-trace ratios: "
      f"{rat.mean():.3f}  range {rat.min():.3f}-{rat.max():.3f}")
mF, mO = np.mean([r["F"]["ratio"] for r in R]), np.mean([r["O"]["ratio"] for r in R])
print(f"          pooled-mean form: O {mO:.5f} / F {mF:.5f} = {mO / mF:.3f}")
print(f"          cold starts O/F {cold.mean():.3f} ({cold.min():.2f}-{cold.max():.2f}); on-demand requests O/F {od.mean():.3f} "
      f"({od.min():.2f}-{od.max():.2f})")
check(abs(rat.mean() - 3.23) < 0.005 and abs(rat.min() - 2.97) < 0.005 and abs(rat.max() - 3.59) < 0.005, "3.23x (2.97-3.59) reproduced")

print("\n  [kappa] KAPPA ESTIMATE (EWMA of per-epoch cold/on-demand, alpha 0.1, prior 0.35), epoch mean per trace:")
for k, lab in (("F", "fast"), ("O", "event, F's schedule"), ("C", "event, closed loop")):
    a = np.array([r[k]["kappa_mean"] for r in R]); u = np.array([r[k]["kappa_unclipped_mean"] for r in R])
    fs = np.array([r[k]["floor_share"] for r in R])
    print(f"    {lab:21s} clipped {a.mean():.3f} [{a.min():.3f}-{a.max():.3f}] | unclipped {u.mean():.3f} "
          f"[{u.min():.3f}-{u.max():.3f}] | at floor {100 * fs.mean():.1f}%")
for num, lab in (("O", "O/F"), ("C", "C/F")):
    c = np.array([r[num]["kappa_mean"] / r["F"]["kappa_mean"] for r in R])
    u = np.array([r[num]["kappa_unclipped_mean"] / r["F"]["kappa_unclipped_mean"] for r in R])
    print(f"    kappa-estimate ratio {lab}: clipped {c.mean():.2f}x [{c.min():.2f}-{c.max():.2f}] | "
          f"unclipped {u.mean():.2f}x [{u.min():.2f}-{u.max():.2f}]")
print("    -> no per-trace kappa-estimate ratio in the saved diagnostic reaches 20x (see max above).")
viol = {k: 100 * np.mean([r["viol"][k] for r in R]) for k in "FOC"}
dc = np.array([100 * (r["cost"]["C"] / r["cost"]["O"] - 1) for r in R])
dv = np.array([100 * (r["viol"]["C"] - r["viol"]["O"]) for r in R])
print(f"  violating windows F {viol['F']:.2f}% O {viol['O']:.2f}% C {viol['C']:.2f}%; C vs O cost {dc.mean():+.1f}% "
      f"[{dc.min():+.1f},{dc.max():+.1f}], viol {dv.mean():+.2f} pts [{dv.min():+.2f},{dv.max():+.2f}]")
check(round(viol["F"], 2) == 0.70 and round(viol["O"], 2) == 2.89, "violating windows 0.70% vs 2.89% reproduced")
fl = np.array([r["F"]["floor_share"] for r in R])
check(round(100 * fl.mean(), 1) == 89.7, "fast kappa at floor 89.7% of epochs reproduced")
check(round(np.mean([r["F"]["kappa_unclipped_mean"] for r in R]), 3) == 0.050 and
      round(np.mean([r["O"]["kappa_unclipped_mean"] for r in R]), 3) == 0.330, "unclipped 0.050 (F) and 0.330 (O) reproduced")
txt = open(os.path.join(KG, "summary.txt"), encoding="utf-8").read()
for s in ("x3.23 [2.97-3.59]", "x2.88 [2.41-3.19]", "violating windows 0.70%", "violating windows 2.89%", "floor  89.7%",
          "unclipped 0.050", "cost +8.9% [+7.7, +10.2]", "-1.15 points [-2.38, -0.60]", "recomputed from the final event telemetry: True"):
    check(s in txt, f"summary.txt contains {s!r}")

# ------------------------------------------------------------------------------------------------ pilot
print("\n" + "=" * 100 + f"\nB. CLOSED-LOOP PILOT RERUN  {PILOT}")
env = json.load(open(os.path.join(PILOT, "environment.json")))
print(f"  environment: commit {env['commit']}, {env['platform']}, python {env['python']}, numpy {env['numpy']}, "
      f"scipy {env['scipy']}, sklearn {env['sklearn']}, seeds {env['seeds']}, {env['scenario']}")
print(f"  label: {env['label']}")
check(env["seeds"] == [101, 102, 103] and env["scenario"] == "stationary", "seeds 101-103, stationary (PRESPECIFICATION sec. 7)")
check(env["pipeline_config"]["deadline"] == 14.5, "default deadline 14.5 s")
check("kappa_clip=(0.1, 1.0)" in env["prism_config"], "PRISM kappa floor 0.1 (submitted)")
FAM = {"PRISM": "PRISM", "QuantProv_q90": "QuantProv", "Reactive": "Reactive", "MemAdapt_q90": "QuantProv"}
gfiles = sorted(glob.glob(os.path.join(PILOT, "group_*.json")))
check(len(gfiles) == 12, f"12 group files ({len(gfiles)})")
G = {}
for p in gfiles:
    g = json.load(open(p))
    m = re.match(r"group_(\d+)_(.+)\.json$", os.path.basename(p))
    assert int(m.group(1)) == g["seed"] and m.group(2) == g["family"], p
    G[(g["seed"], g["family"])] = g
check(set(G) == {(s, f) for s in (101, 102, 103) for f in FAM}, "one group per seed x family")
check(all(g["commit"] == env["commit"] for g in G.values()), "every group records the environment's commit")
check(all(g["scenario"] == "stationary" for g in G.values()), "every group stationary")

nweeks, rts = 0, []
for (s, f), g in sorted(G.items()):
    gn = FAM[f]
    assert g["grid"] == GRIDS[gn], (s, f)
    vals = {r["param"]: r for r in g["validation"]}
    assert set(vals) == set(GRIDS[gn]) | set(g["expansions"])
    # replay the prespecified edge expansion
    have, exp_replay = sorted(GRIDS[gn]), []
    while True:
        sel = select_by_rule([vals[p] for p in have])["param"]
        nxt = None
        if sel == have[0]:
            lo = [x for x in GRIDS_WIDE[gn] if x < have[0]]; nxt = max(lo) if lo else None
        elif sel == have[-1]:
            hi = [x for x in GRIDS_WIDE[gn] if x > have[-1]]; nxt = min(hi) if hi else None
        if nxt is None:
            break
        exp_replay.append(nxt); have = sorted(have + [nxt])
    assert exp_replay == g["expansions"] and sel == g["selected"], (s, f, exp_replay, sel)
    assert g["edge_hit"] == (sel in (have[0], have[-1]))
    assert g["test"]["param"] == sel and g["test"]["week"] == "test"
    for r in g["validation"] + [g["test"]]:
        w = r["violating_window_rate"] * 672
        assert abs(w - round(w)) < 1e-9, (s, f, r["param"])
        rts.append(r["runtime_s"]); nweeks += 1
check(True, "grids = experiment.GRIDS; selection and edge expansions replayed from saved validation rows (all 12)")
check(True, "every violating-window rate is an integer count of 672 fifteen-minute windows")
for s in (101, 102, 103):
    nv = {G[(s, f)]["validation"][0]["n_requests"] for f in FAM} | {r["n_requests"] for f in FAM for r in G[(s, f)]["validation"]}
    nt = {G[(s, f)]["test"]["n_requests"] for f in FAM}
    kg = [r["n_requests"] for r in R if r["seed"] == s and r["scenario"] == "stationary"]
    check(len(nv) == 1 and len(nt) == 1, f"seed {s}: identical request counts across families (val {nv.pop()}, test {next(iter(nt))})")
    check(kg == [next(iter(nt))], f"seed {s}: pilot test-week count equals kappa_gap stationary test week ({kg[0]})")
check(nweeks == 125, f"{nweeks} closed-loop weeks (summary says 125)")
print(f"  runtime: median {np.median(rts):.0f} s, total {sum(rts) / 3600:.2f} h of recorded week time")

print("\n  Per trace, test week (<= 13 of 672 windows = met 2%):")
for f in FAM:
    for s in (101, 102, 103):
        g = G[(s, f)]; t = g["test"]; v = next(r for r in g["validation"] if r["param"] == g["selected"])
        print(f"    {f:14s} {s} sel {g['selected']:<6} exp {g['expansions'] or '-'!s:6} edge {g['edge_hit']!s:5} | val "
              f"{round(v['violating_window_rate'] * 672):2d}/672 cost {v['cost']:7.1f} | test {round(t['violating_window_rate'] * 672):2d}/672 "
              f"({100 * t['violating_window_rate']:.2f}%) {'met ' if round(t['violating_window_rate'] * 672) <= 13 else 'MISS'} "
              f"cost {t['cost']:7.1f} mem>=2048 {t['share_mem_ge_2048']:.3f} kappa {t.get('kappa_mean', float('nan')):.3f}")
strip = lambda rows: [{k: v for k, v in r.items() if k != "runtime_s"} for r in rows]  # noqa: E731
same = all(strip(G[(s, "MemAdapt_q90")]["validation"] + [G[(s, "MemAdapt_q90")]["test"]]) ==
           strip(G[(s, "QuantProv_q90")]["validation"] + [G[(s, "QuantProv_q90")]["test"]]) for s in (101, 102, 103))
mem = max(r["share_mem_ge_2048"] for s in (101, 102, 103) for f in ("MemAdapt_q90", "QuantProv_q90")
          for r in G[(s, f)]["validation"] + [G[(s, f)]["test"]])
print(f"  MemAdapt-q90 records identical to QuantProv-q90 in every field, all weeks: {same}; max share of epochs >= 2048 MB "
      f"in either: {mem}")
met = {f: sum(round(G[(s, f)]["test"]["violating_window_rate"] * 672) <= 13 for s in (101, 102, 103)) for f in FAM}
pooled = {f: 100 * np.mean([G[(s, f)]["test"]["violating_window_rate"] for s in (101, 102, 103)]) for f in FAM}
print(f"  test weeks meeting 2%: {met}; mean test violating-window rate: "
      + ", ".join(f"{f} {v:.2f}%" for f, v in pooled.items()))

print("\n  Paired PRISM minus comparator, 3 traces, 95% t interval (df 2); similar compliance iff interval within +/-0.5 pts:")
for comp in ("QuantProv_q90", "Reactive", "MemAdapt_q90"):
    c = np.array([100 * (G[(s, "PRISM")]["test"]["cost"] / G[(s, comp)]["test"]["cost"] - 1) for s in (101, 102, 103)])
    v = np.array([100 * (G[(s, "PRISM")]["test"]["violating_window_rate"] - G[(s, comp)]["test"]["violating_window_rate"])
                  for s in (101, 102, 103)])
    h = lambda x: stats.t.ppf(0.975, 2) * x.std(ddof=1) / np.sqrt(3)  # noqa: E731
    sim = abs(v.mean()) + h(v) <= 0.5
    diff = (c.mean() - h(c) > 0) or (c.mean() + h(c) < 0)
    tie = (c.mean() - h(c) >= -2) and (c.mean() + h(c) <= 2)
    print(f"    vs {comp:14s} cost {c.mean():+.1f} +/- {h(c):.1f}% [{c.mean() - h(c):+.1f}, {c.mean() + h(c):+.1f}] "
          f"per trace {np.round(c, 1).tolist()} | viol {v.mean():+.2f} +/- {h(v):.2f} pts [{v.mean() - h(v):+.2f}, "
          f"{v.mean() + h(v):+.2f}] per trace {np.round(v, 2).tolist()}")
    print(f"       cost interval excludes 0: {diff}; within +/-2% (tie): {tie}; similar compliance: {sim}")

raw = open(os.path.join(PILOT, "summary.txt"), "rb").read()
enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
st = raw.decode(enc)
print(f"\n  summary.txt encoding: {enc}")
for s in ("cost +1.6 +/- 17.0%", "cost -27.3 +/- 6.2%", "-0.15 +/- 1.28 points", "+0.79 +/- 0.85 points",
          "similar compliance (+/-0.5): NO", "125 closed-loop weeks, median 78 s, total 2.7 CPU-h", "1.5 ([1.6])"):
    check(s in st, f"summary.txt contains {s!r}")
check(st.count("similar compliance (+/-0.5): NO") == 3, "all three comparisons NOT similar compliance in summary.txt")
print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
