# Licence — to be chosen by the authors

No licence file is included yet. The three authors have agreed to release this code with the paper
(verbal agreement of all three authors, recorded on 30 Oct 2026); the choice of licence and archive
is still open. Repository (chosen 31 Oct 2026, private during review): https://github.com/rajneeshshukla-stack/PRISM-Serverless-Pipelines. Punit Gupta joined as
fourth author after this record; his agreement to the release should be recorded as well.

Until a `LICENSE` file is added, default copyright applies and others may not reuse the code.

Before publishing: choose a licence (permissive licences such as MIT, BSD-3-Clause or Apache-2.0 are common for
research code), add `LICENSE`, add the repository URL and archive DOI to `CITATION.cff` and to the paper's Data and
Code Availability statement, and regenerate `CHECKSUMS.sha256` (`python scripts/build_manifest.py --verify` only
verifies; regenerate the checksums with the release tooling, not with `build_manifest.py` without `--verify`).

Third-party components are dependencies only (not vendored): NumPy, SciPy, pandas, scikit-learn, matplotlib
(BSD-style licences) and tabulate (MIT); see `THIRD_PARTY_NOTICES.md`.
