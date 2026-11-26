# R2.7 and R4.4: why a within-run change experiment is not yet a fair test, and the narrowed RQ4 (23 Nov 2026)

## Reviewer requests

- **R2.7:** "Please investigate scenarios where the application workload changes during execution, including shifts in
  CPU intensity, memory demand, function execution time, or initialization latency. Such experiments would directly test
  whether dynamic memory optimization provides benefits that cannot be achieved through a one-time configuration
  decision."
- **R4.4:** "Please narrow RQ4 or test it ... Per stage memory and a change within a run would test the claim. The
  graphical abstract caption's 'memory adaptation helping satisfy tighter latency targets' goes beyond this evidence."

## Finding: neither controller can see a change in execution characteristics (verified in the code at fd8b01a)

- **PRISM's optimiser** takes the latency model from the static configuration once: `self.mt = miss_table(cfg)` and
  `self.d = {m: stage_means(cfg, m) ...}` (`src/prism_repro/optimizer.py`, lines 35 and 37).
- **The MemAdapt baseline** does the same: `self._vw = {m: miss_table(self.cfg)[m][0] ...}` and
  `self._dm = {m: stage_means(...) ...}` (`src/prism_repro/policies.py`, lines 200-201).
- **The simulators** draw execution and initialisation times from fixed configuration fields (`experiments/run_experiments.py`
  `DRAW_FIELDS`: `warm_mean_1024`, `exec_shape`, `init_shape`, ...), built once per trace bundle.

So if execution time, CPU intensity, memory demand or initialisation latency changed within a run, PRISM's memory choice
would not react through its latency model. Neither would MemAdapt's. Only the conformal offset reacts, and only on
concurrency, through the realised violations. The experiment would measure how a static-model controller degrades, not
"whether dynamic memory optimization provides benefits that cannot be achieved through a one-time configuration
decision". It was therefore not run.

**Prerequisites for a fair test (not implemented):**
1. Time-varying execution parameters in both simulators. This is a change to `src/`, so it needs a new tagged version
   and a guard that the default is byte-identical.
2. Online estimation of execution and initialisation time from telemetry in PRISM and in MemAdapt, by the same
   estimator for both. This is a change to the method.
3. A prespecified design:
   - development traces;
   - one change point per week;
   - arms: PRISM, MemAdapt and a one-time configuration chosen on the validation week;
   - the common tuning rule;
   - outcome: violating windows and cost after the change.

## What the existing evidence supports: the narrowed RQ4 (decision D4, 22 Nov 2026)

"When default memory is insufficient in the fixed workload regimes studied, can increasing memory restore deadline
compliance, and at what cost?" The answer is yes, in the fixed regimes studied, with one memory size shared by all
stages.

- **Fast simulator, development traces** (`../memadapt/summary.txt`, 7980b69; exploratory, pre-calibration):
  - At 12-13 s, 1024 MB violates 100% of windows. Moving to 2048 MB restores compliance for PRISM and MemAdapt alike
    (5 of 5 weeks).
  - PRISM costs 8-28% more than MemAdapt at matched compliance. Equivalently, MemAdapt costs 8-22% less.
  - At 11 s, PRISM meets the target in more weeks (5 of 5 against 3 of 5) at 4.7% higher cost.
- **Confirmatory C3** (closed-loop event level, 12 s, 25 traces, pre-calibration, Windows; `../confirmatory_20261122/RESULTS.md`):
  - PRISM costs 13.06% more [+8.50, +17.63] and violates fewer windows (-0.655 points).
  - Weeks meeting 2%: 24 against 17 of 25.
  - The cost comparison is confounded by compliance.

**What MemAdapt shows.** The memory benefit comes from moving to a size whose warm service meets the deadline, which a
simple warm-feasibility rule does. PRISM's joint optimisation adds no cost benefit in these fixed regimes. What changes
for each reviewer:
- **R4.4:** RQ4 is narrowed rather than tested. Per-stage memory and within-run change are stated as untested.
- **R2.7:** the experiment it asks for is not run, for the reasons above. The reply states the limitation and the
  prerequisites, and does not claim a dynamic benefit.
