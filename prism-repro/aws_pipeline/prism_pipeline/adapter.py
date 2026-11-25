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
        arr = np.zeros((n, S)); cold = np.zeros((n, S)); comp = np.zeros((n, S)); od = np.zeros((n, S))
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
                    # an environment initialised for provisioned concurrency did its INIT at allocation, not on this
                    # request: neither on demand nor a request-path cold start (handler trace field init_type)
                    pcenv = st.get("init_type") == "provisioned-concurrency"
                    od[ba, s] += not pcenv
                    cold[ba, s] += bool(st.get("cold")) and not pcenv
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
        self._od = od
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
        v.n_od[:hi] = self._od[:hi] * c               # executions not served by a provisioned environment
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


def _err_code(e) -> str:
    r = getattr(e, "response", None)
    return (r or {}).get("Error", {}).get("Code", type(e).__name__) if isinstance(r, dict) else type(e).__name__


def publish_alias(lam, functions: Dict[str, str], alias: str, sleep=time.sleep, poll_s: float = 1.0) -> Dict[str, str]:
    """Publish $LATEST of every stage as a new version and point `alias` at it (created on first use). Provisioned
    concurrency cannot be configured on $LATEST, only on a published version or an alias (provisioned-concurrency.html),
    so in pc_mode='apply' every configuration change (memory, environment, cold-start nonce) is published this way and
    the state machine invokes the alias. Returns {function: version}. The alias must carry no provisioned concurrency
    when it is repointed: callers delete it first (LambdaActuator.clear_pc), so no reallocation behaviour is assumed."""
    out = {}
    for fn in functions.values():
        v = lam.publish_version(FunctionName=fn)["Version"]
        try:
            lam.update_alias(FunctionName=fn, Name=alias, FunctionVersion=v)
        except Exception as e:                                # noqa: BLE001
            if _err_code(e) != "ResourceNotFoundException":
                raise
            lam.create_alias(FunctionName=fn, Name=alias, FunctionVersion=v)
        out[fn] = v
    return out


class LambdaActuator:
    """Applies one epoch's decision. Output keeps what was requested apart from what was confirmed:
    memory_requested / memory_applied (read back from every stage; through the alias in 'apply' mode);
    pc_requested (the controller's live P, after an optional cap: pc_clipped) / pc_submitted (sent to
    PutProvisionedConcurrencyConfig, None = unchanged) / pc_accepted (the API accepted the request) / pc_refused
    (stage -> reason: quota pre-check or the API's error code) / pc_status_after (GetProvisionedConcurrencyConfig right
    after). A configuration request is never reported as readiness: pc_applied stays None here, and readiness (READY,
    available >= requested) is observed only by poll_pc / PcMonitor, which time-stamp it.
    pc_mode='record' (default): P is recorded, never sent (pc_status 'recorded_not_applied').
    pc_mode='apply': needs `alias` (published versions); refused actions are recorded and the arm continues."""

    def __init__(self, lambda_client, functions: Dict[str, str], pc_mode: str = "record",
                 account_settings: Optional[dict] = None, sleep=time.sleep, poll_s: float = 1.0,
                 timeout_s: float = 120.0, mono=time.monotonic, alias: Optional[str] = None,
                 pc_cap_per_stage: Optional[int] = None):
        if pc_mode not in ("record", "apply"):
            raise ValueError("pc_mode must be 'record' or 'apply'")
        if pc_mode == "apply" and not alias:
            raise ValueError("pc_mode='apply' needs an alias: provisioned concurrency cannot be set on $LATEST")
        self.lam, self.functions, self.pc_mode, self.alias = lambda_client, functions, pc_mode, alias
        self.account = account_settings
        self.sleep, self.poll_s, self.timeout_s, self.mono = sleep, poll_s, timeout_s, mono
        self.pc_cap = pc_cap_per_stage
        self.mem = None
        self.pc_cur = [0] * len(functions)                    # provisioned concurrency currently configured (accepted)

    def current_memory(self) -> int:
        q = {"Qualifier": self.alias} if self.alias else {}
        ms = {self.lam.get_function_configuration(FunctionName=f, **q)["MemorySize"] for f in self.functions.values()}
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

    def _unreserved(self) -> int:
        if self.account is None:
            self.account = self.lam.get_account_settings()["AccountLimit"]
        return int(self.account.get("UnreservedConcurrentExecutions", 0))

    def clear_pc(self) -> Dict[str, str]:
        """Delete every provisioned-concurrency configuration on the alias (before repointing it or at an arm reset)."""
        out = {}
        if not self.alias:
            return out
        for i, fn in enumerate(self.functions.values()):
            try:
                self.lam.delete_provisioned_concurrency_config(FunctionName=fn, Qualifier=self.alias)
                out[fn] = "deleted"
            except Exception as e:                            # noqa: BLE001
                if _err_code(e) not in ("ProvisionedConcurrencyConfigNotFoundException", "ResourceNotFoundException"):
                    raise
                out[fn] = "none"
            self.pc_cur[i] = 0
        return out

    def poll_pc(self) -> List[dict]:
        """One read of every stage's provisioned-concurrency state on the alias (read only)."""
        rows = []
        for i, (s, fn) in enumerate(self.functions.items()):
            if not self.alias:
                break
            try:
                c = self.lam.get_provisioned_concurrency_config(FunctionName=fn, Qualifier=self.alias)
                rows.append({"stage": s, "configured": self.pc_cur[i], "status": c.get("Status"),
                             "requested": c.get("RequestedProvisionedConcurrentExecutions"),
                             "allocated": c.get("AllocatedProvisionedConcurrentExecutions"),
                             "available": c.get("AvailableProvisionedConcurrentExecutions"),
                             "reason": c.get("StatusReason")})
            except Exception as e:                            # noqa: BLE001
                code = _err_code(e)
                if code not in ("ProvisionedConcurrencyConfigNotFoundException", "ResourceNotFoundException"):
                    raise
                rows.append({"stage": s, "configured": self.pc_cur[i], "status": "NONE", "requested": 0,
                             "allocated": 0, "available": 0, "reason": None})
        return rows

    def apply(self, P, mem: int) -> dict:
        pc_req = [int(x) for x in np.ceil(np.asarray(P, float))]
        clipped = None
        if self.pc_cap is not None and any(x > self.pc_cap for x in pc_req):
            clipped = list(pc_req)
            pc_req = [min(x, self.pc_cap) for x in pc_req]
        out = {"memory_requested": int(mem), "memory_applied": None, "memory_changed": False, "memory_update_s": None,
               "pc_requested": pc_req, "pc_clipped_from": clipped, "pc_applied": None, "pc_mode": self.pc_mode,
               "pc_submitted": None, "pc_accepted": None, "pc_refused": {}, "pc_status_after": None,
               "pc_status": "none_requested" if sum(pc_req) == 0 else "recorded_not_applied"}
        if self.mem is None:
            self.current_memory()
        if int(mem) != self.mem:
            t0 = self.mono()
            for fn in self.functions.values():            # sequential: every stage changes before the epoch starts
                self.lam.update_function_configuration(FunctionName=fn, MemorySize=int(mem))
            for fn, c in self._wait_all(list(self.functions.values())).items():
                if int(c.get("MemorySize", mem)) != int(mem):
                    raise RuntimeError(f"{fn}: MemorySize {c.get('MemorySize')} after update to {mem}")
            if self.alias:                                # the alias serves a published version: republish
                out["pc_cleared_for_memory_change"] = self.clear_pc()
                out["published_versions"] = publish_alias(self.lam, self.functions, self.alias, sleep=self.sleep,
                                                          poll_s=self.poll_s)
                for fn in self.functions.values():
                    got = int(self.lam.get_function_configuration(FunctionName=fn, Qualifier=self.alias)["MemorySize"])
                    if got != int(mem):
                        raise RuntimeError(f"{fn}:{self.alias}: MemorySize {got} after publishing {mem}")
            out.update(memory_changed=True, memory_update_s=self.mono() - t0, memory_from=self.mem)
            self.mem = int(mem)
        out["memory_applied"] = int(self.mem)          # confirmed: unchanged, or every stage reported the new size
        if self.pc_mode != "apply":
            return out
        if pc_req == self.pc_cur:
            out["pc_status"] = "unchanged" if sum(pc_req) else "none_requested"
            return out
        unres = self._unreserved()
        if sum(pc_req) > unres - UNRESERVED_MIN:
            out["pc_status"] = "refused_quota"
            out["pc_refused"] = {"all": f"total {sum(pc_req)} > unreserved {unres} - {UNRESERVED_MIN} (pre-check; "
                                        "nothing sent, the previous configuration stays)"}
            return out
        sub, acc = [None] * len(pc_req), [None] * len(pc_req)
        for i, (s, fn) in enumerate(self.functions.items()):
            if pc_req[i] == self.pc_cur[i]:
                continue
            sub[i] = pc_req[i]
            try:
                if pc_req[i] > 0:
                    self.lam.put_provisioned_concurrency_config(FunctionName=fn, Qualifier=self.alias,
                                                                ProvisionedConcurrentExecutions=pc_req[i])
                else:
                    self.lam.delete_provisioned_concurrency_config(FunctionName=fn, Qualifier=self.alias)
                acc[i] = True
                self.pc_cur[i] = pc_req[i]
            except Exception as e:                            # noqa: BLE001  (refused: recorded, arm continues)
                acc[i] = False
                out["pc_refused"][s] = f"{_err_code(e)}: {e}"
        out.update(pc_submitted=sub, pc_accepted=acc, pc_configured=list(self.pc_cur), pc_status_after=self.poll_pc())
        out["pc_status"] = ("requested_pending_readiness" if not out["pc_refused"] else
                            "partially_refused" if any(acc) else "refused")
        return out


class PcMonitor:
    """Background reader of provisioned-concurrency readiness (apply mode): one poll_pc() every period_s, appended to
    pc_status.jsonl with a wall-clock time stamp. Activation lag is computed from these rows (pc_readiness)."""

    def __init__(self, actuator: LambdaActuator, path: str, period_s: float = 10.0, wall_ns=time.time_ns,
                 sleep=time.sleep):
        self.act, self.path, self.period_s, self.wall_ns, self.sleep = actuator, path, period_s, wall_ns, sleep
        self._stop = threading.Event()
        self._thread = None
        self.error = None

    def poll_once(self):
        rows = self.act.poll_pc()
        t = self.wall_ns()
        with open(self.path, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(dict(r, wall_ns=t), separators=(",", ":")) + "\n")
        return rows

    def _run(self):
        try:
            while not self._stop.is_set():
                self.poll_once()
                self._stop.wait(self.period_s)
        except Exception as e:                                # noqa: BLE001  (recorded)
            self.error = f"{type(e).__name__}: {e}"

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.poll_once()                                      # a final reading at the arm's end


def pc_readiness(decisions: List[dict], status_rows: List[dict], stages) -> List[dict]:
    """Per accepted provisioned-concurrency request: the first later poll showing READY with available >= requested
    (activation lag = that poll's time - the request's applied_wall_ns, resolution = the polling period), or
    'not ready by arm end'. Readiness is observed, never inferred from the request."""
    out = []
    for d in decisions:
        a = d.get("actuation") or {}
        for i, s in enumerate(stages):
            if not (a.get("pc_accepted") or [None] * len(stages))[i] or not a["pc_submitted"][i]:
                continue
            n, t_req = a["pc_submitted"][i], d["applied_wall_ns"]
            ready = next((r for r in status_rows if r["stage"] == s and r["wall_ns"] >= t_req and r["status"] == "READY"
                          and (r.get("requested") or 0) == n and (r.get("allocated") or 0) >= n), None)
            out.append({"k": d["k"], "stage": s, "requested": n, "requested_wall_ns": t_req,
                        "ready_wall_ns": ready["wall_ns"] if ready else None,
                        "activation_lag_s": (ready["wall_ns"] - t_req) / 1e9 if ready else None,
                        "status": "ready" if ready else "not ready by arm end"})
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
