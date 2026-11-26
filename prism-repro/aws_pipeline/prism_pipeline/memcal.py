"""First multi-memory calibration campaign: the four docpipe stages at 512, 1024, 2048 and 3008 MB (us-east-2,
on demand). PREPARED LOCALLY; nothing here calls AWS unless authorised (aws.allowed: --execute AND
PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES). Plan: aws_pipeline/MEMCAL_PLAN.md.

Workload: aws_pipeline/handlers/docpipe.py, unchanged, declared by the author as the research workload for this
campaign. Its work units K are FROZEN at the values calibrated at 1024 MB on AWS on 22 Nov 2026 and reused unchanged
at every size: the 1024 MB warm times match the paper's means BY CONSTRUCTION, and only the trend across sizes (plus
the cold-start terms and billing) is measured. Nothing is retuned per size (PRISM_CALIBRATION=0, so the handler
ignores k_override).

Design (reused from aws_measurement/prism_measure): one function per stage and size (16), each visit retires the
function's warm environments through a configuration nonce, runs one cold batch of 8 released together, then warm
batches of up to 8 on those environments. Visits are randomised within each of 3 blocks (3 days). 39 cold batches per
cell: 29 FIT visits and 10 CHECK visits, assigned before any data (seeded, stratified by block); the CHECK visits are
held out from every fit and used only to check the calibration.

REPORT lines: the log tail is kept per invocation, and every REPORT line of the run's log groups is collected from
CloudWatch with aws.collect_reports (page by page, resumable). report_coverage matches them to every recorded request
ID. teardown keeps this campaign's log groups (14-day retention) unless coverage is complete; cleanup_logs deletes them
later.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from . import aws
from .campaign import WARM_MEAN_1024, wait_updated
from prism_measure.design import Cell, Design, _split, build_design, check_cap
from prism_measure.runner import Runner

PREFIX = "prism-mcal"
TAG = {"project": "prism-memcal"}
ROLE = f"{PREFIX}-lambda-role"
REGION = "us-east-2"
SIZES = (512, 1024, 2048, 3008)
STAGES = ("ingest", "transform", "aggregate", "load")
RUNTIME, ARCH, TIMEOUT_S = aws.RUNTIME, aws.ARCH, aws.TIMEOUT_S        # python3.12, x86_64, 60 s
LOG_RETENTION_DAYS = 14               # covers the three-day campaign plus collection, with margin
CAP = 8                               # in flight at most (prism_measure CAP_MAX; account limit checked at preflight)
SEED = 20261122                       # design seed; the split uses SEED + 1, the smoke design SEED + 7
BLOCKS = 3
COLD_BATCHES_FIT, COLD_BATCHES_CHECK = 29, 10
COLD_PER_CELL = (COLD_BATCHES_FIT + COLD_BATCHES_CHECK) * CAP          # 312
WARM_PER_CELL = 1000
BASIC_POLICY = aws.BASIC_POLICY

# Work units frozen at the 1024 MB reference (saved calibration of run livetest_20261122-090236, us-east-2, 22 Nov 2026
# 09:02 CST, campaign.calibrate on the 3,000-word reference document doc_seed 20261121; handler unchanged since ea32370).
FROZEN_K = {"ingest": 373, "transform": 4908, "aggregate": 2264, "load": 1966}
FROZEN_K_SOURCE = {
    "run": "livetest_20261122-090236 (us-east-2, 1024 MB, 22 Nov 2026 09:02 CST; saved manifest 'calibration')",
    "method": "campaign.calibrate: linear fit of handler time on K at 1024 MB, reference document of the mean size",
    "targets_s": WARM_MEAN_1024,
    "achieved_median_s": {"ingest": 0.8005, "transform": 4.0451, "aggregate": 2.5160, "load": 1.1852},
    "handler_commit": "ea32370 (aws_pipeline/handlers/docpipe.py has no later commit)",
}
REFERENCE = {"pipeline_request_id": "memcal-reference", "record_id": "memcal-reference", "doc_seed": 20261121,
             "n_words": 3000, "deadline_s": 14.5, "arm": "memcal"}

# Current list prices, us-east-2, from the public AWS Price List (retrieved 22 Nov 2026 16:23 UTC; AWSLambda
# publication 2026-11-20T20:36:47Z, AmazonCloudWatch 2026-11-19T17:10:40Z). Free tier not assumed.
PRICES = {"lambda_gb_s_x86_tier1": 0.0000166667, "lambda_request": 0.0000002, "logs_ingest_per_gb": 0.50,
          "logs_storage_per_gb_month": 0.03,
          "source": "pricing.us-east-1.amazonaws.com offers v1.0 AWSLambda / AmazonCloudWatch current us-east-2"}
DATA_TRANSFER_OUT_PER_GB_UNVERIFIED = 0.09

RECORDS, SMOKE_DIR, DESIGN_FILE, SPEC_FILE = "records.jsonl", "smoke", "design.json", "workload_spec.json"
STARTUP = {
    "module_scope_inside_INIT": [
        "standard-library imports: base64, hashlib, json, os, re, tempfile, time, unicodedata, uuid, zlib",
        "ENV_ID = uuid4 (one per execution environment)",
        "synthetic vocabulary of 2,000 words (_vocab)",
        "_build_tables(PRISM_INIT_ROWS = 0): empty, so no classifier/lexicon start-up work (decision P3 default)",
        "one 'env_init' JSON log line; four regular expressions compiled",
    ],
    "first_invocation": "no extra work: the handler only flags cold=True; any first-use costs (Unicode tables, regex "
                        "and zlib first use) fall inside Duration and are measured as X",
    "not_present": "no network, no files, no dependency outside the standard library; sink 'none' (boto3 never "
                   "imported); PRISM_CALIBRATION=0 (k_override ignored)",
    "consequence": "the cold penalty measured is the platform's plus the standard library's; the paper's 6 s mean "
                   "initialisation has no code counterpart here (P3), so magnitudes are not the paper's",
}


@dataclass(frozen=True)
class McalCell(Cell):
    @property
    def function(self) -> str:
        return f"{PREFIX}-{self.variant}-{self.memory_mb}"


def visit_id(v) -> str:
    return f"b{v.block}-o{v.order}"                       # as prism_measure.runner names visits


def build(smoke: bool = False) -> Design:
    if smoke:
        d = build_design(seed=SEED + 7, batch=CAP, blocks=1, sizes=SIZES, stages=STAGES, init_variants=(),
                         cold_main=CAP, warm_main=CAP)
    else:
        d = build_design(seed=SEED, batch=CAP, blocks=BLOCKS, sizes=SIZES, stages=STAGES, init_variants=(),
                         cold_main=COLD_PER_CELL, warm_main=WARM_PER_CELL)
    for v in d.visits:
        v.cell = McalCell(v.cell.group, v.cell.variant, v.cell.memory_mb)
    return d


def split_of(d: Design, seed: int = SEED + 1) -> Dict[str, str]:
    """FIT or CHECK per visit, fixed before any data: per cell, COLD_BATCHES_CHECK visits spread over the blocks
    (4/3/3 in random block order), chosen at random within each block."""
    rng = random.Random(seed)
    by_cell: Dict[str, list] = {}
    for v in d.visits:
        by_cell.setdefault(v.cell.key, []).append(v)
    out = {}
    for key in sorted(by_cell):
        k = _split(COLD_BATCHES_CHECK, d.blocks)
        rng.shuffle(k)
        for b, kb in zip(range(d.blocks), k):
            pool = sorted((v for v in by_cell[key] if v.block == b), key=lambda v: v.order)
            rng.shuffle(pool)
            for i, v in enumerate(pool):
                out[visit_id(v)] = "check" if i < kb else "fit"
    return out


def function_env(stage: str, k_scale: float = 1.0) -> Dict[str, str]:
    k = max(int(round(FROZEN_K[stage] * k_scale)), 1)
    return {"PRISM_STAGE": stage, "PRISM_K": str(k), "PRISM_INIT_ROWS": "0", "PRISM_SINK": "none",
            "PRISM_CALIBRATION": "0", "PRISM_COLD_NONCE": "deploy"}


# --------------------------------------------------------------------------- workload record
def _git(*args) -> Optional[str]:
    try:
        return subprocess.run(["git", *args], cwd=os.path.dirname(aws.HANDLER_FILE), capture_output=True, text=True,
                              timeout=20).stdout.strip() or None
    except Exception:                                         # noqa: BLE001  (provenance only)
        return None


def _load_handler():
    saved = {k: os.environ.pop(k, None) for k in ("PRISM_INIT_ROWS", "PRISM_SINK", "PRISM_K", "PRISM_CALIBRATION")}
    try:
        spec = importlib.util.spec_from_file_location("docpipe_memcal_local", aws.HANDLER_FILE)
        mod = importlib.util.module_from_spec(spec)
        mod.print = lambda *a, **k: None
        spec.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    return mod


def stage_inputs() -> Dict[str, dict]:
    """The request body of each stage: the reference document passed down the chain, computed locally with the pure
    stage functions (the document each stage receives does not depend on K; only metadata does). Identical at every
    memory size."""
    mod = _load_handler()
    cur = dict(REFERENCE, trace=[])
    out = {}
    for s in STAGES:
        out[s] = json.loads(json.dumps(cur))
        cur = mod._LOGIC[s](json.loads(json.dumps(cur)), 1)
        cur["trace"], cur["workload"] = [], mod.WORKLOAD
    return out


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def workload_spec() -> dict:
    with open(aws.HANDLER_FILE, "rb") as f:
        raw = f.read()
    lf = raw.replace(b"\r\n", b"\n")
    inputs = stage_inputs()
    mod = _load_handler()
    return {
        "label": "DECLARED RESEARCH WORKLOAD for the first multi-memory calibration campaign: the synthetic four-stage "
                 "document-ingestion pipeline (aws_pipeline/SPEC.md); not the authors' application",
        "declaration": "declared by the author for this campaign on 22 Nov 2026 (SPEC.md decision P1); the handler's "
                       "own LABEL text is unchanged because the code is frozen",
        "handler_label_in_code": mod.LABEL, "workload_id": mod.WORKLOAD,
        "handler_file": "prism-repro/aws_pipeline/handlers/docpipe.py",
        "handler_sha256_lf": hashlib.sha256(lf).hexdigest(),
        "handler_git_blob": hashlib.sha1(b"blob %d\0" % len(lf) + lf).hexdigest(),
        "handler_last_commit": _git("log", "-1", "--format=%h", "--", "../handlers/docpipe.py"),
        "repository_head_at_preparation": _git("rev-parse", "--short", "HEAD"),
        "runtime": RUNTIME, "architecture": ARCH, "timeout_s": TIMEOUT_S, "region": REGION,
        "package": "zip holding docpipe.py only; standard library; no layers", "entry_points":
            {s: f"docpipe.{s}" for s in STAGES},
        "memory_sizes_mb": list(SIZES), "functions": {s: [f"{PREFIX}-{s}-{m}" for m in SIZES] for s in STAGES},
        "work_units_K": FROZEN_K, "work_units_source": FROZEN_K_SOURCE, "retuned_per_size": False,
        "reference_matched_by_construction": "K was fitted so that each stage's warm handler time at 1024 MB equals the "
            "paper's mean (0.8/4.0/2.5/1.2 s) on the reference document; 1024 MB warm times therefore reproduce the "
            "targets by construction and are a check, not a finding. The same K is used at 512, 2048 and 3008 MB, so "
            "the measured trend is Lambda's own scaling of this fixed work.",
        "environment": {s: function_env(s) for s in STAGES},
        "input_mix": {"description": "one reference document for every invocation of a stage, at every size: doc_seed "
                                     "20261121, 3,000 words (the calibration document). The P2 log-normal size mix is "
                                     "NOT used: its spread is by construction and would swamp the cold-minus-warm "
                                     "difference.",
                      "reference": REFERENCE,
                      "request_bytes": {s: len(json.dumps(inputs[s]).encode()) for s in STAGES},
                      "request_sha256": {s: _sha(inputs[s]) for s in STAGES}},
        "startup_behaviour": STARTUP,
        "invocation": "synchronous Invoke (RequestResponse, LogType=Tail) of each stage function directly from the "
                      "client; no Step Functions in this campaign",
    }


# --------------------------------------------------------------------------- local preparation
def design_document(d: Design, split: Dict[str, str]) -> dict:
    return {"campaign": "memcal-1", "seed": SEED, "split_seed": SEED + 1, "cap": CAP, "blocks": d.blocks,
            "cold_per_cell": COLD_PER_CELL, "warm_per_cell": WARM_PER_CELL,
            "cold_batches": {"fit": COLD_BATCHES_FIT, "check": COLD_BATCHES_CHECK},
            "design": json.loads(d.to_json()), "split": split}


def prepare(run_dir: str) -> dict:
    """Write design.json and workload_spec.json into a new run directory (refuses to overwrite)."""
    os.makedirs(run_dir, exist_ok=True)
    for f in (DESIGN_FILE, SPEC_FILE):
        if os.path.exists(os.path.join(run_dir, f)):
            raise FileExistsError(f"{f} already exists in the run directory; use a new directory")
    d = build()
    doc = design_document(d, split_of(d))
    spec = workload_spec()
    for name, obj in ((DESIGN_FILE, doc), (SPEC_FILE, spec)):
        with open(os.path.join(run_dir, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=1)
            f.write("\n")
    return {"design_sha256": _sha(doc), "workload_spec_sha256": _sha(spec), "visits": len(d.visits),
            "invocations": sum(v.cold + sum(v.warm_batches) for v in d.visits)}


def counts(d: Design, split: Dict[str, str]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for v in d.visits:
        c = out.setdefault(v.cell.key, {"cold": 0, "warm": 0, "visits": 0, "fit_visits": 0, "check_visits": 0,
                                        "fit_cold": 0, "check_cold": 0, "fit_warm": 0, "check_warm": 0,
                                        "check_by_block": [0] * d.blocks})
        s = split[visit_id(v)]
        c["cold"] += v.cold
        c["warm"] += sum(v.warm_batches)
        c["visits"] += 1
        c[f"{s}_visits"] += 1
        c[f"{s}_cold"] += v.cold
        c[f"{s}_warm"] += sum(v.warm_batches)
        if s == "check":
            c["check_by_block"][v.block] += 1
    return out


# --------------------------------------------------------------------------- AWS actions (guarded)
def _clients(cl):
    return cl or aws.clients(REGION)


def leftovers(cl) -> Dict[str, list]:
    fns = [f["FunctionName"] for p in cl["lambda"].get_paginator("list_functions").paginate()
           for f in p["Functions"] if f["FunctionName"].startswith(PREFIX + "-")]
    lgs = [g["logGroupName"] for p in cl["logs"].get_paginator("describe_log_groups").paginate(
        logGroupNamePrefix=f"/aws/lambda/{PREFIX}-") for g in p["logGroups"]]
    roles = [ROLE] if aws._ignore(cl["iam"].get_role, "NoSuchEntity", RoleName=ROLE) else []
    return {"functions": fns, "log_groups": lgs, "roles": roles}


def preflight(execute: bool = False, cl=None) -> List[str]:
    plan = ["sts.get_caller_identity", "lambda.get_account_settings (ConcurrentExecutions, Unreserved...)",
            f"lambda.list_functions, logs.describe_log_groups, iam.get_role: any '{PREFIX}-' leftover (read only)"]
    if not aws.allowed(execute, cl):
        return plan
    cl = _clients(cl)
    cl["sts"].get_caller_identity()
    lim = cl["lambda"].get_account_settings()["AccountLimit"]
    left = leftovers(cl)
    plan.append(f"region {REGION}: ConcurrentExecutions={lim.get('ConcurrentExecutions')}, "
                f"UnreservedConcurrentExecutions={lim.get('UnreservedConcurrentExecutions')}; leftovers={left}")
    if (lim.get("ConcurrentExecutions") or 0) < CAP + 2:
        plan.append(f"STOP: the account limit is below the cap plus headroom ({CAP + 2})")
    if any(left.values()):
        plan.append("STOP: leftovers from an earlier campaign; run teardown and verify first")
    return plan


def deploy(run_dir: str, execute: bool = False, cl=None, sleep=time.sleep, k_scale: float = 1.0) -> List[str]:
    """Role, 16 log groups (14-day retention) and 16 functions. Resumable: the manifest is saved after every resource,
    and a function already in the manifest is skipped. k_scale != 1 is for the local fakes only."""
    d = build()
    plan = [f"iam.create_role {ROLE} (trust lambda.amazonaws.com) + attach {BASIC_POLICY}"]
    for c in d.cells():
        plan.append(f"logs.create_log_group /aws/lambda/{c.function} retention={LOG_RETENTION_DAYS} d tags={TAG}")
        plan.append(f"lambda.create_function {c.function} handler=docpipe.{c.variant} runtime={RUNTIME} arch={ARCH} "
                    f"memory={c.memory_mb} MB timeout={TIMEOUT_S}s env={function_env(c.variant)} tags={TAG}")
    if not aws.allowed(execute, cl):
        return plan
    fakes = cl is not None and all(getattr(c, "IS_FAKE", False) or getattr(c, "IS_OFFLINE_HOOKED", False)
                                   for c in cl.values())     # local fakes, or botocore clients hooked offline
    if k_scale != 1.0 and not fakes:
        raise ValueError("k_scale is for the local fakes only; the campaign uses the frozen K")
    for f in (DESIGN_FILE, SPEC_FILE):
        if not os.path.exists(os.path.join(run_dir, f)):
            raise FileNotFoundError(f"{f} missing: run `memcal prepare --run <run dir>` first")
    spec = aws.load_manifest(os.path.join(run_dir, SPEC_FILE))
    cur = workload_spec()
    if spec["handler_sha256_lf"] != cur["handler_sha256_lf"] or spec["input_mix"] != cur["input_mix"] \
            or spec["work_units_K"] != FROZEN_K:
        raise RuntimeError("handler, inputs or K differ from the saved workload_spec.json; refusing to deploy")
    cl = _clients(cl)
    iam, lam, logs = cl["iam"], cl["lambda"], cl["logs"]
    mp = os.path.join(run_dir, "manifest.json")
    man = aws.load_manifest(mp) if os.path.exists(mp) else {
        "campaign": "memcal-1", "region": REGION, "prefix": PREFIX, "tag": TAG, "role": ROLE, "functions": {},
        "log_groups": [], "created_wall_ns": time.time_ns(), "k_scale": k_scale,
        "workload_spec_sha256": _sha(spec), "design_sha256": _sha(aws.load_manifest(os.path.join(run_dir, DESIGN_FILE)))}
    man["account"] = cl["sts"].get_caller_identity()["Account"]
    aws._save(man, mp)
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                                                     "Action": "sts:AssumeRole"}]}
    try:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust),
                              Tags=[{"Key": k, "Value": v} for k, v in TAG.items()])["Role"]["Arn"]
    except Exception as e:                                    # noqa: BLE001
        if aws._code(e) != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
    iam.attach_role_policy(RoleName=ROLE, PolicyArn=BASIC_POLICY)
    man["role_arn"] = arn
    aws._save(man, mp)
    code = aws.package()
    man["code_sha256"] = base64.b64encode(hashlib.sha256(code).digest()).decode()
    man["package_bytes"] = len(code)
    for c in d.cells():
        fn, lg = c.function, f"/aws/lambda/{c.function}"
        if fn in man["functions"]:
            continue
        aws._ignore(logs.create_log_group, "ResourceAlreadyExistsException", logGroupName=lg, tags=TAG)
        logs.put_retention_policy(logGroupName=lg, retentionInDays=LOG_RETENTION_DAYS)
        if lg not in man["log_groups"]:
            man["log_groups"].append(lg)
        aws._save(man, mp)
        env = function_env(c.variant, k_scale)
        for attempt in range(8):                              # a new role takes a few seconds to become assumable
            try:
                r = lam.create_function(FunctionName=fn, Runtime=RUNTIME, Role=arn, Handler=f"docpipe.{c.variant}",
                                        Code={"ZipFile": code}, Timeout=TIMEOUT_S, MemorySize=c.memory_mb,
                                        Architectures=[ARCH], Environment={"Variables": env}, Tags=TAG)
                break
            except Exception as e:                            # noqa: BLE001
                if aws._code(e) != "InvalidParameterValueException" or attempt == 7:
                    raise
                sleep(10)
        man["functions"][fn] = {"stage": c.variant, "memory_mb": c.memory_mb, "arn": r["FunctionArn"], "env": env}
        aws._save(man, mp)
        wait_updated(lam, fn, sleep=sleep)
    plan.append(f"deployed {len(man['functions'])} functions; manifest <run dir>/manifest.json")
    return plan


def check_deployed(man: dict, lam) -> List[str]:
    """Every function must still be what was declared: memory, runtime, architecture, handler, timeout, code and the
    frozen environment (the nonce aside). Any difference blocks the run."""
    bad = []
    for fn, f in sorted(man["functions"].items()):
        c = lam.get_function_configuration(FunctionName=fn)
        want = {"MemorySize": f["memory_mb"], "Runtime": RUNTIME, "Handler": f"docpipe.{f['stage']}",
                "Timeout": TIMEOUT_S, "Architectures": [ARCH], "CodeSha256": man.get("code_sha256")}
        for k, v in want.items():
            if c.get(k) != v:
                bad.append(f"{fn}: {k} is {c.get(k)!r}, expected {v!r}")
        env = dict(c.get("Environment", {}).get("Variables", {}))
        exp = function_env(f["stage"], man.get("k_scale", 1.0))
        env.pop("PRISM_COLD_NONCE", None)
        exp.pop("PRISM_COLD_NONCE", None)
        if env != exp:
            bad.append(f"{fn}: environment {env} differs from the frozen {exp}")
    return bad


def runtime_from_tail(log_result_b64: Optional[str]) -> Optional[dict]:
    """'Runtime Version: python:3.12.vNN' from a cold invocation's INIT_START line (the runtime ARN is dropped).
    Lambda patches managed runtimes automatically, so a change between blocks must be visible."""
    if not log_result_b64:
        return None
    try:
        text = base64.b64decode(log_result_b64).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return None
    for line in text.splitlines():
        if line.startswith("INIT_START"):
            part = line.split("	")[0]
            return {"runtime_version": part.split("Runtime Version:", 1)[-1].strip()[:80]}
    return None


def normalise(body: dict) -> dict:
    """Keep only what the analysis needs from a stage's response (the envelope itself carries the document)."""
    if "trace" not in body:
        return {"first_call": None, "error_type": body.get("errorType"), "error": str(body.get("errorMessage"))[:200]}
    t = body["trace"][-1] if body["trace"] else {}
    return {"first_call": t.get("cold"), "aws_request_id": t.get("aws_request_id"), "env_id": t.get("env_id"),
            "nonce": t.get("nonce"), "module_init_s": t.get("module_init_s"), "handler_s": t.get("handler_s"),
            "k": t.get("k"), "memory_mb": t.get("memory_mb"), "init_rows": t.get("init_rows"),
            "stage": t.get("stage"), "in_bytes": t.get("in_bytes"), "out_bytes": t.get("out_bytes"),
            "workload": body.get("workload")}


def run(run_dir: str, blocks: Optional[List[int]] = None, execute: bool = False, cl=None, smoke: bool = False,
        host_note: str = "", sleep=time.sleep) -> List[str]:
    d = build(smoke)
    path = os.path.join(run_dir, SMOKE_DIR, RECORDS) if smoke else os.path.join(run_dir, RECORDS)
    n = sum(v.cold + sum(v.warm_batches) for v in d.visits if smoke or blocks is None or v.block in blocks)
    plan = [f"{'smoke' if smoke else 'campaign'} blocks {blocks if blocks is not None else 'all'}: check every "
            f"function's configuration (read only), then {n} invocations (cap {CAP}) -> <run dir>/"
            f"{os.path.relpath(path, run_dir)}"]
    if not aws.allowed(execute, cl):
        return plan
    mp = os.path.join(run_dir, "manifest.json")
    man = aws.load_manifest(mp)
    doc = aws.load_manifest(os.path.join(run_dir, DESIGN_FILE))
    full = build()
    if _sha(doc) != man["design_sha256"] or doc["design"] != json.loads(full.to_json()) \
            or doc["split"] != split_of(full):
        plan.append("STOP: design.json does not match the manifest or the current code")
        return plan
    cl = _clients(cl)
    bad = check_deployed(man, cl["lambda"])
    if bad:
        plan += ["STOP: deployed configuration differs from the declared one:"] + [f"  {b}" for b in bad]
        return plan
    spec = aws.load_manifest(os.path.join(run_dir, SPEC_FILE))
    inputs = stage_inputs()
    if {s: _sha(inputs[s]) for s in STAGES} != spec["input_mix"]["request_sha256"]:
        plan.append("STOP: the stage inputs differ from workload_spec.json")
        return plan
    os.makedirs(os.path.dirname(path), exist_ok=True)
    envs = {fn: f["env"] for fn, f in man["functions"].items()}
    payloads = {fn: inputs[f["stage"]] for fn, f in man["functions"].items()}
    r = Runner(cl["lambda"], envs, path, cap=CAP, payloads=payloads, normalise=normalise, sleep=sleep,
               tail_hook=runtime_from_tail,
               meta={"campaign": "memcal-1", "smoke": smoke, "design_sha256": man["design_sha256"],
                     "workload_spec_sha256": man["workload_spec_sha256"], "code_sha256": man.get("code_sha256")})
    summ = r.run(d, None if smoke else blocks, host_note=host_note)
    plan.append(f"visits run {summ['visits_run']}, max in flight {summ['max_in_flight']} (cap {CAP})")
    if smoke:
        chk = smoke_check(path, {s: int(function_env(s, man.get("k_scale", 1.0))["PRISM_K"]) for s in STAGES})
        plan.append(f"smoke check: {json.dumps(chk)}")
        plan.append("SMOKE OK" if chk["ok"] else "STOP: smoke check failed; investigate before any campaign block")
    return plan


def smoke_check(path: str, k_expected: Optional[Dict[str, int]] = None) -> dict:
    k_expected = k_expected or FROZEN_K
    rows = aws._jsonl(path)
    inv = [r for r in rows if r.get("type") == "invocation"]
    pay = [r.get("payload") or {} for r in inv]
    cold = [r for r, p in zip(inv, pay) if p.get("first_call") is True]
    warm = [r for r, p in zip(inv, pay) if p.get("first_call") is False]
    chk = {"invocations": len(inv), "errors": sum(bool(r.get("error") or r.get("function_error")) for r in inv),
           "cold": len(cold), "warm": len(warm),
           "cold_in_cold_batches": sum(r["batch_kind"] == "cold" for r in cold),
           "cold_with_init_in_tail": sum(bool((r.get("report") or {}).get("init_duration_ms")) for r in cold),
           "warm_with_init_in_tail": sum(bool((r.get("report") or {}).get("init_duration_ms")) for r in warm),
           "tail_report_missing": sum(r.get("report") is None for r in inv),
           "memory_mismatch": sum(p.get("memory_mb") != r["memory_mb"] for r, p in zip(inv, pay)),
           "k_mismatch": sum(p.get("k") != k_expected.get(p.get("stage")) for p in pay),
           "request_id_mismatch": sum(p.get("aws_request_id") != r.get("request_id") for r, p in zip(inv, pay)),
           "runtime_versions": sorted({(r.get("tail_extra") or {}).get("runtime_version") or "not in tail"
                                       for r in cold})}
    chk["ok"] = (chk["invocations"] > 0 and chk["errors"] == 0 and chk["cold"] == chk["cold_in_cold_batches"]
                 and chk["cold_with_init_in_tail"] == chk["cold"] and chk["warm_with_init_in_tail"] == 0
                 and chk["memory_mismatch"] == 0 and chk["k_mismatch"] == 0 and chk["request_id_mismatch"] == 0)
    return chk


def _invocations(run_dir: str) -> List[dict]:
    out = []
    for p in (os.path.join(run_dir, RECORDS), os.path.join(run_dir, SMOKE_DIR, RECORDS)):
        out += [dict(r, _file=os.path.relpath(p, run_dir)) for r in aws._jsonl(p) if r.get("type") == "invocation"]
    return out


def collect(run_dir: str, execute: bool = False, cl=None, rescan: bool = False, sleep=time.sleep) -> List[str]:
    """REPORT lines of the 16 log groups, through aws.collect_reports (page by page, saved before each token,
    resumable). The window is fixed at the first call: from 10 min before the first recorded invocation to
    LOG_RETENTION_DAYS - 1 days later, so later blocks are collected with rescan=True (duplicates skipped)."""
    plan = [f"logs.filter_log_events '\"REPORT RequestId\"' on the 16 /aws/lambda/{PREFIX}-<stage>-<MB> log groups, "
            "paginated, each page saved before its token; resumable" + (" (rescan from the start)" if rescan else "")]
    if not aws.allowed(execute, cl):
        return plan
    inv = _invocations(run_dir)
    if not inv:
        plan.append("nothing to collect: no recorded invocation")
        return plan
    t0 = min(r["wall_start_ns"] for r in inv) // 1_000_000 - 10 * 60_000
    plan += aws.collect_reports(os.path.join(run_dir, "manifest.json"), t0,
                                t0 + (LOG_RETENTION_DAYS - 1) * 86_400_000, execute=execute, cl=cl, sleep=sleep,
                                rescan=rescan)[len(aws.STAGES):]
    return plan


def report_coverage(run_dir: str) -> dict:
    """Every recorded request ID (campaign and smoke) must have a REPORT saved from CloudWatch. Also compares the
    log-tail copy with the CloudWatch copy field by field. Writes <run dir>/cloudwatch_coverage.json."""
    inv = _invocations(run_dir)
    expected = {r["request_id"]: r for r in inv if r.get("request_id")}
    no_id = [r for r in inv if not r.get("request_id")]
    cw = {r["request_id"]: r for r in aws._jsonl(os.path.join(run_dir, aws.REPORTS_FILE))}
    sp = os.path.join(run_dir, aws.COLLECT_STATE_FILE)
    status = aws.load_manifest(sp).get("status", "unknown") if os.path.exists(sp) else "not collected"
    missing = sorted(set(expected) - set(cw))
    fields = ("duration_ms", "billed_duration_ms", "memory_size_mb", "init_duration_ms")
    both = [rid for rid in expected if rid in cw and expected[rid].get("report")]
    differ = [rid for rid in both if any(expected[rid]["report"].get(k) != cw[rid].get(k) for k in fields)]
    cov = {"expected_request_ids": len(expected), "matched": len(expected) - len(missing), "missing": len(missing),
           "missing_ids": [{"request_id": r, "function": expected[r]["function"], "visit_id": expected[r]["visit_id"],
                            "file": expected[r]["_file"]} for r in missing],
           "extra_reports": len(set(cw) - set(expected)),
           "invocations_without_request_id": len(no_id),
           "tail_and_cloudwatch_both": len(both), "tail_and_cloudwatch_differ": len(differ),
           "collection_status": status}
    cov["complete"] = status == "complete" and bool(expected) and not missing
    aws._atomic_json(cov, os.path.join(run_dir, aws.COVERAGE_FILE))
    return cov


def _tagged(lam, fn) -> bool:
    try:
        arn = lam.get_function_configuration(FunctionName=fn)["FunctionArn"]
        return lam.list_tags(Resource=arn).get("Tags", {}).get("project") == TAG["project"]
    except Exception as e:                                    # noqa: BLE001
        if aws._code(e) == "ResourceNotFoundException":
            return False
        raise


def teardown(run_dir: str, execute: bool = False, cl=None, delete_log_groups: str = "auto") -> List[str]:
    """Functions (manifest, or prefix AND tag) and the role are deleted. Log groups are deleted only when
    cloudwatch_coverage.json says complete ('auto'); otherwise they are KEPT with LOG_RETENTION_DAYS retention and
    listed in the manifest (cleanup_logs deletes them later). 'always' / 'never' override."""
    plan = [f"lambda.delete_function for the manifest's 16 functions and any '{PREFIX}-' function tagged {TAG}",
            f"logs.delete_log_group /aws/lambda/{PREFIX}-* ONLY if REPORT coverage is complete; otherwise kept "
            f"({LOG_RETENTION_DAYS}-day retention) and listed in the manifest",
            f"iam.detach_role_policy {BASIC_POLICY}; iam.delete_role {ROLE}",
            f"then list every remaining '{PREFIX}-' function, log group and role"]
    if not aws.allowed(execute, cl):
        return plan
    if delete_log_groups not in ("auto", "always", "never"):
        raise ValueError("delete_log_groups must be 'auto', 'always' or 'never'")
    mp = os.path.join(run_dir, "manifest.json")
    man = aws.load_manifest(mp) if os.path.exists(mp) else {}
    cl = _clients(cl)
    lam, logs, iam = cl["lambda"], cl["logs"], cl["iam"]
    keep = delete_log_groups == "never" or (delete_log_groups == "auto" and not aws.coverage_complete(run_dir))
    names = set(man.get("functions", {}))
    for p in lam.get_paginator("list_functions").paginate():
        for f in p["Functions"]:
            if f["FunctionName"].startswith(PREFIX + "-") and _tagged(lam, f["FunctionName"]):
                names.add(f["FunctionName"])
    groups = set(man.get("log_groups", [])) | {f"/aws/lambda/{fn}" for fn in names}
    for fn in sorted(names):
        aws._ignore(lam.delete_function, "ResourceNotFoundException", FunctionName=fn)
    retained = []
    for lg in sorted(groups):
        if keep:
            retained.append(lg)
        else:
            aws._ignore(logs.delete_log_group, "ResourceNotFoundException", logGroupName=lg)
    if keep:
        present = set(leftovers(cl)["log_groups"])
        retained = [g for g in retained if g in present]
        for lg in retained:
            aws._ignore(logs.put_retention_policy, "ResourceNotFoundException", logGroupName=lg,
                        retentionInDays=LOG_RETENTION_DAYS)
        if man:
            man["retained_log_groups"] = {"groups": retained, "retention_days": LOG_RETENTION_DAYS,
                                          "wall_ns": time.time_ns(),
                                          "reason": "REPORT coverage not complete" if delete_log_groups == "auto"
                                          else "delete_log_groups='never'"}
            aws._save(man, mp)
    aws._ignore(iam.detach_role_policy, "NoSuchEntity", RoleName=ROLE, PolicyArn=BASIC_POLICY)
    aws._ignore(iam.delete_role, "NoSuchEntity", RoleName=ROLE)
    left = leftovers(cl)
    plan.append(f"remaining after teardown: {left}")
    if retained:
        plan.append(f"RETAINED {len(retained)} log groups ({LOG_RETENTION_DAYS}-day retention): REPORT coverage is not "
                    "verified complete. Resume collection, re-check coverage, then run cleanup-logs.")
    others = dict(left, log_groups=[g for g in left["log_groups"] if g not in retained])
    plan.append("NOT CLEAN: delete the listed resources by hand and re-run verify" if any(others.values()) else
                ("CLEAN except the retained log groups" if retained else "CLEAN"))
    return plan


def cleanup_logs(run_dir: str, execute: bool = False, cl=None, force: bool = False) -> List[str]:
    plan = [f"logs.delete_log_group for this campaign's /aws/lambda/{PREFIX}-* groups, only if REPORT coverage is "
            "complete (or with --force-delete-incomplete)"]
    if not aws.allowed(execute, cl):
        return plan
    mp = os.path.join(run_dir, "manifest.json")
    man = aws.load_manifest(mp)
    if not aws.coverage_complete(run_dir) and not force:
        plan.append("REFUSED: REPORT coverage is not complete; run collect and coverage first")
        return plan
    cl = _clients(cl)
    owned = sorted({g for g in man.get("log_groups", []) + (man.get("retained_log_groups") or {}).get("groups", [])
                    if g.startswith(f"/aws/lambda/{PREFIX}-")})
    for lg in owned:
        aws._ignore(cl["logs"].delete_log_group, "ResourceNotFoundException", logGroupName=lg)
    man["retained_log_groups"] = dict(man.get("retained_log_groups") or {}, deleted=owned, deleted_wall_ns=time.time_ns(),
                                      forced=bool(force and not aws.coverage_complete(run_dir)))
    aws._save(man, mp)
    left = leftovers(cl)
    plan.append(f"deleted (or already absent) {len(owned)} log groups; remaining: {left}")
    plan.append("CLEAN" if not any(left.values()) else "NOT CLEAN: delete the listed resources by hand and re-run verify")
    return plan


def verify(execute: bool = False, cl=None) -> List[str]:
    plan = [f"list '{PREFIX}-' functions, log groups and the role in {REGION} (read only)"]
    if not aws.allowed(execute, cl):
        return plan
    left = leftovers(_clients(cl))
    plan.append(f"remaining: {left}")
    plan.append("CLEAN" if not any(left.values()) else "NOT CLEAN")
    return plan


# --------------------------------------------------------------------------- estimate
def estimate(scenarios: Optional[Dict[str, dict]] = None) -> dict:
    """Invocations, billable GB-seconds and list-price cost of the campaign (smoke included). Billed Duration includes
    the INIT phase (observed on all 44 REPORTs of run livetest_20261122-090236, ceil(Duration + Init)), so the
    'init billed' figures are the planning figures. Actual charges must be reconciled with the bill later."""
    from prism_measure.estimate import estimate as est
    scenarios = scenarios or {
        "in_region_client": {"platform_cold_s": 0.3, "client_overhead_s": 0.05, "update_wait_s": 5.0},
        "laptop_wan_planning": {"platform_cold_s": 1.0, "client_overhead_s": 0.25, "update_wait_s": 10.0}}
    inputs = stage_inputs()
    resp = {s: len(json.dumps(inputs[STAGES[i + 1]]).encode()) if i + 1 < len(STAGES) else 2_000
            for i, s in enumerate(STAGES)}
    out = {"prices": PRICES, "scenarios": {}}
    for smoke in (True, False):
        d = build(smoke)
        n = sum(v.cold + sum(v.warm_batches) for v in d.visits)
        cold = sum(v.cold for v in d.visits)
        resp_bytes = sum((v.cold + sum(v.warm_batches)) * (resp[v.cell.variant] + 5_600) for v in d.visits)
        log_bytes = n * (1_150 + 4 * 26) + cold * 300
        key = "smoke" if smoke else "campaign"
        for name, sc in scenarios.items():
            e = est(d, WARM_MEAN_1024, price_gb_s=PRICES["lambda_gb_s_x86_tier1"],
                    price_request=PRICES["lambda_request"], **sc)
            out["scenarios"].setdefault(name, {})[key] = {
                "assumptions": sc, "invocations": n, "cold_invocations": cold, "visits": len(d.visits),
                "config_updates": len(d.visits),
                "models": {m: {"billed_gb_s_incl_init": round(v["billed_gb_s"] + v["init_gb_s_if_billed"], 1),
                               "lambda_usd": v["cost_usd_if_init_billed"], "active_hours": v["active_hours"],
                               "active_hours_per_block": v["active_hours_per_block"]}
                           for m, v in e["models"].items()},
                "requests_usd": round(n * PRICES["lambda_request"], 4),
                "logs_ingest_gb": round(log_bytes / 1e9, 4),
                "logs_usd": round(log_bytes / 1e9 * PRICES["logs_ingest_per_gb"]
                                  + log_bytes / 1e9 * PRICES["logs_storage_per_gb_month"] * LOG_RETENTION_DAYS / 30, 4),
                "response_bytes_gb": round(resp_bytes / 1e9, 3),
                "data_transfer_usd_upper_unverified": round(resp_bytes / 1e9 * DATA_TRANSFER_OUT_PER_GB_UNVERIFIED, 3)}
    for name, sc in out["scenarios"].items():
        tot = sc["campaign"]["models"]
        worst = max(tot.values(), key=lambda v: v["lambda_usd"])
        sworst = max(sc["smoke"]["models"].values(), key=lambda v: v["lambda_usd"])
        sc["planning_upper_usd"] = round(worst["lambda_usd"] + sworst["lambda_usd"]
                                         + sc["campaign"]["logs_usd"] + sc["smoke"]["logs_usd"]
                                         + sc["campaign"]["data_transfer_usd_upper_unverified"], 2)
    return out


# --------------------------------------------------------------------------- analysis
def _boot_median(rows, f, n_boot, rng):
    vals = [f(r) for r in rows if f(r) is not None]
    if not vals:
        return math.nan, (math.nan, math.nan)
    import numpy as np
    groups: Dict[str, list] = {}
    for r in rows:
        if f(r) is not None:
            groups.setdefault(r["batch_id"], []).append(f(r))
    keys = sorted(groups)
    reps = [float(np.median([x for k in rng.integers(0, len(keys), len(keys)) for x in groups[keys[k]]]))
            for _ in range(n_boot)]
    return float(np.median(vals)), (float(np.quantile(reps, 0.025)), float(np.quantile(reps, 0.975)))


def _fit_form(sizes, values):
    """Least squares in logs of v(m) = a * (ns + (1 - ns) * 1024 / m), ns in [0, 1] (Eq. (2), and Eq. (3) as
    implemented: init_factor = duration_factor(m, init_nonscaling)). Returns (a, ns, rms_log_error)."""
    import numpy as np
    y = np.log(np.asarray(values, float))
    best = None
    for ns in np.linspace(0, 1, 1001):
        x = np.log(ns + (1 - ns) * 1024.0 / np.asarray(sizes, float))
        la = float(np.mean(y - x))
        sse = float(np.sum((y - x - la) ** 2))
        if best is None or sse < best[2] - 1e-15:
            best = (math.exp(la), float(ns), sse)
    return best[0], best[1], math.sqrt(best[2] / len(sizes))


def _pred(a, ns, m):
    return a * (ns + (1 - ns) * 1024.0 / m)


def analyse(run_dir: str, out_dir: str, n_boot: int = 2000, seed: int = 1) -> dict:
    import numpy as np
    from prism_measure import analyse as A
    from prism_repro.config import Prices
    recs = aws._jsonl(os.path.join(run_dir, RECORDS))
    smoke_ids = {r.get("request_id") for r in aws._jsonl(os.path.join(run_dir, SMOKE_DIR, RECORDS))}
    cw = {r["request_id"]: r for r in aws._jsonl(os.path.join(run_dir, aws.REPORTS_FILE))
          if r["request_id"] not in smoke_ids}                # smoke REPORTs are not campaign orphans
    doc = aws.load_manifest(os.path.join(run_dir, DESIGN_FILE))
    split = doc["split"]
    prices = Prices(od=PRICES["lambda_gb_s_x86_tier1"], req=PRICES["lambda_request"])
    sub = {name: [r for r in recs if r.get("visit_id") is None or split.get(r["visit_id"]) == name]
           for name in ("fit", "check")}
    res = {name: A.analyse(rs, cw, n_boot=n_boot, seed=seed, prices=prices) for name, rs in sub.items()}
    res["all"] = A.analyse(recs, cw, n_boot=n_boot, seed=seed, prices=prices)
    for name, r in res.items():
        A.write_outputs(r, os.path.join(out_dir, name))
    rng = np.random.default_rng(seed + 7)
    cells = {name: {(c["variant"], c["memory_mb"]): c for c in res[name]["cells"]} for name in ("fit", "check")}
    warm = {}
    for name in ("fit", "check"):
        for st in STAGES:
            for m in SIZES:
                rows = [r for r in res[name]["rows"] if r["variant"] == st and r["memory_mb"] == m and A.usable(r, "warm")]
                warm[(name, st, m)] = _boot_median(rows, A._dur, n_boot, rng)
    checks, calib = [], {"warm_eq2": {}, "init_eq3_P_mean": {}, "init_eq3_I": {}}
    for st in STAGES + ("POOLED",):
        members = STAGES if st == "POOLED" else (st,)
        if st != "POOLED":
            y = [warm[("fit", st, m)][0] for m in SIZES]
            if all(math.isfinite(v) and v > 0 for v in y):
                a, ns, rms = _fit_form(SIZES, y)
                calib["warm_eq2"][st] = {"d1024_s": a, "nonscaling": ns, "rms_log_error": rms,
                                         "ratio_3008_over_2048": y[3] / y[2]}
                for m in SIZES:
                    obs, (lo, hi) = warm[("check", st, m)]
                    p = _pred(a, ns, m)
                    checks.append({"quantity": "warm Duration median (Eq. 2 form)", "stage": st, "memory_mb": m,
                                   "fit_split_value": round(warm[("fit", st, m)][0], 6), "predicted": round(p, 6),
                                   "check_observed": round(obs, 6), "check_lo": round(lo, 6), "check_hi": round(hi, 6),
                                   "rel_error": round(p / obs - 1, 4) if obs else math.nan,
                                   "inside_check_interval": bool(lo <= p <= hi)})
        for q, key in (("P_mean", "init_eq3_P_mean"), ("I", "init_eq3_I")):
            y = [float(np.mean([cells["fit"][(s, m)][f"{q}_s"] for s in members])) for m in SIZES]
            if not all(math.isfinite(v) and v > 0 for v in y):
                calib[key][st] = {"fit": "not estimable (non-positive or missing value)"}
                continue
            a, ns, rms = _fit_form(SIZES, y)
            calib[key][st] = {"at_1024_s": a, "init_nonscaling": ns, "rms_log_error": rms,
                              "boundary": ns in (0.0, 1.0), "measured_candidate": [[m, round(v, 4)]
                                                                                   for m, v in zip(SIZES, y)]}
            for m, yv in zip(SIZES, y):
                if st == "POOLED":
                    continue
                c = cells["check"][(st, m)]
                obs, lo, hi = c[f"{q}_s"], c[f"{q}_lo"], c[f"{q}_hi"]
                for form, p in (("Eq. 3 form", _pred(a, ns, m)), ("measured mode (fit-split mean)", yv)):
                    checks.append({"quantity": f"{q} ({form})", "stage": st, "memory_mb": m,
                                   "fit_split_value": round(yv, 6), "predicted": round(p, 6),
                                   "check_observed": obs, "check_lo": lo, "check_hi": hi,
                                   "rel_error": round(p / obs - 1, 4) if obs else math.nan,
                                   "inside_check_interval": bool(lo <= p <= hi)})
    # trend comparison: Lambda-reported init (I) against the full first-call penalty (P), fit split only
    reps = {}
    for st in STAGES:
        for m in SIZES:
            rs = [r for r in res["fit"]["rows"] if r["variant"] == st and r["memory_mb"] == m]
            reps[(st, m)] = A.cell_stats([r for r in rs if A.usable(r, "cold")], [r for r in rs if A.usable(r, "warm")],
                                         n_boot, rng)["reps"]
    trend = []
    s_eq = A.eq3_slope(SIZES)
    tr_fit = {(t["variant"]): t for t in res["fit"]["trends"]}
    for st in STAGES + ("POOLED",):
        members = STAGES if st == "POOLED" else (st,)
        sl = {}
        for q in ("I", "P"):
            arr = np.array([[np.mean([reps[(s, m)][q][i] for s in members]) for m in SIZES] for i in range(n_boot)])
            sl[q] = np.array([A._slope(SIZES, a) for a in arr])
        diff = sl["P"] - sl["I"]
        ok = np.isfinite(diff)
        lo, hi = (float(np.quantile(diff[ok], 0.025)), float(np.quantile(diff[ok], 0.975))) if ok.all() else (math.nan,) * 2
        t = tr_fit.get(st, {})
        reading = ("not estimable" if not math.isfinite(lo) else
                   "P and I trends differ: Eq. (3) must name which quantity it models (the model's initialisation is "
                   "the full first-call penalty P)" if (lo > 0 or hi < 0) else
                   "no detectable difference between the P and I trends")
        trend.append({"stage": st, "eq3_slope": round(s_eq, 4), "I_slope": t.get("I_slope"),
                      "I_slope_lo": t.get("I_slope_lo"), "I_slope_hi": t.get("I_slope_hi"), "P_slope": t.get("P_slope"),
                      "P_slope_lo": t.get("P_slope_lo"), "P_slope_hi": t.get("P_slope_hi"),
                      "P_minus_I_slope_lo": round(lo, 4) if math.isfinite(lo) else lo,
                      "P_minus_I_slope_hi": round(hi, 4) if math.isfinite(hi) else hi,
                      "reading": reading, "decision_on_P": t.get("decision_on_P")})
    os.makedirs(out_dir, exist_ok=True)
    for name, rows in (("calibration_check", checks), ("trend_compare", trend)):
        if rows:
            with open(os.path.join(out_dir, f"{name}.csv"), "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
    with open(os.path.join(out_dir, "calibration.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(calib, f, indent=1, default=float)
    rv: Dict[str, set] = {}
    for r in recs:
        if r.get("type") == "invocation" and (r.get("payload") or {}).get("first_call"):
            rv.setdefault(f"block {r['block']}", set()).add((r.get("tail_extra") or {}).get("runtime_version")
                                                            or "not in tail")
    summary = {"runtime_versions_by_block": {k: sorted(v) for k, v in sorted(rv.items())},
               "runtime_changed_during_campaign": len({x for v in rv.values() for x in v}) > 1,
               "invocations": {n: sum(1 for r in sub[n] if r.get("type") == "invocation") for n in sub},
               "issues": res["all"]["issues"], "reports_from_cloudwatch": len(cw),
               "check_rows": len(checks), "check_inside_interval": sum(c["inside_check_interval"] for c in checks),
               "trend": trend}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1, default=str)
    return {"calibration": calib, "checks": checks, "trend": trend, "summary": summary}


# --------------------------------------------------------------------------- local dry run on the fakes
def dry_run(out_dir: str, k_scale: float = 0.001, smoke_only: bool = False, drop_cloudwatch: int = 0) -> dict:
    """The whole campaign on the in-process fakes (real handler code, K scaled down so it runs in minutes; host
    timings, NOT AWS measurements). Sockets are blocked. drop_cloudwatch > 0 deletes that many REPORT lines from the
    fake CloudWatch before collection, to exercise the retain-on-missing path."""
    from .fake import fake_cloud
    real = socket.socket

    class Blocked(real):
        def __init__(self, *a, **k):
            raise RuntimeError("network access attempted in the memcal dry run")
    socket.socket = Blocked
    try:
        cl = fake_cloud(account_limit=10)
        info = prepare(out_dir)
        log = {"prepare": info, "preflight": preflight(execute=True, cl=cl),
               "deploy": deploy(out_dir, execute=True, cl=cl, sleep=lambda s: None, k_scale=k_scale)[-1:]}
        log["smoke"] = run(out_dir, execute=True, cl=cl, smoke=True, sleep=lambda s: None)[1:]
        if not smoke_only:
            for b in range(BLOCKS):
                log[f"block_{b}"] = run(out_dir, [b], execute=True, cl=cl, sleep=lambda s: None)[1:]
        if drop_cloudwatch:
            ev = cl["logs"].events
            dropped = 0
            for g in sorted(ev):
                keep = []
                for e in ev[g]:
                    if dropped < drop_cloudwatch and e["message"].startswith("REPORT RequestId"):
                        dropped += 1
                        continue
                    keep.append(e)
                ev[g] = keep
            log["dropped_cloudwatch_reports"] = dropped
        log["collect"] = collect(out_dir, execute=True, cl=cl, sleep=lambda s: None)[1:]
        log["coverage"] = {k: v for k, v in report_coverage(out_dir).items() if k != "missing_ids"}
        log["teardown"] = teardown(out_dir, execute=True, cl=cl)[4:]
        log["cleanup_logs"] = cleanup_logs(out_dir, execute=True, cl=cl)[1:]
        log["verify"] = verify(execute=True, cl=cl)[1:]
        log["fake_lambda"] = {"calls": cl["lambda"].calls, "max_in_flight": cl["lambda"].max_in_flight,
                              "throttles": cl["lambda"].throttles, "updates": cl["lambda"].updates}
    finally:
        socket.socket = real
    with open(os.path.join(out_dir, "dry_run_log.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, indent=1, default=str)
    return log


# --------------------------------------------------------------------------- command line
def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python -m prism_pipeline.memcal")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "deploy", "smoke", "run", "collect", "coverage", "teardown", "cleanup-logs", "analyse"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True, help="campaign run directory (outside Git)")
        if name in ("deploy", "smoke", "run", "collect", "teardown", "cleanup-logs"):
            s.add_argument("--execute", action="store_true", help="really call AWS (also needs PRISM_AWS_AUTHORIZED)")
        if name in ("smoke", "run"):
            s.add_argument("--host-note", default="")
        if name == "run":
            s.add_argument("--block", type=int, action="append", required=True)
        if name == "collect":
            s.add_argument("--rescan", action="store_true")
        if name == "teardown":
            s.add_argument("--delete-log-groups", choices=("auto", "always", "never"), default="auto")
        if name == "cleanup-logs":
            s.add_argument("--force-delete-incomplete", action="store_true")
        if name == "analyse":
            s.add_argument("--out", required=True)
            s.add_argument("--n-boot", type=int, default=2000)
    for name in ("preflight", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--execute", action="store_true")
    s = sub.add_parser("estimate")
    s.add_argument("--out")
    s = sub.add_parser("dry-run")
    s.add_argument("--out", required=True)
    s.add_argument("--smoke-only", action="store_true")
    s.add_argument("--k-scale", type=float, default=0.001)
    s.add_argument("--drop-cloudwatch", type=int, default=0)
    a = p.parse_args(argv)
    ex = getattr(a, "execute", False)
    if a.cmd == "prepare":
        print(json.dumps(prepare(a.run), indent=1))
        return 0
    if a.cmd == "estimate":
        e = estimate()
        if a.out:
            with open(a.out, "w", encoding="utf-8", newline="\n") as f:
                json.dump(e, f, indent=1)
        print(json.dumps(e, indent=1))
        return 0
    if a.cmd == "dry-run":
        os.makedirs(a.out, exist_ok=True)
        print(json.dumps(dry_run(a.out, a.k_scale, a.smoke_only, a.drop_cloudwatch), indent=1, default=str))
        return 0
    if a.cmd == "coverage":
        c = report_coverage(a.run)
        print(json.dumps({k: v for k, v in c.items() if k != "missing_ids"}, indent=1))
        return 0 if c["complete"] else 3
    if a.cmd == "analyse":
        r = analyse(a.run, a.out, a.n_boot)
        print(json.dumps(r["summary"], indent=1, default=str))
        return 0
    plan = {"preflight": lambda: preflight(ex), "verify": lambda: verify(ex),
            "deploy": lambda: deploy(a.run, ex), "smoke": lambda: run(a.run, None, ex, smoke=True, host_note=a.host_note),
            "run": lambda: run(a.run, a.block, ex, host_note=a.host_note),
            "collect": lambda: collect(a.run, ex, rescan=a.rescan),
            "teardown": lambda: teardown(a.run, ex, delete_log_groups=a.delete_log_groups),
            "cleanup-logs": lambda: cleanup_logs(a.run, ex, force=a.force_delete_incomplete)}[a.cmd]()
    print(("EXECUTED:\n" if ex else "PLAN ONLY (no AWS call made):\n") + "\n".join(f"  {x}" for x in plan))
    return 1 if any(str(x).startswith(("STOP", "NOT CLEAN", "REFUSED")) for x in plan) else 0


if __name__ == "__main__":
    sys.exit(main())
