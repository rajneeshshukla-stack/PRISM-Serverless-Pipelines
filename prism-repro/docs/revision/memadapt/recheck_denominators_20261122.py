#!/usr/bin/env python3
"""Recheck of the RQ4 cost percentages (22 Nov 2026), read-only on the saved rows of this folder (7980b69).
Same selection and aggregation as scripts/revision/memadapt_compare.py: per trace, the validation-selected setting of
each family (experiment.select_by_rule on the validation week), its test-week cost, then the per-trace percentage
averaged over the five traces. Both denominators are reported, because 'PRISM costs X% more than MemAdapt' and
'MemAdapt costs Y% less than PRISM' are different numbers. EXPLORATORY, PRE-CALIBRATION, fast simulator.
usage (from prism-repro/): python docs/revision/memadapt/recheck_denominators_20261122.py ."""
import glob, json, os, sys
import numpy as np
ROOT = os.path.abspath(sys.argv[1]); sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.experiment import select_by_rule
D = os.path.join(ROOT, "docs", "revision", "memadapt")
rows = [json.loads(l) for f in sorted(glob.glob(os.path.join(D, "rows_*.jsonl"))) for l in open(f, encoding="utf-8")]


def test_cost(seed, ns, dl, fam):
    val = [r for r in rows if (r["seed"], r["nonscaling"], r["deadline"], r["family"], r["week"]) == (seed, ns, dl, fam, "val")]
    s = select_by_rule(val, key_viol="viol")
    t = [r for r in rows if (r["seed"], r["nonscaling"], r["deadline"], r["family"], r["week"]) == (seed, ns, dl, fam, "test")
         and r["param"] == s["param"]]
    return t[0]["cost"], t[0]["viol"]


seeds = sorted({r["seed"] for r in rows})
out = ["RQ4 COST PERCENTAGES, BOTH DENOMINATORS (saved rows of 7980b69; validation-selected; mean over 5 traces of the "
       "per-trace percentage). EXPLORATORY, PRE-CALIBRATION.", ""]
for ns, dl in ((0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)):
    p = np.array([test_cost(s, ns, dl, "PRISM")[0] for s in seeds])
    m = np.array([test_cost(s, ns, dl, "MemAdapt_q90")[0] for s in seeds])
    pv = np.array([test_cost(s, ns, dl, "PRISM")[1] for s in seeds]); mv = np.array([test_cost(s, ns, dl, "MemAdapt_q90")[1] for s in seeds])
    out.append(f"  non-scaling {ns}, deadline {dl:4.1f} s: PRISM vs MemAdapt (MemAdapt = 100%) {np.mean(100 * (p / m - 1)):+5.1f}%;  "
               f"MemAdapt vs PRISM (PRISM = 100%) {np.mean(100 * (m / p - 1)):+5.1f}%;  mean costs PRISM {p.mean():7.1f}, "
               f"MemAdapt {m.mean():7.1f};  viol PRISM {100*pv.mean():.2f}% / MemAdapt {100*mv.mean():.2f}%;  "
               f"weeks within 2%: PRISM {int((pv <= 0.02 + 1e-12).sum())}/5, MemAdapt {int((mv <= 0.02 + 1e-12).sum())}/5")
out.append("")
for ns, dl in ((0.5, 13.0), (0.5, 12.0), (0.15, 12.0)):
    m = np.array([test_cost(s, ns, dl, "MemAdapt_q90")[0] for s in seeds])
    m0 = np.array([test_cost(s, ns, 14.5, "MemAdapt_q90")[0] for s in seeds])
    out.append(f"  remedy cost, MemAdapt at {dl:4.1f} s against MemAdapt at 14.5 s (non-scaling {ns}): {np.mean(100 * (m / m0 - 1)):+5.1f}% "
               f"(per trace {', '.join(f'{x:+.1f}' for x in 100 * (m / m0 - 1))}); ratio of mean costs {100 * (m.mean() / m0.mean() - 1):+5.1f}%")
txt = "\n".join(out) + "\n"
open(os.path.join(D, "recheck_denominators_20261122.txt"), "w", encoding="utf-8", newline="\n").write(txt)
print(txt)
