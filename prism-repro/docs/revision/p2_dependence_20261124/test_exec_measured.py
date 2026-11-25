"""Opt-in per-memory execution-time mode (exec_scaling="measured"; calibration candidate, 24 Nov 2026)."""
import unittest

import numpy as np

from prism_repro.config import PipelineConfig
from prism_repro.latency import duration_factor, miss_table, stage_means

# memcal-1 FIT-split factors relative to 1024 MB (docs/revision/calibration_20261124/exec_factor_measured.json)
FAC = ((512, (2.026158, 2.013151, 2.012798, 2.033747)), (1024, (1.0, 1.0, 1.0, 1.0)),
       (2048, (0.57838, 0.574046, 0.57394, 0.571574)), (3008, (0.578199, 0.572444, 0.573641, 0.570857)))


class TestLegacyUnchanged(unittest.TestCase):
    def test_default_is_eq2(self):
        cfg = PipelineConfig()
        self.assertEqual(cfg.exec_scaling, "eq2")
        self.assertIsNone(cfg.exec_factor_measured)
        for m in cfg.mem_options:
            np.testing.assert_array_equal(stage_means(cfg, m), np.asarray(cfg.warm_mean_1024) * duration_factor(m, 0.5))

    def test_legacy_values_by_hand(self):
        # Eq. (2) at non-scaling 0.5: 2048 MB -> 0.75, 512 MB -> 1.5; ingest 0.8 s at 1024 MB
        cfg = PipelineConfig()
        self.assertAlmostEqual(stage_means(cfg, 2048)[0], 0.6)
        self.assertAlmostEqual(stage_means(cfg, 512)[1], 6.0)


class TestMeasuredLookup(unittest.TestCase):
    def setUp(self):
        self.cfg = PipelineConfig().with_(exec_scaling="measured", exec_factor_measured=FAC)

    def test_lookup_and_units_seconds(self):
        # transform: 4.0 s at 1024 MB x 0.574046 = 2.296184 s at 2048 MB (memcal-1 CHECK median 2.289 s)
        self.assertAlmostEqual(stage_means(self.cfg, 2048)[1], 4.0 * 0.574046, places=12)
        np.testing.assert_allclose(stage_means(self.cfg, 1024), self.cfg.warm_mean_1024)
        np.testing.assert_allclose(stage_means(self.cfg, 512), np.asarray(self.cfg.warm_mean_1024) * np.asarray(FAC[0][1]))

    def test_plateau(self):
        # measured: no speed-up from 2048 to 3008 MB (Eq. (2) would give a further 11%)
        r = stage_means(self.cfg, 3008) / stage_means(self.cfg, 2048)
        self.assertTrue(np.all(np.abs(r - 1) < 0.005))

    def test_unsupported_memory(self):
        with self.assertRaises(ValueError):
            stage_means(self.cfg, 1536)
        with self.assertRaises(ValueError):
            stage_means(self.cfg, 2048.5)

    def test_caches_distinguish_modes(self):
        a, b = miss_table(PipelineConfig().with_(deadline=13.0)), miss_table(self.cfg.with_(deadline=13.0))
        self.assertEqual(a[1024], b[1024])          # same at the reference size
        self.assertNotEqual(a[2048], b[2048])       # different scaling, different warm miss table


class TestValidation(unittest.TestCase):
    def test_bad_mode(self):
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="linear")

    def test_missing_size(self):
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="measured", exec_factor_measured=FAC[:3])

    def test_wrong_stage_count_or_sign(self):
        bad = ((512, (2.0, 2.0, 2.0)),) + FAC[1:]
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="measured", exec_factor_measured=bad)
        neg = ((512, (2.0, -1.0, 2.0, 2.0)),) + FAC[1:]
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="measured", exec_factor_measured=neg)

    def test_reference_must_be_one(self):
        bad = FAC[:1] + ((1024, (1.0, 1.0, 1.01, 1.0)),) + FAC[2:]
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="measured", exec_factor_measured=bad)

    def test_measured_without_factors(self):
        with self.assertRaises(ValueError):
            PipelineConfig().with_(exec_scaling="measured")


if __name__ == "__main__":
    unittest.main()
