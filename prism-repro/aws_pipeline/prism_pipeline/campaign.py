"""Calibration, forced-cold reset and one arm (driver + controller adapter). Works with the real boto3 clients or the
local fakes; nothing here decides whether AWS may be called (aws.py does).
"""
from __future__ import annotations

import json
import os
import statistics
import time
import uuid
from typing import Dict, Optional, Sequence

from .adapter import ControllerAdapter, LambdaActuator, LiveTelemetry, PcMonitor, pc_readiness, publish_alias
from .driver import CAP_MAX, STAGES, Driver
from .workload import DEADLINE_S, MEAN_WORDS, Record, envelope

WARM_MEAN_1024 = {"ingest": 0.8, "transform": 4.0, "aggregate": 2.5, "load": 1.2}   # PipelineConfig.warm_mean_1024


def _invoke(lam, fn, env):
    r = lam.invoke(FunctionName=fn, InvocationType="RequestResponse", LogType="Tail",
                   Payload=json.dumps(env).encode())
    body = json.loads(r["Payload"].read())
    if r.get("FunctionError"):
        raise RuntimeError(f"{fn}: {body}")
    return body


def calibrate(lam, functions: Dict[str, str], targets: Dict[str, float] = WARM_MEAN_1024,
              n_words: int = MEAN_WORDS, doc_seed: int = 20261121, reps: int = 3, k_lo: int = 1,
              k_hi0: int = 50, min_frac: float = 0.4, max_iter: int = 6, k_max: int = 200_000) -> dict:
    """Linear fit handler_s = a + b*k per stage on a reference document of the mean size, at the deployed memory
    (1024 MB). Needs the functions deployed with PRISM_CALIBRATION=1 (so k_override is honoured)."""
    ref = Record("calibration", doc_seed, n_words, 0.0)
    cur = envelope(ref, "calibration", f"cal-{uuid.uuid4().hex}")
    out = {}

    def med(env, fn, k):
        hs = []
        for _ in range(reps):
            e = dict(env, k_override=k, trace=[])
            hs.append(_invoke(lam, fn, e)["trace"][-1]["handler_s"])
        return statistics.median(hs), hs

    for s in STAGES:
        fn, tgt = functions[s], targets[s]
        _invoke(lam, fn, dict(cur, k_override=k_lo, trace=[]))          # warm-up (cold start excluded)
        h_lo, p_lo = med(cur, fn, k_lo)
        k_hi, probes = k_hi0, [(k_lo, p_lo)]
        for _ in range(max_iter):
            h_hi, p_hi = med(cur, fn, k_hi)
            probes.append((k_hi, p_hi))
            if h_hi >= min_frac * tgt or k_hi >= k_max:
                break
            k_hi = int(min(max(k_hi * 2, k_hi * 0.7 * tgt / max(h_hi - h_lo, 1e-4)), k_max))
        b = (h_hi - h_lo) / max(k_hi - k_lo, 1)
        a = h_lo - b * k_lo
        if b <= 0:
            raise RuntimeError(f"{s}: handler time does not grow with k ({probes})")
        k_star = int(min(max(round((tgt - a) / b), 1), k_max))
        h_star, p_star = med(cur, fn, k_star)
        out[s] = {"k": k_star, "a_s": a, "b_s_per_k": b, "target_s": tgt, "achieved_median_s": h_star,
                  "achieved": p_star, "probes": probes, "n_words": n_words}
        cur = _invoke(lam, fn, dict(cur, k_override=k_star, trace=[]))   # next stage's input
        cur["trace"] = []
    return out


def wait_updated(lam, fn, sleep=time.sleep, timeout_s=300.0, poll_s=1.0, mono=time.monotonic):
    t0 = mono()
    while True:
        c = lam.get_function_configuration(FunctionName=fn)
        if c.get("LastUpdateStatus") in (None, "Successful") and c.get("State", "Active") == "Active":
            return mono() - t0
        if c.get("LastUpdateStatus") == "Failed" or c.get("State") == "Failed":
            raise RuntimeError(f"{fn}: {c.get('LastUpdateStatusReason') or c.get('StateReason')}")
        if mono() - t0 > timeout_s:
            raise TimeoutError(fn)
        sleep(poll_s)


def set_environment(lam, functions: Dict[str, str], updates: Dict[str, str], sleep=time.sleep,
                    poll_s: float = 1.0) -> Dict[str, dict]:
    """Merge `updates` into every function's variables (Environment replaces all variables, so all are sent). Any
    configuration change retires the function's warm environments."""
    out = {}
    for s, fn in functions.items():
        cur = lam.get_function_configuration(FunctionName=fn).get("Environment", {}).get("Variables", {})
        env = dict(cur, **{k: str(v) for k, v in updates.items()})
        lam.update_function_configuration(FunctionName=fn, Environment={"Variables": env})
        out[fn] = env
    for fn in functions.values():
        wait_updated(lam, fn, sleep=sleep, poll_s=poll_s)
    return out


def force_cold(lam, functions: Dict[str, str], sleep=time.sleep, poll_s: float = 1.0) -> str:
    nonce = uuid.uuid4().hex[:16]
    set_environment(lam, functions, {"PRISM_COLD_NONCE": nonce}, sleep=sleep, poll_s=poll_s)
    return nonce


def run_arm(executor, lam, functions: Dict[str, str], records: Sequence[Record], arm: str, out_dir: str, cfg,
            controller, n_epochs: int, bin_s: float = 60.0, count_scale: float = 1.0, pc_scale: float = 1.0,
            cap: int = CAP_MAX, deadline_s: float = DEADLINE_S, reset: bool = True, host_note: str = "",
            sleep=time.sleep, clock_ns=time.perf_counter_ns, wall_ns=time.time_ns,
            actuator: Optional[LambdaActuator] = None, poll_s: float = 1.0, pc_poll_s: float = 10.0,
            pc_initial_wait_s: float = 300.0, mono=time.monotonic) -> dict:
    """Forced-cold reset (optional), epoch-0 decision applied, then the records run open loop while the adapter
    takes decisions 1..n_epochs-1 in the background. Writes records.jsonl and decisions.jsonl under out_dir/arm."""
    d = os.path.join(out_dir, arm)
    os.makedirs(d, exist_ok=True)
    act = actuator or LambdaActuator(lam, functions, sleep=sleep, poll_s=poll_s)
    reset_info = {}
    if act.alias:                                        # apply mode: no provisioned concurrency carried over
        reset_info["pc_cleared"] = act.clear_pc()
    nonce = force_cold(lam, functions, sleep=sleep, poll_s=poll_s) if reset else None
    if act.alias and reset:                              # the alias must serve the new (cold) configuration
        reset_info["published_versions"] = publish_alias(lam, functions, act.alias, sleep=sleep, poll_s=poll_s)
    mon = PcMonitor(act, os.path.join(d, "pc_status.jsonl"), period_s=pc_poll_s, wall_ns=wall_ns,
                    sleep=sleep) if act.pc_mode == "apply" else None
    tel = LiveTelemetry(n_epochs * cfg.epoch_min, bin_s, wall_ns(), count_scale, len(STAGES))
    ad = ControllerAdapter(controller, act, tel, cfg, n_epochs, os.path.join(d, "decisions.jsonl"),
                           pc_scale=pc_scale, wall_ns=wall_ns, clock_ns=clock_ns, sleep=sleep)
    ad.start()
    first = ad.initial()
    initial_wait = None
    if mon and any(act.pc_cur):                          # epoch 0's provisioned concurrency: wait (bounded) for READY
        t_w, initial_wait = mono(), {"timeout_s": pc_initial_wait_s}
        while True:
            rows = mon.poll_once()
            pending = [r["stage"] for r in rows if r["configured"] and r["status"] != "READY"]
            if not pending or mono() - t_w > pc_initial_wait_s:
                break
            sleep(pc_poll_s)
        initial_wait.update(waited_s=mono() - t_w, not_ready=pending, ready=not pending)
    drv = Driver(executor, os.path.join(d, "records.jsonl"), arm, cap=cap, deadline_s=deadline_s,
                 clock_ns=clock_ns, wall_ns=wall_ns, sleep=sleep, on_result=tel.add, on_submit=ad.note_submitted)
    t0 = clock_ns()
    tel.t0 = wall_ns()
    if mon:
        mon.start()
    ad.run_in_background(t0)
    summary = drv.run(records, host_note=host_note, t0_ns=t0)
    ad.join(timeout_s=n_epochs * cfg.epoch_min * bin_s + 300)   # remaining epochs end on schedule (no invocations)
    readiness = None
    if mon:
        mon.stop()
        with open(mon.path, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        readiness = pc_readiness(ad.decisions, rows, list(functions))
        with open(os.path.join(d, "pc_readiness.json"), "w", encoding="utf-8") as f:
            json.dump(readiness, f, indent=1)
    served = {}                                         # stage executions by initialisation type (handler trace)
    for r in tel.records:
        for st in r.get("stages", []):
            key = f"{st.get('stage')}:{st.get('init_type') or 'unknown'}"
            served[key] = served.get(key, 0) + 1
    meta = {"arm": arm, "served_by_init_type": dict(sorted(served.items())), "reset_nonce": nonce, "first_decision": first, "summary": summary,
            "n_decisions": len(ad.decisions), "adapter_error": ad.error, "bin_s": bin_s, "n_epochs": n_epochs,
            "count_scale": count_scale, "pc_scale": pc_scale, "t0_wall_ns": tel.t0, "pc_mode": act.pc_mode,
            "alias": act.alias, "reset": reset_info, "pc_initial_wait": initial_wait, "pc_monitor_error": mon.error if mon else None,
            "pc_readiness": readiness}
    with open(os.path.join(d, "arm.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, default=float)
    return meta
