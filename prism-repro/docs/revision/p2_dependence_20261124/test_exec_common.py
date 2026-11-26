"""Opt-in shared execution factor (exec_common_frac = rho; P2 candidate, 24 Nov 2026)."""
import unittest

import numpy as np

from prism_repro.config import PipelineConfig
from prism_repro.des import EventDraws
from prism_repro.latency import exec_mult, lognormal_mult, miss_probabilities


class TestRhoZeroIsLegacy(unittest.TestCase):
    def test_default(self):
        self.assertEqual(PipelineConfig().exec_common_frac, 0.0)

    def test_exec_mult_identity(self):
        z = np.random.default_rng(1).standard_normal((1000, 4))
        np.testing.assert_array_equal(exec_mult(z, PipelineConfig()), lognormal_mult(z, 0.30))

    def test_event_draws_identical(self):
        counts = np.full(30, 20)
        a = EventDraws(PipelineConfig(), counts, 101, 3)
        b = EventDraws(PipelineConfig().with_(exec_common_frac=0.0), counts, 101, 3)
        np.testing.assert_array_equal(a.ex, b.ex)
        np.testing.assert_array_equal(a.arrival, b.arrival)


class TestShared(unittest.TestCase):
    def test_marginals_and_correlation(self):
        z = np.random.default_rng(2).standard_normal((400_000, 4))
        for rho in (0.5, 0.9977, 1.0):
            cfg = PipelineConfig().with_(exec_common_frac=rho)
            x = exec_mult(z, cfg, np.random.default_rng(3))
            self.assertTrue(np.all(np.abs(x.mean(0) - 1) < 0.003))              # mean-one kept
            self.assertTrue(np.all(np.abs(np.log(x).std(0) - 0.30) < 0.002))     # sigma kept
            c = np.corrcoef(np.log(x).T)[np.triu_indices(4, 1)]
            self.assertTrue(np.all(np.abs(c - rho) < 0.01), (rho, c))

    def test_rho_one_equal_across_stages(self):
        counts = np.full(30, 20)
        d = EventDraws(PipelineConfig().with_(exec_common_frac=1.0), counts, 101, 3)
        np.testing.assert_allclose(d.ex, np.broadcast_to(d.ex[0], d.ex.shape), rtol=1e-6)
        # arrivals and the other draws are unchanged by rho
        L = EventDraws(PipelineConfig(), counts, 101, 3)
        np.testing.assert_array_equal(d.arrival, L.arrival)
        np.testing.assert_array_equal(d.ov, L.ov)
        np.testing.assert_array_equal(d.init, L.init)

    def test_needs_separate_stream(self):
        with self.assertRaises(ValueError):
            exec_mult(np.zeros((3, 4)), PipelineConfig().with_(exec_common_frac=0.5))

    def test_validation(self):
        for bad in (-0.1, 1.01):
            with self.assertRaises(ValueError):
                PipelineConfig().with_(exec_common_frac=bad)

    def test_miss_table_reflects_rho(self):
        ind = miss_probabilities(PipelineConfig(), 1024)[0]
        shr = miss_probabilities(PipelineConfig().with_(exec_common_frac=1.0), 1024)[0]
        self.assertEqual(ind, 0.0021625)    # the pinned tree's legacy value (3edc386), reproduced exactly
        self.assertGreater(shr, 0.03)       # the shared-factor value is about 0.033 (p2_correlation_check: 0.0333)


if __name__ == "__main__":
    unittest.main()
