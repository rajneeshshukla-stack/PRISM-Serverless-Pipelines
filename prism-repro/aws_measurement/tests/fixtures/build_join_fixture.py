"""Writes join_fixture.jsonl and join_fixture_cloudwatch.jsonl (one cell, main/ingest/1024, every fault the join
must handle). Hand-computed expectations are in tests/test_harness.py::TestJoinFixture."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CELL = {"group": "main", "variant": "ingest", "memory_mb": 1024, "function": "prism-meas-ingest-1024"}


def rep(rid, dur_ms, init_ms=None, billed=None):
    return {"request_id": rid, "duration_ms": dur_ms, "billed_duration_ms": billed or float(int(dur_ms) + 1),
            "memory_size_mb": 1024, "max_memory_used_mb": 40, "init_duration_ms": init_ms,
            "restore_duration_ms": None, "complete": True}


def inv(visit, batch, kind, rid, e2e, report, first, payload_rid=None, error=None, attempt=0):
    payload = None if error else {"first_call": first, "aws_request_id": payload_rid or rid, "env_id": "e"}
    return dict(CELL, type="invocation", visit_id=visit, attempt=attempt, batch_id=batch, batch_kind=kind,
                request_id=rid, e2e_s=e2e, error=error, function_error=None, report=report,
                report_source="tail" if report else None, payload=payload, wall_start_ns=0)


recs = [
    # visit v1: cold batch (r1, r2, r3 - r3's REPORT only in CloudWatch), warm batch w1
    inv("v1", "v1-cold", "cold", "r1", 2.0, rep("r1", 1000, 300), True),
    inv("v1", "v1-cold", "cold", "r2", 2.2, rep("r2", 1100, 400), True),
    inv("v1", "v1-cold", "cold", "r3", 2.4, None, True),
    inv("v1", "v1-w1", "warm", "w1", 1.0, rep("w1", 800), False),
    inv("v1", "v1-w1", "warm", "w2", 1.2, rep("w2", 900), False),
    inv("v1", "v1-w1", "warm", "w3", 1.4, rep("w3", 1000), False),
    {"type": "visit_done", "visit_id": "v1", "attempt": 0},
    # visit v2: cold batch with a cold REPORT lacking Init Duration (r4) and an unexpected warm (r5)
    inv("v2", "v2-cold", "cold", "r4", 2.6, rep("r4", 1300), True),
    inv("v2", "v2-cold", "cold", "r5", 1.1, rep("r5", 900), False),
    # warm batch w2: duplicate request ID (r9 twice), payload ID mismatch (r10), REPORT ID mismatch (r11),
    # a throttled call (no request ID), and one clean warm (w5)
    inv("v2", "v2-w2", "warm", "r9", 1.6, rep("r9", 950), False),
    inv("v2", "v2-w2", "warm", "r9", 1.8, rep("r9", 960), False),
    inv("v2", "v2-w2", "warm", "r10", 1.7, rep("r10", 970), False, payload_rid="zzz"),
    inv("v2", "v2-w2", "warm", "r11", 1.9, rep("r99", 980), False),
    inv("v2", "v2-w2", "warm", None, 0.01, None, None, error="FakeThrottle: Rate Exceeded"),
    inv("v2", "v2-w2", "warm", "w5", 1.6, rep("w5", 1100), False),
    {"type": "visit_done", "visit_id": "v2", "attempt": 0},
    # visit v3 never completed: dropped by the join
    inv("v3", "v3-cold", "cold", "r20", 9.9, rep("r20", 9000, 9000), True),
]
cloudwatch = [rep("r3", 1200, 500), rep("r77", 1000, 100)]          # r77: orphan, no invocation record

if __name__ == "__main__":
    with open(os.path.join(HERE, "join_fixture.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r) + "\n" for r in recs)
    with open(os.path.join(HERE, "join_fixture_cloudwatch.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r) + "\n" for r in cloudwatch)
    print(len(recs), "records,", len(cloudwatch), "cloudwatch reports")
