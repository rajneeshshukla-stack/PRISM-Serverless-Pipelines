"""PRISM's main configuration is found as "PRISM" by the experiments that reuse its selection (E3, E7, E9).

policies.PRISM names runs after the risk model ('PRISM_EB' for Erlang-B, 'PRISM' for Eq. (5)). Since f119bee made
Erlang-B the default, the main configuration's E1 rows read 'PRISM_EB', and E3, E7 and E9 failed with KeyError: 'PRISM'
in selections(). These tests pin the naming, the lookup and the guard against mixing the two risk models.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "experiments"))

from prism_repro.config import PrismConfig  # noqa: E402
from prism_repro.experiment import make_policy  # noqa: E402
import run_experiments as RX  # noqa: E402


def _row(seed, policy, param, cost, viol, risk=None):
    spec = dict(family="PRISM", param=param)
    if risk:
        spec["prism"] = dict(risk_model=risk)
    return dict(seed=seed, week="val", status="ok", policy=policy, label=f"{policy}-{param}", spec=spec, param=param,
                cost=cost, violating_window_rate=viol)


class MainPrismVariant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._results = RX.RESULTS
        RX.RESULTS = self.tmp

    def tearDown(self):
        RX.RESULTS = self._results
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rows):
        os.makedirs(os.path.join(self.tmp, "E1"), exist_ok=True)
        with open(os.path.join(self.tmp, "E1", "rows.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def test_naming_follows_risk_model(self):
        self.assertEqual(PrismConfig().risk_model, "erlangb")
        self.assertEqual(make_policy(dict(family="PRISM", param=0.05)).variant, "PRISM_EB")
        self.assertEqual(make_policy(dict(family="PRISM", param=0.05, prism=dict(risk_model="occupancy"))).variant,
                         "PRISM")
        self.assertEqual(RX.MAIN_PRISM_VARIANT, "PRISM_EB")

    def test_selection_keyed_prism_for_main_configuration(self):
        self._write([_row(101, "PRISM_EB", e, c, v) for e, c, v in ((0.02, 1200, 0.005), (0.05, 1100, 0.012),
                                                                    (0.08, 1000, 0.030))]
                    + [dict(seed=101, week="val", status="ok", policy="Static", label="Static-95",
                            spec=dict(family="Static", param=95), param=95, cost=1500, violating_window_rate=0.01)])
        sel = RX.selections(101)
        self.assertEqual(set(sel), {"PRISM", "Static"})
        self.assertEqual(sel["PRISM"], dict(family="PRISM", param=0.05))   # cheapest with <= 2% violating windows
        self.assertEqual(make_policy(sel["PRISM"]).label, "PRISM_EB-0.05")   # E1's stored label, for array lookups

    def test_submitted_style_rows_unchanged(self):
        self._write([_row(101, "PRISM", 0.05, 1100, 0.01, risk="occupancy")])
        self.assertEqual(set(RX.selections(101)), {"PRISM"})

    def test_mixed_risk_models_refused(self):
        self._write([_row(101, "PRISM_EB", 0.05, 1100, 0.01), _row(101, "PRISM", 0.05, 1090, 0.012, risk="occupancy")])
        with self.assertRaises(ValueError):
            RX.selections(101)


if __name__ == "__main__":
    unittest.main()
