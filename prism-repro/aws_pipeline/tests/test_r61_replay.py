"""R6.1 trace-replay arm and provisioned-concurrency actuation. NO AWS CALLS: fakes only, sockets blocked for the whole
module, boto3 never imported. Run from prism-repro/aws_pipeline:  ../venv/Scripts/python -m unittest discover -s tests
"""
import json
import os
import socket
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np  # noqa: E402
import prism_pipeline  # noqa: E402,F401
import prism_repro.closed_loop  # noqa: E402,F401  (imports ssl before sockets are blocked)
from prism_pipeline import aws  # noqa: E402
from prism_pipeline.adapter import LambdaActuator, LiveTelemetry, pc_readiness, publish_alias  # noqa: E402
from prism_pipeline.campaign import set_environment  # noqa: E402
from prism_pipeline.driver import SfnExecutor  # noqa: E402
from prism_pipeline.fake import fake_cloud  # noqa: E402
from prism_pipeline.livetest import ARM_DIFFERENCES, TestSpec, plan, preview_decisions, replay_records, run  # noqa: E402
from prism_pipeline.selftest import scaled_spec  # noqa: E402
from prism_pipeline.workload import Record, envelope  # noqa: E402

_REAL = socket.socket
NOSLEEP = lambda s: None  # noqa: E731


def setUpModule():
    class Blocked(_REAL):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in an R6.1 test")
    socket.socket = Blocked


def tearDownModule():
    socket.socket = _REAL


def deployed(alias="live", **kw):
    cl = fake_cloud(**kw)
    d = tempfile.mkdtemp()
    man = os.path.join(d, "manifest.json")
    aws.deploy(man, cl=cl, sleep=NOSLEEP, alias=alias)
    set_environment(cl["lambda"], aws.functions(), {"PRISM_K": 1, "PRISM_CALIBRATION": "0"}, sleep=NOSLEEP, poll_s=0)
    if alias:
        publish_alias(cl["lambda"], aws.functions(), alias)
    return cl, man, d


def jl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f]


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def one_record(cl, man, rid="r-1"):
    m = aws.load_manifest(man)
    sfn = SfnExecutor(cl["stepfunctions"], m["state_machine"])
    return sfn.run(envelope(Record(rid, 5, 120, 0.0), "t", f"t-{rid}"))


class TestActuation(unittest.TestCase):
    def test_apply_needs_an_alias(self):
        cl, _, _ = deployed(alias=None, account_limit=400)
        with self.assertRaises(ValueError):
            LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply")

    def test_quota_refusal_is_recorded_and_nothing_is_sent(self):
        cl, _, _ = deployed(account_limit=10)
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0)
        a = act.apply([3, 0, 0, 0], 1024)
        self.assertEqual(a["pc_status"], "refused_quota")
        self.assertIn("all", a["pc_refused"])
        self.assertEqual((a["pc_applied"], a["memory_applied"], cl["lambda"].pc_calls), (None, 1024, 0))
        self.assertEqual(act.pc_cur, [0, 0, 0, 0])

    def test_api_refusal_is_recorded_per_stage(self):
        cl, _, _ = deployed(account_limit=103)              # the API allows 3 in total
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0,
                             account_settings={"UnreservedConcurrentExecutions": 1000})   # pre-check passes
        a = act.apply([2, 2, 0, 0], 1024)
        self.assertEqual(a["pc_status"], "partially_refused")
        self.assertEqual(a["pc_accepted"], [True, False, None, None])
        self.assertIn("InvalidParameterValueException", a["pc_refused"]["transform"])
        self.assertEqual(act.pc_cur, [2, 0, 0, 0])

    def test_request_is_not_readiness_and_readiness_is_observed(self):
        cl, man, _ = deployed(account_limit=400, pc_ready_polls=3)
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0)
        a = act.apply([1, 2, 0, 0], 1024)
        self.assertEqual(a["pc_status"], "requested_pending_readiness")
        self.assertEqual((a["pc_submitted"], a["pc_accepted"]), ([1, 2, None, None], [True, True, None, None]))
        self.assertIsNone(a["pc_applied"])
        self.assertEqual({r["status"] for r in a["pc_status_after"] if r["configured"]}, {"IN_PROGRESS"})
        before = one_record(cl, man, "before")            # not ready: served on demand
        self.assertEqual({s["init_type"] for s in before["output"]["trace"]}, {"on-demand"})
        rows = [act.poll_pc() for _ in range(3)][-1]
        self.assertEqual([r["status"] for r in rows], ["READY", "READY", "NONE", "NONE"])
        after = one_record(cl, man, "after")
        types = [s["init_type"] for s in after["output"]["trace"]]
        self.assertEqual(types[:2], ["provisioned-concurrency"] * 2)
        self.assertEqual(types[2:], ["on-demand"] * 2)
        self.assertEqual({s["function_version"] for s in after["output"]["trace"]}, {"2"})   # deploy's v1, then the calibrated v2: not $LATEST

    def test_changes_reach_the_api_and_zero_deletes(self):
        cl, _, _ = deployed(account_limit=400)
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0)
        act.apply([1, 2, 1, 1], 1024)
        a = act.apply([1, 1, 1, 0], 1024)
        self.assertEqual(a["pc_submitted"], [None, 1, None, 0])
        self.assertEqual(act.pc_cur, [1, 1, 1, 0])
        self.assertEqual([r["status"] for r in act.poll_pc()][3], "NONE")
        self.assertEqual(act.apply([1, 1, 1, 0], 1024)["pc_status"], "unchanged")

    def test_memory_change_republishes_the_alias_and_reapplies_pc(self):
        cl, _, _ = deployed(account_limit=400)
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0)
        act.apply([1, 0, 0, 0], 1024)
        a = act.apply([1, 0, 0, 0], 2048)
        self.assertTrue(a["memory_changed"])
        self.assertEqual(a["memory_applied"], 2048)
        self.assertEqual(a["pc_cleared_for_memory_change"]["prism-pipe-ingest"], "deleted")
        self.assertEqual(a["pc_submitted"], [1, None, None, None])
        for fn in aws.functions().values():
            self.assertEqual(cl["lambda"].get_function_configuration(FunctionName=fn, Qualifier="live")["MemorySize"],
                             2048)

    def test_cap_is_recorded(self):
        cl, _, _ = deployed(account_limit=400)
        act = LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0,
                             pc_cap_per_stage=2)
        a = act.apply([1, 5, 0, 0], 1024)
        self.assertEqual((a["pc_requested"], a["pc_clipped_from"]), ([1, 2, 0, 0], [1, 5, 0, 0]))

    def test_record_mode_never_calls_the_api(self):
        cl, _, _ = deployed(alias=None, account_limit=400)
        a = LambdaActuator(cl["lambda"], aws.functions()).apply([3, 5, 1, 0], 1024)
        self.assertEqual((a["pc_status"], a["pc_applied"], cl["lambda"].pc_calls), ("recorded_not_applied", None, 0))

    def test_teardown_deletes_pc_first_and_is_clean(self):
        cl, man, d = deployed(account_limit=400)
        LambdaActuator(cl["lambda"], aws.functions(), pc_mode="apply", alias="live", poll_s=0).apply([1, 1, 1, 1], 1024)
        plan_ = aws.teardown(man, cl=cl, delete_log_groups="always")
        self.assertTrue(any("delete_provisioned_concurrency_config" in x for x in plan_))
        self.assertEqual(aws.leftovers(cl), {"functions": [], "state_machines": [], "log_groups": [], "roles": []})

    def test_readiness_summary(self):
        dec = [{"k": 0, "applied_wall_ns": 100, "actuation": {"pc_submitted": [1, None], "pc_accepted": [True, None]}},
               {"k": 1, "applied_wall_ns": 500, "actuation": {"pc_submitted": [2, None], "pc_accepted": [True, None]}}]
        rows = [{"stage": "a", "wall_ns": 150, "status": "IN_PROGRESS", "requested": 1, "allocated": 0},
                {"stage": "a", "wall_ns": 300, "status": "READY", "requested": 1, "allocated": 1},
                {"stage": "a", "wall_ns": 600, "status": "IN_PROGRESS", "requested": 2, "allocated": 1}]
        r = pc_readiness(dec, rows, ["a", "b"])
        self.assertEqual([(x["k"], x["status"]) for x in r], [(0, "ready"), (1, "not ready by arm end")])
        self.assertAlmostEqual(r[0]["activation_lag_s"], 200 / 1e9)


class TestTelemetry(unittest.TestCase):
    def test_provisioned_environment_is_neither_on_demand_nor_cold(self):
        tel = LiveTelemetry(4, 1.0, 0)
        st = lambda init, cold: {"stage": "ingest", "start_wall_ns": int(0.5e9), "end_wall_ns": int(0.6e9),  # noqa
                                 "cold": cold, "init_type": init}
        tel.add({"type": "record", "stages": [st("provisioned-concurrency", True)]})
        tel.add({"type": "record", "stages": [st("on-demand", True)]})
        v = tel.view(0)
        self.assertEqual((v.arrivals[0, 0], v.n_od[0, 0], v.cold[0, 0]), (2.0, 1.0, 1.0))
        self.assertTrue(np.isnan(v.arrivals[1, 0]))          # no lookahead past the observed bin


class TestReplayPlan(unittest.TestCase):
    def test_replay_is_deterministic_and_plan_counts(self):
        sp = TestSpec(mode="prism_replay", pc_mode="apply")
        a, b = replay_records(sp), replay_records(sp)
        self.assertEqual([r.to_dict() for r in a], [r.to_dict() for r in b])
        p = plan(sp)
        self.assertTrue(any(f"expected: {2 * len(a) + sp.smoke} executions, {4 * (2 * len(a) + sp.smoke)}" in x for x in p))
        self.assertTrue(any("create_alias live" in x for x in p))
        self.assertIn(ARM_DIFFERENCES, p)

    def test_preview_shows_adaptive_pc_decisions(self):
        sp = TestSpec(mode="prism_replay", bin_s=60.0, n_epochs=8, forecaster="seasonal_naive", pc_mode="apply")
        pv = preview_decisions(sp)
        live = [tuple(d["P_live"]) for d in pv]
        self.assertTrue(all(sum(x) > 0 for x in live))        # PRISM provisions; the baseline never does
        self.assertGreater(len(set(live)), 1)                 # and changes P between epochs
        self.assertEqual({d["memory"] for d in pv}, {1024})   # memory does not change at 14.5 s


class TestReplayLiveTestOnFakes(unittest.TestCase):
    """The whole live sequence in mode prism_replay, pc_mode apply, on the fakes (scaled time)."""

    @classmethod
    def setUpClass(cls):
        sp = scaled_spec()
        sp.mode, sp.n_epochs, sp.thin, sp.bin_s, sp.forecaster = "prism_replay", 4, 1 / 600, 1.0, "seasonal_naive"
        sp.pc_mode, sp.pc_poll_s, sp.pc_initial_wait_s = "apply", 0.05, 5.0
        cls.spec, cls.dir = sp, tempfile.mkdtemp()
        cls.cl = fake_cloud(account_limit=400)
        cls.res = run(cls.dir, sp, cl=cls.cl)

    def rows(self, arm, name):
        return jl(os.path.join(self.dir, arm, name))

    def test_verified_and_clean(self):
        self.assertIsNone(self.res.get("error"))
        self.assertTrue(self.res["verified"])
        self.assertEqual(aws.leftovers(self.cl), {"functions": [], "state_machines": [], "log_groups": [], "roles": []})
        self.assertNotIn("boto3", sys.modules)

    def test_same_records_reach_both_arms(self):
        planned = jl(os.path.join(self.dir, "records_plan.jsonl"))
        key = lambda r: (r["record_id"], r["offset_s"], r["n_words"])  # noqa: E731
        for arm in ("baseline_ondemand", "adapter_prism"):
            got = [r for r in self.rows(arm, "records.jsonl") if r.get("type") == "record"]
            self.assertEqual(sorted(map(key, got)), sorted(map(key, planned)), arm)

    def test_decisions_reach_actuation_with_timing(self):
        dec = [d for d in self.rows("adapter_prism", "decisions.jsonl") if d["type"] == "decision"]
        self.assertEqual([d["k"] for d in dec], list(range(self.spec.n_epochs)))
        E, L = 5, 2
        for d in dec:
            self.assertEqual(d["observed_upto_bin"], d["k"] * E - L)
            self.assertLessEqual(d["decided_wall_ns"], d["applied_wall_ns"])
            self.assertIn("decision_s", d)
            a = d["actuation"]
            self.assertEqual(a["memory_applied"], a["memory_requested"])
            self.assertEqual(a["pc_requested"], [min(x, self.spec.pc_cap) for x in d["P_live"]])
        self.assertTrue(any(x for x in dec[0]["actuation"]["pc_submitted"]))   # epoch 0 provisions
        self.assertEqual(self.cl["lambda"].throttles, 0)

    def test_readiness_observed_and_pc_served(self):
        meta = jload(os.path.join(self.dir, "adapter_prism", "arm.json"))
        self.assertTrue(meta["pc_initial_wait"]["ready"])
        self.assertTrue(meta["pc_readiness"] and all(r["status"] == "ready" for r in meta["pc_readiness"]))
        types = [s.get("init_type") for r in self.rows("adapter_prism", "records.jsonl") if r.get("type") == "record"
                 for s in r["stages"]]
        self.assertIn("provisioned-concurrency", types)
        base = [s.get("init_type") for r in self.rows("baseline_ondemand", "records.jsonl") if r.get("type") == "record"
                for s in r["stages"]]
        self.assertNotIn("provisioned-concurrency", base)

    def test_records_carry_deadline_outcome_and_request_ids(self):
        for arm in ("baseline_ondemand", "adapter_prism"):
            for r in self.rows(arm, "records.jsonl"):
                if r.get("type") != "record":
                    continue
                self.assertEqual(r["deadline_s"], self.spec.deadline_s)
                self.assertIn(r["outcome"], ("met", "missed", "failed", "shed_client_cap", "timeout"))
                if r["status"] == "SUCCEEDED":
                    self.assertEqual(len({s["aws_request_id"] for s in r["stages"]}), 4)

    def test_code_fingerprint_is_recorded(self):
        lt = jload(os.path.join(self.dir, "livetest.json"))
        self.assertIn("prism_pipeline/livetest.py", lt["code"]["files_sha256"])
        self.assertIn("handlers/docpipe.py", lt["code"]["files_sha256"])
        self.assertTrue(("git_head" in lt["code"]) or ("git_error" in lt["code"]))

    def test_coverage_checks_the_prism_arm(self):
        cov = jload(os.path.join(self.dir, aws.COVERAGE_FILE))
        self.assertIn("adapter_prism", cov["arms"])
        self.assertTrue(cov["complete"])


class TestThrottlingRecorded(unittest.TestCase):
    def test_throttled_invocation_is_a_failed_record_with_its_error(self):
        from prism_pipeline.driver import Driver
        cl, man, d = deployed(alias=None, account_limit=1)     # a second concurrent execution is throttled
        m = aws.load_manifest(man)
        recs = [Record(f"th-{i}", i, 400, 0.0) for i in range(4)]
        out = Driver(SfnExecutor(cl["stepfunctions"], m["state_machine"]), os.path.join(d, "th.jsonl"), "th", cap=4,
                     deadline_s=60, sleep=NOSLEEP).run(recs)
        rows = [r for r in jl(os.path.join(d, "th.jsonl")) if r.get("type") == "record"]
        failed = [r for r in rows if r["outcome"] == "failed"]
        self.assertGreater(cl["lambda"].throttles, 0)
        self.assertEqual(out["failed"], len(failed))
        self.assertTrue(failed and all("TooManyRequestsException" in (r.get("error") or "") for r in failed))


class TestQuotaGate(unittest.TestCase):
    def test_apply_stops_before_deploy_when_quota_is_too_low(self):
        sp = scaled_spec()
        sp.mode, sp.pc_mode, sp.forecaster = "prism_replay", "apply", "seasonal_naive"
        cl = fake_cloud(account_limit=10)
        r = run(tempfile.mkdtemp(), sp, cl=cl)
        self.assertTrue(r["stopped"][0].startswith("STOP: unreserved concurrency 10"))
        self.assertEqual(r["pc_quota"]["Unreserved"], 10)
        self.assertEqual((cl["lambda"].fns, cl["lambda"].pc_calls), ({}, 0))      # nothing created or requested


class TestCoverageAllArms(unittest.TestCase):
    def test_missing_prism_arm_report_blocks_verification_and_keeps_logs(self):
        cl, man, d = deployed(alias=None, account_limit=400)
        os.makedirs(os.path.join(d, "adapter_prism"))
        with open(os.path.join(d, "adapter_prism", "records.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "record", "record_id": "x", "stages": [{"stage": "ingest",
                                                                               "aws_request_id": "rid-x"}]}) + "\n")
        aws._atomic_json({"status": "complete"}, os.path.join(d, aws.COLLECT_STATE_FILE))
        cov = aws.report_coverage(d)
        self.assertEqual((cov["arms"], cov["missing"], cov["complete"]), (["adapter_prism"], 1, False))
        p = aws.teardown(man, cl=cl)
        self.assertTrue(any(x.startswith("RETAINED") for x in p))


if __name__ == "__main__":
    unittest.main()
