"""Real AWS actions for a SEPARATELY AUTHORISED run. Not executed in the preparation pass.

Every function takes `execute`. With execute=False (the default everywhere) it only returns the list of API calls it
would make. With execute=True it also requires the environment variable PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES, and
only then imports boto3 and calls AWS. All resources carry the tag project=prism-measurement and the name prefix
"prism-meas-", which teardown uses to find leftovers.
"""
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from typing import Dict, List, Optional

from .design import CAP_MAX, Design, function_environment
from .estimate import WARM_MEAN_1024
from .runner import fallback_reports

AUTH_ENV, AUTH_VALUE = "PRISM_AWS_AUTHORIZED", "I-ACCEPT-CHARGES"
TAG = {"project": "prism-measurement"}
ROLE = "prism-meas-lambda-role"
RUNTIME, ARCH, TIMEOUT_S, LOG_RETENTION_DAYS = "python3.12", "x86_64", 60, 7
HANDLER_FILE = os.path.join(os.path.dirname(__file__), "..", "handlers", "stage_proxy.py")
BASIC_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


def authorised(execute: bool) -> bool:
    if not execute:
        return False
    if os.environ.get(AUTH_ENV) != AUTH_VALUE:
        raise PermissionError(f"refusing to call AWS: set {AUTH_ENV}={AUTH_VALUE} to confirm the run is authorised "
                              "and its charges accepted")
    return True


def clients(region: str):
    import boto3                                         # imported only on an authorised run
    from botocore.config import Config
    cfg = Config(region_name=region, retries={"mode": "standard", "max_attempts": 1},   # no silent retries
                 read_timeout=300, connect_timeout=10, max_pool_connections=CAP_MAX + 2)
    return {"lambda": boto3.client("lambda", config=cfg), "logs": boto3.client("logs", config=cfg),
            "iam": boto3.client("iam", config=cfg), "sts": boto3.client("sts", config=cfg)}


def package() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HANDLER_FILE, "stage_proxy.py")
    return buf.getvalue()


def _wait_active(lam, fn: str, timeout_s: float = 300) -> None:
    t0 = time.monotonic()
    while True:
        c = lam.get_function_configuration(FunctionName=fn)
        if c.get("State") == "Active" and c.get("LastUpdateStatus") in (None, "Successful"):
            return
        if c.get("State") == "Failed" or c.get("LastUpdateStatus") == "Failed":
            raise RuntimeError(f"{fn}: {c.get('StateReason') or c.get('LastUpdateStatusReason')}")
        if time.monotonic() - t0 > timeout_s:
            raise TimeoutError(fn)
        time.sleep(2)


def preflight(region: str, execute: bool = False) -> List[str]:
    """Read-only checks before deploying: account concurrency limit and leftovers from an earlier run."""
    plan = ["sts.get_caller_identity", "lambda.get_account_settings (ConcurrentExecutions, UnreservedConcurrentExecutions)",
            "lambda.list_functions (any 'prism-meas-' function left from an earlier run)"]
    if not authorised(execute):
        return plan
    cl = clients(region)
    acct = cl["sts"].get_caller_identity()["Account"]
    lim = cl["lambda"].get_account_settings()["AccountLimit"]
    left = [f["FunctionName"] for p in cl["lambda"].get_paginator("list_functions").paginate()
            for f in p["Functions"] if f["FunctionName"].startswith("prism-meas-")]
    plan.append(f"account {acct}: ConcurrentExecutions={lim.get('ConcurrentExecutions')}, "
                f"UnreservedConcurrentExecutions={lim.get('UnreservedConcurrentExecutions')}; leftovers={left}")
    if (lim.get("ConcurrentExecutions") or 0) < CAP_MAX + 2:
        plan.append(f"STOP: the account limit is below the cap plus headroom ({CAP_MAX + 2})")
    if left:
        plan.append("STOP: run teardown first")
    return plan


def deploy(design: Design, region: str, manifest_path: str, execute: bool = False) -> List[str]:
    plan = [f"iam.create_role {ROLE} (trust lambda.amazonaws.com) + attach {BASIC_POLICY}"]
    for c in design.cells():
        plan.append(f"lambda.create_function {c.function} runtime={RUNTIME} arch={ARCH} memory={c.memory_mb} MB "
                    f"timeout={TIMEOUT_S}s env={function_environment(c)} tags={TAG}")
        plan.append(f"logs.create_log_group /aws/lambda/{c.function} retention={LOG_RETENTION_DAYS} d")
    if not authorised(execute):
        return plan
    cl = clients(region)
    iam, lam, logs = cl["iam"], cl["lambda"], cl["logs"]
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                                                     "Action": "sts:AssumeRole"}]}
    try:
        role_arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust),
                                   Tags=[{"Key": k, "Value": v} for k, v in TAG.items()])["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
    iam.attach_role_policy(RoleName=ROLE, PolicyArn=BASIC_POLICY)
    code = package()
    manifest = {"region": region, "role": ROLE, "role_arn": role_arn, "account": cl["sts"].get_caller_identity()["Account"],
                "runtime": RUNTIME, "architecture": ARCH, "functions": {}, "created_wall_ns": time.time_ns()}
    for c in design.cells():
        env = function_environment(c)
        for attempt in range(8):                        # a new role takes a few seconds to become assumable
            try:
                lam.create_function(FunctionName=c.function, Runtime=RUNTIME, Role=role_arn,
                                    Handler="stage_proxy.handler", Code={"ZipFile": code}, Timeout=TIMEOUT_S,
                                    MemorySize=c.memory_mb, Architectures=[ARCH],
                                    Environment={"Variables": env}, Tags=TAG)
                break
            except lam.exceptions.InvalidParameterValueException:
                if attempt == 7:
                    raise
                time.sleep(10)
        try:
            logs.create_log_group(logGroupName=f"/aws/lambda/{c.function}", tags=TAG)
        except logs.exceptions.ResourceAlreadyExistsException:
            pass
        logs.put_retention_policy(logGroupName=f"/aws/lambda/{c.function}", retentionInDays=LOG_RETENTION_DAYS)
        _wait_active(lam, c.function)
        manifest["functions"][c.function] = {"memory_mb": c.memory_mb, "group": c.group, "variant": c.variant,
                                             "env": env}
        with open(manifest_path, "w", encoding="utf-8") as f:     # written after every function: resumable teardown
            json.dump(manifest, f, indent=1)
    return plan


def calibrate(design: Design, manifest_path: str, execute: bool = False, init_target_s: float = 2.0,
              target_probe_s: float = 1.0, n: int = 7) -> List[str]:
    """Measure SHA-256 iterations per second on the 1024 MB 'aggregate' proxy (warm), then set every function's
    work units: stage proxies to their warm mean at 1024 MB, init proxies to init_target_s at 1024 MB. The units
    stay fixed across memory sizes, so measured durations show Lambda's own CPU scaling."""
    probe_fn = next(c.function for c in design.cells() if c.group == "main" and c.memory_mb == 1024)
    plan = [f"lambda.invoke {probe_fn} warm-up, then {n} warm probes with event work_units (adaptive)",
            "lambda.update_function_configuration on every function with calibrated PRISM_*_UNITS"]
    if not authorised(execute):
        return plan
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    lam = clients(manifest["region"])["lambda"]
    units, rates = 100_000, []
    lam.invoke(FunctionName=probe_fn, Payload=json.dumps({"work_units": 1000}).encode())
    for _ in range(n):
        p = json.loads(lam.invoke(FunctionName=probe_fn, Payload=json.dumps({"work_units": units}).encode())
                       ["Payload"].read())
        rates.append(units / max(p["work_s"], 1e-6))
        units = int(min(max(units * target_probe_s / max(p["work_s"], 1e-3), 10_000), 50_000_000))
    rates.sort()
    rate = rates[len(rates) // 2]
    manifest["calibration"] = {"probe_function": probe_fn, "rate_iter_per_s_1024": rate, "probes": rates,
                               "init_target_s": init_target_s, "warm_mean_1024": WARM_MEAN_1024}
    for c in design.cells():
        env = function_environment(c, {"cpu": rate}, WARM_MEAN_1024, init_target_s)
        lam.update_function_configuration(FunctionName=c.function, Environment={"Variables": env})
        _wait_active(lam, c.function)
        manifest["functions"][c.function]["env"] = env
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    return plan


def collect(records_path: str, manifest_path: str, out_path: str, execute: bool = False) -> List[str]:
    """CloudWatch fallback for invocations whose log tail had no REPORT line; writes {request_id: report} JSONL."""
    recs = [json.loads(l) for l in open(records_path, encoding="utf-8") if l.strip()]
    todo = [r for r in recs if r.get("type") == "invocation" and r.get("request_id") and not r.get("report")]
    plan = [f"logs.filter_log_events for {len(todo)} request IDs without a REPORT in the log tail"]
    if not authorised(execute):
        return plan
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    found = fallback_reports(clients(manifest["region"])["logs"], todo)
    with open(out_path, "a", encoding="utf-8") as f:
        for rep in found.values():
            f.write(json.dumps(rep) + "\n")
    return plan


def teardown(manifest_path: Optional[str], region: str, execute: bool = False) -> List[str]:
    plan = ["lambda.delete_function for every function in the manifest and every 'prism-meas-' function found",
            "logs.delete_log_group /aws/lambda/<function> for each",
            f"iam.detach_role_policy {BASIC_POLICY}; iam.delete_role {ROLE}"]
    if not authorised(execute):
        return plan
    cl = clients(region)
    lam, logs, iam = cl["lambda"], cl["logs"], cl["iam"]
    names = set()
    if manifest_path and os.path.exists(manifest_path):
        names |= set(json.load(open(manifest_path, encoding="utf-8"))["functions"])
    for page in lam.get_paginator("list_functions").paginate():
        names |= {f["FunctionName"] for f in page["Functions"] if f["FunctionName"].startswith("prism-meas-")}
    for fn in sorted(names):
        try:
            lam.delete_function(FunctionName=fn)
        except lam.exceptions.ResourceNotFoundException:
            pass
        try:
            logs.delete_log_group(logGroupName=f"/aws/lambda/{fn}")
        except logs.exceptions.ResourceNotFoundException:
            pass
    try:
        iam.detach_role_policy(RoleName=ROLE, PolicyArn=BASIC_POLICY)
        iam.delete_role(RoleName=ROLE)
    except iam.exceptions.NoSuchEntityException:
        pass
    return plan
