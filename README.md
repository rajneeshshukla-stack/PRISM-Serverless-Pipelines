# PRISM-Serverless-Pipelines

Code and reproducibility artifacts for the paper

**Joint Cost–SLA Provisioning of Concurrency and Memory for Serverless Data Pipelines: A Chance-Constrained Formulation and a Simulation Study under Workload Shift**
R. Shukla, E. Ramasamy, V. Shukla, P. Gupta (submitted to IEEE Access; not yet published).

**Status:** release candidate 2.2.0rc1 — private during peer review; to be made public with the article. No licence has been chosen yet (`prism-repro/LICENSE_PENDING.md`).

- `prism-repro/` — PRISM, all baselines, both simulators, the synthetic workload generator, experiment and analysis scripts, stored raw results, 48 automated tests, `CHECKSUMS.sha256`, and the separate correction patch. Start with [`prism-repro/README.md`](prism-repro/README.md).
- `CODE_PACKAGE_README.txt` — package notes for this release candidate.

All workloads are synthetic and are regenerated deterministically from the seeds listed in the paper's Supplementary Table S1; no real-world or personal data are included.
