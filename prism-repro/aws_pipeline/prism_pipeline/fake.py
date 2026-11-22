"""In-process fakes of the AWS calls the pipeline makes. NO NETWORK, NO AWS.

FakeLambda runs the REAL handler module (handlers/docpipe.py): a cold start imports a fresh copy of the module (its
module-scope start-up work runs, a new ENV_ID is drawn), a warm call reuses an idle copy, and any configuration change
retires every idle copy, as Lambda retires environments. Each invocation writes START/END/REPORT lines (Init Duration
on cold calls) to FakeLogs and returns them as the base64 log tail. Durations are the handler's measured host time
times `slow(memory_mb)` (default 1024/m, CPU share proportional to memory); when that exceeds the host time the fake
sleeps the difference, so client-side timing and deadlines see it. An account concurrency limit throttles above
`account_limit`. FakeStepFunctions interprets the linear Task-state ASL of asl.py against FakeLambda. FakeIAM,
FakeLogs and FakeSTS hold just enough state to test deploy, collect and teardown, including what they leave behind.
"""
from __future__ import annotations

import base64
import importlib.util
import io
import itertools
import json
import math
import os
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional

from prism_measure.report import format_report_line

HANDLER_FILE = os.path.join(os.path.dirname(__file__), "..", "handlers", "docpipe.py")
_IMPORT_LOCK = threading.Lock()
_SEQ = itertools.count()


class FakeClientError(Exception):
    def __init__(self, code: str, msg: str = ""):
        super().__init__(f"{code}: {msg}")
        self.response = {"Error": {"Code": code, "Message": msg}}


class _Body(io.BytesIO):
    pass


class _Paginator:
    def __init__(self, fn, key):
        self.fn, self.key = fn, key

    def paginate(self, **kw):
        yield self.fn(**kw)


class _Ctx:
    def __init__(self, rid, fn, mem):
        self.aws_request_id, self.function_name, self.memory_limit_in_mb = rid, fn, mem
        self.function_version = "$LATEST"


# --------------------------------------------------------------------------- logs
class FakeLogs:
    IS_FAKE = True
    def __init__(self, clock_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000):
        self.groups: Dict[str, dict] = {}
        self.events: Dict[str, List[dict]] = {}
        self.clock_ms = clock_ms
        self._lock = threading.Lock()
        self.page_size = 50

    def create_log_group(self, logGroupName, tags=None):
        with self._lock:
            if logGroupName in self.groups:
                raise FakeClientError("ResourceAlreadyExistsException", logGroupName)
            self.groups[logGroupName] = {"tags": dict(tags or {}), "retention": None}
            self.events.setdefault(logGroupName, [])

    def put_retention_policy(self, logGroupName, retentionInDays):
        self.groups[logGroupName]["retention"] = retentionInDays

    def delete_log_group(self, logGroupName):
        with self._lock:
            if logGroupName not in self.groups:
                raise FakeClientError("ResourceNotFoundException", logGroupName)
            del self.groups[logGroupName]
            self.events.pop(logGroupName, None)

    def put(self, group, message):
        with self._lock:
            if group not in self.groups:                     # Lambda creates a missing group itself (no retention)
                self.groups[group] = {"tags": {}, "retention": None, "auto_created": True}
            self.events.setdefault(group, []).append({"timestamp": self.clock_ms(), "message": message})

    def describe_log_groups(self, logGroupNamePrefix=""):
        return {"logGroups": [{"logGroupName": g} for g in sorted(self.groups) if g.startswith(logGroupNamePrefix)]}

    def get_paginator(self, name):
        return _Paginator(getattr(self, name), name)

    def filter_log_events(self, logGroupName, filterPattern="", startTime=0, endTime=2**63, nextToken=None, **_):
        needle = filterPattern.strip('"')
        ev = [e for e in self.events.get(logGroupName, [])
              if needle in e["message"] and startTime <= e["timestamp"] <= endTime]
        i = int(nextToken or 0)
        page = ev[i:i + self.page_size]
        out = {"events": page}
        if i + self.page_size < len(ev):
            out["nextToken"] = str(i + self.page_size)
        return out


# --------------------------------------------------------------------------- lambda
class FakeLambda:
    IS_FAKE = True
    def __init__(self, logs: Optional[FakeLogs] = None, account_limit: int = 10, unreserved: Optional[int] = None,
                 slow: Optional[Callable[[int], float]] = None, runtime_init_s: float = 0.0,
                 create_s: float = 0.0, p_drop_tail_report: float = 0.0, seed: int = 1, sleep=time.sleep,
                 update_polls: int = 1):
        import random
        self.logs = logs or FakeLogs()
        self.account_limit = account_limit
        self.unreserved = account_limit if unreserved is None else unreserved
        self.slow = slow or (lambda m: 1024.0 / m)
        self.runtime_init_s, self.create_s = runtime_init_s, create_s
        self.p_drop = p_drop_tail_report
        self.rng = random.Random(seed)
        self.sleep = sleep
        self.update_polls = update_polls
        self.fns: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self.in_flight = self.max_in_flight = self.calls = self.throttles = self.updates = 0
        self.pc_calls = 0
        self.network_calls = 0

    # ---- management
    def create_function(self, FunctionName, Runtime, Role, Handler, Code, Timeout, MemorySize, Architectures,
                        Environment, Tags=None):
        with self._lock:
            if FunctionName in self.fns:
                raise FakeClientError("ResourceConflictException", FunctionName)
            arn = f"arn:aws:lambda:us-east-2:000000000000:function:{FunctionName}"
            self.fns[FunctionName] = {"arn": arn, "handler": Handler, "memory": int(MemorySize),
                                      "env": dict(Environment["Variables"]), "tags": dict(Tags or {}), "gen": 0,
                                      "idle": [], "pending": 0, "timeout": Timeout, "zip_bytes": len(Code["ZipFile"])}
        return {"FunctionArn": arn, "State": "Pending"}

    def delete_function(self, FunctionName):
        with self._lock:
            if FunctionName not in self.fns:
                raise FakeClientError("ResourceNotFoundException", FunctionName)
            del self.fns[FunctionName]

    def list_functions(self):
        return {"Functions": [{"FunctionName": n, "FunctionArn": f["arn"]} for n, f in sorted(self.fns.items())]}

    def list_tags(self, Resource):
        for f in self.fns.values():
            if f["arn"] == Resource:
                return {"Tags": dict(f["tags"])}
        raise FakeClientError("ResourceNotFoundException", Resource)

    def get_paginator(self, name):
        return _Paginator(getattr(self, name), name)

    def get_account_settings(self):
        return {"AccountLimit": {"ConcurrentExecutions": self.account_limit,
                                 "UnreservedConcurrentExecutions": self.unreserved}}

    def update_function_configuration(self, FunctionName, Environment=None, MemorySize=None):
        with self._lock:
            f = self._get(FunctionName)
            if Environment is not None:
                f["env"] = dict(Environment["Variables"])
            if MemorySize is not None:
                f["memory"] = int(MemorySize)
            f["gen"] += 1
            f["idle"] = []                                   # every warm environment is retired
            f["pending"] = self.update_polls
            self.updates += 1
        return {"LastUpdateStatus": "InProgress"}

    def get_function_configuration(self, FunctionName):
        with self._lock:
            f = self._get(FunctionName)
            st = "InProgress" if f["pending"] > 0 else "Successful"
            f["pending"] = max(f["pending"] - 1, 0)
            return {"FunctionName": FunctionName, "FunctionArn": f["arn"], "MemorySize": f["memory"],
                    "State": "Active", "LastUpdateStatus": st, "Environment": {"Variables": dict(f["env"])}}

    def put_provisioned_concurrency_config(self, **kw):
        self.pc_calls += 1
        raise FakeClientError("InvalidParameterValueException", "quota too low for provisioned concurrency")

    def _get(self, fn):
        if fn not in self.fns:
            raise FakeClientError("ResourceNotFoundException", fn)
        return self.fns[fn]

    # ---- invocation
    def _new_env(self, fn, env):
        name = f"docpipe_fake_{next(_SEQ)}"
        spec = importlib.util.spec_from_file_location(name, HANDLER_FILE)
        mod = importlib.util.module_from_spec(spec)
        lines = []
        mod.print = lambda *a, **k: lines.append(" ".join(str(x) for x in a))
        with _IMPORT_LOCK:                                   # module scope reads os.environ: set it for the import
            saved = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                t0 = time.perf_counter()
                spec.loader.exec_module(mod)
                init_s = time.perf_counter() - t0
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        mod._ENV = dict(env)
        return mod, init_s, lines

    def invoke(self, FunctionName, InvocationType="RequestResponse", LogType="None", Payload=b"{}"):
        with self._lock:
            self.calls += 1
            if self.in_flight + 1 > self.account_limit:
                self.throttles += 1
                raise FakeClientError("TooManyRequestsException", f"Rate Exceeded (limit {self.account_limit})")
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            f = self._get(FunctionName)
            gen, mem, env, handler = f["gen"], f["memory"], dict(f["env"]), f["handler"]
            slot = f["idle"].pop() if f["idle"] else None
            rid = str(uuid.UUID(int=self.rng.getrandbits(128)))
            drop = self.rng.random() < self.p_drop
        group = f"/aws/lambda/{FunctionName}"
        lines: List[str] = [f"START RequestId: {rid} Version: $LATEST"]
        init_ms = None
        try:
            if slot is None:
                mod, init_s, ilines = self._new_env(FunctionName, env)
                lines = ilines + lines
                init_total = self.runtime_init_s + init_s * self.slow(mem)
                extra = self.create_s + self.runtime_init_s + init_s * max(self.slow(mem) - 1.0, 0.0)
                if extra > 0:
                    self.sleep(extra)
                init_ms = init_total * 1000.0
            else:
                mod = slot
            inv_lines: List[str] = []
            mod.print = lambda *a, **k: inv_lines.append(" ".join(str(x) for x in a))
            ev = json.loads(Payload or b"{}")
            t0 = time.perf_counter()
            err = None
            try:
                out = getattr(mod, handler.split(".", 1)[1])(ev, _Ctx(rid, FunctionName, mem))
            except Exception as e:                            # Lambda's unhandled-error response
                out, err = {"errorMessage": str(e), "errorType": type(e).__name__}, "Unhandled"
            host = time.perf_counter() - t0
            dur = host * self.slow(mem)
            if dur > host:
                self.sleep(dur - host)
            lines += inv_lines
            dur_ms = dur * 1000.0
            rep = format_report_line(rid, dur_ms, math.ceil(dur_ms), mem, 40, init_ms)
            lines += [f"END RequestId: {rid}", rep]
            for ln in lines:
                self.logs.put(group, ln)
            tail_lines = lines if not drop else lines[:-1]
            tail = ("\n".join(tail_lines) + "\n").encode()[-4096:]
            resp = {"StatusCode": 200, "Payload": _Body(json.dumps(out).encode()),
                    "LogResult": base64.b64encode(tail).decode() if LogType == "Tail" else None,
                    "ResponseMetadata": {"RequestId": rid, "HTTPHeaders": {"x-amzn-requestid": rid}}}
            if err:
                resp["FunctionError"] = err
            return resp
        finally:
            with self._lock:
                self.in_flight -= 1
                fcur = self.fns.get(FunctionName)
                if fcur is not None and fcur["gen"] == gen and "mod" in locals():
                    fcur["idle"].append(mod)                  # a retired environment is not reused


# --------------------------------------------------------------------------- step functions
class FakeStepFunctions:
    IS_FAKE = True
    def __init__(self, lam: FakeLambda):
        self.lam = lam
        self.machines: Dict[str, dict] = {}
        self.executions = 0

    def create_state_machine(self, name, definition, roleArn, type, loggingConfiguration=None, tags=None):
        if type != "EXPRESS":
            raise FakeClientError("ValidationException", "only EXPRESS is used")
        arn = f"arn:aws:states:us-east-2:000000000000:stateMachine:{name}"
        if arn in self.machines:
            raise FakeClientError("StateMachineAlreadyExists", name)
        self.machines[arn] = {"name": name, "definition": json.loads(definition), "role": roleArn,
                              "tags": {t["key"]: t["value"] for t in (tags or [])},
                              "logging": loggingConfiguration}
        return {"stateMachineArn": arn}

    def delete_state_machine(self, stateMachineArn):
        if stateMachineArn not in self.machines:
            raise FakeClientError("StateMachineDoesNotExist", stateMachineArn)
        del self.machines[stateMachineArn]

    def list_state_machines(self):
        return {"stateMachines": [{"name": m["name"], "stateMachineArn": a} for a, m in sorted(self.machines.items())]}

    def list_tags_for_resource(self, resourceArn):
        return {"tags": [{"key": k, "value": v} for k, v in self.machines[resourceArn]["tags"].items()]}

    def get_paginator(self, name):
        return _Paginator(getattr(self, name), name)

    def start_sync_execution(self, stateMachineArn, name, input):
        m = self.machines[stateMachineArn]
        d = m["definition"]
        self.executions += 1
        t0 = time.time()
        cur, data = d["StartAt"], json.loads(input)
        base = {"executionArn": f"{stateMachineArn.replace(':stateMachine:', ':express:')}:{name}:{uuid.uuid4()}",
                "stateMachineArn": stateMachineArn, "name": name, "input": input, "startDate": t0}
        while True:
            st = d["States"][cur]
            fn = st["Resource"].rsplit(":", 1)[-1]
            try:
                r = self.lam.invoke(FunctionName=fn, InvocationType="RequestResponse", Payload=json.dumps(data).encode())
            except FakeClientError as e:
                return dict(base, status="FAILED", error=f"Lambda.{e.response['Error']['Code']}", cause=str(e),
                            stopDate=time.time())
            body = json.loads(r["Payload"].read())
            if r.get("FunctionError"):
                return dict(base, status="FAILED", error=body.get("errorType", "Error"),
                            cause=json.dumps(body), stopDate=time.time())
            data = body
            if st.get("End"):
                t1 = time.time()
                return dict(base, status="SUCCEEDED", output=json.dumps(data), stopDate=t1,
                            billingDetails={"billedMemoryUsedInMB": 64,
                                            "billedDurationInMilliseconds": max(100, int(math.ceil((t1 - t0) * 1000 / 100)) * 100)})
            cur = st["Next"]


# --------------------------------------------------------------------------- iam, sts
class FakeIAM:
    IS_FAKE = True
    def __init__(self):
        self.roles: Dict[str, dict] = {}

    def create_role(self, RoleName, AssumeRolePolicyDocument, Tags=None):
        if RoleName in self.roles:
            raise FakeClientError("EntityAlreadyExists", RoleName)
        self.roles[RoleName] = {"arn": f"arn:aws:iam::000000000000:role/{RoleName}", "attached": set(),
                                "inline": {}, "trust": json.loads(AssumeRolePolicyDocument)}
        return {"Role": {"Arn": self.roles[RoleName]["arn"]}}

    def get_role(self, RoleName):
        if RoleName not in self.roles:
            raise FakeClientError("NoSuchEntity", RoleName)
        return {"Role": {"Arn": self.roles[RoleName]["arn"]}}

    def attach_role_policy(self, RoleName, PolicyArn):
        self.roles[RoleName]["attached"].add(PolicyArn)

    def detach_role_policy(self, RoleName, PolicyArn):
        if RoleName not in self.roles or PolicyArn not in self.roles[RoleName]["attached"]:
            raise FakeClientError("NoSuchEntity", RoleName)
        self.roles[RoleName]["attached"].discard(PolicyArn)

    def put_role_policy(self, RoleName, PolicyName, PolicyDocument):
        self.roles[RoleName]["inline"][PolicyName] = json.loads(PolicyDocument)

    def delete_role_policy(self, RoleName, PolicyName):
        if RoleName not in self.roles or PolicyName not in self.roles[RoleName]["inline"]:
            raise FakeClientError("NoSuchEntity", RoleName)
        del self.roles[RoleName]["inline"][PolicyName]

    def delete_role(self, RoleName):
        r = self.roles.get(RoleName)
        if r is None:
            raise FakeClientError("NoSuchEntity", RoleName)
        if r["attached"] or r["inline"]:
            raise FakeClientError("DeleteConflict", "detach and delete policies first")
        del self.roles[RoleName]


class FakeSTS:
    IS_FAKE = True
    def get_caller_identity(self):
        return {"Account": "000000000000"}


def fake_cloud(**lambda_kw) -> dict:
    logs = FakeLogs()
    lam = FakeLambda(logs=logs, **lambda_kw)
    return {"lambda": lam, "logs": logs, "iam": FakeIAM(), "sts": FakeSTS(), "stepfunctions": FakeStepFunctions(lam)}
