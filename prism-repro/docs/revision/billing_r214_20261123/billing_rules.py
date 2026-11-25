#!/usr/bin/env python3
"""R2.14(a): per-invocation AWS Lambda billing rules that are verified against AWS's own records, as a tested module.

Verified rule (memcal-1, 22 Nov 2026, 21,248 REPORT records, prism-repro/docs/revision/aws_memcal_20261122/RESULTS.md):
  on-demand Billed Duration = floor(Duration + Init Duration) + 1 ms
i.e. the sum rounded up to the next whole millisecond, and one millisecond more when the sum is already whole (94 of the
21,248 records; the other 21,154 equal ceil(Duration + Init)). Initialisation is billed for on-demand invocations that
report it. Charge = billed seconds x memory GB x the duration price + the request price.

Not implemented here, because the rules or the inputs are not verified locally:
  - provisioned-concurrency (PC) billing increments and activation timing (no PC was configured in any saved run;
    the repository has no sourced rule for them: docs/PRICING_PROVENANCE.md lists only the per-GB-s prices);
  - recycling of PC environments (no observed recycling; no sourced rule);
  - whether initialisation of PC environments is charged (no PC run; the simulator charges none).

Prices default to the manuscript's (prism_repro.config.Prices; USD 1.66667e-5 per GB-s on demand, 9.7222e-6 per GB-s
PC duration, 2e-7 per request), which are not claimed to be current provider prices.
"""
import math

OD_GBS, PCD_GBS, REQ = 1.66667e-5, 9.7222e-6, 2e-7


def billed_ms(duration_ms, init_ms=0.0):
    """On-demand billed duration in whole ms: floor(Duration + Init) + 1 (verified on 21,248 REPORT records)."""
    s = float(duration_ms) + float(init_ms)
    if s < 0 or not math.isfinite(s):
        raise ValueError("duration must be finite and non-negative")
    return int(math.floor(s + 1e-9)) + 1


def gb_seconds(billed, memory_mb):
    return billed / 1000.0 * memory_mb / 1024.0


def charge(duration_ms, init_ms, memory_mb, gbs_price=OD_GBS, req_price=REQ):
    """USD for one on-demand invocation: billed GB-s x price + request fee."""
    return gb_seconds(billed_ms(duration_ms, init_ms), memory_mb) * gbs_price + req_price


def rounding_increment_ms(duration_ms, init_ms=0.0):
    """Billed minus unrounded duration, in ms: in (0, 1], 1 exactly when the sum is a whole number."""
    return billed_ms(duration_ms, init_ms) - (float(duration_ms) + float(init_ms))
