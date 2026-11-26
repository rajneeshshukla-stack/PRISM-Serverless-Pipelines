#!/usr/bin/env python3
"""R3.6, E11 on the current code: restore the Eq. (5) against Erlang-B contrast. PRE-CALIBRATION, fast simulator, traces
101-105, the E11 design.

On the submitted code, E11 ran PRISM with risk_model='erlangb' against the main configuration, which used Eq. (5)
('occupancy'). On the current code the main configuration itself uses Erlang-B (f119bee), so E11 as written compares
Erlang-B with itself. This script:
  run    runs PRISM with risk_model='occupancy' on exactly E11's grid, weeks, scenarios and traces, stored as experiment
         'E11occ' (results/raw/E11occ, the E11 Store format);
  table  writes the regenerated E11 table with scripts/analyze.py's own method (validation-rule selection, test-week
         means, max |cost diff|, violating-window diff range): Eq. (5) (E11occ) against Erlang-B (E1, the main
         configuration). It also checks that E11's explicit-Erlang-B rows equal E1's default rows run for run.

usage: python e11_occupancy.py <tree prism-repro> run|table [raw dir]

Release copy (label_fix_20261123/tools/), changed from ../../regeneration_20261122/e11_occupancy.py in two ways only:
the optional [raw dir] (default: <tree>/results/raw_regenerated if it exists, else <tree>/results/raw), so the table
can be built from any directory of stored rows; and assertions that the arms are the intended risk models (E11occ rows
'occupancy', i.e. Eq. (5); E11 rows 'erlangb'; E1's main-configuration rows, labelled 'PRISM_EB', with no risk-model
override, i.e. the PrismConfig default 'erlangb'). The table and its method are unchanged.
"""
import json
import os
import sys

TREE, CMD = sys.argv[1], sys.argv[2]
RAW_ARG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, os.path.join(TREE, "src"))
sys.path.insert(0, os.path.join(TREE, "experiments"))
if CMD == "run":
    import run_experiments as RX                          # noqa: E402
    from prism_repro.config import PipelineConfig          # noqa: E402
    from prism_repro.experiment import GRIDS, TraceBundle  # noqa: E402
    from prism_repro.workload import MAIN_SCENARIOS        # noqa: E402
    st = RX.Store("E11occ")
    for seed in (101, 102, 103, 104, 105):
        if st.done(seed):
            continue
        b = TraceBundle(seed, PipelineConfig())
        rows, arrays = [], {}
        for wk, sc in [("val", "stationary")] + [("test", s) for s in MAIN_SCENARIOS]:
            for e in GRIDS["PRISM"]:
                RX.run_one(st, b, sc, wk, dict(family="PRISM", param=e, prism=dict(risk_model="occupancy")),
                           rows, arrays, tag="OCC")
        st.save(seed, rows, arrays)
        print(f"[E11occ] seed {seed} done", flush=True)
    sys.exit(0)

import numpy as np                                         # noqa: E402
import pandas as pd                                        # noqa: E402
from prism_repro.experiment import select_by_rule          # noqa: E402

RAW = RAW_ARG or (os.path.join(TREE, "results", "raw_regenerated")             # labels as the current code wrote them
                  if os.path.isdir(os.path.join(TREE, "results", "raw_regenerated")) else os.path.join(TREE, "results", "raw"))
L = lambda e: pd.DataFrame([json.loads(l) for l in open(os.path.join(RAW, e, "rows.jsonl"), encoding="utf-8")])  # noqa: E731
e1, e11, occ = L("E1"), L("E11"), L("E11occ")
from prism_repro.config import PrismConfig                 # noqa: E402
_risk = lambda df: {(s.get("prism") or {}).get("risk_model", "default") for s in df["spec"]}  # noqa: E731
assert PrismConfig().risk_model == "erlangb", "the main configuration is expected to use Erlang-B"
assert _risk(occ) == {"occupancy"}, f"E11occ rows must be Eq. (5) (occupancy): {_risk(occ)}"
assert _risk(e11) == {"erlangb"}, f"E11 rows must be Erlang-B: {_risk(e11)}"
assert len(e1[e1.policy == "PRISM_EB"]) and _risk(e1[e1.policy == "PRISM_EB"]) == {"default"}, \
    "E1 must hold the main configuration's rows as 'PRISM_EB' with no risk-model override (unnormalised labels)"
SCEN = ("stationary", "growth", "bursty", "new_spike")
lines = ["# E11 regenerated: PRISM with Eq. (5) (occupancy) against PRISM with Erlang-B (the current main configuration)",
         "", "PRE-CALIBRATION, fast simulator, traces 101-105, both validation-tuned by the common rule; test weeks.", ""]
# check: E11's explicit Erlang-B rows equal E1's default PRISM rows
cols = ["cost", "violating_window_rate", "record_attainment"]
a = e11[e11.status == "ok"].set_index(["seed", "scenario", "week", "param"])[cols].sort_index()
b = e1[(e1.policy == "PRISM_EB") & (e1.status == "ok")].set_index(["seed", "scenario", "week", "param"])[cols].sort_index()
same = a.index.equals(b.index) and np.array_equal(a.values, b.values)
lines.append(f"Check: E11's explicit-Erlang-B rows equal E1's default PRISM rows run for run: {same} ({len(a)} rows)")
lines.append("")


def sel(df):
    out = {}
    for s, g in df[df.week == "val"].groupby("seed"):
        out[s] = select_by_rule(g.to_dict("records"))
    return out


s_occ, s_eb = sel(occ[occ.status == "ok"]), sel(e1[(e1.policy == "PRISM_EB") & (e1.status == "ok")])
rows = []
for sc in SCEN:
    x, y = [], []
    for s in sorted(s_eb):
        x.append(occ[(occ.seed == s) & (occ.week == "test") & (occ.scenario == sc) & (occ.param == s_occ[s]["param"])].iloc[0])
        y.append(e1[(e1.seed == s) & (e1.week == "test") & (e1.scenario == sc) & (e1.policy == "PRISM_EB")
                    & (e1.param == s_eb[s]["param"])].iloc[0])
    x, y = pd.DataFrame(x), pd.DataFrame(y)
    rows.append({"Scenario": sc, "PRISM, Eq. (5)": f"{x.cost.mean():,.0f} / {x.violating_window_rate.mean() * 100:.2f}%",
                 "PRISM, Erlang-B": f"{y.cost.mean():,.0f} / {y.violating_window_rate.mean() * 100:.2f}%",
                 "max |cost diff| (USD)": f"{np.max(np.abs(y.cost.values - x.cost.values)):,.0f}",
                 "viol diff range (pp)": f"{np.min(y.violating_window_rate.values - x.violating_window_rate.values) * 100:+.2f} … "
                                         f"{np.max(y.violating_window_rate.values - x.violating_window_rate.values) * 100:+.2f}"})
lines.append(pd.DataFrame(rows).to_markdown(index=False))
lines.append("")
lines.append("Selected eps per trace: Eq. (5) " + str({int(s): v["param"] for s, v in s_occ.items()}) + "; Erlang-B "
             + str({int(s): v["param"] for s, v in s_eb.items()}))
out = os.path.join(TREE, "results", "tables", "revision", "E11_erlangb_regenerated.md")
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("\n".join(lines))
