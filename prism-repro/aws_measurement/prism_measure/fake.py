"""In-process fake of the Lambda and CloudWatch Logs calls the harness makes. NO NETWORK, NO AWS.

It models what the analysis must handle: execution environments reused while warm and retired by a configuration
change; a cold start adding environment creation (not reported by Lambda) plus the reported INIT phase; first-call
work inside the handler; an account-level concurrency limit that throttles above `account_limit`; and injectable
faults (REPORT missing from the log tail, Init Duration missing on a cold REPORT). The ground truth is known, so tests
can check that the analysis recovers it. Simulated times are multiplied by `time_scale`, both in the reported fields
and in real sleeps (time_scale = 0 runs instantly; > 0 makes invocations overlap so the concurrency cap is exercised).
"""
from __future__ import annotations

import base64
import io
import json
import math
import random
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from .report import format_report_line


class FakeThrottle(Exception):
    """Stands in for TooManyRequestsException."""


@dataclass
class Truth:
    """Seconds at 1024 MB unless noted. CPU work speeds up in proportion to memory (rate * m / 1024)."""
    rate_1024: float = 1_000_000.0      # SHA-256 iterations per second at 1024 MB
    create_s: float = 0.25              # environment creation before INIT (not reported by Lambda): R
    runtime_init_s: float = 0.15        # empty-handler INIT phase, independent of memory
    network_s: float = 0.02             # client round trip, every invocation

    def rate(self, m: int) -> float:
        return self.rate_1024 * m / 1024.0

    def init_s(self, m: int, init_units: int) -> float:
        return self.runtime_init_s + init_units / self.rate(m)

    def first_call_s(self, m: int, first_units: int) -> float:
        return first_units / self.rate(m)

    def work_s(self, m: int, units: int) -> float:
        return units / self.rate(m)


class _Body(io.BytesIO):
    pass


class FakeLogs:
    def __init__(self):
        self._lines: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def put(self, fn: str, line: str) -> None:
        with self._lock:
            self._lines.setdefault(f"/aws/lambda/{fn}", []).append(line)

    def filter_log_events(self, logGroupName: str, filterPattern: str = "", **_):
        needle = filterPattern.strip('"')
        with self._lock:
            ev = [{"message": m, "timestamp": 0} for m in self._lines.get(logGroupName, []) if needle in m]
        return {"events": ev}


class FakeLambda:
    def __init__(self, functions: Dict[str, Dict], truth: Optional[Truth] = None, time_scale: float = 0.0,
                 seed: int = 1, p_drop_tail_report: float = 0.0, p_missing_init: float = 0.0,
                 account_limit: int = 10, sleep=None):
        """functions: name -> {"memory_mb": int, "env": {..}}"""
        import time as _time
        self.truth = truth or Truth()
        self.time_scale = time_scale
        self.rng = random.Random(seed)
        self.p_drop, self.p_noinit = p_drop_tail_report, p_missing_init
        self.account_limit = account_limit
        self.sleep = sleep or _time.sleep
        self.logs = FakeLogs()
        self._lock = threading.Lock()
        self._fn = {k: {"memory_mb": int(v["memory_mb"]), "env": dict(v["env"]), "gen": 0, "idle": []}
                    for k, v in functions.items()}
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0
        self.throttles = 0
        self.updates = 0
        self.network_calls = 0          # stays 0: nothing here touches a socket

    # ---- configuration
    def update_function_configuration(self, FunctionName: str, Environment: Dict) -> Dict:
        with self._lock:
            f = self._fn[FunctionName]
            f["env"] = dict(Environment["Variables"])
            f["gen"] += 1
            f["idle"] = []              # every warm environment is retired
            self.updates += 1
        return {"LastUpdateStatus": "InProgress"}

    def get_function_configuration(self, FunctionName: str) -> Dict:
        f = self._fn[FunctionName]
        return {"LastUpdateStatus": "Successful", "State": "Active", "MemorySize": f["memory_mb"],
                "Environment": {"Variables": dict(f["env"])}}

    # ---- invocation
    def invoke(self, FunctionName: str, InvocationType: str = "RequestResponse", LogType: str = "Tail",
               Payload: bytes = b"{}") -> Dict:
        ev = json.loads(Payload or b"{}")
        with self._lock:
            self.calls += 1
            if self.in_flight + 1 > self.account_limit:
                self.throttles += 1
                raise FakeThrottle(f"Rate Exceeded: account concurrency {self.account_limit}")
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            f = self._fn[FunctionName]
            gen, m, env = f["gen"], f["memory_mb"], dict(f["env"])
            cold = not f["idle"]
            env_id = uuid.UUID(int=self.rng.getrandbits(128)).hex if cold else f["idle"].pop()
            rid = str(uuid.UUID(int=self.rng.getrandbits(128)))
            drop = self.rng.random() < self.p_drop
            noinit = self.rng.random() < self.p_noinit
        t = self.truth
        init_units = int(env.get("PRISM_INIT_UNITS", 0))
        first_units = int(env.get("PRISM_FIRST_CALL_UNITS", 0)) if cold else 0
        units = int(ev.get("work_units", env.get("PRISM_WORK_UNITS", 0)))
        init = t.init_s(m, init_units) if cold else 0.0
        first = t.first_call_s(m, first_units)
        work = t.work_s(m, units)
        create = t.create_s if cold else 0.0
        duration = first + work
        e2e = t.network_s + create + init + duration
        k = self.time_scale
        if k > 0:
            self.sleep(e2e * k)
        dur_ms = duration * k * 1000
        line = format_report_line(rid, dur_ms, math.ceil(dur_ms), m, 40,
                                  init * k * 1000 if cold and not noinit else None)
        self.logs.put(FunctionName, line)
        tail = f"START RequestId: {rid} Version: $LATEST\nEND RequestId: {rid}\n" + ("" if drop else line + "\n")
        payload = {"label": "PROXY WORKLOAD (fake)", "stage": env.get("PRISM_STAGE"), "env_id": env_id,
                   "first_call": cold, "module_init_s": (init_units / t.rate(m)) * k,
                   "first_call_work_s": first * k, "work_s": work * k, "work_units": units,
                   "nonce": env.get("PRISM_COLD_NONCE", ""), "aws_request_id": rid}
        with self._lock:
            self.in_flight -= 1
            if f["gen"] == gen:          # an environment retired by a config change is not reused
                f["idle"].append(env_id)
        return {"StatusCode": 200, "Payload": _Body(json.dumps(payload).encode()),
                "LogResult": base64.b64encode(tail.encode()).decode(),
                "ResponseMetadata": {"RequestId": rid, "HTTPHeaders": {"x-amzn-requestid": rid}}}

    # ---- expected values for tests (unscaled seconds)
    def expected(self, fn: str) -> Dict[str, float]:
        f, t = self._fn[fn], self.truth
        m, env = f["memory_mb"], f["env"]
        return {"I": t.init_s(m, int(env.get("PRISM_INIT_UNITS", 0))),
                "X": t.first_call_s(m, int(env.get("PRISM_FIRST_CALL_UNITS", 0))),
                "R": t.create_s,
                "P": t.create_s + t.init_s(m, int(env.get("PRISM_INIT_UNITS", 0)))
                     + t.first_call_s(m, int(env.get("PRISM_FIRST_CALL_UNITS", 0)))}
