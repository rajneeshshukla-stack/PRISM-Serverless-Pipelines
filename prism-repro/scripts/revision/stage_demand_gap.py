#!/usr/bin/env python3
"""Optimality gap of the one-parameter family under stage-specific demand (Phase D; R4.1, R2.5).

Reviewer 4: "Either test the optimizer where this fails, or present PRISM as one rule among
the families and adjust the title and contributions. Stage specific demand would be one such
test."

The paper models a pipeline in which every stage sees the same demand, so P_s proportional to
d_s is nearly optimal and the optimizer has little to choose. Real data pipelines filter, fan
out and batch. This applies a per-stage demand multiplier phi_s to concurrency and execution
counts, and compares the cheapest feasible member of PRISM's one-parameter family against
integer coordinate descent.

Static and per-epoch; coordinate descent gives a LOWER bound on the gap. The phi profiles are
illustrative, not measured. Implementing stage-specific demand properly requires a model change
through workload.py, simulator.py and des.py.

Usage: python stage_demand_gap.py <code_root> <out.json>
"""
import json
import os
import sys

import numpy as np

if __name__ == '__main__':  # importable as a module; argv only read when run directly
    sys.path.insert(0, os.path.join(sys.argv[1], 'src'))
from prism_repro.config import PipelineConfig, PrismConfig          # noqa: E402
from prism_repro.forecast import scenarios                          # noqa: E402
from prism_repro.latency import gb, init_mean, miss_table, stage_means  # noqa: E402
from prism_repro.optimizer import ChanceConstrainedOptimizer        # noqa: E402
from prism_repro.risk import overflow_prob                          # noqa: E402

CFG = PipelineConfig()
MT = miss_table(CFG)
PHIS = {
    'common': [1.0, 1.0, 1.0, 1.0],            # what the paper models
    'filter_half_at_2': [1.0, 1.0, 0.5, 0.5],  # stage 2 drops half the records
    'fanout_x3_at_3': [1.0, 1.0, 3.0, 3.0],    # stage 3 expands each record
    'batch_10to1_at_4': [1.0, 1.0, 1.0, 0.1],  # stage 4 batches 10:1
}
EPS_GRID = (0.01, 0.02, 0.05)
DEMAND = [400.0, 600.0, 900.0, 1200.0]
# Grid-bound control: level_hi is the paper's candidate upper bound (default 1.15 x max
# scenario). When the family is infeasible at the default, widening it separates a structural
# limit of the proportional restriction from an artifact of the candidate grid.
LEVEL_HI_SWEEP = (2.0, 4.0, 8.0)


def eval_phi(P, m, scen, kappa, pc, phi, cfg=CFG, r=0.8):
    """Mean epoch cost and feasible-scenario share with stage s seeing lambda*phi_s records.

    At phi = (1,...,1) this must equal integer_search_gap.eval_P; asserted by
    tests.test_controller.TestStageDemandEvaluator.
    """
    P = np.asarray(P, float)
    D = stage_means(cfg, m)
    lam = np.asarray(scen, float)
    phi = np.asarray(phi, float)
    use_ceff = pc.use_ceff if pc.risk_model == "occupancy" else False
    c = (lam[:, None] * phi[None, :]) * D[None, :] / 60.0
    f = overflow_prob(P[None, :], c, pc.risk_model, use_ceff)
    p_c = 1.0 - np.prod(1.0 - kappa * f, axis=-1)
    v = (1.0 - p_c) * MT[m][0] + p_c * MT[m][1]
    feas = float(np.mean(v <= pc.eps))
    tau, g, pr = cfg.epoch_min * 60.0, gb(m), cfg.prices
    n = (r * lam * cfg.epoch_min)[:, None] * phi[None, :]
    cost = (P[None, :] * g * tau * pr.pc
            + n * (1 - f) * D[None, :] * g * pr.pcd
            + n * f * D[None, :] * g * pr.od
            + kappa * n * f * init_mean(cfg, m) * g * pr.od).sum(-1) + (n * pr.req).sum(-1)
    return float(cost.mean()), feas


def family_best(m, scen, kappa, pc, phi, cfg=CFG, r=0.8):
    """Cheapest feasible member of PRISM's one-parameter family under phi."""
    ys = ChanceConstrainedOptimizer(cfg, pc, r).candidates(np.asarray(scen, float))
    D = stage_means(cfg, m)
    best_c, best_P = np.inf, None
    for y in ys:
        P = np.ceil(y * D / 60.0 - 1e-9)
        c, f = eval_phi(P, m, scen, kappa, pc, phi, cfg, r)
        if f >= 1 - pc.delta - 1e-12 and c < best_c:
            best_c, best_P = c, P
    return best_c, best_P


def search(P0, m, scen, kappa, pc, phi, cfg=CFG, r=0.8, radius=5, rounds=14):
    P = np.array(P0, float).copy()
    best, _ = eval_phi(P, m, scen, kappa, pc, phi, cfg, r)
    thr = 1 - pc.delta - 1e-12
    for _ in range(rounds):
        improved = False
        for s in range(len(P)):
            for d in range(-radius, radius + 1):
                if d == 0:
                    continue
                Q = P.copy()
                Q[s] = max(0.0, Q[s] + d)
                c, f = eval_phi(Q, m, scen, kappa, pc, phi, cfg, r)
                if f >= thr and c < best - 1e-12:
                    P, best, improved = Q, c, True
        if not improved:
            break
    return P, best


def main():
    out_path = sys.argv[2]
    rows = []
    for name, phi in PHIS.items():
        for eps in EPS_GRID:
            pc = PrismConfig(eps=eps)
            sc = scenarios(np.array(DEMAND), 100)
            c0, P0 = family_best(1024, sc, 0.35, pc, phi)
            if P0 is None:
                # Grid-bound control: widen level_hi until a feasible family member exists.
                sweep = []
                for lh in LEVEL_HI_SWEEP:
                    pc2 = PrismConfig(eps=eps, level_hi=lh)
                    c2, P2 = family_best(1024, sc, 0.35, pc2, phi)
                    if P2 is None:
                        sweep.append(dict(level_hi=lh, family_feasible=False))
                        continue
                    P3, c3 = search(P2, 1024, sc, 0.35, pc2, phi)
                    sweep.append(dict(level_hi=lh, family_feasible=True,
                                      family_P=[int(x) for x in P2], family_cost=c2,
                                      searched_P=[int(x) for x in P3], searched_cost=c3,
                                      gap=(c2 - c3) / c2))
                rows.append(dict(profile=name, eps=eps, family_feasible=False,
                                 default_level_hi=pc.level_hi, level_hi_sweep=sweep))
                got = [r for r in sweep if r.get('family_feasible')]
                tail = (f"; feasible at level_hi={got[0]['level_hi']} with gap "
                        f"{100*got[0]['gap']:.2f}%") if got else "; infeasible across the sweep"
                print(f"{name} eps={eps}: family INFEASIBLE at level_hi={pc.level_hi}{tail}",
                      flush=True)
                continue
            P1, c1 = search(P0, 1024, sc, 0.35, pc, phi)
            rows.append(dict(profile=name, eps=eps, family_feasible=True,
                             family_P=[int(x) for x in P0], family_cost=c0,
                             searched_P=[int(x) for x in P1], searched_cost=c1,
                             gap=(c0 - c1) / c0))
            print(f"{name} eps={eps}: gap {100*rows[-1]['gap']:.2f}%", flush=True)
    by = {}
    for name in PHIS:
        g = [r['gap'] for r in rows if r['profile'] == name and r.get('family_feasible')]
        widened = [w['gap'] for r in rows if r['profile'] == name
                   for w in r.get('level_hi_sweep', []) if w.get('family_feasible')]
        by[name] = dict(mean_gap=float(np.mean(g)) if g else None,
                        infeasible=sum(1 for r in rows if r['profile'] == name
                                       and not r.get('family_feasible')),
                        max_gap_after_widening=float(np.max(widened)) if widened else None)
    json.dump(dict(rows=rows, by_profile=by, environment=sys.version),
              open(out_path, 'w'), indent=1)
    print(by)


if __name__ == '__main__':
    main()
