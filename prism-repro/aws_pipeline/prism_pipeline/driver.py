"""Run a record stream through the deployed pipeline (or a fake) and log every record as it finishes.

Executors
  SfnExecutor    the deployment path: one synchronous Express execution per record (StartSyncExecution). Per-stage
                 Lambda request IDs, environment IDs, cold flags and wall-clock times come back in the output's
                 `trace`; Lambda's REPORT lines (Duration, Billed Duration, Init Duration) are joined afterwards from
                 CloudWatch by request ID (collect step).
  ChainExecutor  the client invokes the four functions in turn (RequestResponse, LogType=Tail). Used for calibration
                 and as an orchestration-free reference: the REPORT line comes back with each call.
Driver
  Open loop: record i is submitted at t0 + offset_i whatever the state of earlier records (arrivals do not wait for
  completions, as in the simulator). A client-side cap bounds the records in flight; because stages run one after
  another, a record in flight occupies at most one Lambda execution, so the cap bounds Lambda concurrency too
  (8 = quota 10 minus headroom 2, as in the measurement harness). A record arriving when the cap is reached is not
  run: it is logged as `shed_client_cap` and counted separately from deadline misses (the design keeps shedding
  rare). Nothing is retried.
Each record line holds: arm, record_id (shared across arms), pipeline_request_id (unique per execution), execution
ARN, scheduled/submitted/finished wall times, client end-to-end seconds, deadline, met/missed, status, error, and
per stage the Lambda request ID, function, memory, environment ID, cold flag, module init time, start/end wall
times, handler seconds and (chain mode) the REPORT fields.
"""
from __future__ import annotations

import json
import platform
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional, Sequence

from .workload import DEADLINE_S, Record, envelope

CAP_MAX = 8
STAGES = ("ingest", "transform", "aggregate", "load")


def _report_from_tail(log_result):
    from prism_measure.report import parse_log_tail     # reused from the measurement harness
    return parse_log_tail(log_result)


class ChainExecutor:
    mode = "chain"

    def __init__(self, lambda_client, functions: Dict[str, str], clock_ns=time.perf_counter_ns):
        self.lam, self.functions, self.clock_ns = lambda_client, functions, clock_ns

    def run(self, env: dict) -> dict:
        stages, cur = [], env
        for s in STAGES:
            fn = self.functions[s]
            t0 = self.clock_ns()
            try:
                resp = self.lam.invoke(FunctionName=fn, InvocationType="RequestResponse", LogType="Tail",
                                       Payload=json.dumps(cur).encode())
                body = resp["Payload"].read()
            except Exception as e:                       # throttling, timeouts: recorded, never retried
                stages.append({"stage": s, "function": fn, "client_s": (self.clock_ns() - t0) / 1e9,
                               "error": f"{type(e).__name__}: {e}"[:300]})
                return {"status": "FAILED", "error": f"{s}: {type(e).__name__}", "stages_client": stages}
            t1 = self.clock_ns()
            meta = resp.get("ResponseMetadata", {})
            rid = meta.get("RequestId") or meta.get("HTTPHeaders", {}).get("x-amzn-requestid")
            rep = _report_from_tail(resp.get("LogResult"))
            stages.append({"stage": s, "function": fn, "request_id": rid, "client_s": (t1 - t0) / 1e9,
                           "report": rep, "report_source": "tail" if rep else None,
                           "function_error": resp.get("FunctionError")})
            try:
                out = json.loads(body) if body else None
            except ValueError:
                out = None
            if resp.get("FunctionError") or not isinstance(out, dict):
                msg = (out or {}).get("errorMessage") if isinstance(out, dict) else None
                return {"status": "FAILED", "error": f"{s}: {resp.get('FunctionError')}: {msg}"[:300],
                        "stages_client": stages}
            cur = out
        return {"status": "SUCCEEDED", "output": cur, "stages_client": stages}


class SfnExecutor:
    mode = "sfn"

    def __init__(self, sfn_client, state_machine_arn: str):
        self.sfn, self.arn = sfn_client, state_machine_arn

    def run(self, env: dict) -> dict:
        try:
            r = self.sfn.start_sync_execution(stateMachineArn=self.arn, name=env["pipeline_request_id"][:80],
                                              input=json.dumps(env))
        except Exception as e:
            return {"status": "FAILED", "error": f"start_sync_execution: {type(e).__name__}: {e}"[:300]}
        out = None
        if r.get("output"):
            try:
                out = json.loads(r["output"])
            except ValueError:
                out = None
        res = {"status": r.get("status"), "execution_arn": r.get("executionArn"), "output": out,
               "billing": r.get("billingDetails"), "error": None}
        if r.get("status") != "SUCCEEDED":
            res["error"] = f"{r.get('error')}: {r.get('cause')}"[:300]
        return res


def stage_rows(result: dict) -> List[dict]:
    """Per-stage rows: the handler's trace entries, with the client-side fields of chain mode merged in."""
    trace = ((result.get("output") or {}).get("trace")) or []
    client = {c["stage"]: c for c in result.get("stages_client") or []}
    rows = []
    for t in trace:
        row = {k: t.get(k) for k in ("stage", "aws_request_id", "function", "function_version", "memory_mb",
                                       "env_id", "cold", "module_init_s", "env_start_wall_ns", "start_wall_ns",
                                       "end_wall_ns", "handler_s", "k", "init_rows", "in_bytes", "out_bytes",
                                       "nonce", "init_type")}
        c = client.get(t.get("stage"))
        if c:
            row.update(client_s=c.get("client_s"), report=c.get("report"), report_source=c.get("report_source"),
                       request_id_header=c.get("request_id"))
        rows.append(row)
    for s, c in client.items():                         # a failed stage has no trace entry
        if not any(r["stage"] == s for r in rows):
            rows.append({"stage": s, "function": c.get("function"), "aws_request_id": c.get("request_id"),
                         "client_s": c.get("client_s"), "report": c.get("report"), "error": c.get("error")})
    return rows


class Driver:
    def __init__(self, executor, out_path: str, arm: str, cap: int = CAP_MAX, deadline_s: float = DEADLINE_S,
                 clock_ns: Callable[[], int] = time.perf_counter_ns, wall_ns: Callable[[], int] = time.time_ns,
                 sleep: Callable[[float], None] = time.sleep, on_result: Optional[Callable[[dict], None]] = None,
                 on_submit: Optional[Callable[[str, int], None]] = None, run_id: Optional[str] = None):
        if not 1 <= cap <= CAP_MAX:
            raise ValueError(f"cap must be in 1..{CAP_MAX} (quota 10, headroom 2)")
        self.ex, self.out_path, self.arm, self.cap, self.deadline = executor, out_path, arm, cap, deadline_s
        self.clock_ns, self.wall_ns, self.sleep, self.on_result = clock_ns, wall_ns, sleep, on_result
        self.on_submit = on_submit
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0
        self.results: List[dict] = []
        self._fh = None
        self.t0_ns = self.t0_wall_ns = None

    def _write(self, rec: dict) -> None:
        with self._lock:
            self._fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            self._fh.flush()

    def _one(self, rec: Record, base: dict) -> None:
        pid = base["pipeline_request_id"]
        env = envelope(rec, self.arm, pid, self.deadline)
        t0 = self.clock_ns()
        sub = self.wall_ns()
        if self.on_submit:
            self.on_submit(rec.record_id, sub)
        try:
            res = self.ex.run(env)
        except Exception as e:                           # an executor bug must not kill the arm silently
            res = {"status": "FAILED", "error": f"executor: {type(e).__name__}: {e}"[:300]}
        t1 = self.clock_ns()
        e2e = (t1 - t0) / 1e9
        ok = res.get("status") == "SUCCEEDED"
        line = dict(base, submit_wall_ns=sub, done_wall_ns=self.wall_ns(), submit_rel_s=(t0 - self.t0_ns) / 1e9,
                    e2e_s=e2e, status=res.get("status"), error=res.get("error"),
                    execution_arn=res.get("execution_arn"), billing=res.get("billing"),
                    met=bool(ok and e2e <= self.deadline), outcome=("met" if ok and e2e <= self.deadline else
                                                                    "missed" if ok else "failed"),
                    stages=stage_rows(res))
        out = res.get("output") or {}
        line["result"] = {k: out.get(k) for k in ("ingest", "transform", "aggregate", "load")} if ok else None
        with self._lock:
            self._in_flight -= 1
            self.results.append(line)
        self._write(line)
        if self.on_result:
            self.on_result(line)

    def run(self, records: Sequence[Record], host_note: str = "", t0_ns: Optional[int] = None) -> dict:
        self._fh = open(self.out_path, "a", encoding="utf-8")
        threads = []
        try:
            self.t0_ns = t0_ns if t0_ns is not None else self.clock_ns()
            self.t0_wall_ns = self.wall_ns()
            self._write({"type": "arm_meta", "run_id": self.run_id, "arm": self.arm, "executor": self.ex.mode,
                         "cap": self.cap, "deadline_s": self.deadline, "n_records": len(records),
                         "t0_wall_ns": self.t0_wall_ns, "host": platform.platform(),
                         "python": platform.python_version(), "host_note": host_note})
            shed = 0
            for rec in sorted(records, key=lambda r: r.offset_s):
                due = self.t0_ns + int(rec.offset_s * 1e9)
                wait = (due - self.clock_ns()) / 1e9
                if wait > 0:
                    self.sleep(wait)
                base = {"type": "record", "run_id": self.run_id, "arm": self.arm, "record_id": rec.record_id,
                        "pipeline_request_id": f"{self.arm}-{uuid.uuid4().hex}", "n_words": rec.n_words,
                        "offset_s": rec.offset_s, "deadline_s": self.deadline, "executor": self.ex.mode,
                        "late_dispatch_s": max((self.clock_ns() - due) / 1e9, 0.0)}
                with self._lock:
                    full = self._in_flight >= self.cap
                    if not full:
                        self._in_flight += 1
                        self.max_in_flight = max(self.max_in_flight, self._in_flight)
                if full:
                    shed += 1
                    line = dict(base, status="NOT_RUN", outcome="shed_client_cap", met=False, e2e_s=None,
                                submit_rel_s=(self.clock_ns() - self.t0_ns) / 1e9, stages=[])
                    with self._lock:
                        self.results.append(line)
                    self._write(line)
                    if self.on_result:
                        self.on_result(line)
                    continue
                t = threading.Thread(target=self._one, args=(rec, base), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
            res = self.results
            summary = {"type": "arm_summary", "run_id": self.run_id, "arm": self.arm,
                       "n": len(res), "met": sum(r["outcome"] == "met" for r in res),
                       "missed": sum(r["outcome"] == "missed" for r in res),
                       "failed": sum(r["outcome"] == "failed" for r in res), "shed_client_cap": shed,
                       "max_in_flight": self.max_in_flight, "cap": self.cap,
                       "elapsed_s": (self.clock_ns() - self.t0_ns) / 1e9}
            self._write(summary)
            return summary
        finally:
            self._fh.close()
            self._fh = None
