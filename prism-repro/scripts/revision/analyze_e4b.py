#!/usr/bin/env python3
"""Summarize E4b (post hoc fixed-memory comparators) per memory regime, mean over the two traces, with the same
best-headroom rule as Table IX (per trace: cheapest grid point with violating windows <= 2%, else least violating,
ties by cost; chosen with test-week knowledge). Also compares the re-runs of stored columns with the stored E4 rows.
Inputs: the outputs of e4b_fixed_memory.py, e4b_ondemand.py and e4b_prism_eps.py (all seeds).
Usage: python analyze_e4b.py <stored_E4_rows.jsonl> <out.json> <jsonl> [...]"""
import json, sys
from collections import defaultdict
stored_path, out_path, files = sys.argv[1], sys.argv[2], sys.argv[3:]
allrows = [json.loads(l) for f in files for l in open(f)]
rows = [r for r in allrows if 'spec' in r]
od = [r for r in allrows if r['label'].startswith('OnDemand') and 'spec' not in r]
pe = [r for r in allrows if 'eps' in r and 'spec' not in r]
stored = [json.loads(l) for l in open(stored_path)]

def sel(rs):
    ok = [r for r in rs if r['violating_window_rate'] <= 0.02 + 1e-12]
    return min(ok, key=lambda r: (r['cost'], r['violating_window_rate'])) if ok else \
        min(rs, key=lambda r: (r['violating_window_rate'], r['cost']))

def mean(rs, k):
    return sum(r[k] for r in rs) / len(rs)

regimes = sorted({(r['nonscaling'], r['deadline']) for r in rows}, key=lambda x: (-x[0], -x[1]))
out = []
for ns, D in regimes:
    g = [r for r in rows if r['nonscaling'] == ns and r['deadline'] == D]
    seeds = sorted({r['seed'] for r in g})
    eps_list = sorted({r['spec']['param'] for r in g if r['spec']['family'] == 'PRISM'}, reverse=True)
    for e in eps_list:
        rec = dict(nonscaling=ns, deadline=D, eps=e)
        def cell(lbl):
            rs = [r for r in g if r['label'] == lbl]
            return dict(cost=mean(rs, 'cost'), viol=mean(rs, 'violating_window_rate') * 100,
                        share_ge2048=mean(rs, 'share_mem_ge_2048') * 100, n=len(rs))
        rec['PRISM_with_memory'] = cell(f'PRISM-{e}')
        for m in (1024, 2048, 3008):
            rec[f'PRISM_fixed_{m}'] = cell(f'PRISM-fixedmem{m}-{e}')
            best = [sel([r for r in g if r['seed'] == s and r['label'].startswith(f'PredHead{m}-')]) for s in seeds]
            rec[f'best_PredHead_{m}'] = dict(cost=mean(best, 'cost'), viol=mean(best, 'violating_window_rate') * 100,
                                            h=[b['spec']['param'] for b in best])
        rec['OnDemand'] = cell('OnDemand')
        for m in (2048, 3008):
            rs = [r for r in od if r['nonscaling'] == ns and r['deadline'] == D and r['mem'] == m]
            rec[f'OnDemand_{m}'] = dict(cost=mean(rs, 'cost'), viol=mean(rs, 'violating_window_rate') * 100, n=len(rs))
        bp = [sel([r for r in pe if r['seed'] == s and r['nonscaling'] == ns and r['deadline'] == D]) for s in seeds]
        rec['best_PRISM_with_memory'] = dict(cost=mean(bp, 'cost'), viol=mean(bp, 'violating_window_rate') * 100,
                                             eps=[b['eps'] for b in bp], share_ge2048=mean(bp, 'share_mem_ge_2048') * 100)
        rec['best_PredHead_2048_vs_best_PRISM_pct'] = (1 - rec['best_PredHead_2048']['cost'] / rec['best_PRISM_with_memory']['cost']) * 100
        # stored comparison
        tag = f'ns{ns}_D{D}'
        st = [r for r in stored if r['tag'] == tag]
        def scell(label):
            rs = [r for r in st if r['label'] == label]
            return dict(cost=mean(rs, 'cost'), viol=mean(rs, 'violating_window_rate') * 100) if rs else None
        bst = [sel([r for r in st if r['seed'] == s and r['policy'] == 'PredHead']) for s in seeds]
        rec['stored'] = dict(PRISM_with_memory=scell(f'PRISM-{e}'), PRISM_fixed_1024=scell(f'PRISM-fixedmem-{e}'),
                             best_PredHead_1024=dict(cost=mean(bst, 'cost'), viol=mean(bst, 'violating_window_rate') * 100),
                             OnDemand=scell('OnDemand'))
        out.append(rec)
# per-run environment effect on the re-run stored configurations
diffs = []
for r in rows:
    tag = f"ns{r['nonscaling']}_D{r['deadline']}"
    lab = r['label']
    if lab.startswith('PredHead1024-'):
        slabel = 'PredHead-' + lab.split('-')[1]
    elif lab.startswith('PRISM-fixedmem1024-'):
        slabel = 'PRISM-fixedmem-' + lab.split('-')[-1]
    elif lab.startswith('PRISM-') and 'fixedmem' not in lab:
        slabel = lab
    elif lab == 'OnDemand':
        slabel = 'OnDemand'
    else:
        continue
    m = [s for s in stored if s['tag'] == tag and s['seed'] == r['seed'] and s['label'] == slabel]
    if m:
        diffs.append(dict(label=lab, tag=tag, seed=r['seed'], dcost_pct=(r['cost'] / m[0]['cost'] - 1) * 100,
                          dviol_pp=(r['violating_window_rate'] - m[0]['violating_window_rate']) * 100))
env = dict(n=len(diffs), max_abs_cost_pct=max(abs(d['dcost_pct']) for d in diffs),
           max_abs_viol_pp=max(abs(d['dviol_pp']) for d in diffs),
           ondemand_identical=all(abs(d['dcost_pct']) < 1e-9 and abs(d['dviol_pp']) < 1e-9 for d in diffs if d['label'] == 'OnDemand'))
json.dump(dict(regimes=out, environment_effect=env, diffs=diffs), open(out_path, 'w'), indent=1)
for rec in out:
    f = lambda c: f"{c['cost']:,.0f}/{c['viol']:.2f}"
    print(rec['nonscaling'], rec['deadline'], rec['eps'], '| PRISM mem', f(rec['PRISM_with_memory']),
          f"{rec['PRISM_with_memory']['share_ge2048']:.0f}%", '| fix1024', f(rec['PRISM_fixed_1024']),
          '| fix2048', f(rec['PRISM_fixed_2048']), '| fix3008', f(rec['PRISM_fixed_3008']),
          '| PH1024', f(rec['best_PredHead_1024']), '| PH2048', f(rec['best_PredHead_2048']), rec['best_PredHead_2048']['h'],
          '| PH3008', f(rec['best_PredHead_3008']), rec['best_PredHead_3008']['h'], '| OD', f(rec['OnDemand']))
    print('   best PRISM', f(rec['best_PRISM_with_memory']), rec['best_PRISM_with_memory']['eps'], 'PH2048 cheaper by %.1f%%' % rec['best_PredHead_2048_vs_best_PRISM_pct'],
          '| OD2048', f(rec['OnDemand_2048']), '| OD3008', f(rec['OnDemand_3008']))
    s = rec['stored']; print('   stored: PRISM mem', f(s['PRISM_with_memory']), 'fix1024', f(s['PRISM_fixed_1024']), 'PH1024', f(s['best_PredHead_1024']), 'OD', f(s['OnDemand']))
print(env)
