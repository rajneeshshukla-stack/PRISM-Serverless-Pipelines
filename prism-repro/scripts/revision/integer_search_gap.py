#!/usr/bin/env python3
"""Optimality gap of PRISM's one-parameter capacity family (R2.13; also R2.5, R4.1, R7.1).

Reviewer 2 asks us to quantify the loss from evaluating a one-parameter family of capacity
vectors P_s = ceil(y d_s / 60) rather than searching per-stage integers. This runs integer
coordinate descent from PRISM's own chosen vector, under the paper's feasibility rule (share
of scenarios with v <= eps at least 1 - delta), and reports the cost gap.

The gap is a LOWER bound: coordinate descent finds a local optimum. The comparison is static
and per-epoch; it shows cheaper feasible vectors exist, not what that is worth over a week.
The searched vector is an offline benchmark, not an implementable policy.

Usage: python integer_search_gap.py <code_root> <out.json>
"""
import json
import os
import sys

import numpy as np

if __name__ == '__main__':  # importable as a module; argv is only read when run directly
    sys.path.insert(0, os.path.join(sys.argv[1], 'src'))
from prism_repro.config import PipelineConfig, PrismConfig          # noqa: E402
from prism_repro.forecast import scenarios                          # noqa: E402
from prism_repro.latency import gb, init_mean, miss_table, stage_means  # noqa: E402
from prism_repro.optimizer import ChanceConstrainedOptimizer        # noqa: E402
from prism_repro.risk import overflow_prob                          # noqa: E402

CFG = PipelineConfig()
MT = miss_table(CFG)
EPS_GRID = (0.005, 0.01, 0.02, 0.05)
MEMS = (1024, 2048)
DEMANDS = ([400.0, 600.0, 900.0, 1200.0], [800.0, 1000.0, 1500.0, 2000.0])


def eval_P(P, m, scen, kappa, pc, cfg=CFG, r=0.8):
    """Mean epoch cost and feasible-scenario share of an arbitrary integer vector P.

    Mirrors ChanceConstrainedOptimizer.evaluate() for a single candidate; the agreement is
    asserted by tests.test_controller.TestIntegerSearchEvaluator.
    """
    P = np.asarray(P, float)
    D = stage_means(cfg, m)
    lam = np.asarray(scen, float)
    use_ceff = pc.use_ceff if pc.risk_model == "occupancy" else False
    c = lam[:, None] * D[None, :] / 60.0
    f = overflow_prob(P[None, :], c, pc.risk_model, use_ceff)
    p_c = 1.0 - np.prod(1.0 - kappa * f, axis=-1)
    v = (1.0 - p_c) * MT[m][0] + p_c * MT[m][1]
    feas = float(np.mean(v <= pc.eps))
    tau, g, pr = cfg.epoch_min * 60.0, gb(m), cfg.prices
    n = (r * lam * cfg.epoch_min)[:, None]
    cost = (P[None, :] * g * tau * pr.pc
            + n * (1 - f) * D[None, :] * g * pr.pcd
            + n * f * D[None, :] * g * pr.od
            + kappa * n * f * init_mean(cfg, m) * g * pr.od).sum(-1) + cfg.n_stages * n[:, 0] * pr.req
    return float(cost.mean()), feas


def coord_search(P0, m, scen, kappa, pc, cfg=CFG, r=0.8, radius=4, rounds=12):
    """Integer coordinate descent from P0, never leaving the feasible set."""
    P = np.array(P0, float).copy()
    best_c, _ = eval_P(P, m, scen, kappa, pc, cfg, r)
    thr = 1 - pc.delta - 1e-12
    for _ in range(rounds):
        improved = False
        for s in range(len(P)):
            for dlt in range(-radius, radius + 1):
                if dlt == 0:
                    continue
                Q = P.copy()
                Q[s] = max(0.0, Q[s] + dlt)
                c, f = eval_P(Q, m, scen, kappa, pc, cfg, r)
                if f >= thr and c < best_c - 1e-12:
                    P, best_c, improved = Q, c, True
        if not improved:
            break
    return P, best_c


def main():
    out_path = sys.argv[2]
    rows = []
    for eps in EPS_GRID:
        pc = PrismConfig(eps=eps)
        opt = ChanceConstrainedOptimizer(CFG, pc, 0.8)
        for m in MEMS:
            for q in DEMANDS:
                sc = scenarios(np.array(q), 100)
                d = opt.decide(sc, (m,), 0.35)
                c0, _ = eval_P(d.P, m, sc, 0.35, pc)
                P1, c1 = coord_search(d.P, m, sc, 0.35, pc)
                rows.append(dict(eps=eps, mem=m, demand=q,
                                 prism_P=[int(x) for x in d.P], prism_cost=c0,
                                 searched_P=[int(x) for x in P1], searched_cost=c1,
                                 gap=(c0 - c1) / c0 if c0 > 0 else float('nan')))
                print(f"eps={eps} m={m} gap={100*rows[-1]['gap']:.3f}%", flush=True)
    gaps = [r['gap'] for r in rows if np.isfinite(r['gap'])]
    tot = dict(configurations=len(gaps), max_gap=max(gaps), mean_gap=float(np.mean(gaps)),
               min_gap=min(gaps))
    json.dump(dict(rows=rows, totals=tot, environment=sys.version), open(out_path, 'w'), indent=1)
    print(tot)


if __name__ == '__main__':
    main()
