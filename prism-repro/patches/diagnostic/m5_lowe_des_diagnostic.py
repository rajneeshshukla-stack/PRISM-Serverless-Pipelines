#!/usr/bin/env python3
"""Stage 2.1 DIAGNOSTIC (scratch only), M5 at the tightest budgets.

(a) fast simulator: PRISM at epsilon = 0.005 and 0.01, all 20 test weeks (these grid points change memory
    up to 41 and 10 times per week and enter the frontiers of Table VII);
(b) event-level simulator: replay of the STORED E1 test-week schedules of PRISM-0.005 for traces 101 and 102,
    the two traces whose event-level retuning (Table XI) selected epsilon = 0.005 (E12 replay convention:
    draw stream 3, open loop).
Run once with the unfixed and once with the fixed code root; nothing is written to results/.
Usage: python m5_lowe_des_diagnostic.py <code_root> <stored_results_root> <out.jsonl>
"""
import json, os, sys, time
import numpy as np

ROOT, STORED, OUT = sys.argv[1:4]
sys.path.insert(0, os.path.join(ROOT, 'src'))
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, simulate_events  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
from prism_repro.workload import MAIN_SCENARIOS, generate_trace  # noqa: E402

KEYS = ('cost', 'violating_window_rate', 'record_attainment', 'slo_met')
cfg = PipelineConfig()
t0 = time.time()
with open(OUT, 'w') as f:
    for seed in (101, 102, 103, 104, 105):
        b = TraceBundle(seed, cfg)
        for eps in (0.005, 0.01):
            for sc in MAIN_SCENARIOS:
                ctx = b.context(sc, 'test', True)
                s = simulate(ctx, make_policy(dict(family='PRISM', param=eps)))['summary']
                f.write(json.dumps(dict(job='fast_lowe', seed=seed, scenario=sc, eps=eps,
                                        **{k: (bool(s[k]) if k == 'slo_met' else float(s[k])) for k in KEYS})) + '\n')
        f.flush(); print(f'[{seed}] fast done {time.time() - t0:.0f}s', flush=True)
    for seed in (101, 102):
        arr = np.load(os.path.join(STORED, 'results', 'raw', 'E1', f'arrays_seed{seed}.npz'))
        for sc in MAIN_SCENARIOS:
            tc = generate_trace(seed, sc)['counts'][21 * 1440:28 * 1440]
            key = f'E1|{seed}|{sc}|test|PRISM-0.005|'
            m_ep = arr[key + '::mem_epoch']
            s = simulate_events(cfg, EventDraws(cfg, tc, seed, 3), arr[key + '::P_epoch'], m_ep)['summary']
            f.write(json.dumps(dict(job='des_replay', seed=seed, scenario=sc, eps=0.005,
                                    switches=int((m_ep[1:] != m_ep[:-1]).sum()),
                                    **{k: (bool(s[k]) if k == 'slo_met' else float(s[k])) for k in KEYS})) + '\n')
            f.flush(); print(f'[{seed}] des {sc} done {time.time() - t0:.0f}s', flush=True)
print('done', flush=True)

# (c) M12: forecast-driven validation runs whose stored violating-window rate lies within one window (0.15 points)
# of the 2 % selection threshold; if their rates do not change, no validation selection can change.
NEAR = [(101, 'PredHead', dict(family='PredHead')), (101, 'PredHead+hyst', dict(family='PredHead', hyst=True)),
        (101, 'QuantProv_q90', dict(family='QuantProv', tau_idx=2)), (102, 'PredHead+hyst', dict(family='PredHead', hyst=True)),
        (102, 'PRISM', dict(family='PRISM')), (103, 'QuantProv_q90', dict(family='QuantProv', tau_idx=2)),
        (105, 'PredHead+hyst', dict(family='PredHead', hyst=True))]
rows = [json.loads(l) for l in open(os.path.join(STORED, 'results', 'raw', 'E1', 'rows.jsonl'))]
with open(OUT, 'a') as f:
    bundles = {}
    for seed, pol, base in NEAR:
        cand = [r for r in rows if r['seed'] == seed and r['week'] == 'val' and r['policy'] == pol
                and 0.02 - 0.0015 < r['violating_window_rate'] <= 0.02 + 1e-12]
        for r in cand:
            if seed not in bundles:
                bundles = {seed: TraceBundle(seed, cfg)}
            ctx = bundles[seed].context('stationary', 'val', True)
            s = simulate(ctx, make_policy(r['spec']))['summary']
            f.write(json.dumps(dict(job='near_threshold_val', seed=seed, policy=pol, label=r['label'],
                                    stored_viol=r['violating_window_rate'],
                                    **{k: (bool(s[k]) if k == 'slo_met' else float(s[k])) for k in KEYS})) + '\n')
            f.flush(); print(f'[{seed}] near-threshold {r["label"]} done {time.time() - t0:.0f}s', flush=True)
print('done (c)', flush=True)
