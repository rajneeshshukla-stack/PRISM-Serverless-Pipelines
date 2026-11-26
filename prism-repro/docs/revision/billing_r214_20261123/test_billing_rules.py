"""Hand-calculated checks of billing_rules.py (R2.14(a)) and of the memcal-1 list-price totals."""
import csv
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import billing_rules as B  # noqa: E402


class BillingRules(unittest.TestCase):
    def test_billed_duration_rounds_up(self):
        self.assertEqual(B.billed_ms(1624.37), 1625)          # ceil
        self.assertEqual(B.billed_ms(801.01, 113.70), 915)    # 914.71 -> 915, Init included
        self.assertEqual(B.billed_ms(0.2), 1)

    def test_whole_millisecond_sum_gets_one_more(self):
        self.assertEqual(B.billed_ms(100.0), 101)             # the 94-record quirk: floor + 1
        self.assertEqual(B.billed_ms(450.25, 49.75), 501)     # sum 500.00 exactly

    def test_charge_hand_calculated(self):
        # 1625 ms at 1024 MB: 1.625 GB-s x 1.66667e-5 = 2.70833875e-5, + 2e-7 request = 2.72833875e-5
        self.assertAlmostEqual(B.charge(1624.37, 0, 1024), 1.625 * 1.66667e-5 + 2e-7, places=15)
        self.assertAlmostEqual(B.charge(1624.37, 0, 1024), 2.72833875e-5, places=13)
        # 915 ms at 2048 MB: 1.83 GB-s x 1.66667e-5 = 3.05000610e-5, + 2e-7 = 3.07000610e-5
        self.assertAlmostEqual(B.charge(801.01, 113.70, 2048), 3.0700061e-5, places=12)
        # 3008 MB, 2288 ms (2287.4 rounded up): 2.288 x 2.9375 = 6.7210 GB-s
        self.assertAlmostEqual(B.gb_seconds(B.billed_ms(2287.4), 3008), 2.288 * 3008 / 1024, places=12)

    def test_increment_bounds(self):
        for d in (0.0, 0.5, 1.0, 1624.37, 2287.999, 5000.0):
            self.assertTrue(0 < B.rounding_increment_ms(d) <= 1.0 + 1e-9, d)

    def test_memcal_list_price_totals(self):
        # billing.csv: billed GB-s and requests per block (AWS's own Billed Duration); list price as the paper's.
        p = os.path.join(HERE, "..", "aws_memcal_20261122", "tables", "billing.csv")
        rows = {r["scope"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}
        blocks = [rows[f"block {b}"] for b in (0, 1, 2)]
        req = sum(int(r["requests"]) for r in blocks)
        gbs = sum(float(r["billed_gb_s"]) for r in blocks)
        self.assertEqual(req, 20992)
        self.assertAlmostEqual(gbs, 55234.5, places=1)
        usd = gbs * B.OD_GBS + req * B.REQ
        self.assertAlmostEqual(usd, 0.9248, places=4)          # 0.92058 duration + 0.00420 requests
        self.assertAlmostEqual(sum(float(r["usd_lambda_list_price"]) for r in blocks), 0.9247, places=3)


if __name__ == "__main__":
    unittest.main()
