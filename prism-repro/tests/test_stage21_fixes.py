"""Stage 2.1 (branch stage2.1-m12-m5-fix, not merged): tests of the M12 and M5 code fixes.

M12  first epoch of a week: reactive tracking must not read beyond its visible horizon; the pre-week warm
     pool must expire minute by minute.
M5   memory change: warm on-demand environments of the previous version cannot be reused (fast and
     event-level simulator).
"""
import os
import sys
import unittest
from collections import deque

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import _stage_pass  # noqa: E402
from prism_repro.policies import OnDemand, Policy, Reactive  # noqa: E402
from prism_repro.simulator import WEEK, SimContext, Telemetry, WeekDraws, simulate  # noqa: E402


def context(K_week_by_mem, K_hist, N=1000.0):
    cfg = PipelineConfig()
    counts = np.full(2 * WEEK, N, dtype=np.int64)
    ctx = SimContext(cfg=cfg, counts=counts, week_start=WEEK, draws=WeekDraws(cfg, 5, 1),
                     K_hist_default=K_hist, r_mean_peak=0.8)
    for m, K in K_week_by_mem.items():
        ctx._Kweek[m] = np.repeat(np.asarray(K, float)[:, None], cfg.n_stages, axis=1)
    return ctx


class MemSchedule(Policy):
    """No provisioned capacity; memory per epoch from a list."""
    family = "MemSchedule"

    def __init__(self, mems):
        super().__init__(None)
        self.mems = mems

    def decide(self, k, tel):
        return np.zeros(self.cfg.n_stages), self.mems[k] if k < len(self.mems) else self.mems[-1]


class TestM12(unittest.TestCase):
    def test_reactive_first_epoch_window_ends_at_visible_horizon(self):
        S = 4
        hist = np.zeros((2 * WEEK, S))
        hist[WEEK - 1] = 1000.0          # minute -1: NOT visible at decision k = 0 (visible through minute -2)
        hist[WEEK - 2] = 10.0            # minute -2: visible
        ctx = context({1024: np.zeros(WEEK)}, hist)
        pol = Reactive(0.5)
        pol.prepare(ctx)
        tel = Telemetry(N=np.zeros(WEEK), K=np.zeros((WEEK, S)), P=np.zeros((WEEK, S)),
                        n_od=np.zeros((WEEK, S)), cold=np.zeros((WEEK, S)))
        P, _ = pol.decide(0, tel)
        np.testing.assert_allclose(P, np.full(S, 20.0))   # ceil(10 / 0.5); minute -1 ignored

    def test_pre_week_pool_expires_minute_by_minute(self):
        S = 4
        hist = np.zeros((2 * WEEK, S))
        hist[WEEK - 10] = 6.0            # used only at minute -10: warm at minute 0, expired from minute 1
        K = np.zeros(WEEK)
        K[1] = 6.0
        res = simulate(context({1024: K}, hist), OnDemand())
        self.assertEqual(res["telemetry"].cold[1, 0], 6.0)   # before the fix: 0 (expired pool still counted)
        K0 = np.zeros(WEEK)
        K0[0] = 6.0
        res0 = simulate(context({1024: K0}, hist), OnDemand())
        self.assertEqual(res0["telemetry"].cold[0, 0], 0.0)  # still warm at minute 0


class TestM5(unittest.TestCase):
    def test_fast_simulator_memory_change_empties_warm_pool(self):
        S = 4
        hist = np.zeros((2 * WEEK, S))
        K = np.zeros(WEEK)
        K[3], K[6] = 5.0, 5.0            # same demand before and after a switch at minute 5 (epoch 1)
        ctx = context({1024: K, 2048: K}, hist)
        res = simulate(ctx, MemSchedule([1024, 2048]))
        cold = res["telemetry"].cold[:, 0]
        self.assertEqual(cold[3], 5.0)
        self.assertEqual(cold[6], 5.0)  # before the fix: 0 (environments of the 1024 MB version reused)
        res_same = simulate(context({1024: K}, hist), MemSchedule([1024, 1024]))
        self.assertEqual(res_same["telemetry"].cold[6, 0], 0.0)   # no switch: reuse as before

    def test_event_level_memory_change_prevents_reuse(self):
        arr = np.array([10.0, 200.0])            # second request after the version changes at minute 1
        x, z = np.full(2, 1.0), np.full(2, 5.0)
        fin, cold, pc = _stage_pass(arr, x, z, np.zeros(5), 600.0, gen_min=np.array([0, 1, 1, 1, 1]))
        np.testing.assert_array_equal(cold, [True, True])
        fin, cold, pc = _stage_pass(arr, x, z, np.zeros(5), 600.0, gen_min=np.zeros(5, int))
        np.testing.assert_array_equal(cold, [True, False])
        fin2, cold2, pc2 = _stage_pass(arr, x, z, np.zeros(5), 600.0)     # legacy path unchanged
        np.testing.assert_array_equal(cold2, [True, False])


if __name__ == "__main__":
    unittest.main()
