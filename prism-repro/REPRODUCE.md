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
version (Supplementary S1). Exact numbers need the pinned versions; with other versions expect the
same orderings and small numeric differences. Example: the level-choice count is 26 of 40,307 epochs
in the pinned Windows environment and 22 of 40,309 in the earlier Python 3.13 / scikit-learn 1.9.1
session (`KNOWN_ISSUES.md`, revision-branch section).

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
| Cold-hit floor retuned at matched compliance (R2.12) | `python scripts/revision/kappa_floor_retune.py . <out_dir>` (5 processes) | 16 min (300 runs) |

## 4. Analyses of the stored results (read only)

| What | Command |
|---|---|
| Tables of E1-E11 | `python scripts/analyze.py` |
| Grid-edge audit (R5.M4, R4.7) | `python scripts/revision/grid_edge_audit.py . results/raw/E1/rows.jsonl` (also `results/raw/E12`, `results/raw/R1/rows.jsonl`; `--week test` for post hoc selections) |
| Epsilon to violating-window mapping (R2.3, R7.3) | `python scripts/revision/eps_window_mapping.py . results/raw/E1/rows.jsonl` |
| Revision analyses of the submission | as listed in `README.md` ("Reproduce") |
| File checksums | `python scripts/build_manifest.py --verify` (never run it without `--verify`). `CHECKSUMS.sha256` hashes the LF file contents of `v1-submitted` (0 mismatches against that tag's committed files). On an LF checkout every file changed since then mismatches until the regeneration rebuilds the file: 13 on `main` at `2bdeaba`, more on the revision branch. On Windows with `core.autocrlf=true` the tool hashes the CRLF working copy, so almost every text file mismatches (201 of 290 here); verify on an LF checkout |

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
