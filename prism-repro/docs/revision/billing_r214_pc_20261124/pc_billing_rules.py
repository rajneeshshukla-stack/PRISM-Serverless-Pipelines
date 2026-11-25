#!/usr/bin/env python3
"""R2.14(a): provisioned-concurrency (PC) billing components whose rules are stated by AWS, on top of the verified
on-demand rule in ../billing_r214_20261123/billing_rules.py (reused unchanged). No AWS call.

Sources, read 24 Nov 2026 (public pages; quotes in README.md):
  https://aws.amazon.com/lambda/pricing/ ; https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html

Implemented (rule stated by AWS):
  capacity     "calculated from the time you enable it on your function until it is disabled, rounded up to the
               nearest five minutes"; "You pay for the amount of concurrency you configure, and for the period of time
               you configure it"; USD 0.0000041667 per GB-s (examples in US East, N. Virginia). Billing starts when PC
               is ENABLED (configured), not when it becomes READY, so activation time is billed (activation timing).
  invocation   on PC: "Compute charges while Provisioned Concurrency is enabled", USD 0.0000097222 per GB-s, duration
               "rounded up to the nearest 1ms", plus requests at USD 0.20 per million.
  overflow     "If your function exceeds the configured concurrency, you will be billed for excess function execution
               at the rate outlined in the AWS Lambda Pricing section above": on-demand, using the measured on-demand
               rule (billing_rules.billed_ms: floor(Duration + Init) + 1 ms, initialisation billed).

NOT implemented, rule not stated (documented assumptions, README.md):
  U1 the charge for initialising PC environments ("Lambda bills you for initialization even if the environment
     instance never processes a request ... separate billing from initialization and invocation costs": no amount or
     rate is given);
  U2 re-initialisation after recycling ("periodically recycles the execution environments and re-runs your
     initialization code": frequency and billing not given);
  U3 how a change of the configured amount within one enabled period is rounded (one period rounded once, or each
     amount separately); both readings are computed (capacity_gb_s modes), and they coincide when every change falls
     on a 5-minute boundary (PRISM's epochs are 5 minutes);
  U4 the PC duration rounding is documented ("rounded up to the nearest 1ms") but not measured; the measured
     on-demand rule adds 1 ms to whole-ms sums, so the two differ only there;
  U5 free tier (account level; the pricing page says it "does not apply to functions enabling Provisioned
     Concurrency", while its first example applies it to the non-PC part).
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "billing_r214_20261123"))
from billing_rules import OD_GBS, REQ, billed_ms  # noqa: E402  (verified on-demand rule, reused unchanged)

PC_GBS = 0.0000041667        # capacity, per configured GB-s
PCD_GBS = 0.0000097222       # duration of invocations served by PC, per GB-s
FIVE_MIN = 300.0


def round_up_5min(seconds):
    if seconds < 0 or not math.isfinite(seconds):
        raise ValueError("period must be finite and non-negative")
    return math.ceil(seconds / FIVE_MIN - 1e-12) * FIVE_MIN


def capacity_gb_s(segments, memory_mb, mode="period"):
    """Configured GB-s for ONE enabled period, given as consecutive (start_s, end_s, concurrency) segments from
    enabling to disabling (concurrency > 0 throughout). mode 'period' (U3 reading 1): the whole period is rounded up
    to 5 minutes once, the extra time at the last segment's concurrency. mode 'segment' (U3 reading 2): each
    segment's duration is rounded up to 5 minutes separately."""
    if not segments:
        return 0.0
    for (a, b, c), nxt in zip(segments, list(segments[1:]) + [None]):
        if b < a or c <= 0 or (nxt is not None and abs(nxt[0] - b) > 1e-9):
            raise ValueError("segments must be consecutive, non-negative and with concurrency > 0")
    g = memory_mb / 1024.0
    if mode == "segment":
        return sum(c * g * round_up_5min(b - a) for a, b, c in segments)
    if mode != "period":
        raise ValueError(mode)
    exact = sum(c * g * (b - a) for a, b, c in segments)
    total = segments[-1][1] - segments[0][0]
    return exact + segments[-1][2] * g * (round_up_5min(total) - total)


def capacity_charge(segments, memory_mb, mode="period", price=PC_GBS):
    return capacity_gb_s(segments, memory_mb, mode) * price


def pc_invocation_billed_ms(duration_ms):
    """Documented rule for invocations on PC: duration rounded up to the nearest 1 ms (U4: not measured)."""
    d = float(duration_ms)
    if d < 0 or not math.isfinite(d):
        raise ValueError("duration must be finite and non-negative")
    return int(math.ceil(d - 1e-9)) if d > 0 else 0


def invocation_charge(duration_ms, memory_mb, on_pc, init_ms=0.0):
    """USD for one invocation: on PC at the PC duration price (no request-path initialisation), or overflow at the
    on-demand price with the measured on-demand rule (initialisation billed). Both pay the request fee."""
    g = memory_mb / 1024.0
    if on_pc:
        if init_ms:
            raise ValueError("an invocation served by a provisioned environment has no request-path initialisation")
        return pc_invocation_billed_ms(duration_ms) / 1000.0 * g * PCD_GBS + REQ
    return billed_ms(duration_ms, init_ms) / 1000.0 * g * OD_GBS + REQ


def unresolved_pc_initialisation(*_a, **_k):
    """U1, U2: not implemented; the rule is not stated by AWS. Callers must report these as unquantified."""
    raise NotImplementedError("PC environment initialisation and recycling charges: rule not stated (README U1, U2)")
