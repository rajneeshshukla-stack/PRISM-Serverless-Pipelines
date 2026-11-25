# Calibration for the final PRISM evaluation: table, held-out check, opt-in per-size execution mode (24 Nov 2026)

No AWS call. No change to the pinned `src/` (3edc386; R6.1 run sheet), to the frozen prespecification, or to submitted
outputs. Every fitted value comes from the memcal-1 FIT split. No trace or seed is used for fitting, and seeds 106-130
are untouched.

## Files

| File | What it is |
|---|---|
| `CALIBRATION_TABLE.md` | Each simulator input: the measured quantity, value, units, memory, scope, and whether it supports a replacement |
| `DECISION_RECORD.md` | What can be calibrated now, what remains an assumption, what needs later AWS evidence; P2/P3 recommendations; the checks before a Linux C1-C3 rerun |
| `build_calibration.py` | Derives the per-size execution factors from FIT and checks them on CHECK |
| `exec_factor_measured.json`, `heldout_exec_measured.csv`, `heldout_coverage.txt` | Outputs of `build_calibration.py` |
| `candidate_exec_measured.patch` | The opt-in mode (`exec_scaling` = "measured", `exec_factor_measured`), against 3edc386 |
| `test_exec_measured.py` | Its 11 focused tests (a copy) |
| `worktree_test_suite.txt` | The full suite in the patched worktree: 139 of 139 pass |
| `smoke_exec_measured.py` | The smoke test |
| `smoke_legacy_pinned_tree.json/.txt`, `smoke_worktree.json/.txt` | Smoke outputs |

## Commands (from `prism-repro/`; one BLAS thread, `PYTHONUTF8=1`)

```bash
venv/Scripts/python docs/revision/calibration_20261124/build_calibration.py
(cd .. && git worktree add --detach prism-repro/private/calib_build_20261124 3edc386)   # isolated build
(cd private/calib_build_20261124/prism-repro && git apply ../../../docs/revision/calibration_20261124/candidate_exec_measured.patch)
cp docs/revision/calibration_20261124/test_exec_measured.py private/calib_build_20261124/prism-repro/tests/
(cd private/calib_build_20261124/prism-repro && PYTHONPATH=src ../../../venv/Scripts/python -m unittest discover -s tests -v)
venv/Scripts/python docs/revision/calibration_20261124/smoke_exec_measured.py . docs/revision/calibration_20261124/smoke_legacy_pinned_tree.json --legacy-only
venv/Scripts/python docs/revision/calibration_20261124/smoke_exec_measured.py private/calib_build_20261124/prism-repro docs/revision/calibration_20261124/smoke_worktree.json
```

The worktree used here is `prism-repro/private/calib_build_20261124` (Git-ignored), at 3edc386 plus the patch.

## Results

1. **Held-out coverage, 37/56** (`heldout_coverage.txt`):
   - the Eq. (2) warm-duration form misses all 16 cells (−10.1% to +13.1%);
   - Lambda Init passes 14/16 (Eq. (3) form) and 15/16 (measured mode), and its misses are about 2 ms;
   - P_mean passes 8/8.

   The model's real miss is Eq. (2): it cannot follow the one-vCPU plateau above 2048 MB.
2. **The per-size execution mode on CHECK:**
   - 14/16 cells inside the strict 95% interval;
   - 16/16 within the 0.41% between-block repeatability;
   - scaling factors within 0.30% (mean 0.14%), against Eq. (2)'s mean |error| of 9.0%.

   The live integration run's per-1,000-word ratios corroborate them.
3. **The opt-in mode, in an isolated worktree:**
   - the default stays `exec_scaling` = "eq2";
   - **11 of 11 new tests pass**: lookup, units in seconds, the plateau, unsupported sizes (1536, 2048.5), invalid
     modes, missing sizes, wrong stage count or sign, the 1024 MB reference fixed at 1, and caches that tell the modes
     apart;
   - **the full suite passes, 139 of 139**, including the byte-identical rerun gate and the regression anchors;
   - **legacy behaviour is unchanged:** the smoke cases give identical results from the pinned tree and the worktree.
4. **Smoke test** (development trace 101, fast simulator; `DECISION_RECORD.md` section 4):
   - At 14.5 s nothing changes, because 1024 MB is the reference.
   - At 13 s the selections (PRISM eps 0.01, MemAdapt 0.6) and the SLA verdicts (0.00%) are unchanged, but costs fall
     34% (PRISM) and 23% (MemAdapt). PRISM stops using 3008 MB, and its premium over MemAdapt goes from +28.7% to
     +10.4%.

   **The candidate stays opt-in:** promotion is decision D-CAL-1, and the frozen calibrated build comes after the R6.1
   run.

## Consequences for earlier claims (flagged; `notes/manuscript_proposals.md` M21)

Figures that rest on the assumed Eq. (2), which the measurements contradict above 2048 MB:
- the fast-simulator RQ4 premium "PRISM costs 8-28% more";
- "PRISM used 2048 and 3008 MB at 13 s";
- the fixed-2048 MB headroom saving of "13-27%" (or 14-29% submitted);
- the R2.7 shift test's "a one-time 3008 MB choice met the target". Under the measured scaling 3008 MB is no faster
  than 2048 MB.

They are correct for the pre-calibration model and must carry that scope until the calibrated evaluation recomputes
them.

R4.8's reply said "measured distribution" for the start-up time. The 6 s is declared, not measured.

At 14.5 s on the smoke trace, PRISM stayed at 1024 MB and every result was identical under both modes. The measured
scaling makes 2048 MB cheaper (about 1.15x the GB-s of 1024 MB instead of 1.5x), so whether PRISM stays at 1024 MB on
other traces, including the R1.1 margin traces, was **not checked**. The R1.1 finding keeps its pre-calibration scope.
