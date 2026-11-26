"""Workload generator, fast-simulator invariants and hand-checked cases, metrics and
the tuning rule."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import KDraws, select_by_rule  # noqa: E402
from prism_repro.metrics import runs_of_true, weighted_quantile_hist, window_attainment  # noqa: E402
from prism_repro.policies import OnDemand, Policy, Static  # noqa: E402
from prism_repro.pricing import stage_cost  # noqa: E402
from prism_repro.latency import stage_means, init_mean  # noqa: E402
from prism_repro.simulator import WEEK, SimContext, WeekDraws, simulate  # noqa: E402
from prism_repro.workload import MIN_PER_DAY, generate_trace  # noqa: E402
from scipy.stats import t as stats_t  # noqa: E402


class TestWorkload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tr = {sc: generate_trace(11, sc) for sc in ("stationary", "growth", "new_spike", "bursty")}

    def test_synthetic_label_and_determinism(self):
        a = generate_trace(11, "stationary")
        self.assertTrue(a["meta"]["synthetic"])
        np.testing.assert_array_equal(a["counts"], self.tr["stationary"]["counts"])

    def test_first_21_days_identical(self):
        b = self.tr["stationary"]["counts"][:21 * MIN_PER_DAY]
        for sc, t in self.tr.items():
            np.testing.assert_array_equal(t["counts"][:21 * MIN_PER_DAY], b)

    def test_mean_rate(self):
        self.assertAlmostEqual(self.tr["stationary"]["counts"][:21 * MIN_PER_DAY].mean() / 600, 1, delta=0.08)

    def test_growth_and_spike(self):
        s, g = self.tr["stationary"]["baseline"], self.tr["growth"]["baseline"]
        late = slice(25 * MIN_PER_DAY, 28 * MIN_PER_DAY)
        np.testing.assert_allclose(g[late] / s[late], 1.4)
        r_s, r_n = self.tr["stationary"]["rate"], self.tr["new_spike"]["rate"]
        t = np.arange(len(r_s))
        m15 = (t >= 21 * MIN_PER_DAY) & (t % 60 == 15)
        self.assertGreater(np.median(r_n[m15] / r_s[m15]), 2.9)

    def test_bursty_has_more_burst_mass(self):
        sl = slice(21 * MIN_PER_DAY, None)
        self.assertGreater(self.tr["bursty"]["rate"][sl].sum(), self.tr["stationary"]["rate"][sl].sum())


class FixedK(Policy):
    family = "Fixed"

    def __init__(self, P):
        super().__init__(None)
        self.Pv = np.asarray(P, float)

    def decide(self, k, tel):
        return self.Pv, 1024


def tiny_context(K_stage, N=1000.0, keepalive=10):
    cfg = PipelineConfig().with_(keepalive_min=keepalive)
    counts = np.full(2 * WEEK, N, dtype=np.int64)
    dr = WeekDraws(cfg, 5, 1)
    ctx = SimContext(cfg=cfg, counts=counts, week_start=WEEK, draws=dr,
                     K_hist_default=np.zeros((2 * WEEK, cfg.n_stages)), r_mean_peak=0.8)
    ctx._Kweek[1024] = np.repeat(np.asarray(K_stage, float)[:, None], cfg.n_stages, axis=1)
    return ctx


class TestFastSimulator(unittest.TestCase):
    def test_keepalive_cold_start_count_hand_example(self):
        K = np.zeros(WEEK)
        K[:6] = [0, 5, 5, 3, 8, 8]
        K[20] = 4  # pool from minute 4 (8 envs) expired after 10 idle minutes? last use at 5 -> pool 0 at 20
        res = simulate(tiny_context(K), OnDemand())
        cold = res["telemetry"].cold[:, 0]
        np.testing.assert_allclose(cold[:6], [0, 5, 0, 0, 3, 0])
        self.assertEqual(cold[20], 4)

    def test_provisioned_covers_all(self):
        K = np.full(WEEK, 10.0)  # N=100/min -> mean loads 1.3, 6.7, 4.2, 2.0 envs
        res = simulate(tiny_context(K, N=100.0), FixedK([20, 20, 20, 20]))
        s, tel = res["summary"], res["telemetry"]
        self.assertEqual(s["cost_od"], 0.0)
        self.assertEqual(tel.cold.sum(), 0.0)
        self.assertTrue(0.0 < s["billing_utilisation"] < 1.0)

    def test_cost_matches_independent_formula(self):
        K = np.full(WEEK, 30.0)
        K[::7] = 45
        P = np.array([5, 25, 15, 8], float)
        ctx = tiny_context(K)
        res = simulate(ctx, FixedK(P))
        tel, cfg, s = res["telemetry"], ctx.cfg, res["summary"]
        d = stage_means(cfg, 1024)
        tot = 0.0
        for st in range(4):
            n_od = tel.n_od[:, st]
            tot += stage_cost(P[st], 1000 - n_od, n_od, tel.cold[:, st], d[st], init_mean(cfg, 1024), 1.0,
                              60.0, cfg.prices).sum()
        tot += 1000 * WEEK * 4 * cfg.prices.req
        self.assertAlmostEqual(s["cost"], tot, places=6)

    def test_invariants_and_determinism(self):
        cfg = PipelineConfig()
        tr = generate_trace(3, "stationary")
        counts = tr["counts"]
        kh = np.vstack([KDraws(cfg, 3, w).peak_concurrency(counts[w * WEEK:(w + 1) * WEEK].astype(float), 1024)
                        for w in range(4)])
        ctx = SimContext(cfg=cfg, counts=counts, week_start=2 * WEEK, draws=WeekDraws(cfg, 3, 2), K_hist_default=kh)
        r1 = simulate(ctx, Static(90))
        r2 = simulate(ctx, Static(90))
        self.assertEqual(r1["summary"]["cost"], r2["summary"]["cost"])
        tel = r1["telemetry"]
        self.assertTrue(np.all(tel.cold <= tel.n_od + 1e-9))
        self.assertTrue(np.all(tel.n_od <= tel.N[:, None] + 1e-9))
        self.assertTrue(0 <= r1["summary"]["billing_utilisation"] <= 1)
        # policy-independent concurrency at 1024 MB matches the history draws (CRN)
        np.testing.assert_allclose(ctx.K_week(1024), kh[2 * WEEK:3 * WEEK])


class TestMetricsAndTuning(unittest.TestCase):
    def test_window_attainment(self):
        n = np.array([10, 10, 0, 0, 5, 5], float)
        ok = np.array([10, 9, 0, 0, 5, 4], float)
        att, late, tot = window_attainment(n, ok, 2)
        np.testing.assert_allclose(att, [0.95, 1.0, 0.9])
        np.testing.assert_allclose(late, [1, 0, 1])

    def test_runs(self):
        np.testing.assert_array_equal(runs_of_true([1, 1, 0, 1, 0, 0, 1, 1, 1]), [2, 1, 3])

    def test_weighted_quantile(self):
        rng = np.random.default_rng(0)
        v = rng.uniform(0, 20, (300, 50))
        w = rng.uniform(0, 3, (300, 1))
        q = weighted_quantile_hist(v, w, 0.99)
        flat, ww = v.ravel(), np.broadcast_to(w, v.shape).ravel()
        o = np.argsort(flat)
        ref = flat[o][np.searchsorted(np.cumsum(ww[o]), 0.99 * ww.sum())]
        self.assertAlmostEqual(q, ref, delta=0.02)

    def test_selection_rule(self):
        rows = [dict(cost=10, violating_window_rate=0.03), dict(cost=12, violating_window_rate=0.02),
                dict(cost=15, violating_window_rate=0.0)]
        self.assertEqual(select_by_rule(rows)["cost"], 12)
        rows = [dict(cost=10, violating_window_rate=0.05), dict(cost=12, violating_window_rate=0.03)]
        self.assertEqual(select_by_rule(rows)["cost"], 12)


class TestGridEdgeAudit(unittest.TestCase):
    """R5.M4 / R4.7: the audit applies the paper's selection rule per trace and family and flags a
    selection at either edge of the grid actually run; GRIDS_WIDE extends past every edge."""

    def _rows(self, fam_spec, vals, viol, cost, seed=1, week="val", tag=""):
        return [dict(seed=seed, scenario="stationary", week=week, tag=tag, spec=dict(fam_spec, param=v),
                     violating_window_rate=w, cost=c) for v, w, c in zip(vals, viol, cost)]

    def test_audit_flags_edges_by_rule(self):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "revision"))
        from grid_edge_audit import audit
        rows = (self._rows({"family": "PRISM"}, [0.01, 0.02, 0.05], [0.01, 0.015, 0.03], [30, 20, 10])  # interior
                + self._rows({"family": "PredHead"}, [1.0, 1.5, 2.0], [0.09, 0.06, 0.04], [10, 20, 30])  # none meets: high
                + self._rows({"family": "QuantProv", "tau_idx": 2}, [0.6, 0.9], [0.0, 0.0], [5, 9])       # cheapest: low
                + self._rows({"family": "QuantProv", "tau_idx": 3}, [0.6, 0.9], [0.05, 0.01], [5, 9])     # separate family
                + self._rows({"family": "PRISM"}, [0.005, 0.08], [0.0, 0.0], [1, 2], tag="-nohyst")       # ablation: ignored
                + [dict(seed=1, week="val", tag="", spec={"family": "OnDemand"}, violating_window_rate=0, cost=1)])
        res = {r["family"]: r for r in audit(rows)}
        self.assertEqual(set(res), {"PRISM", "PredHead", "QuantProv_q90", "QuantProv_q99"})
        self.assertEqual((res["PRISM"]["selected"], res["PRISM"]["edge"]), (0.02, False))
        self.assertEqual((res["PredHead"]["side"], res["PredHead"]["met_threshold"]), ("high", False))
        self.assertEqual((res["QuantProv_q90"]["selected"], res["QuantProv_q90"]["side"]), (0.6, "low"))
        self.assertEqual((res["QuantProv_q99"]["selected"], res["QuantProv_q99"]["side"]), (0.9, "high"))
        self.assertTrue(all(not r["post_hoc"] for r in res.values()))
        post = audit(self._rows({"family": "PRISM"}, [0.01, 0.05], [0.0, 0.0], [2, 1], week="test"), week="test")
        self.assertTrue(post[0]["post_hoc"] and post[0]["side"] == "high")

    def test_wide_grids_extend_past_both_edges(self):
        from prism_repro.experiment import GRIDS, GRIDS_WIDE
        self.assertEqual(set(GRIDS_WIDE), set(GRIDS))
        for fam, g in GRIDS.items():
            w = GRIDS_WIDE[fam]
            self.assertEqual(w, sorted(w), fam)
            self.assertTrue(set(g) <= set(w), fam)
            self.assertLess(min(w), min(g), fam)
            self.assertGreater(max(w), max(g), fam)


class TestRevisionTraceSet(unittest.TestCase):
    """R2.18 / R3.5 / R5.M4: the 30 revision traces are fixed a priori and recorded by checksum in
    data/trace_set_revision.json; regenerating any of them must reproduce the recorded counts."""

    def test_seeds_fixed_and_checksums_reproduce(self):
        import json
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "revision"))
        from trace_set import SEEDS, counts_sha256
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "data", "trace_set_revision.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual(m["seeds"], list(range(101, 131)))
        self.assertEqual(list(SEEDS), m["seeds"])
        self.assertFalse({7, 201, 202, 203, 204, 205} & set(m["seeds"]))   # dev seed, real traces
        self.assertTrue(m["all_first21_identical"])
        for seed in (101, 117, 130):
            for sc in ("stationary", "new_spike"):
                self.assertEqual(counts_sha256(generate_trace(seed, sc)["counts"]),
                                 m["counts_sha256"][str(seed)][sc], (seed, sc))


class TestByteIdenticalRerun(unittest.TestCase):
    """R2.16 / R3.5 gate: the same configuration run twice from scratch (forecaster training
    included) gives byte-identical outputs: every summary field except wall-clock timings and
    every raw array, for a forecast-driven policy and a baseline."""

    TIMING = ("sim_seconds", "decision_ms_median", "decision_ms_p99")

    def test_two_independent_runs_identical(self):
        from prism_repro.experiment import TraceBundle, make_policy
        cfg = PipelineConfig()
        out = []
        for _ in range(2):
            b = TraceBundle(101, cfg, scenarios=("stationary",))
            out.append([simulate(b.context("stationary", "val"), make_policy(spec))
                        for spec in ({"family": "PRISM", "param": 0.02}, {"family": "Reactive", "param": 0.6})])
        for r1, r2 in zip(*out):
            s1 = {k: v for k, v in r1["summary"].items() if k not in self.TIMING}
            s2 = {k: v for k, v in r2["summary"].items() if k not in self.TIMING}
            self.assertEqual(s1.keys(), s2.keys())
            for k in s1:
                a, b_ = np.asarray(s1[k]), np.asarray(s2[k])
                if a.dtype.kind in "biufc":   # numbers: compare the bytes
                    self.assertEqual((a.dtype, a.tobytes()), (b_.dtype, b_.tobytes()), k)
                else:                         # labels and other objects: compare values
                    self.assertEqual(s1[k], s2[k], k)
            self.assertEqual(sorted(r1["raw"]), sorted(r2["raw"]))
            for k in r1["raw"]:
                a, b_ = np.asarray(r1["raw"][k]), np.asarray(r2["raw"][k])
                self.assertEqual(a.dtype.kind in "biufc", True, k)
                self.assertEqual((a.dtype, a.shape, a.tobytes()), (b_.dtype, b_.shape, b_.tobytes()), k)


class TestEpsWindowMapping(unittest.TestCase):
    """R2.3 / R7.3: the epsilon -> violating-window mapping uses the trace as the unit, a t-interval
    over traces, and scores held-out weeks against a prediction interval refitted without them."""

    def _mod(self):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "revision"))
        import eps_window_mapping
        return eps_window_mapping

    def test_curve_interval_and_leave_one_out(self):
        m = self._mod()
        rows = []
        for s, off in zip((1, 2, 3, 4), (0.000, 0.002, 0.004, 0.006)):
            for e in (0.01, 0.03, 0.05):
                rows.append(dict(seed=s, week="val", scenario="stationary", tag="",
                                 spec={"family": "PRISM", "param": e}, violating_window_rate=e / 2 + off))
                for sc in ("a", "b"):
                    rows.append(dict(seed=s, week="test", scenario=sc, tag="",
                                     spec={"family": "PRISM", "param": e}, violating_window_rate=e / 2 + off))
        rows.append(dict(seed=1, week="val", scenario="stationary", tag="-nohyst",
                         spec={"family": "PRISM", "param": 0.01}, violating_window_rate=0.9))   # ablation: ignored
        pts = m.prism_points(rows)
        self.assertEqual(len(pts), 4 * 3 * 3)
        c = m.curve(pts, "val")
        x = np.array([0.005, 0.007, 0.009, 0.011])
        t = stats_t.ppf(0.975, 3)
        self.assertAlmostEqual(c[0.01]["mean"], x.mean(), places=12)
        self.assertAlmostEqual(c[0.01]["ci"][1], x.mean() + t * x.std(ddof=1) / 2, places=12)
        self.assertAlmostEqual(c[0.01]["pi"][1], x.mean() + t * x.std(ddof=1) * np.sqrt(1.25), places=12)
        res = m.analyse(pts)
        self.assertEqual(res["val_to_test_pi_coverage"], 1.0)   # test weeks equal validation here
        self.assertEqual(res["loo_n"], 24)
        self.assertAlmostEqual(res["spearman_eps_vs_val_rate"], 1.0)
        self.assertEqual(res["operator_max_eps_upper_pi_within_target"], 0.01)


if __name__ == "__main__":
    unittest.main()
