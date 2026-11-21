"""Guard for stage-specific demand (R2.5, R4.1, R7.1): at unit demand the whole pipeline is byte-identical.

Written BEFORE the per-stage demand multiplier phi was added. tests/data/unit_phi_golden.json holds SHA-256 digests
of the outputs of the code as it stood before the feature (commit f77c00c plus a default-off calibration option):
the optimiser's candidate evaluation and decisions, the fast simulator for several policies (summary and every raw
array), a memory-switching regime and an event-level replay with telemetry. Each digest is recomputed now with
the default configuration and, once the feature exists, with phi = (1, 1, 1, 1) given explicitly; any difference
in any byte fails the test. A change that moves a number at unit phi is wrong and must be reverted.

The forecaster is the deterministic seasonal-naive reference (no GBM), so the digests do not depend on the
platform-sensitive gradient-boosting path; that path was checked against the pre-feature commit separately (see
notes/number_audit.md). The digests depend on numpy/scipy arithmetic, so the test skips, with a message, when those
versions differ from the ones that produced the golden file.

Regenerate the golden file ONLY on the pre-feature code: python tests/test_stage_demand_guard.py --write-golden
"""
import dataclasses
import hashlib
import json
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

GOLDEN = os.path.join(HERE, "data", "unit_phi_golden.json")


def _canon(x):
    """Deterministic, exact serialisation: floats by their hex form, arrays by dtype, shape and bytes."""
    if isinstance(x, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}:{_canon(x[k])}" for k in sorted(x, key=str)) + "}"
    if isinstance(x, (list, tuple)):
        return "[" + ",".join(_canon(v) for v in x) + "]"
    if isinstance(x, np.ndarray):
        a = np.ascontiguousarray(x)
        return f"nd({a.dtype.str},{a.shape},{hashlib.sha256(a.tobytes()).hexdigest()})"
    if isinstance(x, (bool, np.bool_)):
        return "T" if x else "F"
    if isinstance(x, (int, np.integer)):
        return f"i{int(x)}"
    if isinstance(x, (float, np.floating)):
        return f"f{float(x).hex()}"
    if x is None:
        return "N"
    return json.dumps(str(x))


def _digest(obj):
    return hashlib.sha256(_canon(obj).encode()).hexdigest()


TIMING = ("sim_seconds", "decision_ms_median", "decision_ms_p99")


def _sim_digest(res):
    s = {k: v for k, v in res["summary"].items() if k not in TIMING}
    return _digest(dict(summary=s, raw=res.get("raw")))


def pipeline_digests(cfg_kw=None):
    """Digests of every stage of the pipeline for one configuration (cfg_kw added to the defaults)."""
    from prism_repro.config import PipelineConfig, PrismConfig
    from prism_repro.des import EventDraws, simulate_events
    from prism_repro.experiment import TraceBundle, make_policy
    from prism_repro.forecast import scenarios
    from prism_repro.optimizer import ChanceConstrainedOptimizer
    from prism_repro.simulator import simulate
    cfg = PipelineConfig().with_(**(cfg_kw or {}))
    out = {}
    # optimiser: every candidate's feasibility and cost, and the decision, for every memory size
    opt = ChanceConstrainedOptimizer(cfg, PrismConfig(eps=0.02), 0.8)
    sc = scenarios(np.array([400.0, 600.0, 900.0, 1200.0]), 100)
    ev = opt.evaluate(sc, cfg.mem_options, 0.35)
    d = opt.decide(sc, cfg.mem_options, 0.35)
    out["optimizer"] = _digest(dict(ev={k: ev[k] for k in ("ys", "P", "feas", "cost", "v_q")}, mems=list(ev["mems"]),
                                    decision=dataclasses.asdict(d)))
    # fast simulator, deterministic forecaster, held-out new-spike week
    b = TraceBundle(101, cfg, scenarios=("stationary", "new_spike"), forecasters=("seasonal_naive",))
    specs = {"Static-95": dict(family="Static", param=95), "Reactive-0.6": dict(family="Reactive", param=0.6),
             "QuantProv_q90-1.0": dict(family="QuantProv", tau_idx=2, param=1.0, fc="seasonal_naive"),
             "PredHead+hyst-1.3": dict(family="PredHead", param=1.3, hyst=True, fc="seasonal_naive"),
             "PRISM-0.02": dict(family="PRISM", param=0.02, fc="seasonal_naive"),
             "Oracle-0.02": dict(family="Oracle", param=0.02, fc="seasonal_naive")}
    prism_raw = None
    for name, spec in specs.items():
        res = simulate(b.context("new_spike", "test"), make_policy(spec))
        out["fast:" + name] = _sim_digest(res)
        if name == "PRISM-0.02":
            prism_raw = res["raw"]
    # memory-switching regime (12 s deadline): PRISM must move to larger memory
    ctx = dataclasses.replace(b.context("stationary", "test"), cfg=cfg.with_(deadline=12.0), _Kweek={})
    out["fast:PRISM-0.02@D12"] = _sim_digest(simulate(ctx, make_policy(dict(family="PRISM", param=0.02, fc="seasonal_naive"))))
    # event-level replay of PRISM's schedule on the first 300 minutes of the week, with telemetry
    counts = b.traces["new_spike"]["counts"][21 * 1440:21 * 1440 + 300]
    dr = EventDraws(cfg, counts, 101, 0)
    n_ep = 300 // cfg.epoch_min
    ev_res = simulate_events(cfg, dr, prism_raw["P_epoch"][:n_ep], prism_raw["mem_epoch"][:n_ep], want_telemetry=True)
    tel = ev_res["raw"].pop("telemetry")
    out["event"] = _digest(dict(summary=ev_res["summary"], raw=ev_res["raw"],
                                tel={k: getattr(tel, k) for k in ("N", "K", "P", "n_od", "cold", "arrivals",
                                                                  "completed", "inflight_end", "mem", "filled")}))
    return out


def _env():
    import scipy
    return dict(numpy=np.__version__, scipy=scipy.__version__)


class TestUnitStageDemandIsByteIdentical(unittest.TestCase):
    def setUp(self):
        with open(GOLDEN, encoding="utf-8") as fh:
            self.golden = json.load(fh)
        if self.golden["environment"] != _env():
            self.skipTest(f"golden digests made with {self.golden['environment']}, running {_env()}")

    def test_default_configuration_matches_pre_feature_code(self):
        got = pipeline_digests()
        for k, v in self.golden["digests"].items():
            self.assertEqual(got[k], v, f"{k} moved at unit demand")

    def test_explicit_unit_phi_matches_pre_feature_code(self):
        from prism_repro.config import PipelineConfig
        if not hasattr(PipelineConfig(), "stage_demand"):
            self.skipTest("stage_demand not implemented yet")
        got = pipeline_digests(dict(stage_demand=(1.0,) * PipelineConfig().n_stages))
        for k, v in self.golden["digests"].items():
            self.assertEqual(got[k], v, f"{k} moved at explicit phi = 1")


if __name__ == "__main__":
    if "--write-golden" in sys.argv:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        dg = pipeline_digests()
        with open(GOLDEN, "w", encoding="utf-8") as fh:
            json.dump(dict(environment=_env(), note="digests of the pre-feature code; regenerate only on it",
                           digests=dg), fh, indent=1)
        print(json.dumps(dg, indent=1))
    else:
        unittest.main()
