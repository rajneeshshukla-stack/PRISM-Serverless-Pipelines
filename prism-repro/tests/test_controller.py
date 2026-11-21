"""Controller tests: quantile ordering (C08), conformal behaviour, optimiser semantics,
zero demand, hysteresis drain (C07), features without look-ahead."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig, PrismConfig  # noqa: E402
from prism_repro.features import FeatureBuilder, window_peak_target  # noqa: E402
from prism_repro.forecast import ConformalScaler, calibrate, scenarios  # noqa: E402
from prism_repro.latency import gb, init_mean, miss_table, stage_means  # noqa: E402
from prism_repro.optimizer import ChanceConstrainedOptimizer  # noqa: E402
from prism_repro.risk import c_eff, occupancy_overflow, overflow_prob  # noqa: E402


class TestQuantileOrdering(unittest.TestCase):
    def test_C08_all_offsets_monotone(self):
        rng = np.random.default_rng(0)
        for _ in range(200):
            q = np.sort(rng.uniform(0, 1000, 4))
            for s in np.linspace(-0.3, 0.8, 23):
                qc = calibrate(q[None, :], np.array([s]))[0]
                self.assertTrue(np.all(np.diff(qc) >= 0))
                sc = scenarios(qc, 100)
                self.assertTrue(np.all(np.diff(sc) >= 0) and np.all(sc >= 0))

    def test_upper_far_below_median(self):
        q = np.array([100.0, 500.0, 20.0, 30.0])  # upper quantiles far below the median
        qc = calibrate(q[None, :], np.array([-0.3]))[0]
        self.assertTrue(np.all(np.diff(qc) >= 0))
        self.assertTrue(np.all(np.diff(scenarios(qc)) >= 0))


class TestConformal(unittest.TestCase):
    def test_long_run_miss_rate_near_target(self):
        rng = np.random.default_rng(1)
        n = 30000
        y = rng.exponential(100, n)
        q_raw = np.tile([10.5, 69.3, 230.3, 300.0], (n, 1))  # q99 too low (true 460.5)
        q, s, _ = ConformalScaler().run(q_raw, y)
        miss = np.mean(y[5000:] > q[5000:, 3])
        self.assertLess(abs(miss - 0.01), 0.006)

    def test_delay_two_epochs(self):
        """A miss at epoch 3 may affect the offset used at epoch 5 but not at epochs <= 4
        (hits also move the offset by -gamma*0.01, so compare against a no-miss run)."""
        n = 10
        q_raw = np.ones((n, 4))
        y_hit = np.zeros(n)
        y_miss = y_hit.copy()
        y_miss[3] = 1e9
        _, s_hit, _ = ConformalScaler(delay=2).run(q_raw, y_hit)
        _, s_miss, _ = ConformalScaler(delay=2).run(q_raw, y_miss)
        np.testing.assert_array_equal(s_hit[:5], s_miss[:5])
        self.assertAlmostEqual(s_miss[5] - s_hit[5], 0.05)

    def test_clipping(self):
        n = 400
        q_raw = np.ones((n, 4))
        _, s, _ = ConformalScaler().run(q_raw, np.full(n, 1e9))
        self.assertAlmostEqual(s.max(), 0.8)
        _, s, _ = ConformalScaler().run(q_raw, np.zeros(n))
        self.assertGreaterEqual(s.min(), -0.3)





class TestIntegerSearchEvaluator(unittest.TestCase):
    """R2.13: the standalone evaluator used by scripts/revision/integer_search_gap.py must
    agree with ChanceConstrainedOptimizer.evaluate(). Every reported optimality gap depends
    on it; silent drift would make those numbers meaningless."""

    def test_matches_optimizer_evaluate(self):
        import os
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "revision"))
        from integer_search_gap import eval_P

        cfg = PipelineConfig()
        rng = np.random.default_rng(11)
        for eps in (0.01, 0.05):
            pc = PrismConfig(eps=eps)
            opt = ChanceConstrainedOptimizer(cfg, pc, 0.8)
            for _ in range(3):
                q = np.sort(rng.uniform(300, 1400, 4))
                sc = scenarios(q, 60)
                for m in (1024, 2048):
                    d = opt.decide(sc, (m,), 0.35)
                    ev = opt.evaluate(sc, (m,), 0.35)
                    j = int(np.argmin(np.abs(np.asarray(ev["ys"]) - d.level)))
                    cost, feas = eval_P(d.P, m, sc, 0.35, pc, cfg)
                    self.assertAlmostEqual(cost, float(ev["cost"][0, j]), places=9)
                    self.assertAlmostEqual(feas, float(ev["feas"][0, j]), places=9)


class TestStageDemandEvaluator(unittest.TestCase):
    """Phase D: stage_demand_gap.eval_phi must reduce exactly to integer_search_gap.eval_P at
    phi = (1,...,1). That pins the stage-specific-demand probe to the evaluator already
    validated against the optimiser."""

    def test_unit_phi_matches_common_demand_evaluator(self):
        import os
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "revision"))
        from integer_search_gap import eval_P
        from stage_demand_gap import eval_phi

        cfg = PipelineConfig()
        rng = np.random.default_rng(23)
        ones = [1.0] * cfg.n_stages
        for eps in (0.01, 0.05):
            pc = PrismConfig(eps=eps)
            for _ in range(3):
                sc = scenarios(np.sort(rng.uniform(300, 1400, 4)), 60)
                P = np.ceil(rng.uniform(5, 90, cfg.n_stages))
                for m in (1024, 2048):
                    a = eval_P(P, m, sc, 0.35, pc, cfg)
                    b = eval_phi(P, m, sc, 0.35, pc, ones, cfg)
                    self.assertAlmostEqual(a[0], b[0], places=9)
                    self.assertAlmostEqual(a[1], b[1], places=9)

class TestDefaultRiskModel(unittest.TestCase):
    """R4.9: Supplement S6 recommends Erlang-B while the submitted main configuration used
    Eq. (5). This guards against silently reverting that."""

    def test_main_configuration_uses_erlangb(self):
        self.assertEqual(PrismConfig().risk_model, "erlangb")

class TestEpsMonotonicity(unittest.TestCase):
    """R5.M5: with infeasible candidates ranked by violation quantile, tightening eps
    must not buy less capacity, cost less, or violate more (Table IX regime, D = 13 s,
    memory fixed). Under the previous cost tie-break the trade-off reversed below the
    warm miss probability of every size."""

    def test_tightening_eps_is_monotone(self):
        cfg = PipelineConfig(deadline=13.0)
        q = np.array([400.0, 600.0, 900.0, 1200.0])
        sc = scenarios(q, 100)
        eps_grid = (0.08, 0.05, 0.02, 0.01, 0.005)
        cap, cost, excess = [], [], []
        for eps in eps_grid:
            d = ChanceConstrainedOptimizer(cfg, PrismConfig(eps=eps), 0.8).decide(sc, (1024,), 0.35)
            cap.append(int(d.P.sum()))
            cost.append(float(d.exp_cost))
            excess.append(float(d.excess))
        for a, b, ea, eb in zip(cap, cap[1:], eps_grid, eps_grid[1:]):
            self.assertGreaterEqual(b, a, f"capacity fell when eps tightened {ea} -> {eb}: {a} -> {b}")
        for a, b, ea, eb in zip(cost, cost[1:], eps_grid, eps_grid[1:]):
            self.assertGreaterEqual(b + 1e-9, a, f"cost fell when eps tightened {ea} -> {eb}: {a} -> {b}")
        self.assertLess(max(excess), 0.05, f"violation when infeasible too large: {excess}")

    def test_infeasible_prefers_least_violating(self):
        """The fallback must not pick a cheap, badly-violating candidate."""
        cfg = PipelineConfig(deadline=13.0)
        sc = scenarios(np.array([400.0, 600.0, 900.0, 1200.0]), 100)
        d = ChanceConstrainedOptimizer(cfg, PrismConfig(eps=0.005), 0.8).decide(sc, (1024,), 0.35)
        self.assertFalse(d.feasible)
        self.assertLess(d.excess, 0.02, "fallback chose a badly-violating candidate")

def reference_decide(cfg, pc, scen, mems, kappa, r):
    """Scalar loop implementation of §4.4 used as an oracle."""
    mt = miss_table(cfg)
    best, best_key, fb, fb_key = None, None, None, None
    tau = cfg.epoch_min * 60.0
    pr = cfg.prices
    for m in mems:
        d = stage_means(cfg, m)
        lo, hi = pc.level_lo * min(scen), pc.level_hi * max(scen)
        ys = [0.0] + list(np.linspace(lo, hi, pc.n_levels))
        for y in ys:
            P = [math.ceil(y * ds / 60.0 - 1e-9) for ds in d]
            ok, cost, vs = 0, 0.0, []
            for lam in scen:
                pnc = 1.0
                cst = 0.0
                n = r * lam * cfg.epoch_min
                for s, ds in enumerate(d):
                    f = float(overflow_prob(P[s], lam * ds / 60.0, pc.risk_model,
                                            pc.use_ceff if pc.risk_model == "occupancy" else False))
                    pnc *= 1 - kappa * f
                    cst += (P[s] * gb(m) * tau * pr.pc + n * (1 - f) * ds * gb(m) * pr.pcd
                            + n * f * ds * gb(m) * pr.od + kappa * n * f * init_mean(cfg, m) * gb(m) * pr.od)
                cst += cfg.n_stages * n * pr.req
                v = pnc * mt[m][0] + (1 - pnc) * mt[m][1]
                vs.append(v)
                ok += v <= pc.eps
                cost += cst
            frac, cost = ok / len(scen), cost / len(scen)
            iq = min(len(scen) - 1, max(0, math.ceil((1 - pc.delta) * len(scen)) - 1))
            vq = vs[iq]
            if frac >= 1 - pc.delta - 1e-12 and (best_key is None or cost < best_key):
                best, best_key = (tuple(P), m), cost
            if fb_key is None or (-vq, -cost) > fb_key:
                fb, fb_key = (tuple(P), m), (-vq, -cost)
    return (best, True) if best is not None else (fb, False)


class TestOptimizer(unittest.TestCase):
    def setUp(self):
        self.cfg = PipelineConfig()

    def test_matches_scalar_reference(self):
        rng = np.random.default_rng(2)
        for eps in (0.005, 0.02, 0.08):
            pc = PrismConfig(eps=eps, n_scenarios=20)
            opt = ChanceConstrainedOptimizer(self.cfg, pc, 0.8)
            for _ in range(4):
                q = np.sort(rng.uniform(100, 1500, 4))
                sc = scenarios(q, 20)
                for mems in [(1024,), self.cfg.mem_options]:
                    kappa = rng.uniform(0.1, 1)
                    d = opt.decide(sc, mems, kappa)
                    (P, m), feas = reference_decide(self.cfg, pc, sc, mems, kappa, 0.8)
                    self.assertEqual((tuple(int(x) for x in d.P), d.mem, d.feasible), (P, m, feas))

    def test_zero_demand_no_provisioning(self):
        opt = ChanceConstrainedOptimizer(self.cfg, PrismConfig(eps=0.02), 0.8)
        d = opt.decide(np.zeros(100), self.cfg.mem_options, 0.35)
        self.assertTrue(np.all(d.P == 0) and d.feasible and d.mem == 1024)

    def test_infeasible_flag_and_cap(self):
        pc = PrismConfig(eps=0.001, cap=5)  # v_w(1024)=0.2% > eps at fixed memory -> infeasible
        opt = ChanceConstrainedOptimizer(self.cfg, pc, 0.8)
        d = opt.decide(scenarios(np.array([500, 600, 700, 800.])), (1024,), 0.5)
        self.assertFalse(d.feasible)
        self.assertGreater(d.excess, 0)
        self.assertTrue(np.all(d.P <= 5))

    def test_quantile_mode_feasibility_equivalence(self):
        """§4.3: with v monotone in demand, scenario feasibility == check at the 1-delta scenario."""
        rng = np.random.default_rng(3)
        for _ in range(20):
            q = np.sort(rng.uniform(50, 2000, 4))
            sc = scenarios(q, 100)
            k = rng.uniform(0.1, 1)
            for eps in (0.005, 0.02, 0.05):
                a = ChanceConstrainedOptimizer(self.cfg, PrismConfig(eps=eps), 0.8).evaluate(sc, (1024, 2048), k)
                b = ChanceConstrainedOptimizer(self.cfg, PrismConfig(eps=eps, feasibility_mode="quantile"),
                                               0.8).evaluate(sc, (1024, 2048), k)
                np.testing.assert_array_equal(a["feas"] >= 0.9 - 1e-12, b["feas"] >= 0.9 - 1e-12)

    def test_cost_not_monotone_in_P(self):
        """§3.5: above the break-even utilisation more capacity can be cheaper."""
        pc = PrismConfig(eps=0.5, n_scenarios=10)
        opt = ChanceConstrainedOptimizer(self.cfg, pc, 1.0)
        # wide demand grid (0.5*1000 .. 1.15*3000) so capacity passes the break-even
        ev = opt.evaluate(np.array([1000.0] * 9 + [3000.0]), (1024,), 1.0)
        cost = ev["cost"][0]
        self.assertTrue(np.any(np.diff(cost) < 0) and np.any(np.diff(cost) > 0))


class TestHysteresis(unittest.TestCase):
    def test_C07_pools_drain(self):
        for P0 in range(1, 11):
            P, k = P0, 0
            while P > 0:
                P = math.floor(0.85 * P)
                k += 1
            self.assertLessEqual(k, 8)
        P, k = 10, 0
        while P > 0:
            P, k = math.floor(0.85 * P), k + 1
        self.assertEqual(k, 8)


class TestFeatures(unittest.TestCase):
    def test_target(self):
        N = np.arange(30)
        y = window_peak_target(N)
        self.assertEqual(y[0], 6)
        self.assertEqual(y[10], 16)
        self.assertTrue(np.isnan(y[-1]))

    def test_no_lookahead(self):
        rng = np.random.default_rng(4)
        N = rng.poisson(500, 5000)
        t = 3000
        fa = FeatureBuilder(N, [0, 1, 30]).matrix(np.array([t]))[0]
        N2 = N.copy()
        N2[t + 1:] = rng.poisson(5000, len(N) - t - 1)
        fb = FeatureBuilder(N2, [0, 1, 30]).matrix(np.array([t]))[0]
        np.testing.assert_allclose(fa, fb)

    def test_zero_demand_floor(self):
        N = np.zeros(4000, int)
        X, lev = FeatureBuilder(N, [0, 1, 30]).matrix(np.array([3500]))
        self.assertTrue(np.all(np.isfinite(X)) and lev[0] == 1.0)


class TestLagHorizon(unittest.TestCase):
    """R1.3 / R4.3 / R5.M2 (disclosed issue M1): the forecast horizon and the conformal
    feedback delay follow cfg.lag_min, so lag sweeps at L = 5 and 10 stay free of
    look-ahead. At the default L = 2 both equal the submitted values."""

    def test_horizon_and_delay_follow_lag(self):
        from prism_repro.features import forecast_horizon, min_feedback_delay
        base = PipelineConfig()
        self.assertEqual(forecast_horizon(base), (2, 6))
        self.assertEqual(min_feedback_delay(base), PrismConfig().conformal_delay_epochs)
        self.assertEqual(forecast_horizon(base.with_(lag_min=5)), (5, 9))
        self.assertEqual(forecast_horizon(base.with_(lag_min=10)), (10, 14))
        for L in range(0, 16):   # brute force: first j with 5(k+j) - L >= 5k + 4
            j = next(j for j in range(1, 10) if 5 * j - L >= 4)
            self.assertEqual(min_feedback_delay(base.with_(lag_min=L)), j, L)
        self.assertEqual(min_feedback_delay(base.with_(lag_min=10)), 3)

    def test_target_and_features_at_lag_10(self):
        from prism_repro.features import online_features
        rng = np.random.default_rng(8)
        N = rng.poisson(400, 5000)
        h = (10, 14)
        fb = FeatureBuilder(N, [0, 1, 30], horizon=h)
        for t in (1600, 2500, 4000):
            self.assertEqual(fb.y[t], N[t + 10:t + 15].max())
        self.assertTrue(np.isnan(fb.y[len(N) - 14]) and not np.isnan(fb.y[len(N) - 15]))
        np.testing.assert_array_equal(window_peak_target(N), FeatureBuilder(N, [0, 1, 30]).y)
        for t in (1600, 3000, 4980):
            x_b, l_b = fb.matrix(np.array([t]))
            x_o, l_o = online_features(N, t, [0, 1, 30], horizon=h)
            np.testing.assert_allclose(x_b[0], x_o, rtol=1e-12)
            self.assertAlmostEqual(l_b[0], l_o)
        t = 3000   # no look-ahead at the longer horizon either
        N2 = N.copy()
        N2[t + 1:] = rng.poisson(5000, len(N) - t - 1)
        np.testing.assert_allclose(fb.matrix(np.array([t]))[0],
                                   FeatureBuilder(N2, [0, 1, 30], horizon=h).matrix(np.array([t]))[0])


if __name__ == "__main__":
    unittest.main()
