"""Hand-calculated checks of integrated_estimate.py. Run from prism-repro/:
venv/Scripts/python -m unittest docs/revision/billing_r214_pc_20261124/test_integrated_estimate.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrated_estimate as ie  # noqa: E402

REQ, PCD, OD = 2e-7, 9.7222e-6, 1.66667e-5


class T(unittest.TestCase):
    def test_prices_are_the_simulators(self):
        self.assertEqual((ie.PR.req, ie.PR.pcd, ie.PR.od), (REQ, PCD, OD))

    def test_decomposition(self):
        row = dict(cost=10.0, cost_pc=4.0, cost_pcd=3.0, cost_od=2.0, cost_init=0.5, cost_req=0.5)
        self.assertAlmostEqual(ie.decomposition_gap(row), 0.0)
        row["cost"] = 10.1
        self.assertAlmostEqual(ie.decomposition_gap(row), 0.1)

    def test_rounding_hand_case_1024(self):
        # 1,000,000 invocations (cost_req = 0.2 USD), 10% overflow, all at 1024 MB.
        # mid: 0.5 ms x 1 GB x (900,000 x PCD + 100,000 x OD) = 0.0005 x (8.74998 + 1.66667) = 0.005208325 USD
        row = dict(cost_req=0.2, overflow_share=0.1, share_mem_ge_2048=0.0)
        self.assertAlmostEqual(ie.rounding_increment_usd(row, 0.5, False), 0.0005 * (900000 * PCD + 100000 * OD), places=12)
        self.assertAlmostEqual(ie.rounding_increment_usd(row, 0.5, False), 0.005208325, places=9)
        # upper: 1 ms; memory share 0 -> GB = 1
        self.assertAlmostEqual(ie.rounding_increment_usd(row, 1.0, True), 0.01041665, places=9)

    def test_rounding_memory_share(self):
        # half the minutes at >= 2048 MB: mid uses 2048 (GB 2), upper 3008 (GB 2.9375)
        row = dict(cost_req=0.2, overflow_share=0.0, share_mem_ge_2048=0.5)
        base = 1e-3 * 1000000 * PCD
        self.assertAlmostEqual(ie.rounding_increment_usd(row, 1.0, False), base * (0.5 + 0.5 * 2.0), places=12)
        self.assertAlmostEqual(ie.rounding_increment_usd(row, 1.0, True), base * (0.5 + 0.5 * 2.9375), places=12)


if __name__ == "__main__":
    unittest.main()
