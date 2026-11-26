#!/usr/bin/env python3
"""End-to-end smoke check of the closed-loop evaluator on development seed 101 (R2.1, R4.2, R6.4). EXPLORATORY;
development inputs only (PRESPECIFICATION.md section 3), PRE-CALIBRATION defaults. Full weeks with the GBM forecaster,
complementing the unit tests (tests/test_des_closed_loop.py, which use a seasonal-naive forecaster for speed).

Checks, on the closed-loop validation week of trace 101 (event draw key 2):
  A. telemetry cutoff: at every decision k the controller's view holds minutes [0, max(0, 5k-1)) and nothing later
     (every field NaN from the visible horizon on), i.e. the paper's feedback delay 5k-2;
  B. exact attainment: window attainment is computed from every request's latency: the per-minute request counts it
     uses sum to the number of requests, the on-time counts are integers, and the violating-window rate recomputed
     from them equals the reported one;
  C. no lookahead at full scale: demand after the minute an epoch-k decision must not see is changed sharply (x3 + 200,
     every earlier request's draws kept, as tests/test_des_closed_loop.py splice()); decisions up to k are identical,
     the forecaster's decision-time inputs (q_raw, q_cal, s) are identical up to k, the realised targets y (filled
     only once observed) are identical for every epoch whose window ends before the cut, and later decisions change
     (QuantProv-q90 with GBM forecasts, and Reactive). The first run of this check compared y up to k and flagged the
     two epochs whose windows reach the cut; that was a defect of the check, corrected here;
  D. shared forecasting (R6.4): PRISM and QuantProv-q90 run on the same week read identical calibrated forecasts
     (q_raw, q_cal and the conformal offset at every epoch), and both apply the 0.85 scale-in rule.

usage (from prism-repro/): python docs/revision/confirmatory_20261122/smoke_check_101.py <out.json>
"""
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from prism_repro import des                                          # noqa: E402
from prism_repro.closed_loop import PolicyController                 # noqa: E402
from prism_repro.config import PipelineConfig, PrismConfig           # noqa: E402
from prism_repro.des import EventDraws, simulate_events              # noqa: E402
from prism_repro.experiment import WEEK_START, TraceBundle, make_policy  # noqa: E402

OUT = sys.argv[1]
cfg = PipelineConfig()
E, L = cfg.epoch_min, cfg.lag_min
MAIN = ("stationary", "growth", "bursty", "new_spike")
t_start = time.time()
b = TraceBundle(101, cfg, scenarios=MAIN)
ws = WEEK_START["val"]
counts = b.traces["stationary"]["counts"][ws:ws + 7 * 1440].copy()
dr = EventDraws(cfg, counts, 101, 2)
report = dict(label="EXPLORATORY smoke check, development seed 101, validation week; PRE-CALIBRATION defaults",
              n_requests=int(dr.n), checks={})

captured = []
_orig_wa = des.window_attainment


def _capture(N, ontime, w):
    captured.append((np.array(N, float), np.array(ontime, float), w))
    return _orig_wa(N, ontime, w)


des.window_attainment = _capture          # the module-level name _event_results calls


class Recorder:
    """Wraps a PolicyController; checks the view at every decision before the policy reads it."""

    def __init__(self, ctl):
        self.ctl, self.bad, self.n = ctl, [], 0

    def start(self, *a):
        return self.ctl.start(*a)

    def decide(self, k, tel):
        self.n += 1
        want = max(0, k * E - L + 1)          # minutes [0, 5k-1) are visible, i.e. up to 5k-2
        if tel.filled != want:
            self.bad.append((k, "filled", int(tel.filled), want))
        for f in ("N", "K", "P", "n_od", "cold", "arrivals", "completed", "inflight_end", "mem"):
            a = getattr(tel, f)
            if np.any(np.isfinite(a[want:])):
                self.bad.append((k, f, "finite beyond the visible horizon"))
            if want and not np.all(np.isfinite(a[:want])):
                self.bad.append((k, f, "NaN inside the visible horizon"))
        return self.ctl.decide(k, tel)


def run(spec, draws, counts_for_check=None):
    pol = make_policy(spec)
    ctl = PolicyController(pol, b, "stationary", week="val")
    rec = Recorder(ctl)
    n0 = len(captured)
    t0 = time.time()
    res = simulate_events(cfg, draws, controller=rec)
    assert len(captured) == n0 + 1
    return pol, ctl, rec, res, captured[-1], round(time.time() - t0, 1)


# ---------------- A, B, D: PRISM and QuantProv-q90 on the same week
runs = {}
for name, spec in (("PRISM", dict(family="PRISM", param=0.02)), ("QuantProv_q90", dict(family="QuantProv", tau_idx=2, param=1.0))):
    pol, ctl, rec, res, (N, ontime, w), rt = run(spec, dr)
    s = res["summary"]
    nwin = len(N) // w
    tot_w, ok_w = N[:nwin * w].reshape(nwin, w).sum(1), ontime[:nwin * w].reshape(nwin, w).sum(1)
    att = np.where(tot_w > 0, ok_w / np.where(tot_w > 0, tot_w, 1), 1.0)     # an empty window counts as attained
    vwr = float(np.mean(att < 1 - cfg.sla_eps - 1e-12))
    runs[name] = (pol, ctl)
    report["checks"][f"A telemetry cutoff, {name}"] = dict(decisions=rec.n, violations=rec.bad[:5], ok=not rec.bad)
    report["checks"][f"B exact attainment, {name}"] = dict(
        requests_counted=float(N.sum()), requests=int(dr.n), ontime_integer=bool(np.all(ontime == np.round(ontime))),
        record_attainment_reported=float(s["record_attainment"]), record_attainment_from_counts=float(ontime.sum() / N.sum()),
        windows=int(nwin), violating_window_rate_reported=float(s["violating_window_rate"]),
        violating_window_rate_recomputed=vwr, runtime_s=rt,
        ok=bool(N.sum() == dr.n and np.all(ontime == np.round(ontime))
                and abs(ontime.sum() / N.sum() - s["record_attainment"]) < 1e-12
                and abs(vwr - s["violating_window_rate"]) < 1e-12))
fp, fq = runs["PRISM"][1].forecasts["gbm"].arrays, runs["QuantProv_q90"][1].forecasts["gbm"].arrays
same = {k: bool(np.array_equal(np.asarray(fp[k]), np.asarray(fq[k]), equal_nan=True)) for k in fp}
pc = PrismConfig()
qp = runs["QuantProv_q90"][0]
report["checks"]["D shared forecasting and smoothing (R6.4)"] = dict(
    forecast_arrays_identical=same, prism_reads="q_cal" if pc.use_conformal else "q_raw", quantprov_reads="q_cal",
    prism_scale_in=dict(use_hysteresis=pc.use_hysteresis, factor=pc.hysteresis, applies_when="memory unchanged"),
    quantprov_scale_in=dict(factor=qp.hyst), ok=all(same.values()) and pc.use_conformal and pc.use_hysteresis
    and qp.hyst == pc.hysteresis)


# ---------------- C: no lookahead, full week, real forecaster
def splice(dr0, counts_new, cut_min, seed):
    """As tests/test_des_closed_loop.py splice(): keep every request of minutes < cut_min exactly as in dr0."""
    assert np.array_equal(counts_new[:cut_min], dr0.counts[:cut_min])
    alt = EventDraws(cfg, counts_new, seed, 9)
    n_keep = int(np.sum(dr0.counts[:cut_min]))
    assert np.all(dr0.minute[:n_keep] < cut_min) and np.all(alt.minute[:n_keep] < cut_min)
    alt.arrival[:n_keep] = dr0.arrival[:n_keep]
    for f in ("ex", "ov", "init"):
        getattr(alt, f)[:, :n_keep] = getattr(dr0, f)[:, :n_keep]
    assert np.all(np.diff(alt.arrival) >= 0)
    return alt


k = 1000                                    # an epoch in the middle of the week (day 3.5)
cut = k * E - L + 1                         # first minute the epoch-k decision must not see
alt_counts = counts.copy()
alt_counts[cut:] = alt_counts[cut:] * 3 + 200
dra = splice(dr, alt_counts, cut, 77)
for name, spec in (("QuantProv_q90", dict(family="QuantProv", tau_idx=2, param=1.0)), ("Reactive", dict(family="Reactive", param=0.7))):
    _, c0, _, r0, _, _ = run(spec, dr)
    _, c1, _, r1, _, _ = run(spec, dra)
    Pb, Pa = r0["raw"]["P_epoch"], r1["raw"]["P_epoch"]
    row = dict(epoch=k, cut_minute=cut, decisions_identical_up_to_k=bool(np.array_equal(Pa[:k + 1], Pb[:k + 1])),
               memory_identical_up_to_k=bool(np.array_equal(r1["raw"]["mem_epoch"][:k + 1], r0["raw"]["mem_epoch"][:k + 1])),
               later_decisions_changed=bool(np.any(Pa[k + 1:] != Pb[k + 1:])))
    if name != "Reactive":
        f0, f1 = c0.forecasts["gbm"].arrays, c1.forecasts["gbm"].arrays
        # q_raw, q_cal and s are what the policy reads at decision time: they must be identical up to k.
        row["decision_inputs_identical_up_to_k"] = {
            kk: bool(np.array_equal(np.asarray(f1[kk])[:k + 1], np.asarray(f0[kk])[:k + 1])) for kk in ("q_raw", "q_cal", "s")}
        # y[j] is epoch j's realised window peak, filled once observed (closed_loop.OnlineForecast). Its window is
        # minutes [5j - L + h_lo, 5j - L + h_hi] = [5j, 5j + 4]: only windows reaching the cut minute may differ.
        from prism_repro.features import forecast_horizon
        h_lo, h_hi = forecast_horizon(cfg)
        win_end = np.arange(k + 1) * E - L + h_hi
        j_max = int(np.max(np.nonzero(win_end < cut)[0]))
        y0, y1 = np.asarray(f0["y"])[:k + 1], np.asarray(f1["y"])[:k + 1]
        same = (y0 == y1) | (np.isnan(y0) & np.isnan(y1))
        diff_j = [int(j) for j in np.nonzero(~same)[0]]
        row["realised_targets"] = dict(
            identical_for_windows_before_cut=bool(np.array_equal(y0[:j_max + 1], y1[:j_max + 1], equal_nan=True)),
            last_epoch_with_window_before_cut=j_max, epochs_that_differ=diff_j,
            all_differences_in_windows_reaching_the_cut=all(j > j_max for j in diff_j))
    rt = row.get("realised_targets", {})
    row["ok"] = (row["decisions_identical_up_to_k"] and row["memory_identical_up_to_k"] and row["later_decisions_changed"]
                 and all(row.get("decision_inputs_identical_up_to_k", {"": True}).values())
                 and rt.get("identical_for_windows_before_cut", True) and rt.get("all_differences_in_windows_reaching_the_cut", True))
    report["checks"][f"C no lookahead, {name}"] = row
des.window_attainment = _orig_wa
report["all_ok"] = all(v["ok"] for v in report["checks"].values())
report["runtime_s"] = round(time.time() - t_start, 1)
json.dump(report, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1)
print(json.dumps(report, indent=1))
sys.exit(0 if report["all_ok"] else 1)
