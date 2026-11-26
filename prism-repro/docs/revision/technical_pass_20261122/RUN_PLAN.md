# Remaining calibrated runs: the smallest set that covers R2.1, R2.18, R3.3, R4.2, R5.M4, R6.4, R6.5 and R7.6

Written 22 Nov 2026 at HEAD 0316789 on branch `closed-loop`. Nothing in this file has been run. Every run below waits
for measured constants (AWS campaigns; `notes/decisions_pending.md` D7 and the measurement plan). Until then any
result would be PRE-CALIBRATION. The frozen `../PRESPECIFICATION.md` (d16fbea, unchanged, with no addendum) governs
every confirmatory run, and the confirmatory seeds 106-130 have not been run.

## 1. What each comment asks, and what covers it

| ID | Reviewer wording (key clause) | Covered by |
|---|---|---|
| R2.1 | "make the event-level simulation the primary evaluation environment or provide a calibrated approximation" | C1-C3 (event-level, closed loop) as the primary table |
| R4.2 | "make a closed loop event level simulation, with exact attainment, the primary evaluation" | the same runs; event-level attainment is computed per request, so it is exact |
| R3.3 | "add a test without this match and move the event level Table X next to Table V" | the same runs (no match to Eq. (14)); moving the table is manuscript work |
| R6.4 | "Compare PRISM directly with a simple calibrated-q90 + smoothing controller as the primary baseline" | C1: QuantProv-q90 is the calibrated q0.9 rule with the scale-in rule |
| R6.5 | "Expand beyond five traces and report stronger statistical evidence" | 25 confirmatory traces, with paired 95% t intervals and direction counts (section 5 of the prespecification) |
| R2.18 | "additional independent workload realizations and repeated experiments using different simulation configurations ... distinguish exploratory post hoc comparisons from confirmatory findings" | 25 traces; the pre-calibration rerun and the calibrated rerun are two configurations; the labels are manuscript work |
| R5.M4 | "run more traces, evaluate all families in the shifted-trigger scenario and widen every grid whose edge is selected" | 25 traces; the prespecified edge expansion; shifted triggers is **not** in the prespecified scenarios (see section 4) |
| R7.6 | "clarify which differences are statistically meaningful" | the prespecified difference and tie criteria (section 5 of the prespecification); see section 3 |

## 2. The confirmatory run set (prespecified; after calibration)

- **C1 and C2.** PRISM, QuantProv-q90 and Reactive, default deadline 14.5 s.
  - Each is tuned on the closed-loop validation week (days 14-20, event draw key 2) over `experiment.GRIDS`, with the
    edge expansion of section 4 of the prespecification.
  - The selected setting runs on the four test weeks: stationary, growth, bursty, new_spike, key 3.
- **C3.** PRISM and MemAdapt-q90, deadline 12 s, non-scaling 0.5, stationary scenario. Tuning and testing are the
  same as for C1 and C2.
- **Traces:** seeds 106-130, from `data/trace_set_revision.json`. The 25 development counts were rechecked on 22 Nov:
  `trace_inventory.txt`.
- **Driver: not built.** `scripts/revision/closed_loop_pilot.py` implements the tuning rule and the edge expansion,
  but it is fixed to seeds 101-103, the stationary scenario and the default deadline. Smallest next step:
  1. add `--seeds`, `--scenarios`, `--families`, `--deadline` and `--nonscaling` options, without touching its
     selection or expansion code;
  2. check that the extended driver reproduces the saved pilot group files for trace 101 byte for byte;
  3. run.

  Proposed commands for the extended driver (from `prism-repro/`):

  ```
  python scripts/revision/closed_loop_pilot.py . docs/revision/confirmatory_<date>/C1C2 --seeds=106-130 --scenarios=stationary,growth,bursty,new_spike --families=PRISM,QuantProv_q90,Reactive --workers=4
  python scripts/revision/closed_loop_pilot.py . docs/revision/confirmatory_<date>/C3 --seeds=106-130 --scenarios=stationary --families=PRISM,MemAdapt_q90 --deadline=12 --nonscaling=0.5 --workers=4
  python scripts/revision/closed_loop_pilot.py . docs/revision/confirmatory_<date>/C1C2 --analyse
  ```

- **Inputs:**
  - measured constants in `PipelineConfig` and `PrismConfig`, applied as the prespecification requires;
  - `data/trace_set_revision.json`;
  - an environment and platform pinned and recorded in each run folder.
- **Outputs:** `docs/revision/confirmatory_<date>/`, holding the group files, `environment.json`, `run.log` and
  `summary.txt`, with SHA-256 lists for both CRLF and LF.
- **Runtime estimates** (not measured for this design):
  - **From per-week timings** in `../closed_loop/README.md` (PRISM 170 s, forecast-driven rules 110 s, Reactive 35 s
    per closed-loop week), about 1.05 CPU-h per trace for C1 and C2 and 0.67 for C3, before edge expansions. For 25
    traces that is about 43 CPU-h, or 9-11 h wall at 4-5 workers.
  - **From the pilot's throughput**: 125 closed-loop weeks in 2 h 58 min, worker count not recorded. The design has
    about 57 closed-loop weeks per trace, or 1,425 weeks, which extrapolates to about 34 h wall.
  - Plan for 1-1.5 days. Write output per job, as the pilot does, and record any suspension: the machine suspended
    for about 3 h on 21 Nov and a Windows Update restart ended a run on 22 Nov.

## 3. R7.6: comparisons and uncertainty checks on one pinned, calibrated implementation

- **Primary (prespecified).**
  - Per trace (25), PRISM minus comparator, for cost (%) and violating windows (points). Report the mean with a 95% t
    interval (df 24), plus counts of traces in each direction.
  - Call a cost difference a difference only if its interval excludes zero. Call a tie only if the whole interval
    lies within +/- 2%. An interval that includes zero but extends beyond +/- 2% is reported as "not distinguishable",
    never as equivalence.
  - Call compliance similar only if the violating-window interval lies within +/- 0.5 points; otherwise report the
    cost comparison as confounded by compliance.
- **Tables VI and XII, as R5.M7(d) words them.**
  - The selected-configuration comparison against QuantProv-q90 comes from C1.
  - The real-trace analogue (Table XII) is **not** in the prespecified set: it needs an exploratory closed-loop R1
    replay (section 4).
  - Revised-code checks so far, both including zero: Table VI analogue at f77c00c, and Table XII analogue at HEAD at
    +1.6 +/- 4.0% (`../matched_compliance_discrepancy/FINDINGS_20261122.md`).
- **Table VII, the matched-compliance comparison (POST HOC, exploratory).**
  - It needs every grid point on the test weeks, about 10.7 CPU-h per trace (`../closed_loop/README.md`).
  - Report it with the frontier-bracketing check and the R2.19 refined and evaluated columns.
  - At the 1.0% target, keep both earlier figures with their provenance until the regenerated one replaces them:
    stored -0.4 +/- 3.3% and current code -2.3 +/- 2.0%. Their paired change, -1.91 +/- 2.42 points, includes zero.
    The code part of the change is exact attainment plus Erlang-B. The -0.32-point platform part is unattributed.
- **Pinning.**
  - Exact attainment and the Erlang-B risk model stay on, as the current defaults; they are the two switches that
    moved Table VII.
  - Use one commit and one platform, and record the environment.
  - If cross-platform agreement is claimed (R3.6, R2.16), rerun one development trace on a second platform first.
    No stored Linux row reproduces on this laptop.

## 4. Requests outside the prespecified set (author decision before the confirmatory runs)

Each of these needs an exploratory run, or a dated addendum before the first run on seeds 106-130, or a scoped
statement in the manuscript instead:

- **Shifted-trigger scenario for all families (R5.M4(b)).** Fast-simulator check done 22 Nov (`shifted_triggers/`).
  A closed-loop version would add about 0.1-0.2 CPU-h per trace for the test weeks of the selected settings.
- **PredHead and PredHead+S, the graphical-abstract comparators (R4.10, R5.m5; also R5.M1(e)).** The prespecification
  lists them as exploratory. The new-spike values for the abstract need them, which would add about 0.5 CPU-h per
  trace.
- **Static, the "13-29% saving" (R5.M7(a)).** Exploratory family.
- **Matched-compliance frontiers, "within 1.6%" (R5.M7(b), R7.6).** About 267 CPU-h for 25 traces.
- **Huawei real-trace replay (R5.M7(c), (d) Table XII).** Not prespecified.
- **Per-trace ablation and QuantProv memory tables (R5.m4).** Not prespecified. Regenerating them needs the ablation
  and memory experiments, or a statement that the supplement tables are pre-calibration fast-simulator values.
- **Event-level retuning on the widened grids (R5.M4(c)).** The prespecified edge expansion covers the confirmatory
  families. The paper's other families need the exploratory set.
