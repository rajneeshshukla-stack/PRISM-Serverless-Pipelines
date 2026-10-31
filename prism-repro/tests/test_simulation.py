"""Workload generator, fast-simulator invariants and hand-checked cases, metrics and
the tuning rule."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import KDraws, select_by_rule  # noqa: E402
from prism_repro.metrics import runs_of_true, weighted_quantile_hist, window_attainment  # noqa: E402
from prism_repro.policies import OnDemand, Policy, Static  # noqa: E402
from prism_repro.pricing import stage_cost  # noqa: E402
from prism_repro.latency import stage_means, init_mean  # noqa: E402
from prism_repro.simulator import WEEK, SimContext, WeekDraws, simulate  # noqa: E402
from prism_repro.workload import MIN_PER_DAY, generate_trace  # noqa: E402


class TestWorkload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tr = {sc: generate_trace(11, sc) for sc in ("stationary", "growth", "new_spike", "bursty")}

    def test_synthetic_label_and_determinism(self):
        a = generate_trace(11, "stationary")
        self.assertTrue(a["meta"]["synthetic"])
        np.testing.assert_array_equal(a["counts"], self.tr["stationary"]["counts"])

    def test_first_21_days_identical(self):
        b = self.tr["stationary"]["counts"][:21 * MIN_PER_DAY]
        for sc, t in self.tr.items():
            np.testing.assert_array_equal(t["counts"][:21 * MIN_PER_DAY], b)

    def test_mean_rate(self):
        self.assertAlmostEqual(self.tr["stationary"]["counts"][:21 * MIN_PER_DAY].mean() / 600, 1, delta=0.08)

    def test_growth_and_spike(self):
        s, g = self.tr["stationary"]["baseline"], self.tr["growth"]["baseline"]
        late = slice(25 * MIN_PER_DAY, 28 * MIN_PER_DAY)
        np.testing.assert_allclose(g[late] / s[late], 1.4)
        r_s, r_n = self.tr["stationary"]["rate"], self.tr["new_spike"]["rate"]
        t = np.arange(len(r_s))
        m15 = (t >= 21 * MIN_PER_DAY) & (t % 60 == 15)
        self.assertGreater(np.median(r_n[m15] / r_s[m15]), 2.9)

    def test_bursty_has_more_burst_mass(self):
        sl = slice(21 * MIN_PER_DAY, None)
        self.assertGreater(self.tr["bursty"]["rate"][sl].sum(), self.tr["stationary"]["rate"][sl].sum())


class FixedK(Policy):
    family = "Fixed"

    def __init__(self, P):
        super().__init__(None)
        self.Pv = np.asarray(P, float)

    def decide(self, k, tel):
        return self.Pv, 1024


def tiny_context(K_stage, N=1000.0, keepalive=10):
    cfg = PipelineConfig().with_(keepalive_min=keepalive)
    counts = np.full(2 * WEEK, N, dtype=np.int64)
    dr = WeekDraws(cfg, 5, 1)
    ctx = SimContext(cfg=cfg, counts=counts, week_start=WEEK, draws=dr,
                     K_hist_default=np.zeros((2 * WEEK, cfg.n_stages)), r_mean_peak=0.8)
    ctx._Kweek[1024] = np.repeat(np.asarray(K_stage, float)[:, None], cfg.n_stages, axis=1)
    return ctx


class TestFastSimulator(unittest.TestCase):
    def test_keepalive_cold_start_count_hand_example(self):
        K = np.zeros(WEEK)
        K[:6] = [0, 5, 5, 3, 8, 8]
        K[20] = 4  # pool from minute 4 (8 envs) expired after 10 idle minutes? last use at 5 -> pool 0 at 20
        res = simulate(tiny_context(K), OnDemand())
        cold = res["telemetry"].cold[:, 0]
        np.testing.assert_allclose(cold[:6], [0, 5, 0, 0, 3, 0])
        self.assertEqual(cold[20], 4)

    def test_provisioned_covers_all(self):
        K = np.full(WEEK, 10.0)  # N=100/min -> mean loads 1.3, 6.7, 4.2, 2.0 envs
        res = simulate(tiny_context(K, N=100.0), FixedK([20, 20, 20, 20]))
        s, tel = res["summary"], res["telemetry"]
        self.assertEqual(s["cost_od"], 0.0)
        self.assertEqual(tel.cold.sum(), 0.0)
        self.assertTrue(0.0 < s["billing_utilisation"] < 1.0)

    def test_cost_matches_independent_formula(self):
        K = np.full(WEEK, 30.0)
        K[::7] = 45
        P = np.array([5, 25, 15, 8], float)
        ctx = tiny_context(K)
        res = simulate(ctx, FixedK(P))
        tel, cfg, s = res["telemetry"], ctx.cfg, res["summary"]
        d = stage_means(cfg, 1024)
        tot = 0.0
        for st in range(4):
            n_od = tel.n_od[:, st]
            tot += stage_cost(P[st], 1000 - n_od, n_od, tel.cold[:, st], d[st], init_mean(cfg, 1024), 1.0,
                              60.0, cfg.prices).sum()
        tot += 1000 * WEEK * 4 * cfg.prices.req
        self.assertAlmostEqual(s["cost"], tot, places=6)

    def test_invariants_and_determinism(self):
        cfg = PipelineConfig()
        tr = generate_trace(3, "stationary")
        counts = tr["counts"]
        kh = np.vstack([KDraws(cfg, 3, w).peak_concurrency(counts[w * WEEK:(w + 1) * WEEK].astype(float), 1024)
                        for w in range(4)])
        ctx = SimContext(cfg=cfg, counts=counts, week_start=2 * WEEK, draws=WeekDraws(cfg, 3, 2), K_hist_default=kh)
        r1 = simulate(ctx, Static(90))
        r2 = simulate(ctx, Static(90))
        self.assertEqual(r1["summary"]["cost"], r2["summary"]["cost"])
        tel = r1["telemetry"]
        self.assertTrue(np.all(tel.cold <= tel.n_od + 1e-9))
        self.assertTrue(np.all(tel.n_od <= tel.N[:, None] + 1e-9))
        self.assertTrue(0 <= r1["summary"]["billing_utilisation"] <= 1)
        # policy-independent concurrency at 1024 MB matches the history draws (CRN)
        np.testing.assert_allclose(ctx.K_week(1024), kh[2 * WEEK:3 * WEEK])


class TestMetricsAndTuning(unittest.TestCase):
    def test_window_attainment(self):
        n = np.array([10, 10, 0, 0, 5, 5], float)
        ok = np.array([10, 9, 0, 0, 5, 4], float)
        att, late, tot = window_attainment(n, ok, 2)
        np.testing.assert_allclose(att, [0.95, 1.0, 0.9])
        np.testing.assert_allclose(late, [1, 0, 1])

    def test_runs(self):
        np.testing.assert_array_equal(runs_of_true([1, 1, 0, 1, 0, 0, 1, 1, 1]), [2, 1, 3])

    def test_weighted_quantile(self):
        rng = np.random.default_rng(0)
        v = rng.uniform(0, 20, (300, 50))
        w = rng.uniform(0, 3, (300, 1))
        q = weighted_quantile_hist(v, w, 0.99)
        flat, ww = v.ravel(), np.broadcast_to(w, v.shape).ravel()
        o = np.argsort(flat)
        ref = flat[o][np.searchsorted(np.cumsum(ww[o]), 0.99 * ww.sum())]
        self.assertAlmostEqual(q, ref, delta=0.02)

    def test_selection_rule(self):
        rows = [dict(cost=10, violating_window_rate=0.03), dict(cost=12, violating_window_rate=0.02),
                dict(cost=15, violating_window_rate=0.0)]
        self.assertEqual(select_by_rule(rows)["cost"], 12)
        rows = [dict(cost=10, violating_window_rate=0.05), dict(cost=12, violating_window_rate=0.03)]
        self.assertEqual(select_by_rule(rows)["cost"], 12)


if __name__ == "__main__":
    unittest.main()
