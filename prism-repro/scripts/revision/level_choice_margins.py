#!/usr/bin/env python3
"""Tie sensitivity of the level-choice statistic (R2.5, R2.17, R4.1, R5.M6, R6.7). DIAGNOSTIC, post hoc.

level_choice_diagnostic.py counts epochs in which PRISM's optimiser picks a capacity level above the
smallest feasible one (published: 16 of 40,293 feasible epochs; 20 runs x 2,016 epochs = 40,320). The count
moves between code states and environments. This probe asks whether it moves because of floating-point
near-ties or because the inputs (forecasts, hence scenarios) differ. It wraps
ChanceConstrainedOptimizer.decide exactly as the diagnostic does (decisions are unchanged) and records, per
epoch:

  feasible / chosen index j / smallest feasible index s (chosen memory row), as in the diagnostic;
  margin_above   (cost[s] - cost[j]) / cost[j] for every epoch with j > s (how much the choice saves);
  gap_global     relative cost gap between the best and the second-best feasible candidate over all
                 (memory, level) pairs: a cost near-tie if below 1e-9;
  eps_flip       whether the decision (P, memory) changes when eps is scaled by 1 -/+ 1e-9: a
                 feasibility near-tie.

It also compares each run's per-epoch provisioning schedule with the stored E1 arrays
(results/raw/E1/arrays_seed*.npz, produced by the code tagged v1-submitted in the reference sandbox), so a
run of the archived tree shows whether the stored decisions reproduce in the current environment.

Usage: python level_choice_margins.py <code_root> <out.json> [<stored_results_root>]
  <code_root>            tree whose src/ is imported (e.g. a `git archive` of v1-submitted, or this repo)
  <stored_results_root>  tree holding results/raw/E1 (default: <code_root>)
"""
import dataclasses
import json
import os
import sys

import numpy as np

ROOT, OUT = sys.argv[1], sys.argv[2]
STORE = sys.argv[3] if len(sys.argv) > 3 else ROOT
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro import optimizer as optmod  # noqa: E402

SEL = {101: 0.02, 102: 0.03, 103: 0.05, 104: 0.05, 105: 0.05}   # as level_choice_diagnostic.py
SCEN = ('stationary', 'growth', 'bursty', 'new_spike')
TIE = 1e-9
LOG = []
_orig = optmod.ChanceConstrainedOptimizer.decide


def _smallest(ev, i, thr):
    f = ev['feas'][i] >= thr
    return int(np.argmax(f)) if f.any() else -1


def decide(self, scen, mems, kappa):
    dec = _orig(self, scen, mems, kappa)
    pc = self.pcfg
    thr = 1 - pc.delta - 1e-12
    ev = self.evaluate(scen, mems, kappa)
    i = list(ev['mems']).index(dec.mem)
    j = int(np.argmin(np.abs(np.asarray(ev['ys']) - dec.level)))
    s = _smallest(ev, i, thr)
    rec = dict(feasible=bool(dec.feasible), j=j, s=s, mem=int(dec.mem))
    feas = ev['feas'] >= thr
    if feas.any():
        c = np.where(feas, ev['cost'], np.inf).ravel()
        two = np.partition(c, 1)[:2] if np.isfinite(c).sum() > 1 else None
        rec['gap_global'] = float((two[1] - two[0]) / two[0]) if two is not None and two[0] > 0 else None
        if dec.feasible and s >= 0 and j != s:
            cs, cj = ev['cost'][i][s], ev['cost'][i][j]
            rec['margin_above'] = float((cs - cj) / cj)
    flip = False
    for f in (1 - TIE, 1 + TIE):
        self.pcfg = dataclasses.replace(pc, eps=pc.eps * f)
        try:
            d2 = _orig(self, scen, mems, kappa)
        finally:
            self.pcfg = pc
        if d2.mem != dec.mem or not np.array_equal(d2.P, dec.P):
            flip = True
    rec['eps_flip'] = flip
    LOG.append(rec)
    return dec


optmod.ChanceConstrainedOptimizer.decide = decide

stored = {}
for seed in SEL:
    p = os.path.join(STORE, 'results', 'raw', 'E1', f'arrays_seed{seed}.npz')
    if os.path.exists(p):
        z = np.load(p)
        for sc in SCEN:
            k = f'E1|{seed}|{sc}|test|PRISM-{SEL[seed]:g}|::P_epoch'
            if k in z.files:
                stored[(seed, sc)] = z[k]

out = []
for seed, eps in SEL.items():
    b = TraceBundle(seed, PipelineConfig())
    for sc in SCEN:
        LOG.clear()
        res = simulate(b.context(sc, 'test'), make_policy({'family': 'PRISM', 'param': eps}))
        s = res['summary']
        L = list(LOG)
        feas = np.array([r['feasible'] for r in L])
        above = [r for r in L if r['feasible'] and r['s'] >= 0 and r['j'] != r['s']]
        gaps = np.array([r['gap_global'] for r in L if r.get('gap_global') is not None])
        P_run = res.get('raw', {}).get('P_epoch') if isinstance(res.get('raw'), dict) else None
        st = stored.get((seed, sc))
        sched = None
        if P_run is not None and st is not None and np.shape(P_run) == np.shape(st):
            sched = int(np.any(np.asarray(P_run) != st, axis=1).sum())
        out.append(dict(seed=seed, scenario=sc, eps=eps, epochs=len(L), feasible_epochs=int(feas.sum()),
                        no_feasible_epochs=int((~feas).sum()), above_smallest=len(above),
                        margins_above=sorted(r['margin_above'] for r in above),
                        global_near_ties=int((gaps < TIE).sum()), min_gap_global=float(gaps.min()) if len(gaps) else None,
                        eps_flips=int(sum(r['eps_flip'] for r in L)),
                        eps_flips_among_above=int(sum(r['eps_flip'] for r in above)),
                        epochs_schedule_differs_from_stored_E1=sched, cost=float(s['cost']),
                        viol=float(s['violating_window_rate'])))
        print({k: v for k, v in out[-1].items() if k != 'margins_above'}, flush=True)

allm = [m for o in out for m in o['margins_above']]
tot = dict(runs=len(out), epochs=sum(o['epochs'] for o in out), feasible_epochs=sum(o['feasible_epochs'] for o in out),
           no_feasible_epochs=sum(o['no_feasible_epochs'] for o in out), above_smallest=len(allm),
           above_smallest_share_of_feasible=len(allm) / max(1, sum(o['feasible_epochs'] for o in out)),
           margin_above_min=min(allm) if allm else None, margin_above_median=float(np.median(allm)) if allm else None,
           margin_above_below_1e9=int(sum(m < TIE for m in allm)),
           global_near_ties=sum(o['global_near_ties'] for o in out), eps_flips=sum(o['eps_flips'] for o in out),
           eps_flips_among_above=sum(o['eps_flips_among_above'] for o in out),
           runs_schedule_identical_to_stored_E1=sum(1 for o in out if o['epochs_schedule_differs_from_stored_E1'] == 0),
           runs_compared_to_stored_E1=sum(1 for o in out if o['epochs_schedule_differs_from_stored_E1'] is not None))
env = dict(python=sys.version)
for mod in ('numpy', 'scipy', 'sklearn', 'pandas'):
    try:
        env[mod] = __import__(mod).__version__
    except Exception:  # pragma: no cover
        env[mod] = None
try:  # the commit of the code under test, when it is a git checkout (never an absolute local path)
    import subprocess
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None
except Exception:  # pragma: no cover
    head = None
json.dump(dict(runs=out, totals=tot, environment=env, code_root_arg=ROOT, code_git_head=head), open(OUT, 'w'), indent=1)
print(tot)
