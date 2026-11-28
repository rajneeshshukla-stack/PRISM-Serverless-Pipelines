# Data sources, licences and unpublished inputs (revision, 25 Nov 2026)

Paths are relative to `prism-repro/`. Licences were checked at the upstream sources on 25 Nov 2026.

## 1. Summary

| Data | Used for | Licence | In this repository | Otherwise |
|---|---|---|---|---|
| Synthetic workloads | every simulation result | generated; no third-party content | regenerated from the seeds | `docs/DATA_CARD.md` section 1 |
| Huawei Private 2023: five functions | Huawei replay (submitted Table XII, planned revised Table XIII) | CC BY 4.0 | `data/real/huawei_fn*.csv` (derived) | `data/real/README.md` |
| Huawei Public Cloud 2025, Region 2 per-minute requests | R2.9 less-structured traces; R3.2 hybrid-histogram check | CC BY 4.0 | `data/real/huawei2025_region2_r29/` (10 derived traces) | section 2 |
| Huawei Public Cloud 2025: cold starts (Regions 1-5) and the Region 2 runtime table | R1.2 and R5.M2, initialisation time against memory | CC BY 4.0 | not included (0.82 GB) | section 2 |
| SeBS artifact (AWS Lambda, 2020): 74 performance-cost files | R1.2 and R5.M2, initialisation time against memory | CC BY 4.0 (Zenodo record) | not included (33.9 MB): the copy used comes from the artifact's GitHub repository, which states no licence, and was not checked against the Zenodo archive | section 3 |
| Azure Functions Dataset 2019: days 1-7 invocations | R3.2 hybrid-histogram reproduction attempt | CC BY 4.0 | not included (about 965 MB) | section 4 |
| Own AWS measurements: memcal-1, the integration run, the R6.1 replay | planned Tables XIV and S16-S18; replies R6.1, R2.14, R2.20, R4.3, R6.2 | own data | aggregates, sanitized summaries and hashes only | section 5 |

`third_party_inputs.tsv` lists every third-party file held for this work, with its size, SHA-256, upstream archive and
archive member, and which study used it. Files marked "not used by a reported result" were downloaded with the others
but feed no result.

## 2. Huawei Public Cloud Trace 2025

- **Where:** https://github.com/sir-lab/data-release/blob/main/README_data_release_2025.md. The files are Google Drive
  links listed there:
  - "Huawei Public cold starts": Region 1-5 cold starts, `R1.zip` to `R5.zip`;
  - "Huawei Public trigger types and runtime languages (2025)": Region 2 runtimes and trigger types,
    `df_funcID_runtime_triggerType.csv`;
  - "Huawei Public time series (2025)": Region 2 quantiles, downloaded as `R2-minute-metrics.zip`.
- **Version:** the 2025 release (31 days), downloaded on 21 Nov 2026. Check a download against the SHA-256 in
  `third_party_inputs.tsv`.
- **Paper:** "Serverless Cold Starts and Where to Find Them", EuroSys 2025, arXiv:2410.06145.
- **Licence:** CC BY 4.0. The repository README states "Licensed under the Creative Commons Attribution 4.0
  International (CC BY 4.0) license".
- **R2.9 inputs:**
  - The selection rule is in `data/real/huawei2025_region2_r29/README.md`, and the traces are published there.
  - To re-derive them (no simulation):
    `python scripts/revision/less_structured_region2.py . --select <data>/huawei_public_2025/R2_minute_metrics/R2/requests <new derived dir> <new out dir>`.
  - Compare the result with `SHA256SUMS` in `data/real/huawei2025_region2_r29/`.
  - The `--run` step of the same script is a simulation (`docs/revision/less_structured_r29_20261122/README.md`).
- **Initialisation against memory:**
  - The command is `python -I docs/revision/init_vs_memory/rerun_20261121-163247/r12_init_vs_memory.py <data> <out>`.
  - `<data>` holds the files at the `dest_path` locations of `third_party_inputs.tsv`, and a copy of that file named
    `MANIFEST.tsv`. The script checks all 80 inputs against it before use.

## 3. SeBS artifact (AWS Lambda, 2020)

- **Archival record:** https://doi.org/10.5281/zenodo.5209001
  - "SeBS: A Serverless Benchmark Suite for Function-as-a-Service Computing";
  - published 17 Aug 2021, licence CC BY 4.0;
  - one file, `artifact.tar.gz`, 3,932,866,866 bytes.
- **Copy used:** the same artifact's GitHub repository, https://github.com/spcl/serverless-benchmarks-artifact, at
  commit `22e8134ca789a54cffd789265303c17d5a0536db` (1 Sep 2021). Paths used:
  `data/performance/aws_perf_cost/<benchmark>/perf-cost/*.json` (74 files) and `experiments/perf_cost/aws/*.json`
  (configurations).
- **Checksums:** GitHub builds archive zips on request, so a fresh download can differ byte for byte. Use the
  per-file SHA-256 in `third_party_inputs.tsv`.
- **Caveats:**
  - The data were collected in 2020; the README says August, the invocation timestamps say November.
  - The runtimes are Python 3.6 and Node.js.
  - 299 cold invocations lack the initialisation fields.
  - Lambda's initialisation duration excludes environment creation.

## 4. Azure Functions Dataset 2019

- **Where:** https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md. The download is
  https://github.com/Azure/AzurePublicDataset/releases/download/dataset-functions-2019/azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz
  (copy used: 142,968,140 bytes, SHA-256 `aff8b3ca7240a41a109e4ee598e0a96e45fcb92e7b8395ac19cb3748cd260d89`).
- **Files used:** the archive members `invocations_per_function_md.anon.d01.csv` to `d07.csv`; SHA-256 in
  `third_party_inputs.tsv`.
- **Licence:** CC BY 4.0, from the repository `LICENSE`. The dataset page asks users to cite M. Shahrad et al.,
  "Serverless in the Wild", USENIX ATC 2020.
- **Commands:**
  - `python -I scripts/revision/hybrid_reproduction.py <folder with the seven files> <out>`;
  - `python scripts/revision/hybrid_tablev_decisions.py <out>`.
  - The outcome, a hybrid policy that was **not reproduced** against the prespecified criteria, is in
    `docs/revision/hybrid_reproduction_r32_20261124/README.md`.

## 5. Inputs that are not published, and the results they affect

Each entry is an input withheld on purpose. These are availability limits, not checksum failures. Every published
checksum list verifies (`README.md`, Verify).

| Not published | Why | Published instead | Affected results |
|---|---|---|---|
| Raw AWS run folders, CloudTrail logs and billing exports | they carry account identifiers and billing data | aggregates; the harnesses `aws_pipeline/` and `aws_measurement/`; SHA-256 of the private files that each published analysis read: `docs/revision/aws_live_integration/sources.sha256` (integration run, 18 files including its CloudTrail export), `aws_live_collector_20261122/sources.sha256` (collector test, 20 including its CloudTrail export), `aws_memcal_20261122/sources.sha256` (memcal-1, the 10 run files read), `r61_live_run_20261125/raw_sources.sha256` (R6.1 run folder, 21), `billing_reconciliation_20261124/reconciliation.json` (22 Nov 2026 export, 3) and, added 28 Nov 2026, `r61_live_run_20261125/sanitized_summaries_20261128/sources.sha256` (25 Nov 2026 export, 3, and the R6.1 CloudTrail export, 2, with sanitized summaries of both). **Not every raw file has a public checksum.** Without one: the memcal-1 CloudTrail export (4 files), 38 memcal-1 run files that no published analysis read (32 local analysis files and 6 per-block run files), and 3 files of the earlier 22 Nov 2026 Cost Explorer queries (two byte-identical responses without line items and the query command). | Tables XIV and S16-S17 cannot be re-derived from raw records. TR5's 25 Nov 2026 billing row (Supplementary Table S18) is generated from the sanitized summary; checking its figures against the export itself needs access to the export. Repeating the measurements needs an AWS account, and charges apply. |
| REGEN-WIN raw files other than the figure inputs and the 40 files in the input archive: the E2 arrays for seeds 102-105, the first-written rows of E3, E7 and E9 (the archive holds their label-fix rows), and all of E4, E4b, E5, E6, E8, E10, E12, R1 and R2 (71 of 111 files) | size; the tables they produce are published | the regenerated tables (`docs/revision/regeneration_20261122/outputs/tables/`); the rows behind Fig. 2 and Figs. S2-S5 (`docs/reproducibility/figure_inputs_regen_win/`); the input archive `docs/reproducibility/inputs/` (40 REGEN-WIN files byte-identical to the run's: all files of E1, E11 and E11occ and the arrays of E3, E7 and E9; plus the label-fix rows of E3, E7 and E9) | Re-analysing the other tables from REGEN-WIN rows needs a rerun at fd8b01a (`docs/revision/regeneration_20261122/README.md`). The rerun is a simulation of about 1.5-2 h for E1-E11, plus E8 and E12. Forecast-driven results are reproduced exactly only on the platform of the set (Windows 11, pinned packages); see TR6. |
| Per-week outputs of the calibrated development runs (Linux run folders): none since 28 Nov 2026 | published unchanged on 28 Nov 2026 | the per-week outputs themselves, `docs/revision/calibrated_build_20261125/weeks/calbuild_20261125/` (737 files) and `docs/revision/calibrated_build_20261125/weeks/calbuild_p3_20261125/` (467 files), with checksums in `docs/revision/calibrated_build_20261125/weeks/SHA256SUMS`; the per-trace results (`p3_results.json`, `group_A_results.json`, `group_B_results.json`), the scripts and the run plan | None for re-analysis. Regeneration has no standalone command in the index: `run_linux.sh` and `run_linux_p3.sh` assume the authors' local directory layout (a Linux clone of 92e3e68 with `docs/revision/p2_dependence_20261124/candidate_exec_p2.patch`); a rerun is a simulation. |
| Linux E4 and E4b rows behind `docs/revision/graphical_abstract_20261123/linux_e4b/` (7 files) | kept with the Linux clone | their SHA-256 (`linux_e4b/inputs.sha256`) and the outputs | Only the Linux check of the 13-27% memory statement. The Windows values used in the abstract are reproducible from `regeneration_20261122`. |
| Third-party inputs: Huawei 2025 cold starts and runtime table (0.82 GB), SeBS files (33.9 MB), Azure 2019 days 1-7 (965 MB) | size, and for SeBS an unconfirmed licence for the exact copy used; all are available upstream | links, versions and per-file SHA-256 (sections 2-4) | None, once downloaded. |
