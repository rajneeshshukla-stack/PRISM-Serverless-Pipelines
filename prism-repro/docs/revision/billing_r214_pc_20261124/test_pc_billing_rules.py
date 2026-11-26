"""Hand-calculated checks of pc_billing_rules.py, including AWS's own worked examples from the pricing page
(read 24 Nov 2026). Run: python -m unittest test_pc_billing_rules.py (from this folder)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pc_billing_rules import (PC_GBS, PCD_GBS, capacity_charge, capacity_gb_s, invocation_charge,  # noqa: E402
                              pc_invocation_billed_ms, round_up_5min, unresolved_pc_initialisation)
from billing_rules import OD_GBS, REQ  # noqa: E402


class TestAWSWorkedExamples(unittest.TestCase):
    def test_cyber_monday_example(self):
        # PC 7 at 4096 MB for 24 h; 2,000,000 requests of 280 ms, all on PC. AWS: $10.08 + $21.78 + $0.40 = $32.26
        cap = capacity_charge([(0, 86_400, 7)], 4096)
        self.assertAlmostEqual(capacity_gb_s([(0, 86_400, 7)], 4096), 2_419_200)
        self.assertEqual(round(cap, 2), 10.08)
        inv = 2_000_000 * invocation_charge(280, 4096, on_pc=True)
        compute, req = inv - 2_000_000 * REQ, 2_000_000 * REQ
        self.assertAlmostEqual(compute, 2_240_000 * PCD_GBS, places=6)
        self.assertEqual((round(compute, 2), round(req, 2)), (21.78, 0.40))
        self.assertEqual(round(round(cap, 2) + round(compute, 2) + round(req, 2), 2), 32.26)

    def test_mobile_launch_example_components(self):
        # PC 100 at 1536 MB for 8 h: 150 GB x 28,800 s = 4,320,000 GB-s -> $18; 500,000 requests of 100 ms on PC:
        # 75,000 GB-s -> $0.73; 2,500,000 requests of 120 ms without PC: 450,000 GB-s, minus the example's 400,000 GB-s
        # free tier (U5) -> 50,000 GB-s -> $0.83; requests 3M - 1M free -> $0.40. AWS total $19.96.
        self.assertAlmostEqual(capacity_gb_s([(0, 28_800, 100)], 1536), 4_320_000)
        self.assertEqual(round(capacity_charge([(0, 28_800, 100)], 1536), 2), 18.00)
        pc_compute = 500_000 * (invocation_charge(100, 1536, on_pc=True) - REQ)
        self.assertEqual(round(pc_compute, 2), 0.73)
        od_gbs = 2_500_000 * (120 + 1) / 1000 * 1.5          # measured on-demand rule: 120 ms whole -> 121 ms billed
        self.assertAlmostEqual(od_gbs, 453_750)                # vs the example's 450,000 (it uses unrounded 120 ms)
        self.assertEqual(round((450_000 - 400_000) * OD_GBS, 2), 0.83)
        self.assertEqual(round(18.00 + 0.40 + 0.73 + 0.83, 2), 19.96)


class TestRules(unittest.TestCase):
    def test_five_minute_rounding_and_activation_is_billed(self):
        # enabled for 7 min, READY after 2 min: billed 10 min from enabling (activation time is billed)
        self.assertEqual(round_up_5min(420), 600)
        self.assertAlmostEqual(capacity_gb_s([(0, 420, 2)], 1024), 2 * 600)
        self.assertEqual(round_up_5min(300), 300)

    def test_amount_changes_on_five_minute_boundaries_agree(self):
        segs = [(0, 300, 2), (300, 900, 1), (900, 1200, 3)]    # PRISM-like 5-minute epochs
        self.assertAlmostEqual(capacity_gb_s(segs, 2048, "period"), capacity_gb_s(segs, 2048, "segment"))
        self.assertAlmostEqual(capacity_gb_s(segs, 2048), 2.0 * (2 * 300 + 1 * 600 + 3 * 300))

    def test_amount_changes_off_boundary_bound_the_ambiguity(self):
        segs = [(0, 200, 2), (200, 400, 1)]                    # 400 s -> one 10-min period, or 5 + 5 min
        p, s = capacity_gb_s(segs, 1024, "period"), capacity_gb_s(segs, 1024, "segment")
        self.assertAlmostEqual(p, 2 * 200 + 1 * 200 + 1 * 200)  # extra 200 s at the last amount (1)
        self.assertAlmostEqual(s, 2 * 300 + 1 * 300)
        self.assertGreater(s, p)

    def test_pc_and_overflow_invocations(self):
        # 1,624.37 ms at 1024 MB: on PC ceil -> 1,625 ms x 1 GB x PCD + req; overflow with a 412.5 ms init on demand:
        # floor(2,036.87) + 1 = 2,037 ms x OD + req
        self.assertAlmostEqual(invocation_charge(1624.37, 1024, True), 1.625 * PCD_GBS + REQ)
        self.assertAlmostEqual(invocation_charge(1624.37, 1024, False, init_ms=412.5), 2.037 * OD_GBS + REQ)
        with self.assertRaises(ValueError):
            invocation_charge(100, 1024, True, init_ms=5)

    def test_pc_rounding_differs_from_measured_on_demand_only_at_whole_ms(self):
        self.assertEqual(pc_invocation_billed_ms(120), 120)     # documented: rounded up to the nearest 1 ms
        self.assertEqual(pc_invocation_billed_ms(120.2), 121)

    def test_unresolved_components_refuse(self):
        with self.assertRaises(NotImplementedError):
            unresolved_pc_initialisation()

    def test_invalid_segments(self):
        with self.assertRaises(ValueError):
            capacity_gb_s([(0, 100, 1), (150, 200, 1)], 1024)
        with self.assertRaises(ValueError):
            capacity_gb_s([(0, 100, 0)], 1024)
        self.assertEqual(PC_GBS, 0.0000041667)


if __name__ == "__main__":
    unittest.main()
