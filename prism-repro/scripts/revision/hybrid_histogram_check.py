#!/usr/bin/env python3
"""R3.2: what the hybrid histogram policy of Shahrad et al. (USENIX ATC 2020, Section 4.2) would decide on the
paper's workloads. Read-only on the traces; no policy of PRISM's is run. EXPLORATORY.

The policy acts on one application's idle times (ITs) between invocations, in a range-limited histogram of 1-minute bins
(4-hour range); pre-warming window = 5th percentile of the ITs (rounded down to a bin), keep-alive window = 99th
percentile (rounded up), with a 10% margin (pre-warm x 0.9, keep-alive x 1.1); if the coefficient of variation of the
bin counts is below 2, pre-warm 0 and keep-alive = range. ARIMA (for out-of-bounds ITs) is not reproduced: no trace
here has an IT beyond the 4-hour range. The paper models one loaded image per application and states that cold starts
from load spikes, where new instances are needed, are not considered.

Approximation, at minute resolution: ITs inside an active minute and between consecutive active minutes are below 1
minute (bin 0); a run of z empty minutes gives one IT of about z + 1 minutes. The histogram is built offline from the
whole trace (the paper learns it online), and app-level cold starts are counted as in the paper's simulator
(execution time 0; an invocation is cold if the IT exceeds the keep-alive window, with pre-warm 0 as computed here).
usage (from prism-repro/): python scripts/revision/hybrid_histogram_check.py . <region2 derived dir> <out file>"""
import glob, json, math, os, sys
import numpy as np
ROOT = os.path.abspath(sys.argv[1]); sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro.trace_io import load_minute_csv
from prism_repro.workload import SCENARIOS, generate_trace
RANGE_MIN, HEAD, TAIL, MARGIN, CV_MIN = 240, 5, 99, 0.10, 2.0


def its(counts):
    c = np.asarray(counts, dtype=np.int64)
    n = int(c.sum())
    gaps, z, active_seen = [], 0, False
    for v in c:
        if v == 0:
            z += 1
        else:
            if active_seen and z > 0:
                gaps.append(z + 1)
            z, active_seen = 0, True
    bin0 = n - 1 - len(gaps)                      # every other IT is under a minute
    return bin0, gaps


def windows(bin0, gaps):
    hist = np.zeros(RANGE_MIN, dtype=np.int64)
    hist[0] = bin0
    oob = 0
    for g in gaps:
        if g < RANGE_MIN:
            hist[int(g)] += 1
        else:
            oob += 1
    cv = hist.std() / hist.mean() if hist.mean() > 0 else 0.0
    if cv < CV_MIN:
        return dict(mode="standard keep-alive", prewarm_min=0.0, keepalive_min=float(RANGE_MIN), cv=float(cv), oob=oob)
    cum = np.cumsum(hist) / hist.sum()
    head = int(np.searchsorted(cum, HEAD / 100))            # bin index, i.e. rounded down to the bin's lower edge
    tail = int(np.searchsorted(cum, TAIL / 100)) + 1        # rounded up to the bin's upper edge
    return dict(mode="histogram", prewarm_min=head * (1 - MARGIN), keepalive_min=tail * (1 + MARGIN), cv=float(cv), oob=oob)


def cold_share(bin0, gaps, keepalive_min):
    n = bin0 + len(gaps) + 1
    return (1 + sum(1 for g in gaps if g > keepalive_min)) / n


traces = []
for s in (101, 102, 103, 104, 105):
    for sc in SCENARIOS:
        traces.append((f"synthetic {s} {sc}", generate_trace(s, sc)["counts"][:28 * 1440]))
for fn in ("150", "72", "60", "183", "42"):
    traces.append((f"Huawei Private 2023 fn{fn} (R1)", load_minute_csv(os.path.join(ROOT, "data", "real", f"huawei_fn{fn}.csv"))[:28 * 1440]))
for p in sorted(glob.glob(os.path.join(sys.argv[2], "r2_*.csv"))):
    traces.append((f"Huawei Public 2025 Region 2 {os.path.basename(p)[:-4]}", load_minute_csv(p)[:28 * 1440]))
out = []
for name, c in traces:
    b0, g = its(c)
    w = windows(b0, g)
    out.append(dict(trace=name, minutes=len(c), min_count=int(np.min(c)), empty_minutes=int((np.asarray(c) == 0).sum()),
                    longest_idle_min=max(g) if g else 0, its_of_1min_or_more=len(g), **w,
                    app_cold_share_hybrid=cold_share(b0, g, w["keepalive_min"]), app_cold_share_fixed10=cold_share(b0, g, 10)))
L = ["HYBRID HISTOGRAM POLICY (Shahrad et al. 2020, Sec. 4.2) ON THE PAPER'S WORKLOADS; minute-resolution approximation; EXPLORATORY", ""]
for r in out:
    L.append(f"  {r['trace']:46s} min/minute {r['min_count']:5d}  empty minutes {r['empty_minutes']:5d}  longest idle {r['longest_idle_min']:4d} min  "
             f"-> {r['mode']}, pre-warm {r['prewarm_min']:.1f} min, keep-alive {r['keepalive_min']:.1f} min; app cold starts: hybrid "
             f"{100*r['app_cold_share_hybrid']:.4f}%, fixed 10 min {100*r['app_cold_share_fixed10']:.4f}%")
no_idle = [r for r in out if r["its_of_1min_or_more"] == 0]
L += ["", f"Traces with no idle time of a minute or more: {len(no_idle)} of {len(out)} (all ITs in bin 0: pre-warm 0, keep-alive 1.1 min; "
      "the single application image is never unloaded, i.e. the policy equals 'no unloading', and decides nothing about concurrent instances)."]
txt = "\n".join(L) + "\n"
open(sys.argv[3], "w", encoding="utf-8", newline="\n").write(txt)
json.dump(out, open(sys.argv[3].replace(".txt", ".json"), "w", encoding="utf-8"), indent=1)
print(txt)
