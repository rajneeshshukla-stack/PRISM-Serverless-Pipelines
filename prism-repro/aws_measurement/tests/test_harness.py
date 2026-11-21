"""Local validation of the measurement harness. NO AWS CALLS: every test uses fixtures or FakeLambda, socket creation
is blocked for the whole module, and boto3 must never be imported.

Run from prism-repro/aws_measurement:  ../venv/Scripts/python -m unittest discover -s tests -v
"""
import base64
import contextlib
import importlib
import io
import json
import math
import os
import socket
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from prism_measure import analyse as A  # noqa: E402
from prism_measure import aws  # noqa: E402
from prism_measure.design import CAP_MAX, Cell, Design, Visit, build_design, check_cap  # noqa: E402
from prism_measure.dryrun import fake_for, run_dry  # noqa: E402
from prism_measure.estimate import estimate  # noqa: E402
from prism_measure.fake import FakeLambda, Truth  # noqa: E402
from prism_measure.report import format_report_line, parse_log_tail, parse_report_line  # noqa: E402
from prism_measure.runner import Runner, fallback_reports  # noqa: E402

_REAL_SOCKET = socket.socket


def setUpModule():
    def blocked(*a, **k):
        raise RuntimeError("network access attempted in a harness test")
    socket.socket = blocked


def tearDownModule():
    socket.socket = _REAL_SOCKET


class TestReport(unittest.TestCase):
    def test_cold_line(self):
        r = parse_report_line("REPORT RequestId: 8f5c-1\tDuration: 812.32 ms\tBilled Duration: 813 ms\t"
                              "Memory Size: 1024 MB\tMax Memory Used: 41 MB\tInit Duration: 152.07 ms\t")
        self.assertEqual(r["request_id"], "8f5c-1")
        self.assertEqual((r["duration_ms"], r["billed_duration_ms"], r["init_duration_ms"]), (812.32, 813.0, 152.07))
        self.assertEqual((r["memory_size_mb"], r["max_memory_used_mb"]), (1024, 41))
        self.assertTrue(r["complete"])

    def test_warm_line_has_no_init(self):
        r = parse_report_line(format_report_line("abc", 10.0, 11, 512, 30))
        self.assertIsNone(r["init_duration_ms"])
        self.assertEqual(r["duration_ms"], 10.0)        # not confused with Billed Duration

    def test_duration_not_taken_from_init_or_billed(self):
        r = parse_report_line("REPORT RequestId: x\tInit Duration: 5.00 ms\tBilled Duration: 7 ms\tDuration: 6.50 ms\t"
                              "Memory Size: 512 MB\tMax Memory Used: 9 MB")
        self.assertEqual((r["duration_ms"], r["init_duration_ms"], r["billed_duration_ms"]), (6.5, 5.0, 7.0))

    def test_incomplete_and_garbage(self):
        self.assertFalse(parse_report_line("REPORT RequestId: x\tDuration: 1.00 ms")["complete"])
        self.assertIsNone(parse_report_line("START RequestId: x Version: $LATEST"))
        self.assertIsNone(parse_log_tail(None))
        self.assertIsNone(parse_log_tail("@@not-base64@@"))

    def test_tail(self):
        tail = "START RequestId: q\nEND RequestId: q\n" + format_report_line("q", 3.0, 3, 2048, 20, 99.5) + "\n"
        r = parse_log_tail(base64.b64encode(tail.encode()).decode())
        self.assertEqual((r["request_id"], r["init_duration_ms"]), ("q", 99.5))
        self.assertIsNone(parse_log_tail(base64.b64encode(b"START RequestId: q\nEND RequestId: q\n").decode()))


class TestDesign(unittest.TestCase):
    def test_counts_match_the_plan(self):
        d = build_design()
        c = d.counts()
        self.assertEqual(len(c), 4 * 4 + 2 * 4)
        for k, v in c.items():
            cold, warm = (232, 1000) if k.startswith("main/") else (232, 200)
            self.assertEqual((v["cold"], v["warm"], v["cold_batches"]), (cold, warm, 29), k)
            self.assertGreaterEqual(v["cold_batches"], 25)
        self.assertEqual(sum(v["cold"] + v["warm"] for v in c.values()), 23168)
        self.assertEqual({c.memory_mb for c in d.cells()}, {512, 1024, 2048, 3008})

    def test_cap_everywhere(self):
        d = build_design()
        self.assertTrue(all(v.cold <= CAP_MAX and all(w <= CAP_MAX for w in v.warm_batches) for v in d.visits))
        self.assertEqual(CAP_MAX, 8)
        for bad in (0, 9, 10):
            with self.assertRaises(ValueError):
                check_cap(bad)
            with self.assertRaises(ValueError):
                build_design(batch=bad)

    def test_blocks_and_randomisation(self):
        d = build_design()
        for key, v in d.counts().items():
            blocks = {x.block for x in d.visits if x.cell.key == key}
            self.assertEqual(blocks, {0, 1, 2}, key)          # every cell visited on every day
        for b in range(3):
            seq = [v.cell.memory_mb for v in d.visits if v.block == b]
            self.assertNotEqual(seq, sorted(seq))              # memory sizes interleaved, not in sequence
            self.assertGreater(sum(x != y for x, y in zip(seq, seq[1:])), len(seq) // 2)
        same = build_design(seed=20261121)
        self.assertEqual([v.cell.key for v in d.visits], [v.cell.key for v in same.visits])
        other = build_design(seed=7)
        self.assertNotEqual([v.cell.key for v in d.visits], [v.cell.key for v in other.visits])

    def test_function_names(self):
        self.assertEqual(Cell("main", "ingest", 512).function, "prism-meas-ingest-512")
        self.assertEqual(Cell("init", "init_first_call", 3008).function, "prism-meas-init-first-call-3008")


class TestJoinFixture(unittest.TestCase):
    """Hand-computed expectations for tests/fixtures/join_fixture.jsonl (see build_join_fixture.py).
    Cold used: r1 r2 r3 r4 -> e2e median 2.3, Duration median 1.15, Init median of 0.3/0.4/0.5 (r4 has none) 0.4.
    Warm used: w1 w2 w3 w5 -> e2e median 1.3, Duration median 0.95. P = 1.0, X = 0.2, I = 0.4, R = 0.4."""

    @classmethod
    def setUpClass(cls):
        f = os.path.join(HERE, "fixtures")
        cls.recs = A.load_jsonl(os.path.join(f, "join_fixture.jsonl"))
        cls.cw = {r["request_id"]: r for r in A.load_jsonl(os.path.join(f, "join_fixture_cloudwatch.jsonl"))}
        cls.res = A.analyse(cls.recs, cls.cw, n_boot=50)

    def test_values(self):
        (c,) = self.res["cells"]
        self.assertEqual((c["n_cold"], c["n_cold_with_init"], c["n_warm"]), (4, 3, 4))
        self.assertEqual((c["cold_batches"], c["warm_batches"]), (2, 2))
        for q, v in (("P", 1.0), ("X", 0.2), ("I", 0.4), ("R", 0.4), ("P_mean", 1.0)):
            self.assertAlmostEqual(c[f"{q}_s"], v, places=6, msg=q)

    def test_missing_accounting(self):
        (m,) = self.res["missing"]
        expect = {"invocations": 14, "report_from_cloudwatch": 1, "no_report": 0, "throttled": 1, "no_request_id": 1,
                  "duplicate_request_id": 2, "payload_id_mismatch": 1, "report_id_mismatch": 1,
                  "cold_without_init": 1, "unexpected_warm_in_cold_batch": 1, "unexpected_cold_in_warm_batch": 0,
                  "warm_with_init": 0, "error": 0, "function_error": 0, "report_incomplete": 0}
        for k, v in expect.items():
            self.assertEqual(m[k], v, k)
        self.assertEqual(self.res["issues"], {"incomplete_visit_invocations_dropped": 1, "orphan_cloudwatch_reports": 1})

    def test_without_cloudwatch_the_report_is_missing(self):
        (m,) = A.analyse(self.recs, None, n_boot=10)["missing"]
        self.assertEqual((m["no_report"], m["report_from_cloudwatch"]), (1, 0))

    def test_billing(self):
        (b,) = self.res["billing"]
        self.assertEqual((b["requests"], b["reports_with_billing"]), (14, 13))   # 6 (v1) + 8 (v2); v3 dropped
        self.assertGreater(b["cost_usd_if_init_billed"], b["cost_usd_at_model_prices"])


def synthetic(p_of_m, sizes=(512, 1024, 2048, 3008), batches=25, per=8, warm_s=1.0, noise_s=0.02, seed=11):
    """Records for one stage with >= 25 batches per cell; cold e2e = warm + p_of_m(m) + N(0, noise_s), seeded, so
    the bootstrap intervals have a real width."""
    import random
    rng = random.Random(seed)
    recs = []
    for m in sizes:
        for b in range(batches):
            vid = f"m{m}-v{b}"
            for kind in ("cold", "warm"):
                for i in range(per):
                    e2e = warm_s + rng.gauss(0.0, noise_s) + (p_of_m(m) if kind == "cold" else 0.0)
                    rid = f"{vid}-{kind}-{i}"
                    rep = {"request_id": rid, "duration_ms": 500.0, "billed_duration_ms": 500.0, "memory_size_mb": m,
                           "max_memory_used_mb": 30, "init_duration_ms": 100.0 if kind == "cold" else None,
                           "restore_duration_ms": None, "complete": True}
                    recs.append({"type": "invocation", "visit_id": vid, "attempt": 0, "batch_id": f"{vid}-{kind}",
                                 "batch_kind": kind, "group": "main", "variant": "ingest", "memory_mb": m,
                                 "function": f"f{m}", "request_id": rid, "e2e_s": e2e, "error": None,
                                 "function_error": None, "report": rep, "report_source": "tail",
                                 "payload": {"first_call": kind == "cold", "aws_request_id": rid}})
            recs.append({"type": "visit_done", "visit_id": vid, "attempt": 0})
    return recs


class TestDecision(unittest.TestCase):
    S_EQ = A.eq3_slope((512, 1024, 2048, 3008))

    def test_eq3_slope_is_the_simulators(self):
        self.assertAlmostEqual(self.S_EQ, -0.2727, places=3)      # same as the external analysis (-0.273)

    def test_zero_width_interval_at_eq3_counts_as_containing_it(self):
        s = self.S_EQ
        self.assertTrue(A.decision(s + 1e-15, s + 1e-15, s).startswith("keep Eq. (3)"))

    def test_rule_table(self):
        s = self.S_EQ
        self.assertTrue(A.decision(-0.4, -0.2, s).startswith("keep Eq. (3)"))
        self.assertIn("'constant' is not excluded", A.decision(-0.4, 0.1, s))
        self.assertTrue(A.decision(-0.9, -0.5, s).startswith("keep the direction"))
        self.assertTrue(A.decision(-0.1, 0.1, s).startswith("init_scaling = 'constant'"))
        self.assertTrue(A.decision(0.05, 0.2, s).startswith("init_scaling = 'inverted'"))
        self.assertTrue(A.decision(math.nan, 0.1, s).startswith("not estimable"))

    def _trend(self, recs):
        res = A.analyse(recs, n_boot=300)
        return next(t for t in res["trends"] if t["variant"] == "ingest")

    def test_constant_penalty_gives_constant(self):
        t = self._trend(synthetic(lambda m: 1.0))
        self.assertTrue(t["decision_on_P"].startswith("init_scaling = 'constant'"), t["decision_on_P"])
        self.assertGreaterEqual(t["min_cold_batches"], 25)

    def test_eq3_shaped_penalty_keeps_eq3(self):
        t = self._trend(synthetic(lambda m: 1.0 * (0.7 + 0.3 * 1024 / m)))
        self.assertAlmostEqual(t["P_slope"], self.S_EQ, places=2)
        self.assertTrue(t["decision_on_P"].startswith("keep Eq. (3)"), t["decision_on_P"])

    def test_growing_penalty_gives_inverted(self):
        t = self._trend(synthetic(lambda m: 1.0 * (m / 1024) ** 0.3))
        self.assertTrue(t["decision_on_P"].startswith("init_scaling = 'inverted'"), t["decision_on_P"])

    def test_too_few_batches_gives_no_decision(self):
        t = self._trend(synthetic(lambda m: 1.0, batches=5))
        self.assertTrue(t["decision_on_P"].startswith("no decision"), t["decision_on_P"])

    def test_init_sample_target_flag(self):
        t = self._trend(synthetic(lambda m: 1.0))
        self.assertEqual(t["min_cold_with_init"], 200)                 # 25 batches x 8
        self.assertTrue(t["meets_init_sample_target"])


def small_design(**kw):
    return build_design(sizes=(512, 1024, 3008), stages=("ingest",), init_variants=("init_module",),
                        cold_main=16, warm_main=16, cold_init=16, warm_init=8, blocks=2, **kw)


class TestRunnerWithFake(unittest.TestCase):
    def test_cap_holds_under_real_overlap(self):
        d = small_design()
        fake, envs = fake_for(d, Truth(), time_scale=0.02, seed=3)
        with tempfile.TemporaryDirectory() as t:
            s = Runner(fake, envs, os.path.join(t, "r.jsonl"), cap=8, poll_s=0).run(d)
        self.assertEqual(s["max_in_flight"], 8)              # batches of 8 really overlap ...
        self.assertLessEqual(fake.max_in_flight, CAP_MAX)    # ... and never exceed the cap
        self.assertEqual(fake.throttles, 0)

    def test_smaller_cap_is_respected(self):
        d = small_design(batch=4)
        fake, envs = fake_for(d, Truth(), time_scale=0.02, seed=4)
        with tempfile.TemporaryDirectory() as t:
            s = Runner(fake, envs, os.path.join(t, "r.jsonl"), cap=4, poll_s=0).run(d)
        self.assertLessEqual(s["max_in_flight"], 4)
        self.assertLessEqual(fake.max_in_flight, 4)

    def test_runner_rejects_design_above_its_cap(self):
        d = small_design()
        fake, envs = fake_for(d, Truth())
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                Runner(fake, envs, os.path.join(t, "r.jsonl"), cap=4).run(d)
            with self.assertRaises(ValueError):
                Runner(fake, envs, os.path.join(t, "r.jsonl"), cap=9)

    def test_throttles_are_recorded_not_retried(self):
        d = small_design()
        fake, envs = fake_for(d, Truth(), time_scale=0.02, seed=5, account_limit=3)
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.jsonl")
            Runner(fake, envs, p, cap=8, poll_s=0).run(d)
            recs = A.load_jsonl(p)
        self.assertGreater(fake.throttles, 0)
        inv = [r for r in recs if r.get("type") == "invocation"]
        self.assertEqual(len(inv), fake.calls)                         # one record per call, no retries
        res = A.analyse(recs, n_boot=10)
        self.assertEqual(sum(m["throttled"] for m in res["missing"]), fake.throttles)

    def test_request_id_join_and_cloudwatch_fallback(self):
        d = small_design()
        fake, envs = fake_for(d, Truth(), time_scale=0.0, seed=6, p_drop_tail_report=0.3)
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.jsonl")
            Runner(fake, envs, p, cap=8, poll_s=0).run(d)
            recs = A.load_jsonl(p)
        inv = [r for r in recs if r.get("type") == "invocation"]
        missing = [r for r in inv if not r["report"]]
        self.assertGreater(len(missing), 0)
        cw = fallback_reports(fake.logs, recs)
        self.assertEqual(set(cw), {r["request_id"] for r in missing})
        for r in inv:
            if r["report"]:
                self.assertEqual(r["report"]["request_id"], r["request_id"])
                self.assertEqual(r["payload"]["aws_request_id"], r["request_id"])
        res = A.analyse(recs, cw, n_boot=10)
        self.assertEqual(sum(m["no_report"] for m in res["missing"]), 0)
        self.assertEqual(sum(m["report_from_cloudwatch"] for m in res["missing"]), len(missing))

    def test_resume_reruns_only_the_incomplete_visit(self):
        d = small_design()
        fake, envs = fake_for(d, Truth(), seed=8)
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.jsonl")
            Runner(fake, envs, p, cap=8, poll_s=0).run(d)
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()
            last_done = max(i for i, l in enumerate(lines) if '"visit_done"' in l)
            vid = json.loads(lines[last_done])["visit_id"]
            with open(p, "w", encoding="utf-8") as f:               # simulate an interruption before visit_done
                f.write("\n".join(lines[:last_done]) + "\n")
            s = Runner(fake, envs, p, cap=8, poll_s=0).run(d)
            recs = A.load_jsonl(p)
        self.assertEqual(s["visits_run"], 1)
        rows, issues = A.join(recs)
        self.assertEqual({r["attempt"] for r in rows if r["visit_id"] == vid}, {1})
        self.assertGreater(issues["incomplete_visit_invocations_dropped"], 0)
        planned = sum(v.cold + sum(v.warm_batches) for v in d.visits)
        self.assertEqual(len(rows), planned)


class TestDryRun(unittest.TestCase):
    def test_timed_dry_run_recovers_truth_without_network_or_boto3(self):
        with tempfile.TemporaryDirectory() as t:
            c = run_dry(t, mode="timed", time_scale=0.01, n_boot=50)
        self.assertNotIn("boto3", sys.modules)
        self.assertEqual(c["invocations_recorded"], c["invocations_planned"])
        self.assertLessEqual(c["fake_max_in_flight"], CAP_MAX)
        self.assertEqual(c["no_report_after_fallback"], 0)
        self.assertEqual(c["unexpected_warm_in_cold_batch"], 0)
        for row in c["truth_comparison"]:
            # REPORT fields carry 0.01 ms (1e-5 s) precision, as Lambda's do: recovered to that resolution
            self.assertAlmostEqual(row["I_measured"], row["I_expected"], delta=1e-5, msg=row["cell"])
            self.assertAlmostEqual(row["X_measured"], row["X_expected"], delta=1e-5, msg=row["cell"])
            self.assertLess(abs(row["P_measured"] - row["P_expected"]), 0.003, row["cell"])        # thread jitter


class TestHandler(unittest.TestCase):
    def _load(self, **env):
        for k in ("PRISM_INIT_UNITS", "PRISM_FIRST_CALL_UNITS", "PRISM_WORK_UNITS", "PRISM_STAGE"):
            os.environ.pop(k, None)
        os.environ.update(env)
        sys.path.insert(0, os.path.join(ROOT, "handlers"))
        try:
            import stage_proxy
            return importlib.reload(stage_proxy)
        finally:
            sys.path.pop(0)

    def test_first_call_then_warm_and_label(self):
        h = self._load(PRISM_STAGE="ingest", PRISM_WORK_UNITS="2000", PRISM_FIRST_CALL_UNITS="3000")
        ctx = type("C", (), {"aws_request_id": "rid-1"})()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            a, b = h.handler({}, ctx), h.handler({"work_units": 10}, ctx)
        self.assertEqual(out.getvalue(), "")                    # prints nothing: the log tail stays REPORT-only
        self.assertTrue(a["first_call"])
        self.assertFalse(b["first_call"])
        self.assertEqual(a["env_id"], b["env_id"])
        self.assertIn("PROXY WORKLOAD", a["label"])
        self.assertEqual((a["work_units"], b["work_units"], a["aws_request_id"]), (2000, 10, "rid-1"))
        self.assertGreater(a["first_call_work_s"], 0)
        self.assertEqual(b["first_call_work_s"] < a["first_call_work_s"], True)

    def test_module_scope_init_work(self):
        h = self._load(PRISM_INIT_UNITS="20000")
        self.assertGreater(h.MODULE_INIT_S, 0)


class TestAwsGuard(unittest.TestCase):
    def test_plan_only_by_default_and_refuses_without_authorisation(self):
        d = small_design()
        os.environ.pop(aws.AUTH_ENV, None)
        with tempfile.TemporaryDirectory() as t:
            plan = aws.deploy(d, "us-east-1", os.path.join(t, "m.json"), execute=False)
            self.assertTrue(any("create_function" in p for p in plan))
            self.assertFalse(os.path.exists(os.path.join(t, "m.json")))
            self.assertTrue(any("get_account_settings" in p for p in aws.preflight("us-east-1", execute=False)))
            for fn in (lambda: aws.preflight("us-east-1", execute=True),
                       lambda: aws.deploy(d, "us-east-1", os.path.join(t, "m.json"), execute=True),
                       lambda: aws.teardown(None, "us-east-1", execute=True),
                       lambda: aws.calibrate(d, os.path.join(t, "m.json"), execute=True)):
                with self.assertRaises(PermissionError):
                    fn()
        self.assertNotIn("boto3", sys.modules)

    def test_package_contains_only_the_handler(self):
        import zipfile
        z = zipfile.ZipFile(io.BytesIO(aws.package()))
        self.assertEqual(z.namelist(), ["stage_proxy.py"])


class TestEstimate(unittest.TestCase):
    def test_estimate_is_consistent_with_the_design(self):
        d = build_design()
        e = estimate(d)
        self.assertEqual(e["invocations"], 23168)
        self.assertEqual(e["visits"], 696)
        for m in e["models"].values():
            self.assertGreaterEqual(m["cost_usd_if_init_billed"], m["cost_usd"])
            self.assertGreater(m["active_hours"], 0)
        self.assertEqual(e["planning_cost_usd_upper"], max(m["cost_usd_if_init_billed"] for m in e["models"].values()))
        self.assertIn("NOT current", e["assumptions"]["price_source"])


if __name__ == "__main__":
    unittest.main()
