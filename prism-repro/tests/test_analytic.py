"""Analytic and hand-checkable tests (claims C01-C07, C39). Oracles are independent
implementations (brute-force sums, recursion, closed forms), not the code under test."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig, Prices  # noqa: E402
from prism_repro.forecast import quantile_knots  # noqa: E402
from prism_repro.latency import duration_factor, lognormal_mult, miss_probabilities  # noqa: E402
from prism_repro.pricing import break_even_utilisation, stage_cost  # noqa: E402
from prism_repro.risk import (c_eff, erlang_b, erlang_b_recursive, occupancy_overflow,  # noqa: E402
                              record_violation)


def brute_occupancy(P, c, kmax=2000):
    s, p = 0.0, math.exp(-c)
    for k in range(kmax):
        if k > P:
            s += (k - P) * p
        p *= c / (k + 1)
    return s / c


def brute_erlang(P, c):
    terms = [c ** k / math.factorial(k) for k in range(P + 1)]
    return terms[-1] / sum(terms)


class TestOverflowFormulas(unittest.TestCase):
    def test_occupancy_matches_bruteforce(self):
        for c in (0.5, 3.0, 17.0, 40.0, 120.0):
            for P in (0, 1, 5, 20, 40, 60, 150):
                self.assertAlmostEqual(float(occupancy_overflow(P, c)), brute_occupancy(P, c), places=9)

    def test_erlang_b_matches_recursion_and_sum(self):
        for c in (0.5, 3.0, 17.0, 40.0, 100.0):
            for P in (0, 1, 5, 20, 40, 60, 100):
                self.assertAlmostEqual(float(erlang_b(P, c)), erlang_b_recursive(P, c), places=10)
                if P <= 60:
                    self.assertAlmostEqual(float(erlang_b(P, c)), brute_erlang(P, c), places=10)

    def test_C01_reported_values(self):
        # §3.2: (c,P) = (40,40): B=0.116, o=0.063; (40,50): 0.019 vs 0.005; (100,100): 0.076 vs 0.040
        for c, P, B, o in [(40, 40, 0.116, 0.063), (40, 50, 0.019, 0.005), (100, 100, 0.076, 0.040)]:
            self.assertAlmostEqual(float(erlang_b(P, c)), B, delta=0.0005)
            self.assertAlmostEqual(float(occupancy_overflow(P, c)), o, delta=0.0005)

    def test_monotonicity(self):
        c = np.linspace(0.1, 200, 300)
        for P in (0, 10, 50):
            for f in (occupancy_overflow, erlang_b):
                self.assertTrue(np.all(np.diff(f(P, c)) >= -1e-12))
        P = np.arange(0, 120)
        for f in (occupancy_overflow, erlang_b):
            self.assertTrue(np.all(np.diff(f(P, 50.0)) <= 1e-12))

    def test_zero_load(self):
        self.assertEqual(float(occupancy_overflow(0, 0.0)), 0.0)
        self.assertEqual(float(erlang_b(5, 0.0)), 0.0)

    def test_C05_ceff_is_upper45_mean_with_intensity(self):
        """c_eff ~ E_Z[mean of the upper 45 % of Poisson(c Z)], Z=exp(0.148 N) — the same
        construction the fast simulator samples from (consistency of optimiser and simulator)."""
        from scipy import stats
        rng = np.random.default_rng(0)
        for c in (20.0, 60.0, 200.0):
            u = rng.uniform(0.55, 1.0, 200_000)
            z = np.exp(0.148 * rng.standard_normal(200_000))
            k = stats.poisson.ppf(u, c * z)
            self.assertAlmostEqual(k.mean() / float(c_eff(c)), 1.0, delta=0.02)

    def test_record_violation_limits(self):
        f = np.array([0.3, 0.2, 0.1, 0.0])
        self.assertAlmostEqual(float(record_violation(f, 0.0, 0.002, 0.53)), 0.002)
        self.assertAlmostEqual(float(record_violation(np.ones(4), 1.0, 0.002, 0.53)), 0.53)
        pc = 1 - (1 - 0.5 * 0.3) * (1 - 0.5 * 0.2) * (1 - 0.5 * 0.1)
        self.assertAlmostEqual(float(record_violation(f, 0.5, 0.01, 0.6)), (1 - pc) * 0.01 + pc * 0.6)


class TestLatencyAndPrices(unittest.TestCase):
    def test_C03_doubling_memory(self):
        self.assertAlmostEqual(duration_factor(2048, 0.5), 0.75)
        self.assertAlmostEqual(duration_factor(1024, 0.5), 1.0)
        self.assertAlmostEqual(duration_factor(512, 0.5), 1.5)

    def test_lognormal_mean_one(self):
        z = np.random.default_rng(1).standard_normal(2_000_000)
        self.assertAlmostEqual(lognormal_mult(z, 0.3).mean(), 1.0, delta=0.002)

    def test_C06_table3_miss_probabilities(self):
        cfg = PipelineConfig()
        vw512, _, _, _ = miss_probabilities(cfg, 512, n=200_000, seed=99)
        vw1024, rho1024, _, _ = miss_probabilities(cfg, 1024, n=400_000, seed=98)
        vw2048, _, _, _ = miss_probabilities(cfg, 2048, n=200_000, seed=97)
        self.assertAlmostEqual(vw512, 0.251, delta=0.006)
        self.assertAlmostEqual(vw1024, 0.002, delta=0.0006)
        self.assertLess(vw2048, 0.001)
        self.assertAlmostEqual(rho1024, 0.53, delta=0.01)

    def test_C02_break_even(self):
        self.assertAlmostEqual(break_even_utilisation(Prices()), 0.6, places=3)

    def test_break_even_is_cost_indifference(self):
        """At utilisation u, a provisioned env costs pc + u*pcd per GB-s of capacity versus
        u*od on demand; indifference exactly at the break-even."""
        pr = Prices()
        u = break_even_utilisation(pr)
        busy = u * 300  # busy seconds of one env over 300 s
        pc = stage_cost(1, busy / 1.0, 0, 0, 1.0, 0, 1.0, 300, pr)  # executions of 1 s
        od = stage_cost(0, 0, busy / 1.0, 0, 1.0, 0, 1.0, 300, pr)
        self.assertAlmostEqual(float(pc), float(od), places=12)

    def test_stage_cost_hand_example(self):
        pr = Prices()
        # 2 envs x 1 GB x 300 s, 100 PC execs of 2 s, 10 OD execs of 2 s, 3 cold starts of 6 s
        expect = 2 * 300 * pr.pc + 100 * 2 * pr.pcd + 10 * 2 * pr.od + 3 * 6 * pr.od
        self.assertAlmostEqual(float(stage_cost(2, 100, 10, 3, 2.0, 6.0, 1.0, 300, pr)), expect, places=15)

    def test_C04_exponential_tail_exact(self):
        lam = 0.01
        q = lambda tau: -math.log(1 - tau) / lam + 100  # shifted exponential quantile function
        knots = quantile_knots(np.array([q(0.1), q(0.5), q(0.9), q(0.99)]))
        self.assertAlmostEqual(knots[4], q(0.999), places=8)

    def test_C39_window_share(self):
        self.assertAlmostEqual(100 / (7 * 24 * 4), 0.149, places=3)


if __name__ == "__main__":
    unittest.main()
