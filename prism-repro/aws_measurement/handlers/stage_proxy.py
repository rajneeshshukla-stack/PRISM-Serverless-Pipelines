"""PROXY WORKLOAD for the PRISM init-vs-memory campaign (R1.2, R2.8, R3.1, R4.3, R5.M2, R6.2).

This is NOT PRISM stage code. The repository specifies PRISM's four stages only statistically (names
ingest/transform/aggregate/load, warm-time means 0.8/4.0/2.5/1.2 s at 1024 MB, log-normal spread, Eq. (2) memory
scaling, one stage-independent initialisation; prism_repro.config.PipelineConfig). It does not specify what any stage
computes, its dependencies, package, runtime or I/O. This handler stands in with deterministic, single-threaded CPU
work (a SHA-256 chain), so the measurements describe how AWS Lambda times and bills CPU-bound work at each memory
size, not PRISM's real stages.

Environment variables (set by the harness at deployment and calibration):
  PRISM_STAGE             label only (ingest/transform/aggregate/load or an init variant)
  PRISM_WORK_UNITS        SHA-256 iterations per invocation (calibrated to the stage's warm mean at 1024 MB)
  PRISM_INIT_UNITS        iterations at module scope, i.e. inside Lambda's reported INIT phase (variant init_module)
  PRISM_FIRST_CALL_UNITS  iterations on the first invocation of an environment only (variant init_first_call)
  PRISM_COLD_NONCE        changed by the harness to retire every warm environment before a cold batch

Standard library only. Prints nothing, so the log tail returned to the harness holds only START/END/REPORT.
"""
import hashlib
import os
import time
import uuid

_T0 = time.perf_counter()
ENV_ID = uuid.uuid4().hex                      # one per execution environment: a new value means a cold start
LABEL = "PROXY WORKLOAD: synthetic CPU work standing in for a PRISM stage; not PRISM stage code"


def _spin(units):
    h = b"prism-proxy"
    for _ in range(int(units)):
        h = hashlib.sha256(h).digest()
    return h[:4].hex()


_spin(os.environ.get("PRISM_INIT_UNITS", "0"))             # module scope: runs inside the INIT phase
MODULE_INIT_S = time.perf_counter() - _T0
_FIRST = True


def handler(event, context):
    global _FIRST
    t0 = time.perf_counter()
    first, _FIRST = _FIRST, False
    _spin(os.environ.get("PRISM_FIRST_CALL_UNITS", "0") if first else 0)
    t1 = time.perf_counter()
    units = (event or {}).get("work_units", os.environ.get("PRISM_WORK_UNITS", "0"))
    _spin(units)
    t2 = time.perf_counter()
    return {
        "label": LABEL,
        "stage": os.environ.get("PRISM_STAGE", "proxy"),
        "env_id": ENV_ID,
        "first_call": first,
        "module_init_s": MODULE_INIT_S,
        "first_call_work_s": t1 - t0,
        "work_s": t2 - t1,
        "work_units": int(units),
        "nonce": os.environ.get("PRISM_COLD_NONCE", ""),
        "aws_request_id": getattr(context, "aws_request_id", None),
    }
