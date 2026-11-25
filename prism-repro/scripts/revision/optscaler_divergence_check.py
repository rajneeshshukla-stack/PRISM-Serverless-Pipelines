#!/usr/bin/env python3
"""POST HOC mechanism check for the OLR divergence seen in docs/revision/optscaler_r32_20261124 (R3.2).
Replays one validation run (trace, c*) with the prespecified policy and records, per stage and decision epoch, w_k,
the provisioned level, the largest unit workload u = y/x among the OLR feedback minutes, and how many feedback minutes
had observed utilization capped at 1. LMS (Algorithm 1) is unstable once eta * u^2 > 2.
usage (from prism-repro/): venv/Scripts/python scripts/revision/optscaler_divergence_check.py <out json> <seed> <c*>
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
from prism_repro.config import PipelineConfig  # noqa: E402
from prism_repro.experiment import TraceBundle  # noqa: E402
from prism_repro.simulator import simulate  # noqa: E402
import optscaler_policy as op  # noqa: E402


class Traced(op.OptScaler):
    def prepare(self, ctx):
        super().prepare(ctx)
        self.trace = []

    def _feedback(self, tel, v):
        lo = self.fed_upto + 1
        u_max = np.zeros(self.cfg.n_stages)
        capped = np.zeros(self.cfg.n_stages, int)
        for t in range(lo, v + 1):
            P, K, y = tel.P[t], tel.K[t], tel.N[t]
            on = P > 0
            if y > 0 and np.any(on):
                u_max = np.maximum(u_max, np.where(on, y / np.where(on, P, 1.0), 0.0))
                capped += (on & (K >= P)).astype(int)
        super()._feedback(tel, v)
        self._last = (u_max, capped)

    def decide(self, k, tel):
        self._last = (np.zeros(self.cfg.n_stages), np.zeros(self.cfg.n_stages, int))
        P, m = super().decide(k, tel)
        self.trace.append(dict(k=k, w=self.w.tolist(), P=P.tolist(), u_max=self._last[0].tolist(),
                               capped=self._last[1].tolist()))
        return P, m


def main(out, seed, c):
    b = TraceBundle(seed, PipelineConfig())
    pol = Traced(c)
    s = simulate(b.context("stationary", "val"), pol)["summary"]
    thr = float(np.sqrt(2.0 / pol.eta)) if pol.eta > 0 else float("inf")
    S = pol.cfg.n_stages
    res = dict(seed=seed, c_star=c, eta=pol.eta, w0=pol.w0.tolist(), sigma=pol.sig.tolist(), u_unstable=thr,
               cost=s["cost"], violating_window_rate=s["violating_window_rate"], stages=[])
    for st in range(S):
        w = np.array([r["w"][st] for r in pol.trace])
        u = np.array([r["u_max"][st] for r in pol.trace])
        cap = np.array([r["capped"][st] for r in pol.trace])
        P = np.array([r["P"][st] for r in pol.trace])
        bad = np.flatnonzero((w < 0.5 * pol.w0[st]) | (w > 2 * pol.w0[st]))
        first_bad = int(bad[0]) if len(bad) else None
        first_unstable = int(np.flatnonzero(u > thr)[0]) if np.any(u > thr) else None
        pre = slice(max(0, (first_bad or 0) - 288), first_bad) if first_bad else slice(0, 0)
        res["stages"].append(dict(
            stage=st, w_final=float(w[-1]), first_epoch_w_outside_half_to_double_w0=first_bad,
            first_epoch_eta_u2_gt_2=first_unstable,
            share_capped_feedback_minutes_overall=float(cap.sum() / max(1, 5 * len(cap))),
            share_capped_in_day_before_first_bad=float(cap[pre].sum() / max(1, 5 * (pre.stop - pre.start))) if first_bad else None,
            w_trend_day_before_first_bad=(float(w[pre][0]), float(w[pre][-1])) if first_bad and pre.stop - pre.start > 1 else None,
            P_at_first_bad=float(P[first_bad]) if first_bad is not None else None,
            epochs_P_zero=int(np.sum(P == 0))))
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]))
