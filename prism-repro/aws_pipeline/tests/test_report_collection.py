"""REPORT collection and cleanup (fix of 22 Nov 2026 for run livetest_20261121-203051). NO AWS CALLS: in-process fakes
only, sockets blocked for the whole module, boto3 never imported.
Run from prism-repro/aws_pipeline:  python -m unittest tests.test_report_collection -v
"""
import json
import os
import socket
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import prism_pipeline  # noqa: E402,F401  (path setup)
import prism_repro.closed_loop  # noqa: E402,F401  (imports ssl before sockets are blocked)
from prism_pipeline import aws  # noqa: E402
from prism_pipeline.driver import ChainExecutor, Driver  # noqa: E402
from prism_pipeline.fake import FakeClientError, fake_cloud  # noqa: E402
from prism_pipeline.workload import poisson_stream  # noqa: E402

_REAL_SOCKET = socket.socket


def setUpModule():
    class Blocked(_REAL_SOCKET):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in a collection test")
    socket.socket = Blocked


def tearDownModule():
    socket.socket = _REAL_SOCKET


class EndpointConnectionError(Exception):
    """Same class name as botocore's, raised by the fake on a credential-refresh failure."""


def run_with_reports(n=4, page_size=3):
    """Deploy on the fakes, drive n records through the four stages (one arm), return (cl, manifest, run dir, window)."""
    cl = fake_cloud()
    d = tempfile.mkdtemp()
    man = os.path.join(d, "manifest.json")
    aws.deploy(man, cl=cl, sleep=lambda s: None)
    from prism_pipeline.campaign import set_environment
    set_environment(cl["lambda"], aws.functions(), {"PRISM_K": 1, "PRISM_CALIBRATION": "0"}, sleep=lambda s: None,
                    poll_s=0)
    cl["logs"].page_size = page_size
    t0 = time.time_ns() // 1_000_000
    os.makedirs(os.path.join(d, "baseline_ondemand"))
    Driver(ChainExecutor(cl["lambda"], aws.functions()), os.path.join(d, "baseline_ondemand", "records.jsonl"),
           "baseline_ondemand").run(poisson_stream(n, 600.0, 3, mean_words=150))
    return cl, man, d, (t0 - 1000, time.time_ns() // 1_000_000 + 1000)


def report_ids_in_logs(cl):
    from prism_measure.report import parse_report_line
    return {parse_report_line(e["message"])["request_id"] for evs in cl["logs"].events.values() for e in evs
            if e["message"].startswith("REPORT RequestId")}


def saved(d):
    return aws._jsonl(os.path.join(d, aws.REPORTS_FILE))


def fail_on(cl, calls, exc=lambda: EndpointConnectionError('Could not connect to the endpoint URL: "https://'
                                                           'us-east-2.signin.aws.amazon.com/v1/token"')):
    """Make filter_log_events raise on the given 1-based call numbers (a set, or 'from:k' for every call from k)."""
    real = cl["logs"].filter_log_events
    n = {"i": 0}

    def wrapped(**kw):
        n["i"] += 1
        hit = n["i"] >= calls[1] if isinstance(calls, tuple) else n["i"] in calls
        if hit:
            raise exc()
        return real(**kw)
    cl["logs"].filter_log_events = wrapped
    return real


class TestCollection(unittest.TestCase):
    def test_interrupted_pagination_keeps_completed_pages_and_does_not_raise(self):
        cl, man, d, (lo, hi) = run_with_reports(n=7, page_size=3)      # first group: pages of 3, 3, 1
        fail_on(cl, ("from", 3))                              # pages 1-2 of the first group succeed, then it fails
        sleeps = []
        plan = aws.collect_reports(man, lo, hi, cl=cl, sleep=sleeps.append)
        self.assertTrue(plan[-1].startswith("collection INCOMPLETE (EndpointConnectionError"))
        self.assertEqual(len(saved(d)), 6)                    # two full pages, flushed before the failure
        st = aws.load_manifest(os.path.join(d, aws.COLLECT_STATE_FILE))
        g = st["groups"][aws.load_manifest(man)["log_groups"][0]]
        self.assertEqual((g["pages"], g["done"], g["next_token"] is not None), (2, False, True))
        self.assertEqual(st["status"], "incomplete")
        self.assertEqual(sleeps, [1, 2, 4, 8])                # bounded backoff, aws.COLLECT_ATTEMPTS = 5

    def test_transient_failure_is_retried_within_the_call(self):
        cl, man, d, (lo, hi) = run_with_reports()
        fail_on(cl, {2})                                      # one failed page, then recovery
        plan = aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        self.assertEqual(plan[-1], "collection complete")
        self.assertEqual({r["request_id"] for r in saved(d)}, report_ids_in_logs(cl))

    def test_resume_after_failure_completes_without_duplicates(self):
        cl, man, d, (lo, hi) = run_with_reports(n=5, page_size=3)
        real = fail_on(cl, ("from", 4))
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        before = len(saved(d))
        cl["logs"].filter_log_events = real                    # connection back; no Lambda invocation is rerun
        n_inv = cl["lambda"].invocations if hasattr(cl["lambda"], "invocations") else None
        plan = aws.collect_reports(man, cl=cl, sleep=lambda s: None)    # resume: window and tokens from the state
        self.assertEqual(plan[-1], "collection complete")
        ids = [r["request_id"] for r in saved(d)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), report_ids_in_logs(cl))
        self.assertGreater(len(ids), before)
        self.assertEqual(aws.load_manifest(os.path.join(d, aws.COLLECT_STATE_FILE))["calls"], 2)
        if n_inv is not None:
            self.assertEqual(cl["lambda"].invocations, n_inv)

    def test_crash_after_page_write_before_token_save_resumes_without_duplicates(self):
        cl, man, d, (lo, hi) = run_with_reports(n=7, page_size=3)
        real_save, n = aws._atomic_json, {"i": 0}

        def crash_second_save(obj, path):
            n["i"] += 1
            if n["i"] == 2:
                raise RuntimeError("process killed")
            real_save(obj, path)
        aws._atomic_json = crash_second_save
        try:
            with self.assertRaises(RuntimeError):
                aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        finally:
            aws._atomic_json = real_save
        self.assertEqual(len(saved(d)), 6)                    # page 2 is on disk, its token is not
        aws.collect_reports(man, cl=cl, sleep=lambda s: None)
        ids = [r["request_id"] for r in saved(d)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), report_ids_in_logs(cl))
        st = aws.load_manifest(os.path.join(d, aws.COLLECT_STATE_FILE))
        self.assertGreaterEqual(sum(g["skipped_duplicates"] for g in st["groups"].values()), 3)

    def test_expired_token_restarts_the_group_without_duplicates(self):
        cl, man, d, (lo, hi) = run_with_reports(n=4, page_size=3)
        real = cl["logs"].filter_log_events
        n = {"i": 0}

        def expire_once(**kw):
            if kw.get("nextToken") and n["i"] == 0:
                n["i"] += 1
                raise FakeClientError("InvalidParameterException", "The specified nextToken is expired")
            return real(**kw)
        cl["logs"].filter_log_events = expire_once
        plan = aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        self.assertEqual(plan[-1], "collection complete")
        ids = [r["request_id"] for r in saved(d)]
        self.assertEqual((len(ids), set(ids)), (len(set(ids)), report_ids_in_logs(cl)))

    def test_a_first_call_needs_a_window(self):
        cl, man, d, _ = run_with_reports(n=2)
        with self.assertRaises(ValueError):
            aws.collect_reports(man, cl=cl)


class TestCoverage(unittest.TestCase):
    def test_complete_when_every_recorded_id_has_a_report(self):
        cl, man, d, (lo, hi) = run_with_reports(n=4)
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        cov = aws.report_coverage(d)
        self.assertTrue(cov["complete"])
        self.assertEqual((cov["expected_request_ids"], cov["missing"]), (16, 0))     # 4 records x 4 stages
        self.assertTrue(aws.coverage_complete(d))

    def test_missing_reports_are_listed_and_block_verification(self):
        cl, man, d, (lo, hi) = run_with_reports(n=4)
        lg = aws.load_manifest(man)["log_groups"][1]
        dropped = [e for e in cl["logs"].events[lg] if e["message"].startswith("REPORT RequestId")][:2]
        for e in dropped:                                     # two REPORT lines never delivered
            cl["logs"].events[lg].remove(e)
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        cov = aws.report_coverage(d)
        self.assertEqual(cov["collection_status"], "complete")
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["missing"], 2)
        want = {e["message"].split()[2] for e in dropped}
        self.assertEqual({m["request_id"] for m in cov["missing_ids"]}, want)
        self.assertTrue(all(m["arm"] == "baseline_ondemand" and m["stage"] for m in cov["missing_ids"]))

    def test_incomplete_collection_is_not_complete_even_without_missing_ids(self):
        cl, man, d, (lo, hi) = run_with_reports(n=2, page_size=50)
        fail_on(cl, ("from", 4))                              # the fourth group never answers
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        cov = aws.report_coverage(d)
        self.assertEqual(cov["collection_status"], "incomplete")
        self.assertFalse(cov["complete"])


class TestCleanup(unittest.TestCase):
    def test_successful_collection_then_teardown_deletes_everything(self):
        cl, man, d, (lo, hi) = run_with_reports(n=3)
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        self.assertTrue(aws.report_coverage(d)["complete"])
        plan = aws.teardown(man, cl=cl)
        self.assertFalse(any(x.startswith(("RETAINED", "NOT CLEAN")) for x in plan))
        self.assertEqual(aws.leftovers(cl), {"functions": [], "state_machines": [], "log_groups": [], "roles": []})

    def test_failed_collection_keeps_only_this_runs_log_groups_then_resume_and_cleanup(self):
        cl, man, d, (lo, hi) = run_with_reports(n=3, page_size=3)
        cl["logs"].create_log_group(logGroupName="/aws/lambda/prism-meas-ingest-1024")   # not this run's
        cl["logs"].create_log_group(logGroupName="/aws/lambda/unrelated")
        real = fail_on(cl, ("from", 2))
        aws.collect_reports(man, lo, hi, cl=cl, sleep=lambda s: None)
        self.assertFalse(aws.report_coverage(d)["complete"])
        owned = aws.load_manifest(man)["log_groups"]
        cl["logs"].groups[owned[0]]["retention"] = None      # bounded retention is re-applied
        plan = aws.teardown(man, cl=cl)
        left = aws.leftovers(cl)
        self.assertEqual((left["functions"], left["state_machines"], left["roles"]), ([], [], []))
        self.assertEqual(sorted(left["log_groups"]), sorted(owned))
        self.assertTrue(all(cl["logs"].groups[g]["retention"] == aws.LOG_RETENTION_DAYS for g in owned))
        self.assertTrue(any(x.startswith("RETAINED 4 log groups") for x in plan))
        self.assertFalse(any(x.startswith("NOT CLEAN") for x in plan))
        self.assertEqual(sorted(aws.load_manifest(man)["retained_log_groups"]["groups"]), sorted(owned))
        refused = aws.cleanup_log_groups(man, cl=cl)
        self.assertTrue(refused[-1].startswith("REFUSED"))
        self.assertEqual(sorted(aws.leftovers(cl)["log_groups"]), sorted(owned))
        cl["logs"].filter_log_events = real                    # credentials refreshed by hand; resume
        self.assertEqual(aws.collect_reports(man, cl=cl, sleep=lambda s: None)[-1], "collection complete")
        self.assertTrue(aws.report_coverage(d)["complete"])
        done = aws.cleanup_log_groups(man, cl=cl)
        self.assertEqual(done[-1], "CLEAN")
        self.assertIn("/aws/lambda/prism-meas-ingest-1024", cl["logs"].groups)       # scope: untouched
        self.assertIn("/aws/lambda/unrelated", cl["logs"].groups)

    def test_teardown_without_a_coverage_check_keeps_logs(self):
        cl, man, d, _ = run_with_reports(n=2)                 # crashed before collection: no coverage file
        plan = aws.teardown(man, cl=cl)
        self.assertTrue(any(x.startswith("RETAINED") for x in plan))
        self.assertEqual(len(aws.leftovers(cl)["log_groups"]), 4)

    def test_forced_cleanup_and_old_behaviour_are_explicit(self):
        cl, man, d, _ = run_with_reports(n=2)
        aws.teardown(man, cl=cl)
        out = aws.cleanup_log_groups(man, cl=cl, force=True)
        self.assertEqual(out[-1], "CLEAN")
        self.assertTrue(aws.load_manifest(man)["retained_log_groups"]["forced"])
        cl2, man2, _, _ = run_with_reports(n=2)
        aws.teardown(man2, cl=cl2, delete_log_groups="always")
        self.assertEqual(aws.leftovers(cl2)["log_groups"], [])


class TestLiveTestSequence(unittest.TestCase):
    """The whole live-test sequence on the fakes, with and without a collection failure."""

    def _run(self, fail):
        from prism_pipeline.selftest import scaled_spec
        from prism_pipeline.livetest import run
        cl = fake_cloud(account_limit=10)
        if fail:
            fail_on(cl, ("from", 1))
        spec = scaled_spec()
        spec.collect_attempts = 1
        d = tempfile.mkdtemp()
        return cl, d, run(d, spec, cl=cl)

    def test_collection_failure_marks_unverified_and_keeps_logs(self):
        cl, d, r = self._run(fail=True)
        self.assertFalse(r["verified"])
        self.assertEqual(r["coverage"]["collection_status"], "incomplete")
        self.assertGreater(r["coverage"]["missing"], 0)
        left = aws.leftovers(cl)
        self.assertEqual((left["functions"], left["state_machines"], left["roles"]), ([], [], []))
        self.assertEqual(len(left["log_groups"]), 4)
        self.assertTrue(any(x.startswith("RETAINED") for x in r["teardown"]))
        self.assertTrue(os.path.exists(os.path.join(d, aws.COLLECT_STATE_FILE)))

    def test_successful_collection_is_verified_and_clean(self):
        cl, d, r = self._run(fail=False)
        self.assertTrue(r["verified"])
        self.assertTrue(r["coverage"]["complete"])
        self.assertEqual(r["coverage"]["missing"], 0)
        self.assertEqual(aws.leftovers(cl), {"functions": [], "state_machines": [], "log_groups": [], "roles": []})
        self.assertNotIn("boto3", sys.modules)


if __name__ == "__main__":
    unittest.main()
