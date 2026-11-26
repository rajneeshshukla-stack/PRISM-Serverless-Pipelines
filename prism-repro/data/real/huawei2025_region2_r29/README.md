# Huawei Public Cloud Trace 2025, Region 2: ten derived arrival traces (R2.9)

**What these files are.** Ten per-minute arrival series, `r2_00.csv` to `r2_09.csv` (columns `minute,count`; 40,320
minutes, i.e. 28 days, each). They are the inputs of the less-structured-workload study for reviewer comment R2.9
(`../../../docs/revision/less_structured_r29_20261122/`) and of the R3.2 hybrid-histogram check
(`../../../docs/revision/hybrid_histogram_r32_20261122/`).

**Same files as used.** For each file, the SHA-256 of its counts as little-endian int64 equals `counts_sha256` in
`../../../docs/revision/less_structured_r29_20261122/selection_public.json` (10 of 10, checked 25 Nov 2026).

## Source and licence

- **Source:** the *Huawei Public Cloud Trace 2025* of Huawei's Systems Infrastructure Research (SIR) lab,
  https://github.com/sir-lab/data-release (`README_data_release_2025.md`).
- **Paper:** "Serverless Cold Starts and Where to Find Them", EuroSys 2025, arXiv:2410.06145.
- **Licence:** the upstream repository states "Licensed under the Creative Commons Attribution 4.0 International
  (CC BY 4.0) license" (checked 25 Nov 2026). These derived files are shared under the same licence,
  https://creativecommons.org/licenses/by/4.0/.

## Changes made

The rule was fixed in `../../../docs/revision/less_structured_r29_20261122/PLAN.md` before any trace was selected. The code is
`scripts/revision/less_structured_region2.py --select`.

1. **Input:** Region 2 per-minute `requests`, files `R2/requests/day_00.csv` to `day_27.csv` of the Region 2 time-series
   archive (downloaded as `R2-minute-metrics.zip`). Their SHA-256 are in `selection_public.json` under `source_files`.
2. **Eligible functions:** mean at least 600 requests per minute, and at least one request in at least 95% of the
   minutes of the 28 days.
3. **Selection:** the 10 eligible functions with the smallest `sha256(funcID)`. Function IDs are not included here.
4. **Thinning:** each series is thinned binomially to a mean of 600 requests per minute, `Binomial(x, 600 / mean(x))`,
   with NumPy `default_rng(20261122 + rank)`.
5. **Output:** `r2_<rank>.csv`, with the minute index starting at 0.

**When published.** The R2.9 plan kept these files local because the downloaded dataset README states no licence.
The CC BY 4.0 statement in the upstream repository was confirmed on 25 Nov 2026, and the files were then published
unchanged.

## Verify

Run `sha256sum -c SHA256SUMS` in this folder. `.gitattributes` keeps the files byte for byte on every platform.
