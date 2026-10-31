"""Configuration objects with validated defaults.

Defaults reproduce Supplementary Table S1 of the V2.6 manuscript (reported parameters). Values marked
"ASSUMPTION Dxx" are not specified in the manuscript and are documented in
ASSUMPTIONS_AND_DECISIONS.md.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Tuple

STAGES: Tuple[str, ...] = ("ingest", "transform", "aggregate", "load")


@dataclass(frozen=True)
class Prices:
    """USD per GB-second (od, pc, pcd) and per request (req). Manuscript §III-D.

    These are the values stated in the manuscript; they are NOT claimed to be
    current provider prices (see docs/PRICING_PROVENANCE.md).
    """

    od: float = 1.66667e-5
    pc: float = 4.1667e-6
    pcd: float = 9.7222e-6
    req: float = 2e-7

    def validate(self) -> None:
        for k, v in asdict(self).items():
            if not (v > 0):
                raise ValueError(f"price {k} must be positive, got {v}")
        if not self.pcd < self.od:
            raise ValueError("provisioned duration price must be below on-demand price")

    @property
    def break_even_utilisation(self) -> float:
        """Billing utilisation above which provisioned capacity is cheaper (§III-D, Eq. (10))."""
        return self.pc / (self.od - self.pcd)


@dataclass(frozen=True)
class PipelineConfig:
    warm_mean_1024: Tuple[float, ...] = (0.8, 4.0, 2.5, 1.2)  # s, Table S1
    exec_shape: float = 0.30  # sigma of log, Table S1 (ASSUMPTION D01: sigma of log)
    overhead_mean: float = 0.1  # s per stage
    overhead_shape: float = 0.30
    init_mean_1024: float = 6.0  # s
    init_shape: float = 0.30
    mem_options: Tuple[int, ...] = (512, 1024, 2048, 3008)
    nonscaling: float = 0.5  # Eq. (2)
    init_nonscaling: float = 0.7  # §III-A, Eq. (3)
    default_mem: int = 1024
    deadline: float = 14.5  # s
    window_min: int = 15
    sla_eps: float = 0.01  # window compliant if attainment >= 1 - sla_eps
    slo_violating_window_target: float = 0.02  # tuning threshold §V-C
    keepalive_min: int = 10
    epoch_min: int = 5
    lag_min: int = 2
    # Fast-simulator peak-concurrency model (§V-A). intensity_sigma DERIVED from
    # the 1.011 factor of c_eff: exp(sigma^2/2)=1.011 -> sigma≈0.148 (D02).
    intensity_sigma: float = 0.148
    peak_upper_frac: float = 0.45
    latency_samples: int = 100
    prices: Prices = field(default_factory=Prices)

    @property
    def n_stages(self) -> int:
        return len(self.warm_mean_1024)

    def validate(self) -> None:
        self.prices.validate()
        if self.n_stages < 1 or any(d <= 0 for d in self.warm_mean_1024):
            raise ValueError("stage warm means must be positive")
        for name in ("exec_shape", "overhead_shape", "init_shape", "intensity_sigma"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if not (0 <= self.nonscaling <= 1 and 0 <= self.init_nonscaling <= 1):
            raise ValueError("non-scaling fractions must be in [0,1]")
        if self.default_mem not in self.mem_options:
            raise ValueError("default_mem must be one of mem_options")
        if any(m <= 0 for m in self.mem_options):
            raise ValueError("memory sizes must be positive")
        if not (0 < self.sla_eps < 1):
            raise ValueError("sla_eps must be in (0,1)")
        if not (0 < self.peak_upper_frac <= 1):
            raise ValueError("peak_upper_frac must be in (0,1]")
        if self.epoch_min < 1 or self.lag_min < 0 or self.keepalive_min < 0:
            raise ValueError("invalid timing parameters")
        if (7 * 1440) % self.window_min or self.window_min % 1:
            raise ValueError("window length must divide a week")
        if self.deadline <= 0 or self.init_mean_1024 < 0:
            raise ValueError("deadline must be positive and init time non-negative")

    def with_(self, **kw) -> "PipelineConfig":
        c = replace(self, **kw)
        c.validate()
        return c

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PrismConfig:
    """PRISM controller settings (§IV). Unspecified items are assumptions."""

    eps: float = 0.05
    delta: float = 0.1
    gamma: float = 0.05  # Eq. (13)
    s_min: float = -0.3
    s_max: float = 0.8
    target_miss: float = 0.01
    conformal_delay_epochs: int = 2
    use_conformal: bool = True
    n_scenarios: int = 100
    n_levels: int = 20  # plus the zero level
    level_lo: float = 0.5
    level_hi: float = 1.15
    risk_model: str = "occupancy"  # "occupancy" (Eq. (5) o at c_eff, Eq. (14), as in paper) or "erlangb"
    use_ceff: bool = True
    kappa_prior: float = 0.35
    kappa_alpha: float = 0.1  # ASSUMPTION D10
    kappa_min_overflow: float = 1000.0  # ASSUMPTION D10: overflow requests before leaving prior
    kappa_clip: Tuple[float, float] = (0.1, 1.0)
    hysteresis: float = 0.85
    use_hysteresis: bool = True
    memory_every: int = 12
    optimise_memory: bool = True
    feasibility_mode: str = "scenarios"  # or "quantile" (§IV-C; Supplement S9)
    cap: int | None = None

    def validate(self) -> None:
        if not (0 < self.eps < 1 and 0 < self.delta < 1):
            raise ValueError("eps and delta must be in (0,1)")
        if self.risk_model not in ("occupancy", "erlangb"):
            raise ValueError("risk_model must be 'occupancy' or 'erlangb'")
        if self.feasibility_mode not in ("scenarios", "quantile"):
            raise ValueError("feasibility_mode must be 'scenarios' or 'quantile'")
        if self.n_scenarios < 2 or self.n_levels < 1:
            raise ValueError("need >=2 scenarios and >=1 level")
        if not (0 < self.hysteresis <= 1):
            raise ValueError("hysteresis factor must be in (0,1]")
        if self.cap is not None and self.cap < 0:
            raise ValueError("cap must be non-negative")

    def with_(self, **kw) -> "PrismConfig":
        c = replace(self, **kw)
        c.validate()
        return c


def dump_json(obj, path: str) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True, default=str)
