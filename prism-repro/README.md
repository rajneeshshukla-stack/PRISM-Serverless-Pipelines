# PRISM — code and results for the paper

**Joint Cost-SLA Provisioning of Concurrency and Memory for Serverless Data Pipelines: A Chance-Constrained Formulation and a Simulation Study under Workload Shift**
R. Shukla, E. Ramasamy, V. Shukla, P. Gupta (manuscript V2.8, submission candidate V11; not yet published).

> **Status: RELEASE CANDIDATE 2.2.0rc1 (30 Oct 2026). Not released.** The authors have agreed to release this
> code with the paper. Repository: https://github.com/rajneeshshukla-stack/PRISM-Serverless-Pipelines
> (private during review). The licence and the archive (DOI) are still to be chosen (`LICENSE_PENDING.md`). Until a licence is added, default copyright applies.

## What this is

The implementation of PRISM, all baselines, both simulators (fast per-minute and event-level) and the
synthetic workload generator that produced **every result in the paper**, together with the experiment and
analysis scripts, the raw per-run results and run logs, the evaluation protocol with its change log, 48 automated
tests, SHA-256 checksums of every file, and a separate patch (`patches/`) that corrects three code defects found
after the runs (paper, Section VI-G and Supplementary Section S1). The stored results come from the code
without the patch.

**Provenance.** At the direction and under the supervision of the authors, the code was implemented by the
generative AI system Claude (Anthropic) from the authors' specification, and the experiments were run with it; the
authors reviewed, tested, and verified the code and results. The paper's Acknowledgment discloses the use of AI. An
earlier prototype implementation, which produced the results of an earlier draft of the paper, is **not**
included; Section V-E of the paper states where its results differ from these. Some file headers and the
module docstring of `src/prism_repro/__init__.py` still use the working title of the manuscript from which
the code was written and call the code an "independent reimplementation"; they were left unchanged so that the
recorded source hash stays traceable (`PROVENANCE.md`).

**Data.** The main workloads are synthetic and are regenerated deterministically from the seeds (evaluation
101–105; development 7). Experiment R1 (post hoc) replays five real per-minute arrival traces derived from the public
Huawei Private 2023 trace (CC BY 4.0; anonymized request counts, no personal data) in `data/real/`; see
`docs/DATA_CARD.md` §4. Run it with `python experiments/run_real_traces.py` and analyze with
`python scripts/revision/analyze_real_traces.py` (about 6 minutes on one core).
Experiment R2 (post hoc, synthetic) runs the calibrated-quantile rules in the memory regimes of Table IX:
`python scripts/revision/r2_quantprov_memory.py . results/raw/R2/r2_seed101.jsonl 101` (and seed 102), then
`python scripts/revision/analyze_r2.py`.

## Reproduce

Run from the repository root.

| Step | Command | Notes |
|---|---|---|
| Environment | `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` | Pinned versions (Python 3.12.3). Exact reproduction of the forecast-driven runs needs exactly these versions (paper, Supplementary Section S1). |
| Tests | `python -m unittest discover -s tests -v` | 48 tests (52 with the patch applied; `patches/README.md`) |
| Tables of E1–E11 | `python scripts/analyze.py` | Regenerates `results/tables/` and `results/summary.json` from `results/raw/` |
| Revision analyses | `python scripts/revision/analyze_e8.py . results/raw/E8/rows.jsonl`; `python scripts/revision/analyze_e12.py results/raw/E12`; `python scripts/revision/posthoc_analysis.py .`; `python scripts/revision/pc_billing_bounds.py .`; `python scripts/revision/matched_compliance_pertrace.py .` | Outputs in `results/tables/revision/` |
| Fig. 2 and Suppl. Figs. S2–S5 | `python scripts/revision/figures/make_figs.py . <out_dir>` | Output files keep an earlier numbering (`fig3`–`fig7`) |
| Fig. 1 and Suppl. Fig. S1 (diagrams) | `python scripts/revision/figures/make_diagrams.py <out_dir>` | |
| Corrective patch (optional) | `patch -p1 < patches/m12_m5_corrections.patch` | Corrects the three defects of `KNOWN_ISSUES.md`; changes no stored result. Its paired diagnostic is in `patches/diagnostic/` |
| Verify files | `python scripts/build_manifest.py --verify` | Checks `CHECKSUMS.sha256`. Do **not** run it without `--verify`: that would overwrite `RUN_MANIFEST.json`, which records the original runs. |
| Version checks | `scripts/revision/version_check/` | Re-simulation under other library versions; source equivalence after comment-only changes |
| Post hoc fixed-memory comparison (E4b) and level-choice diagnostic | `python scripts/revision/e4b_fixed_memory.py . results/raw/E4b/e4b_seed101.jsonl 101` (likewise seed 102, and `e4b_ondemand.py`, `e4b_prism_eps.py`); `python scripts/revision/analyze_e4b.py results/raw/E4/rows.jsonl <out.json> results/raw/E4b/*.jsonl`; `python scripts/revision/level_choice_diagnostic.py . <out.json>` | Run under scikit-learn 1.9.1 (30 Oct 2026); outputs in `results/raw/E4b/` and `results/tables/revision/` |
| Re-run experiments | `bash scripts/run_all.sh`, or `python experiments/run_experiments.py --exp E1 --seeds 101 102 103 104 105` | About 1.5–2 h for E1–E11 on one core (`RUN_MANIFEST.json`: 5,245 s of run time, 23:12–00:58 UTC), plus about 2.9 h for E8 and 2.1 h for E12 |

## Where the paper's results come from

| Paper | Raw results | Generated table |
|---|---|---|
| Table IV (forecast coverage) | `results/raw/E2` | `results/tables/T4_forecast_coverage.md` |
| Tables V, VI; Suppl. Tables S2–S4 | `results/raw/E1` | `T5_test_weeks.md`, `T6_paired_*.md`, `E1_selected_parameters.md`, `E1_aggregate_all_test_weeks.md` |
| Table VII, Fig. 2 (matched compliance, post hoc) | `results/raw/E1` | `results/tables/revision/posthoc_matched_compliance.txt`, `matched_compliance_pertrace.txt` |
| Table VIII (ablations) | `results/raw/E3` | `E3_ablation_conformal_oracle.md` |
| Table IX (memory regimes) | `results/raw/E4` | `T8_memory_regimes.md` |
| Table X (fast vs event level) | `results/raw/E9` | `T10_fast_vs_event.md`, `T10b_prism_vs_predhead_fidelity.md`, `T11_overflow_estimates.md` |
| Table XI (event-level retuning, post hoc) | `results/raw/E12` | `results/tables/revision/E12_event_level_retuning_analysis.txt` |
| Suppl. S5–S9 | `results/raw/E5`, `E11`, `E8`, `E7`, `E1`/`E3`/`E10` | `T9_sensitivity.md`, `E11_erlangb.md`, `T18_*`, `T19_*`, `T20_feature_ablation.md`, `T13_infeasibility.md`, `T14_hysteresis.md`, `T15_severity.md`, `E10_overhead.md` |
| Suppl. Table S5 (caps) | `results/raw/E6` | `E6_caps.md` |
| Billing bounds (Section III-D) | `results/raw/E1` | `results/tables/revision/pc_billing_bounds.txt` |
| Table IX, headroom at 2048 MB; Suppl. Table S14 (post hoc) | `results/raw/E4b` | `results/tables/revision/E4b_fixed_memory_summary.json` |
| Section VII-B and Suppl. S9, level-choice diagnostic (post hoc) | re-run of E1 configurations | `results/tables/revision/level_choice_diagnostic.json` |

`scripts/run_all.sh` reproduces the original chain, in which E8 ran for traces 101-103 only. The E8 completion
(`python experiments/run_experiments.py --exp E8 --seeds 104 105`) and E12
(`python scripts/revision/e12_event_retune.py . results/raw/E12 101 102 103 104 105`) were run later
(`RUN_MANIFEST_REVISION.json`). `scripts/analyze.py` also redraws `results/figures/`; image files depend on the
matplotlib version and fonts, so after running it `build_manifest.py --verify` may report those files as changed
while every table regenerates byte for byte. `make manifest` rewrites `RUN_MANIFEST.json`; use it only when
recording new runs (`make all` verifies instead).

## Known issues

`KNOWN_ISSUES.md` lists the limitations that the paper discloses and three code defects found after the runs
(two first-epoch edge cases; warm pool kept across memory changes). The program code here is the one that
produced the reported results; the corrections are a separate patch (`patches/`), and a paired re-simulation of
435 stored configurations with and without the patch changed no violating-window rate or target outcome and
changed cost by at most USD 0.21 per week.

## Licence and citation

Licence: **to be chosen by the authors** (`LICENSE_PENDING.md`). Third-party dependencies:
`THIRD_PARTY_NOTICES.md`. Citation: `CITATION.cff` (to be completed with the venue and DOI on publication).
