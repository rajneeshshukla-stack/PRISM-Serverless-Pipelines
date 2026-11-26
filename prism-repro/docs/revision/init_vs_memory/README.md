# Initialisation time vs memory (R1.2)

The reference run is **`rerun_20261121-163247/`**: its README, `RESULTS.md`, the outputs, `SHA256SUMS`, and the
exact script that produced them.

The CSVs, `run.log` and `environment.json` in this folder come from an earlier, preliminary run, kept unchanged.
That run dropped Huawei pools named `custom-<cpu>-<mem>` as unparsed and had no same-day sensitivity rows.
Every row and column it shares with the reference run is identical.

`r12_init_vs_memory.py` here is the current script, identical to the reference run's copy (SHA-256 `ce47fa52...`).
The preliminary outputs were produced by an earlier version of it.

`MEASUREMENT_PLAN.md` drafts the on-demand AWS campaign on PRISM's own stages. It also records two gaps in the
reference run's `RESULTS.md`: the custom-pool count is 225,605 per `huawei_quality.csv`, not 25,909; and the
"first-call work" reading is not verified by the saved tables.

**Checksums.** The run wrote its CSVs and logs with CRLF line endings on Windows, and Git commits text with LF
(`core.autocrlf=true`), so the reference run has two lists:

- `rerun_20261121-163247/SHA256SUMS` hashes the files as written; a Windows checkout verifies against it.
- `rerun_20261121-163247/SHA256SUMS.lf` hashes the committed LF content, for any other checkout.

The lists differ only in the 11 files Python wrote. Each committed file equals the written one after CRLF->LF.
