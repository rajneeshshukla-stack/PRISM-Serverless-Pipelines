"""V1 checks for scripts/revision/optscaler_policy.py (docs/revision/optscaler_r32_20261124/PLAN.md section 3).
Hand-calculated where possible. Run from prism-repro/: venv/Scripts/python -m unittest scripts/revision/test_optscaler_policy.py
"""
import itertools
import math
import os
import sys
import types
import unittest

import numpy as np
from scipy import optimize, stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.simulator import Telemetry  # noqa: E402
import optscaler_policy as op  # noqa: E402


class V1a_MLE(unittest.TestCase):
    def test_closed_form_equals_numerical(self):
        rng = np.random.default_rng(1)
        y = rng.integers(1, 200, 400).astype(float)
        K = np.maximum(0.03 * y + rng.normal(0, 0.006 * y), 0)
        w, s = op.mle_ratio(K, y)
        res = optimize.minimize(op.neg_loglik, x0=[0.02, 0.01], args=(K, y), method="Nelder-Mead",
                                options=dict(xatol=1e-12, fatol=1e-12, maxiter=20000))
        self.assertAlmostEqual(res.x[0] / w, 1.0, delta=1e-5)
        self.assertAlmostEqual(res.x[1] / s, 1.0, delta=1e-5)

    def test_hand_example(self):
        # r = K/y = 0.1, 0.3 -> w = 0.2, sigma = 0.1 (population sd); y = 0 ignored
        w, s = op.mle_ratio(np.array([1.0, 6.0, 5.0]), np.array([10.0, 20.0, 0.0]))
        self.assertAlmostEqual(w, 0.2)
        self.assertAlmostEqual(s, 0.1)


class V1b_Decision(unittest.TestCase):
    def test_eq13(self):
        z = stats.norm.ppf(0.95)                    # 1.6449
        m = (z * 0.01 + 0.03) * 100                 # = 4.6449
        self.assertEqual(op.provision(np.array([0.03]), np.array([0.01]), 100.0, 0.5, z)[0], math.ceil(m / 0.5))
        self.assertEqual(op.provision(np.array([0.03]), np.array([0.01]), 100.0, 0.5, z)[0], 10.0)
        self.assertEqual(op.provision(np.array([0.0]), np.array([0.0]), 100.0, 0.5, z)[0], 0.0)


class V1c_HorizonIndependence(unittest.TestCase):
    def test_bruteforce_D3(self):
        c_star, ms = 0.5, [3.2, 7.9, 1.1]
        lb = [math.ceil(m / c_star) for m in ms]
        best = max(itertools.product(*[range(l, l + 6) for l in lb]),
                   key=lambda xs: sum(m / x for m, x in zip(ms, xs)))
        self.assertEqual(best[0], math.ceil(ms[0] / c_star))


class V1d_OLR(unittest.TestCase):
    def test_algorithm1_by_hand(self):
        # w = 0.03, y = 100, x = 10: u = 10, c_hat = 0.3; c = 0.4: e = -0.1; w <- 0.03 - 0.01 * (-0.1) * 10 = 0.04
        w, e = op.olr_step(0.03, 0.01, 100.0, 10.0, 0.4)
        self.assertAlmostEqual(e, -0.1)
        self.assertAlmostEqual(w, 0.04)

    def test_eta_zero_closed(self):
        w, _ = op.olr_step(0.03, 0.0, 100.0, 10.0, 0.9)
        self.assertEqual(w, 0.03)


def fake_ctx(seed=0, weeks=3):
    cfg = PipelineConfig()
    rng = np.random.default_rng(seed)
    n = weeks * 7 * 1440
    counts = rng.poisson(60, n)
    K = rng.poisson(counts[:, None] * np.array([0.02, 0.03, 0.04, 0.05])[None, :]).astype(float)
    ws = (weeks - 1) * 7 * 1440
    q = np.column_stack([counts[ws::5][:2016] * f for f in (0.8, 1.0, 1.2, 1.5)]).astype(float)
    ctx = types.SimpleNamespace(cfg=cfg, counts=counts, week_start=ws, K_hist_default=K,
                                forecasts={"gbm": dict(q_cal=q)})
    return ctx, K[ws:], counts[ws:].astype(float)


def fake_tel(Kw, Nw, P_level=5.0):
    n = len(Nw)
    return Telemetry(N=Nw.copy(), K=Kw.copy(), P=np.full((n, Kw.shape[1]), P_level), n_od=np.zeros_like(Kw),
                     cold=np.zeros_like(Kw), filled=n)


class V1e_NoLookAhead(unittest.TestCase):
    def test_perturb_future(self):
        ctx, Kw, Nw = fake_ctx()
        k = 40
        v = k * 5 - 2
        for eta in (0.0, 1e-3):
            outs = []
            for perturb in (False, True):
                pol = op.OptScaler(0.5, eta=eta)
                pol.prepare(ctx)
                tel = fake_tel(Kw, Nw)
                q = ctx.forecasts["gbm"]["q_cal"].copy()
                if perturb:
                    tel.N[v + 1:] *= 7
                    tel.K[v + 1:] += 50
                    tel.P[v + 1:] = 99
                    ctx.forecasts["gbm"]["q_cal"][k + 1:] *= 3
                for kk in range(k + 1):
                    P, _ = pol.decide(kk, tel)
                ctx.forecasts["gbm"]["q_cal"][:] = q
                outs.append(P)
            np.testing.assert_array_equal(outs[0], outs[1])


class V1f_EtaSelection(unittest.TestCase):
    def test_argmin(self):
        ctx, _, _ = fake_ctx(seed=3)
        K, y = ctx.K_hist_default[:3000], ctx.counts[:3000].astype(float)
        w0, s0 = np.zeros(4), np.zeros(4)
        for s in range(4):
            w0[s], s0[s] = op.mle_ratio(K[:, s], y)
        z = stats.norm.ppf(0.95)
        best, losses = op.select_eta(K, y, w0, s0, z)
        self.assertEqual(set(losses), set(op.ETA_GRID))
        self.assertEqual(losses[best], min(losses.values()))
        self.assertAlmostEqual(losses[0.0], op.replay_loss(K, y, w0, s0, 0.0, z))


if __name__ == "__main__":
    unittest.main()
