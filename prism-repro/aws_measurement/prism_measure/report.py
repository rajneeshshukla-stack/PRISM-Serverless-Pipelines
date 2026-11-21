"""Parse Lambda's plain-text REPORT log line (one per invocation; `Init Duration` appears only on cold starts).

Example: "REPORT RequestId: 8f5c...\tDuration: 812.32 ms\tBilled Duration: 813 ms\tMemory Size: 1024 MB\t
          Max Memory Used: 41 MB\tInit Duration: 152.07 ms"
Functions must use Lambda's default text log format; the JSON log format is not parsed here.
"""
from __future__ import annotations

import base64
import re
from typing import Dict, Optional

_ID = re.compile(r"REPORT RequestId:\s*([0-9A-Za-z-]+)")
_FIELDS = {                     # plain "Duration:" is parsed by position in _duration()
    "billed_duration_ms": re.compile(r"Billed Duration:\s*([0-9.]+)\s*ms"),
    "memory_size_mb": re.compile(r"Memory Size:\s*([0-9]+)\s*MB"),
    "max_memory_used_mb": re.compile(r"Max Memory Used:\s*([0-9]+)\s*MB"),
    "init_duration_ms": re.compile(r"Init Duration:\s*([0-9.]+)\s*ms"),
    "restore_duration_ms": re.compile(r"Restore Duration:\s*([0-9.]+)\s*ms"),
}
REQUIRED = ("duration_ms", "billed_duration_ms", "memory_size_mb", "max_memory_used_mb")


def _duration(line: str) -> Optional[float]:
    # "Duration:" also occurs inside "Billed Duration:", "Init Duration:" and "Restore Duration:"; take the field
    # that follows the request ID, i.e. the first tab-separated "Duration:" field.
    for part in line.split("\t"):
        part = part.strip()
        if part.startswith("Duration:"):
            m = re.match(r"Duration:\s*([0-9.]+)\s*ms", part)
            return float(m.group(1)) if m else None
    return None


def parse_report_line(line: str) -> Optional[Dict]:
    m = _ID.search(line or "")
    if not m:
        return None
    rec = {"request_id": m.group(1), "duration_ms": _duration(line)}
    for k, rx in _FIELDS.items():
        f = rx.search(line)
        rec[k] = (int(f.group(1)) if k.endswith("_mb") else float(f.group(1))) if f else None
    rec["complete"] = all(rec.get(k) is not None for k in REQUIRED)
    return rec


def parse_log_tail(log_result_b64: Optional[str]) -> Optional[Dict]:
    """Decode the base64 `LogResult` of a RequestResponse invoke with LogType=Tail (last 4 KB of the log) and
    return its REPORT record, or None if the tail has no REPORT line (truncated or missing)."""
    if not log_result_b64:
        return None
    try:
        text = base64.b64decode(log_result_b64).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return None
    found = None
    for line in text.splitlines():
        if line.startswith("REPORT RequestId:"):
            found = parse_report_line(line)
    return found


def format_report_line(request_id: str, duration_ms: float, billed_ms: float, memory_mb: int, max_used_mb: int,
                       init_ms: Optional[float] = None) -> str:
    """The line Lambda writes (used by the fake client and the fixtures)."""
    s = (f"REPORT RequestId: {request_id}\tDuration: {duration_ms:.2f} ms\tBilled Duration: {billed_ms:.0f} ms\t"
         f"Memory Size: {memory_mb} MB\tMax Memory Used: {max_used_mb} MB\t")
    if init_ms is not None:
        s += f"Init Duration: {init_ms:.2f} ms\t"
    return s
