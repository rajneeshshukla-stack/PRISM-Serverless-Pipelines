# Platform check of the closed-loop event-level path (C1-C3 driver), Linux against Windows, trace 101 (24 Nov 2026)

**Purpose.** C1-C3 ran on Windows only. Their forecast-driven values may differ on the Linux reference platform. This
check measures how much, without using a confirmatory seed.

**What ran.** The C1-C3 driver (`scripts/revision/closed_loop_confirmatory.py`, SHA-256 3f909dc9..., the version
that produced C1-C3), set `pilot101`:
- development trace 101, stationary validation and test weeks;
- PRISM, QuantProv-q90, Reactive and MemAdapt-q90, each tuned by the frozen rule;
- 41 closed-loop event-level weeks.

**Linux run:** a clean clone of HEAD 3edc386 (`src/`, `experiments/` and `tests/` clean, as the driver requires), WSL2
x86-64, Python 3.12.3, pinned `py312` (scikit-learn 1.8.0), 4 workers (`run_linux.sh`). The first attempt from the
Windows working tree was refused by the driver's clean-code guard, because the checkout's line endings show as local
changes in WSL. Nothing ran in that attempt.

**Windows reference:** `../pilot101_check/`, the same set, at fd8b01a, whose `src/` equals 3edc386. It used an earlier
driver version (d9050e4b...) that gives the same selection and week logic: its weeks equal the saved pilot exactly.

**Result** (`linux_vs_windows.json`; `compare_platforms.py`):
- **Selections identical:** PRISM eps 0.01, QuantProv-q90 1.3, Reactive 0.55, MemAdapt-q90 1.3. No edge expansions.
- **Reactive,** which uses no forecast, is **bit-identical** in all 12 weeks.
- **PRISM, QuantProv-q90 and MemAdapt-q90,** which are forecast-driven: none of the 29 weeks is identical.
  - Validation weeks: cost within +/-1.0%, violating windows within 0.6 points.
  - Test weeks: PRISM 1,298.6 -> 1,286.7 USD (−0.92%), violating windows 1.79% on both; QuantProv-q90 and MemAdapt-q90
    1,256.8 -> 1,239.4 (−1.38%), violating windows 2.23% on both.
  - Paired PRISM minus QuantProv-q90 on this trace: +3.33% (Windows) against +3.82% (Linux), so the platform moves the
    paired cost difference by 0.5 points.

**What this answers.** The platform effect on the closed-loop path comes only from the forecasts. On one trace it moves
weekly cost by up to 1.4%, and the paired cost difference by about 0.5 points, without changing a selection.
- **C1:** cost +0.30% [−1.42, +2.01]. Its "no difference" reading is robust to shifts of this size. Its "not a tie"
  verdict is not: the upper end exceeds +2% by 0.011 points, so it is **platform-fragile**.
- **C3:** +13.06% [+8.50, +17.63], with compliance −0.655 points. Robust in direction and in its confounding.

C1-C3 therefore stay reported as Windows, pre-calibration. A Linux rerun of C1-C3 (about 34 CPU-h) would settle the
tie verdict on the reference platform. It is not run now, because the calibrated rerun, which the frozen prespecification requires,
supersedes the pre-calibration values and needs its modelling inputs settled first
(`../../calibration_inputs_20261124/README.md`). Running C1-C3 once, calibrated, on Linux would avoid a second full rerun.

**Files:**
- `run_linux.sh`, `run_log.txt`, `driver_run.log`;
- `environment.json`, `failures.json`;
- `groups/`, `weeks/`;
- `compare_platforms.py`, `linux_vs_windows.json`;
- `SHA256SUMS`.
