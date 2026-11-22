"""Offline check of every AWS request the live test makes, against botocore's service models. NOTHING IS SENT.

Real boto3 clients are built with dummy credentials for us-east-2. botocore validates and serialises each request as
it would for AWS (ParamValidationError on a wrong name or type), then its `before-call` hook hands the call to the
in-process fakes, whose answer is returned instead of an HTTP request; request signing and sending never happen.
Sockets are blocked for the whole run. The live-test sequence (livetest.run) then runs end to end through these
clients on its real authorised path; the authorisation variable is set inside this process only, which is safe
because no request can leave it.

Not part of `unittest discover` (it needs botocore). Run from prism-repro/aws_pipeline:
  ../venv/Scripts/python tests/check_botocore_shapes.py <out dir>
It uses aws_measurement/.venv-aws's site-packages for boto3 if the project venv has none (nothing is installed).
"""
import collections
import json
import os
import socket
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
try:
    import boto3  # noqa: F401
except ImportError:
    sys.path.append(os.path.join(ROOT, "..", "aws_measurement", ".venv-aws", "Lib", "site-packages"))
import boto3  # noqa: E402
import botocore  # noqa: E402
from botocore import xform_name  # noqa: E402

import prism_pipeline  # noqa: E402,F401
import prism_repro.closed_loop  # noqa: E402,F401  (imports ssl before sockets are blocked)
from prism_pipeline import aws  # noqa: E402
from prism_pipeline.fake import FakeClientError, fake_cloud  # noqa: E402


class _Http:
    def __init__(self, code):
        self.status_code, self.headers, self.content, self.raw = code, {}, b"", None


def hooked_clients(fakes, calls):
    out = {}
    for svc in ("lambda", "logs", "iam", "sts", "stepfunctions"):
        c = boto3.client(svc, region_name=aws.DEFAULT_REGION, aws_access_key_id="OFFLINE",
                         aws_secret_access_key="OFFLINE", aws_session_token="OFFLINE")
        fake = fakes[svc]

        def keep(params, context, model, _svc=svc, **kw):
            context["offline_params"] = dict(params)

        def answer(model, context, _svc=svc, _fake=fake, **kw):
            op = xform_name(model.name)
            calls[f"{_svc}.{op}"] += 1
            try:
                r = getattr(_fake, op)(**context["offline_params"])
            except FakeClientError as e:
                return _Http(400), {"Error": e.response["Error"], "ResponseMetadata": {"HTTPStatusCode": 400}}
            r = dict(r or {})
            r.setdefault("ResponseMetadata", {"HTTPStatusCode": 200})
            return _Http(200), r

        c.meta.events.register(f"before-parameter-build.{c.meta.service_model.service_id.hyphenize()}", keep)
        c.meta.events.register(f"before-call.{c.meta.service_model.service_id.hyphenize()}", answer)
        out[svc] = c
    return out


def main(out_dir):
    real = socket.socket

    class Blocked(real):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in the offline botocore check")
    socket.socket = Blocked
    os.environ[aws.AUTH_ENV] = aws.AUTH_VALUE           # in-process only; no request can leave (see docstring)
    calls = collections.Counter()
    try:
        from prism_pipeline.livetest import run
        from prism_pipeline.selftest import scaled_spec
        fakes = fake_cloud(account_limit=10)
        cl = hooked_clients(fakes, calls)
        r = run(out_dir, scaled_spec(), cl=cl, execute=True)
        bad = []
        try:                                            # a deliberately wrong parameter must be rejected locally
            cl["lambda"].update_function_configuration(FunctionName="x", MemorySizeMB=512)
            bad.append("wrong parameter accepted")
        except botocore.exceptions.ParamValidationError:
            pass
    finally:
        os.environ.pop(aws.AUTH_ENV, None)
        socket.socket = real
    rep = {"botocore": botocore.__version__, "region": aws.DEFAULT_REGION, "error": r.get("error"),
           "teardown_last": (r.get("teardown") or [None])[-1], "calls": dict(sorted(calls.items())),
           "negative_control": bad or "wrong parameter rejected by ParamValidationError",
           "arms": {k: v["summary"] for k, v in (r.get("arms") or {}).items()}}
    rep["ok"] = rep["error"] is None and not bad and "remaining after teardown" in str(rep["teardown_last"]) \
        and "NOT CLEAN" not in json.dumps(r.get("teardown"))
    with open(os.path.join(out_dir, "botocore_check.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
    os.makedirs(d, exist_ok=True)
    raise SystemExit(main(d))
