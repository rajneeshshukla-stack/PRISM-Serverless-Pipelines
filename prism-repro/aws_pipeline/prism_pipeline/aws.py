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

REPORT lines (22 Nov 2026 fix): collect_reports saves each page before recording its token and resumes after a
failure; report_coverage checks every recorded request ID against the saved REPORTs; teardown keeps this run's log
groups (7-day retention) unless that check passed, and cleanup_log_groups deletes them afterwards.
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
# Run livetest_20261121-203051 lost every REPORT line: the first filter_log_events call failed on a credential refresh
# (EndpointConnectionError on the sign-in token endpoint), nothing had been saved, and teardown then deleted the log
# groups. Collection is therefore page-by-page and resumable, its completeness is checked against the request IDs
# the arms recorded, and teardown keeps this run's log groups unless that check passed.
REPORTS_FILE, COLLECT_STATE_FILE, COVERAGE_FILE = "cloudwatch_reports.jsonl", "cloudwatch_collect_state.json", \
    "cloudwatch_coverage.json"
COLLECT_ATTEMPTS = 5                  # per page; backoff 1, 2, 4, 8 s between attempts
ARMS_WITH_RECORDS = ("smoke", "baseline_ondemand", "adapter_schedule")


def _run_dir(manifest_path: str) -> str:
    return os.path.dirname(os.path.abspath(manifest_path))


def _atomic_json(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _jsonl(path) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def collect_reports(manifest_path: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None,
                    execute: bool = False, cl=None, attempts: int = COLLECT_ATTEMPTS, sleep=time.sleep,
                    rescan: bool = False) -> List[str]:
    """Every REPORT line of the run's log groups in [start_ms, end_ms], fetched page by page.

    Each page's REPORT records are appended to <run dir>/cloudwatch_reports.jsonl and flushed to disk BEFORE the
    page's nextToken is saved to cloudwatch_collect_state.json, so an interruption loses at most the page in flight.
    A failed page is retried `attempts` times; if it still fails, the state is saved, the status is 'incomplete' and
    the function returns without raising. Calling it again resumes from the saved token and window (start_ms and
    end_ms are then ignored); a request ID already in the file is never written twice, so a page re-fetched after a
    crash adds nothing. rescan=True re-reads every group from the start (for REPORT lines delivered late); duplicates
    are still skipped. An expired token (InvalidParameterException) restarts that group, also without duplicates.
    Returns the plan; with execute, the last line is 'collection complete' or 'collection INCOMPLETE ...'."""
    plan = [f"logs.filter_log_events on /aws/lambda/{function_name(s)} pattern '\"REPORT RequestId\"' "
            f"[{start_ms}, {end_ms}] (paginated; each page saved and flushed before its token is recorded; "
            f"up to {attempts} attempts per page; resumable)" for s in STAGES]
    if not allowed(execute, cl):
        return plan
    man = load_manifest(manifest_path)
    rd = _run_dir(manifest_path)
    out, state_path = os.path.join(rd, REPORTS_FILE), os.path.join(rd, COLLECT_STATE_FILE)
    state = load_manifest(state_path) if os.path.exists(state_path) else None
    if state is None:
        if start_ms is None or end_ms is None:
            raise ValueError("a first collection needs start_ms and end_ms")
        state = {"window_ms": [int(start_ms), int(end_ms)], "groups": {}, "calls": 0}
    lo, hi = state["window_ms"]
    state["calls"] = state.get("calls", 0) + 1
    if rescan:
        for g in state["groups"].values():
            g.update(next_token=None, done=False)
    have = {r["request_id"] for r in _jsonl(out)}
    cl = cl or clients(man["region"])
    new, status, err = 0, "complete", None
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        for lg in man["log_groups"]:
            g = state["groups"].setdefault(lg, {"next_token": None, "done": False, "pages": 0, "written": 0,
                                                "skipped_duplicates": 0, "retries": 0})
            while not g["done"]:
                kw = dict(logGroupName=lg, filterPattern='"REPORT RequestId"', startTime=int(lo), endTime=int(hi))
                if g["next_token"]:
                    kw["nextToken"] = g["next_token"]
                page, last = None, None
                for a in range(attempts):
                    try:
                        page = cl["logs"].filter_log_events(**kw)
                        break
                    except Exception as e:                    # noqa: BLE001  (bounded; recorded; resumable)
                        last = e
                        g["retries"] += 1
                        if _code(e) == "InvalidParameterException" and kw.get("nextToken"):
                            kw.pop("nextToken")               # expired token: restart the group, duplicates skipped
                            g["next_token"] = None
                            continue
                        if a + 1 < attempts:
                            sleep(min(2 ** a, 30))
                if page is None:
                    status, err = "incomplete", f"{type(last).__name__}: {last}"
                    g["last_error"] = err
                    break
                for e in page.get("events", []):
                    rep = parse_report_line(e["message"])
                    if not rep:
                        continue
                    if rep["request_id"] in have:
                        g["skipped_duplicates"] += 1
                        continue
                    rep["log_group"] = lg
                    f.write(json.dumps(rep) + "\n")
                    have.add(rep["request_id"])
                    g["written"] += 1
                    new += 1
                f.flush()
                os.fsync(f.fileno())                          # the page is on disk before its token is recorded
                g["pages"] += 1
                g["next_token"] = page.get("nextToken")
                g["done"] = not g["next_token"]
                _atomic_json(state, state_path)
            if status == "incomplete":
                break
    done = all(state["groups"].get(lg, {}).get("done") for lg in man["log_groups"])
    state["status"] = "complete" if done else "incomplete"
    state["last_error"] = err
    _atomic_json(state, state_path)
    plan.append(f"wrote {new} new REPORT records to <run dir>/{REPORTS_FILE} ({len(have)} in total)")
    plan.append("collection complete" if done else
                f"collection INCOMPLETE ({err}); state saved in <run dir>/{COLLECT_STATE_FILE}; resume with: "
                f"python -m prism_pipeline collect --manifest <run dir>/manifest.json --execute")
    return plan


def report_coverage(run_dir: str, arms=ARMS_WITH_RECORDS) -> dict:
    """Local check: every Lambda request ID the arms recorded must have a captured REPORT. Writes and returns
    <run dir>/cloudwatch_coverage.json. complete = the collection finished, at least one ID was expected, and none is
    missing. REPORT lines without a recorded ID (calibration probes, other invocations) are counted as extras."""
    expected, no_id = {}, 0
    for arm in arms:
        for rec in _jsonl(os.path.join(run_dir, arm, "records.jsonl")):
            if rec.get("type") != "record":
                continue
            for st in rec.get("stages", []):
                rid = st.get("aws_request_id")
                if rid:
                    expected[rid] = {"arm": arm, "record_id": rec.get("record_id"), "stage": st.get("stage")}
                else:
                    no_id += 1
    captured = {r["request_id"] for r in _jsonl(os.path.join(run_dir, REPORTS_FILE))}
    sp = os.path.join(run_dir, COLLECT_STATE_FILE)
    status = load_manifest(sp).get("status", "unknown") if os.path.exists(sp) else "not collected"
    missing = sorted(set(expected) - captured)
    cov = {"arms": list(arms), "expected_request_ids": len(expected), "matched": len(expected) - len(missing),
           "missing": len(missing), "missing_ids": [dict(request_id=r, **expected[r]) for r in missing],
           "extra_reports": len(captured - set(expected)), "stage_rows_without_request_id": no_id,
           "collection_status": status}
    cov["complete"] = status == "complete" and bool(expected) and not missing
    _atomic_json(cov, os.path.join(run_dir, COVERAGE_FILE))
    return cov


def coverage_complete(run_dir: str) -> bool:
    p = os.path.join(run_dir, COVERAGE_FILE)
    return os.path.exists(p) and bool(load_manifest(p).get("complete"))


# --------------------------------------------------------------------------- teardown and verification
def _tagged_function(lam, fn) -> bool:
    try:
        arn = lam.get_function_configuration(FunctionName=fn)["FunctionArn"]
        return lam.list_tags(Resource=arn).get("Tags", {}).get("project") == TAG["project"]
    except Exception as e:                                    # noqa: BLE001
        if _code(e) == "ResourceNotFoundException":
            return False
        raise


def teardown(manifest_path: Optional[str], region: str = DEFAULT_REGION, execute: bool = False, cl=None,
             delete_log_groups: str = "auto") -> List[str]:
    """delete_log_groups: 'auto' (default) deletes the log groups only if <run dir>/cloudwatch_coverage.json says the
    REPORT collection is complete; otherwise this run's log groups are KEPT, with their LOG_RETENTION_DAYS retention
    re-applied, and listed under 'retained_log_groups' in the manifest (delete them later with cleanup_log_groups).
    'always' deletes them regardless (the old behaviour); 'never' keeps them."""
    plan = [f"stepfunctions.delete_state_machine {STATE_MACHINE}",
            f"lambda.delete_function {', '.join(functions().values())} (manifest, or prefix '{PREFIX}-' AND tag {TAG})",
            f"logs.delete_log_group /aws/lambda/{PREFIX}-<stage> for each, ONLY if REPORT coverage is complete "
            f"({COVERAGE_FILE}); otherwise kept with {LOG_RETENTION_DAYS}-day retention and listed in the manifest",
            f"iam: delete inline policy, detach {BASIC_POLICY}, delete roles {LAMBDA_ROLE}, {SFN_ROLE}",
            "then verify: list every remaining 'prism-pipe-' function, state machine, log group and role"]
    if not allowed(execute, cl):
        return plan
    if delete_log_groups not in ("auto", "always", "never"):
        raise ValueError("delete_log_groups must be 'auto', 'always' or 'never'")
    man = load_manifest(manifest_path) if manifest_path and os.path.exists(manifest_path) else {}
    cl = cl or clients(man.get("region", region))
    lam, logs, iam, sfn = cl["lambda"], cl["logs"], cl["iam"], cl["stepfunctions"]
    rd = _run_dir(manifest_path) if manifest_path else None
    keep_logs = delete_log_groups == "never" or (delete_log_groups == "auto" and not (rd and coverage_complete(rd)))
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
    retained = []
    for fn in sorted(names):
        _ignore(lam.delete_function, "ResourceNotFoundException", FunctionName=fn)
        if keep_logs:
            if f"/aws/lambda/{fn}" not in man.get("log_groups", []):
                retained.append(f"/aws/lambda/{fn}")
        else:
            _ignore(logs.delete_log_group, "ResourceNotFoundException", logGroupName=f"/aws/lambda/{fn}")
    for lg in man.get("log_groups", []):
        if keep_logs:
            retained.append(lg)
        else:
            _ignore(logs.delete_log_group, "ResourceNotFoundException", logGroupName=lg)
    if keep_logs:
        present = {g for g in leftovers_log_groups(cl)}
        retained = sorted(g for g in set(retained) if g in present)
        for lg in retained:                                   # bounded retention, even if it was changed by hand
            _ignore(logs.put_retention_policy, "ResourceNotFoundException", logGroupName=lg,
                    retentionInDays=LOG_RETENTION_DAYS)
        if manifest_path and man:
            man["retained_log_groups"] = {"groups": retained, "retention_days": LOG_RETENTION_DAYS,
                                          "wall_ns": time.time_ns(), "reason": "REPORT coverage not complete"
                                          if delete_log_groups == "auto" else "delete_log_groups='never'"}
            _save(man, manifest_path)
    _ignore(iam.delete_role_policy, "NoSuchEntity", RoleName=SFN_ROLE, PolicyName=f"{SFN_ROLE}-invoke")
    _ignore(iam.detach_role_policy, "NoSuchEntity", RoleName=LAMBDA_ROLE, PolicyArn=BASIC_POLICY)
    for r in (LAMBDA_ROLE, SFN_ROLE):
        _ignore(iam.delete_role, "NoSuchEntity", RoleName=r)
    left = leftovers(cl)
    plan.append(f"remaining after teardown: {left}")
    others = dict(left, log_groups=[g for g in left["log_groups"] if g not in retained])
    if retained:
        plan.append(f"RETAINED {len(retained)} log groups ({LOG_RETENTION_DAYS}-day retention) because REPORT "
                    f"collection is not verified complete: {retained}. Resume: python -m prism_pipeline collect "
                    "--manifest <run dir>/manifest.json --execute; then: python -m prism_pipeline cleanup-logs "
                    "--manifest <run dir>/manifest.json --execute")
    if any(others.values()):
        plan.append("NOT CLEAN: delete the listed resources by hand and re-run verify")
    return plan


def leftovers_log_groups(cl) -> List[str]:
    return [g["logGroupName"] for p in cl["logs"].get_paginator("describe_log_groups").paginate(
        logGroupNamePrefix=f"/aws/lambda/{PREFIX}-") for g in p["logGroups"]]


def cleanup_log_groups(manifest_path: str, region: str = DEFAULT_REGION, execute: bool = False, cl=None,
                       force: bool = False) -> List[str]:
    """Delete the log groups this run created (the manifest's 'log_groups', all under /aws/lambda/prism-pipe-) once
    REPORT coverage is complete. Refuses otherwise unless force=True. Touches nothing else."""
    plan = [f"logs.delete_log_group for the manifest's log groups (/aws/lambda/{PREFIX}-<stage>), only if "
            f"{COVERAGE_FILE} says complete (or with --force-delete-incomplete)"]
    if not allowed(execute, cl):
        return plan
    man = load_manifest(manifest_path)
    rd = _run_dir(manifest_path)
    if not coverage_complete(rd) and not force:
        cov = load_manifest(os.path.join(rd, COVERAGE_FILE)) if os.path.exists(os.path.join(rd, COVERAGE_FILE)) else {}
        plan.append(f"REFUSED: REPORT coverage is not complete (missing {cov.get('missing', '?')}, collection "
                    f"{cov.get('collection_status', 'not checked')}); run collect and coverage first, or pass "
                    "--force-delete-incomplete to delete the evidence anyway")
        return plan
    cl = cl or clients(man.get("region", region))
    owned = [g for g in man.get("log_groups", []) if g.startswith(f"/aws/lambda/{PREFIX}-")]
    owned += [g for g in (man.get("retained_log_groups") or {}).get("groups", [])
              if g.startswith(f"/aws/lambda/{PREFIX}-") and g not in owned]
    for lg in owned:
        _ignore(cl["logs"].delete_log_group, "ResourceNotFoundException", logGroupName=lg)
    man["retained_log_groups"] = dict(man.get("retained_log_groups") or {}, deleted_wall_ns=time.time_ns(),
                                      deleted=owned, forced=bool(force and not coverage_complete(rd)))
    _save(man, manifest_path)
    left = leftovers(cl)
    plan.append(f"deleted {len(owned)} log groups; remaining: {left}")
    plan.append("CLEAN" if not any(left.values()) else "NOT CLEAN: delete the listed resources by hand and re-run verify")
    return plan
