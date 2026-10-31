PRISM code - release candidate 2.2.0rc1 for manuscript V2.8 (Stage 2.2), 30 Oct 2026
NOT A PUBLIC RELEASE. Do not publish or redistribute. No licence has been chosen (LICENSE_PENDING.md).

prism-repro/  Release candidate from branch stage2.2 (last commit that changed it: a79136d).
              Program code (src/, experiments/) and the stored results that the paper reports are unchanged from
              the code that produced them. patches/ holds the corrections of the three code defects disclosed in
              Section VI-G and Supplementary S1 (not applied; four tests; paired diagnostic of 435 configurations).
              results/raw/E4b/ and scripts/revision/e4b_*.py, level_choice_diagnostic.py hold the post hoc
              analyses added in Stage 2.2 (Table IX last-but-one column, Supplementary S9 and S11).
Checks (30 Oct 2026): build_manifest.py --verify 0 mismatches; 48 tests pass; 52 with the patch applied.

Added 31 Oct 2026 (manuscript V12): experiment R1, a post hoc replay of five real per-minute arrival traces
(Huawei Private 2023, CC BY 4.0; data/real/), with experiments/run_real_traces.py,
scripts/revision/analyze_real_traces.py, results/raw/R1/ (765 rows, PROVENANCE_R1.json) and
results/tables/R1_real_traces.{md,json}. Program code (src/) unchanged. CHECKSUMS.sha256 regenerated;
build_manifest.py --verify: 283 files, 0 mismatches; 48 tests pass.
Added 31 Oct 2026 (manuscript V13): experiment R2 (post hoc, synthetic), calibrated-quantile rules in the memory
regimes of Table IX (scripts/revision/r2_quantprov_memory.py, analyze_r2.py; results/raw/R2/ with
PROVENANCE_R2.json; results/tables/R2_quantprov_memory.{md,json}). Program code (src/) unchanged.
