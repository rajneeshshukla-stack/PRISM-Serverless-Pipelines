# Final evidence and consistency audit: C1-C3 and the table regeneration against all 73 comments (23 Nov 2026)

Window audited: 20-23 Nov 2026, Central time (Git commits e28ab91 to fd8b01a, 20 Nov 19:06 CST to 22 Nov 15:17 CST;
uncommitted evidence of 22-23 Nov). No new run was made for this audit; every figure is from saved outputs. The manuscript is not
in the repository and was not edited. Results remain PRE-CALIBRATION (assumed constants).

## 1. Baseline

- Tracker: `PRISM_Tracker_dispositions_confirmatory_regeneration_verified_20261123-133300.xlsx`, the newest in both
  `review-inputs` and `PRISM_tracker_backups`, identical (SHA-256 `138cbb2c814e9d23de67fbec55b6c77f3e5a31887466babed75432bc968b2f9f`).
  No newer verified pair exists. Totals counted from column C: 0 Fixed, 49 Partially fixed, 23 Not fixed,
  1 No change warranted (as reported).
- Repository: branch `closed-loop`, HEAD fd8b01a; tracked changes in `notes/dispositions.md`,
  `notes/manuscript_proposals.md` and three `aws_memcal_20261122` files; the revision evidence folders and two
  scripts untracked. All preserved.
- Protected items unchanged: `results/` (no diff against `v1-submitted`), `CHECKSUMS.sha256`,
  `docs/revision/PRESPECIFICATION.md` (one commit d16fbea, no working-tree change, no addendum).
  `scripts/build_manifest.py --verify` lists 21 mismatches, every one a file changed by a commit since `v1-submitted`
  (none from the working tree).

## 2. Verification of the completed runs

**C1-C3 (`checks/verify_run_final.txt`, ok).** Reconciled from the group files:

| Set, family | Groups | Initial grid | Validation weeks (with expansions) | Test weeks |
|---|---|---|---|---|
| C1/C2 PRISM | 25 | 6 | 152 (2 expansions) | 100 |
| C1/C2 QuantProv-q90 | 25 | 10 | 252 (2) | 100 |
| C1/C2 Reactive | 25 | 11 | 275 (0) | 100 |
| C3 PRISM | 25 | 6 | 150 (0) | 25 |
| C3 MemAdapt-q90 | 25 | 10 | 253 (3) | 25 |

125 groups and 979 + 453 = 1,432 weeks, equal to the run log's end line (582 run plus 850 reused) and to the week files.
Every row carries its set's configuration hash and matches its manifest-verified trace hash, and the 10 weeks logged
FAILED at the first interruption were retried and saved (`failures.json` empty). There are no duplicate or orphan
files. All five segments ran commit fd8b01a with the same driver SHA-256 and clean `src/`, and two weeks recomputed
identically. **PRISM's risk model** is `erlangb` in all five segments (`run/environment.json`, `prism_config`).
**Exception noted, not a defect:** the costs are the simulator's modelled weekly cost at the assumed prices
(`pc`/`pcd` are among the open constants in `CONSTANTS.md`); they are not AWS charges or list-price estimates.

**Regeneration (`../regeneration_20261122/README.md`).**
- Raw row counts equal the submitted ones, experiment by experiment: E1 1,900; E2 20; E3 110; E4 172; E5 540; E6 40;
  E7 180; E8 1,280; E9 72; E10 1; E11 150; E12 395; E4b and R2 per seed; R1 765. The submitted folders also hold three
  files that the scripts do not write. Unit tests pass, 124 of 124.
- **PRISM_EB rows:** E1 holds 150 PRISM rows labelled `PRISM_EB` (the Erlang-B default). The analysis copy relabels
  them `PRISM` (111 files, 10,958 strings), so every table includes them.
- **E11:**
  - The stock E11 runs only the explicit Erlang-B arm (150 rows, `risk_model: erlangb`). It compares that arm with E1's
    default, which is also Erlang-B at fd8b01a, so the stock table is degenerate.
  - The intended comparison is Eq. (5) occupancy (E11occ, 150 rows, `risk_model: occupancy`) against Erlang-B, in
    `E11_erlangb_regenerated.md`. It checks that the explicit Erlang-B rows equal E1's PRISM rows run for run (150 of 150).
- **E3/E7/E9 defect.** Built from shimmed drivers:
  - Table VIII, `E3_quantile_vs_scenario_feasibility` and `T14_hysteresis` (from E3);
  - `T20_feature_ablation` (from E7);
  - Table X (`T10_fast_vs_event`, `T10b`, `T11`) and the `E9_*` in-flight and sampling tables (from E9);
  - the ablation half of the per-trace supplement and of the R5.m4 tables (from E3).

  These values are verified, since the shim changes only the lookup and its `--check` mode passed. They cannot be
  rebuilt by the released scripts until the lookup is fixed in the released code (R3.6(b)). All other tables are
  independent of the defect.
- **Platform exception.** The regeneration ran on Windows 11. `REPRODUCE.md` and `KNOWN_ISSUES.md` name Linux x86-64
  as the reference platform for forecast-driven results, which are not bit-reproducible across platforms. Where they
  overlap, the regenerated values equal the earlier current-code analyses on the same laptop: Table VI +1.6, +1.3,
  0.0 and −0.1%; Table XII +1.6 ± 4.0%; and 1.0% matched −2.27 ± 2.02% (`../matched_compliance_discrepancy/`).
- **Why the values differ from the submitted tables.** The shift is decomposed only for the 1.0% matched comparison.
  The controlled replay (`FINDINGS_20261122.md`) reproduces it from exact attainment (1ab053c) and the Erlang-B
  default (f119bee). It leaves a residual −0.32 points between the Linux stored rows and the same code on this laptop,
  which is not attributed. Every other shifted table is reported as changed, with the cause not isolated. Code changes
  since `v1-submitted` and the platform both differ, and neither was varied separately.
- **Material differences carried into replies:**

  | Table or value | Submitted | Regenerated |
  |---|---|---|
  | Table X, PRISM violating windows, fast / event level | 1.44% / 3.75% | 1.69% / 6.14% |
  | Table V, new spike, PRISM | 1.55% | 2.11% |
  | S4, PRISM cost and violating windows | 1,267 USD / 1.36% | 1,150 USD / 1.78%; now above QuantProv-q90 |
  | Table XII | PRISM lowest-violating | QuantProv-q90 lowest-violating (0.18% against 0.33%) |
  | E1 selections | | PRISM at eps 0.08, the top of the grid, on traces 103-105 |
  | Table XII selections | | PRISM at eps 0.08 on 4 of 5 traces |

**Cost and compliance together (prespecified rules, section 5 of the prespecification).**

| | Cost: PRISM minus comparator | Violating windows | Call |
|---|---|---|---|
| C1, vs QuantProv-q90 | +0.30% [−1.42, +2.01] | −0.106 points [−0.274, +0.062] | Not distinguishable, and not a tie. Similar compliance. |
| C2, vs Reactive | −26.49% [−28.76, −24.23] | +0.018 points | PRISM cheaper. Similar compliance. |
| C3, vs MemAdapt-q90 | +13.06% [+8.50, +17.63] | −0.655 points [−0.921, −0.389] | PRISM costlier, but compliance is outside ±0.5 points, so the cost comparison is confounded. |

No interval both excludes 0 and lies within ±2%, so no row carries a "difference and tie" double reading.

**R7.6, 1.0% matched compliance (POST HOC, separate from C1).**
- Scope: development traces 101-105 (n = 5), fast simulator, pre-calibration, test-week knowledge.
- Bracketing: both families bracket 1.0% on all 5 traces. The cheapest evaluated settings meeting 1.0% give
  −2.40 ± 1.01%, with achieved violating windows of 0.71-0.97% for PRISM and 0.74-0.97% for QuantProv-q90. Pairing is
  by trace.
- Regenerated estimate: −2.27 ± 2.02%. The interval excludes 0 narrowly, and since it extends below −2% it is not
  equivalence.
- Stored estimate: −0.36 ± 3.30%, which includes 0.
- The paired change between them is −1.91 ± 2.42 points and includes 0, so the two estimates are not shown to differ.
  They read differently because the corrected metric, together with Erlang-B, moves where each frontier crosses 1.0%.
- At 1.5% and 2.0% the regenerated intervals include 0, with 4 of 5 traces bracketed. The stored 2.0% "tie" is not
  reproduced as a tie.
- **R5.M7 consistency.** The "within 1.6%" basis is the pooled matched difference (pc_billing: −1.5% regenerated,
  −1.4% stored at 1.0%). It is a different statistic from R7.6's per-trace paired mean, and each is now cited with its
  own scope.

**R5.m4.**
- `r5m4_complete_tables.md` covers both comparisons the reviewer cites: the per-trace ablation (p. 12, ll. 40-43) for
  every trace and scenario, with the 20 missing cells run; and the per-trace QuantProv memory results (p. 16,
  ll. 33-48) on the paper and widened grids.
- Limitations: 20 of 48 QuantProv-2048 selections remain at the lower grid edge, and the ablation half depends on E3.

## 3. Cross-row audit: claims affected by the 20-23 Nov work

Columns: earlier wording (source: the 133300 tracker cell unless stated); new finding (source); comparable?;
correction applied. "Applied" means appended to Evidence or Remaining, or replaced in the Suggested reply or
Requests, in the new workbook.

| ID | Earlier wording | New finding (source) | Comparable? | Correction applied |
|---|---|---|---|---|
| R7.6 | Reply: 1.0% moved "-0.4 +/- 3.3% to -2.3 +/- 2.0% when window attainment was computed exactly"; "not distinguishable in cost at matched compliance" | Regenerated -2.27 +/- 2.02% excludes 0; shift = exact attainment + Erlang-B + unattributed platform residual (FINDINGS_20261122.md, r76) | same question and statistic, different code | Reply rewritten: C1 not distinguishable and not tied; post hoc 1.0% narrowly excludes 0; attribution corrected; 1.5/2.0% include 0 |
| R6.4 | Reply: "at matched compliance, with ... bootstrap intervals" | C1 is at validation-selected settings, similar compliance, 95% t intervals (RESULTS.md) | different question (prespecified vs post hoc) | Reply rewritten with C1's figures and rule |
| R6.5 | Reply: "Thirty traces ... bootstrap CIs" | 25 confirmatory traces, t intervals (RESULTS.md) | same question | Reply corrected |
| R2.18 | Reply: "increased to 30 independent traces" | 25 new traces in two configurations (RESULTS.md) | same | Reply corrected; scope of configurations stated |
| R2.1, R4.2, R3.3 | Replies "[pending]" without results; R2.1 evidence cites Table X 1.44% -> 3.75% | C1-C3 results; regenerated Table X 1.69% -> 6.14% (T10, via shim) | Table X: same table, different code and platform | Replies give the pre-calibration results with scope; Table X change and E9 fix recorded |
| R3.6 | Reply: "one pinned environment on one reference platform" | Regeneration on Windows; reference platform is Linux (REPRODUCE.md) | contradiction | Reply marks platform pending; decision recorded |
| R4.10, R5.m5 | Replies cite no values; reviewer cites 3.24% / 6.67% (submitted) | Regenerated 4.11% / 7.92%; caption 13-27% (graphical_abstract caption.md s.4) | same quantities, different code | Replies give both versions pending the version decision |
| R4.11 | Reply "[pending]" restructure | C1-C3 supply the primary evaluation | n/a | Reply names it |
| R5.M7 | Reply generic | Huawei lowest-violating now QuantProv-q90; S4 ordering changed; pooled vs per-trace 1.0% figures (README s.5) | stored vs regenerated: same tables | Reply names the orderings that did not hold; evidence separates the two 1.0% statistics |
| R5.m4 | Reply "Both tables are added" | Tables complete; QuantProv-2048 grid-edge limit; E3 dependence | n/a | Reply states the limit |
| R3.5 | Requests: "The 25 confirmatory traces (seeds 106-130) have not run"; reply "expanded evaluation remains pending" | C1-C3 ran; frozen file precedes first run (d16fbea 21 Nov 11:54:54 CST < 22 Nov 22:49:32 UTC) | same | Requests (a) and reply corrected; status unchanged (manuscript open) |
| R2.2 | Requests: "the confirmatory, calibrated evaluation has not run" | ran on assumed constants, three baselines only | same | Requests and reply corrected |
| R6.3 | Requests: "The calibrated confirmatory evaluation is open"; reply "full closed-loop comparison remains pending" | C1-C3 complete on assumed constants | same | Requests and reply corrected (calibrated rerun still open) |
| R5.M4 | Requests (a): "the 25 confirmatory traces have not run"; Remaining: addendum "before the first run"; reply "[pending] We ran 30 traces" | first run happened 22 Nov 22:49:32 UTC | same | Requests (a), reply and Remaining corrected; addendum option lapsed |
| R5.M1 | Remaining "Next: the confirmatory C1-C3" | done, pre-calibration | same | Remaining updated |
| R4.6 | Remaining "checked on unseen seeds 106-130" | seeds 106-130 now used by C1-C3 | n/a | Remaining corrected |
| R2.6, R3.7, R4.4, R7.4 | Replies: the memory-adaptive rule "meets the target as PRISM does" at lower cost (fast simulator, E4b/MemAdapt, development traces) | C3: MemAdapt 13% cheaper but 17 vs 24 of 25 weeks meeting 2%; confounded (RESULTS.md) | different evaluator, traces and question; both kept with scope | Replies scoped to the fast simulator and C3 added |
| R7.2 | Remaining: "about 0.23 s of platform start-up"; reply: Table X 1.44% / 3.75% | 0.23 s is client-visible cold-stage latency, not Init Duration (aws_live_followup/README.md); regenerated Table X 1.69% / 6.14% | 0.23 s: label only; Table X: different code | Remaining clarified; decomposition to redo after E9 fix |
| R4.7 | Reply: "every provisioned family except scheduled provisioning meets the target on all five traces" | widened-grid replay (22 Nov); on regenerated paper-grid Table XII Reactive also 4/5; PRISM not lowest-violating | different grids | Reply scoped to widened grids; paper-grid result recorded |
| R2.15 | Reply: regenerated "[pending], with a diff ... that classifies every value that moved" | line-by-line comparison exists; no classification by cause | n/a | Evidence and Remaining updated |
| R2.16, R2.17, R5.M6 | Replies: every figure from one reference platform | regeneration on Windows (README) | contradiction | Remaining records the decision needed; replies unchanged pending it |
| R3.4, R4.9 | E11 cited as the Eq. (5) / Erlang-B comparison | stock E11 degenerate; E11_erlangb_regenerated: Eq. (5) 2.5-3.0% cheaper, more violating in 3 of 4, selection at grid top | same question | Evidence added |
| R2.3, R7.3 | "Blocker: regeneration" | pre-calibration regeneration exists; mapping not rerun | n/a | Remaining clarified |

**Checked and unaffected:**
- The AWS rows (R1.2, R2.8, R2.14, R2.20, R3.1, R4.3, R5.M2, R6.1, R6.2). They already distinguish Lambda Init
  Duration (about 115 ms), client-observed first-call penalty (0.23-0.51 s) and the modelled 6 s application start-up.
  They also keep usage-based list-price estimates (USD 0.92) separate from unreconciled AWS charges. No C1-C3 or
  regeneration figure is presented as an AWS cost.
- R2.4, R2.19, R2.9, R5.M5, R1.x, R2.5 and R4.1. They cite fast-simulator or open-loop analyses with their own scope
  and "[figures to be regenerated]" markers, and no regenerated value contradicts them.
- The two 1.92% figures stay in separate, named rows: R3.4 (the Erlang-B overflow error) and R2.13 (the integer-search
  saving).

## 4. Status review

| ID | Status | Basis |
|---|---|---|
| R2.1, R2.18, R3.3, R3.6, R4.2, R6.4, R6.5 | Partially fixed, kept | A substantive subrequest is answered in simulation by verified evidence (C1-C3; regeneration for R3.6(a), in one library version), and the manuscript, release or calibrated rerun is open. |
| R4.10, R4.11, R5.M7, R5.m4, R5.m5, R7.6 | Not fixed, kept | Every subrequest is a figure, wording or supplement edit. |
| Outside the targets | No change proposed | R3.5 now has both requests met in simulation but stays Partially fixed, because the manuscript must report them. R6.6 and R2.22 are manuscript labelling. |

## 5. Unresolved contradictions and decisions

1. **Reporting platform** (R3.6, R2.16, R2.17, R5.M6, R2.15): regenerate the forecast-driven tables on Linux x86-64,
   as `REPRODUCE.md` commits, or report the Windows regeneration and name that platform. Evidence needed for the first:
   `scripts/check_reproducibility.py` 6 of 6 on Linux, then `run_regeneration.sh` there.
2. **Which table version the paper reports** (submitted or regenerated). This affects R4.10, R5.m5, R5.M7, R7.6 and
   K6. It is tied to decision 1 and to the calibrated rerun.
3. **E3/E7/E9 lookup fix in the released code** before release (R3.6(b)), and the regeneration of Tables VIII and X
   from the fixed code.
4. **P3 and the other constants** (`CONSTANTS.md`): every C1-C3 and regenerated value supersedes at recalibration.
5. **Unattributed residual.** The platform part of the stored-to-current shift (−0.32 points at 1.0%) is not
   attributed. Isolating it would need a Linux run (decision 1).

## 6. Further runs (documented, not run)

| Question | Proposed test | IDs |
|---|---|---|
| Do the regenerated tables hold on the reference platform? | `check_reproducibility.py`, then `run_regeneration.sh rest/post` on Linux x86-64; compare with `outputs/` | R3.6, R2.15, R2.16, R2.17, R5.M6 |
| Does Table X's larger gap (event level 6.14% against fast 1.69%) decompose like the stored one? | `event_severity_factors.py` R72 group on the regenerated E9 schedules after the code fix | R7.2, R3.3, R2.1 |
| Are the other baselines' closed-loop results consistent with C1-C3? | Exploratory closed-loop runs of PredHead, PredHead+S, Static, Scheduled on seeds 106-130, labelled exploratory | R2.2, R6.3, R5.M4, R4.10 |
| Where is the QuantProv-2048 optimum? | R2 grid extended below a = 0.4 (0.2, 0.3) on traces 101-102 | R5.m4, R5.M7 |
| Does the eps-to-compliance mapping hold on the regenerated rows? | Rerun the mapping script on the regenerated E1 | R2.3, R7.3 |
| Final values | C1-C3 and the regeneration on measured constants (after P3) | all 13 targets |
