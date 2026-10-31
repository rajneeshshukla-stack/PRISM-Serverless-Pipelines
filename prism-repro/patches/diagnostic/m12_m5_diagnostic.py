#!/usr/bin/env python3
"""Stage 2.1 DIAGNOSTIC (scratch only): size of the M12 and M5 code fixes on a bounded set of runs.

Runs the same specifications with one code root (unfixed = stage2.1 branch, or fixed = branch
stage2.1-m12-m5-fix) in the CURRENT Python environment and writes one JSON line per run to <out>.
Comparing the two outputs isolates the code change, because the environment, seeds and trained
forecasters are identical. Nothing is written to results/ of either code root; stored results are not
replaced. This is not the rerun of the experiments (see M12_M5_RERUN_PLAN.md).

Usage: python m12_m5_diagnostic.py <code_root> <stored_results_root> <out.jsonl> <job> [<job> ...]
jobs: E1sel  (validation-selected configuration of every family, 20 test weeks; Table V scope)
      E1valnf (validation grids of the families without a learned forecaster; checks selection changes)
      E4      (PRISM with memory, memory-regime rows of Table IX)
      E6      (PRISM under capacity caps; Supplementary Table S5)
"""
import dataclasses, json, os, sys, time

ROOT, STORED, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
JOBS = sys.argv[4:]
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy, select_by_rule, GRIDS  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS  # noqa: E402

KEYS = ('cost', 'violating_window_rate', 'record_attainment', 'late_records', 'cold_start_ratio', 'slo_met')
SEEDS = (101, 102, 103, 104, 105)


def stored_rows(exp):
    return [json.loads(l) for l in open(os.path.join(STORED, 'results', 'raw', exp, 'rows.jsonl'))]


def run(b, sc, wk, spec, cfg=None):
    ctx = b.context(sc, wk, True)
    if cfg is not None:
        ctx = dataclasses.replace(ctx, cfg=cfg, _Kweek={})
    pol = make_policy(spec, None)
    s = simulate(ctx, pol)['summary']
    return pol.label, {k: (bool(s[k]) if k == 'slo_met' else float(s[k])) for k in KEYS}


def emit(f, **row):
    f.write(json.dumps(row) + '\n'); f.flush()


def main():
    t0 = time.time()
    with open(OUT, 'w') as f:
        if 'E1sel' in JOBS or 'E1valnf' in JOBS:
            e1 = [r for r in stored_rows('E1') if r['status'] == 'ok']
            for seed in SEEDS:
                b = TraceBundle(seed, PipelineConfig())
                val = [r for r in e1 if r['seed'] == seed and r['week'] == 'val']
                if 'E1sel' in JOBS:
                    for v in sorted({r['policy'] for r in val}):
                        spec = select_by_rule([r for r in val if r['policy'] == v])['spec']
                        for sc in MAIN_SCENARIOS:
                            lab, s = run(b, sc, 'test', spec)
                            emit(f, job='E1sel', seed=seed, scenario=sc, week='test', variant=v, label=lab, spec=spec, **s)
                if 'E1valnf' in JOBS:
                    for r in val:
                        if r['spec']['family'] in ('OnDemand', 'Static', 'Scheduled', 'Reactive'):
                            lab, s = run(b, 'stationary', 'val', r['spec'])
                            emit(f, job='E1valnf', seed=seed, scenario='validation', week='val', variant=r['policy'],
                                 label=lab, spec=r['spec'], **s)
                print(f'[{seed}] E1 jobs done {time.time() - t0:.0f}s', flush=True)
        if 'E4' in JOBS:
            regimes = [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]
            for seed in (101, 102):
                bundles = {}
                for ns, D in regimes:
                    if ns not in bundles:
                        bundles[ns] = TraceBundle(seed, PipelineConfig().with_(nonscaling=ns), scenarios=('stationary',))
                    b = bundles[ns]
                    cfg = b.cfg.with_(deadline=D)
                    for e in [0.02] + ([0.01] if D == 13.0 else []):
                        lab, s = run(b, 'stationary', 'test', dict(family='PRISM', param=e), cfg)
                        emit(f, job='E4', seed=seed, scenario='stationary', week='test', variant='PRISM',
                             label=lab, tag=f'ns{ns}_D{D}', **s)
                print(f'[{seed}] E4 done {time.time() - t0:.0f}s', flush=True)
        if 'E6' in JOBS:
            for seed in SEEDS:
                b = TraceBundle(seed, PipelineConfig(), scenarios=('stationary', 'new_spike'))
                for sc in ('stationary', 'new_spike'):
                    for cap in (None, 250, 60, 40):
                        spec = dict(family='PRISM', param=0.02, tag=f'-cap{cap}', prism=dict(cap=cap))
                        lab, s = run(b, sc, 'test', spec)
                        emit(f, job='E6', seed=seed, scenario=sc, week='test', variant='PRISM', label=lab,
                             tag=f'cap{cap}', **s)
                print(f'[{seed}] E6 done {time.time() - t0:.0f}s', flush=True)
    print(f'done in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
