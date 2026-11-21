"""Regression anchors: numbers the response letter cites, pinned to the precision at which they are cited.

The behavioural tests bound these quantities (Erlang-B within 2.5%, Eq. (5) 20-28% off); a code change could
move a cited figure and still pass them. These tests fail on any change that moves a cited value at its
printed precision. A change that moves one is a regression until shown otherwise: investigate, then update
the letter and this test together, never the test alone. Provenance of every value: notes/number_audit.md.

Platform note: these are deterministic computations without the GBM forecaster, so they are expected to hold
on every platform; forecast-driven figures (e.g. the level-choice count) are deliberately not pinned here
because they differ between platforms at identical code and package versions."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "revision"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, _stage_pass  # noqa: E402
from prism_repro.latency import init_mean  # noqa: E402
from prism_repro.risk import c_eff, erlang_b, occupancy_overflow  # noqa: E402
from scipy import stats  # noqa: E402


def _run_script_main(module_name):
    """Run a revision script's own main() into a temporary JSON file and return the parsed output."""
    mod = __import__(module_name)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    saved = sys.argv
    sys.argv = [module_name + ".py", os.path.join(HERE, ".."), path]
    try:
        mod.main()
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        sys.argv = saved
        os.remove(path)


class TestOverflowAnchors(unittest.TestCase):
    """R3.4, R4.9: Erlang-B 0.116156 vs event-level 0.118431 (1.92%); Eq. (5) at c_eff 0.144785 (22.25%)."""

    def test_values_at_printed_precision(self):
        cfg = PipelineConfig()
        counts = np.random.default_rng(0).poisson(600, 400)
        dr = EventDraws(cfg, counts, 3, 0)
        _, _, pc = _stage_pass(dr.arrival, dr.ex[1] * 4.0, dr.init[1] * 6.0, np.full(400, 40.0), 600.0)
        measured = 1 - pc.mean()
        eb, eq5 = float(erlang_b(40, 40)), float(occupancy_overflow(40, c_eff(40)))
        self.assertEqual(round(measured, 6), 0.118431)
        self.assertEqual(round(eb, 6), 0.116156)
        self.assertEqual(round(eq5, 6), 0.144785)
        self.assertEqual(round(100 * abs(eb - measured) / measured, 2), 1.92)
        self.assertEqual(round(100 * abs(eq5 - measured) / measured, 2), 22.25)


class TestImpossibleInitAnchors(unittest.TestCase):
    """R4.8: under the submitted log-normal, 3.20% of 1024 MB and 16.40% of 512 MB initialisations exceed 10 s."""

    def test_shares(self):
        cfg = PipelineConfig()
        for m, share in ((1024, 3.20), (512, 16.40)):
            mu, s = init_mean(cfg, m), cfg.init_shape
            p = stats.norm.sf((np.log(10.0 / mu) + s * s / 2) / s)
            self.assertEqual(round(100 * p, 2), share, m)


class TestOptimalityGapAnchors(unittest.TestCase):
    """R2.13, R4.1, R2.5: static gaps of the one-parameter family (static benchmarks, not end-to-end)."""

    def test_integer_search_static_gap(self):
        out = _run_script_main("integer_search_gap")["totals"]
        self.assertEqual(out["configurations"], 16)
        self.assertEqual(round(100 * out["mean_gap"], 2), 2.71)
        self.assertEqual(round(100 * out["min_gap"], 2), 1.52)
        self.assertEqual(round(100 * out["max_gap"], 2), 5.90)

    def test_stage_demand_gaps(self):
        out = _run_script_main("stage_demand_gap")
        by = out["by_profile"]
        self.assertEqual(round(100 * by["common"]["mean_gap"], 2), 2.90)
        self.assertEqual(round(100 * by["filter_half_at_2"]["mean_gap"], 2), 5.06)
        self.assertEqual(round(100 * by["batch_10to1_at_4"]["mean_gap"], 2), 5.78)
        fan = [r for r in out["rows"] if r["profile"] == "fanout_x3_at_3"]
        self.assertEqual(len(fan), 3)
        self.assertTrue(all(not r["family_feasible"] and r["default_level_hi"] == 1.15 for r in fan))
        at4 = [w for r in fan if r["eps"] == 0.02 for w in r["level_hi_sweep"] if w["level_hi"] == 4.0]
        self.assertTrue(at4[0]["family_feasible"])
        self.assertEqual(round(100 * at4[0]["gap"], 2), 17.40)


if __name__ == "__main__":
    unittest.main()
