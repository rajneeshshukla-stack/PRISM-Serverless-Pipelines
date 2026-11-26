# Configuration note: start-up scaling in Groups A and B (25 Nov 2026, after the runs)

**Finding:** the calibrated configuration used for Groups A and B (`RUN_PLAN.md`, `cal_closed_loop.py`) set
`init_max_s = 10.0` but did not set `init_scaling`. So start-up kept the frozen Eq. (3) form, which shortens as memory
grows (`init_scaling = "eq3"`, `init_nonscaling = 0.7`).

**What was adopted:**
- P3 is a **memory-independent** start-up: 6 s, σ 0.30.
  - `../calibration_final_20261124/DECISIONS.md` section 3;
  - `../calibration_20261124/DECISION_RECORD.md`: "constant" in the primary configuration;
  - `ADOPTED_DECISIONS.md`.
- The configuration-mapping table in `ADOPTED_DECISIONS.md` lists only `init_max_s` for P3. That omission carried into
  the run.

**Mean start-up after truncation at 10 s, computed with the build:**

| Memory | As run (Eq. (3)) | Adopted (constant) |
|---|---|---|
| 1024 MB | 5.83 s | 5.83 s |
| 2048 MB | 5.05 s | 5.83 s |
| 3008 MB | 4.78 s | 5.83 s |

**Effect on the saved results (inference; not rerun):**
- **Fixed-1024 MB policies (QuantProv-q90, Reactive):** start-up at 1024 MB is identical under both forms, so their
  results, including infeasibility at every tested setting, are expected to be unchanged.
- **PRISM and MemAdapt-q90, at 2048 MB in every epoch:**
  - Their cold starts were about 0.8 s shorter than adopted, so cold-start misses may be understated.
  - Their planning tables also used Eq. (3).
  - At 12 s, MemAdapt-q90 is 0.21-0.81 points below the 2% target, so its compliance verdict is the most sensitive.
- **Cost:** costs and premiums may also change, because provisioning responds to the planning tables.
- **Miss table:** the warm-miss entries (`miss_table.txt`) are unaffected. The one-cold-stage entries used Eq. (3).

**Labelling:** Groups A and B are calibrated development evidence (traces 101-105) with one input, start-up scaling,
not yet at the adopted value.

**Before they are cited as the adopted configuration:** rerun Groups A and B, or at least the PRISM and MemAdapt-q90
groups, with `init_scaling = "constant"`.
- This needs authorisation; nothing was run.
- `RUN_PLAN.md`, `ADOPTED_DECISIONS.md`, `ADDENDUM.md` and their hashes are unchanged.
- This note is the dated record.

## Resolution: corrected rerun (25 Nov 2026, 18:50-22:04Z)

- **Driver and output:** `cal_closed_loop_p3.py` and `run_linux_p3.sh`, the original configuration plus
  `init_scaling = "constant"`, written to a fresh output directory, `~/prism_linux/calbuild_p3_20261125`. The Eq. (3)
  results are preserved.
- **Pre-launch check (`precheck_p3_output.txt`):** start-up draws are identical at 1024 and 2048 MB and, at 1024 MB,
  identical to the Eq. (3) runs.
- **Fixed-1024 MB equivalence:** 20 of 20 weeks are bit-identical (`equivalence_p3.txt`), so the Group A QuantProv-q90
  and Reactive groups are reused.
- **Corrected PRISM and MemAdapt-q90 groups:** 100 weeks at 14.5 s and 101 at 12 s (`p3_results.txt` and `.json`).
  - **14.5 s:** both meet 2% on 5 of 5 traces, PRISM +18.6-19.2%.
  - **12 s:** PRISM meets 2% in 4 of 5 test weeks and MemAdapt-q90 in 2 of 5, PRISM +10.7-18.6% (confounded).
- **Readiness:** the C3 edge condition is met (MemAdapt-q90 at the edge on 1 of 5 traces). C1-C2 is not, so the
  held-out run stays blocked.
