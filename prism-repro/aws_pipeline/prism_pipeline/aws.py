"""AWS actions for a SEPARATELY AUTHORISED live test. Not executed in the preparation pass.

Guard (shared with the measurement harness, prism_measure.aws.authorised): every action takes `execute`; with
execute=False it returns the list of calls it would make and touches nothing. With execute=True it also needs
PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES, and only then are clients built (boto3 imported lazily). Tests pass fakes
through `cl=` instead of building clients; the guard still applies.

Scope: every resource is named "prism-pipe-..." and tagged project=prism-pipeline. Teardown deletes only what the
manifest lists plus anything else carrying BOTH that prefix and that tag; it never touches the measurement harness's
"prism-meas-" resources or anything untagged. Created per test:
  IAM   prism-pipe-lambda-role (AWSLambdaBasicExecutionRole), prism-pipe-sfn-role (inline: lambda:InvokeFunction on
        the four functions only)
  Lambda prism-pipe-ingest / -transform / -aggregate / -load (python3.12, x86_64, 1024 MB, timeout 60 s)
  Logs  /aws/lambda/prism-pipe-<stage> (created first, 7-day retention)
  Step Functions  prism-pipe-docpipe (EXPRESS, logging OFF)
No S3 bucket, queue, table, VPC, alias, version or provisioned concurrency is created (sink "none").
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from typing import Dict, List, Optional

from . import asl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "aws_measurement"))
from prism_measure.aws import AUTH_ENV, AUTH_VALUE, authorised  # noqa: E402,F401  (same guard, reused)
from prism_measure.report import parse_report_line  # noqa: E402

PREFIX = "prism-pipe"
TAG = {"project": "prism-pipeline"}
DEFAULT_REGION = "us-east-2"
LAMBDA_ROLE, SFN_ROLE = f"{PREFIX}-lambda-role", f"{PREFIX}-sfn-role"
STATE_MACHINE = f"{PREFIX}-docpipe"
RUNTIME, ARCH, TIMEOUT_S, LOG_RETENTION_DAYS, DEFAULT_MEMORY = "python3.12", "x86_64", 60, 7, 1024
BASIC_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
HANDLER_FILE = os.path.join(os.path.dirname(__file__), "..", "handlers", "docpipe.py")
STAGES = asl.STAGES
CAP_MAX = 8


def allowed(execute: bool, cl=None) -> bool:
    """The real guard, except that a client set made ONLY of local fakes (IS_FAKE) needs no authorisation."""
    if cl is not None and cl and all(getattr(c, "IS_FAKE", False) for c in cl.values()):
        return True
    return authorised(execute)


def function_name(stage: str) -> str:
    return f"{PREFIX}-{stage}"


def functions() -> Dict[str, str]:
    return {s: function_name(s) for s in STAGES}


def _code(e) -> Optional[str]:
    return (getattr(e, "response", None) or {}).get("Error", {}).get("Code")


def _ignore(fn, *codes, **kw):
    try:
        return fn(**kw)
    except Exception as e:                                    # noqa: BLE001  (only the named codes are swallowed)
        if _code(e) in codes:
            return None
        raise


AWS_VENV_SITE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "aws_measurement", ".venv-aws",
                                             "Lib", "site-packages"))


def clients(region: str):
    try:                                                      # imported only on an authorised run
        import boto3
    except ImportError:                                       # the project venv has no boto3: use the harness's
        sys.path.append(AWS_VENV_SITE)
        import boto3
    from botocore.config import Config
    cfg = Config(region_name=region, retries={"mode": "standard", "max_attempts": 1},
                 read_timeout=300, connect_timeout=10, max_pool_connections=CAP_MAX + 4)
    return {n: boto3.client(n, config=cfg) for n in ("lambda", "logs", "iam", "sts", "stepfunctions")}


def package() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HANDLER_FILE, "docpipe.py")
    return buf.getvalue()


def base_environment(stage: str, k: int = 1, init_rows: int = 0, sink: str = "none", calibration: bool = True):
    return {"PRISM_STAGE": stage, "PRISM_K": str(int(k)), "PRISM_INIT_ROWS": str(int(init_rows)),
            "PRISM_SINK": sink, "PRISM_CALIBRATION": "1" if calibration else "0", "PRISM_COLD_NONCE": "initial"}


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(manifest, path):
    with open(path, "w", encoding="utf-8") as f:              # after every created resource: resumable teardown
        json.dump(manifest, f, indent=1)


# --------------------------------------------------------------------------- read-only checks
def preflight(region: str = DEFAULT_REGION, execute: bool = False, cl=None) -> List[str]:
    plan = ["sts.get_caller_identity", "lambda.get_account_settings (ConcurrentExecutions, Unreserved...)",
            f"lambda.list_functions, stepfunctions.list_state_machines, iam.get_role: any '{PREFIX}-' leftover"]
    if not allowed(execute, cl):
        return plan
    cl = cl or clients(region)
    acct = cl["sts"].get_caller_identity()["Account"]
    lim = cl["lambda"].get_account_settings()["AccountLimit"]
    left = leftovers(cl)
    plan.append(f"account {acct} region {region}: ConcurrentExecutions={lim.get('ConcurrentExecutions')}, "
                f"UnreservedConcurrentExecutions={lim.get('UnreservedConcurrentExecutions')}; leftovers={left}")
    if (lim.get("ConcurrentExecutions") or 0) < CAP_MAX + 2:
        plan.append(f"STOP: the account limit is below the cap plus headroom ({CAP_MAX + 2})")
    if any(left.values()):
        plan.append("STOP: run teardown first")
    return plan


def leftovers(cl) -> Dict[str, list]:
    fns = [f["FunctionName"] for p in cl["lambda"].get_paginator("list_functions").paginate()
           for f in p["Functions"] if f["FunctionName"].startswith(PREFIX + "-")]
    sms = [m["name"] for p in cl["stepfunctions"].get_paginator("list_state_machines").paginate()
           for m in p["stateMachines"] if m["name"].startswith(PREFIX + "-")]
    lgs = [g["logGroupName"] for p in cl["logs"].get_paginator("describe_log_groups").paginate(
        logGroupNamePrefix=f"/aws/lambda/{PREFIX}-") for g in p["logGroups"]]
    roles = [r for r in (LAMBDA_ROLE, SFN_ROLE) if _ignore(cl["iam"].get_role, "NoSuchEntity", RoleName=r)]
    return {"functions": fns, "state_machines": sms, "log_groups": lgs, "roles": roles}


def verify(region: str = DEFAULT_REGION, execute: bool = False, cl=None) -> List[str]:
    """Read-only: list every remaining prism-pipe- function, state machine, log group and role."""
    plan = [f"list '{PREFIX}-' functions, state machines, log groups and roles in {region} (read only)"]
    if not allowed(execute, cl):
        return plan
    left = leftovers(cl or clients(region))
    plan.append(f"remaining: {left}")
    plan.append("CLEAN" if not any(left.values()) else "NOT CLEAN")
    return plan


# --------------------------------------------------------------------------- deploy
def deploy(manifest_path: str, region: str = DEFAULT_REGION, execute: bool = False, memory_mb: int = DEFAULT_MEMORY,
           init_rows: int = 0, sink: str = "none", cl=None, sleep=time.sleep) -> List[str]:
    if sink != "none":
        raise ValueError("the prepared live test uses sink 'none'; an S3 sink needs a bucket (decision P4)")
    plan = [f"iam.create_role {LAMBDA_ROLE} (trust lambda.amazonaws.com) + attach {BASIC_POLICY}",
            f"iam.create_role {SFN_ROLE} (trust states.amazonaws.com) + put_role_policy lambda:InvokeFunction on the "
            "four function ARNs"]
    for s in STAGES:
        plan.append(f"logs.create_log_group /aws/lambda/{function_name(s)} retention={LOG_RETENTION_DAYS} d tags={TAG}")
        plan.append(f"lambda.create_function {function_name(s)} handler=docpipe.{s} runtime={RUNTIME} arch={ARCH} "
                    f"memory={memory_mb} MB timeout={TIMEOUT_S}s env={base_environment(s, init_rows=init_rows)}")
    plan.append(f"stepfunctions.create_state_machine {STATE_MACHINE} type=EXPRESS logging=OFF "
                f"definition=asl.definition(4 Task states, no Retry)")
    if not allowed(execute, cl):
        return plan
    cl = cl or clients(region)
    iam, lam, logs, sfn = cl["iam"], cl["lambda"], cl["logs"], cl["stepfunctions"]
    acct = cl["sts"].get_caller_identity()["Account"]
    tags_iam = [{"Key": k, "Value": v} for k, v in TAG.items()]
    man = {"region": region, "account": acct, "prefix": PREFIX, "tag": TAG, "created_wall_ns": time.time_ns(),
           "roles": {}, "functions": {}, "log_groups": [], "state_machine": None, "memory_mb": memory_mb,
           "init_rows": init_rows, "sink": sink}
    _save(man, manifest_path)

    def role(name, service, attach=None, inline=None):
        trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": service},
                                                         "Action": "sts:AssumeRole"}]}
        try:
            arn = iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust), Tags=tags_iam)["Role"]["Arn"]
        except Exception as e:                                # noqa: BLE001
            if _code(e) != "EntityAlreadyExists":
                raise
            arn = iam.get_role(RoleName=name)["Role"]["Arn"]
        man["roles"][name] = arn
        _save(man, manifest_path)
        if attach:
            iam.attach_role_policy(RoleName=name, PolicyArn=attach)
        if inline:
            iam.put_role_policy(RoleName=name, PolicyName=f"{name}-invoke", PolicyDocument=json.dumps(inline))
        return arn

    lrole = role(LAMBDA_ROLE, "lambda.amazonaws.com", attach=BASIC_POLICY)
    code = package()
    arns = {}
    for s in STAGES:
        fn = function_name(s)
        lg = f"/aws/lambda/{fn}"
        _ignore(logs.create_log_group, "ResourceAlreadyExistsException", logGroupName=lg, tags=TAG)
        logs.put_retention_policy(logGroupName=lg, retentionInDays=LOG_RETENTION_DAYS)
        if lg not in man["log_groups"]:
            man["log_groups"].append(lg)
        _save(man, manifest_path)
        env = base_environment(s, init_rows=init_rows, sink=sink)
        for attempt in range(8):                              # a new role takes a few seconds to become assumable
            try:
                r = lam.create_function(FunctionName=fn, Runtime=RUNTIME, Role=lrole, Handler=f"docpipe.{s}",
                                        Code={"ZipFile": code}, Timeout=TIMEOUT_S, MemorySize=memory_mb,
                                        Architectures=[ARCH], Environment={"Variables": env}, Tags=TAG)
                break
            except Exception as e:                            # noqa: BLE001
                if _code(e) != "InvalidParameterValueException" or attempt == 7:
                    raise
                sleep(10)
        arns[s] = r["FunctionArn"]
        man["functions"][fn] = {"stage": s, "arn": r["FunctionArn"], "memory_mb": memory_mb, "env": env}
        _save(man, manifest_path)
        from .campaign import wait_updated
        wait_updated(lam, fn, sleep=sleep)
    inline = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "lambda:InvokeFunction",
                                                      "Resource": [arns[s] for s in STAGES]}]}
    srole = role(SFN_ROLE, "states.amazonaws.com", inline=inline)
    defn = asl.definition(arns)
    asl.validate(defn)
    for attempt in range(8):
        try:
            sm = sfn.create_state_machine(name=STATE_MACHINE, definition=json.dumps(defn), roleArn=srole,
                                          type="EXPRESS", loggingConfiguration={"level": "OFF"},
                                          tags=[{"key": k, "value": v} for k, v in TAG.items()])
            break
        except Exception as e:                                # noqa: BLE001  (new role not yet assumable)
            if _code(e) not in ("AccessDeniedException", "InvalidDefinition") or attempt == 7:
                raise
            sleep(10)
    man["state_machine"] = sm["stateMachineArn"]
    man["definition"] = defn
    _save(man, manifest_path)
    return plan


# --------------------------------------------------------------------------- REPORT lines from CloudWatch
def collect_reports(manifest_path: str, start_ms: int, end_ms: int, execute: bool = False, cl=None) -> List[str]:
    """Every REPORT line of the four log groups in [start_ms, end_ms], one paginated filter per group.
    Returns the plan; with execute, also writes <manifest dir>/cloudwatch_reports.jsonl."""
    plan = [f"logs.filter_log_events on /aws/lambda/{function_name(s)} pattern '\"REPORT RequestId\"' "
            f"[{start_ms}, {end_ms}] (paginated)" for s in STAGES]
    if not allowed(execute, cl):
        return plan
    man = load_manifest(manifest_path)
    cl = cl or clients(man["region"])
    out = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "cloudwatch_reports.jsonl")
    n = 0
    with open(out, "a", encoding="utf-8") as f:
        for lg in man["log_groups"]:
            kw = dict(logGroupName=lg, filterPattern='"REPORT RequestId"', startTime=int(start_ms),
                      endTime=int(end_ms))
            while True:
                page = cl["logs"].filter_log_events(**kw)
                for e in page.get("events", []):
                    rep = parse_report_line(e["message"])
                    if rep:
                        rep["log_group"] = lg
                        f.write(json.dumps(rep) + "\n")
                        n += 1
                tok = page.get("nextToken")
                if not tok:
                    break
                kw["nextToken"] = tok
    plan.append(f"wrote {n} REPORT records to {out}")
    return plan


# --------------------------------------------------------------------------- teardown and verification
def _tagged_function(lam, fn) -> bool:
    try:
        arn = lam.get_function_configuration(FunctionName=fn)["FunctionArn"]
        return lam.list_tags(Resource=arn).get("Tags", {}).get("project") == TAG["project"]
    except Exception as e:                                    # noqa: BLE001
        if _code(e) == "ResourceNotFoundException":
            return False
        raise


def teardown(manifest_path: Optional[str], region: str = DEFAULT_REGION, execute: bool = False, cl=None) -> List[str]:
    plan = [f"stepfunctions.delete_state_machine {STATE_MACHINE}",
            f"lambda.delete_function {', '.join(functions().values())} (manifest, or prefix '{PREFIX}-' AND tag {TAG})",
            f"logs.delete_log_group /aws/lambda/{PREFIX}-<stage> for each",
            f"iam: delete inline policy, detach {BASIC_POLICY}, delete roles {LAMBDA_ROLE}, {SFN_ROLE}",
            "then verify: list every remaining 'prism-pipe-' function, state machine, log group and role"]
    if not allowed(execute, cl):
        return plan
    man = load_manifest(manifest_path) if manifest_path and os.path.exists(manifest_path) else {}
    cl = cl or clients(man.get("region", region))
    lam, logs, iam, sfn = cl["lambda"], cl["logs"], cl["iam"], cl["stepfunctions"]
    sm_arns = {man["state_machine"]} if man.get("state_machine") else set()
    for p in sfn.get_paginator("list_state_machines").paginate():
        for m in p["stateMachines"]:
            if m["name"] == STATE_MACHINE:
                tags = {t["key"]: t["value"] for t in sfn.list_tags_for_resource(resourceArn=m["stateMachineArn"])
                        .get("tags", [])}
                if tags.get("project") == TAG["project"]:
                    sm_arns.add(m["stateMachineArn"])
    for arn in sorted(sm_arns):
        _ignore(sfn.delete_state_machine, "StateMachineDoesNotExist", stateMachineArn=arn)
    names = set(man.get("functions", {}))
    for p in lam.get_paginator("list_functions").paginate():
        for f in p["Functions"]:
            if f["FunctionName"].startswith(PREFIX + "-") and _tagged_function(lam, f["FunctionName"]):
                names.add(f["FunctionName"])
    for fn in sorted(names):
        _ignore(lam.delete_function, "ResourceNotFoundException", FunctionName=fn)
        _ignore(logs.delete_log_group, "ResourceNotFoundException", logGroupName=f"/aws/lambda/{fn}")
    for lg in man.get("log_groups", []):
        _ignore(logs.delete_log_group, "ResourceNotFoundException", logGroupName=lg)
    _ignore(iam.delete_role_policy, "NoSuchEntity", RoleName=SFN_ROLE, PolicyName=f"{SFN_ROLE}-invoke")
    _ignore(iam.detach_role_policy, "NoSuchEntity", RoleName=LAMBDA_ROLE, PolicyArn=BASIC_POLICY)
    for r in (LAMBDA_ROLE, SFN_ROLE):
        _ignore(iam.delete_role, "NoSuchEntity", RoleName=r)
    left = leftovers(cl)
    plan.append(f"remaining after teardown: {left}")
    if any(left.values()):
        plan.append("NOT CLEAN: delete the listed resources by hand and re-run verify")
    return plan
