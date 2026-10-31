#!/usr/bin/env python3
"""Stage 2.2 POST HOC E4b, part 3: PRISM with memory optimization over its full epsilon grid in the memory regimes
of Table IX (stationary test week), so that PRISM can also be given its best case (epsilon chosen with test-week
knowledge), as the headroom rule is. Same environment and conventions as e4b_fixed_memory.py.
Usage: python e4b_prism_eps.py <code_root> <out.jsonl> <seed>"""
import dataclasses, json, os, sys
ROOT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy, GRIDS  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
REGIMES = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
KEYS = ('cost', 'violating_window_rate', 'share_mem_ge_2048', 'infeasible_share')
f = open(OUT, 'w'); bundles = {}
for ns, D in REGIMES:
    if ns not in bundles:
        bundles[ns] = TraceBundle(SEED, PipelineConfig().with_(nonscaling=ns), scenarios=('stationary',))
    b = bundles[ns]
    for e in GRIDS['PRISM']:
        ctx = dataclasses.replace(b.context('stationary', 'test'), cfg=b.cfg.with_(deadline=D), _Kweek={})
        s = simulate(ctx, make_policy(dict(family='PRISM', param=e)))['summary']
        f.write(json.dumps(dict(seed=SEED, nonscaling=ns, deadline=D, mem=1024, label=f'PRISM-{e}', eps=e,
                                **{k: float(s[k]) for k in KEYS})) + '\n'); f.flush()
    print(f'seed {SEED} ns {ns} D {D} done', flush=True)
f.close()
