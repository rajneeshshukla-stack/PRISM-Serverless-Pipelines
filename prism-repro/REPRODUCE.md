# Reproducing PRISM (R3.6, R7.7)

Exact commands, environments and measured run times. `README.md` maps each table of the paper to
its stored output; this file says how to rebuild or check them, and what cannot be checked without a
real cloud platform. All workloads are **synthetic** unless stated (`docs/DATA_CARD.md`).

## 1. Which code produced what

| State | Code | Results |
|---|---|---|
| As submitted | tag `v1-submitted` (commit `3b4bc33`) | everything in `results/` (`CHECKSUMS.sha256` describes this state) |
| Corrected, not yet regenerated | `main` from `33d1000` on, and the revision branch `phase-e-review` | none of `results/` (see `KNOWN_ISSUES.md`); regeneration happens once, after the AWS constants are measured |

`git diff v1-submitted -- src/ tests/` lists every code change since submission. Every option added on
the revision branch defaults to the submitted behaviour, so the default configuration is unchanged
by it (bit-identical forecasts checked; see the commit messages).

## 2. Environment

| | Tested |
|---|---|
| Pinned | `requirements.txt`: numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, scikit-learn 1.8.0, matplotlib 3.10.8 |
| Windows 11 x86-64, Python 3.12.9, pinned versions in `venv/` | full test suite (`docs/TEST_REPORT.md`), every revision script below |
| Linux x86-64, Python 3.13.18 (numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1) | test suite at commit `2bdeaba` only |
| Reference sandbox, Python 3.12.3, pinned versions | the stored runs in `results/` |

```bash
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt     # Windows; venv/bin/python on Linux
```

Forecast-driven results (every policy that uses the GBM forecaster) depend on the scikit-learn
version (Supplementary S1) **and on the platform**. Exact numbers need the pinned versions on the
reference platform (Linux x86-64). Measured on Windows 11 with the pinned versions and the archived
`v1-submitted` tree (`scripts/check_reproducibility.py`, seed 101): OnDemand, Static and Reactive
reproduce the stored E1 rows bit for bit, while PredHead, QuantProv and PRISM do not (PRISM-0.05 USD
1,017.03 against 1,034.95 stored, -1.7%; across the 20 level-choice runs PRISM's cost differs from
E1 by up to 4.1%). The synthetic traces are bit-identical across the two platforms, and the
difference persists with one OpenMP thread and with numpy's AVX2/FMA3 dispatch disabled; its root
cause is not isolated. Expect the same orderings and percent-level numeric differences off the
reference platform. The level-choice count is the clearest case. On Linux with Python 3.13.18:
16 of 40,293 feasible epochs for the submitted tree (the published figure; reproduced exactly from an
archived `3b4bc33` tree in the author's Linux run) and 22 of 40,309 for corrected `main`. On Windows
(Python 3.12.9, pinned): 10 of 40,280 for the same archived submitted tree (identical, run by run, to
current code with `risk_model` set back to Eq. (5)) and 26 of 40,307 for corrected code. Every run
set has 40,320 epochs; provenance in `notes/number_audit.md`.

## 3. Checks that need no stored results

Times on a 4-core laptop CPU (Intel i5-10310U, 16 GB), one process unless stated.

| What | Command | Time |
|---|---|---|
| Unit and regression tests | `python -m unittest discover -s tests -v` | about 1 min |
| Byte-identical rerun gate (R2.16) | `python -m unittest tests.test_simulation.TestByteIdenticalRerun` | about 1-2 min |
| Trace set: 30 seeds, checksums, property screen | `python scripts/revision/trace_set.py . <out.json>` (recorded copy: `data/trace_set_revision.json`) | 20 s |
| One-parameter family gap, static (R2.13) | `python scripts/revision/integer_search_gap.py . <out.json>` | 4 s |
| Stage-specific demand gap, static (R4.1) | `python scripts/revision/stage_demand_gap.py . <out.json>` | 6 s |
| Level-choice diagnostic (20 PRISM test weeks) | `python scripts/revision/level_choice_diagnostic.py . <out.json>` | 8.5 min |
| Level-choice tie sensitivity (R2.17, R5.M6) | `python scripts/revision/level_choice_margins.py <code_root> <out.json>`; on the submitted code: `git archive 3b4bc33 prism-repro \| tar -x -C <dir>`, then run it with `<dir>/prism-repro` as `<code_root>` | 15 min |
| Cited anchors at printed precision | `python -m unittest tests.test_regression_anchors -v` | 10 s |
| Integer-search saving, end to end (R2.13; independent check, not the cited script) | `python scripts/revision/integer_search_e2e_check.py . <out.json>` (6 processes) | 6.5 min |
| Cold-hit floor retuned at matched compliance (R2.12) | `python scripts/revision/kappa_floor_retune.py . <out_dir>` (5 processes) | 16 min (300 runs) |
| Per-week held-out compliance (R2.4) | `python scripts/revision/weekly_compliance.py .` (reads `docs/revision/kappa_floor/`) | 1 s |
| Lag and init-direction sensitivity (R1.2, R1.3, R5.M2; pre-calibration) | `python scripts/revision/lag_init_sensitivity.py . <out_dir> both` (5 processes) | see `notes/number_audit.md` |

## 4. Analyses of the stored results (read only)

| What | Command |
|---|---|
| Tables of E1-E11 | `python scripts/analyze.py` |
| Grid-edge audit (R5.M4, R4.7) | `python scripts/revision/grid_edge_audit.py . results/raw/E1/rows.jsonl` (also `results/raw/E12`, `results/raw/R1/rows.jsonl`; `--week test` for post hoc selections) |
| Epsilon to violating-window mapping (R2.3, R7.3) | `python scripts/revision/eps_window_mapping.py . results/raw/E1/rows.jsonl` |
| Revision analyses of the submission | as listed in `README.md` ("Reproduce") |
| File checksums | `python scripts/build_manifest.py --verify` (never run it without `--verify`; `--root <tree>` checks another checkout against its own `CHECKSUMS.sha256`). `CHECKSUMS.sha256` hashes the LF file contents of `v1-submitted` (0 mismatches against that tag's committed files). Every file changed since then mismatches until the regeneration rebuilds the manifest; counts per commit are in `notes/number_audit.md` at the repository root. Text files also verify after CRLF->LF normalisation, so a Windows checkout (`core.autocrlf=true`) no longer flags unchanged files (before the fix: 201 of 290); binary files are compared byte for byte, and content changes and missing files still fail |

## 5. Re-running the experiments

`bash scripts/run_all.sh` (E1-E11, about 1.5-2 h on one core), then `python scripts/analyze.py`. E8
(about 2.9 h) and E12 (`python scripts/revision/e12_event_retune.py . <out_dir> 101 102 103 104 105`,
about 2.1 h) run separately. On the corrected code these runs will **not** reproduce `results/`
byte for byte; the measured differences of the code corrections are in `patches/diagnostic/`.

## 6. What still needs a real platform

Nothing in this repository calls a cloud API. These inputs are assumptions until measured on AWS
Lambda, and every result depends on them (`KNOWN_ISSUES.md` lists the switches that are ready):

| Input | Used as | Waiting for |
|---|---|---|
| Initialisation time vs memory (Eq. (3)) and its distribution | `init_mean_1024`, `init_shape`, `init_scaling`, `init_max_s` | init-duration campaign; the direction test decides RQ4 |
| Warm service-time distribution | `warm_mean_1024`, `exec_shape`, `nonscaling` | warm service-time campaign |
| Activation lag | `lag_min` (horizon and conformal delay follow it) | activation-lag campaign |
| Burst overflow beyond provisioned capacity | loss routing in both simulators | burst-overflow campaign |
| Billing (provisioning init, activation timing, recycling, granularity) | `pricing.py`, `prices` | bill reconciliation against the cost model |
| Memory sizes | `mem_options = (512, 1024, 2048, 3008)` | the campaign plans five sizes including 1536 MB (decision open) |
