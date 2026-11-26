"""Event-level simulator (§V-A, §VI-H). SIMULATION ONLY.

Every request is an event. Arrivals are placed uniformly at random within each
minute; service, orchestration and initialisation draws of every request and stage
are fixed per (trace, week, scenario) so that every policy sees identical draws.
Per stage, a request is served by a free provisioned environment if one exists
(loss routing, so the provisioned pool is an M/G/P/P system); otherwise by an idle
warm on-demand environment (last-in first-out, retained for the keep-alive period);
otherwise it cold-starts, and the new environment is occupied for init + execution.
An upstream completion plus the orchestration delay is the downstream arrival.
Every request's latency is computed, so window attainment is exact.

This is an independent reconstruction of the manuscript's description. Given a
schedule it replays provisioning decisions produced elsewhere (open loop, §VI-H, as
E9 and E12 use it). Given a controller (`simulate_events(cfg, draws, controller=...)`,
R2.2 stage 2, R6.3) it runs closed loop: before each epoch the controller sees the
telemetry observed up to the feedback delay and sets that epoch's provisioning and
memory; `closed_loop.PolicyController` drives the fast simulator's policies this way.
`simulate_events(..., want_telemetry=True)` additionally records per-minute
telemetry (`EventTelemetry`), with the fields of `simulator.Telemetry` that policies
read.

R2.2, stage 1: the replay is epoch-major. `_EventEngine` advances epoch by epoch and,
within an epoch, routes every stage's arrivals that fall in it, carrying each stage's
state across the boundary explicitly (`_StageState`: provisioned environments busy
until their finish times, on-demand environments busy until theirs, the LIFO pool of
idle warm environments with their keep-alive clocks, and the memory version of the
last request routed). Requests still running at a boundary stay in those heaps, and a
request's downstream arrival waits in the next stage's pending set until the epoch it
falls in. Each stage sees exactly the arrival sequence of the former stage-major pass
(by time, ties by the upstream stage's routing order), so outputs are byte-identical
to it (tests/test_des_epoch_major_guard.py). Costs and shares are still summed once,
over each stage's full request array in that order.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

import numpy as np

from .config import PipelineConfig
from .latency import init_mean, init_seconds, lognormal_mult, stage_demand, stage_means
from .metrics import severity, weighted_quantile_hist, window_attainment
from .simulator import Telemetry


class EventDraws:
    def __init__(self, cfg: PipelineConfig, counts: np.ndarray, seed: int, key: int):
        rng = np.random.default_rng([seed, 500 + key])
        n_min = len(counts)
        S = cfg.n_stages
        self.counts = counts.astype(np.int64)
        self.minute = np.repeat(np.arange(n_min), self.counts)
        self.arrival = self.minute * 60.0 + rng.uniform(0, 60, len(self.minute))
        order = np.argsort(self.arrival, kind="stable")
        self.arrival, self.minute = self.arrival[order], self.minute[order]
        n = len(self.arrival)
        self.ex = lognormal_mult(rng.standard_normal((S, n)), cfg.exec_shape).astype(np.float32)
        self.ov = (cfg.overhead_mean * lognormal_mult(rng.standard_normal((S, n)), cfg.overhead_shape)).astype(np.float32)
        self.init = lognormal_mult(rng.standard_normal((S, n)), cfg.init_shape).astype(np.float32)
        self.n, self.n_min = n, n_min


class _StageState:
    """Routing state of one stage, carried across epoch boundaries (R2.2).

    pc_busy: heap of finish times of busy provisioned environments (requests in flight on them).
    od_busy: heap of busy on-demand environments, as finish times, or (finish time, memory version) with the M5 fix.
    idle:    warm idle on-demand environments in the order they became idle; reused last-in first-out, expired
             first-in first-out once idle longer than the keep-alive (their idle-since time is their keep-alive clock).
    cur_gen: memory version of the last on-demand request routed (the M5 version counter's state)."""
    __slots__ = ("pc_busy", "od_busy", "idle", "cur_gen")

    def __init__(self):
        self.pc_busy, self.od_busy, self.idle, self.cur_gen = [], [], deque(), None


def _stage_pass(arr, x, z, P_min, KA, gen_min=None):
    """One stage. arr sorted ascending. Returns finish times, cold flags, provisioned flags.
    gen_min (M5 fix): memory-version index per minute; an on-demand environment is reused only by a
    request of the same version."""
    n = len(arr)
    finish = np.empty(n)
    cold = np.zeros(n, bool)
    used_pc = np.zeros(n, bool)
    _route(_StageState(), arr.tolist(), x.tolist(), z.tolist(), P_min.tolist(), KA,
           gen_min.tolist() if gen_min is not None else None, finish, cold, used_pc)
    return finish, cold, used_pc


def _route(st, arr_l, x_l, z_l, P_l, KA, G_l, finish, cold, used_pc):
    """Route requests through one stage, continuing from state `st` and leaving it as the state after the last one.
    arr_l, x_l, z_l: arrival, execution and initialisation times (lists, arrival-ordered); P_l: provisioned level per
    minute; G_l: memory version per minute (None: no versioning). Writes finish, cold and used_pc (same length).
    The loop body is the former whole-horizon _stage_pass, unchanged; only its state outlives the call."""
    pc_busy, od_busy, idle, cur_gen = st.pc_busy, st.od_busy, st.idle, st.cur_gen
    hpush, hpop = heapq.heappush, heapq.heappop
    nP = len(P_l)
    for j in range(len(arr_l)):
        t = arr_l[j]
        while pc_busy and pc_busy[0] <= t:
            hpop(pc_busy)
        m = int(t // 60.0)
        Pm = P_l[m] if m < nP else P_l[-1]
        if len(pc_busy) < Pm:
            f = t + x_l[j]
            hpush(pc_busy, f)
            used_pc[j] = True
        else:
            if G_l is None:
                while od_busy and od_busy[0] <= t:
                    idle.append(hpop(od_busy))
                lim = t - KA
                while idle and idle[0] < lim:
                    idle.popleft()
                if idle:
                    idle.pop()
                    f = t + x_l[j]
                else:
                    f = t + z_l[j] + x_l[j]
                    cold[j] = True
                hpush(od_busy, f)
            else:  # M5 fix: entries are (finish time, version)
                g = G_l[m] if m < len(G_l) else G_l[-1]
                if g != cur_gen:
                    cur_gen = g
                    idle = deque(e for e in idle if e[1] == g)
                while od_busy and od_busy[0][0] <= t:
                    e = hpop(od_busy)
                    if e[1] == g:
                        idle.append(e)
                lim = t - KA
                while idle and idle[0][0] < lim:
                    idle.popleft()
                if idle:
                    idle.pop()
                    f = t + x_l[j]
                else:
                    f = t + z_l[j] + x_l[j]
                    cold[j] = True
                hpush(od_busy, (f, g))
        finish[j] = f
    st.idle, st.cur_gen = idle, cur_gen   # the heaps were changed in place; the pool may have been rebuilt


class _EventEngine:
    """Epoch-major event routing (R2.2). `route_until(t_hi)` routes, stage by stage, every request whose arrival at
    the stage is earlier than t_hi; `drain()` routes the rest. Called with t_hi at successive epoch ends, it advances
    one epoch at a time with all stages inside each epoch.

    Why this reproduces the former stage-major pass exactly: a stage's state changes only when one of its own
    arrivals is routed, so the stage gives the same results whenever it sees the same arrival sequence. Stage 0 takes
    the trace's arrivals in order. A request reaches stage s+1 at its stage-s finish plus the orchestration delay,
    always later than it reached stage s, so every stage-(s+1) arrival before t_hi comes from a stage-s arrival
    before t_hi, already routed when stage s+1's turn in the same epoch comes. Pending arrivals are taken in the
    order of the former global stable sort: by time, ties by the position at which stage s routed them.

    Kept per stage, in routing order, for the summary: the per-request execution and initialisation cost terms,
    cold and provisioned flags, and (when asked) arrival and finish times."""

    def __init__(self, cfg: PipelineConfig, draws: EventDraws, bill_init: bool = True, keep_times: bool = False):
        self.cfg, self.draws, self.bill_init, self.keep_times = cfg, draws, bill_init, keep_times
        S = cfg.n_stages
        self.S, self.KA = S, cfg.keepalive_min * 60.0
        self.state = [_StageState() for _ in range(S)]
        self.mems = np.array(cfg.mem_options)
        self.d = [np.array([stage_means(cfg, int(m))[s] for m in cfg.mem_options]) for s in range(S)]
        self.ini = np.array([init_mean(cfg, int(m)) for m in cfg.mem_options])
        self.next0 = 0                                     # next stage-0 position (the trace's arrival order)
        e_t, e_i = np.empty(0), np.empty(0, np.int64)
        self.pend = [None] + [(e_t, e_i, e_i) for _ in range(1, S)]   # stage s >= 1: (time, upstream position, id)
        self.seq = [0] * S                                 # requests routed so far, per stage
        self.out = [dict(cold=[], used=[], ex=[], ini=[], arr=[], fin=[]) for _ in range(S)]
        self.done = np.empty(draws.n)                      # completion after the last stage's orchestration delay

    def _take(self, s, t_hi):
        """Requests arriving at stage s before t_hi (all remaining if t_hi is None), in stage-major order."""
        if s == 0:
            a = self.draws.arrival
            lo = self.next0
            hi = len(a) if t_hi is None else max(lo, int(np.searchsorted(a, t_hi, side="left")))
            self.next0 = hi
            return a[lo:hi], np.arange(lo, hi)
        t, q, r = self.pend[s]
        sel = np.ones(len(t), bool) if t_hi is None else t < t_hi
        o = np.lexsort((q[sel], t[sel]))                   # by time, ties by upstream routing position
        tt, rr = t[sel][o], r[sel][o]
        keep = ~sel
        self.pend[s] = (t[keep], q[keep], r[keep])
        return tt, rr

    def _route_stage(self, s, tt, rr, P_l, G_l, mem_min):
        n = len(tt)
        if n == 0:
            return None
        cfg, dr = self.cfg, self.draws
        m_req = mem_min[np.minimum((tt // 60).astype(np.int64), dr.n_min - 1)]
        mi = np.searchsorted(self.mems, m_req)
        x = dr.ex[s, rr] * self.d[s][mi]
        if cfg.init_max_s is None:
            z = dr.init[s, rr] * self.ini[mi]
        else:  # R4.8: truncated initialisation, per memory size
            u = dr.init[s, rr]
            z = np.empty(len(u))
            for j, m in enumerate(cfg.mem_options):
                sel = mi == j
                if sel.any():
                    z[sel] = init_seconds(cfg, u[sel], m)
        fin = np.empty(n)
        cold = np.zeros(n, bool)
        used = np.zeros(n, bool)
        _route(self.state[s], tt.tolist(), x.tolist(), z.tolist(), P_l[s], self.KA, G_l, fin, cold, used)
        pr = cfg.prices
        g = m_req / 1024.0
        o = self.out[s]
        o["ex"].append(x * g * np.where(used, pr.pcd, pr.od))
        if self.bill_init:
            o["ini"].append(z * g * cold * pr.od)
        o["cold"].append(cold)
        o["used"].append(used)
        if self.keep_times:
            o["arr"].append(np.asarray(tt, float))
            o["fin"].append(fin)
        nxt = fin + dr.ov[s, rr]
        if s + 1 < self.S:
            t, q, r = self.pend[s + 1]
            self.pend[s + 1] = (np.concatenate([t, nxt]), np.concatenate([q, self.seq[s] + np.arange(n)]),
                                np.concatenate([r, rr]))
        else:
            self.done[rr] = nxt
        self.seq[s] += n
        return dict(arr=tt, fin=fin, cold=cold, used=used)

    def route_until(self, t_hi, P_l, G_l, mem_min):
        """Route every stage's arrivals before t_hi, stage 0 first. P_l: per stage, provisioned level per minute;
        G_l: memory version per minute; mem_min: memory per minute. Returns each stage's newly routed requests."""
        return [self._route_stage(s, *self._take(s, t_hi), P_l, G_l, mem_min) for s in range(self.S)]

    def drain(self, P_l, G_l, mem_min):
        """Route the requests still on their way when the horizon ends (lookups beyond it use its last minute)."""
        return self.route_until(None, P_l, G_l, mem_min)

    def stage(self, s, key, dtype=float):
        parts = self.out[s][key]
        return np.concatenate(parts) if parts else np.empty(0, dtype)


def max_inflight_per_minute(arr, finish, n_min):
    """Maximum number of in-flight executions in each minute (sweep over +1/-1 events),
    including the level carried into a minute from earlier events."""
    times = np.concatenate([arr, finish])
    delta = np.concatenate([np.ones(len(arr)), -np.ones(len(finish))])
    o = np.lexsort((-delta, times))  # at equal times process arrivals first (conservative)
    times, level = times[o], np.cumsum(delta[o])
    mins = np.minimum((times // 60).astype(np.int64), n_min - 1)
    out = np.zeros(n_min)
    np.maximum.at(out, mins, level)
    # level in force at the start of each minute = level after the last earlier event
    k = np.searchsorted(times, np.arange(n_min) * 60.0, side="left") - 1
    carry = np.where(k >= 0, level[np.maximum(k, 0)], 0.0)
    return np.maximum(out, carry)


@dataclass
class EventTelemetry(Telemetry):
    """Per-minute telemetry of an open-loop event-level replay (R2.2: instrumentation and data contract).

    The fields inherited from `simulator.Telemetry` carry the same meaning as in the
    fast simulator, so a policy's `decide(k, tel)` can read either: N arrivals per
    minute, K peak in-flight executions per stage, P provisioned level, n_od requests
    served on demand and cold the cold starts, each binned by the minute a request
    reaches the stage. The extra fields support conservation checks: `arrivals` and
    `completed` count stage arrivals and completions in each minute, and `inflight_end`
    counts executions still running at the end of each minute. Events after the last
    minute of the horizon are not observed (K is the exception: it reuses
    `max_inflight_per_minute`, which folds them into the last minute)."""
    arrivals: np.ndarray = None      # (n, S) stage arrivals per minute
    completed: np.ndarray = None     # (n, S) stage completions per minute
    inflight_end: np.ndarray = None  # (n, S) executions in flight at the end of each minute
    mem: np.ndarray = None           # (n,) memory applied per minute


def stage_telemetry(arr, fin, cold, used_pc, n_min):
    """Per-minute telemetry of one stage from its event outcomes.

    arr, fin: arrival and finish times (s); cold, used_pc: per-request flags from
    `_stage_pass`. Returns dict(arrivals, completed, inflight_end, n_od, cold, K), each of
    length n_min. inflight_end is counted directly at each minute boundary, not as a
    running sum of the other two, so arrivals - completed accumulating to inflight_end
    is a real check."""
    arr = np.asarray(arr, float)
    fin = np.asarray(fin, float)
    T = n_min * 60.0
    a_min = (arr // 60.0).astype(np.int64)
    f_min = (fin // 60.0).astype(np.int64)
    seen = arr < T
    od = seen & ~np.asarray(used_pc, bool)
    arrivals = np.bincount(a_min[seen], minlength=n_min)[:n_min]
    completed = np.bincount(f_min[fin < T], minlength=n_min)[:n_min]
    bounds = (np.arange(n_min) + 1) * 60.0
    started = np.searchsorted(np.sort(arr), bounds, side="left")    # arrivals strictly before the boundary
    finished = np.searchsorted(np.sort(fin), bounds, side="left")   # finishes strictly before the boundary
    inflight_end = started - finished
    n_od = np.bincount(a_min[od], minlength=n_min)[:n_min]
    n_cold = np.bincount(a_min[od & np.asarray(cold, bool)], minlength=n_min)[:n_min]
    K = max_inflight_per_minute(arr, fin, n_min)
    return dict(arrivals=arrivals, completed=completed, inflight_end=inflight_end,
                n_od=n_od, cold=n_cold, K=K)


class _ObservedTelemetry:
    """Per-minute telemetry of a closed-loop run, built epoch by epoch as requests are routed (R2.2, stage 2).

    Same definitions as `stage_telemetry` (arrivals, n_od and cold binned by the minute a request reaches the stage;
    completions by the minute it finishes; executions in flight at the end of each minute; K the peak in flight within
    each minute, arrivals counted before departures at equal times). After the requests arriving before minute M are
    routed, every minute below M is final: any event in it belongs to a request that arrived before it. `expose`
    copies final minutes up to the visible one into the controller's view, so the view never holds a value the
    controller could not have observed."""

    FIELDS = ("arrivals", "completed", "n_od", "cold", "K")

    def __init__(self, cfg: PipelineConfig, draws: EventDraws):
        n, S = draws.n_min, cfg.n_stages
        self.n, self.S = n, S
        for f in self.FIELDS:
            setattr(self, f, np.zeros((n, S)))
        self.P = np.zeros((n, S))
        self.mem = np.zeros(n, np.int64)
        self.level = np.zeros(S)                                 # executions in flight at the last swept instant
        self.fin_pending = [np.empty(0) for _ in range(S)]       # finish times not yet swept, per stage
        self.final = 0                                           # minutes [0, final) are final
        self.shown = 0                                           # minutes [0, shown) are in the view

    def add(self, routed, t_lo, t_hi):
        """Fold in the requests routed for arrivals in [t_lo, t_hi) (one list entry per stage, None if none)."""
        n, T = self.n, self.n * 60.0
        a_m, b_m = int(t_lo // 60), min(int(t_hi // 60), n)
        for s, r in enumerate(routed):
            arr = np.empty(0) if r is None else np.asarray(r["arr"], float)
            fin = np.empty(0) if r is None else r["fin"]
            if r is not None:
                seen = arr < T
                a_min = (arr // 60.0).astype(np.int64)
                od = seen & ~r["used"]
                self.arrivals[:, s] += np.bincount(a_min[seen], minlength=n)[:n]
                self.n_od[:, s] += np.bincount(a_min[od], minlength=n)[:n]
                self.cold[:, s] += np.bincount(a_min[od & r["cold"]], minlength=n)[:n]
                self.completed[:, s] += np.bincount((fin[fin < T] // 60.0).astype(np.int64), minlength=n)[:n]
            # peak in flight per minute of [t_lo, t_hi): sweep this interval's arrivals and finishes from the level
            # carried in (as max_inflight_per_minute does over the whole horizon)
            buf = np.concatenate([self.fin_pending[s], fin])
            now = buf < t_hi
            self.fin_pending[s] = buf[~now]
            times = np.concatenate([arr, buf[now]])
            delta = np.concatenate([np.ones(len(arr)), -np.ones(int(now.sum()))])
            o = np.lexsort((-delta, times))
            times, lvl = times[o], self.level[s] + np.cumsum(delta[o])
            if b_m > a_m:
                mins = (times // 60).astype(np.int64)
                inside = mins < b_m
                out = np.zeros(b_m - a_m)
                np.maximum.at(out, mins[inside] - a_m, lvl[inside])
                j = np.searchsorted(times, np.arange(a_m, b_m) * 60.0, side="left") - 1
                carry = np.where(j >= 0, lvl[np.maximum(j, 0)] if len(lvl) else 0.0, self.level[s])
                self.K[a_m:b_m, s] = np.maximum(out, carry)
            if len(lvl):
                self.level[s] = lvl[-1]
        self.final = b_m

    def view(self):
        nan = lambda *shape: np.full(shape, np.nan)  # noqa: E731
        n, S = self.n, self.S
        return EventTelemetry(N=nan(n), K=nan(n, S), P=nan(n, S), n_od=nan(n, S), cold=nan(n, S), filled=0,
                              arrivals=nan(n, S), completed=nan(n, S), inflight_end=nan(n, S), mem=nan(n))

    def expose(self, view: EventTelemetry, upto: int):
        """Show minutes [shown, upto] in the view (they must be final); later minutes stay NaN."""
        hi = min(upto + 1, self.n)
        if hi > self.final:
            raise RuntimeError(f"minute {hi - 1} is not final yet (final below {self.final}): lookahead")
        lo = self.shown
        if hi <= lo:
            return
        for f in self.FIELDS:
            getattr(view, f)[lo:hi] = getattr(self, f)[lo:hi]
        view.N[lo:hi] = self.arrivals[lo:hi, 0]
        view.P[lo:hi] = self.P[lo:hi]
        view.mem[lo:hi] = self.mem[lo:hi]
        prev = view.inflight_end[lo - 1] if lo > 0 else np.zeros(self.S)
        view.inflight_end[lo:hi] = prev + np.cumsum(self.arrivals[lo:hi] - self.completed[lo:hi], axis=0)
        view.filled = hi
        self.shown = hi


def simulate_events(cfg: PipelineConfig, draws: EventDraws, P_epoch: np.ndarray | None = None,
                    mem_epoch: np.ndarray | None = None, bill_init: bool = True, want_inflight: bool = False,
                    sample_seed: int | None = None, want_telemetry: bool = False, controller=None) -> dict:
    """Replay a provisioning schedule (per epoch, S stages) and memory schedule (open loop), or, with `controller`,
    let a controller set them epoch by epoch from what the simulation observes (closed loop, R2.2).
    want_telemetry: also return raw['telemetry'], an EventTelemetry (R2.2).

    Closed loop: `controller.decide(k, tel)` returns (P, memory) for epoch k; `controller.start(cfg, n_min, n_epochs)`
    is called first if defined. `tel` is an EventTelemetry whose minutes up to k*epoch_min - lag_min (5k - 2 at the
    defaults, the paper's feedback delay) hold the observed values and whose later minutes are NaN; it never shows a
    minute of epoch k or later. Epoch k is then simulated under that decision. raw['P_epoch'] and raw['mem_epoch']
    record the decisions."""
    if np.any(stage_demand(cfg) != 1.0):   # R2.5/R4.1: not modelled at event level (see PipelineConfig.stage_demand)
        raise NotImplementedError("event-level simulator: stage-specific demand (stage_demand != 1) is not modelled; "
                                  "fan-out joins, filter exits and batch formation would need defined semantics")
    if controller is not None:
        if P_epoch is not None or mem_epoch is not None:
            raise ValueError("pass either a schedule (open loop) or a controller (closed loop), not both")
        return _simulate_closed_loop(cfg, draws, controller, bill_init, want_inflight, want_telemetry, sample_seed)
    if P_epoch is None or mem_epoch is None:
        raise ValueError("open loop needs P_epoch and mem_epoch")
    S, E = cfg.n_stages, cfg.epoch_min
    P_min = np.repeat(np.asarray(P_epoch, float), E, axis=0)[:draws.n_min]
    mem_min = np.repeat(np.asarray(mem_epoch), E)[:draws.n_min]
    gen_min = np.concatenate([[0], np.cumsum(mem_min[1:] != mem_min[:-1])])  # M5 fix: memory version per minute
    eng = _EventEngine(cfg, draws, bill_init, keep_times=want_inflight or want_telemetry)
    P_l = [P_min[:, s].tolist() for s in range(S)]
    G_l = gen_min.tolist()
    for k in range(-(-draws.n_min // E)):            # epoch-major: epoch k, every stage, state carried over
        eng.route_until((k + 1) * E * 60.0, P_l, G_l, mem_min)
    eng.drain(P_l, G_l, mem_min)
    return _event_results(cfg, draws, eng, P_min, mem_min, bill_init, want_inflight, want_telemetry, sample_seed)


def _simulate_closed_loop(cfg, draws, controller, bill_init, want_inflight, want_telemetry, sample_seed):
    """R2.2, stage 2. Each epoch k: show the controller the telemetry observed up to minute k*E - L (never a minute of
    epoch k or later), take its decision for epoch k, route epoch k under it, fold the outcome into the telemetry.
    The routing engine, its carried state and the final aggregation are the open loop's."""
    S, E, L = cfg.n_stages, cfg.epoch_min, cfg.lag_min
    n = draws.n_min
    n_ep = -(-n // E)
    eng = _EventEngine(cfg, draws, bill_init, keep_times=True)
    obs = _ObservedTelemetry(cfg, draws)
    view = obs.view()
    if hasattr(controller, "start"):
        controller.start(cfg, n, n_ep)
    P_l = [[] for _ in range(S)]
    G_l = []
    mem_min = np.zeros(n, np.int64)
    P_ep, m_ep = np.zeros((n_ep, S)), np.zeros(n_ep, np.int64)
    gen, m_prev = 0, None
    for k in range(n_ep):
        obs.expose(view, min(k * E - L, k * E - 1))   # the paper's feedback delay; never epoch k's own minutes
        P, m = controller.decide(k, view)
        P = np.asarray(P, float)
        if P.shape != (S,) or np.any(P < 0) or not np.all(np.isfinite(P)):
            raise ValueError(f"controller returned invalid P {P} at epoch {k}")
        m = int(m)
        if m not in cfg.mem_options:
            raise ValueError(f"controller returned memory {m} at epoch {k}, not one of {cfg.mem_options}")
        a, b = k * E, min((k + 1) * E, n)
        if m_prev is not None and m != m_prev:
            gen += 1                                   # M5 fix: a new memory version, as gen_min counts in open loop
        m_prev = m
        for s in range(S):
            P_l[s].extend([float(P[s])] * (b - a))
        G_l.extend([gen] * (b - a))
        mem_min[a:b] = m
        obs.P[a:b], obs.mem[a:b] = P, m
        P_ep[k], m_ep[k] = P, m
        routed = eng.route_until((k + 1) * E * 60.0, P_l, G_l, mem_min)
        obs.add(routed, k * E * 60.0, (k + 1) * E * 60.0)
    eng.drain(P_l, G_l, mem_min)
    P_min = np.array(P_l, float).T.reshape(n, S)
    res = _event_results(cfg, draws, eng, P_min, mem_min, bill_init, want_inflight, want_telemetry, sample_seed)
    res["raw"]["P_epoch"], res["raw"]["mem_epoch"] = P_ep, m_ep
    res["raw"]["observed"] = view        # the telemetry as the controller last saw it
    return res


def _event_results(cfg, draws, eng, P_min, mem_min, bill_init, want_inflight, want_telemetry, sample_seed):
    """Summary and raw outputs of a routed horizon; the former stage-major aggregation, unchanged, applied to each
    stage's requests in routing order."""
    S = cfg.n_stages
    pr = cfg.prices
    cost = (P_min * (mem_min[:, None] / 1024.0) * 60.0 * pr.pc).sum() + draws.n * S * pr.req
    od_share, cold_ratio, inflight, stel = [], [], [], []
    for s in range(S):
        cold, used_pc = eng.stage(s, "cold", bool), eng.stage(s, "used", bool)
        cost += eng.stage(s, "ex").sum()
        if bill_init:
            cost += eng.stage(s, "ini").sum()
        od_share.append(1 - used_pc.mean())
        cold_ratio.append(cold.mean())
        if want_inflight or want_telemetry:
            arr, fin = eng.stage(s, "arr"), eng.stage(s, "fin")
            if want_inflight:
                inflight.append(max_inflight_per_minute(arr, fin, draws.n_min))
            if want_telemetry:
                stel.append(stage_telemetry(arr, fin, cold, used_pc, draws.n_min))
    done = eng.done                  # after final stage incl. its orchestration overhead
    lat = done - draws.arrival
    ok = lat <= cfg.deadline
    ontime = np.bincount(draws.minute, weights=ok.astype(float), minlength=draws.n_min)
    N = draws.counts.astype(float)
    att, late, tot = window_attainment(N, ontime, cfg.window_min)
    sev = severity(att, late, tot, 1 - cfg.sla_eps)
    out = dict(cost=float(cost), record_attainment=float(ok.mean()),
               p99_latency=weighted_quantile_hist(lat[None, :], np.ones((1, 1)), 0.99),
               overflow_share=float(np.mean(od_share)), cold_start_ratio=float(np.mean(cold_ratio)),
               slo_met=bool(sev["violating_window_rate"] <= cfg.slo_violating_window_target + 1e-12), **sev)
    raw = dict(window_attainment=att.astype(np.float32), overflow_share_stage=np.array(od_share))
    if want_inflight:
        raw["inflight_max"] = np.stack(inflight, 1).astype(np.float32)
    if want_telemetry:
        col = {f: np.stack([t[f] for t in stel], 1).astype(float) for f in stel[0]}
        raw["telemetry"] = EventTelemetry(
            N=draws.counts.astype(float), K=col["K"], P=P_min.copy(), n_od=col["n_od"], cold=col["cold"],
            filled=draws.n_min, arrivals=col["arrivals"], completed=col["completed"],
            inflight_end=col["inflight_end"], mem=np.asarray(mem_min).copy())
    if sample_seed is not None:  # latency-sampling error of the fast simulator (Supplement S4)
        raw["sampling_flip_share"] = sampling_flips(draws, lat, cfg, sample_seed)
        raw["sampling_flip_direction"] = sampling_flip_direction(draws, lat, cfg, sample_seed)
    return dict(summary=out, raw=raw)


def sampling_flip_direction(draws: EventDraws, lat: np.ndarray, cfg: PipelineConfig, seed: int,
                            reps: int = 5):
    """Direction of the sampling-induced misclassification (R5.M1).

    sampling_flips reports how often the 100-request sample changes a window's compliance
    verdict; Reviewer 5 notes the net direction was never reported. Returns the share of
    windows the sample calls compliant while exact attainment calls them violating
    ("optimistic" - these hide real violations) and the converse ("pessimistic"), plus
    net = optimistic - pessimistic. Positive net means sampling understates violations.
    """
    N = draws.counts.astype(float)
    ok = (lat <= cfg.deadline).astype(float)
    exact_ot = np.bincount(draws.minute, weights=ok, minlength=draws.n_min)
    att_exact, _, _ = window_attainment(N, exact_ot, cfg.window_min)
    starts = np.concatenate([[0], np.cumsum(draws.counts)[:-1]])
    rng = np.random.default_rng(seed)
    thr = 1 - cfg.sla_eps
    exact_bad = att_exact < thr
    opt, pes = [], []
    k = cfg.latency_samples
    for _ in range(reps):
        pick = starts[:, None] + (rng.uniform(size=(draws.n_min, k)) * np.maximum(draws.counts, 1)[:, None]).astype(np.int64)
        pick = np.minimum(pick, len(ok) - 1)
        frac = np.where(draws.counts > 0, ok[pick].mean(1), 1.0)
        att_s, _, _ = window_attainment(N, N * frac, cfg.window_min)
        samp_bad = att_s < thr
        opt.append(float(np.mean(exact_bad & ~samp_bad)))
        pes.append(float(np.mean(~exact_bad & samp_bad)))
    o, p_ = float(np.mean(opt)), float(np.mean(pes))
    return dict(optimistic=o, pessimistic=p_, net=o - p_)


def sampling_flips(draws: EventDraws, lat: np.ndarray, cfg: PipelineConfig, seed: int, reps: int = 5):
    """Share of windows whose compliance classification changes when attainment is
    estimated from 100 sampled requests per minute (volume weighted) instead of exactly."""
    N = draws.counts.astype(float)
    ok = (lat <= cfg.deadline).astype(float)
    exact_ot = np.bincount(draws.minute, weights=ok, minlength=draws.n_min)
    att_exact, _, _ = window_attainment(N, exact_ot, cfg.window_min)
    starts = np.concatenate([[0], np.cumsum(draws.counts)[:-1]])
    rng = np.random.default_rng(seed)
    flips = []
    k = cfg.latency_samples
    for _ in range(reps):
        pick = starts[:, None] + (rng.uniform(size=(draws.n_min, k)) * np.maximum(draws.counts, 1)[:, None]).astype(np.int64)
        pick = np.minimum(pick, len(ok) - 1)
        frac = np.where(draws.counts > 0, ok[pick].mean(1), 1.0)
        att_s, _, _ = window_attainment(N, N * frac, cfg.window_min)
        thr = 1 - cfg.sla_eps
        flips.append(np.mean((att_s < thr) != (att_exact < thr)))
    return np.array(flips)
