#!/usr/bin/env python3
"""Analysis of R2: best calibrated-quantile rule per regime (Table IX rule: per trace, cheapest grid point with
violating windows <= 2%, else least violating, ties by cost; test-week knowledge), against PRISM with memory
(best epsilon, E4b) and the best headroom rule at 1024/2048 MB (E4b). Environment check against E4b."""
import json, os, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = lambda p: [json.loads(l) for f in sorted(glob.glob(p)) for l in open(f)]
r2 = L(os.path.join(ROOT, 'results/raw/R2/r2_seed*.jsonl'))
e4b = L(os.path.join(ROOT, 'results/raw/E4b/e4b_seed*.jsonl'))
pe = L(os.path.join(ROOT, 'results/raw/E4b/e4b_prism_eps_seed*.jsonl'))

def sel(rs):
    ok = [r for r in rs if r['violating_window_rate'] <= 0.02 + 1e-12]
    return min(ok, key=lambda r: (r['cost'], r['violating_window_rate'])) if ok else min(rs, key=lambda r: (r['violating_window_rate'], r['cost']))
mean = lambda rs, k: sum(r[k] for r in rs) / len(rs)
out = []
lines = ['| alpha | D | PRISM with memory (best eps) | QP-q90 1024 | QP-q99 1024 | QP-q90 2048 | QP-q99 2048 | PredHead 1024 | PredHead 2048 | env check PRISM-0.02 (R2 vs E4b) |', '|' + '---|' * 10]
for ns, D in [(0.5, 14.5), (0.5, 13.0), (0.5, 12.0), (0.5, 11.0), (0.15, 14.5), (0.15, 12.0)]:
    seeds = [101, 102]
    g = [r for r in r2 if r['nonscaling'] == ns and r['deadline'] == D]
    h = [r for r in e4b if r['nonscaling'] == ns and r['deadline'] == D]
    rec = dict(nonscaling=ns, deadline=D)
    def best(rows, prefix):
        b = [sel([r for r in rows if r['seed'] == s and r['label'].startswith(prefix)]) for s in seeds]
        return dict(cost=mean(b, 'cost'), viol=100 * mean(b, 'violating_window_rate'), param=[x['spec']['param'] for x in b])
    for nm in ('q90', 'q99'):
        for m in (1024, 2048):
            rec[f'QP_{nm}_{m}'] = best(g, f'QuantProv_{nm}{m}-')
    for m in (1024, 2048):
        rec[f'PH_{m}'] = best(h, f'PredHead{m}-')
    bp = [sel([r for r in pe if r['seed'] == s and r['nonscaling'] == ns and r['deadline'] == D]) for s in seeds]
    rec['PRISM_best'] = dict(cost=mean(bp, 'cost'), viol=100 * mean(bp, 'violating_window_rate'), eps=[b['eps'] for b in bp])
    a = [r for r in g if r['label'] == 'PRISM-0.02']; b = [r for r in h if r['label'] == 'PRISM-0.02']
    rec['env_check'] = dict(r2=[(r['seed'], r['cost'], r['violating_window_rate']) for r in sorted(a, key=lambda r: r['seed'])],
                            e4b=[(r['seed'], r['cost'], r['violating_window_rate']) for r in sorted(b, key=lambda r: r['seed'])])
    rec['env_identical'] = rec['env_check']['r2'] == rec['env_check']['e4b']
    out.append(rec)
    c = lambda d: f"{d['cost']:,.0f} / {d['viol']:.2f}"
    lines.append(f"| {ns} | {D} | {c(rec['PRISM_best'])} | {c(rec['QP_q90_1024'])} | {c(rec['QP_q99_1024'])} | {c(rec['QP_q90_2048'])} | {c(rec['QP_q99_2048'])} | {c(rec['PH_1024'])} | {c(rec['PH_2048'])} | {'identical' if rec['env_identical'] else 'DIFFERS'} |")
os.makedirs(os.path.join(ROOT, 'results/tables'), exist_ok=True)
open(os.path.join(ROOT, 'results/tables/R2_quantprov_memory.md'), 'w').write('\n'.join(lines) + '\n')
json.dump(out, open(os.path.join(ROOT, 'results/tables/R2_quantprov_memory.json'), 'w'), indent=1)
print('\n'.join(lines))
for r in out: print(r['nonscaling'], r['deadline'], 'QP90@1024 a=', r['QP_q90_1024']['param'], 'QP90@2048 a=', r['QP_q90_2048']['param'], 'PRISM eps', r['PRISM_best']['eps'])
