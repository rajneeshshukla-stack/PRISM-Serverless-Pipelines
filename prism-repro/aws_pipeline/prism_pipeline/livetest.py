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


def plan(spec: TestSpec, region: str = aws.DEFAULT_REGION) -> List[str]:
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
    res: dict = {"spec": asdict(spec), "region": region, "host_note": host_note, "log": log}

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
        aws.deploy(man_path, region, execute=True, cl=cl, sleep=sleep, init_rows=init_rows)
        note("deployed")
        fns = aws.functions()
        lam = cl["lambda"]
        cal = calibrate(lam, fns, targets=spec.targets, n_words=spec.mean_words, **spec.calib_kw)
        res["calibration"] = cal
        note(f"calibrated: {{{', '.join(f'{s}: k={c['k']}' for s, c in cal.items())}}}")
        for s, fn in fns.items():
            set_environment(lam, {s: fn}, {"PRISM_K": cal[s]["k"], "PRISM_CALIBRATION": "0"}, sleep=sleep,
                            poll_s=spec.poll_s)
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
        recs = poisson_stream(spec.n_records, spec.rate_per_min, spec.seed, spec.mean_words)
        with open(os.path.join(out_dir, "records_plan.jsonl"), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r.to_dict()) + "\n")
        n_ep = len(spec.schedule_mb)
        need = recs[-1].offset_s / (cfg.epoch_min * spec.bin_s)
        if need > n_ep:
            note(f"WARNING: the records span {need:.1f} epochs but the schedule has {n_ep}; the last configuration holds")
        base_ctl = PolicyOnly(OnDemand())
        res["arms"] = {}
        res["arms"]["baseline_ondemand"] = run_arm(sfn, lam, fns, recs, "baseline_ondemand", out_dir, cfg, base_ctl,
                                                   n_ep, bin_s=spec.bin_s, cap=spec.cap, deadline_s=spec.deadline_s,
                                                   sleep=sleep, host_note=host_note, poll_s=spec.poll_s)
        note("arm baseline_ondemand done")
        sched = ScheduleController(np.zeros((n_ep, 4)), np.array(spec.schedule_mb))
        res["arms"]["adapter_schedule"] = run_arm(sfn, lam, fns, recs, "adapter_schedule", out_dir, cfg, sched, n_ep,
                                                  bin_s=spec.bin_s, cap=spec.cap, deadline_s=spec.deadline_s,
                                                  sleep=sleep, host_note=host_note, poll_s=spec.poll_s)
        note("arm adapter_schedule done")
        if not fake:
            sleep(spec.log_settle_s)
        res["collect"] = aws.collect_reports(man_path, t_start_ms - 60_000, time.time_ns() // 1_000_000 + 60_000,
                                             execute=True, cl=cl, sleep=sleep, attempts=spec.collect_attempts)
        note(f"collect: {res['collect'][-1]}")
        res["coverage"] = {k: v for k, v in aws.report_coverage(out_dir).items() if k != "missing_ids"}
        note(f"coverage: matched {res['coverage']['matched']} of {res['coverage']['expected_request_ids']}, "
             f"missing {res['coverage']['missing']}, collection {res['coverage']['collection_status']}")
        an = analyse(out_dir, ["baseline_ondemand", "adapter_schedule"], spec.bin_s,
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
