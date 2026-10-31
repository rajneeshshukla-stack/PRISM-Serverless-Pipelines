# Provenance

## Runs and environments

| Results | Produced | Environment | Record |
|---|---|---|---|
| E1–E7, E9–E11 (original evaluation) | 29–30 Oct 2026, one CPU core | Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, scikit-learn 1.8.0, matplotlib 3.10.8 (`requirements.txt`) | `RUN_MANIFEST.json` (git log, source hashes, file hashes) |
| E8 completion, E12 (post hoc, revision) | 30 Oct 2026 | scikit-learn 1.9.1 (see `RUN_MANIFEST_REVISION.json`) | `RUN_MANIFEST_REVISION.json` |
| Post hoc analyses (no new simulation) | 30 Oct 2026 | — | `results/tables/revision/` |
| E4b and level-choice diagnostic (post hoc, manuscript V2.8) | 30 Oct 2026 | Python 3.13.18, numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, scikit-learn 1.9.1 | `results/raw/E4b/`, `results/tables/revision/E4b_fixed_memory_summary.json`, `level_choice_diagnostic.json` |

**Source versions.** Every stored run records the hash of the code that produced it (`source_sha256`). The
final code has `8c1710f74c3d…`. The E1 runs of seeds 101–103 ran on an earlier, uncommitted state of the source
(`af08337bc262…`); the protocol log did not record a change to `src/` between the two E1 batches. Re-simulated
with the final code (under scikit-learn 1.9.1), the 84 stored runs of seeds 101–103 without a learned forecaster
are bit-identical, and their 144 forecast-driven runs change about as much as the 48 runs of seed 104, which ran on
the final code: cost by a median of 0.08% and at most 0.80% (seed 104: 0.24% and 1.49%), violating-window rate by
at most 0.74 points (seed 104: 0.60) (`scripts/revision/version_check/resim_new_spike_101-102-103-104.json`).

**Comment-only update.** During the manuscript correction, comments and docstrings in `src/prism_repro` were
updated to the paper's numbering. The program is unchanged (syntax trees identical:
`scripts/revision/version_check/check_source_equivalence.py`), but the hash of the commented source is
`d4bad4e2b096…`, not `8c1710f74c3d…`. The released source is the commented one; the check above shows that it is
the same program.

**Protocol timing.** `EVALUATION_PROTOCOL.md` states that it was written before any evaluation-seed run. The
earliest commit containing it (`6db1f8d`, 23:15:54 UTC on 29 Oct 2026) is about four minutes later than the
start of the first stored E1 run (23:12:16 UTC); both times are in `RUN_MANIFEST.json`.

## Earlier record of additions (from the revision addendum)


This release extends the original evaluation release (E1–E11, unchanged) with the material behind the
revised manuscript. Nothing in `results/raw/E1`–`E7` or `E9`–`E11` was changed, and `scripts/analyze.py`
regenerates all of their tables byte for byte from the stored raw results.

| Added or changed | Where |
|---|---|
| E8 completed for seeds 101–105 (reference forecasters) | `results/raw/E8/` (original partial rows kept as `*_original_env.*`) |
| E12 event-level re-tuning (open loop) | `results/raw/E12/` |
| Revision and audit scripts; scripts that draw the manuscript's Figs. 3–7 and its two diagrams (numbering of the earlier version; in manuscript V2.8: Fig. 2 and Suppl. Figs. S2–S5, and the diagrams Fig. 1 and Suppl. Fig. S1) | `scripts/revision/`, `scripts/revision/figures/` |
| Analysis outputs of the revision (E8, E12, post hoc matched compliance, per-trace intervals, billing bounds) | `results/tables/revision/` |
| T18 regenerated (gradient-boosting rows from E2, as in the paper); T19 now generated | `results/tables/T18_*`, `results/tables/T19_*` |
| Provenance of E8/E12 and the post hoc outputs; checksums of every file | `RUN_MANIFEST_REVISION.json`, `CHECKSUMS.sha256` |
| Protocol change log entries for the above | `EVALUATION_PROTOCOL.md`, section 9 |

`RUN_MANIFEST.json` still describes the original runs and their environment (scikit-learn 1.8.0). E8 and E12
were run later under scikit-learn 1.9.1; E12 replays stored schedules and the E8 reference forecasters use no
learned model, so neither result depends on that difference.

Regenerate and verify:

```
python scripts/analyze.py
python scripts/revision/analyze_e8.py . results/raw/E8/rows.jsonl
python scripts/revision/analyze_e12.py results/raw/E12
python scripts/revision/posthoc_analysis.py .
python scripts/revision/pc_billing_bounds.py .
python scripts/revision/matched_compliance_pertrace.py .
python scripts/revision/figures/make_figs.py . <out_dir>     # V2.8: Fig. 2 and Suppl. Figs. S2-S5
python scripts/revision/figures/make_diagrams.py <out_dir>    # V2.8: Fig. 1 and Suppl. Fig. S1
python scripts/build_manifest.py --verify
```

## Stage 2 correction of the manuscript (V2.6 draft; working copy, not a release)

| Changed or added | Where | Effect on results |
|---|---|---|
| Comments and docstrings cite the V2.6 article and supplement numbering (M15); `scripts/` keep the original manuscript's numbering because they transcribe and test its claims | `src/prism_repro/*.py` | none: syntax trees identical; the recorded source hash changes from `8c1710f74c3d…` to `d4bad4e2b096…` |
| Paired differences pair rows by trace (seed) key (M16) | `scripts/analyze.py` | none: all 53 tables of `analyze.py` and `results/summary.json` regenerate byte for byte (as do the 6 revision outputs) |
| Version-sensitivity check and source-equivalence check (P6, M15) | `scripts/revision/version_check/` | post hoc verification only |

`RUN_MANIFEST.json` still records the original environment and the source hash `8c1710f74c3d…` of the final
code (E1 seeds 101–103 ran on the earlier source `af08337…`); it was deliberately not regenerated. `CHECKSUMS.sha256` was regenerated for
this working copy. (Superseded on 30 Oct 2026: all three authors have agreed, verbally, to the results basis, the author list and
the release of this code; release now waits for the choice of licence, repository and archive.)
