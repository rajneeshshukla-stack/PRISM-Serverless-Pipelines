# R5.M6(b) on the reference platform: Table VI under scikit-learn 1.8.0 and 1.9.1, Linux x86-64 (24 Nov 2026)

Reviewer 5, major comment 6: "Under scikit-learn 1.9.1, single-run violating-window rates move by up to 0.74 points
and three validation selections would change ... Please ... report the Table VI differences under both library
versions."

**What ran.** The committed `scripts/revision/table6_versions.py` (91a4d8b), unchanged, once per environment, then
`--compare` (`run_linux.sh`).
- **Code:** `~/prism_linux/fix/prism-repro`. Its `src/` and `experiments/run_experiments.py` equal HEAD 3edc386 after
  line-ending normalisation.
- **Platform:** WSL2, x86-64, Python 3.12.3.
- **Environments:**
  - A: the pinned `py312`, `../../label_fix_20261123/env/linux_py312_freeze.txt`;
  - B: `py312_sk191`, the same pins with scikit-learn 1.9.1 (`linux_py312_sk191_freeze.txt`). scikit-learn 1.9.1
    also installs its dependency narwhals 2.29.0; nothing else differs.
- **Design:** fast simulator, development traces 101-105, four families (PRISM, PredHead, PredHead+hyst,
  QuantProv-q90), Section V-C tuning, four test weeks. PRE-CALIBRATION.

**Consistency check.** Under 1.8.0 the selections equal the Linux E1 rows (PRISM eps 0.08, 0.03, 0.08, 0.08, 0.08),
and the PRISM-minus-QuantProv-q90 row equals `../../label_fix_20261123/outputs/linux_tables/T6_paired_PRISM_vs_QuantProvq90.md`
(+0.4 +/- 3.4% stationary).

**Result** (`comparison.txt`; A -> B):
- **Selections:** 2 of 20 change (101: PRISM 0.08 -> 0.05; 102: PredHead+hyst 1.4 -> 1.3). Windows: 3 of 20.
- **Single-run test weeks:** violating windows move by up to 2.08 points, cost by up to 9.59%. Windows: 0.74 points
  and 8.43%.
- **Table VI:**
  - **vs QuantProv-q90:** every cost interval includes 0 under both versions (+0.4 / −0.2 / −2.0 / −1.5% -> +1.8 / +1.3
    / +0.0 / +0.1%). Mean differences move by +1.4 to +2.0 points. The reading "PRISM is not distinguishable from
    QuantProv-q90 in cost" holds under both.
  - **vs PredHead:** PRISM is costlier, with every interval excluding 0, under both (+12.0 to +17.8% -> +13.3 to
    +20.1%).
  - **vs PredHead+hyst:** cost moves by +1.9 to +3.0 points. The stationary interval changes from including 0 (+3.8
    +/- 5.6%) to excluding it (+5.9 +/- 5.6%). The violating-window differences shift by 0 to −0.63 points, and their
    intervals narrow.
- **Direction counts** (traces in which PRISM is cheaper): 0-4 under A, 0-3 under B.

**Reading.** The library version moves single runs and individual selections by more than the 0.74 points reported
on Windows. It changes no paired-comparison conclusion against QuantProv-q90 or PredHead. Against PredHead+hyst, one
stationary cost interval crosses 0. Statements at the 1-2% level should therefore be qualified by library version,
which is the reviewer's point.

**Files:**
- `run_linux.sh`, `run.log`;
- `table6_sklearn_1.8.0.json`, `table6_sklearn_1.9.1.json`, `comparison.txt`;
- `linux_py312_sk191_freeze.txt`;
- `SHA256SUMS`.

The Windows comparison (`../comparison.txt`, 21 Nov 2026) is unchanged.
