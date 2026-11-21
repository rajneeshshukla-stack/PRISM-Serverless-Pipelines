"""Stage-specific demand phi through the model (R2.5, R4.1, R7.1). Unit phi is pinned byte for byte by
tests/test_stage_demand_guard.py; these tests check behaviour at phi != 1."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "revision"))

from prism_repro.config import PipelineConfig, PrismConfig  # noqa: E402
from prism_repro.forecast import scenarios  # noqa: E402
from prism_repro.latency import stage_demand, stage_means  # noqa: E402
from prism_repro.optimizer import ChanceConstrainedOptimizer  # noqa: E402

FANOUT = (1.0, 1.0, 3.0, 3.0)
BATCH = (1.0, 1.0, 1.0, 0.1)


class TestStageDemand(unittest.TestCase):
    def test_validation_and_default(self):
        np.testing.assert_array_equal(stage_demand(PipelineConfig()), np.ones(4))
        for bad in ((1.0, 1.0, 1.0), (1.0, 0.0, 1.0, 1.0), (1.0, -1.0, 1.0, 1.0)):
            with self.assertRaises(ValueError):
                PipelineConfig().with_(stage_demand=bad)

    def test_optimizer_matches_the_static_probe(self):
        """End-to-end model and the static probe agree: for every candidate of the paper's family, the
        optimiser's cost and feasible share under phi equal stage_demand_gap.eval_phi."""
        from stage_demand_gap import eval_phi
        sc = scenarios(np.array([400.0, 600.0, 900.0, 1200.0]), 100)
        for phi in (FANOUT, BATCH, (1.0, 1.0, 0.5, 0.5)):
            cfg = PipelineConfig().with_(stage_demand=phi)
            pc = PrismConfig(eps=0.02)
            ev = ChanceConstrainedOptimizer(cfg, pc, 0.8).evaluate(sc, (1024,), 0.35)
            for j in range(len(ev["ys"])):
                c, f = eval_phi(ev["P"][0, j], 1024, sc, 0.35, pc, list(phi))
                self.assertAlmostEqual(ev["cost"][0, j], c, places=9)
                self.assertAlmostEqual(ev["feas"][0, j], f, places=12)

    def test_candidate_family(self):
        sc = scenarios(np.array([400.0, 600.0, 900.0, 1200.0]), 100)
        cfg = PipelineConfig().with_(stage_demand=FANOUT)
        d = stage_means(cfg, 1024)
        ev0 = ChanceConstrainedOptimizer(cfg, PrismConfig(), 0.8).evaluate(sc, (1024,), 0.35)
        ev1 = ChanceConstrainedOptimizer(cfg, PrismConfig(family_follows_stage_demand=True), 0.8).evaluate(sc, (1024,), 0.35)
        y = ev0["ys"][5]
        np.testing.assert_array_equal(ev0["P"][0, 5], np.ceil(y * d / 60.0 - 1e-9))                       # paper's (15)
        np.testing.assert_array_equal(ev1["P"][0, 5], np.ceil(y * d * np.array(FANOUT) / 60.0 - 1e-9))  # phi-scaled
        # the fan-out stage is the bottleneck of the paper's family: never more feasible than the phi-scaled one
        self.assertTrue(np.all(ev1["feas"] >= ev0["feas"] - 1e-12))

    def test_fast_simulator_scales_concurrency_and_counts(self):
        from prism_repro.simulator import WeekDraws
        counts = np.full(10080, 600.0)
        base = WeekDraws(PipelineConfig(), 3, 2).peak_concurrency(counts, 1024)
        fan = WeekDraws(PipelineConfig().with_(stage_demand=FANOUT), 3, 2).peak_concurrency(counts, 1024)
        np.testing.assert_array_equal(fan[:, :2], base[:, :2])                  # same draws, unchanged stages
        self.assertGreater(fan[:, 2].mean(), 2.5 * base[:, 2].mean())           # about 3x the concurrency
        self.assertLess(fan[:, 2].mean(), 3.5 * base[:, 2].mean())

    def test_rules_follow_phi(self):
        from prism_repro.policies import QuantProv

        class Ctx:
            pass
        ctx = Ctx()
        for phi in (None, FANOUT):
            ctx.cfg = PipelineConfig().with_(stage_demand=phi)
            ctx.forecasts = {"gbm": {"q_cal": np.full((2016, 4), 600.0)}}
            pol = QuantProv(2, 1.0)
            pol.prepare(ctx)
            expect = stage_means(ctx.cfg, 1024) * (np.ones(4) if phi is None else np.array(phi))
            np.testing.assert_array_equal(pol.d, expect)

    def test_event_level_refuses_phi(self):
        from prism_repro.des import EventDraws, simulate_events
        cfg = PipelineConfig().with_(stage_demand=FANOUT)
        counts = np.full(30, 100)
        dr = EventDraws(cfg, counts, 1, 0)
        with self.assertRaises(NotImplementedError):
            simulate_events(cfg, dr, np.full((6, 4), 10), np.full(6, 1024))


if __name__ == "__main__":
    unittest.main()
