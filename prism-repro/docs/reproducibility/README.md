# Reproducibility materials for the revision (25 Nov 2026)

The entry point is `../../../REPRODUCIBILITY.md`. This folder holds what the evidence folders under `../revision/` do
not:
- the generators of the revision tables and figures, and the inputs they need;
- the input archive for re-running the analysis from completed experiment rows;
- the data notes.

Paths are relative to `prism-repro/`. None of the commands below runs a simulation or contacts a cloud service.

| Path | Contents |
|---|---|
| `make_tables.py` | Rebuilds `tables/`: TR1-TR6, the graphical-abstract inputs and the REGEN-WIN table map. It reads committed evidence only, and asserts every value against the value verified on 25 Nov 2026. |
| `make_figures.py` | Rebuilds FR1 (planned Fig. S6), FR2 (planned Fig. S7) and the REGEN-WIN paper figures (Fig. 2, Figs. S2-S5). |
| `tables/` | Committed outputs of `make_tables.py`. |
| `figure_inputs_regen_win/` | The REGEN-WIN rows read by `scripts/revision/figures/make_figs.py`: the E1, E2 and E9 rows, and the E2 arrays of trace 101. They come from commit fd8b01a on Windows, and are the analysis copy after the label normalisation described in `docs/revision/regeneration_20261122/README.md`. |
| `inputs/prism_r36_reproduction_inputs_20261123.tar.gz` | 42,466,849 bytes, SHA-256 `52c1c701655a08f17516bae56ae4f92be79b139a19e0b3e18128d05d62f27dd2`. It holds 74 completed experiment row files written by the corrected code (label-fix pass, 6e0f05c): Windows E1, E3, E7, E9, E11 and E11occ, and Linux E1, E3, E7 and E9. Their manifest, `release_inputs.sha256`, is inside. The rows are synthetic simulation output and contain no third-party or personal data. |
| `DATA_SOURCES.md`, `third_party_inputs.tsv` | Third-party data: where to obtain it, its licence and per-file SHA-256. Also lists inputs that are not published and the results they affect. |
| `SHA256SUMS` | Every file in this folder. `.gitattributes` keeps the files byte for byte on every platform. |

## Environment

Use Python 3.12 with the pinned packages: numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, scikit-learn 1.8.0,
matplotlib 3.10.8 and tabulate 0.10.0. The freeze files are:
- Windows: `docs/revision/label_fix_20261123/env/windows_venv_freeze.txt`;
- Linux: `docs/revision/label_fix_20261123/env/linux_py312_freeze.txt`.

## Commands

1. **Revision tables.** Run `python docs/reproducibility/make_tables.py <new dir>`, then `diff -r docs/reproducibility/tables <new dir>`.
2. **Revision and REGEN-WIN figures.** Run `python docs/reproducibility/make_figures.py <new dir>`.
   - It prints MATCH or DIFFER for every PNG and TIFF against reference hashes from Windows 11.
   - Pixels depend on the installed fonts (the reference used the DejaVu Serif fallback). The plotted values do not.
3. **Regenerated analysis tables from completed rows (R3.6).**
   ```bash
   mkdir inputs && tar -xzf docs/reproducibility/inputs/prism_r36_reproduction_inputs_20261123.tar.gz -C inputs
   (cd inputs/prism_r36_inputs && sha256sum -c release_inputs.sha256)          # 74 x OK
   I=inputs/prism_r36_inputs
   python docs/revision/label_fix_20261123/reproduce_analysis.py --code . --out out_windows \
       --input E1=$I/windows --input E3=$I/windows --input E7=$I/windows --input E9=$I/windows \
       --input E11=$I/windows --input E11occ=$I/windows
   python docs/revision/label_fix_20261123/reproduce_analysis.py --code . --out out_linux \
       --input E1=$I/linux --input E3=$I/linux --input E7=$I/linux --input E9=$I/linux
   ```
   - **Expected output:** every `CHECK` line is true.
   - **Windows rows:** `out_windows/tree/results/tables/` equals `docs/revision/regeneration_20261122/outputs/tables/`.
   - **Linux rows:** `out_linux/tree/results/tables/` equals `docs/revision/label_fix_20261123/outputs/linux_tables/`.
   - **Allowed differences:** line endings may differ. The measured decision-time column of
     `E3_quantile_vs_scenario_feasibility` is wall-clock time.
   - **Older notes:** this replaces the status notes of `docs/revision/release_check_20261124/REVIEWER_ACCESS.md`, a
     dated draft written before the code reached `main` and before this archive was published.
4. **C1-C3 from the saved held-out weeks.**
   - Copy `docs/revision/confirmatory_20261122/run` to a new folder.
   - Run `python scripts/revision/closed_loop_confirmatory.py analyse <copy>`.
   - Expected: `<copy>/tables/` equals the committed `run/tables/`.

## Verify

- **This folder and the R2.9 traces:** run `sha256sum -c SHA256SUMS` here and in `data/real/huawei2025_region2_r29/`.
- **Evidence folders under `docs/revision/`, on a Windows checkout with `core.autocrlf=true`:** run
  `sha256sum -c SHA256SUMS`.
- **Any other checkout:** use `SHA256SUMS.lf` where it exists. It hashes the committed LF content.
- **Companions added on 25 Nov 2026:** twelve `.lf` companions. Three of their entries name a script by a path relative
  to the folder (`../../../scripts/revision/...`), where the parent list used a path relative to `prism-repro/`.
- **Submitted outputs:** `python scripts/build_manifest.py --verify` checks `CHECKSUMS.sha256`. Every `results/` entry
  verifies. The 22 entries it reports are files changed since `v1-submitted`, because the manifest is frozen. Never run
  that script without `--verify`.
- **Documented exceptions:** these lists do not verify against the current files by design.
  - `docs/revision/matched_compliance_discrepancy/replay_20261122/SHA256SUMS.pre_redaction` hashes the working copies
    from before redaction.
  - `docs/revision/verification_20261122/SHA256SUMS(.lf)`:
    - its paths are relative to `docs/revision/`;
    - its progress-note entry is a historical snapshot (`VERIFICATION.md`).
  - `docs/revision/event_severity_resumed_20261122/ORIGINAL_ROWS(.lf).sha256` hashes the row files from before the run
    was resumed. Each is a byte prefix of the committed copy, and one was empty.
  - In `docs/revision/calibration_final_20261124/PLAN.sha256`, `ADDENDUM_DRAFT.md` gained a dated note after hashing.
    The hashed text is a prefix of the committed file.
  - `docs/revision/closed_loop_pilot/run_20261121-122241(.lf).sha256` is checked from the run folder:
    `cd run_20261121-122241 && sha256sum -c ../run_20261121-122241.lf.sha256`.
- **Lists checked from `prism-repro/`:** their paths are relative to `prism-repro/`.
  - `aws_pipeline/validation/memcal_prep_20261122/PLAN.sha256` (one entry and a comment line);
  - `docs/revision/r61_live_plan_20261123/PINNED_FILES.sha256` (nine entries and a note line);
  - the four `scripts/revision/` lines of `docs/revision/hybrid_reproduction_r32_20261124/SHA256SUMS`. Check the other
    lines of that list from its folder, as its README says.
- **Archive contents:** `docs/revision/label_fix_20261123/release_inputs.sha256` (74 entries) is checked inside the
  extracted archive (command 3).
- **Lists of files kept outside Git:** `sources.sha256` in three AWS folders, `docs/revision/r61_live_run_20261125/raw_sources.sha256`
  and `docs/revision/graphical_abstract_20261123/linux_e4b/inputs.sha256`. Their files are not in the repository
  (`DATA_SOURCES.md`, section 5). This is an availability limit, not a checksum failure.
