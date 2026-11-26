#!/usr/bin/env python3
"""Minimal matched replay for the PRISM vs QuantProv-q90 1.0% matched-compliance discrepancy (R7.6, R5.M7(d)).

PRE-CALIBRATION, POST HOC, fast simulator, development traces 101-105 only (confirmatory seeds 106-130 unused).
Runs exactly the stored E1 test-week jobs of PRISM (paper-grid eps) and QuantProv-q90 (paper-grid a) for one seed in
the four test scenarios, with one code tree and one configuration variant, so that a single candidate cause can be
switched on or off while everything else is held fixed.

usage: python matched_replay.py <src_dir> <seed> <variant> <out.jsonl>
  src_dir  a prism-repro/src tree (the current tree, or one extracted with `git archive <rev> prism-repro/src`)
  variant  head               the tree's defaults
           occupancy          PrismConfig.risk_model = "occupancy" (the submitted default; f119bee switched it)
           sampled            PipelineConfig.exact_attainment = False (the submitted 100-draw sample; 1ab053c)
           occupancy+sampled  both
           tag                the tree's defaults (used with the v1-submitted tree)
Rows are appended and flushed one at a time; an existing (scenario, family, param) is skipped."""
import json, os, sys, time

src, seed, variant, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, os.path.abspath(src))
from prism_repro.config import PipelineConfig, PrismConfig      # noqa: E402
from prism_repro.experiment import GRIDS, TraceBundle, run_policy  # noqa: E402

SCEN = ("stationary", "growth", "bursty", "new_spike")
pkw, ckw = {}, {}
if "occupancy" in variant:
    pkw["risk_model"] = "occupancy"
if "sampled" in variant:
    ckw["exact_attainment"] = False
cfg = PipelineConfig().with_(**ckw) if ckw else PipelineConfig()
pcfg = PrismConfig().with_(**pkw) if pkw else None
jobs = [(sc, {"family": "PRISM", "param": float(e)}) for sc in SCEN for e in GRIDS["PRISM"]]
jobs += [(sc, {"family": "QuantProv", "tau_idx": 2, "param": float(a)}) for sc in SCEN for a in GRIDS["QuantProv"]]
done = set()
if os.path.exists(out):
    for l in open(out, encoding="utf-8"):
        if l.strip():
            r = json.loads(l); done.add((r["scenario"], r["family"], r["param"]))
b = TraceBundle(seed, cfg)
eff = dict(risk_model=(pcfg or PrismConfig()).risk_model,
           exact_attainment=getattr(cfg, "exact_attainment", "absent (sampled)"), latency_samples=cfg.latency_samples)
with open(out, "a", encoding="utf-8") as f:
    for sc, spec in jobs:
        fam = "PRISM" if spec["family"] == "PRISM" else "QuantProv_q90"
        if (sc, fam, spec["param"]) in done:
            continue
        t0 = time.perf_counter()
        s = run_policy(b, sc, "test", spec, pcfg_base=pcfg)["summary"]
        f.write(json.dumps(dict(seed=seed, scenario=sc, family=fam, param=spec["param"], variant=variant, src=src,
                                effective=eff, cost=float(s["cost"]), violating_window_rate=float(s["violating_window_rate"]),
                                data_sha256=s.get("data_sha256"), runtime_s=time.perf_counter() - t0)) + "\n")
        f.flush()
print(f"done {seed} {variant}", flush=True)
