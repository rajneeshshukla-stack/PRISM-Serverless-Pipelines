"""Adapter between PRISM's controller and the deployed pipeline (R2.2, R2.20, R6.1).

The controller interface is the simulator's, unchanged (prism_repro.policies / closed_loop): `start(cfg, n_min,
n_epochs)` once, then `decide(k, tel) -> (P per stage, memory MB)` for epoch k, where `tel` is an EventTelemetry whose
minutes up to k*E - L are observed and later minutes are NaN. Any controller with that interface plugs in:
closed_loop.PolicyController(PRISM, bundle, ...) for PRISM itself, ScheduleController for a fixed schedule, and
PolicyOnly(OnDemand()) for the paper's on-demand baseline.

Timing (decision D05 of ASSUMPTIONS_AND_DECISIONS.md, live): decision k is taken at the end of bin kE - L, sees bins
<= kE - L, and its configuration is applied at the start of bin kE. Epoch 0 is decided and applied before the first
record. A "bin" is one minute in paper time (bin_s = 60, E = 5, L = 2); a short live test may compress time
(bin_s < 60), which keeps the decision structure but not the paper's absolute timing (decision P6).

Telemetry from the deployment: per bin and stage, arrivals (a stage execution's start time), executions served on
demand (all of them while provisioned concurrency is not applied), cold starts (handler-reported new environment),
peak executions in flight (from start/end intervals), the applied P and memory. Only records that have FINISHED by
decision time are counted (the driver learns a record's stage times when its execution returns); the decision log
records how many records that arrived in observed bins were still running, so any undercount is visible. Counts can
be multiplied by `count_scale` (1/thin for a thinned trace replay, decision P5) before the controller sees them.

Actuation:
  memory  UpdateFunctionConfiguration(MemorySize) on all four functions (PRISM chooses one size for the pipeline),
          waiting for LastUpdateStatus = Successful. A configuration change retires warm environments, so the next
          executions are cold; the actuation delay (request to Successful) is logged per change.
  P       "record" (default, the only mode possible at the applied quota of 10): the requested provisioned levels are
          logged, not applied. "apply" would call PutProvisionedConcurrencyConfig on a published version's alias; it
          is refused unless the account's unreserved concurrency minus the request leaves AWS's minimum of 100, which
          a quota of 10 never does.
"""
from __future__ import annotations

import json
import math
import threading
import time
from typing import Callable, Dict, List, Optional

import numpy as np

STAGES = ("ingest", "transform", "aggregate", "load")
UNRESERVED_MIN = 100                    # AWS keeps at least 100 unreserved concurrent executions per account


def _event_telemetry_cls():
    from prism_repro.des import EventTelemetry
    return EventTelemetry


class LiveTelemetry:
    """Builds EventTelemetry views from finished records. Times are relative to the arm's t0 (client wall clock);
    stage start/end are the handlers' wall clocks (AWS), so client-AWS clock offset (NTP-level) enters the binning."""

    def __init__(self, n_bins: int, bin_s: float, t0_wall_ns: int, count_scale: float = 1.0,
                 n_stages: int = 4):
        self.n, self.bin_s, self.t0, self.scale, self.S = n_bins, bin_s, t0_wall_ns, count_scale, n_stages
        self._lock = threading.Lock()
        self.records: List[dict] = []
        self.P = np.zeros((n_bins, n_stages))
        self.mem = np.zeros(n_bins, np.int64)

    def add(self, rec: dict) -> None:
        if rec.get("type") == "record" and rec.get("stages"):
            with self._lock:
                self.records.append(rec)

    def set_config(self, bin_from: int, P, mem: int) -> None:
        with self._lock:
            self.P[bin_from:] = np.asarray(P, float)
            self.mem[bin_from:] = int(mem)

    def _bin(self, wall_ns):
        return int(math.floor((wall_ns - self.t0) / 1e9 / self.bin_s))

    def counts(self, upto: int):
        """Per-bin arrays for bins [0, upto] from the finished records (unscaled)."""
        n, S = self.n, self.S
        arr = np.zeros((n, S)); cold = np.zeros((n, S)); comp = np.zeros((n, S))
        ivals = [[] for _ in range(S)]
        with self._lock:
            recs = list(self.records)
        for r in recs:
            for st in r["stages"]:
                if st.get("start_wall_ns") is None or st.get("stage") not in STAGES:
                    continue
                s = STAGES.index(st["stage"])
                a, f = st["start_wall_ns"], st.get("end_wall_ns") or st["start_wall_ns"]
                ba, bf = self._bin(a), self._bin(f)
                if 0 <= ba < n:
                    arr[ba, s] += 1
                    cold[ba, s] += bool(st.get("cold"))
                if 0 <= bf < n:
                    comp[bf, s] += 1
                ivals[s].append(((a - self.t0) / 1e9, (f - self.t0) / 1e9))
        K = np.zeros((n, S))
        for s in range(S):
            if not ivals[s]:
                continue
            ev = sorted([(a, 1) for a, _ in ivals[s]] + [(f, -1) for _, f in ivals[s]], key=lambda x: (x[0], -x[1]))
            lvl = 0
            for t, d in ev:
                lvl += d
                b = int(math.floor(t / self.bin_s))
                if 0 <= b < n:
                    K[b, s] = max(K[b, s], lvl)
            # carry the level into bins with no event
            lvl, j = 0, 0
            for b in range(n):
                start = b * self.bin_s
                while j < len(ev) and ev[j][0] < start:
                    lvl += ev[j][1]
                    j += 1
                K[b, s] = max(K[b, s], lvl)
        return arr, cold, comp, K

    def view(self, upto: int):
        """EventTelemetry with bins [0, upto] observed (scaled by count_scale) and later bins NaN."""
        ET = _event_telemetry_cls()
        n, S = self.n, self.S
        nan = lambda *sh: np.full(sh, np.nan)  # noqa: E731
        v = ET(N=nan(n), K=nan(n, S), P=nan(n, S), n_od=nan(n, S), cold=nan(n, S), filled=0,
               arrivals=nan(n, S), completed=nan(n, S), inflight_end=nan(n, S), mem=nan(n))
        if upto < 0:
            return v
        hi = min(upto + 1, n)
        arr, cold, comp, K = self.counts(upto)
        c = self.scale
        v.arrivals[:hi] = arr[:hi] * c
        v.N[:hi] = arr[:hi, 0] * c
        v.n_od[:hi] = (arr[:hi] - 0.0) * c            # P is never applied at quota 10: every execution is on demand
        v.cold[:hi] = cold[:hi] * c
        v.completed[:hi] = comp[:hi] * c
        v.K[:hi] = K[:hi] * c
        v.P[:hi] = self.P[:hi]
        v.mem[:hi] = self.mem[:hi]
        v.inflight_end[:hi] = np.cumsum(arr[:hi] - comp[:hi], axis=0) * c
        v.filled = hi
        return v


class PolicyOnly:
    """Runs a policy that needs no forecasts or history (OnDemand, or a fixed-memory rule) through the adapter."""

    def __init__(self, policy):
        self.policy = policy

    def start(self, cfg, n_min, n_epochs):
        from prism_repro.closed_loop import ClosedLoopContext
        self.policy.prepare(ClosedLoopContext(cfg=cfg, week_start=0, K_hist_default=np.zeros((1, cfg.n_stages)),
                                              n_epochs=n_epochs))

    def decide(self, k, tel):
        return self.policy.decide(k, tel)


class LambdaActuator:
    def __init__(self, lambda_client, functions: Dict[str, str], pc_mode: str = "record",
                 account_settings: Optional[dict] = None, sleep=time.sleep, poll_s: float = 1.0,
                 timeout_s: float = 120.0, mono=time.monotonic):
        if pc_mode not in ("record", "apply"):
            raise ValueError("pc_mode must be 'record' or 'apply'")
        self.lam, self.functions, self.pc_mode = lambda_client, functions, pc_mode
        self.account = account_settings
        self.sleep, self.poll_s, self.timeout_s, self.mono = sleep, poll_s, timeout_s, mono
        self.mem = None

    def current_memory(self) -> int:
        ms = {self.lam.get_function_configuration(FunctionName=f)["MemorySize"] for f in self.functions.values()}
        if len(ms) != 1:
            raise RuntimeError(f"stages have different memory sizes {sorted(ms)}; PRISM sets one size")
        self.mem = ms.pop()
        return self.mem

    def _wait_all(self, fns):
        """Poll every function each round until all report Successful (total wait = the slowest, not the sum)."""
        t0, pending, cfgs = self.mono(), list(fns), {}
        while pending:
            for fn in list(pending):
                c = self.lam.get_function_configuration(FunctionName=fn)
                if c.get("LastUpdateStatus") == "Failed":
                    raise RuntimeError(f"{fn}: {c.get('LastUpdateStatusReason')}")
                if c.get("LastUpdateStatus") in (None, "Successful") and c.get("State", "Active") == "Active":
                    cfgs[fn] = c
                    pending.remove(fn)
            if not pending:
                break
            if self.mono() - t0 > self.timeout_s:
                raise TimeoutError(f"{pending}: memory update not applied after {self.timeout_s} s")
            self.sleep(self.poll_s)
        return cfgs

    def apply(self, P, mem: int) -> dict:
        out = {"memory_requested": int(mem), "memory_changed": False, "memory_update_s": None,
               "pc_requested": [int(x) for x in np.ceil(np.asarray(P, float))], "pc_applied": None,
               "pc_mode": self.pc_mode}
        if self.mem is None:
            self.current_memory()
        if int(mem) != self.mem:
            t0 = self.mono()
            for fn in self.functions.values():            # sequential: every stage changes before the epoch starts
                self.lam.update_function_configuration(FunctionName=fn, MemorySize=int(mem))
            for fn, c in self._wait_all(list(self.functions.values())).items():
                if int(c.get("MemorySize", mem)) != int(mem):
                    raise RuntimeError(f"{fn}: MemorySize {c.get('MemorySize')} after update to {mem}")
            out.update(memory_changed=True, memory_update_s=self.mono() - t0, memory_from=self.mem)
            self.mem = int(mem)
        if self.pc_mode == "apply" and sum(out["pc_requested"]) > 0:
            acct = self.account or {}
            unres = acct.get("UnreservedConcurrentExecutions", 0)
            if unres - sum(out["pc_requested"]) < UNRESERVED_MIN:
                raise PermissionError(f"provisioned concurrency {sum(out['pc_requested'])} would leave "
                                      f"{unres - sum(out['pc_requested'])} unreserved (< {UNRESERVED_MIN}); "
                                      "not possible at this account's quota")
            raise NotImplementedError("pc_mode='apply' needs published versions and aliases (SPEC.md, P7)")
        return out


class ControllerAdapter:
    def __init__(self, controller, actuator, telemetry: LiveTelemetry, cfg, n_epochs: int, log_path: str,
                 pc_scale: float = 1.0, wall_ns: Callable[[], int] = time.time_ns,
                 clock_ns: Callable[[], int] = time.perf_counter_ns, sleep: Callable[[float], None] = time.sleep):
        self.ctl, self.act, self.tel, self.cfg = controller, actuator, telemetry, cfg
        self.E, self.L = cfg.epoch_min, cfg.lag_min
        self.n_epochs, self.log_path, self.pc_scale = n_epochs, log_path, pc_scale
        self.wall_ns, self.clock_ns, self.sleep = wall_ns, clock_ns, sleep
        self.decisions: List[dict] = []
        self._stop = threading.Event()
        self._thread = None
        self.error = None

    def _log(self, rec):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":"), default=float) + "\n")
        self.decisions.append(rec)

    def start(self):
        if hasattr(self.ctl, "start"):
            self.ctl.start(self.cfg, self.tel.n, self.n_epochs)

    def _decide(self, k: int) -> dict:
        v = k * self.E - self.L
        tel = self.tel.view(v)
        t0 = self.clock_ns()
        P, mem = self.ctl.decide(k, tel)
        dt = (self.clock_ns() - t0) / 1e9
        P = np.asarray(P, float)
        running = 0
        if v >= 0:
            cut = self.tel.t0 + int((v + 1) * self.tel.bin_s * 1e9)
            done = {r["record_id"] for r in self.tel.records}
            running = sum(1 for r in getattr(self, "submitted", []) if r[1] < cut and r[0] not in done)
        return {"type": "decision", "k": k, "observed_upto_bin": v, "decision_s": dt, "P_model": P.tolist(),
                "P_live": [int(math.ceil(x * self.pc_scale)) for x in P], "memory": int(mem),
                "records_running_at_decision": running, "decided_wall_ns": self.wall_ns()}

    def initial(self) -> dict:
        """Epoch 0: decided and applied before the first record."""
        d = self._decide(0)
        a = self.act.apply(d["P_live"], d["memory"])
        self.tel.set_config(0, d["P_live"], self.act.mem)
        d.update(actuation=a, applied_wall_ns=self.wall_ns(), effective_bin=0)
        self._log(d)
        return d

    def note_submitted(self, record_id: str, wall_ns: int):
        if not hasattr(self, "submitted"):
            self.submitted = []
        self.submitted.append((record_id, wall_ns))

    def run(self, t0_ns: int):
        """Epochs 1..n_epochs-1 against the driver's clock origin t0_ns (perf counter)."""
        bin_ns = int(self.tel.bin_s * 1e9)
        try:
            for k in range(1, self.n_epochs):
                due = t0_ns + (k * self.E - self.L + 1) * bin_ns
                while not self._stop.is_set():
                    w = (due - self.clock_ns()) / 1e9
                    if w <= 0:
                        break
                    self.sleep(min(w, 0.5))
                if self._stop.is_set():
                    return
                d = self._decide(k)
                act_due = t0_ns + k * self.E * bin_ns
                w = (act_due - self.clock_ns()) / 1e9
                if w > 0:
                    self.sleep(w)
                a = self.act.apply(d["P_live"], d["memory"])
                late = (self.clock_ns() - act_due) / 1e9
                self.tel.set_config(k * self.E, d["P_live"], self.act.mem)
                d.update(actuation=a, applied_wall_ns=self.wall_ns(), effective_bin=k * self.E,
                         applied_late_s=late)
                self._log(d)
        except Exception as e:                             # recorded; the arm continues on the last configuration
            self.error = f"{type(e).__name__}: {e}"
            self._log({"type": "adapter_error", "error": self.error, "wall_ns": self.wall_ns()})

    def run_in_background(self, t0_ns: int):
        self._thread = threading.Thread(target=self.run, args=(t0_ns,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()

    def join(self, timeout_s=None):
        """Let the remaining scheduled epochs run to their natural end."""
        if self._thread:
            self._thread.join(timeout_s)
        if self._thread and self._thread.is_alive():
            self.stop()
