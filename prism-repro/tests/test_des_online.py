"""Event-level simulator tests (Erlang-B oracle, hand-traced routing) and the
online-vs-batch feature equivalence used by the overhead measurement (C31)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import (EventDraws, _stage_pass, max_inflight_per_minute, simulate_events,  # noqa: E402
                             stage_telemetry)
from prism_repro.simulator import Telemetry  # noqa: E402
from prism_repro.features import FeatureBuilder, online_features  # noqa: E402
from prism_repro.risk import c_eff, erlang_b, occupancy_overflow  # noqa: E402
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

    def test_erlangb_accuracy_vs_eq5_gap(self):
        """R3.4 / R4.9 gate: against the event-level simulator at mean load, Erlang-B is
        within 2.5% while Eq. (5) evaluated at c_eff is 20-28% off. Reviewer 3 cites these
        figures; this test holds the main configuration to them."""
        cfg = PipelineConfig()
        counts = np.random.default_rng(0).poisson(600, 400)
        dr = EventDraws(cfg, counts, 3, 0)
        _, _, pcv = _stage_pass(dr.arrival, dr.ex[1] * 4.0, dr.init[1] * 6.0, np.full(400, 40.0), 600.0)
        measured = 1 - pcv.mean()
        eb_err = abs(float(erlang_b(40, 40)) - measured) / measured
        eq5_err = abs(float(occupancy_overflow(40, c_eff(40))) - measured) / measured
        self.assertLess(eb_err, 0.025, f"Erlang-B error {eb_err:.1%} exceeds the 2.5% claimed in VI-H")
        self.assertTrue(0.20 <= eq5_err <= 0.28,
                        f"Eq. (5) error {eq5_err:.1%} outside the 20-28% band reported for VI-H")

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


class TestEventTelemetry(unittest.TestCase):
    """R2.2, first closed-loop step: the event-level simulator emits the per-minute
    telemetry a policy reads (simulator.Telemetry fields) and the emitted counts conserve
    requests: arrivals minus completions accumulate to the executions in flight."""

    def test_stage_telemetry_hand_trace(self):
        # request 0 runs 0 -> 65 on demand (cold); 1 runs 10 -> 20 provisioned; 2 runs 70 -> 80
        # warm on demand; 3 arrives exactly on the minute boundary and 4 finishes exactly on it
        arr = np.array([0.0, 10.0, 70.0, 60.0, 30.0])
        fin = np.array([65.0, 20.0, 80.0, 90.0, 60.0])
        cold = np.array([True, False, False, False, False])
        pc = np.array([False, True, False, True, True])
        t = stage_telemetry(arr, fin, cold, pc, 2)
        np.testing.assert_array_equal(t["arrivals"], [3, 2])
        np.testing.assert_array_equal(t["completed"], [1, 4])   # fin = 60 belongs to minute 1
        np.testing.assert_array_equal(t["inflight_end"], [2, 0])
        np.testing.assert_array_equal(t["n_od"], [1, 1])
        np.testing.assert_array_equal(t["cold"], [1, 0])
        # boundary arrival with no boundary finish: pins the half-open convention
        t = stage_telemetry(np.array([0.0, 60.0]), np.array([30.0, 150.0]),
                            np.zeros(2, bool), np.zeros(2, bool), 2)
        np.testing.assert_array_equal(t["arrivals"], [1, 1])
        np.testing.assert_array_equal(t["completed"], [1, 0])
        np.testing.assert_array_equal(t["inflight_end"], [0, 1])
        # events after the horizon are not observed; the request is still in flight at its end
        t = stage_telemetry(np.array([0.0, 130.0]), np.array([150.0, 140.0]), np.zeros(2, bool),
                            np.zeros(2, bool), 2)
        np.testing.assert_array_equal(t["arrivals"], [1, 0])
        np.testing.assert_array_equal(t["completed"], [0, 0])
        np.testing.assert_array_equal(t["inflight_end"], [1, 1])

    def _run(self, want_telemetry):
        cfg = PipelineConfig()
        counts = generate_trace(5, "stationary")["counts"][:600].copy()
        counts[-10:] = 0                       # drain, so every request finishes inside the horizon
        dr = EventDraws(cfg, counts, 5, 0)
        # continuous draws never land on a minute boundary, so the gate could not see the
        # half-open convention; snap each minute's first arrival onto its boundary (order kept)
        first = np.r_[0, np.cumsum(dr.counts)[:-1]][dr.counts > 0]
        dr.arrival[first] = dr.minute[first] * 60.0
        P = np.tile([6, 30, 18, 8], (120, 1))   # mixed provisioned / on-demand service
        mem = np.r_[np.full(60, 1024), np.full(60, 2048)]   # one memory change (M5 path)
        return cfg, dr, P, simulate_events(cfg, dr, P, mem, want_telemetry=want_telemetry)

    def test_conservation_gate(self):
        cfg, dr, P, out = self._run(True)
        tel = out["raw"]["telemetry"]
        self.assertIsInstance(tel, Telemetry)
        n, S = dr.n_min, cfg.n_stages
        for f in ("K", "P", "n_od", "cold", "arrivals", "completed", "inflight_end"):
            self.assertEqual(getattr(tel, f).shape, (n, S), f)
        self.assertEqual(tel.filled, n)
        np.testing.assert_array_equal(tel.P, np.repeat(P, cfg.epoch_min, axis=0))
        # gate: in flight + completed = arrivals, per minute and per window, every stage
        net = np.cumsum(tel.arrivals, 0) - np.cumsum(tel.completed, 0)
        np.testing.assert_array_equal(net, tel.inflight_end)
        w = cfg.window_min
        np.testing.assert_array_equal(net[w - 1::w], tel.inflight_end[w - 1::w])
        # no request lost or duplicated across stages; the horizon drains
        np.testing.assert_array_equal(tel.arrivals[:, 0], tel.N)
        np.testing.assert_array_equal(tel.arrivals.sum(0), np.full(S, dr.n))
        np.testing.assert_array_equal(tel.completed.sum(0), np.full(S, dr.n))
        np.testing.assert_array_equal(tel.inflight_end[-1], np.zeros(S))
        # invariants shared with the fast simulator: cold <= overflow <= arrivals
        self.assertTrue(np.all(tel.cold <= tel.n_od) and np.all(tel.n_od <= tel.arrivals))
        self.assertTrue(np.all(tel.K >= tel.inflight_end))
        self.assertTrue(0 < tel.n_od.sum() < tel.arrivals.sum() and tel.cold.sum() > 0)
        # telemetry agrees with the simulator's own summary
        s = out["summary"]
        self.assertAlmostEqual(float(np.mean(tel.n_od.sum(0) / dr.n)), s["overflow_share"], places=12)
        self.assertAlmostEqual(float(np.mean(tel.cold.sum(0) / dr.n)), s["cold_start_ratio"], places=12)

    def test_emitting_telemetry_changes_nothing_else(self):
        _, _, _, a = self._run(False)
        _, _, _, b = self._run(True)
        self.assertEqual(a["summary"], b["summary"])
        self.assertNotIn("telemetry", a["raw"])
        np.testing.assert_array_equal(a["raw"]["window_attainment"], b["raw"]["window_attainment"])


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
