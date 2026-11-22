"""Record streams for the deployed pipeline. Deterministic from a seed, so a baseline arm and a controlled arm run the
SAME records (same record IDs, documents, sizes and arrival offsets).

Two arrival modes:
  poisson  a homogeneous Poisson stream at `rate_per_min` (the smallest live test)
  trace    the paper's synthetic trace (prism_repro.workload.generate_trace), a slice of minutes, each arrival kept
           with probability `thin` (independent thinning keeps a Poisson-type stream Poisson). The live account's
           quota of 10 cannot carry 600 records/min x about 9 s per record (about 90 executions in flight), so a
           trace run is always a THINNED replay; the controller sees counts divided by `thin` (adapter.count_scale).
Document size: log-normal with the stated MEAN and sigma of the log (the D01 convention of PipelineConfig), so the
stage times, which are proportional to document length, inherit the paper's log-normal spread (decision P2).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import List, Optional, Sequence

DEADLINE_S = 14.5                     # prism_repro.config.PipelineConfig.deadline, per record, end to end
MEAN_WORDS = 3000                     # decision P2: mean document length (words); about 20 KB of text
SIGMA_WORDS = 0.30                    # sigma of log document length = PipelineConfig.exec_shape


@dataclass(frozen=True)
class Record:
    record_id: str
    doc_seed: int
    n_words: int
    offset_s: float                   # arrival time after the start of the arm

    def to_dict(self):
        return asdict(self)


def _size(rng: random.Random, mean_words: float, sigma: float) -> int:
    mu = math.log(mean_words) - sigma * sigma / 2.0
    return max(int(round(rng.lognormvariate(mu, sigma))), 20)


def poisson_stream(n: int, rate_per_min: float, seed: int, mean_words: float = MEAN_WORDS,
                   sigma: float = SIGMA_WORDS, start_s: float = 0.0) -> List[Record]:
    if n < 1 or rate_per_min <= 0:
        raise ValueError("need n >= 1 and a positive rate")
    rng = random.Random(seed)
    t, out = start_s, []
    for i in range(n):
        t += rng.expovariate(rate_per_min / 60.0)
        out.append(Record(f"r{seed}-{i:05d}", rng.getrandbits(48), _size(rng, mean_words, sigma), round(t, 6)))
    return out


def thinned_counts(counts: Sequence[int], thin: float, seed: int) -> List[int]:
    if not 0 < thin <= 1:
        raise ValueError("thin must be in (0, 1]")
    rng = random.Random(seed)
    return [sum(1 for _ in range(int(c)) if rng.random() < thin) for c in counts]


def trace_stream(counts_per_bin: Sequence[int], bin_s: float, seed: int, mean_words: float = MEAN_WORDS,
                 sigma: float = SIGMA_WORDS) -> List[Record]:
    """Arrivals uniform within each bin (as des.EventDraws places a minute's arrivals)."""
    rng = random.Random(seed + 1)
    out = []
    for b, c in enumerate(counts_per_bin):
        ts = sorted(rng.random() for _ in range(int(c)))
        for u in ts:
            out.append(Record(f"t{seed}-{len(out):06d}", rng.getrandbits(48), _size(rng, mean_words, sigma),
                              round((b + u) * bin_s, 6)))
    return out


def paper_trace_counts(seed: int = 101, scenario: str = "stationary", week: str = "test", start_min: int = 0,
                       n_min: int = 60) -> List[int]:
    """Per-minute counts of the paper's synthetic trace (imports prism_repro read-only)."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    from prism_repro.experiment import WEEK_START
    from prism_repro.workload import WorkloadParams, generate_trace
    c = generate_trace(seed, scenario, WorkloadParams())["counts"]
    a = WEEK_START[week] + start_min
    return [int(x) for x in c[a:a + n_min]]


def envelope(rec: Record, arm: str, pipeline_request_id: str, deadline_s: float = DEADLINE_S,
             k_override: Optional[int] = None) -> dict:
    env = {"pipeline_request_id": pipeline_request_id, "record_id": rec.record_id, "doc_seed": rec.doc_seed,
           "n_words": rec.n_words, "deadline_s": deadline_s, "arm": arm, "trace": []}
    if k_override is not None:
        env["k_override"] = int(k_override)
    return env
