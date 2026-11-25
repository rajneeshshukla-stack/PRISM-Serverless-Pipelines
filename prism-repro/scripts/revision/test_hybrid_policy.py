"""Hand-calculated checks of hybrid_policy.py (run from prism-repro/: venv/Scripts/python -m unittest
scripts/revision/test_hybrid_policy.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hybrid_policy import fixed_keepalive, hybrid, hybrid_windows, no_unloading  # noqa: E402


class TestFixed(unittest.TestCase):
    def test_cold_and_wasted(self):
        # invocations at minutes 0, 5, 30 (one each), horizon 60, keep-alive 10:
        # 0 cold; 5 warm (wasted 5); 30 cold (wasted 10); trailing min(10, 30) = 10
        r = fixed_keepalive([0, 5, 30], [1, 1, 1], 10, 60)
        self.assertEqual((r["cold"], r["invocations"], r["wasted_min"]), (2, 3, 25.0))

    def test_same_minute_is_warm(self):
        r = fixed_keepalive([0], [4], 10, 5)
        self.assertEqual((r["cold"], r["wasted_min"]), (1, 5.0))      # trailing window cut at the horizon


class TestHybridWindows(unittest.TestCase):
    def test_empty_histogram_is_standard_keepalive(self):
        a, b, std = hybrid_windows([0], [1])
        self.assertEqual((a[0], b[0], bool(std[0])), (0.0, 240.0, True))

    def test_concentrated_histogram_sets_prewarm_and_keepalive(self):
        # 101 minutes, every IT = 10 min: one bin (10) -> CV high; head 10 -> pre-warm 9; tail edge 11 -> until 12.1
        t = [10 * i for i in range(101)]
        a, b, std = hybrid_windows(t, [1] * len(t))
        self.assertFalse(std[-1])
        self.assertAlmostEqual(a[-1], 9.0)
        self.assertAlmostEqual(b[-1], 12.1)
        _, b2, _ = hybrid_windows(t, [1] * len(t), ka_mode="II")
        self.assertAlmostEqual(b2[-1], 9.0 + 12.1)

    def test_every_minute_active_gives_prewarm_0_and_keepalive_2_2(self):
        # ITs of 1 minute (bin 1) plus same-minute zeros: head bin 0 -> pre-warm 0; tail bin 1 -> edge 2 -> 2.2 min
        t = list(range(200))
        a, b, _ = hybrid_windows(t, [3] * len(t))
        self.assertEqual(a[-1], 0.0)
        self.assertAlmostEqual(b[-1], 2.2)

    def test_spread_histogram_is_not_representative(self):
        # ITs spread evenly over 1..120 min: CV of 240 bin counts = sqrt(240/120 - 1) = 1 < 2 -> standard keep-alive
        g = list(range(1, 121)) * 2
        t = [0]
        for x in g:
            t.append(t[-1] + x)
        a, b, std = hybrid_windows(t, [1] * len(t))
        self.assertTrue(std[-1])
        self.assertEqual((a[-1], b[-1]), (0.0, 240.0))

    def test_out_of_bounds_its_are_excluded(self):
        t = [0, 300, 600, 610, 620]                          # two ITs of 300 (OOB), two of 10
        a, b, std = hybrid_windows(t, [1] * 5)
        self.assertAlmostEqual(a[-1], 9.0)                   # only the in-range ITs of 10 count


class TestHybridSimulation(unittest.TestCase):
    def test_periodic_app_after_learning(self):
        # IT 10 every time: the first window is standard (240 min), then pre-warm 9 / until 12.1 -> every later IT warm
        t = [10 * i for i in range(50)]
        r = hybrid(t, [1] * 50, horizon_min=t[-1] + 100)
        self.assertEqual(r["cold"], 1)
        # wasted: first IT under standard keep-alive = 10; 48 later ITs each wasted 10 - 9 = 1; trailing 12.1 - 9
        self.assertAlmostEqual(r["wasted_min"], 10 + 48 * 1.0 + 3.1)

    def test_same_minute_invocation_is_cold_when_prewarm_is_positive(self):
        t = [10 * i for i in range(50)] + [500]
        c = [1] * 50 + [3]                                   # minute 500 has 3 invocations; pre-warm 9 > 0
        r = hybrid(t, c, horizon_min=600)
        self.assertEqual(r["cold"], 1 + 2)

    def test_no_unloading(self):
        self.assertEqual(no_unloading([3, 9], [1, 2], 20), {"invocations": 3, "cold": 1, "wasted_min": 17.0})


if __name__ == "__main__":
    unittest.main()
