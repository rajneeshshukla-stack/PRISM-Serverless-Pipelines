#!/usr/bin/env python3
"""Stage 2.2 POST HOC experiment E4b: fixed larger memory sizes in the memory regimes of Table IX.

Question (raised by the Stage 2.2 reviewer simulations): is PRISM's online joint memory sizing better than
choosing a larger memory size once, offline, and then using a simple capacity rule at that size?
For the two traces and seven regimes of E4 (stationary test week), it runs with the released, unmodified code:
  - PredHead-h, h in {1.0, ..., 2.0}, at 1024, 2048 and 3008 MB (best headroom chosen with test-week
    knowledge per trace, as for the 1024-MB column of Table IX);
  - PRISM at the regime's epsilon with memory fixed at 2048 MB and at 3008 MB;
  - and, as an environment check, the stored E4 configurations (PRISM with memory, PRISM fixed at 1024 MB,
    PredHead at 1024 MB, on-demand) re-run in the current environment.
Environment: current workspace (Python 3.13, scikit-learn 1.9.1); the stored E4 runs used scikit-learn 1.8.0, so
forecast-driven runs differ slightly (library-version effect, Supplementary S1); the re-runs measure it.
Nothing is written to results/. Usage: python e4b_fixed_memory.py <code_root> <out.jsonl> <seed>
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
    base_ctx = b.context('stationary', 'test')
    eps_list = [0.02] + ([0.01] if D == 13.0 else [])

    def run(spec, mem, label):
        cfg = b.cfg.with_(deadline=D, default_mem=mem)
        ctx = dataclasses.replace(b.context('stationary', 'test'), cfg=cfg, _Kweek={})
        t0 = time.perf_counter()
        s = simulate(ctx, make_policy(spec))['summary']
        row = dict(seed=SEED, nonscaling=ns, deadline=D, mem=mem, label=label, spec=spec,
                   runtime_s=round(time.perf_counter() - t0, 2), **{k: float(s[k]) for k in KEYS if k in s})
        f.write(json.dumps(row) + '\n'); f.flush()

    for e in eps_list:
        run(dict(family='PRISM', param=e), 1024, f'PRISM-{e}')                       # stored column, re-run
        for mem in (1024, 2048, 3008):
            run(dict(family='PRISM', param=e, tag='-fixedmem', prism=dict(optimise_memory=False)), mem,
                f'PRISM-fixedmem{mem}-{e}')
    run(dict(family='OnDemand'), 1024, 'OnDemand')
    for mem in (1024, 2048, 3008):
        for h in GRIDS['PredHead']:
            run(dict(family='PredHead', param=h), mem, f'PredHead{mem}-{h}')
    print(f'seed {SEED} ns {ns} D {D} done', flush=True)
f.close()
