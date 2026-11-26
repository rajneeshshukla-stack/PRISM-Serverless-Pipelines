"""The smallest live test, as one sequence: preflight, deploy, calibrate, smoke, baseline arm, adapter arm, collect,
coverage, analyse, teardown. Teardown runs in `finally` (unless keep=True), so a failure part-way still deletes what
this test created, EXCEPT its log groups when the REPORT coverage check has not passed: those are kept (7-day
retention) so that `collect` can resume, and `cleanup-logs` deletes them afterwards. The run is marked verified only
when every recorded request ID has a saved REPORT. Plan-only unless execute and PRISM_AWS_AUTHORIZED are set; the
local self-test runs the same sequence against the fakes (fake.fake_cloud), with documents, targets and time scaled
down.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List

import numpy as np

from . import aws
from .adapter import PolicyOnly
from .analyse import analyse, write_tables
from .campaign import WARM_MEAN_1024, calibrate, run_arm, set_environment
from .driver import Driver, SfnExecutor
from .workload import DEADLINE_S, MEAN_WORDS, Record, poisson_stream


@dataclass
class TestSpec:
    seed: int = 20261122
    n_records: int = 40                      # per arm
    rate_per_min: float = 12.0               # about 2-4 records in flight at 9-17 s each; cap 8
    mean_words: int = MEAN_WORDS
    bin_s: float = 12.0                      # compressed time: epoch = 5 bins = 60 s, lag = 2 bins (decision P6)
    schedule_mb: List[int] = field(default_factory=lambda: [1024, 512, 2048, 1024, 1024])
    smoke: int = 3
    smoke_gap_s: float = 30.0                # one record at a time (cap 1): the first is cold at every stage
    deadline_s: float = DEADLINE_S
    targets: Dict[str, float] = field(default_factory=lambda: dict(WARM_MEAN_1024))
    cap: int = 8
    log_settle_s: float = 60.0               # wait for CloudWatch delivery before collecting REPORT lines
    calib_kw: dict = field(default_factory=dict)
    poll_s: float = 1.0                      # configuration-update polling interval
    collect_attempts: int = aws.COLLECT_ATTEMPTS   # per REPORT page before collection stops (resumable)
    # mode "schedule": the fixed-memory-schedule arm on Poisson records (the original smallest live test).
    # mode "prism_replay" (R6.1): PRISM's own controller (policies.PRISM via closed_loop.PolicyController) against the
    # OnDemand baseline on the SAME thinned replay of one trace-week of the paper's synthetic trace, from the start of
    # the week (the controller forecasts that week; start_min is therefore fixed at 0).
    mode: str = "schedule"
    trace_seed: int = 101
    scenario: str = "stationary"
    week: str = "test"
    n_epochs: int = 8                        # replayed minutes = n_epochs x epoch_min (5)
    thin: float = 1 / 60                     # keep each trace request with probability thin; counts rescaled for PRISM
    prism_eps: float = 0.02
    forecaster: str = "gbm"                  # the paper's forecaster; tests use "seasonal_naive" for speed
    # pc_mode "apply": functions are published and invoked through ALIAS (both arms, same path), and PRISM's live P is
    # configured with PutProvisionedConcurrencyConfig; requests are capped at pc_cap per stage (cost bound; clipping is
    # recorded), and readiness is polled every pc_poll_s. "record": P is logged, never sent.
    pc_mode: str = "record"
    alias: str = "live"
    pc_cap: int = 4
    pc_poll_s: float = 10.0
    pc_initial_wait_s: float = 300.0         # bounded wait for epoch 0's provisioned concurrency to be READY


def code_fingerprint() -> dict:
    """What ran: Git HEAD and whether the harness, handler or src/ differ from it, plus SHA-256 of every harness file
    and the handler. Recorded in livetest.json so a live run can be tied to its code (the 21 Nov run could not)."""
    import hashlib
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    kit = os.path.dirname(here)
    files = sorted([os.path.join(here, f) for f in os.listdir(here) if f.endswith(".py")] +
                   [os.path.join(kit, "handlers", "docpipe.py")])
    def sha(path):
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    out = {"files_sha256": {os.path.relpath(f, kit).replace(os.sep, "/"): sha(f) for f in files}}
    try:
        git = lambda *a: subprocess.run(["git", *a], cwd=kit, capture_output=True, text=True, timeout=30)  # noqa: E731
        out["git_head"] = git("rev-parse", "HEAD").stdout.strip() or None
        st = git("status", "--porcelain", "--", ".", "../src").stdout
        out["uncommitted_paths"] = [l[3:] for l in st.splitlines() if l.strip()]
    except Exception as e:                                   # noqa: BLE001  (recorded, never fatal)
        out["git_error"] = f"{type(e).__name__}: {e}"
    return out


def replay_records(spec: TestSpec) -> List[Record]:
    """The identical record list both arms replay in mode 'prism_replay' (deterministic in the spec)."""
    from .workload import paper_trace_counts, thinned_counts, trace_stream
    counts = paper_trace_counts(spec.trace_seed, spec.scenario, spec.week, 0, spec.n_epochs * 5)
    return trace_stream(thinned_counts(counts, spec.thin, spec.seed), spec.bin_s, spec.seed, spec.mean_words)


def preview_decisions(spec: TestSpec) -> List[dict]:
    """Offline preview (no cloud, no fake): PRISM's controller decides each epoch from telemetry synthesised as if every
    replay record ran its four stages back to back at the warm 1024-MB means from its arrival time, on demand. The live
    decisions depend on measured completions and can differ; this shows which adaptive decisions the plan is expected
    to exercise (P per stage over epochs) before any AWS use."""
    from prism_repro.closed_loop import PolicyController
    from prism_repro.config import PipelineConfig
    from prism_repro.experiment import TraceBundle, make_policy
    from .adapter import LiveTelemetry
    from .campaign import WARM_MEAN_1024
    from .driver import STAGES
    cfg = PipelineConfig()
    recs = replay_records(spec)
    b = TraceBundle(spec.trace_seed, cfg, scenarios=(spec.scenario,), forecasters=(spec.forecaster,))
    ctl = PolicyController(make_policy(dict(family="PRISM", param=spec.prism_eps, fc=spec.forecaster)), b,
                           spec.scenario, spec.week)
    n_bins = spec.n_epochs * cfg.epoch_min
    tel = LiveTelemetry(n_bins, spec.bin_s, 0, count_scale=1 / spec.thin)
    ctl.start(cfg, n_bins, spec.n_epochs)
    for r in recs:
        t, rows = r.offset_s, []
        for st in STAGES:
            d = WARM_MEAN_1024[st] * spec.bin_s / 60.0          # stage time in the run's (compressed) clock
            rows.append({"stage": st, "start_wall_ns": int(t * 1e9), "end_wall_ns": int((t + d) * 1e9), "cold": False})
            t += d
        tel.add({"type": "record", "stages": rows, "_end": t})
    out = []
    for k in range(spec.n_epochs):
        v = k * cfg.epoch_min - cfg.lag_min
        cut = (v + 1) * spec.bin_s
        sub = LiveTelemetry(n_bins, spec.bin_s, 0, count_scale=1 / spec.thin)
        for r in tel.records:
            if r["_end"] <= cut:                               # only records finished by the decision time
                sub.add(r)
        P, mem = ctl.decide(k, sub.view(v))
        live = [int(math.ceil(x * spec.thin)) for x in np.asarray(P, float)]
        out.append({"k": k, "observed_upto_bin": v, "P_model": [round(float(x), 2) for x in P],
                    "P_live": [min(x, spec.pc_cap) for x in live], "memory": int(mem)})
    return out


def replay_estimate(spec: TestSpec, n_records: int) -> dict:
    """Cost for mode 'prism_replay', from the harness's estimator (UNVERIFIED list prices): 'expected' with both arms
    at 1024 MB (PRISM's choice at the 14.5 s deadline in the mocked replay), 'upper' with the PRISM arm at 3008 MB,
    plus a provisioned-concurrency ceiling = pc_cap x 4 stages x 3008 MB x the arm's length (apply mode only)."""
    from .estimate import PRICES_UNVERIFIED, estimate
    arm_s = spec.n_epochs * 5 * spec.bin_s
    exp = estimate(n_records, [1024], smoke=spec.smoke)["planning_total_usd_upper"]
    up = estimate(n_records, [3008], smoke=spec.smoke)["planning_total_usd_upper"]
    pc = (spec.pc_cap * 4 * 3008 / 1024 * arm_s * PRICES_UNVERIFIED["lambda_pc_gb_s"]) if spec.pc_mode == "apply" else 0.0
    return {"records_per_arm": n_records, "arm_length_s": arm_s, "expected_usd": round(exp, 4),
            "upper_usd": round(up, 4), "pc_ceiling_usd": round(pc, 4), "total_upper_usd": round(up + pc, 4),
            "prices": "UNVERIFIED list prices (estimate.PRICES_UNVERIFIED)"}


ARM_DIFFERENCES = ("intentional policy differences only: provisioned concurrency per stage (baseline 0; PRISM its "
                   "decision, recorded, applied only with pc_mode='apply') and the shared memory size (baseline 1024 MB; "
                   "PRISM its decision, applied); everything else is identical: records, arrival offsets, documents, "
                   "deadline, cap, bin length, forced-cold reset before each arm")


def plan(spec: TestSpec, region: str = aws.DEFAULT_REGION) -> List[str]:
    if spec.mode == "prism_replay":
        recs = replay_records(spec)
        p = ["# R6.1 paired live check (PRISM controller vs OnDemand), region " + region]
        p += aws.preflight(region)
        p += aws.deploy("<out>/manifest.json", region, alias=spec.alias if spec.pc_mode == "apply" else None)
        p += ["calibrate: chain-mode probes at 1024 MB per stage (<= 20 invocations each)",
              f"smoke: {spec.smoke} records one after another (StartSyncExecution)",
              f"records: thinned replay of trace {spec.trace_seed} {spec.scenario} {spec.week} week, minutes 0-"
              f"{spec.n_epochs * 5 - 1}, thin {spec.thin:.4f}: {len(recs)} records per arm, bin {spec.bin_s} s",
              f"arm baseline_ondemand: force cold, OnDemand (P=0, 1024 MB), the {len(recs)} records",
              f"arm adapter_prism: force cold, PRISM eps {spec.prism_eps} ({spec.forecaster}) via ControllerAdapter, "
              f"{spec.n_epochs} epochs; memory applied; P " +
              (f"configured on alias '{spec.alias}' (PutProvisionedConcurrencyConfig, capped at {spec.pc_cap} per stage), "
               f"readiness polled every {spec.pc_poll_s:.0f} s" if spec.pc_mode == "apply" else
               "recorded, not applied (pc_mode='record')") + f"; the SAME {len(recs)} records",
              ARM_DIFFERENCES,
              f"expected: {2 * len(recs) + spec.smoke} executions, {4 * (2 * len(recs) + spec.smoke)} stage REPORT "
              f"lines with recorded request IDs (coverage target), plus up to 80 calibration-probe REPORTs (extras)",
              f"estimate: {replay_estimate(spec, len(recs))}",
              "collect, coverage (verified only if every request ID has a REPORT), analyse"]
        p += aws.teardown("<out>/manifest.json", region)
        return p
    n_ep = len(spec.schedule_mb)
    p = ["# smallest live test, region " + region]
    p += aws.preflight(region)
    p += aws.deploy("<out>/manifest.json", region)
    p += ["calibrate: chain-mode probes at 1024 MB per stage (<= 20 invocations each); "
          "update_function_configuration PRISM_K=<k_stage>, PRISM_CALIBRATION=0",
          f"smoke: {spec.smoke} records one after another through {aws.STATE_MACHINE} (StartSyncExecution)",
          f"arm baseline_ondemand: force cold (nonce), OnDemand policy (P=0, 1024 MB), {spec.n_records} records, "
          f"Poisson {spec.rate_per_min}/min, seed {spec.seed}, cap {spec.cap}",
          f"arm adapter_schedule: force cold, ScheduleController memory {spec.schedule_mb} per {5 * spec.bin_s:.0f} s "
          f"epoch via update_function_configuration(MemorySize) x4 per change; P recorded, not applied; SAME records",
          f"collect: wait {spec.log_settle_s:.0f} s, then filter_log_events REPORT per log group, page by page "
          "(saved before each token; retried; resumable)",
          "coverage (local): every recorded request ID must have a saved REPORT; verified only if complete",
          "analyse (local)"]
    p += aws.teardown("<out>/manifest.json", region)
    p.append(f"epochs per arm: {n_ep}; arm length about {n_ep * 5 * spec.bin_s:.0f} s")
    return p


def run(out_dir: str, spec: TestSpec, region: str = aws.DEFAULT_REGION, execute: bool = False, cl=None,
        keep: bool = False, sleep=time.sleep, host_note: str = "", init_rows: int = 0) -> dict:
    if not aws.allowed(execute, cl):
        return {"plan": plan(spec, region)}
    from prism_repro.closed_loop import ScheduleController
    from prism_repro.config import PipelineConfig
    from prism_repro.policies import OnDemand
    os.makedirs(out_dir, exist_ok=True)
    man_path = os.path.join(out_dir, "manifest.json")
    log = []
    res: dict = {"spec": asdict(spec), "region": region, "host_note": host_note, "log": log,
                 "code": code_fingerprint(), "aws_profile": os.environ.get("AWS_PROFILE")}

    def note(msg):
        log.append({"wall_ns": time.time_ns(), "msg": msg})
        with open(os.path.join(out_dir, "livetest.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(log[-1]) + "\n")

    fake = cl is not None and all(getattr(c, "IS_FAKE", False) for c in cl.values())
    cl = cl or aws.clients(region)
    t_start_ms = time.time_ns() // 1_000_000
    try:
        pf = aws.preflight(region, execute=True, cl=cl)
        note(f"preflight: {pf[-1]}")
        if any(x.startswith("STOP") for x in pf):
            res["stopped"] = pf
            return res
        if spec.mode == "prism_replay" and spec.pc_mode == "apply":    # quota gate before anything is created
            acct = cl["lambda"].get_account_settings()["AccountLimit"]
            unres, need = int(acct.get("UnreservedConcurrentExecutions", 0)), 4 * spec.pc_cap
            res["pc_quota"] = {"ConcurrentExecutions": acct.get("ConcurrentExecutions"), "Unreserved": unres,
                               "needed_for_cap": need, "rule": "provisioned <= unreserved - 100"}
            note(f"pc quota: unreserved {unres}, cap needs {need} + 100")
            if unres - 100 < need:
                res["stopped"] = [f"STOP: unreserved concurrency {unres} - 100 < {need} (pc_cap {spec.pc_cap} x 4 "
                                  "stages); provisioned concurrency cannot be applied in this region/account"]
                return res
        apply_pc = spec.mode == "prism_replay" and spec.pc_mode == "apply"
        alias = spec.alias if apply_pc else None
        aws.deploy(man_path, region, execute=True, cl=cl, sleep=sleep, init_rows=init_rows, alias=alias)
        note("deployed")
        fns = aws.functions()
        lam = cl["lambda"]
        cal = calibrate(lam, fns, targets=spec.targets, n_words=spec.mean_words, **spec.calib_kw)
        res["calibration"] = cal
        note(f"calibrated: {{{', '.join(f'{s}: k={c['k']}' for s, c in cal.items())}}}")
        for s, fn in fns.items():
            set_environment(lam, {s: fn}, {"PRISM_K": cal[s]["k"], "PRISM_CALIBRATION": "0"}, sleep=sleep,
                            poll_s=spec.poll_s)
        if alias:                                    # the state machine invokes the alias: publish the calibrated k
            from .adapter import publish_alias
            res["calibrated_versions"] = publish_alias(lam, fns, alias, sleep=sleep, poll_s=spec.poll_s)
        man = aws.load_manifest(man_path)
        man["calibration"] = cal
        aws._save(man, man_path)
        sfn = SfnExecutor(cl["stepfunctions"], man["state_machine"])
        smoke = [Record(f"smoke-{i}", 1000 + i, spec.mean_words, i * spec.smoke_gap_s) for i in range(spec.smoke)]
        sd = os.path.join(out_dir, "smoke")
        os.makedirs(sd, exist_ok=True)
        res["smoke"] = Driver(sfn, os.path.join(sd, "records.jsonl"), "smoke", cap=1,
                              deadline_s=spec.deadline_s, sleep=sleep).run(smoke)
        note(f"smoke: {res['smoke']}")
        cfg = PipelineConfig()
        replay = spec.mode == "prism_replay"
        if spec.mode not in ("schedule", "prism_replay"):
            raise ValueError(f"unknown mode {spec.mode!r}")
        recs = replay_records(spec) if replay else poisson_stream(spec.n_records, spec.rate_per_min, spec.seed,
                                                                   spec.mean_words)
        if not recs:
            raise ValueError("the replay has no records; raise thin or n_epochs")
        with open(os.path.join(out_dir, "records_plan.jsonl"), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r.to_dict()) + "\n")
        n_ep = spec.n_epochs if replay else len(spec.schedule_mb)
        need = recs[-1].offset_s / (cfg.epoch_min * spec.bin_s)
        if need > n_ep:
            note(f"WARNING: the records span {need:.1f} epochs but the arm has {n_ep}; the last configuration holds")
        scale = dict(count_scale=1 / spec.thin, pc_scale=spec.thin) if replay else {}

        def actuator():
            from .adapter import LambdaActuator
            return LambdaActuator(lam, fns, pc_mode="apply" if alias else "record", alias=alias, sleep=sleep,
                                  poll_s=spec.poll_s, pc_cap_per_stage=spec.pc_cap if alias else None)
        scale.update(actuator=None, pc_poll_s=spec.pc_poll_s, pc_initial_wait_s=spec.pc_initial_wait_s)
        base_ctl = PolicyOnly(OnDemand())
        res["arms"] = {}
        res["arm_differences"] = ARM_DIFFERENCES if replay else "memory schedule only"
        res["arms"]["baseline_ondemand"] = run_arm(sfn, lam, fns, recs, "baseline_ondemand", out_dir, cfg, base_ctl,
                                                   n_ep, bin_s=spec.bin_s, cap=spec.cap, deadline_s=spec.deadline_s,
                                                   sleep=sleep, host_note=host_note, poll_s=spec.poll_s,
                                                   **dict(scale, actuator=actuator()))
        note("arm baseline_ondemand done")
        if replay:
            from prism_repro.closed_loop import PolicyController
            from prism_repro.experiment import TraceBundle, make_policy
            b = TraceBundle(spec.trace_seed, cfg, scenarios=(spec.scenario,), forecasters=(spec.forecaster,))
            pol = make_policy(dict(family="PRISM", param=spec.prism_eps, fc=spec.forecaster))
            ctl, arm2 = PolicyController(pol, b, spec.scenario, spec.week), "adapter_prism"
        else:
            ctl, arm2 = ScheduleController(np.zeros((n_ep, 4)), np.array(spec.schedule_mb)), "adapter_schedule"
        res["arms"][arm2] = run_arm(sfn, lam, fns, recs, arm2, out_dir, cfg, ctl, n_ep, bin_s=spec.bin_s, cap=spec.cap,
                                    deadline_s=spec.deadline_s, sleep=sleep, host_note=host_note, poll_s=spec.poll_s,
                                    **dict(scale, actuator=actuator()))
        note(f"arm {arm2} done")
        if not fake:
            sleep(spec.log_settle_s)
        res["collect"] = aws.collect_reports(man_path, t_start_ms - 60_000, time.time_ns() // 1_000_000 + 60_000,
                                             execute=True, cl=cl, sleep=sleep, attempts=spec.collect_attempts)
        note(f"collect: {res['collect'][-1]}")
        res["coverage"] = {k: v for k, v in aws.report_coverage(out_dir).items() if k != "missing_ids"}
        note(f"coverage: matched {res['coverage']['matched']} of {res['coverage']['expected_request_ids']}, "
             f"missing {res['coverage']['missing']}, collection {res['coverage']['collection_status']}")
        an = analyse(out_dir, ["baseline_ondemand", arm2], spec.bin_s,
                     os.path.join(out_dir, "cloudwatch_reports.jsonl"), prices=_prices(), window_bins=15)
        an["smoke"] = analyse(out_dir, ["smoke"], spec.bin_s, os.path.join(out_dir, "cloudwatch_reports.jsonl"))
        write_tables(an, os.path.join(out_dir, "analysis"))
        res["analysis"] = an
        note("analysed")
    except Exception as e:                                   # recorded; teardown still runs
        res["error"] = f"{type(e).__name__}: {e}"
        note(f"ERROR {res['error']}")
    finally:
        cov_ok = aws.coverage_complete(out_dir)
        res["verified"] = bool(cov_ok and not res.get("error") and not res.get("stopped"))
        if not cov_ok:
            note("NOT VERIFIED: REPORT coverage incomplete or not checked; the log groups are kept by teardown")
        if not keep:
            res["teardown"] = aws.teardown(man_path, region, execute=True, cl=cl)   # keeps logs unless coverage ok
            note(f"teardown: {res['teardown'][-1]}")
        with open(os.path.join(out_dir, "livetest.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=float)
    return res


def _prices():
    from .estimate import PRICES_UNVERIFIED
    return PRICES_UNVERIFIED
