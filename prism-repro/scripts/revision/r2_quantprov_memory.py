#!/usr/bin/env python3
"""POST HOC experiment R2 (31 Oct 2026): the calibrated-quantile rules in the memory regimes of Table IX.

Question: does a calibrated-quantile capacity rule, which matched PRISM's cost when only capacity matters,
also cope when latency slack disappears? Same two traces, stationary test week, and six regimes as E4/E4b.
Runs QuantProv-q90 and QuantProv-q99 over their full scale grid at 1024 MB (the rule's default) and at 2048 MB
(a larger size chosen once, offline). The best scale is chosen with test-week knowledge per trace, as for the
headroom columns of Table IX. Also re-runs one stored E4b row per regime (PRISM-0.02 with memory) as an
environment check. Released code unmodified.
Usage: python r2_quantprov_memory.py <code_root> <out.jsonl> <seed>
"""
import dataclasses, json, os, sys, time
ROOT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy, GRIDS  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402

REGIMES = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
KEYS = ('cost', 'violating_window_rate', 'record_attainment', 'share_mem_ge_2048', 'infeasible_share', 'mean_provisioned')
f = open(OUT, 'w')
bundles = {}
for ns, D in REGIMES:
    if ns not in bundles:
        bundles[ns] = TraceBundle(SEED, PipelineConfig().with_(nonscaling=ns), scenarios=('stationary',))
    b = bundles[ns]

    def run(spec, mem, label):
        cfg = b.cfg.with_(deadline=D, default_mem=mem)
        ctx = dataclasses.replace(b.context('stationary', 'test'), cfg=cfg, _Kweek={})
        t0 = time.perf_counter()
        s = simulate(ctx, make_policy(spec))['summary']
        row = dict(seed=SEED, nonscaling=ns, deadline=D, mem=mem, label=label, spec=spec,
                   runtime_s=round(time.perf_counter() - t0, 2), **{k: float(s[k]) for k in KEYS if k in s})
        f.write(json.dumps(row) + '\n'); f.flush()

    run(dict(family='PRISM', param=0.02), 1024, 'PRISM-0.02')  # environment check against E4b
    for ti, nm in ((2, 'q90'), (3, 'q99')):
        for mem in (1024, 2048):
            for a in GRIDS['QuantProv']:
                run(dict(family='QuantProv', tau_idx=ti, param=a), mem, f'QuantProv_{nm}{mem}-{a}')
    print(f'seed {SEED} ns {ns} D {D} done', flush=True)
f.close()
