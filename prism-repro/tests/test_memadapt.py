"""Memory-adaptive calibrated-quantile baseline (R2.6, R3.7, R7.4): it adapts, it logs, and it is QuantProv
whenever the default memory qualifies."""
import dataclasses
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle, make_policy  # noqa: E402
from prism_repro.latency import miss_table, stage_means  # noqa: E402
from prism_repro.policies import MemAdapt, QuantProv  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402


class _Ctx:
    def __init__(self, cfg, level=600.0):
        self.cfg = cfg
        self.forecasts = {"gbm": {"q_cal": np.full((2016, 4), level)}}


def _prepared(cfg, a=1.0, tau_w=0.005):
    pol = MemAdapt(2, a, tau_w)
    pol.prepare(_Ctx(cfg))
    return pol


class TestMemAdapt(unittest.TestCase):
    def test_memory_follows_warm_feasibility(self):
        base = PipelineConfig().with_(nonscaling=0.5)
        cases = [(14.5, 0.005, 1024),   # v_w(1024) = 0.0022 qualifies at the default deadline
                 (12.0, 0.005, 2048),   # v_w(1024) = 0.034 does not; v_w(2048) = 0.0004 does
                 (14.5, 0.002, 2048),   # a stricter tolerance moves the default deadline to 2048 MB
                 (11.0, 0.002, 3008),   # v_w(2048) = 0.0021 > 0.002
                 (5.0, 0.005, 3008)]    # nothing qualifies: the largest (fastest) size
        for D, tw, want in cases:
            cfg = base.with_(deadline=D)
            pol = _prepared(cfg, tau_w=tw)
            self.assertEqual(pol.choose_memory(), want, (D, tw))
            vw = miss_table(cfg)
            smaller = [m for m in cfg.mem_options if m < want]
            self.assertTrue(all(vw[m][0] > tw for m in smaller), (D, tw))   # nothing smaller qualifies

    def test_capacity_at_the_chosen_memory_and_log(self):
        cfg = PipelineConfig().with_(deadline=12.0)
        pol = _prepared(cfg, a=1.2)
        P, m = pol.decide(0, None)
        self.assertEqual(m, 2048)
        np.testing.assert_array_equal(P, np.ceil(1.2 * 600.0 * stage_means(cfg, 2048) / 60.0 - 1e-9))
        for k in range(1, 5):
            self.assertEqual(pol.decide(k, None)[1], 2048)
        self.assertEqual(len(pol.mem_log), 1)
        self.assertEqual(pol.mem_log[0][:2], (0, 2048))
        self.assertEqual(pol.info()["mem_changes"], 0)

    def test_make_policy_and_validation(self):
        pol = make_policy(dict(family="MemAdapt", param=1.1))
        self.assertIsInstance(pol, MemAdapt)
        self.assertEqual((pol.tau_idx, pol.tau_w, pol.label), (2, 0.005, "MemAdapt_q90-1.1"))
        self.assertEqual(make_policy(dict(family="MemAdapt", param=1.1, tau_w=0.002)).label, "MemAdapt_q90[tw0.002]-1.1")
        with self.assertRaises(ValueError):
            MemAdapt(2, 1.0, tau_w=0.0)


class TestMemAdaptReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = TraceBundle(101, PipelineConfig(), scenarios=("stationary",), forecasters=("seasonal_naive",))

    def _run(self, pol, deadline=None):
        ctx = self.b.context("stationary", "test")
        if deadline is not None:
            ctx = dataclasses.replace(ctx, cfg=ctx.cfg.with_(deadline=deadline), _Kweek={})
        return simulate(ctx, pol)

    def test_is_quantprov_when_the_default_memory_qualifies(self):
        a = self._run(MemAdapt(2, 1.0, fc_name="seasonal_naive"))
        q = self._run(QuantProv(2, 1.0, fc_name="seasonal_naive"))
        for key in ("P_epoch", "mem_epoch"):
            np.testing.assert_array_equal(a["raw"][key], q["raw"][key])
        self.assertEqual(a["summary"]["cost"], q["summary"]["cost"])
        self.assertEqual(a["summary"]["violating_window_rate"], q["summary"]["violating_window_rate"])

    def test_moves_the_whole_replay_to_2048_at_a_short_deadline(self):
        pol = MemAdapt(2, 1.0, fc_name="seasonal_naive")
        res = self._run(pol, deadline=12.0)
        self.assertTrue(np.all(res["raw"]["mem_epoch"] == 2048))
        self.assertEqual(res["summary"]["share_mem_ge_2048"], 1.0)
        self.assertEqual(pol.info()["mem_changes"], 0)
        self.assertEqual(pol.mem_log[0][:2], (0, 2048))
        # and it beats staying at 1024 MB on compliance in that regime
        q = self._run(QuantProv(2, 1.0, fc_name="seasonal_naive"), deadline=12.0)
        self.assertLess(res["summary"]["violating_window_rate"], q["summary"]["violating_window_rate"])


if __name__ == "__main__":
    unittest.main()
