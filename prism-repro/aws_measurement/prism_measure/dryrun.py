"""Dry runs against FakeLambda: NO AWS CALLS, and socket creation is blocked while they run.

full  : the full plan design (every cell, visit and batch), instant fake (time_scale 0) with injected faults:
        checks counts, the request-ID join, missing-field accounting, the CloudWatch fallback and the cap.
timed : a reduced design with real (scaled) sleeps, so invocations overlap: checks the concurrency cap under real
        threading and that the analysis recovers the fake's known I, X and R.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
from typing import Dict

from .analyse import analyse, load_jsonl, write_outputs
from .design import Design, build_design, function_environment
from .estimate import WARM_MEAN_1024
from .fake import FakeLambda, Truth
from .runner import Runner, fallback_reports


@contextlib.contextmanager
def no_network():
    real = socket.socket

    def blocked(*a, **k):
        raise RuntimeError("network access attempted during a dry run")
    socket.socket = blocked
    try:
        yield
    finally:
        socket.socket = real


def fake_for(design: Design, truth: Truth, **kw) -> FakeLambda:
    envs = {c.function: function_environment(c, {"cpu": truth.rate_1024}, WARM_MEAN_1024) for c in design.cells()}
    return FakeLambda({c.function: {"memory_mb": c.memory_mb, "env": envs[c.function]} for c in design.cells()},
                      truth, **kw), envs


def run_dry(out_dir: str, mode: str = "full", time_scale: float = 0.01, seed: int = 20261121,
            p_drop_tail_report: float = 0.02, p_missing_init: float = 0.01, n_boot: int = 200) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    if mode == "full":
        design = build_design(seed=seed)
        scale = 0.0
    elif mode == "timed":
        design = build_design(seed=seed, cold_main=24, warm_main=24, cold_init=24, warm_init=24)
        scale = time_scale
    else:
        raise ValueError(mode)
    truth = Truth()
    fake, envs = fake_for(design, truth, time_scale=scale, seed=seed,
                          p_drop_tail_report=p_drop_tail_report, p_missing_init=p_missing_init)
    rec_path = os.path.join(out_dir, "records.jsonl")
    if os.path.exists(rec_path):
        raise FileExistsError(rec_path)
    with no_network():
        summary = Runner(fake, envs, rec_path, cap=design.batch, poll_s=0.0).run(design, host_note=f"dry-run {mode}")
        records = load_jsonl(rec_path)
        cw = fallback_reports(fake.logs, records)
        res = analyse(records, cw, n_boot=n_boot)
    write_outputs(res, out_dir)
    with open(os.path.join(out_dir, "cloudwatch_reports.jsonl"), "w", encoding="utf-8") as f:
        for rep in cw.values():
            f.write(json.dumps(rep) + "\n")
    inv = [r for r in records if r.get("type") == "invocation"]
    check = {
        "mode": mode, "time_scale": scale, "invocations_planned": sum(v.cold + sum(v.warm_batches) for v in design.visits),
        "invocations_recorded": len(inv), "visits": len(design.visits), "fake_config_updates": fake.updates,
        "runner_max_in_flight": summary["max_in_flight"], "fake_max_in_flight": fake.max_in_flight,
        "cap": design.batch, "fake_throttles": fake.throttles, "fake_calls": fake.calls,
        "tail_reports_missing": sum(1 for r in inv if r.get("request_id") and not r.get("report")),
        "recovered_from_cloudwatch": len(cw),
        "no_report_after_fallback": sum(m["no_report"] for m in res["missing"]),
        "cold_without_init": sum(m["cold_without_init"] for m in res["missing"]),
        "unexpected_warm_in_cold_batch": sum(m["unexpected_warm_in_cold_batch"] for m in res["missing"]),
        "issues": res["issues"],
    }
    if scale > 0:          # compare recovered quantities with the fake's truth (scaled), per cell
        cmp = []
        for row in res["cells"]:
            fn = next(c.function for c in design.cells()
                      if (c.group, c.variant, c.memory_mb) == (row["group"], row["variant"], row["memory_mb"]))
            exp = fake.expected(fn)
            cmp.append({"cell": f"{row['group']}/{row['variant']}/{row['memory_mb']}",
                        **{f"{q}_expected": round(exp[q] * scale, 6) for q in ("I", "X", "R", "P")},
                        **{f"{q}_measured": row[f"{q}_s"] for q in ("I", "X", "R", "P")}})
        check["truth_comparison"] = cmp
    with open(os.path.join(out_dir, "dry_run_check.json"), "w", encoding="utf-8") as f:
        json.dump(check, f, indent=1)
    return check
