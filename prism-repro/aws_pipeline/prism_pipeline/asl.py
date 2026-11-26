"""Step Functions EXPRESS state machine for the four-stage pipeline (synchronous: StartSyncExecution).

Why Express, synchronous: each record carries its own deadline and the caller waits for the result (the use case of
SPEC.md); an Express workflow runs at most 5 minutes, which covers the 14.5 s deadline with a wide margin, and is
billed per request and duration rather than per state transition.

Each stage is a Task whose Resource is the function ARN, so the function's return value becomes the next state's
input unchanged (no ResultSelector wrapping). There is NO Retry: a failed stage fails the execution, which the
driver records (a silent retry would hide a failure and lengthen the record's latency without trace, as the
measurement harness also avoids). Logging is OFF: the stages' own CloudWatch logs and the execution output carry the
timing, so no Step Functions log group is created (one fewer resource to clean up).
"""
from __future__ import annotations

import json
from typing import Dict, Sequence

STAGES = ("ingest", "transform", "aggregate", "load")
TASK_TIMEOUT_S = 60                     # equals the functions' timeout


def definition(function_arns: Dict[str, str], stages: Sequence[str] = STAGES, timeout_s: int = 120) -> dict:
    if set(stages) - set(function_arns):
        raise ValueError(f"missing function ARNs for {sorted(set(stages) - set(function_arns))}")
    states = {}
    for i, s in enumerate(stages):
        st = {"Type": "Task", "Resource": function_arns[s], "TimeoutSeconds": TASK_TIMEOUT_S,
              "Comment": f"PRISM stage {i + 1} of {len(stages)}: {s}"}
        if i + 1 < len(stages):
            st["Next"] = stages[i + 1]
        else:
            st["End"] = True
        states[s] = st
    return {"Comment": "PRISM four-stage pipeline (proposed document-ingestion workload, aws_pipeline/SPEC.md)",
            "StartAt": stages[0], "TimeoutSeconds": timeout_s, "States": states}


def definition_json(function_arns: Dict[str, str], **kw) -> str:
    return json.dumps(definition(function_arns, **kw), indent=1)


def validate(defn: dict) -> None:
    """Structural checks of the subset of ASL used here (a linear chain of Task states)."""
    st = defn["States"]
    cur, seen = defn["StartAt"], []
    while True:
        if cur not in st or cur in seen:
            raise ValueError(f"bad chain at {cur!r}")
        seen.append(cur)
        s = st[cur]
        if s["Type"] != "Task" or "Retry" in s or not s["Resource"].startswith("arn:aws:lambda:"):
            raise ValueError(f"state {cur!r} is not a plain Lambda Task without Retry")
        if s.get("End"):
            break
        cur = s["Next"]
    if len(seen) != len(st):
        raise ValueError("unreachable states")
