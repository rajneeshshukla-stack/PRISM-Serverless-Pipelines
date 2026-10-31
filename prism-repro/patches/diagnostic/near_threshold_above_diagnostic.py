#!/usr/bin/env python3
"""Stage 2.1 DIAGNOSTIC (scratch only; round 3, after the independent verification), complement of job (c) in
m5_lowe_des_diagnostic.py.

Job (c) re-ran the forecast-driven validation runs whose stored violating-window rate lies within one window
(0.15 points) BELOW or AT the 2 % selection threshold; a fix could push them above it. A selection could also change
if a CHEAPER configuration whose stored rate lies within one window ABOVE the threshold dropped below it. This job
re-runs exactly those runs: for every trace and family, the validation runs with 2 % < rate <= 2.15 % that cost less
than the selected configuration (stored E1 rows). Run once with the unfixed and once with the fixed code root, in
the same environment; nothing is written to results/.

Usage: python near_threshold_above_diagnostic.py <code_root> <stored_results_root> <out.jsonl>
"""
import json, os, sys, time
from collections import defaultdict

ROOT, STORED, OUT = sys.argv[1:4]
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402

KEYS = ('cost', 'violating_window_rate', 'record_attainment', 'slo_met')
NONFORECAST = {'OnDemand', 'Static', 'Scheduled', 'Reactive'}
rows = [json.loads(l) for l in open(os.path.join(STORED, 'results', 'raw', 'E1', 'rows.jsonl'))]
fam = defaultdict(list)
for r in rows:
    if r['week'] == 'val':
        fam[(r['seed'], r['policy'])].append(r)
cands = []
for (seed, pol), rs in sorted(fam.items()):
    feas = [r for r in rs if r['violating_window_rate'] <= 0.02 + 1e-12]
    sel = min(feas, key=lambda r: r['cost']) if feas else None
    for r in rs:
        v = r['violating_window_rate']
        if 0.02 + 1e-12 < v <= 0.0215 + 1e-12 and (sel is None or r['cost'] < sel['cost']):
            cands.append((seed, pol, r, sel))
cfg = PipelineConfig()
t0 = time.time()
bundles = {}
with open(OUT, 'w') as f:
    for seed, pol, r, sel in cands:
        if pol in NONFORECAST:      # covered by job E1valnf of m12_m5_diagnostic.py
            continue
        if seed not in bundles:
            bundles = {seed: TraceBundle(seed, cfg)}
        ctx = bundles[seed].context('stationary', 'val', True)
        s = simulate(ctx, make_policy(r['spec']))['summary']
        f.write(json.dumps(dict(job='near_threshold_above_val', seed=seed, policy=pol, label=r['label'],
                                stored_viol=r['violating_window_rate'], stored_cost=r['cost'],
                                selected_label=sel['label'] if sel else None, selected_cost=sel['cost'] if sel else None,
                                **{k: (bool(s[k]) if k == 'slo_met' else float(s[k])) for k in KEYS})) + '\n')
        f.flush(); print(f'[{seed}] {r["label"]} done {time.time() - t0:.0f}s', flush=True)
print('done', flush=True)
