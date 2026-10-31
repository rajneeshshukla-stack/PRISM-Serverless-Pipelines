"""SYNTHETIC workload generator (§V-B). All traces produced here are simulated,
not measurements. Structural features follow the manuscript; parameters the
manuscript does not state were fixed a priori (ASSUMPTION D14) before any
comparative experiment and were NOT tuned to reproduce manuscript numbers.

Time unit: minutes. Day 0 of a trace is a Monday (ASSUMPTION D14e).
Splits (§V-B): days 0-13 train, 14-20 validation, 21-27 test.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

import numpy as np

MIN_PER_DAY = 1440
MIN_PER_WEEK = 7 * MIN_PER_DAY
SCENARIOS = ("stationary", "growth", "bursty", "new_spike", "shifted_triggers")
MAIN_SCENARIOS = SCENARIOS[:4]


@dataclass(frozen=True)
class WorkloadParams:
    mean_rate: float = 600.0          # §V-B, Table S1: 600 executions per minute
    days: int = 28
    # diurnal profile with two harmonics (amplitudes/phases: ASSUMPTION D14a)
    h1_amp: float = 0.35
    h1_peak_hour: float = 14.0
    h2_amp: float = 0.10
    h2_peak_hour: float = 10.0
    sat_factor: float = 0.65          # §V-B 35 % reduction
    sun_factor: float = 0.55          # §V-B 45 % reduction
    # multiplicative AR(1) noise on log scale (ASSUMPTION D14b)
    ar_phi: float = 0.99
    ar_sd: float = 0.08               # stationary s.d. of log noise
    # deterministic fan-out spikes (§V-B), additive multiples of baseline
    spike_minutes: tuple = ((0, 2.0), (1, 2.0), (30, 1.0))
    # random bursts (§V-B): 4/day, amplitude U(1,3.5)x baseline (additive, D14c)
    bursts_per_day: float = 4.0
    burst_amp_lo: float = 1.0
    burst_amp_hi: float = 3.5
    burst_dur_lo: int = 2             # minutes, ASSUMPTION D14c
    burst_dur_hi: int = 10
    gamma_shape: float = 40.0         # gamma mixing of Poisson counts (D14d)
    # scenario parameters (§V-B)
    growth_level: float = 0.40
    growth_ramp_days: float = 3.0
    new_spike_minutes: tuple = ((15, 1.5), (16, 1.5))
    new_spike_level: float = 0.20
    shifted_spike_minutes: tuple = ((10, 2.0), (11, 2.0), (40, 1.0))

    def validate(self):
        if self.mean_rate <= 0 or self.days < 21:
            raise ValueError("mean_rate>0 and days>=21 required")
        if not (0 <= self.ar_phi < 1) or self.ar_sd < 0:
            raise ValueError("AR(1) parameters invalid")
        if self.burst_dur_lo < 1 or self.burst_dur_hi < self.burst_dur_lo:
            raise ValueError("burst duration range invalid")
        if self.gamma_shape <= 0:
            raise ValueError("gamma_shape must be > 0")

    def baseline_scale(self) -> float:
        """Scale mu so that the expected stationary mean rate equals mean_rate."""
        weekly = (5 + self.sat_factor + self.sun_factor) / 7
        spike = sum(a for _, a in self.spike_minutes) / 60
        burst = (self.bursts_per_day * 0.5 * (self.burst_amp_lo + self.burst_amp_hi)
                 * 0.5 * (self.burst_dur_lo + self.burst_dur_hi) / MIN_PER_DAY)
        return self.mean_rate / (weekly * (1 + spike + burst))


def _bursts(rng, n_min, rate_per_day, p: WorkloadParams):
    out = np.zeros(n_min)
    k = rng.poisson(rate_per_day * n_min / MIN_PER_DAY)
    starts = rng.integers(0, n_min, size=k)
    amps = rng.uniform(p.burst_amp_lo, p.burst_amp_hi, size=k)
    durs = rng.integers(p.burst_dur_lo, p.burst_dur_hi + 1, size=k)
    for s, a, d in zip(starts, amps, durs):
        out[s:s + d] += a
    return out


def _spike_profile(minute_of_hour, spikes):
    out = np.zeros(minute_of_hour.shape)
    for mm, a in spikes:
        out[minute_of_hour == mm] += a
    return out


def generate_trace(seed: int, scenario: str = "stationary", params: WorkloadParams | None = None
                   ) -> Dict[str, np.ndarray]:
    """Generate one SYNTHETIC 28-day trace (per-minute counts) for a scenario.

    All scenarios of a seed share days 0-20 exactly and share the test-week noise,
    bursts and gamma draws (common random numbers); scenario modifications are
    applied on top.
    """
    p = params or WorkloadParams()
    p.validate()
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}")
    n = p.days * MIN_PER_DAY
    t = np.arange(n)
    rng = np.random.default_rng([seed, 1])
    hour = (t % MIN_PER_DAY) / 60.0
    dow = (t // MIN_PER_DAY) % 7
    diurnal = (1 + p.h1_amp * np.cos(2 * np.pi * (hour - p.h1_peak_hour) / 24)
               + p.h2_amp * np.cos(4 * np.pi * (hour - p.h2_peak_hour) / 24))
    weekly = np.where(dow == 5, p.sat_factor, np.where(dow == 6, p.sun_factor, 1.0))
    eps = rng.standard_normal(n) * p.ar_sd * np.sqrt(1 - p.ar_phi ** 2)
    x = np.empty(n)
    x[0] = rng.standard_normal() * p.ar_sd
    for i in range(1, n):  # AR(1)
        x[i] = p.ar_phi * x[i - 1] + eps[i]
    ar = np.exp(x - 0.5 * p.ar_sd ** 2)
    base = p.baseline_scale() * diurnal * weekly * ar
    moh = t % 60
    bursts = _bursts(rng, n, p.bursts_per_day, p)
    gam = rng.gamma(p.gamma_shape, 1.0 / p.gamma_shape, size=n)
    pois_u = np.random.default_rng([seed, 2])  # count noise stream
    extra_bursts = _bursts(np.random.default_rng([seed, 3]), n, p.bursts_per_day, p)

    test = t >= 21 * MIN_PER_DAY
    spikes = _spike_profile(moh, p.spike_minutes)
    level = np.ones(n)
    if scenario == "growth":
        frac = np.clip((t - 21 * MIN_PER_DAY) / (p.growth_ramp_days * MIN_PER_DAY), 0, 1)
        level = np.where(test, 1 + p.growth_level * frac, 1.0)
    elif scenario == "bursty":
        bursts = bursts + np.where(test, extra_bursts, 0.0)
    elif scenario == "new_spike":
        spikes = spikes + np.where(test, _spike_profile(moh, p.new_spike_minutes), 0.0)
        level = np.where(test, 1 + p.new_spike_level, 1.0)
    elif scenario == "shifted_triggers":
        spikes = np.where(test, _spike_profile(moh, p.shifted_spike_minutes), spikes)
    b = base * level
    rate = b * (1 + spikes + bursts)
    counts = pois_u.poisson(rate * gam)
    trigger_minutes = np.array(sorted(m for m, _ in p.spike_minutes))
    return {
        "counts": counts.astype(np.int64),
        "rate": rate,
        "baseline": b,
        "dow": dow.astype(np.int8),
        "trigger_minutes_known": trigger_minutes,  # schedule known from history
        "meta": {"seed": seed, "scenario": scenario, "params": asdict(p),
                 "synthetic": True, "generator": "prism_repro.workload.generate_trace"},
    }


def split_bounds(week: str):
    """Minute ranges for 'train', 'val', 'test'."""
    return {"train": (0, 14 * MIN_PER_DAY), "val": (14 * MIN_PER_DAY, 21 * MIN_PER_DAY),
            "test": (21 * MIN_PER_DAY, 28 * MIN_PER_DAY)}[week]
