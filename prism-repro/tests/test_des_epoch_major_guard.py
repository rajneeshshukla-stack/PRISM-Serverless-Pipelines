"""Guard for the epoch-major restructuring of des.simulate_events (R2.2, stage 1). Written BEFORE des.py was changed.

tests/data/des_stage_major_3bd1f33.py is a verbatim copy of src/prism_repro/des.py at commit 3bd1f33, the stage-major
implementation (each stage runs across the whole horizon before the next). Its LF-normalised SHA-256 is pinned below,
so the oracle cannot drift. For fixed cfg, draws, P_epoch and mem_epoch, the current simulate_events must return output
BYTE-IDENTICAL to the oracle's: the summary, window_attainment, overflow_share_stage, inflight_max, every telemetry
array and the sampling-flip statistics. Floats are compared by their hex form and arrays by dtype, shape and bytes.
A failure names the first field that differs. Do not adjust the expectation: a moved number means the restructuring
is wrong.

Coverage: three seeds x {stationary, new_spike} on a four-hour daytime window with demand-following schedules,
on-demand overflow and memory switches; and boundary stress cases built so that the state carried across an epoch
boundary matters: executions spanning several epochs, keep-alive spanning boundaries and idle gaps longer than it,
one-minute and seven-minute epochs with a partial last epoch, arrivals exactly on epoch boundaries, a memory change
at every epoch (the version counter), truncated initialisation, unbilled initialisation, all on-demand and all
provisioned.
"""
import dataclasses
import hashlib
import importlib.util
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import prism_repro  # noqa: E402,F401  (parent package of the oracle's relative imports)
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, simulate_events  # noqa: E402
from prism_repro.latency import stage_means  # noqa: E402
from prism_repro.workload import generate_trace  # noqa: E402

REF_PATH = os.path.join(HERE, "data", "des_stage_major_3bd1f33.py")
REF_SHA256 = "78d41359a44fad82679782fe1b2e0c0aa30aacb3f9c35aa9a4903af4209e40a1"   # des.py at 3bd1f33, LF line ends
REF_NAME = "prism_repro._des_stage_major_3bd1f33"


def load_reference():
    """The stage-major oracle, imported inside the prism_repro package so its relative imports resolve."""
    if REF_NAME in sys.modules:
        return sys.modules[REF_NAME]
    spec = importlib.util.spec_from_file_location(REF_NAME, REF_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[REF_NAME] = mod          # dataclasses look the module up while the class body is built
    spec.loader.exec_module(mod)
    return mod


def flatten(x, path="", out=None):
    """Exact, field-by-field serialisation: floats by hex, arrays by dtype, shape and SHA-256 of their bytes."""
    out = {} if out is None else out
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        x = {f.name: getattr(x, f.name) for f in dataclasses.fields(x)}
    if isinstance(x, dict):
        for k in sorted(x, key=str):
            flatten(x[k], f"{path}.{k}" if path else str(k), out)
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            flatten(v, f"{path}[{i}]", out)
    elif isinstance(x, np.ndarray):
        a = np.ascontiguousarray(x)
        out[path] = f"nd({a.dtype.str},{a.shape},{hashlib.sha256(a.tobytes()).hexdigest()})"
    elif isinstance(x, (bool, np.bool_)):
        out[path] = f"b{bool(x)}"
    elif isinstance(x, (int, np.integer)):
        out[path] = f"i{int(x)}"
    elif isinstance(x, (float, np.floating)):
        out[path] = f"f{float(x).hex()}"
    elif x is None:
        out[path] = "N"
    else:
        out[path] = repr(x)
    return out


def demand_schedule(counts, cfg, rng, mem_switch=0.1, zero_share=0.1):
    """Per-epoch capacity that follows the previous epoch's demand with a random scale (so overflow, cold starts and
    idle provisioned capacity all occur), some stages at zero, and random memory switches."""
    E, S = cfg.epoch_min, cfg.n_stages
    n_ep = -(-len(counts) // E)
    d = stage_means(cfg, cfg.default_mem)
    P = np.zeros((n_ep, S))
    mem = np.empty(n_ep, dtype=np.int64)
    m = cfg.default_mem
    for k in range(n_ep):
        prev = counts[max(0, (k - 1) * E):max(E, k * E)]
        base = float(prev.mean()) if len(prev) else 0.0
        P[k] = np.ceil(rng.uniform(0.4, 1.3, S) * base * d / 60.0)
        P[k, rng.uniform(size=S) < zero_share] = 0
        if rng.uniform() < mem_switch:
            m = int(rng.choice(cfg.mem_options))
        mem[k] = m
    return P, mem


def snap_to_boundaries(dr, every_min):
    """Move the first arrival of every `every_min`-th minute onto the minute's start (order is kept, as the first
    arrival of a minute is its earliest), so arrivals sit exactly on epoch boundaries."""
    starts = np.r_[0, np.cumsum(dr.counts)[:-1]]
    mins = np.flatnonzero((dr.counts > 0) & (np.arange(dr.n_min) % every_min == 0))
    dr.arrival[starts[mins]] = mins * 60.0
    return dr


class TestEpochMajorIsByteIdentical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = load_reference()

    def assert_identical(self, case, cfg, dr, P, mem, **kw):
        kw = dict(dict(want_inflight=True, want_telemetry=True, sample_seed=7), **kw)
        got = flatten(simulate_events(cfg, dr, P, mem, **kw))
        want = flatten(self.ref.simulate_events(cfg, dr, P, mem, **kw))
        self.assertEqual(sorted(got), sorted(want), f"{case}: output fields differ")
        for k in sorted(want):
            self.assertEqual(got[k], want[k], f"{case}: field {k} differs from the stage-major oracle")

    def test_oracle_is_the_stage_major_code_at_3bd1f33(self):
        with open(REF_PATH, "rb") as fh:
            body = fh.read().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(body).hexdigest(), REF_SHA256)

    def test_realistic_windows_three_seeds_two_scenarios(self):
        cfg = PipelineConfig()
        lo = 21 * 1440 + 8 * 60           # test week, 08:00-12:00 on its first day: rising demand, hourly spikes
        for seed in (101, 102, 103):
            for sc in ("stationary", "new_spike"):
                counts = generate_trace(seed, sc)["counts"][lo:lo + 240]
                dr = EventDraws(cfg, counts, seed, 3)
                P, mem = demand_schedule(counts, cfg, np.random.default_rng([seed, 1 if sc == "stationary" else 2]))
                self.assert_identical(f"seed {seed} {sc}", cfg, dr, P, mem, sample_seed=seed)

    def test_executions_spanning_several_epochs(self):
        # stage-2 executions of about 7 minutes with 5-minute epochs, 1-minute epochs on a second run: a request that
        # starts in epoch k finishes in epoch k+2 or later; keep-alive of 10 minutes spans boundaries
        rng = np.random.default_rng(11)
        counts = rng.poisson(6, 90)
        counts[40:55] = 0                  # idle gap longer than the keep-alive at the second setting
        for E, ka in ((5, 10), (1, 3)):
            cfg = PipelineConfig().with_(warm_mean_1024=(150.0, 420.0, 90.0, 260.0), epoch_min=E, keepalive_min=ka)
            dr = snap_to_boundaries(EventDraws(cfg, counts, 21, 0), E)
            stage2 = dr.ex[1] * 420.0                      # stage-2 execution times at 1024 MB, s
            self.assertGreater(stage2.max(), 2 * E * 60)    # some executions span two epoch boundaries or more
            self.assertGreater(float(np.mean(stage2 > E * 60)), 0.5)
            self.assertTrue(np.any(dr.arrival % (E * 60) == 0))   # arrivals exactly on epoch boundaries
            P, mem = demand_schedule(counts, cfg, np.random.default_rng(E), mem_switch=0.2)
            self.assert_identical(f"long service, epoch {E} min, keep-alive {ka} min", cfg, dr, P, mem)

    def test_partial_last_epoch_and_boundary_arrivals(self):
        rng = np.random.default_rng(12)
        counts = rng.poisson(40, 120)       # 120 minutes (a whole number of 15-minute windows): 7-minute epochs
        #                                     leave a partial last epoch of 1 minute
        cfg = PipelineConfig().with_(epoch_min=7)
        self.assertNotEqual(len(counts) % cfg.epoch_min, 0)
        dr = snap_to_boundaries(EventDraws(cfg, counts, 22, 1), 7)
        P, mem = demand_schedule(counts, cfg, rng)
        self.assert_identical("7-minute epochs, partial last epoch", cfg, dr, P, mem)

    def test_exact_ties_keep_the_stage_major_order(self):
        # deterministic service and no orchestration delay: a minute's requests arrive at one instant and finish
        # together, so every stage sees many exactly equal arrival times (some on epoch boundaries); the order among
        # them must stay the stage-major one (by time, then by the upstream stage's routing order)
        cfg = PipelineConfig().with_(exec_shape=0.0, overhead_mean=0.0, init_shape=0.0)
        counts = np.random.default_rng(15).poisson(30, 60)
        dr = EventDraws(cfg, counts, 25, 0)
        dr.arrival = dr.minute * 60.0 + 20.0 * (dr.minute % 3)    # still sorted; minutes 0, 5, 10, ... on a boundary
        self.assertTrue(np.all(np.diff(dr.arrival) >= 0))
        self.assertTrue(np.all(dr.ov == 0) and np.all(dr.ex == 1))
        P, mem = demand_schedule(counts, cfg, np.random.default_rng(15), mem_switch=0.3)
        self.assert_identical("exact ties", cfg, dr, P, mem)

    def test_order_sensitive_ties_across_minutes(self):
        # Interchangeable tied requests (above) cannot tell a wrong tie order from the right one. Here they can: with
        # deterministic service, no orchestration delay and no keep-alive (every on-demand request cold-starts), a
        # request arriving at :55 that cold-starts at stage 1 (6 s init + 0.8 s execution) reaches stage 2 at the same
        # instant as a request arriving at :01 of the next minute that stage 1 serves provisioned. Stage 2 has two
        # provisioned slots for six tied requests; the stage-major order (by time, then upstream routing position)
        # gives them to the earlier minute's requests, and with a 16 s deadline only those can be late.
        cfg = PipelineConfig().with_(exec_shape=0.0, overhead_mean=0.0, init_shape=0.0, keepalive_min=0, deadline=16.0)
        counts = np.full(60, 10)
        dr = EventDraws(cfg, counts, 26, 0)
        within = np.arange(dr.n) - np.r_[0, np.cumsum(dr.counts)[:-1]][dr.minute]
        dr.arrival = dr.minute * 60.0 + np.where(within < 4, 1.0, 55.0)
        n_ep = 60 // cfg.epoch_min
        P = np.tile([3.0, 2.0, 100.0, 100.0], (n_ep, 1))
        mem = np.full(n_ep, 1024)
        out = self.ref.simulate_events(cfg, dr, P, mem)["summary"]
        self.assertTrue(0.0 < out["record_attainment"] < 1.0)    # some requests late, some on time
        self.assert_identical("order-sensitive ties", cfg, dr, P, mem)

    def test_memory_change_every_epoch_truncated_init_unbilled(self):
        rng = np.random.default_rng(13)
        counts = rng.poisson(80, 60)
        cfg = PipelineConfig().with_(init_max_s=10.0)
        dr = EventDraws(cfg, counts, 23, 2)
        P, _ = demand_schedule(counts, cfg, rng, zero_share=0.5)
        mem = np.array([cfg.mem_options[k % len(cfg.mem_options)] for k in range(len(P))])   # version changes each epoch
        self.assertTrue(np.all(mem[1:] != mem[:-1]))
        self.assert_identical("memory change every epoch, truncated init", cfg, dr, P, mem)
        self.assert_identical("same, init not billed", cfg, dr, P, mem, bill_init=False)
        self.assert_identical("same, no telemetry or sampling", cfg, dr, P, mem, want_inflight=False,
                              want_telemetry=False, sample_seed=None)

    def test_all_on_demand_and_all_provisioned(self):
        rng = np.random.default_rng(14)
        counts = rng.poisson(50, 75)
        cfg = PipelineConfig()
        dr = EventDraws(cfg, counts, 24, 0)
        n_ep = 75 // cfg.epoch_min
        self.assert_identical("all on demand", cfg, dr, np.zeros((n_ep, 4)), np.full(n_ep, 1024))
        self.assert_identical("all provisioned", cfg, dr, np.full((n_ep, 4), 500.0), np.full(n_ep, 2048))


if __name__ == "__main__":
    unittest.main()
