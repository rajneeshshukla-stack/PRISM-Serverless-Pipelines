#!/usr/bin/env python3
"""Stage 2.2 DIAGNOSTIC (post hoc; no stored result is changed): does PRISM's cost model ever pick a capacity
level above the smallest feasible one, and how does the realized record-level miss compare with epsilon?

Re-runs PRISM at each trace's validation-selected epsilon in all four test weeks (20 runs) with the released code,
wrapping ChanceConstrainedOptimizer.decide (unchanged) to log, per epoch, the chosen level index and the smallest
feasible level index for the chosen memory size. Runs in the current environment (Python 3.13, scikit-learn 1.9.1),
so forecast-driven results differ slightly from the stored ones (library-version effect, Supplementary S1); the
stored cost and violating-window rate are printed alongside for comparison.
Usage: python level_choice_diagnostic.py <code_root> <out.json>
"""
import json, os, sys
import numpy as np
ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro import optimizer as optmod  # noqa: E402

SEL = {101: 0.02, 102: 0.03, 103: 0.05, 104: 0.05, 105: 0.05}   # results/tables/E1_selected_parameters.md
SCEN = ('stationary', 'growth', 'bursty', 'new_spike')
LOG = []
_orig = optmod.ChanceConstrainedOptimizer.decide


def decide(self, scen, mems, kappa):
    dec = _orig(self, scen, mems, kappa)
    ev = self.evaluate(scen, mems, kappa)
    feas = ev['feas'] >= 1 - self.pcfg.delta - 1e-12
    i = list(ev['mems']).index(dec.mem)
    j = int(np.argmin(np.abs(np.asarray(ev['ys']) - dec.level)))
    smallest = int(np.argmax(feas[i])) if feas[i].any() else -1
    LOG.append((bool(dec.feasible), j, smallest, int(dec.mem), len(mems) > 1))
    return dec


optmod.ChanceConstrainedOptimizer.decide = decide
stored = {}
for line in open(os.path.join(ROOT, 'results', 'raw', 'E1', 'rows.jsonl')):
    r = json.loads(line)
    if r['week'] == 'test' and r['policy'] == 'PRISM':
        stored[(r['seed'], r['scenario'], round(r['param'], 4))] = r
out = []
for seed, eps in SEL.items():
    b = TraceBundle(seed, PipelineConfig())
    for sc in SCEN:
        LOG.clear()
        res = simulate(b.context(sc, 'test'), make_policy({'family': 'PRISM', 'param': eps}))
        s = res['summary']
        L = np.array(LOG, dtype=object)
        feas = L[:, 0].astype(bool)
        chosen, small = L[:, 1].astype(int), L[:, 2].astype(int)
        st = stored[(seed, sc, round(eps, 4))]
        out.append(dict(seed=seed, scenario=sc, eps=eps, epochs=len(L), feasible_epochs=int(feas.sum()),
                        above_smallest=int(((chosen != small) & feas).sum()), zero_level=int(((chosen == 0) & feas).sum()),
                        non_default_memory=int((L[:, 3].astype(int) != 1024).sum()),
                        miss=1 - s['record_attainment'], viol=s['violating_window_rate'], cost=s['cost'],
                        stored_miss=1 - st['record_attainment'], stored_viol=st['violating_window_rate'], stored_cost=st['cost']))
        print(out[-1], flush=True)
tot = dict(runs=len(out), feasible_epochs=sum(o['feasible_epochs'] for o in out),
           above_smallest=sum(o['above_smallest'] for o in out), zero_level=sum(o['zero_level'] for o in out),
           miss_range=[min(o['miss'] for o in out), max(o['miss'] for o in out)],
           stored_miss_range=[min(o['stored_miss'] for o in out), max(o['stored_miss'] for o in out)],
           max_abs_cost_pct_vs_stored=max(abs(o['cost'] / o['stored_cost'] - 1) * 100 for o in out),
           max_abs_viol_pp_vs_stored=max(abs(o['viol'] - o['stored_viol']) * 100 for o in out))
json.dump(dict(runs=out, totals=tot, environment=sys.version), open(OUT, 'w'), indent=1)
print(tot)
