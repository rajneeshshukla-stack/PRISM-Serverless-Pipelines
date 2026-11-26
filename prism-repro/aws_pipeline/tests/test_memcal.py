"""Multi-memory calibration campaign (prism_pipeline/memcal.py). NO AWS CALLS: in-process fakes and synthetic records
only, sockets blocked for the whole module, boto3 never imported.
Run from prism-repro/aws_pipeline:  python -m unittest tests.test_memcal -v
"""
import json
import math
import os
import random
import socket
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import prism_pipeline  # noqa: E402,F401  (path setup)
import prism_repro.closed_loop  # noqa: E402,F401  (imports ssl before sockets are blocked)
from prism_pipeline import aws, memcal as M  # noqa: E402
from prism_pipeline.fake import FakeClientError, fake_cloud  # noqa: E402

_REAL_SOCKET = socket.socket
NOSLEEP = lambda s: None  # noqa: E731


def setUpModule():
    class Blocked(_REAL_SOCKET):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in a memcal test")
    socket.socket = Blocked


def tearDownModule():
    socket.socket = _REAL_SOCKET


def deployed(k_scale=0.001):
    cl = fake_cloud(account_limit=10)
    d = tempfile.mkdtemp()
    M.prepare(d)
    M.deploy(d, execute=True, cl=cl, sleep=NOSLEEP, k_scale=k_scale)
    return cl, d


class Design(unittest.TestCase):
    def test_counts_split_and_cap(self):
        d = M.build()
        s = M.split_of(d)
        c = M.counts(d, s)
        self.assertEqual(len(c), 16)
        self.assertEqual(len(d.visits), 624)
        for key, v in c.items():
            self.assertEqual((v["cold"], v["warm"], v["visits"]), (312, 1000, 39), key)
            self.assertEqual((v["fit_visits"], v["check_visits"]), (29, 10), key)
            self.assertEqual((v["fit_cold"], v["check_cold"]), (232, 80), key)
            self.assertEqual(sorted(v["check_by_block"]), [3, 3, 4], key)
        self.assertTrue(all(v.cold <= M.CAP and all(0 < w <= M.CAP for w in v.warm_batches) for v in d.visits))
        self.assertEqual(set(s), {M.visit_id(v) for v in d.visits})
        self.assertEqual(d.to_json(), M.build().to_json())            # deterministic
        self.assertEqual(s, M.split_of(M.build()))
        self.assertTrue(all(c.function.startswith("prism-mcal-") for c in d.cells()))

    def test_sizes_randomised_within_blocks(self):
        d = M.build()
        for b in range(M.BLOCKS):
            seq = [v.cell.memory_mb for v in sorted(d.visits, key=lambda v: v.order) if v.block == b]
            self.assertEqual(sorted(set(seq)), list(M.SIZES))
            self.assertNotEqual(seq, sorted(seq))


class Workload(unittest.TestCase):
    def test_frozen_environment(self):
        for s in M.STAGES:
            e = M.function_env(s)
            self.assertEqual(e["PRISM_K"], str(M.FROZEN_K[s]))
            self.assertEqual((e["PRISM_CALIBRATION"], e["PRISM_INIT_ROWS"], e["PRISM_SINK"]), ("0", "0", "none"))
        self.assertEqual(M.FROZEN_K, {"ingest": 373, "transform": 4908, "aggregate": 2264, "load": 1966})

    def test_inputs_identical_and_independent_of_k(self):
        a, b = M.stage_inputs(), M.stage_inputs()
        self.assertEqual(a, b)
        mod = M._load_handler()
        env = dict(M.REFERENCE, trace=[])
        d1 = mod._LOGIC["ingest"](json.loads(json.dumps(env)), 1)["doc"]
        d2 = mod._LOGIC["ingest"](json.loads(json.dumps(env)), 37)["doc"]
        self.assertEqual(d1, d2)                                     # the document passed on does not depend on K
        self.assertEqual(a["transform"]["doc"], d1)

    def test_spec_records_runtime_and_startup(self):
        s = M.workload_spec()
        self.assertEqual((s["runtime"], s["architecture"], s["region"]), ("python3.12", "x86_64", "us-east-2"))
        self.assertFalse(s["retuned_per_size"])
        self.assertIn("by construction", s["reference_matched_by_construction"])
        self.assertIn("module_scope_inside_INIT", s["startup_behaviour"])


class Guard(unittest.TestCase):
    def test_plan_only_and_refusal(self):
        d = tempfile.mkdtemp()
        os.environ.pop(aws.AUTH_ENV, None)
        for f in (lambda: M.deploy(d), lambda: M.run(d, [0]), lambda: M.collect(d), lambda: M.teardown(d),
                  lambda: M.cleanup_logs(d), lambda: M.preflight(), lambda: M.verify()):
            self.assertIsInstance(f(), list)                         # plan only, nothing built
        with self.assertRaises(PermissionError):
            M.deploy(d, execute=True)

    def test_k_scale_only_on_fakes(self):
        os.environ[aws.AUTH_ENV] = aws.AUTH_VALUE
        try:
            with self.assertRaises(ValueError):
                M.deploy(tempfile.mkdtemp(), execute=True, cl={"lambda": object()}, k_scale=0.5)
        finally:
            os.environ.pop(aws.AUTH_ENV, None)


class Campaign(unittest.TestCase):
    def test_smoke_collect_teardown_clean(self):
        cl, d = deployed()
        man = aws.load_manifest(os.path.join(d, "manifest.json"))
        self.assertEqual(len(man["functions"]), 16)
        self.assertEqual({f["memory_mb"] for f in man["functions"].values()}, set(M.SIZES))
        self.assertEqual({cl["logs"].groups[g]["retention"] for g in man["log_groups"]}, {14})
        out = M.run(d, execute=True, cl=cl, smoke=True, sleep=NOSLEEP)
        self.assertIn("SMOKE OK", out)
        chk = json.loads(next(x for x in out if x.startswith("smoke check: "))[len("smoke check: "):])
        self.assertEqual(chk["runtime_versions"], ["python:3.12.fake"])     # from INIT_START; the ARN is dropped
        recs = aws._jsonl(os.path.join(d, M.SMOKE_DIR, M.RECORDS))
        self.assertFalse(any("arn:aws" in json.dumps(r) for r in recs))
        self.assertLessEqual(cl["lambda"].max_in_flight, M.CAP)
        M.collect(d, execute=True, cl=cl, sleep=NOSLEEP)
        cov = M.report_coverage(d)
        self.assertTrue(cov["complete"])
        self.assertEqual((cov["expected_request_ids"], cov["missing"], cov["tail_and_cloudwatch_differ"]), (256, 0, 0))
        t = M.teardown(d, execute=True, cl=cl)
        self.assertEqual(t[-1], "CLEAN")
        self.assertEqual(M.verify(execute=True, cl=cl)[-1], "CLEAN")

    def test_drift_blocks_the_run(self):
        cl, d = deployed()
        fn = "prism-mcal-transform-2048"
        cl["lambda"].update_function_configuration(FunctionName=fn, MemorySize=1024)
        out = M.run(d, [0], execute=True, cl=cl, sleep=NOSLEEP)
        self.assertTrue(any(x.startswith("STOP") for x in out))
        self.assertTrue(any("MemorySize" in x and fn in x for x in out))
        self.assertFalse(os.path.exists(os.path.join(d, M.RECORDS)))
        cl["lambda"].update_function_configuration(FunctionName=fn, MemorySize=2048)
        env = dict(cl["lambda"].get_function_configuration(FunctionName=fn)["Environment"]["Variables"], PRISM_K="999")
        cl["lambda"].update_function_configuration(FunctionName=fn, Environment={"Variables": env})
        out = M.run(d, [0], execute=True, cl=cl, sleep=NOSLEEP)
        self.assertTrue(any("environment" in x and fn in x for x in out))

    def test_design_tamper_blocks_the_run(self):
        cl, d = deployed()
        p = os.path.join(d, M.DESIGN_FILE)
        doc = aws.load_manifest(p)
        k = next(iter(doc["split"]))
        doc["split"][k] = "fit" if doc["split"][k] == "check" else "check"
        aws._save(doc, p)
        out = M.run(d, [0], execute=True, cl=cl, sleep=NOSLEEP)
        self.assertTrue(any(x.startswith("STOP: design.json") for x in out))

    def test_missing_report_retains_log_groups(self):
        cl, d = deployed()
        M.run(d, execute=True, cl=cl, smoke=True, sleep=NOSLEEP)
        g = "/aws/lambda/prism-mcal-load-512"
        ev = cl["logs"].events[g]
        i = next(i for i, e in enumerate(ev) if e["message"].startswith("REPORT RequestId"))
        del ev[i]
        M.collect(d, execute=True, cl=cl, sleep=NOSLEEP)
        cov = M.report_coverage(d)
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["missing"], 1)
        t = M.teardown(d, execute=True, cl=cl)
        self.assertTrue(any(x.startswith("RETAINED 16 log groups") for x in t))
        left = M.leftovers(cl)
        self.assertEqual((left["functions"], left["roles"], len(left["log_groups"])), ([], [], 16))
        self.assertEqual({cl["logs"].groups[g]["retention"] for g in left["log_groups"]}, {14})
        self.assertTrue(M.cleanup_logs(d, execute=True, cl=cl)[-1].startswith("REFUSED"))
        self.assertEqual(M.cleanup_logs(d, execute=True, cl=cl, force=True)[-1], "CLEAN")

    def test_collection_resumes_after_failure(self):
        cl, d = deployed()
        M.run(d, execute=True, cl=cl, smoke=True, sleep=NOSLEEP)
        real = cl["logs"].filter_log_events
        calls = {"n": 0}

        def flaky(**kw):
            calls["n"] += 1
            if 3 <= calls["n"] <= 8:                                  # fails a whole page's 5 attempts
                raise FakeClientError("EndpointConnectionError", "sign-in token endpoint")
            return real(**kw)
        cl["logs"].filter_log_events = flaky
        first = M.collect(d, execute=True, cl=cl, sleep=NOSLEEP)
        self.assertTrue(first[-1].startswith("collection INCOMPLETE"))
        self.assertFalse(M.report_coverage(d)["complete"])
        second = M.collect(d, execute=True, cl=cl, sleep=NOSLEEP)
        self.assertEqual(second[-1], "collection complete")
        cov = M.report_coverage(d)
        self.assertTrue(cov["complete"])
        ids = [r["request_id"] for r in aws._jsonl(os.path.join(d, aws.REPORTS_FILE))]
        self.assertEqual(len(ids), len(set(ids)))


def synthetic_records(d, split, rng):
    """Known truth: warm Duration = d1024 * (0.3 + 0.7 * 1024/m); Lambda-reported init 0.15 s at every size;
    unreported environment creation 0.2 * 1024/m s; network 0.03 s; 1% multiplicative noise."""
    noise = lambda: math.exp(rng.gauss(0, 0.01))  # noqa: E731
    rows, n = [], 0
    for v in d.visits:
        vid = M.visit_id(v)
        m, st = v.cell.memory_mb, v.cell.variant
        base = {"type": "invocation", "visit_id": vid, "attempt": 0, "block": v.block, "group": "main",
                "variant": st, "memory_mb": m, "function": v.cell.function, "error": None, "function_error": None}
        for kind, sizes in (("cold", [v.cold]), ("warm", v.warm_batches)):
            for j, size in enumerate(sizes):
                for slot in range(size):
                    n += 1
                    rid = f"r{n:06d}"
                    dur = M.WARM_MEAN_1024[st] * (0.3 + 0.7 * 1024 / m) * noise()
                    init = 0.15 * noise() if kind == "cold" else None
                    create = 0.2 * 1024 / m * noise() if kind == "cold" else 0.0
                    rep = {"request_id": rid, "duration_ms": dur * 1000, "billed_duration_ms": math.ceil(
                        (dur + (init or 0)) * 1000), "memory_size_mb": m, "max_memory_used_mb": 40,
                        "init_duration_ms": init * 1000 if init else None, "complete": True}
                    rows.append(dict(base, batch_kind=kind, batch_id=f"{vid}-a0-{kind}{j}", slot=slot, request_id=rid,
                                     e2e_s=dur + (init or 0) + create + 0.03, report=rep,
                                     payload={"first_call": kind == "cold", "aws_request_id": rid},
                                     wall_start_ns=0))
        rows.append({"type": "visit_done", "visit_id": vid, "attempt": 0})
    return rows


class Analysis(unittest.TestCase):
    def test_recovers_known_truth_and_holds_out_check_visits(self):
        rng = random.Random(5)
        d = tempfile.mkdtemp()
        M.prepare(d)
        doc = aws.load_manifest(os.path.join(d, M.DESIGN_FILE))
        rows = synthetic_records(M.build(), doc["split"], rng)
        with open(os.path.join(d, M.RECORDS), "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
        out = os.path.join(d, "analysis")
        r = M.analyse(d, out, n_boot=200)
        inv = r["summary"]["invocations"]
        self.assertEqual(inv["fit"] + inv["check"], 20992)
        self.assertEqual(inv["check"], sum(1 for x in rows if x["type"] == "invocation"
                                           and doc["split"][x["visit_id"]] == "check"))
        for st in M.STAGES:
            self.assertAlmostEqual(r["calibration"]["warm_eq2"][st]["nonscaling"], 0.3, delta=0.02)
        p = r["calibration"]["init_eq3_P_mean"]["POOLED"]
        self.assertAlmostEqual(p["init_nonscaling"], 0.15 / 0.35, delta=0.03)
        self.assertAlmostEqual(p["at_1024_s"], 0.35, delta=0.01)
        pooled = next(t for t in r["trend"] if t["stage"] == "POOLED")
        self.assertLess(pooled["I_slope_hi"], 0.03)
        self.assertGreater(pooled["I_slope_lo"], -0.03)              # Lambda-reported init flat
        self.assertTrue(pooled["P_slope_hi"] < 0)                    # full penalty falls with memory
        self.assertTrue(pooled["reading"].startswith("P and I trends differ"))
        self.assertTrue(pooled["decision_on_P"].startswith("keep the direction"))
        frac = r["summary"]["check_inside_interval"] / r["summary"]["check_rows"]
        self.assertGreater(frac, 0.8)
        for f in ("calibration.json", "calibration_check.csv", "trend_compare.csv", "summary.json",
                  "fit/cells.csv", "check/cells.csv", "all/billing.csv"):
            self.assertTrue(os.path.exists(os.path.join(out, f)), f)


class Estimate(unittest.TestCase):
    def test_estimate_counts_and_prices(self):
        e = M.estimate()
        for sc in e["scenarios"].values():
            self.assertEqual(sc["campaign"]["invocations"], 20992)
            self.assertEqual(sc["smoke"]["invocations"], 256)
            self.assertGreater(sc["planning_upper_usd"], 0)
        self.assertEqual(e["prices"]["lambda_gb_s_x86_tier1"], 0.0000166667)


if __name__ == "__main__":
    unittest.main()
