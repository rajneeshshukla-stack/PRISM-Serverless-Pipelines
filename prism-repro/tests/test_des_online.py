"""Event-level simulator tests (Erlang-B oracle, hand-traced routing) and the
online-vs-batch feature equivalence used by the overhead measurement (C31)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, _stage_pass, max_inflight_per_minute, simulate_events  # noqa: E402
from prism_repro.features import FeatureBuilder, online_features  # noqa: E402
from prism_repro.risk import erlang_b  # noqa: E402
from prism_repro.workload import generate_trace  # noqa: E402


class TestStagePass(unittest.TestCase):
    def test_cold_occupancy_and_keepalive_expiry(self):
        arr = np.array([0.0, 1.0, 2.0, 100.0])
        x = np.array([5.0, 1.0, 1.0, 1.0])
        z = np.full(4, 10.0)
        fin, cold, pc = _stage_pass(arr, x, z, np.zeros(5), 50.0)
        np.testing.assert_allclose(fin, [15, 12, 13, 111])  # all cold; idle envs expired by t=100
        self.assertTrue(cold.all() and not pc.any())
        fin, cold, pc = _stage_pass(arr, x, z, np.zeros(5), 95.0)
        np.testing.assert_allclose(fin, [15, 12, 13, 101])  # LIFO reuse of env idle since 15
        self.assertFalse(cold[3])

    def test_provisioned_loss_routing(self):
        arr = np.array([0.0, 1.0, 7.0])
        fin, cold, pc = _stage_pass(arr, np.full(3, 5.0), np.full(3, 10.0), np.ones(1), 600.0)
        np.testing.assert_array_equal(pc, [True, False, True])
        self.assertTrue(cold[1])

    def test_erlang_b_oracle(self):
        """Poisson arrivals into a pool of P provisioned envs: overflow share = B(P, c)."""
        cfg = PipelineConfig()
        counts = np.random.default_rng(0).poisson(600, 400)
        dr = EventDraws(cfg, counts, 3, 0)
        _, _, pc = _stage_pass(dr.arrival, dr.ex[1] * 4.0, dr.init[1] * 6.0, np.full(400, 40.0), 600.0)
        self.assertAlmostEqual(1 - pc.mean(), float(erlang_b(40, 40)), delta=0.01)

    def test_inflight_sweep(self):
        arr = np.array([0.0, 10.0, 70.0])
        fin = np.array([65.0, 20.0, 80.0])
        np.testing.assert_allclose(max_inflight_per_minute(arr, fin, 2), [2, 1])
        # a minute containing only departures keeps the carried-in level
        np.testing.assert_allclose(max_inflight_per_minute(np.array([0.0, 1.0]), np.array([70.0, 75.0]), 2), [2, 2])
        # brute force on random intervals
        rng = np.random.default_rng(0)
        a = np.sort(rng.uniform(0, 600, 200))
        f = a + rng.exponential(30, 200)
        n_min = int(f.max() // 60) + 1
        grid = np.arange(0, n_min * 60, 0.01)
        lvl = (a[None, :] <= grid[:, None]).sum(1) - (f[None, :] <= grid[:, None]).sum(1)
        ref = np.array([lvl[(grid >= 60 * m) & (grid < 60 * (m + 1))].max() for m in range(n_min)])
        got = max_inflight_per_minute(a, f, n_min)
        self.assertTrue(np.all(got >= ref) and np.all(got - ref <= 1))

    def test_full_pipeline_deterministic_and_bounded(self):
        cfg = PipelineConfig()
        counts = generate_trace(5, "stationary")["counts"][:600]
        dr = EventDraws(cfg, counts, 5, 0)
        P = np.full((120, 4), 30)
        a = simulate_events(cfg, dr, P, np.full(120, 1024))["summary"]
        b = simulate_events(cfg, dr, P, np.full(120, 1024))["summary"]
        self.assertEqual(a["cost"], b["cost"])
        self.assertTrue(0 <= a["violating_window_rate"] <= 1 and 0 <= a["overflow_share"] <= 1)
        od = simulate_events(cfg, dr, np.zeros((120, 4)), np.full(120, 1024))["summary"]
        self.assertEqual(od["overflow_share"], 1.0)
        self.assertGreaterEqual(od["cold_start_ratio"], a["cold_start_ratio"])


class TestOnlineFeatures(unittest.TestCase):
    def test_online_equals_batch(self):
        N = generate_trace(9, "stationary")["counts"]
        fb = FeatureBuilder(N, [0, 1, 30])
        for t in np.random.default_rng(1).integers(fb.min_t, len(N) - 10, 40):
            x_b, l_b = fb.matrix(np.array([t]))
            x_o, l_o = online_features(N, int(t), [0, 1, 30])
            np.testing.assert_allclose(x_o, x_b[0], rtol=1e-10, atol=1e-12)
            self.assertAlmostEqual(l_o, l_b[0])


if __name__ == "__main__":
    unittest.main()
