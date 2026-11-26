"""Offline check of every AWS request the memcal campaign makes, against botocore's service models. NOTHING IS SENT.

Same mechanism as check_botocore_shapes.py: real boto3 clients for us-east-2 with dummy credentials validate and
serialise each request, then a before-call hook answers it from the in-process fakes, so signing and sending never
happen. Sockets are blocked for the whole run. The sequence is the campaign's real authorised path (preflight, deploy,
smoke on a reduced K, one REPORT removed before collection, collect, rescan, coverage, a missing-REPORT teardown that retains the log groups, forced
log cleanup, verify). The authorisation variable is set inside this process only.

Not part of `unittest discover` (it needs botocore). Run from prism-repro/aws_pipeline:
  ../venv/Scripts/python tests/check_botocore_memcal.py <out dir>
"""
import collections
import json
import os
import socket
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_botocore_shapes import botocore, hooked_clients  # noqa: E402  (also sets up boto3 and the paths)
from prism_pipeline import aws, memcal as M  # noqa: E402
from prism_pipeline.fake import fake_cloud  # noqa: E402


def main(out_dir):
    real = socket.socket

    class Blocked(real):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in the offline botocore check")
    socket.socket = Blocked
    os.environ[aws.AUTH_ENV] = aws.AUTH_VALUE
    calls = collections.Counter()
    log, bad = {}, []
    try:
        fakes = fake_cloud(account_limit=10)
        cl = hooked_clients(fakes, calls)
        for c in cl.values():
            c.IS_OFFLINE_HOOKED = True                        # lets the dry-run K scale through deploy; nothing else
        nosleep = lambda s: None  # noqa: E731
        log["prepare"] = M.prepare(out_dir)
        log["preflight"] = M.preflight(execute=True, cl=cl)[3:]
        log["deploy"] = M.deploy(out_dir, execute=True, cl=cl, sleep=nosleep, k_scale=0.001)[-1:]
        log["smoke"] = M.run(out_dir, execute=True, cl=cl, smoke=True, sleep=nosleep)[1:]
        ev = fakes["logs"].events["/aws/lambda/prism-mcal-ingest-512"]
        ev.remove(next(e for e in ev if e["message"].startswith("REPORT RequestId")))   # lost before collection
        log["collect"] = M.collect(out_dir, execute=True, cl=cl, sleep=nosleep)[1:]
        log["collect_rescan"] = M.collect(out_dir, execute=True, cl=cl, sleep=nosleep, rescan=True)[1:]
        cov = M.report_coverage(out_dir)
        log["coverage"] = {k: v for k, v in cov.items() if k != "missing_ids"}
        log["teardown"] = M.teardown(out_dir, execute=True, cl=cl)[4:]
        log["cleanup_refused"] = M.cleanup_logs(out_dir, execute=True, cl=cl)[1:]
        log["cleanup_forced"] = M.cleanup_logs(out_dir, execute=True, cl=cl, force=True)[1:]
        log["verify"] = M.verify(execute=True, cl=cl)[1:]
        try:                                                  # a deliberately wrong parameter must be rejected locally
            cl["lambda"].create_function(FunctionName="x", Runtime="python3.12", Role="r", Handler="h",
                                         Code={"ZipFile": b"0"}, MemorySizeMB=512)
            bad.append("wrong parameter accepted")
        except botocore.exceptions.ParamValidationError:
            pass
    finally:
        os.environ.pop(aws.AUTH_ENV, None)
        socket.socket = real
    rep = {"botocore": botocore.__version__, "region": M.REGION, "calls": dict(sorted(calls.items())),
           "negative_control": bad or "wrong parameter rejected by ParamValidationError", "log": log}
    rep["ok"] = (not bad and "SMOKE OK" in log["smoke"] and cov["missing"] == 1 and not cov["complete"]
                 and any(x.startswith("RETAINED 16 log groups") for x in log["teardown"])
                 and log["cleanup_refused"][-1].startswith("REFUSED") and log["verify"][-1] == "CLEAN")
    with open(os.path.join(out_dir, "botocore_check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
    os.makedirs(d, exist_ok=True)
    raise SystemExit(main(d))
