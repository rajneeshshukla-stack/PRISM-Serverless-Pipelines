#!/usr/bin/env python3
"""Stage 2.2 POST HOC E4b, part 2: on-demand execution (no provisioned concurrency) at 2048 and 3008 MB in the memory
regimes of Table IX (stationary test week). Same environment and conventions as e4b_fixed_memory.py.
Usage: python e4b_ondemand.py <code_root> <out.jsonl> <seed>"""
import dataclasses, json, os, sys
ROOT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
REGIMES = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
f = open(OUT, 'w'); bundles = {}
for ns, D in REGIMES:
    if ns not in bundles:
        bundles[ns] = TraceBundle(SEED, PipelineConfig().with_(nonscaling=ns), scenarios=('stationary',))
    b = bundles[ns]
    for mem in (2048, 3008):
        ctx = dataclasses.replace(b.context('stationary', 'test'), cfg=b.cfg.with_(deadline=D, default_mem=mem), _Kweek={})
        s = simulate(ctx, make_policy(dict(family='OnDemand')))['summary']
        f.write(json.dumps(dict(seed=SEED, nonscaling=ns, deadline=D, mem=mem, label=f'OnDemand{mem}',
                                cost=float(s['cost']), violating_window_rate=float(s['violating_window_rate']))) + '\n')
f.close()
