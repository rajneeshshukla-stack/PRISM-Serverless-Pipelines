# Reviewer access: reproducing the regenerated analysis (draft, 24 Nov 2026; NOT YET PROVIDED)

Access has not been given and nothing has been published. This note is for the author to send through the editor
once the branch and the input archive are released.

## What is released

- **Code:** branch `closed-loop` at commit `3edc386fe88eba8bab16e0906c091e81004a6982`, plus
  `prism-repro/.gitattributes`, which keeps the checksum manifests at LF on Windows checkouts.
  - Status: the commit is local, not pushed; `.gitattributes` is not yet committed.
  - If `.gitattributes` is not in the released commit, Windows users verify with
    `tr -d '\r' < release_inputs.sha256 | sha256sum -c`.
- **Input data:** `prism_r36_reproduction_inputs_20261123.tar.gz`. Status: not yet published.
  - SHA-256 `52c1c701655a08f17516bae56ae4f92be79b139a19e0b3e18128d05d62f27dd2`, 42,466,849 bytes, 74 files.
  - It holds the completed experiment rows written by the current code, under `prism_r36_inputs/windows/` (E1, E3,
    E7, E9, E11, E11occ) and `prism_r36_inputs/linux/` (E1, E3, E7, E9), and the manifest `release_inputs.sha256`.

## Environment

Python 3.12 with the exact versions used for the checks:
- Windows: `docs/revision/label_fix_20261123/env/windows_venv_freeze.txt`;
- Linux x86-64: `docs/revision/label_fix_20261123/env/linux_py312_freeze.txt`.

Both pin numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, scikit-learn 1.8.0, matplotlib 3.10.8 and tabulate 0.10.0. Use these
files rather than `requirements.txt`, which allows any tabulate >= 0.9. The byte-identical table comparisons were made
with tabulate 0.10.0.

## Commands (from the repository's `prism-repro/` directory)

```bash
python -m venv venv && venv/bin/python -m pip install -r docs/revision/label_fix_20261123/env/linux_py312_freeze.txt
mkdir inputs && tar -xzf prism_r36_reproduction_inputs_20261123.tar.gz -C inputs
(cd inputs/prism_r36_inputs && sha256sum -c release_inputs.sha256)          # 74 x OK
I=inputs/prism_r36_inputs
venv/bin/python docs/revision/label_fix_20261123/reproduce_analysis.py --code . --out out_linux \
    --input E1=$I/linux --input E3=$I/linux --input E7=$I/linux --input E9=$I/linux
venv/bin/python docs/revision/label_fix_20261123/reproduce_analysis.py --code . --out out_windows \
    --input E1=$I/windows --input E3=$I/windows --input E7=$I/windows --input E9=$I/windows \
    --input E11=$I/windows --input E11occ=$I/windows
```

On Windows, use `venv\Scripts\python` and the Windows freeze file. Each run takes under a minute and runs no
simulation. `--out` must be a new directory.

## What a successful run shows (verified 24 Nov 2026 from a clean archive of 3edc386)

**The run prints `CHECK` lines, all true:**
- E1 has 1,900 rows;
- PRISM's main configuration is 150 `PRISM_EB` rows;
- the selected PRISM eps are 0.08, 0.03, 0.08, 0.08, 0.08 (Linux rows) or 0.05, 0.03, 0.08, 0.08, 0.08 (Windows rows);
- every Table V scenario has n = 5;
- the E11 table compares Eq. (5) with Erlang-B.

**Outputs that must match:**
- `out_*/tree/results/tables/` equal `docs/revision/label_fix_20261123/outputs/linux_tables/` (Linux rows), and the
  regenerated Windows tables. Line endings may differ. Only the measured decision-time column of
  `E3_quantile_vs_scenario_feasibility` is a wall-clock value.
- `out_*/r76_endpoints.json` equals the corresponding values in
  `docs/revision/label_fix_20261123/outputs/r76_endpoints_full_precision.json`.

## Scope

**This reproduces:**
- the regenerated analysis tables;
- the post hoc matched-compliance (R7.6) endpoints;
- the billing bounds;
- the Erlang-B against Eq. (5) comparison;

all from the completed experiment rows.

**It does not:**
- **rerun the simulations.** The experiment commands and their run times are in `REPRODUCE.md`. Forecast-driven
  results reproduce exactly only on Linux x86-64 with the pinned versions;
- **cover the C1-C3 closed-loop runs.** Their driver and outputs are under `docs/revision/confirmatory_20261122/`.

All values are PRE-CALIBRATION.
