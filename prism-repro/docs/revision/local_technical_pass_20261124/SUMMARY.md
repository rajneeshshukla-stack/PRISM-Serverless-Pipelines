# Local technical pass across the 73 comments (24 Nov 2026)

**Deferred:**
- no AWS call;
- no manuscript, figure, supplement or response-letter edit;
- no commit or push.

**Not changed:** the frozen protocol, seeds 106-130, the submitted results and the root CHECKSUMS.sha256.

**Baseline.** `PRISM_Tracker_dispositions_replies4_verified_20261124-083745.xlsx`. Both copies have SHA-256 9e83c194...,
with totals 0 Fixed / 54 Partially fixed / 18 Not fixed / 1 No change warranted.

## 1. Triage of the Remaining-work fields (Partially fixed and Not fixed rows)

| Kind | IDs |
|---|---|
| **Manuscript, figure or letter only** (queued for the writing pass) | R1.4, R2.10, R2.21, R2.22, R3.8, R4.4, R4.5, R4.10, R4.11, R5.M7, R5.m1-R5.m5, R5.R, R6.6, plus the text parts of nearly every Partially fixed row |
| **AWS only** (queued for the final live pass) | R6.1; R1.1(a); R1.3(c), R3.1(b), R4.3(a), R6.2 (activation lag, overflow); R2.8(a3); R2.14(b) (final charges); R2.20 (live decision path) |
| **Author's outward action** | R3.6(b), R5.M6(a), R7.7(a) (release and reviewer access); R3.2 (whether to send the inquiry); R2.13 (the author's `integer_search_e2e.py`, not on this machine) |
| **Blocked on the calibrated constants** (decision P3 and the R6.1 measurements; see `../calibration_inputs_20261124/`) | The rerun on measured constants named in R2.1, R2.2, R2.3, R2.4, R2.9, R2.15, R2.19, R3.4, R3.5, R4.8, R4.9, R5.M1, R6.3, R7.2(b), R7.3 |
| **Local, done in this pass** | R3.6/R7.7 (clean-checkout reproduction), R5.M6(b) (Linux), R3.2 (Linux row), C1-C3 platform check (R2.1, R2.16, R2.18, R4.2, R6.4, R6.5), R2.14(a) (comparator bound), the calibration audit (R1.2, R2.8(b), R4.3, R4.8, R5.M2, R7.5), and the R1.1 margin decision |
| **Local, still open** (section 5) | R2.12(b) and R5.M5 (κ floor under closed loop); R5.M1(e) and R2.2(b) (PredHead+S and other families under closed loop); R7.5(c), (e) and (d) re-centred; R2.11 (a calibration choice to fix before the rerun) |

## 2. What ran and what passed

| ID(s) | What ran | Result |
|---|---|---|
| R3.6, R7.7 | Clean `git archive` of HEAD 3edc386, plus the 74-file input archive (52c1c701..., manifest 74/74), in fresh directories; the documented `reproduce_analysis.py` with the Windows and the Linux inputs | **Reproduced.** All checks passed. Windows: 37/39 tables byte-identical, and the 2 others differ only in a wall-clock column, as recorded. Linux: 37/37 equal apart from line endings. pc_billing, R7.6 1% and E11 outputs identical; all emitted R7.6 endpoints equal the full-precision references. **Defect fixed:** checksum manifests are CRLF in Windows checkouts, so `sha256sum -c` fails. `prism-repro/.gitattributes` (new, uncommitted) keeps them LF; tested on an archive, 74/74 verify (`../label_fix_20261123/README.md` section 8) |
| R5.M6(b) | Committed `table6_versions.py` on Linux x86-64, pinned environment and an isolated copy differing only in scikit-learn 1.9.1 (plus its dependency narwhals) | 2 of 20 selections change. Single runs move by up to 2.08 points and 9.59%. vs QuantProv-q90, every cost interval includes 0 under both versions; vs PredHead, every interval excludes 0 under both; vs PredHead+hyst, one stationary cost interval crosses 0. On Windows one also crosses (growth), so the earlier reply's "every conclusion holds" was inaccurate (`../table6_versions/linux_20261124/`) |
| R3.2 | Prespecified OptScaler commands on Linux, against the Linux E1 rows | D1 passes on Linux. The published-parameter row is stable and meets 2% on 20/20; PRISM costs 24-29% less than OptScaler, with 1.2-2.5 points more violating windows. The tuned variant diverges again and stays excluded. **Correction:** the earlier "OptScaler 23-28% more expensive than PRISM" inverted the base; it is 30-40% (Windows) or 33-42% (Linux) more (`../optscaler_r32_20261124/` section 8) |
| C1-C3 (R2.1, R2.16, R2.18, R4.2, R6.4, R6.5) | The C1-C3 driver's pilot101 set (development trace 101, four families, 41 closed-loop weeks) on Linux from a clean clone, against the Windows run | Selections identical. Reactive (no forecast) bit-identical; forecast-driven weeks differ by up to 1.4% cost and 0.6 points. The paired PRISM-QuantProv-q90 difference moves by 0.5 points. C1's tie verdict (+2.011% against +2%) is platform-fragile; its no-difference reading and C3 are not (`../confirmatory_20261122/pilot101_linux_20261124/`) |
| R2.14(a) | `comparator_lead_bound.py` on the saved E1 schedules of every provisioning family (Linux and Windows release inputs; no simulation) | The simulator's capacity charges equal AWS's rule in all 160 runs per platform. The lead bound is 5-7% of weekly cost for the forecast-driven rules, 3.5% for Reactive and about 0 for Static/Scheduled. vs QuantProv-q90 the change is 0.1-0.3 points. **Unfavourable:** PRISM's saving over Static/Scheduled shrinks by 4-5 points, and 3 of 8 Linux intervals stop excluding 0 (`../billing_r214_pc_20261124/` section 4) |
| Calibration, R1.1 | Audit of every `PipelineConfig()` constant against memcal-1 and the live integration run | `warm_mean_1024` matched by construction. Eq. (2) contradicted (the plateau at 2048 MB or more). `exec_shape` and application start-up untestable (one document, no start-up work). Lambda Init 0.115 s flat. Lag, keep-alive and overflow unmeasured. The 10% margin is kept in scope; the 50% branch is not pursued (`../calibration_inputs_20261124/`) |
| R7.6 | Reused (no rerun) | The R3.6 check reproduces every emitted endpoint exactly; the 1.0% matched-compliance analysis stays POST HOC and separate |

## 3. Reporting basis: what changes with platform, library or configuration

| Conclusion | Changes with platform? | With scikit-learn? | Evidence |
|---|---|---|---|
| PRISM vs QuantProv-q90: cost not distinguishable (fast simulator, 5 traces) | No (both include 0) | No | T6 on Linux and Windows; Table VI under both versions |
| PRISM costlier than PredHead | No | No | same |
| PRISM vs PredHead+hyst, stationary/growth cost | Interval-level only | **Yes:** one interval crosses 0 on each platform | same |
| OptScaler (published) vs PRISM: a trade-off, not a ranking | No (0.7-1.8 points) | not run | `optscaler_r32_20261124` |
| C1 "not a tie" | **Possibly** (margin 0.011 points; platform moves one trace's difference by 0.5 points) | not run | pilot101 platform check |
| C1 no difference; C2; C3 confounded | No evidence of change | not run | same |
| The submitted values (stored results) | Reproduce only on Linux | — | label_fix_20261123 |

**Linux x86-64 is the reference where verified:**
- E1/E3/E7/E9 tables;
- Table VI under both versions;
- the OptScaler row;
- the analysis package.

**Missing for an all-Linux report:**
- E2, E4-E6, E8, E10-E12, R1, R2, E4b and E11occ (the Linux E4/E4b exist for the caption range only);
- the revision analyses on Linux rows;
- C1-C3 on Linux.

Rows from different platforms are not mixed in any comparison here. C1-C3 stay "Windows, pre-calibration".

## 4. Changes to existing text

- `optscaler_r32_20261124/README.md`, `TABLE_V_ROW.md` and `REPLY_DRAFT.md`: the cost base is corrected, with dated
  notes. The tracker reply is corrected in this pass.
- `label_fix_20261123/README.md`: section 8 added.
- `billing_r214_pc_20261124/README.md`: section 4 added.
- **New folders:**
  - `table6_versions/linux_20261124/`;
  - `confirmatory_20261122/pilot101_linux_20261124/`;
  - `calibration_inputs_20261124/`;
  - this summary.
- **New file:** `prism-repro/.gitattributes`.

## 5. Local technical work still open after this pass, with the exact blocker

1. **R2.12(b), R5.M5:** κ floor 0.1 against 0.001, retuned under the closed loop (exploratory, development traces).
   *Blocker:* machine time only. About 20 closed-loop weeks per trace and floor, roughly 1-2 h on Linux. Not started,
   to keep this pass's runs within one session.
2. **R5.M1(e), R2.2(b):** PredHead+S, and the other families, under the closed loop in the new spike, matched with
   PRISM, QuantProv-q90 and Reactive on the same development traces. *Blocker:* machine time. Seeds 106-130 are
   reserved, so C1 cannot be reused as the comparator, and PRISM, QuantProv-q90 and Reactive would have to run again
   on 101-105.
3. **A per-size execution-time mode** (replacing Eq. (2), contradicted by memcal-1) and **R7.5(d)** re-centred.
   *Blocker:* `src/` is pinned at 3edc386 for the R6.1 run sheet; change it after the live run, or freeze a separate
   build.
4. **The calibrated rerun** (every "rerun on measured constants"). *Blocker:* decision P3 (application start-up), P4
   (input sizes), and the R6.1 activation-lag and overflow measurements.
5. **C1-C3 on Linux** (settles the platform-fragile tie verdict). *Blocker:* best done once, calibrated (item 4). About
   34 CPU-h.
6. **The remaining Linux regenerations** for an all-Linux report (section 3). *Blocker:* the author's reporting
   decision; then about 10-15 CPU-h.
7. **R2.11:** fix shared versus per-quantile calibration before the rerun. *Blocker:* author decision; no run needed.

*Correction, 24 Nov 2026 (calibration pass, `../calibration_20261124/DECISION_RECORD.md`): in `aws_pipeline/SPEC.md` the input-size distribution is decision **P2**, not P4; P4 is the data source and sink. Every "P4 (input sizes)" above means P2.*
