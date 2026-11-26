# Memory-adaptive calibrated-quantile baseline against PRISM (R2.6, R7.4, R3.7)

PRE-CALIBRATION, EXPLORATORY: fast simulator, assumed constants (Eq. (3) init scaling), current code. Forecast-driven
results depend on the platform (NA-1); these come from one Windows machine (`environment.json`: Windows 11, Python
3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0).

**Provenance.** `scripts/revision/memadapt_compare.py . <out> --workers=3`, run 21 Nov 2026 09:36:54Z to 14:09:16Z
(`run.log`; the machine was suspended for about three hours inside that interval) in a separate worktree at commit
a396f40. `summary.txt` is `python scripts/revision/memadapt_compare.py . docs/revision/memadapt --analyse` on the
committed rows. One row per simulated week in `rows_<seed>_ns<non-scaling>.jsonl`, with the memory used, memory
changes per week and, for MemAdapt, its memory log.

**Design.** The six regimes of E4 / Table IX; seeds 101-105 (E4 used two); stationary validation week for tuning
by the common rule, stationary test week for evaluation, as E4. Families: PRISM (joint capacity and memory);
MemAdapt_q90 (`policies.MemAdapt`: smallest size with warm miss probability v_w(m) at most 0.005, a tolerance fixed
in advance; QuantProv-q90 capacity at that size); QuantProv-q90 at 1024 and at 2048 MB; fixed-2048 MB headroom
(PredHead, no scale-in rule, as Table S14). Paper's grids for every family.

## Findings

**The unfavourable result for RQ4 comes first.** In every short-slack regime the memory-adaptive rule meets the
target as PRISM does and costs less; PRISM's joint online memory sizing adds no benefit over automatic memory
selection in these fixed regimes.

| Regime (non-scaling, deadline) | MemAdapt size | PRISM vs MemAdapt, validation-selected (cost; violating windows) | PRISM vs MemAdapt, matched compliance (post hoc, 1.0 / 1.5 / 2.0%) | Weeks within 2%: PRISM, MemAdapt |
|---|---|---|---|---|
| 0.5, 14.5 s (default) | 1024 MB | +1.6%; -0.18 points | -0.9 / -0.3 / +1.7% | 3/5, 3/5 |
| 0.5, 13 s | 2048 MB | +27.9%; 0.00 | +27.6 / +27.4 / +27.2% | 5/5, 5/5 |
| 0.5, 12 s | 2048 MB | +19.8%; 0.00 | +19.5 / +19.3 / +19.1% | 5/5, 5/5 |
| 0.5, 11 s | 2048 MB | +4.7%; -0.39 points | -0.6 / +4.0 / +6.8% | 5/5, 3/5 |
| 0.15, 14.5 s (default) | 1024 MB | +1.6%; -0.18 points | -1.0 / -0.3 / +1.7% | 3/5, 3/5 |
| 0.15, 12 s | 2048 MB | +8.3%; 0.00 | +8.3 / +8.3 / +8.3% | 5/5, 5/5 |

1. **MemAdapt adapts and is QuantProv elsewhere.** It picks 1024 MB at the default deadline (where it is
   QuantProv-q90 exactly, every trace) and 2048 MB in every short-slack regime, once per replay: no memory change
   within a week (logged). PRISM changes memory 1.8 times per week at 13 s and 0.2 at 12 s (non-scaling 0.5).
2. **Fixed 2048 MB headroom is cheaper still**: 6.3-6.6% below MemAdapt at 12-13 s (both with no violating windows,
   both at the bottom edge of their grids, a = 0.6 and h = 1.0, so both could be cheaper with a wider grid), and
   3.0-5.9% below it at 11 s at matched compliance. At the default deadline, at the selected settings,
   QuantProv-q90 at a fixed 2048 MB costs 5.8% (non-scaling 0.15) and 37.6% (0.5) more than MemAdapt, and fixed-2048
   headroom 28.6% more at non-scaling 0.5 but 0.8% less at 0.15 (with no violating windows against 1.73%): where
   memory scales well, the larger size is competitive even without slack pressure.
3. **The stored E4b comparison reproduces in direction with five traces.** With test-week knowledge (cheapest
   setting within 2% on the test week, as E4b), fixed-2048 headroom is cheaper than PRISM's best by 27.0% (13 s),
   22.0% (12 s), 9.8% (11 s) and 13.4% (non-scaling 0.15, 12 s); E4b reported 14-29% on two traces.
4. **Tolerance.** tau_w = 0.01 selects the same sizes as 0.005 in all six regimes. tau_w = 0.002 moves the default
   deadline to 2048 MB (+5.8% / +37.6% cost) and 11 s to 3008 MB (+25.9%): the tolerance matters only where v_w
   sits near it (v_w(1024) = 0.0022 at 14.5 s; v_w(2048) = 0.0021 at 11 s).

**Caveats.** Stationary weeks only, five traces. The memory choice uses the warm miss probability alone, so it does
not depend on the init-versus-memory direction, but costs and compliance do (KNOWN_ISSUES: init direction; RQ4's
2048 MB advantage shrinks if init does not shorten with memory). Within-run changes of execution characteristics,
where an online memory decision could beat a once-per-regime choice, are not tested (R2.7, notes/decisions_pending.md
D4). The latency model is the pre-calibration one; the AWS campaign replaces it.
