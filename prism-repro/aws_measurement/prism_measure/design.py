"""Experiment design for the quota-10 on-demand campaign (docs/revision/init_vs_memory/MEASUREMENT_PLAN.md).

Cells
  main:  4 stage PROXIES x 4 memory sizes. No start-up work beyond the Python runtime, so the cold penalty here is
         the platform's own (Lambda-reported init of an empty handler plus environment creation).
  init:  2 init-placement PROXIES x 4 sizes, a fixed amount of CPU start-up work placed either at module scope
         (inside Lambda's reported INIT phase) or in the first invocation. They bracket where PRISM's unspecified
         start-up work could sit, and show which of Lambda's fields each placement lands in.
Visits
  Each visit to a cell first retires every warm environment (configuration nonce), then runs one cold batch of
  `batch` concurrent invocations on new environments, then a few warm batches on those environments.
Order
  Each cell's visits are split across `blocks` blocks (run on different days); within a block the visits of all
  cells are shuffled, so memory size is never confounded with time of day or day.
Concurrency
  At most `batch` invocations are ever in flight, and `batch` may not exceed CAP_MAX = 8 (quota 10, headroom 2).
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

ACCOUNT_QUOTA = 10
HEADROOM = 2
CAP_MAX = ACCOUNT_QUOTA - HEADROOM             # 8
STAGES = ("ingest", "transform", "aggregate", "load")    # prism_repro.config.STAGES
SIZES = (512, 1024, 2048, 3008)                           # prism_repro.config.PipelineConfig.mem_options
INIT_VARIANTS = ("init_module", "init_first_call")
PREFIX = "prism-meas"


@dataclass(frozen=True)
class Cell:
    group: str           # "main" or "init"
    variant: str         # stage name for main cells, init variant otherwise
    memory_mb: int

    @property
    def function(self) -> str:
        return f"{PREFIX}-{self.variant.replace('_', '-')}-{self.memory_mb}"

    @property
    def key(self) -> str:
        return f"{self.group}/{self.variant}/{self.memory_mb}"


@dataclass
class Visit:
    block: int
    order: int           # position within the block after shuffling
    cell: Cell
    cold: int            # invocations in the cold batch (all concurrent)
    warm_batches: List[int] = field(default_factory=list)   # sizes of the following warm batches


@dataclass
class Design:
    seed: int
    batch: int
    blocks: int
    cold_target: Dict[str, int]
    warm_target: Dict[str, int]
    visits: List[Visit]

    def counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for v in self.visits:
            c = out.setdefault(v.cell.key, {"cold": 0, "warm": 0, "visits": 0, "cold_batches": 0, "warm_batches": 0})
            c["cold"] += v.cold
            c["warm"] += sum(v.warm_batches)
            c["visits"] += 1
            c["cold_batches"] += 1
            c["warm_batches"] += len(v.warm_batches)
        return out

    def cells(self) -> List[Cell]:
        seen: Dict[str, Cell] = {}
        for v in self.visits:
            seen.setdefault(v.cell.key, v.cell)
        return list(seen.values())

    def to_json(self) -> str:
        return json.dumps({"seed": self.seed, "batch": self.batch, "blocks": self.blocks,
                           "cold_target": self.cold_target, "warm_target": self.warm_target,
                           "visits": [dict(asdict(v), function=v.cell.function) for v in self.visits]}, indent=1)


def check_cap(batch: int) -> None:
    if not (1 <= batch <= CAP_MAX):
        raise ValueError(f"batch/concurrency cap must be 1..{CAP_MAX} (quota {ACCOUNT_QUOTA}, headroom {HEADROOM}); "
                         f"got {batch}")


def _split(n: int, parts: int) -> List[int]:
    q, r = divmod(n, parts)
    return [q + (1 if i < r else 0) for i in range(parts)]


def build_design(seed: int = 20261121, batch: int = CAP_MAX, blocks: int = 3,
                 sizes: Tuple[int, ...] = SIZES, stages: Tuple[str, ...] = STAGES,
                 init_variants: Tuple[str, ...] = INIT_VARIANTS,
                 cold_main: int = 230, warm_main: int = 1000, cold_init: int = 230, warm_init: int = 200) -> Design:
    """Cold counts are rounded up to whole batches (230 -> 29 batches of 8 = 232)."""
    check_cap(batch)
    if blocks < 1:
        raise ValueError("blocks must be >= 1")
    rng = random.Random(seed)
    groups = [("main", s, cold_main, warm_main) for s in stages] + [("init", v, cold_init, warm_init) for v in init_variants]
    per_block: Dict[int, List[Visit]] = {b: [] for b in range(blocks)}
    for group, variant, n_cold, n_warm in groups:
        if n_cold <= 0:
            continue
        for m in sizes:
            cell = Cell(group, variant, int(m))
            n_cold_batches = math.ceil(n_cold / batch)
            if n_cold_batches < blocks:
                raise ValueError(f"{cell.key}: {n_cold_batches} cold batches cannot cover {blocks} blocks")
            warm_batch_sizes = [batch] * (n_warm // batch) + ([n_warm % batch] if n_warm % batch else [])
            # distribute warm batches over this cell's visits as evenly as possible, in random order
            per_visit = _split(len(warm_batch_sizes), n_cold_batches)
            rng.shuffle(per_visit)
            it = iter(warm_batch_sizes)
            visits = [Visit(-1, -1, cell, batch, [next(it) for _ in range(k)]) for k in per_visit]
            # assign visits to blocks: equal shares, random which visit goes where
            block_of = [b for b, k in enumerate(_split(n_cold_batches, blocks)) for _ in range(k)]
            rng.shuffle(block_of)
            for v, b in zip(visits, block_of):
                v.block = b
                per_block[b].append(v)
    visits: List[Visit] = []
    for b in range(blocks):
        rng.shuffle(per_block[b])
        for i, v in enumerate(per_block[b]):
            v.order = i
            visits.append(v)
    for v in visits:                                   # nothing above may exceed the cap
        assert v.cold <= batch and all(0 < w <= batch for w in v.warm_batches)
    return Design(seed, batch, blocks,
                  {"main": math.ceil(cold_main / batch) * batch, "init": math.ceil(cold_init / batch) * batch},
                  {"main": warm_main, "init": warm_init}, visits)


def function_environment(cell: Cell, rates: Optional[Dict[str, float]] = None,
                         warm_mean_1024: Optional[Dict[str, float]] = None, init_target_s: float = 2.0) -> Dict[str, str]:
    """Environment variables for a cell's function. `rates` = SHA-256 iterations per second measured at 1024 MB
    by the calibration step (key "cpu"); without it the work units are 0 (deployment before calibration)."""
    rate = (rates or {}).get("cpu", 0.0)
    env = {"PRISM_STAGE": cell.variant, "PRISM_WORK_UNITS": "0", "PRISM_INIT_UNITS": "0",
           "PRISM_FIRST_CALL_UNITS": "0", "PRISM_COLD_NONCE": "deploy"}
    if cell.group == "main" and warm_mean_1024:
        env["PRISM_WORK_UNITS"] = str(int(round(warm_mean_1024[cell.variant] * rate)))
    elif cell.variant == "init_module":
        env["PRISM_INIT_UNITS"] = str(int(round(init_target_s * rate)))
    elif cell.variant == "init_first_call":
        env["PRISM_FIRST_CALL_UNITS"] = str(int(round(init_target_s * rate)))
    return env
