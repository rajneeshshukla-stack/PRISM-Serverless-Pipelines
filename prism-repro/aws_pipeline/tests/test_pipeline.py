"""Local validation of the pipeline deployment kit. NO AWS CALLS: fakes only, socket creation is blocked for the whole
module (after the scientific stack is imported), and boto3 must never be imported.

Run from prism-repro/aws_pipeline:  ../venv/Scripts/python -m unittest discover -s tests -v
"""
import json
import math
import os
import socket
import statistics
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import prism_pipeline  # noqa: E402,F401  (path setup)
import prism_repro.closed_loop  # noqa: E402,F401  (imports ssl before sockets are blocked)
from prism_pipeline import asl, aws  # noqa: E402
from prism_pipeline.adapter import ControllerAdapter, LambdaActuator, LiveTelemetry, PolicyOnly  # noqa: E402
from prism_pipeline.analyse import analyse, join_reports, paired  # noqa: E402
from prism_pipeline.campaign import calibrate, force_cold  # noqa: E402
from prism_pipeline.driver import ChainExecutor, Driver, SfnExecutor  # noqa: E402
from prism_pipeline.estimate import estimate  # noqa: E402
from prism_pipeline.fake import FakeClientError, FakeLambda, fake_cloud  # noqa: E402
from prism_pipeline.workload import Record, envelope, poisson_stream, thinned_counts, trace_stream  # noqa: E402

HANDLER = os.path.join(ROOT, "handlers", "docpipe.py")
_REAL_SOCKET = socket.socket


def setUpModule():
    class Blocked(_REAL_SOCKET):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in a pipeline test")
    socket.socket = Blocked


def tearDownModule():
    socket.socket = _REAL_SOCKET


def deployed(**kw):
    """Fake cloud with the pipeline deployed by aws.deploy (the real deploy code path)."""
    cl = fake_cloud(**kw)
    d = tempfile.mkdtemp()
    man = os.path.join(d, "manifest.json")
    aws.deploy(man, cl=cl, sleep=lambda s: None)
    return cl, man, d


def fast_env(cl, k=1):
    from prism_pipeline.campaign import set_environment
    set_environment(cl["lambda"], aws.functions(), {"PRISM_K": k, "PRISM_CALIBRATION": "0"}, sleep=lambda s: None,
                    poll_s=0)


def small(n=6, rate=600.0, seed=3, words=150):
    return poisson_stream(n, rate, seed, mean_words=words)


# ----------------------------------------------------------------------------------------------- handlers
class TestHandler(unittest.TestCase):
    def setUp(self):
        self.cl, self.man, _ = deployed()
        fast_env(self.cl, 2)
        self.ex = ChainExecutor(self.cl["lambda"], aws.functions())

    def run_one(self, seed=42, words=400, pid="p-1"):
        return self.ex.run(envelope(Record("r1", seed, words, 0.0), "t", pid))

    def test_four_stages_real_work_and_trace(self):
        r = self.run_one()
        self.assertEqual(r["status"], "SUCCEEDED")
        out = r["output"]
        self.assertEqual([t["stage"] for t in out["trace"]], list(asl.STAGES))
        self.assertGreater(sum(out["transform"]["pii"].values()), 0)        # PII found and redacted
        self.assertIn(out["aggregate"]["label"], range(8))
        self.assertNotIn("doc", out)                                         # the document is not returned
        self.assertGreater(out["load"]["index_bytes"], 0)
        for t in out["trace"]:
            self.assertTrue(t["aws_request_id"] and t["env_id"])
            self.assertLessEqual(t["start_wall_ns"], t["end_wall_ns"])
            self.assertEqual(t["memory_mb"], 1024)
        ids = [c["request_id"] for c in r["stages_client"]]
        self.assertEqual(ids, [t["aws_request_id"] for t in out["trace"]])  # header ID == context ID
        self.assertTrue(all(c["report"] for c in r["stages_client"]))

    def test_deterministic_across_environments(self):
        a = self.run_one(pid="p-a")["output"]
        force_cold(self.cl["lambda"], aws.functions(), sleep=lambda s: None, poll_s=0)
        b = self.run_one(pid="p-b")["output"]
        self.assertNotEqual(a["trace"][0]["env_id"], b["trace"][0]["env_id"])
        for k in ("ingest", "transform", "aggregate"):
            self.assertEqual(json.dumps(a[k], sort_keys=True), json.dumps(b[k], sort_keys=True))

    def test_cold_then_warm(self):
        a = self.run_one(pid="p-1")["output"]["trace"]
        b = self.run_one(pid="p-2")["output"]["trace"]
        self.assertTrue(all(t["cold"] for t in a))
        self.assertFalse(any(t["cold"] for t in b))
        self.assertEqual([t["env_id"] for t in a], [t["env_id"] for t in b])

    def test_k_override_only_in_calibration_mode(self):
        env = envelope(Record("r", 1, 200, 0.0), "t", "p", k_override=7)
        out = self.ex.run(env)["output"]
        self.assertEqual(out["trace"][0]["k"], 2)                           # PRISM_CALIBRATION=0: ignored

    def test_missing_ids_fail_loudly(self):
        r = self.ex.run({"doc_seed": 1, "n_words": 10})
        self.assertEqual(r["status"], "FAILED")
        self.assertIn("Unhandled", r["error"])

    def test_work_grows_with_k_and_length(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("docpipe_t", HANDLER)
        m = importlib.util.module_from_spec(spec)
        m.print = lambda *a, **k: None
        spec.loader.exec_module(m)

        def t(stage, k, words):
            env = {"pipeline_request_id": "p", "record_id": "r", "doc_seed": 5, "n_words": words}
            for s in asl.STAGES:
                t0 = time.perf_counter()
                env = getattr(m, f"stage_{s}")(env, k)
                if s == stage:
                    return time.perf_counter() - t0
        for s in ("ingest", "transform", "aggregate", "load"):
            self.assertGreater(min(t(s, 60, 1500) for _ in range(3)), min(t(s, 1, 1500) for _ in range(3)), s)
            self.assertGreater(min(t(s, 30, 3000) for _ in range(3)), min(t(s, 30, 300) for _ in range(3)), s)


# ----------------------------------------------------------------------------------------------- workload, asl, estimate
class TestWorkload(unittest.TestCase):
    def test_same_seed_same_records(self):
        self.assertEqual(poisson_stream(30, 12, 9), poisson_stream(30, 12, 9))
        self.assertNotEqual(poisson_stream(30, 12, 9), poisson_stream(30, 12, 10))

    def test_size_mean_and_spread(self):
        r = poisson_stream(20000, 60, 1, mean_words=3000)
        w = [x.n_words for x in r]
        self.assertAlmostEqual(statistics.mean(w) / 3000, 1.0, delta=0.02)
        self.assertAlmostEqual(statistics.pstdev([math.log(x) for x in w]), 0.30, delta=0.01)
        gaps = np.diff([0.0] + [x.offset_s for x in r])
        self.assertAlmostEqual(gaps.mean(), 1.0, delta=0.03)

    def test_thinning_and_trace_stream(self):
        c = thinned_counts([600] * 50, 1 / 60, 2)
        self.assertAlmostEqual(sum(c) / 50, 10, delta=1.5)
        s = trace_stream(c, 60.0, 2)
        self.assertEqual(len(s), sum(c))
        self.assertTrue(all(int(x.offset_s // 60) < 50 for x in s))


class TestASL(unittest.TestCase):
    def test_linear_chain_without_retry(self):
        arns = {s: f"arn:aws:lambda:us-east-2:1:function:prism-pipe-{s}" for s in asl.STAGES}
        d = asl.definition(arns)
        asl.validate(d)
        self.assertEqual(d["StartAt"], "ingest")
        self.assertTrue(d["States"]["load"]["End"])
        self.assertFalse(any("Retry" in v for v in d["States"].values()))
        with self.assertRaises(ValueError):
            asl.definition({"ingest": arns["ingest"]})


class TestEstimate(unittest.TestCase):
    def test_bounds(self):
        e = estimate(40, [1024, 512, 2048, 1024, 1024])
        lin = e["models"]["cpu_linear"]
        self.assertGreater(e["planning_total_usd_upper"], 0)
        self.assertLess(e["planning_total_usd_upper"], 1.0)
        self.assertAlmostEqual(lin["e2e_s_by_memory"][512] - 0.55, 2 * (lin["e2e_s_by_memory"][1024] - 0.55),
                               delta=0.01)
        self.assertIn("UNVERIFIED", e["assumptions"]["prices_status"])


# ----------------------------------------------------------------------------------------------- driver
class _StubExec:
    mode = "stub"

    def __init__(self, dur, fail=()):
        self.dur, self.fail, self.calls = dur, set(fail), 0
        self.lock = threading.Lock()

    def run(self, env):
        with self.lock:
            self.calls += 1
        time.sleep(self.dur(env))
        if env["record_id"] in self.fail:
            return {"status": "FAILED", "error": "stub"}
        return {"status": "SUCCEEDED", "output": {"trace": []}}


class TestDriver(unittest.TestCase):
    def test_deadline_outcomes_failures_and_no_retry(self):
        recs = [Record(f"r{i}", i, 100, 0.01 * i) for i in range(6)]
        ex = _StubExec(lambda e: 0.25 if e["record_id"] in ("r1", "r3") else 0.01, fail=("r5",))
        with tempfile.TemporaryDirectory() as d:
            drv = Driver(ex, os.path.join(d, "r.jsonl"), "a", cap=8, deadline_s=0.15)
            s = drv.run(recs)
            with open(os.path.join(d, "r.jsonl"), encoding="utf-8") as f:
                lines = [json.loads(l) for l in f]
        out = {r["record_id"]: r["outcome"] for r in lines if r["type"] == "record"}
        self.assertEqual(out, {"r0": "met", "r1": "missed", "r2": "met", "r3": "missed", "r4": "met", "r5": "failed"})
        self.assertEqual((s["met"], s["missed"], s["failed"]), (3, 2, 1))
        self.assertEqual(ex.calls, 6)                                         # nothing retried
        self.assertEqual(lines[0]["type"], "arm_meta")
        self.assertEqual(lines[-1]["type"], "arm_summary")

    def test_cap_sheds_and_bounds_in_flight(self):
        recs = [Record(f"r{i}", i, 100, 0.0) for i in range(5)]
        ex = _StubExec(lambda e: 0.2)
        with tempfile.TemporaryDirectory() as d:
            s = Driver(ex, os.path.join(d, "r.jsonl"), "a", cap=3).run(recs)
        self.assertEqual((s["shed_client_cap"], s["max_in_flight"], ex.calls), (2, 3, 3))
        with self.assertRaises(ValueError):
            Driver(ex, "x", "a", cap=9)                                       # quota 10 minus headroom 2

    def test_sfn_executor_failure_is_recorded(self):
        cl, man, d = deployed()
        fast_env(cl)
        sm = aws.load_manifest(man)["state_machine"]
        r = SfnExecutor(cl["stepfunctions"], sm).run({"pipeline_request_id": "p", "doc_seed": 1})  # no record_id
        self.assertEqual(r["status"], "FAILED")
        ok = SfnExecutor(cl["stepfunctions"], sm).run(envelope(Record("r", 1, 100, 0.0), "a", "p2"))
        self.assertEqual(ok["status"], "SUCCEEDED")
        self.assertEqual(len(ok["output"]["trace"]), 4)
        self.assertTrue(ok["billing"]["billedDurationInMilliseconds"] >= 100)


# ----------------------------------------------------------------------------------------------- adapter
def _rec(rid, starts, t0, cold=False):
    return {"type": "record", "record_id": rid, "stages": [
        {"stage": s, "start_wall_ns": t0 + int(a * 1e9), "end_wall_ns": t0 + int(b * 1e9), "cold": cold}
        for s, (a, b) in zip(asl.STAGES, starts)]}


class TestTelemetry(unittest.TestCase):
    def test_no_lookahead_and_counts(self):
        t0 = 10**18
        tel = LiveTelemetry(10, 1.0, t0, count_scale=2.0)
        tel.add(_rec("a", [(0.1, 0.5), (0.6, 1.4), (1.5, 1.6), (2.2, 2.3)], t0, cold=True))
        tel.add(_rec("b", [(3.5, 3.6), (3.7, 3.8), (3.9, 4.2), (4.3, 4.4)], t0))
        v = tel.view(2)
        self.assertEqual(v.filled, 3)
        self.assertTrue(np.all(np.isnan(v.N[3:])) and np.all(np.isnan(v.K[3:])))
        self.assertEqual(v.N[:3].tolist(), [2.0, 0.0, 0.0])                   # one ingest arrival x scale 2
        self.assertEqual(v.cold[0].tolist(), [2.0, 2.0, 0.0, 0.0])
        self.assertEqual(v.K[1].tolist(), [0.0, 2.0, 2.0, 0.0])               # transform carried into bin 1
        self.assertTrue(np.all(np.isnan(tel.view(-2).N)))
        full = tel.view(9)
        self.assertEqual(np.nansum(full.arrivals) / 2, 8)
        self.assertTrue(np.allclose(full.inflight_end[-1], 0))


class _Watch:
    """Wraps a controller and records what telemetry it was shown."""

    def __init__(self, inner, E=5, L=2):
        self.inner, self.E, self.L, self.seen = inner, E, L, []

    def start(self, *a):
        if hasattr(self.inner, "start"):
            self.inner.start(*a)

    def decide(self, k, tel):
        v = k * self.E - self.L
        self.seen.append((k, v, int(tel.filled), bool(np.all(np.isnan(tel.N[max(v + 1, 0):])))))
        return self.inner.decide(k, tel)


class TestAdapter(unittest.TestCase):
    def setUp(self):
        from prism_repro.config import PipelineConfig
        self.cfg = PipelineConfig()
        self.cl, self.man, self.dir = deployed()
        fast_env(self.cl)

    def test_schedule_actuates_memory_on_epoch_boundaries(self):
        from prism_repro.closed_loop import ScheduleController
        lam = self.cl["lambda"]
        sched = [1024, 2048, 2048, 512]
        ctl = _Watch(ScheduleController(np.zeros((4, 4)), np.array(sched)))
        act = LambdaActuator(lam, aws.functions(), poll_s=0.0)
        tel = LiveTelemetry(20, 0.05, time.time_ns())
        ad = ControllerAdapter(ctl, act, tel, self.cfg, 4, os.path.join(self.dir, "d.jsonl"))
        ad.start()
        before = lam.updates
        ad.initial()
        t0 = time.perf_counter_ns()
        ad.run(t0)
        mem = [d["memory"] for d in ad.decisions]
        self.assertEqual(mem, sched)
        self.assertEqual(lam.updates - before, 4 * 2)                       # two changes x four functions
        self.assertEqual({lam.get_function_configuration(FunctionName=f)["MemorySize"]
                          for f in aws.functions().values()}, {512})
        self.assertEqual([d["effective_bin"] for d in ad.decisions], [0, 5, 10, 15])
        for k, v, filled, nan_after in ctl.seen:
            self.assertEqual(filled, max(v + 1, 0))
            self.assertTrue(nan_after)
        self.assertEqual(tel.mem.tolist(), [1024] * 5 + [2048] * 10 + [512] * 5)

    def test_provisioned_concurrency_refused_at_quota_10(self):
        act = LambdaActuator(self.cl["lambda"], aws.functions(), pc_mode="apply",
                             account_settings=self.cl["lambda"].get_account_settings()["AccountLimit"])
        with self.assertRaises(PermissionError):
            act.apply([3, 0, 0, 0], 1024)
        rec = LambdaActuator(self.cl["lambda"], aws.functions()).apply([3, 5, 1, 0], 1024)
        self.assertEqual((rec["pc_requested"], rec["pc_applied"], rec["memory_changed"]), ([3, 5, 1, 0], None, False))
        self.assertEqual(self.cl["lambda"].pc_calls, 0)

    def test_ondemand_baseline_policy(self):
        from prism_repro.policies import OnDemand
        ctl = PolicyOnly(OnDemand())
        ctl.start(self.cfg, 10, 2)
        P, m = ctl.decide(0, LiveTelemetry(10, 1, 0).view(-2))
        self.assertEqual((list(P), m), ([0, 0, 0, 0], 1024))

    def test_prism_controller_through_adapter(self):
        """PRISM itself (policies.PRISM via closed_loop.PolicyController, seasonal-naive forecaster) decides from
        telemetry built out of finished records of a thinned replay of the paper's trace."""
        from prism_repro.closed_loop import PolicyController
        from prism_repro.experiment import WEEK_START, TraceBundle, make_policy
        b = TraceBundle(101, self.cfg, scenarios=("stationary",), forecasters=("seasonal_naive",))
        pol = make_policy(dict(family="PRISM", param=0.02, fc="seasonal_naive"))
        ctl = _Watch(PolicyController(pol, b, "stationary"))
        thin = 1 / 60
        counts = b.traces["stationary"]["counts"][WEEK_START["test"]:WEEK_START["test"] + 20]
        tc = thinned_counts(counts, thin, 5)
        bin_s = 0.02
        tel = LiveTelemetry(20, bin_s, 10**18, count_scale=1 / thin)
        ad = ControllerAdapter(ctl, LambdaActuator(self.cl["lambda"], aws.functions(), poll_s=0.0), tel, self.cfg,
                               4, os.path.join(self.dir, "p.jsonl"), pc_scale=thin)
        ad.start()
        ad.initial()
        for i, r in enumerate(trace_stream(tc, bin_s, 5)):
            a = r.offset_s
            tel.add(_rec(r.record_id, [(a, a + 0.001), (a + 0.002, a + 0.003), (a + 0.004, a + 0.005),
                                      (a + 0.006, a + 0.007)], 10**18))
        for k in (1, 2, 3):
            d = ad._decide(k)
            self.assertEqual(len(d["P_model"]), 4)
            self.assertTrue(all(np.isfinite(d["P_model"])) and min(d["P_model"]) >= 0)
            self.assertIn(d["memory"], self.cfg.mem_options)
            self.assertEqual(d["P_live"], [math.ceil(x * thin) for x in d["P_model"]])
            self.assertGreater(sum(d["P_model"]), 0)          # full-scale levels from rescaled counts
        for k, v, filled, nan_after in ctl.seen:
            self.assertTrue(nan_after)
            self.assertEqual(filled, max(v + 1, 0))


# ----------------------------------------------------------------------------------------------- aws: guard, scope, cleanup
class TestAWSGuardAndCleanup(unittest.TestCase):
    def test_plan_only_without_execute(self):
        os.environ.pop(aws.AUTH_ENV, None)
        for p in (aws.preflight(), aws.deploy("x.json"), aws.teardown(None), aws.collect_reports("x.json", 0, 1)):
            self.assertTrue(p and all(isinstance(x, str) for x in p))
        self.assertNotIn("boto3", sys.modules)

    def test_execute_needs_authorisation_for_non_fake_clients(self):
        os.environ.pop(aws.AUTH_ENV, None)
        real_like = {"lambda": object(), "logs": object(), "iam": object(), "sts": object(), "stepfunctions": object()}
        with self.assertRaises(PermissionError):
            aws.deploy("x.json", execute=True, cl=real_like)
        with self.assertRaises(PermissionError):
            aws.teardown(None, execute=True, cl=real_like)
        mixed = dict(fake_cloud(), sts=object())
        self.assertFalse(aws.allowed(False, mixed))

    def test_deploy_resources_and_teardown_is_scoped(self):
        cl, man, _ = deployed()
        m = aws.load_manifest(man)
        self.assertEqual(sorted(m["functions"]), sorted(aws.functions().values()))
        self.assertEqual(cl["stepfunctions"].machines[m["state_machine"]]["logging"], {"level": "OFF"})
        inl = cl["iam"].roles[aws.SFN_ROLE]["inline"][f"{aws.SFN_ROLE}-invoke"]
        self.assertEqual(sorted(inl["Statement"][0]["Resource"]), sorted(f["arn"] for f in m["functions"].values()))
        self.assertTrue(all(cl["logs"].groups[g]["retention"] == 7 for g in m["log_groups"]))
        lam = cl["lambda"]
        z = {"ZipFile": b"x"}
        lam.create_function("prism-meas-ingest-1024", "python3.12", "r", "h.h", z, 60, 1024, ["x86_64"],
                            {"Variables": {}}, Tags={"project": "prism-measurement"})
        lam.create_function("prism-pipe-someone-else", "python3.12", "r", "h.h", z, 60, 1024, ["x86_64"],
                            {"Variables": {}}, Tags={})
        lam.create_function("unrelated", "python3.12", "r", "h.h", z, 60, 1024, ["x86_64"], {"Variables": {}})
        # deletion scope, with log groups deleted explicitly (by default they are kept until REPORT coverage is
        # complete: tests/test_report_collection.py)
        plan = aws.teardown(man, cl=cl, delete_log_groups="always")
        self.assertEqual(sorted(lam.fns), ["prism-meas-ingest-1024", "prism-pipe-someone-else", "unrelated"])
        self.assertEqual(cl["stepfunctions"].machines, {})
        self.assertEqual(cl["iam"].roles, {})
        self.assertFalse([g for g in cl["logs"].groups if g.startswith("/aws/lambda/prism-pipe-")
                          and g != "/aws/lambda/prism-pipe-someone-else"])
        self.assertTrue(any(x.startswith("NOT CLEAN") for x in plan))       # the untagged one is reported, kept

    def test_teardown_after_partial_deploy(self):
        cl = fake_cloud()
        d = tempfile.mkdtemp()
        man = os.path.join(d, "m.json")
        orig = cl["stepfunctions"].create_state_machine

        def boom(**kw):
            raise FakeClientError("ValidationException", "injected")
        cl["stepfunctions"].create_state_machine = boom
        with self.assertRaises(FakeClientError):
            aws.deploy(man, cl=cl, sleep=lambda s: None)
        cl["stepfunctions"].create_state_machine = orig
        self.assertEqual(len(cl["lambda"].fns), 4)
        plan = aws.teardown(man, cl=cl)
        self.assertEqual((cl["lambda"].fns, cl["iam"].roles), ({}, {}))
        self.assertFalse(any(x.startswith("NOT CLEAN") for x in plan))

    def test_preflight_stops_on_leftovers_and_low_quota(self):
        cl, man, _ = deployed()
        self.assertTrue(any(x.startswith("STOP: run teardown") for x in aws.preflight(cl=cl)))
        cl2 = fake_cloud(account_limit=5)
        self.assertTrue(any("below the cap" in x for x in aws.preflight(cl=cl2)))


# ----------------------------------------------------------------------------------------------- join and analysis
class TestJoinAndAnalysis(unittest.TestCase):
    def test_cloudwatch_fallback_join_with_pagination(self):
        cl, man, d = deployed(p_drop_tail_report=1.0)                    # no REPORT in any log tail
        fast_env(cl)
        cl["logs"].page_size = 3
        recs = small(5)
        t0 = time.time_ns() // 1_000_000
        ex = ChainExecutor(cl["lambda"], aws.functions())
        os.makedirs(os.path.join(d, "arm"))
        Driver(ex, os.path.join(d, "arm", "records.jsonl"), "arm").run(recs)
        aws.collect_reports(man, t0 - 1000, time.time_ns() // 1_000_000 + 1000, cl=cl)
        res = analyse(d, ["arm"], 1.0, os.path.join(d, "cloudwatch_reports.jsonl"))
        integ = res["integrity"]["arm"]
        self.assertEqual(integ["report_from_tail"] if "report_from_tail" in integ else 0, 0)
        self.assertEqual(integ["report_from_cloudwatch"], 20)
        self.assertEqual(integ.get("report_missing", 0), 0)
        self.assertEqual(integ["duplicate_request_ids"], 0)
        a = res["arms"]["arm"]
        self.assertEqual(a["stages"]["ingest"]["cold"], a["stages"]["ingest"]["n"] - a["stages"]["ingest"]["warm"])
        self.assertGreater(a["lambda_billed_gb_s"], 0)

    def test_paired_same_records(self):
        A = [{"type": "record", "record_id": "x", "outcome": "met", "e2e_s": 1.0, "n_words": 5},
             {"type": "record", "record_id": "y", "outcome": "met", "e2e_s": 2.0, "n_words": 6}]
        B = [{"type": "record", "record_id": "x", "outcome": "missed", "e2e_s": 3.0, "n_words": 5},
             {"type": "record", "record_id": "y", "outcome": "met", "e2e_s": 2.5, "n_words": 6}]
        p = paired(A, B)
        self.assertEqual(p["outcomes_a_b"], {"met|met": 1, "met|missed": 1})
        self.assertAlmostEqual(p["e2e_diff_s"]["p50"], 1.25)
        self.assertTrue(p["same_documents"])

    def test_cold_without_init_duration_flagged(self):
        recs = [{"type": "record", "stages": [{"stage": "ingest", "aws_request_id": "1", "cold": True,
                                               "report": {"request_id": "1", "init_duration_ms": None}}]}]
        self.assertEqual(join_reports(recs, [])["cold_without_init_duration"], 1)


class TestCalibration(unittest.TestCase):
    def test_hits_targets_on_fake(self):
        cl, man, _ = deployed()
        tg = {"ingest": 0.004, "transform": 0.02, "aggregate": 0.0125, "load": 0.006}
        cal = calibrate(cl["lambda"], aws.functions(), targets=tg, n_words=300, k_hi0=4)
        for s, c in cal.items():
            self.assertGreaterEqual(c["k"], 1)
            self.assertAlmostEqual(c["achieved_median_s"] / tg[s], 1.0, delta=0.6, msg=s)   # host timing noise


class TestSelfTest(unittest.TestCase):
    def test_whole_live_test_sequence_on_fakes(self):
        """livetest.run end to end (preflight, deploy, calibrate, smoke, both arms, collect, analyse, teardown)."""
        from prism_pipeline.selftest import run_selftest
        with tempfile.TemporaryDirectory() as d:
            r = run_selftest(d)
        self.assertTrue(r["ok"], [k for k, v in r["checks"].items() if not v])


if __name__ == "__main__":
    unittest.main()
