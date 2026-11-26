import json, sys, numpy as np
sys.path.insert(0, "src")
from prism_repro.config import PipelineConfig
from prism_repro.latency import miss_probabilities
rows = [json.loads(l) for l in open("docs/revision/sensitivity/rows.jsonl")]
lag = [r for r in rows if r["part"] == "lag"]
print("PRE-CALIBRATION, fast simulator, current code (phase-e-review). Every family tuned on the validation week by the paper's rule; held-out test weeks.")
print("\nLAG (seeds 101-105 x 4 test scenarios = 20 weeks per cell): mean cost USD/week | pooled violating windows | weeks meeting 2% | selected parameter per seed | mean conformal offset (test weeks)")
for fam in ("PRISM", "QuantProv_q90", "PredHead+S", "Reactive"):
    for L in (2, 5, 10):
        g = [r for r in lag if r["family"] == fam and r["lag"] == L]
        sel = {r["seed"]: r["param"] for r in g}
        print(f"  {fam:13s} L={L:2d} min: {np.mean([r['cost'] for r in g]):7.1f} | {100*np.mean([r['viol'] for r in g]):4.2f}% | {sum(r['met'] for r in g):2d}/20 | {[sel[s] for s in sorted(sel)]} | {np.mean([r['mean_offset_test'] for r in g]):.3f} (x{np.exp(np.mean([r['mean_offset_test'] for r in g])):.2f})")
print("\nLAG: cost of each predictive family relative to Reactive at the same L")
for L in (2, 5, 10):
    c = {f: np.mean([r["cost"] for r in lag if r["family"] == f and r["lag"] == L]) for f in ("PRISM", "QuantProv_q90", "PredHead+S", "Reactive")}
    print(f"  L={L:2d}: PRISM {100*(c['PRISM']/c['Reactive']-1):+.1f}%, QuantProv-q90 {100*(c['QuantProv_q90']/c['Reactive']-1):+.1f}%, PredHead+S {100*(c['PredHead+S']/c['Reactive']-1):+.1f}%")
ini = [r for r in rows if r["part"] == "init"]
print("\nINIT DIRECTION (nonscaling 0.5, stationary test week, seeds 101-102, eps 0.02 not retuned): mean cost | violating windows | share of epochs at >= 2048 MB")
for D in (13.0, 12.0):
    for mode in ("eq3", "constant", "inverted"):
        parts = []
        for pol in ("PRISM-mem", "PRISM-1024", "OnDemand"):
            g = [r for r in ini if r["deadline"] == D and r["init_scaling"] == mode and r["policy"] == pol]
            parts.append(f"{pol} {np.mean([r['cost'] for r in g]):7.1f} | {100*np.mean([r['viol'] for r in g]):6.2f}% | {np.mean([r['share_mem_ge_2048'] for r in g]):.2f}")
        print(f"  D={D:4.1f} s {mode:8s}: " + "  ||  ".join(parts))
print("\nWarm miss probability v_w and rho (one cold stage) by memory, nonscaling 0.5, Eq. (3) init scaling")
for D in (14.5, 13.0, 12.0):
    c = PipelineConfig().with_(nonscaling=0.5, deadline=D)
    print(f"  D={D:4.1f} s: " + "  ".join(f"{m} MB v_w {miss_probabilities(c, m)[0]:.4f} rho {miss_probabilities(c, m)[1]:.3f}" for m in c.mem_options))
