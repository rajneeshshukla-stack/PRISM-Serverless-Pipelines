"""Local end-to-end self-test: the whole smallest-live-test sequence (livetest.run) against the in-process fakes, with
sockets blocked. Documents, stage targets, deadline and time are scaled down so it runs in well under a minute; the
checks are on mechanics (accounting, request IDs, REPORT join, cold starts, actuation, pairing, cleanup), not on
timing values, which on the fake are the host's.
"""
from __future__ import annotations

import json
import os
import socket
import sys

from .fake import fake_cloud
from .livetest import TestSpec, run

SCALE_T = 0.02                    # stage targets x 0.02 (16-80 ms of real handler work per stage)
SCALE_D = 0.04                    # deadline x 0.04 = 0.58 s


def scaled_spec() -> TestSpec:
    from .campaign import WARM_MEAN_1024
    return TestSpec(seed=7, n_records=16, rate_per_min=150.0, mean_words=300, bin_s=0.25,
                    schedule_mb=[1024, 512, 2048, 1024, 1024], smoke=3, smoke_gap_s=0.6,
                    deadline_s=14.5 * SCALE_D, targets={k: v * SCALE_T for k, v in WARM_MEAN_1024.items()},
                    cap=8, log_settle_s=0.0, calib_kw={"k_hi0": 5, "reps": 3}, poll_s=0.02)


def run_selftest(out_dir: str) -> dict:
    real = socket.socket
    import prism_repro.closed_loop  # noqa: F401  (imports ssl via sklearn/joblib before sockets are blocked)

    class Blocked(real):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in the self-test")
    socket.socket = Blocked
    try:
        cl = fake_cloud(account_limit=10)
        spec = scaled_spec()
        r = run(out_dir, spec, cl=cl)
    finally:
        socket.socket = real
    checks = {}
    an = r.get("analysis") or {}
    arms = an.get("arms", {})
    checks["no_error"] = r.get("error") is None
    checks["boto3_not_imported"] = "boto3" not in sys.modules
    left = r.get("teardown", [""])
    checks["teardown_clean"] = any(x.startswith("remaining after teardown") for x in left) and \
        not any(x.startswith("NOT CLEAN") for x in left)
    lam = cl["lambda"]
    checks["no_throttle"] = lam.throttles == 0
    checks["max_lambda_in_flight<=8"] = lam.max_in_flight <= 8
    checks["smoke_all_run"] = (r.get("smoke") or {}).get("met", 0) + (r.get("smoke") or {}).get("missed", 0) == spec.smoke
    for arm in ("baseline_ondemand", "adapter_schedule"):
        a = arms.get(arm, {})
        o = a.get("outcomes", {})
        checks[f"{arm}:all_records_logged"] = a.get("n") == spec.n_records
        checks[f"{arm}:none_failed"] = o.get("failed", 0) == 0
        integ = an.get("integrity", {}).get(arm, {})
        checks[f"{arm}:request_ids_complete"] = integ.get("missing_request_id", 0) == 0 and \
            integ.get("duplicate_request_ids", 0) == 0
        checks[f"{arm}:reports_joined"] = integ.get("report_missing", 0) == 0 and integ.get("stage_rows", 0) > 0
        checks[f"{arm}:cold_has_init_duration"] = integ.get("cold_without_init_duration", 0) == 0 and \
            integ.get("warm_with_init_duration", 0) == 0
        checks[f"{arm}:decisions_every_epoch"] = a.get("decisions", {}).get("n") == len(spec.schedule_mb)
        checks[f"{arm}:cold_starts_logged"] = all(a["stages"][s]["cold"] >= 1 for s in a.get("stages", {})) \
            if a.get("stages") else False
    b, s = arms.get("baseline_ondemand", {}), arms.get("adapter_schedule", {})
    checks["baseline:memory_1024_only"] = set().union(*[set(map(str, v["memory_mb"])) for v in b["stages"].values()]) \
        == {"1024"} if b else False
    exp_changes = sum(1 for x, y in zip(spec.schedule_mb, spec.schedule_mb[1:]) if x != y)
    checks["adapter:memory_changes_as_scheduled"] = s.get("decisions", {}).get("memory_changes") == exp_changes
    used = set().union(*[set(map(int, v["memory_mb"])) for v in s["stages"].values()]) if s else set()
    checks["adapter:ran_at_scheduled_sizes"] = {1024, 512}.issubset(used)
    cold_mem = s.get("cold_by_memory", {})
    checks["adapter:cold_after_change"] = any(k.endswith("@512") for k in cold_mem)
    pr = (an.get("paired") or {}).get("baseline_ondemand|adapter_schedule", {})
    checks["paired:same_records"] = pr.get("common_records") == spec.n_records and pr.get("same_documents") is True
    ok = all(checks.values())
    out = {"ok": ok, "checks": checks, "fake_lambda": {"calls": lam.calls, "updates": lam.updates,
                                                       "max_in_flight": lam.max_in_flight},
           "sfn_executions": cl["stepfunctions"].executions,
           "calibration_k": {k: v["k"] for k, v in (r.get("calibration") or {}).items()},
           "arms": {k: {"outcomes": v["outcomes"], "e2e_s": v["e2e_s"], "decisions": v["decisions"]["memory_changes"]}
                    for k, v in arms.items()}, "error": r.get("error")}
    with open(os.path.join(out_dir, "selftest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    return out
