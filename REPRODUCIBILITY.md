# Reproducibility index: PRISM revision for IEEE Access (November 2026)

This index maps each result of the revised manuscript and of the replies to reviewers to its code, configuration,
inputs, outputs and commands.
- **Links:** relative, so they resolve within the commit you are viewing. Paths in commands are relative to
  `prism-repro/`.
- **Table and figure numbers:** they follow the planned revision, with submitted numbers in brackets. Check them
  against the final manuscript.
- **Citing:** cite this file at a fixed commit,
  `https://github.com/rajneeshshukla-stack/PRISM-Serverless-Pipelines/blob/<commit>/REPRODUCIBILITY.md`.
- **Evidence update (28 Nov 2026):** adds sanitized summaries of two private sources of the R6.1 replay day, the
  25 Nov 2026 billing export and the CloudTrail export
  ([sanitized_summaries_20261128](prism-repro/docs/revision/r61_live_run_20261125/sanitized_summaries_20261128/README.md)).
  It corrects TR5 to the count definitions used in Supplementary Table S18 and states the actual checksum coverage of
  the raw AWS files. No code, result or protocol changed; every code revision named below is unchanged.

## Reporting sets

| Set | What it is | Code | Platform and constants | Scope | Evidence |
|---|---|---|---|---|---|
| REGEN-WIN | every stored benchmark table, regenerated with the corrected code | fd8b01a (`src/` unchanged since) | Windows 11, Python 3.12.9, pinned packages; assumed platform constants | **PRE-CALIBRATION**; fast simulator unless stated; development traces 101-105 (Huawei replay: 201-205) | [regeneration_20261122](prism-repro/docs/revision/regeneration_20261122/README.md) |
| CONF-C1C3 | prespecified held-out comparisons C1-C3 | fd8b01a | Windows 11; closed-loop event-level simulator; assumed constants | **PRE-CALIBRATION**; held-out seeds 106-130; protocol frozen in [PRESPECIFICATION.md](prism-repro/docs/revision/PRESPECIFICATION.md) (d16fbea) | [confirmatory_20261122](prism-repro/docs/revision/confirmatory_20261122/README.md) |
| CAL-DEV | Groups A/B with corrected start-up: measured per-size execution scaling, cross-stage dependence 0.998, start-up 6 s truncated at 10 s | 92e3e68 + [candidate_exec_p2.patch](prism-repro/docs/revision/p2_dependence_20261124/candidate_exec_p2.patch) | Linux; event-level closed loop | development traces 101-105 only; **not confirmatory**; a calibrated held-out run is not part of this revision | [calibrated_build_20261125](prism-repro/docs/revision/calibrated_build_20261125/RUN_PLAN.md) |
| AWS | memcal-1 (22 Nov 2026), live integration run (21 Nov), R6.1 paired live replay (25 Nov) | harnesses [aws_pipeline](prism-repro/aws_pipeline/README.md), [aws_measurement](prism-repro/aws_measurement/README.md); R6.1 used the frozen controller at 92e3e68 | AWS Lambda and Step Functions, us-east-2 | R6.1: one thinned trace-week, record-level outcomes; a demonstration, not a compliance or cost validation | [memcal-1](prism-repro/docs/revision/aws_memcal_20261122/RESULTS.md), [integration](prism-repro/docs/revision/aws_live_integration/RESULTS.md), [R6.1](prism-repro/docs/revision/r61_live_run_20261125/README.md); R6.1 provisioned-concurrency requests in CloudTrail, sanitized: [cloudtrail_pc_20261125](prism-repro/docs/revision/r61_live_run_20261125/sanitized_summaries_20261128/cloudtrail_pc_20261125.md) |

## Results

| Result | Set | Output files | Reproduce |
|---|---|---|---|
| Tables V-XIII [IV-XII] and Supplementary Tables S2-S15 | REGEN-WIN | [table map](prism-repro/docs/reproducibility/tables/REGEN-WIN_table_map.md), pointing to each file in [outputs/tables](prism-repro/docs/revision/regeneration_20261122/outputs/tables/) | From completed rows, no simulation: [README, command 3](prism-repro/docs/reproducibility/README.md). Full rerun: [regeneration README](prism-repro/docs/revision/regeneration_20261122/README.md) |
| Fig. 2 and Figs. S2-S5 | REGEN-WIN | drawn by [make_figs.py](prism-repro/scripts/revision/figures/make_figs.py) from [figure_inputs_regen_win](prism-repro/docs/reproducibility/figure_inputs_regen_win/) | `python docs/reproducibility/make_figures.py <new dir>` ([script](prism-repro/docs/reproducibility/make_figures.py)) |
| Table IV (new) and Fig. S6: C1-C3 | CONF-C1C3 | [run/tables](prism-repro/docs/revision/confirmatory_20261122/run/tables/); summary [TR1](prism-repro/docs/reproducibility/tables/TR1_confirmatory_C1_C3.md) | From saved weeks: [README, command 4](prism-repro/docs/reproducibility/README.md). Rerun (simulation): [closed_loop_confirmatory.py](prism-repro/scripts/revision/closed_loop_confirmatory.py) `run` |
| Table XV (new), Table S19 and Fig. S7: measured constants | CAL-DEV | [p3_results.json](prism-repro/docs/revision/calibrated_build_20261125/p3_results.json); summary [TR2](prism-repro/docs/reproducibility/tables/TR2_calibrated_development.md) | [make_tables.py](prism-repro/docs/reproducibility/make_tables.py), [make_figures.py](prism-repro/docs/reproducibility/make_figures.py). Rerun (simulation, Linux): [RUN_PLAN.md](prism-repro/docs/revision/calibrated_build_20261125/RUN_PLAN.md) |
| Table XIV (new) and Tables S16-S18: AWS measurements, the R6.1 replay, cost evidence by kind | AWS | [TR3](prism-repro/docs/reproducibility/tables/TR3_r61_live_replay.md), [TR4](prism-repro/docs/reproducibility/tables/TR4_aws_measurements.md), [TR5](prism-repro/docs/reproducibility/tables/TR5_cost_evidence_by_kind.md); 25 Nov 2026 billing export, sanitized: [billing_export_20261125](prism-repro/docs/revision/r61_live_run_20261125/sanitized_summaries_20261128/billing_export_20261125.md) | `make_tables.py`, from the committed aggregates and the sanitized summary. Raw records and exports are not published ([DATA_SOURCES, section 5](prism-repro/docs/reproducibility/DATA_SOURCES.md)) |
| Table S20: platform sensitivity | submitted v1, REGEN-WIN, REGEN-LINUX | [TR6](prism-repro/docs/reproducibility/tables/TR6_platform_sensitivity.md) | `make_tables.py` |
| Table S21: warm-started calibration offset (exploratory) | 31b8c50, Windows | [summary.txt](prism-repro/docs/revision/provisional_split/summary.txt) | [provisional_split README](prism-repro/docs/revision/provisional_split/README.md) (simulation) |
| Table S22: within-run execution-time shift, R2.7 (exploratory; one sensitivity post hoc) | 3edc386, Windows | [r27_shift_20261124](prism-repro/docs/revision/r27_shift_20261124/README.md) | the same README (simulation) |
| Table XIII [XII]: Huawei real-arrival replay | REGEN-WIN | [R1_real_traces.md](prism-repro/docs/revision/regeneration_20261122/outputs/tables/R1_real_traces.md) | inputs [data/real](prism-repro/data/real/README.md) (CC BY 4.0) |
| Graphical abstract: plotted values | REGEN-WIN | [GA_inputs.csv](prism-repro/docs/reproducibility/tables/GA_inputs.csv) | `make_tables.py` |

## Studies cited in the replies

| Reply | Evidence | Scope |
|---|---|---|
| R1.1, operator margin | [margin_r11_fresh](prism-repro/docs/revision/margin_r11_fresh_20261124/README.md), [margin_r11_branch50](prism-repro/docs/revision/margin_r11_branch50_20261124/README.md) | schedules from the first submission's code; open loop; pre-calibration; the 50% branch is unvalidated |
| R2.4 and R7.2, violation severity and modelling factors | [event_severity_resumed](prism-repro/docs/revision/event_severity_resumed_20261122/README.md) | the first submission's schedules, replayed with the event-level code of 78ba419 |
| R2.6, R3.7 and R7.4, MemAdapt-q90 | [memadapt](prism-repro/docs/revision/memadapt/README.md) (a396f40), with C3 (CONF-C1C3) and CAL-DEV | as in each set |
| R2.9, less-structured traces | [less_structured_r29](prism-repro/docs/revision/less_structured_r29_20261122/README.md); inputs [huawei2025_region2_r29](prism-repro/data/real/huawei2025_region2_r29/README.md) | ee24766, Windows |
| R2.19, R4.7 and R5.M4, grid edges | [grid_studies](prism-repro/docs/revision/grid_studies/README.md) | 78ba419, Windows |
| R1.2 and R5.M2, initialisation time against memory | [init_vs_memory](prism-repro/docs/revision/init_vs_memory/rerun_20261121-163247/README.md) | external data ([DATA_SOURCES](prism-repro/docs/reproducibility/DATA_SOURCES.md)) |
| R3.2, comparators from the literature | [hybrid_histogram](prism-repro/docs/revision/hybrid_histogram_r32_20261122/README.md), [hybrid_reproduction](prism-repro/docs/revision/hybrid_reproduction_r32_20261124/README.md), [optscaler](prism-repro/docs/revision/optscaler_r32_20261124/README.md) | the hybrid policy was not reproduced against the prespecified criteria |
| R2.14, billing | [billing_r214](prism-repro/docs/revision/billing_r214_20261123/README.md), [billing_r214_pc](prism-repro/docs/revision/billing_r214_pc_20261124/README.md), [reconciliation](prism-repro/docs/revision/billing_reconciliation_20261124/README.md) (22 Nov 2026 export), [billing_export_20261125](prism-repro/docs/revision/r61_live_run_20261125/sanitized_summaries_20261128/billing_export_20261125.md) (25 Nov 2026 export, sanitized) | estimates; the 25 Nov difference between saved REPORT records and billed requests is not reconciled; the final charges are open |
| R1.2, R1.3, R4.3, R5.M2 and R7.5, activation lag and initialization-scaling sensitivity (final numbering: Supplementary Section S26, Tables S30-S31) | outputs: [sensitivity](prism-repro/docs/revision/sensitivity/summary.txt), committed at a4187f7. Code revision of the run: efcfd12, recorded in [run.log](prism-repro/docs/revision/sensitivity/run.log); the folder does not exist at efcfd12. | pre-calibration; Windows |
| R2.2 and R5.M1, closed-loop development studies | [closed_loop_kappa](prism-repro/docs/revision/closed_loop_kappa_20261124/README.md), [closed_loop_families](prism-repro/docs/revision/closed_loop_families_20261124/README.md) | traces 101-105 |
| R2.8 and R4.8, calibration inputs and cross-stage dependence | [calibration_final](prism-repro/docs/revision/calibration_final_20261124/README.md), [p2_dependence](prism-repro/docs/revision/p2_dependence_20261124/README.md) | development evidence |

## Environment and checks

- **Packages:** [requirements.txt](prism-repro/requirements.txt). The exact versions of the revision checks are in
  [label_fix_20261123/env](prism-repro/docs/revision/label_fix_20261123/env/) (Windows and Linux freeze files).
- **Tests:** `python -m unittest discover -s tests -v` (128 tests passed on 25 Nov 2026).
  - The harness suites `aws_pipeline/tests` (81) and `aws_measurement/tests` (33) passed too. They use fakes and make
    no AWS call.
  - So did the `scripts/revision` tests (18).
- **Checksums and documented exceptions:** [README, Verify](prism-repro/docs/reproducibility/README.md).
- **Data, licences and unpublished inputs:** [DATA_SOURCES.md](prism-repro/docs/reproducibility/DATA_SOURCES.md).

## Limits

- **Assumed constants:** REGEN-WIN and CONF-C1C3 use assumed platform constants. Measured constants enter only CAL-DEV,
  which is development evidence on traces 101-105.
- **Live AWS evidence:** one trace-week, with record-level outcomes. The window-level SLA, burst overflow and
  application start-up were not measured live. Charges attributable to the runs are not final.
- **Platform dependence:** forecast-driven results depend on the platform (TR6). Each set names the platform it was
  produced on.
- **Licence:** the code and the project's own data have no licence yet ([LICENSE_PENDING.md](prism-repro/LICENSE_PENDING.md)).
  Third-party data keep their CC BY 4.0 licences.
