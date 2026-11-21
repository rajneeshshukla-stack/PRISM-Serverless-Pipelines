"""Closed-loop control in the event-level simulator (R2.2, R6.3).

Two properties are tested, not assumed:
  1. NO LOOKAHEAD. Demand changes sharply right after the minute a decision may observe (5k - 2); every decision up
     to epoch k is identical with and without the change, and later decisions respond to it.
  2. CONSERVATION ACROSS BOUNDARIES. In closed loop, arrivals minus completions accumulate to the executions in
     flight, per minute and per window, every stage, over the whole horizon, with requests in flight at epoch
     boundaries; and the telemetry the controller saw equals the final telemetry, minute for minute.
Both modes are tested: without a controller the open-loop replay is unchanged (as E9 and E12 call it; byte identity
with the stage-major code is tests/test_des_epoch_major_guard.py), and a closed loop that replays a schedule equals
the open loop byte for byte. The conformal offset and the cold-hit estimate are shown to come from observed outcomes.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from prism_repro.closed_loop import PolicyController, ScheduleController  # noqa: E402
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.des import EventDraws, simulate_events  # noqa: E402
from prism_repro.experiment import WEEK_START, TraceBundle, make_policy  # noqa: E402
from test_des_epoch_major_guard import demand_schedule, flatten, load_reference  # noqa: E402

H = 240                       # first four hours of the test week: 48 epochs
WS = WEEK_START["test"]
CLOSED_ONLY = ("raw.P_epoch", "raw.mem_epoch", "raw.observed")
SPECS = {"PRISM": dict(family="PRISM", param=0.02, fc="seasonal_naive"),
         "QuantProv_q90": dict(family="QuantProv", tau_idx=2, param=1.0, fc="seasonal_naive"),
         "Reactive": dict(family="Reactive", param=0.6)}


def open_part(flat):
    return {k: v for k, v in flat.items() if not k.startswith(CLOSED_ONLY)}


def splice(dr, cfg, counts_new, cut_min, seed):
    """Event draws for counts_new that keep every request of minutes < cut_min exactly as in dr (arrival, execution,
    orchestration and initialisation draws) and draw fresh ones for the later minutes."""
    assert np.array_equal(counts_new[:cut_min], dr.counts[:cut_min])
    alt = EventDraws(cfg, counts_new, seed, 9)
    n_keep = int(np.sum(dr.counts[:cut_min]))
    assert np.all(dr.minute[:n_keep] < cut_min) and np.all(alt.minute[:n_keep] < cut_min)
    alt.arrival[:n_keep] = dr.arrival[:n_keep]
    for f in ("ex", "ov", "init"):
        getattr(alt, f)[:, :n_keep] = getattr(dr, f)[:, :n_keep]
    assert np.all(np.diff(alt.arrival) >= 0)
    return alt


class _Loop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = PipelineConfig()
        cls.b = TraceBundle(101, cls.cfg, scenarios=("stationary", "new_spike"), forecasters=("seasonal_naive",))

    def counts(self, sc):
        return self.b.traces[sc]["counts"][WS:WS + H].copy()

    def closed(self, spec, dr, sc="stationary", cfg=None, **kw):
        pol = make_policy(spec)
        ctl = PolicyController(pol, self.b, sc)
        return simulate_events(cfg or self.cfg, dr, controller=ctl, **kw), ctl, pol


class TestBothModes(_Loop):
    def test_open_loop_unchanged_without_a_controller(self):
        """E9 and E12 call simulate_events(cfg, draws, P_epoch, mem_epoch, want_inflight=..., sample_seed=...)."""
        ref = load_reference()
        counts = self.counts("new_spike")
        dr = EventDraws(self.cfg, counts, 101, 3)
        P, mem = demand_schedule(counts, self.cfg, np.random.default_rng(1))
        for kw in (dict(want_inflight=True, sample_seed=1101), dict(want_inflight=False, sample_seed=None)):
            self.assertEqual(flatten(simulate_events(self.cfg, dr, P, mem, **kw)),
                             flatten(ref.simulate_events(self.cfg, dr, P, mem, **kw)))
        with self.assertRaises(ValueError):
            simulate_events(self.cfg, dr, P, mem, controller=ScheduleController(P, mem))
        with self.assertRaises(ValueError):
            simulate_events(self.cfg, dr)

    def test_closed_loop_replaying_a_schedule_equals_the_open_loop(self):
        for sc in ("stationary", "new_spike"):
            counts = self.counts(sc)
            dr = EventDraws(self.cfg, counts, 101, 3)
            P, mem = demand_schedule(counts, self.cfg, np.random.default_rng(2), mem_switch=0.2)
            kw = dict(want_inflight=True, want_telemetry=True, sample_seed=5)
            o = flatten(simulate_events(self.cfg, dr, P, mem, **kw))
            res = simulate_events(self.cfg, dr, controller=ScheduleController(P, mem), **kw)
            self.assertEqual(open_part(flatten(res)), o, sc)
            np.testing.assert_array_equal(res["raw"]["P_epoch"], P)
            np.testing.assert_array_equal(res["raw"]["mem_epoch"], mem)

    def test_closed_loop_decisions_replayed_open_loop_give_the_same_run(self):
        dr = EventDraws(self.cfg, self.counts("new_spike"), 101, 3)
        res, _, _ = self.closed(SPECS["PRISM"], dr, "new_spike", want_telemetry=True)
        o = simulate_events(self.cfg, dr, res["raw"]["P_epoch"], res["raw"]["mem_epoch"], want_telemetry=True)
        self.assertEqual(open_part(flatten(res)), flatten(o))


class TestNoLookahead(_Loop):
    def test_controller_never_sees_beyond_its_feedback_delay(self):
        E, L = self.cfg.epoch_min, self.cfg.lag_min
        seen = []

        class Spy:
            def decide(self, k, tel):
                for f in ("N", "K", "P", "n_od", "cold", "arrivals", "completed", "inflight_end", "mem"):
                    a = getattr(tel, f)
                    fin = np.isfinite(a) if a.ndim == 1 else np.isfinite(a).all(axis=1)
                    last = int(np.flatnonzero(fin)[-1]) if fin.any() else -1
                    seen.append((k, f, last, bool(np.all(~(np.isfinite(a[last + 1:]))))))
                return np.full(4, 20.0), 1024

        counts = self.counts("stationary")
        simulate_events(self.cfg, EventDraws(self.cfg, counts, 101, 3), controller=Spy())
        for k, f, last, rest_nan in seen:
            self.assertEqual(last, max(k * E - L, -1), (k, f))     # the paper's 5k - 2, nothing of epoch k or later
            self.assertTrue(rest_nan, (k, f))

    def test_decisions_do_not_move_when_later_minutes_change(self):
        E, L = self.cfg.epoch_min, self.cfg.lag_min
        counts = self.counts("stationary")
        dr = EventDraws(self.cfg, counts, 101, 3)
        for name, spec in SPECS.items():
            base, ctl0, _ = self.closed(spec, dr)
            for k in (9, 26):
                cut = k * E - L + 1                         # first minute the epoch-k decision must not see
                alt_counts = counts.copy()
                alt_counts[cut:] = alt_counts[cut:] * 3 + 200   # sharp, sustained change of demand
                alt, ctl1, _ = self.closed(spec, splice(dr, self.cfg, alt_counts, cut, 77))
                Pb, Pa = base["raw"]["P_epoch"], alt["raw"]["P_epoch"]
                np.testing.assert_array_equal(Pa[:k + 1], Pb[:k + 1], f"{name}: decision moved before epoch {k + 1}")
                np.testing.assert_array_equal(alt["raw"]["mem_epoch"][:k + 1], base["raw"]["mem_epoch"][:k + 1])
                self.assertTrue(np.any(Pa[k + 1:] != Pb[k + 1:]), f"{name}: the change at minute {cut} never showed")
                if name != "Reactive":
                    f0 = ctl0.forecasts["seasonal_naive"].arrays
                    f1 = ctl1.forecasts["seasonal_naive"].arrays
                    np.testing.assert_array_equal(f1["q_raw"][:k + 1], f0["q_raw"][:k + 1])
                    np.testing.assert_array_equal(f1["s"][:k + 1], f0["s"][:k + 1])


class TestConservationAcrossBoundaries(_Loop):
    def _check(self, res, cfg, n_req, case):
        tel, obs = res["raw"]["telemetry"], res["raw"]["observed"]
        S, E, w = cfg.n_stages, cfg.epoch_min, cfg.window_min
        net = np.cumsum(tel.arrivals, 0) - np.cumsum(tel.completed, 0)
        np.testing.assert_array_equal(net, tel.inflight_end, case)                      # per minute, every stage
        np.testing.assert_array_equal(net[w - 1::w], tel.inflight_end[w - 1::w], case)  # per window
        np.testing.assert_array_equal(tel.arrivals.sum(0), np.full(S, n_req), case)     # nobody lost or duplicated
        np.testing.assert_array_equal(tel.completed.sum(0), np.full(S, n_req), case)
        np.testing.assert_array_equal(tel.inflight_end[-1], np.zeros(S), case)         # the horizon drains
        boundary = tel.inflight_end[E - 1:-E:E]                                         # end of every epoch but the last
        self.assertGreater(int((boundary > 0).sum()), 0, f"{case}: no request in flight at an epoch boundary")
        shown = obs.filled
        self.assertGreater(shown, 0)
        for f in ("arrivals", "completed", "n_od", "cold", "inflight_end", "K", "P"):   # what the controller saw is true
            np.testing.assert_array_equal(getattr(obs, f)[:shown], getattr(tel, f)[:shown], f"{case}: {f}")
        np.testing.assert_array_equal(obs.N[:shown], tel.N[:shown])
        return int((boundary > 0).sum())

    def test_prism_closed_loop(self):
        counts = self.counts("new_spike")
        counts[-10:] = 0                                    # drain, so every request finishes inside the horizon
        dr = EventDraws(self.cfg, counts, 101, 3)
        res, _, _ = self.closed(SPECS["PRISM"], dr, "new_spike", want_telemetry=True)
        self._check(res, self.cfg, dr.n, "PRISM")

    def test_requests_spanning_several_epochs(self):
        # executions of several minutes (stage 2 about 7 minutes against 5-minute epochs): a request that starts in
        # epoch k finishes in epoch k+2 or later and must be counted once, in the minute it finishes
        cfg = self.cfg.with_(warm_mean_1024=(150.0, 420.0, 90.0, 260.0))
        rng = np.random.default_rng(3)
        counts = rng.poisson(5, H)
        counts[-60:] = 0
        dr = EventDraws(cfg, counts, 101, 3)
        self.assertGreater(float(np.mean(dr.ex[1] * 420.0 > 2 * cfg.epoch_min * 60)), 0.05)
        res = simulate_events(cfg, dr, controller=PolicyController(make_policy(SPECS["Reactive"]), self.b,
                                                                    "stationary"), want_telemetry=True)
        n_boundaries = self._check(res, cfg, dr.n, "long executions")
        self.assertGreater(n_boundaries, 10)


class TestObservedOutcomes(_Loop):
    def test_conformal_offset_is_computed_from_observed_arrivals(self):
        E, L = self.cfg.epoch_min, self.cfg.lag_min
        K = H // E
        for sc in ("stationary", "new_spike"):
            counts = self.counts(sc)
            dr = EventDraws(self.cfg, counts, 101, 3)
            _, ctl, _ = self.closed(SPECS["QuantProv_q90"], dr, sc)
            f, st = ctl.forecasts["seasonal_naive"].arrays, self.b.forecasts[(sc, "test", "seasonal_naive")]
            for key in ("q_raw", "s", "q_cal"):   # arrivals are exogenous: observing them reproduces the schedule
                np.testing.assert_array_equal(f[key][:K], st[key][:K], f"{sc}: {key}")
            np.testing.assert_array_equal(f["y"][:K - 2], st["y"][:K - 2])   # realised peaks observed so far
            self.assertTrue(np.all(np.isnan(f["y"][K - 2:])))                 # the last two are not observable yet
        # different observed outcomes give different offsets: the update reads the telemetry, not the schedule
        counts = self.counts("stationary")
        dr = EventDraws(self.cfg, counts, 101, 3)
        cut = 10 * E - L + 1
        alt_counts = counts.copy()
        alt_counts[cut:] = alt_counts[cut:] * 3 + 200
        _, ctl, _ = self.closed(SPECS["QuantProv_q90"], splice(dr, self.cfg, alt_counts, cut, 78))
        s_alt, s_sched = ctl.forecasts["seasonal_naive"].arrays["s"][:K], self.b.forecasts[
            ("stationary", "test", "seasonal_naive")]["s"][:K]
        np.testing.assert_array_equal(s_alt[:11], s_sched[:11])
        self.assertTrue(np.any(s_alt[11:] != s_sched[11:]))

    def test_cold_hit_estimate_follows_event_level_telemetry(self):
        dr = EventDraws(self.cfg, self.counts("new_spike"), 101, 3)
        res, _, pol = self.closed(SPECS["PRISM"], dr, "new_spike", want_telemetry=True)
        kappa = pol.rec["kappa"].copy()
        self.assertTrue(kappa[0] == pol.pcfg.kappa_prior and np.any(kappa != kappa[0]))   # it moved off the prior
        # replaying PRISM's own update over the final event-level telemetry gives the same estimates
        fresh = make_policy(SPECS["PRISM"])
        PolicyController(fresh, self.b, "new_spike").start(self.cfg, dr.n_min, len(kappa))
        for k in range(len(kappa)):
            fresh._update_kappa(k, res["raw"]["telemetry"])
            self.assertEqual(fresh.kappa, kappa[k], k)


class TestOnlineForecastTrim(_Loop):
    def test_trimmed_history_gives_identical_forecasts(self):
        """The feature builder is given counts from a week-aligned start (runtime); forecasts must not change. Epochs
        0-360 cover the trim start moving from trace minute 20160 to 30240 (near epoch 328)."""
        from prism_repro.closed_loop import OnlineForecast
        for sc in ("stationary", "new_spike"):
            tel = type("T", (), {})()
            tel.N = self.b.traces[sc]["counts"][WS:WS + 7 * 1440].astype(float)
            f = OnlineForecast(self.b, sc, "test", "seasonal_naive", self.cfg, 2016, trim=True)
            for k in range(361):
                f.step(k, tel)
            st = self.b.forecasts[(sc, "test", "seasonal_naive")]
            for key in ("q_raw", "s", "q_cal"):
                np.testing.assert_array_equal(f.arrays[key][:361], st[key][:361], f"{sc}: {key}")


class TestValidationWeek(_Loop):
    """Closed loop on the validation week (tuning), for the submitted split and the PROVISIONAL split with an
    out-of-sample conformal warm-up (R4.6 / R5.M3): fitting, warm-up, feedback and scoring respect the split."""

    def _val_run(self, bundle):
        from prism_repro.workload import MIN_PER_DAY
        ws = WEEK_START["val"]
        counts = bundle.traces["stationary"]["counts"][ws:ws + H]
        dr = EventDraws(self.cfg, counts, 101, 2)                 # scoring: the validation week alone
        ctl = PolicyController(make_policy(SPECS["QuantProv_q90"]), bundle, "stationary", week="val")
        simulate_events(self.cfg, dr, controller=ctl)
        f = ctl.forecasts["seasonal_naive"]
        st = bundle.forecasts[("stationary", "val", "seasonal_naive")]
        K = H // self.cfg.epoch_min
        for key in ("q_raw", "s", "q_cal"):
            np.testing.assert_array_equal(f.arrays[key][:K], st[key][:K], key)
        self.assertGreaterEqual(f.scaler.delay, 2)                # feedback no earlier than observable
        return f, MIN_PER_DAY

    def test_submitted_split(self):
        f, _ = self._val_run(self.b)
        self.assertEqual(f.warmup_epochs, 0)
        self.assertEqual(f.arrays["s"][0], 0.0)

    def test_provisional_split_with_out_of_sample_warmup(self):
        from prism_repro.config import PrismConfig
        b = TraceBundle(101, self.cfg, scenarios=("stationary",), forecasters=("seasonal_naive",),
                        conformal=PrismConfig(forecast_train_days=11, conformal_warmup_days=3))
        f, DAY = self._val_run(b)
        self.assertEqual(f.warmup_epochs, 3 * DAY // self.cfg.epoch_min)
        self.assertEqual(f.train_hi, 11 * DAY)
        self.assertTrue(f.warmup_out_of_sample)                   # first warm-up target at or after the fit's end
        self.assertGreaterEqual(f.warmup_first_target, 11 * DAY)
        self.assertNotEqual(f.arrays["s"][0], 0.0)                # the offset enters validation warm


if __name__ == "__main__":
    unittest.main()
