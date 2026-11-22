"""Execute a Design against a Lambda client (the real boto3 client, or FakeLambda for dry runs).

Per visit: change the function's nonce (retiring every warm environment), wait until the update is applied, run one
cold batch whose invocations are released together through a barrier (so each gets a new environment), then the warm
batches on those environments. Every invocation is timed on the client with a monotonic clock around the whole call
including reading the response, and written to a JSONL file immediately. A `visit_done` record marks a complete visit;
on restart, completed visits are skipped and an incomplete one is rerun under a new attempt number (the analysis
uses only completed attempts), so an interrupted or suspended run loses at most one visit.

The concurrency cap is enforced twice: no batch may exceed it (design.check_cap), and a bounded semaphore limits
invocations in flight; the maximum observed in flight is recorded in the run summary.
"""
from __future__ import annotations

import json
import os
import platform
import threading
import time
import uuid
from typing import Callable, Dict, Iterable, List, Optional

from .design import CAP_MAX, Design, Visit, check_cap
from .report import parse_log_tail, parse_report_line


def fallback_reports(logs_client, records: List[dict]) -> Dict[str, dict]:
    """CloudWatch Logs lookup of the REPORT line for every invocation whose log tail had none. Works with the real
    logs client and with FakeLogs. Returns {request_id: report}."""
    out: Dict[str, dict] = {}
    for r in records:
        if r.get("type") != "invocation" or not r.get("request_id") or r.get("report"):
            continue
        t = r.get("wall_start_ns", 0) // 1_000_000
        ev = logs_client.filter_log_events(logGroupName=f"/aws/lambda/{r['function']}",
                                           filterPattern=f'"REPORT RequestId: {r["request_id"]}"',
                                           startTime=max(t - 60_000, 0), endTime=t + 900_000).get("events", [])
        for e in ev:
            rep = parse_report_line(e["message"])
            if rep and rep["request_id"] == r["request_id"]:
                out[rep["request_id"]] = rep
    return out


class Runner:
    def __init__(self, client, envs: Dict[str, Dict[str, str]], out_path: str, cap: int = CAP_MAX,
                 clock_ns: Callable[[], int] = time.perf_counter_ns, wall_ns: Callable[[], int] = time.time_ns,
                 sleep: Callable[[float], None] = time.sleep, update_timeout_s: float = 300.0, poll_s: float = 1.0,
                 run_id: Optional[str] = None, payload: Optional[dict] = None,
                 payloads: Optional[Dict[str, dict]] = None, normalise: Optional[Callable[[dict], dict]] = None,
                 meta: Optional[dict] = None, tail_hook: Optional[Callable[[Optional[str]], Optional[dict]]] = None):
        """payloads: optional per-function request bodies (default: `payload` for every function). normalise:
        optional map applied to a dict response before it is stored (e.g. to keep only a stage's trace entry).
        meta: extra fields for the run_meta record. tail_hook: optional extractor of extra fields from the base64 log
        tail, stored as `tail_extra`. All four default to the original behaviour."""
        check_cap(cap)
        self.client, self.envs, self.out_path, self.cap = client, envs, out_path, cap
        self.clock_ns, self.wall_ns, self.sleep = clock_ns, wall_ns, sleep
        self.update_timeout_s, self.poll_s = update_timeout_s, poll_s
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.payload = json.dumps(payload or {}).encode()
        self.payloads = {fn: json.dumps(p).encode() for fn, p in (payloads or {}).items()}
        self.normalise = normalise
        self.meta = dict(meta or {})
        self.tail_hook = tail_hook
        self._sem = threading.BoundedSemaphore(cap)
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0
        self._fh = None

    # ------------------------------------------------------------------ output
    def _write(self, rec: dict) -> None:
        with self._lock:
            self._fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            self._fh.flush()

    def _completed(self) -> Dict[str, int]:
        done, attempts = set(), {}
        if os.path.exists(self.out_path):
            with open(self.out_path, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    if r.get("type") == "visit_done":
                        done.add(r["visit_id"])
                    if "visit_id" in r:
                        attempts[r["visit_id"]] = max(attempts.get(r["visit_id"], 0), r.get("attempt", 0))
        return {"done": done, "attempts": attempts}

    # ------------------------------------------------------------------ AWS actions
    def _force_cold(self, fn: str) -> tuple:
        nonce = uuid.uuid4().hex[:16]
        env = dict(self.envs[fn], PRISM_COLD_NONCE=nonce)       # Environment replaces all variables: send them all
        t0 = time.monotonic()
        self.client.update_function_configuration(FunctionName=fn, Environment={"Variables": env})
        while True:
            cfg = self.client.get_function_configuration(FunctionName=fn)
            if cfg.get("LastUpdateStatus") == "Successful" and cfg.get("State", "Active") == "Active":
                break
            if cfg.get("LastUpdateStatus") == "Failed":
                raise RuntimeError(f"{fn}: configuration update failed: {cfg.get('LastUpdateStatusReason')}")
            if time.monotonic() - t0 > self.update_timeout_s:
                raise TimeoutError(f"{fn}: configuration update not applied after {self.update_timeout_s} s")
            self.sleep(self.poll_s)
        return nonce, time.monotonic() - t0

    def _invoke_one(self, fn: str, barrier: Optional[threading.Barrier], base: dict, out: List[dict]) -> None:
        if barrier is not None:
            barrier.wait()
        with self._sem:
            with self._lock:
                self._in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self._in_flight)
            rec = dict(base, wall_start_ns=self.wall_ns())
            t0 = self.clock_ns()
            try:
                resp = self.client.invoke(FunctionName=fn, InvocationType="RequestResponse", LogType="Tail",
                                          Payload=self.payloads.get(fn, self.payload))
                body = resp["Payload"].read()
                t1 = self.clock_ns()
                meta = resp.get("ResponseMetadata", {})
                rid = meta.get("RequestId") or meta.get("HTTPHeaders", {}).get("x-amzn-requestid")
                try:
                    payload = json.loads(body) if body else None
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and self.normalise is not None:
                    payload = self.normalise(payload)
                rep = parse_log_tail(resp.get("LogResult"))
                rec.update(t0_ns=t0, t1_ns=t1, e2e_s=(t1 - t0) / 1e9, status_code=resp.get("StatusCode"),
                           function_error=resp.get("FunctionError"), error=None, request_id=rid,
                           report=rep, report_source="tail" if rep else None,
                           payload=payload if isinstance(payload, dict) else None)
                if self.tail_hook is not None:
                    extra = self.tail_hook(resp.get("LogResult"))
                    if extra:
                        rec["tail_extra"] = extra
            except Exception as e:                           # throttling, timeouts: recorded, never retried
                t1 = self.clock_ns()
                rec.update(t0_ns=t0, t1_ns=t1, e2e_s=(t1 - t0) / 1e9, status_code=None, function_error=None,
                           error=f"{type(e).__name__}: {e}"[:300], request_id=None, report=None,
                           report_source=None, payload=None)
            finally:
                with self._lock:
                    self._in_flight -= 1
            out.append(rec)

    def _batch(self, visit: Visit, kind: str, n: int, batch_id: str, base: dict) -> None:
        if not 1 <= n <= self.cap:
            raise ValueError(f"batch of {n} outside 1..cap {self.cap}")
        out: List[dict] = []
        barrier = threading.Barrier(n) if n > 1 else None
        threads = [threading.Thread(target=self._invoke_one,
                                    args=(visit.cell.function, barrier, dict(base, batch_id=batch_id, batch_kind=kind,
                                                                             slot=i), out)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for rec in sorted(out, key=lambda r: r["slot"]):
            self._write(rec)

    # ------------------------------------------------------------------ main loop
    def run(self, design: Design, blocks: Optional[Iterable[int]] = None, host_note: str = "") -> dict:
        if design.batch > self.cap:
            raise ValueError(f"design batch {design.batch} exceeds runner cap {self.cap}")
        state = self._completed()
        blocks = set(range(design.blocks)) if blocks is None else set(blocks)
        self._fh = open(self.out_path, "a", encoding="utf-8")
        try:
            self._write({"type": "run_meta", "run_id": self.run_id, "cap": self.cap, "seed": design.seed,
                         "batch": design.batch, "blocks": sorted(blocks), "wall_ns": self.wall_ns(),
                         "host": platform.platform(), "python": platform.python_version(), "host_note": host_note,
                         **self.meta})
            n_visits = 0
            for v in design.visits:
                if v.block not in blocks:
                    continue
                vid = f"b{v.block}-o{v.order}"
                if vid in state["done"]:
                    continue
                attempt = state["attempts"].get(vid, -1) + 1
                w0 = self.wall_ns()
                nonce, wait_s = self._force_cold(v.cell.function)
                base = {"type": "invocation", "run_id": self.run_id, "visit_id": vid, "attempt": attempt,
                        "block": v.block, "order": v.order, "function": v.cell.function, "group": v.cell.group,
                        "variant": v.cell.variant, "memory_mb": v.cell.memory_mb, "nonce": nonce}
                self._batch(v, "cold", v.cold, f"{vid}-a{attempt}-cold", base)
                for j, n in enumerate(v.warm_batches):
                    self._batch(v, "warm", n, f"{vid}-a{attempt}-warm{j}", base)
                self._write({"type": "visit_done", "run_id": self.run_id, "visit_id": vid, "attempt": attempt,
                             "update_wait_s": wait_s, "wall_start_ns": w0, "wall_end_ns": self.wall_ns()})
                n_visits += 1
            summary = {"type": "run_summary", "run_id": self.run_id, "visits_run": n_visits,
                       "max_in_flight": self.max_in_flight, "cap": self.cap, "wall_ns": self.wall_ns()}
            self._write(summary)
            return summary
        finally:
            self._fh.close()
            self._fh = None
