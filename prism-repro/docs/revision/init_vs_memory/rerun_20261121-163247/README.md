# Initialisation time vs memory from external data (R1.2; informs R2.8, R3.1, R4.3, R5.M2, R6.2)

**Exploratory, post hoc, external historical data; not a PRISM measurement, and not a substitute for measuring
PRISM's own pipeline.** It was run on one Windows machine and makes no cross-platform claim. Reviewer statuses are
unchanged. The compact table is in `RESULTS.md`.

## Reproduce

```
python -I r12_init_vs_memory.py "<repo>/additional data" <out_dir>
```

- **Inputs:** the 80 inputs (74 SeBS JSON files, 5 Huawei zips, 1 runtime table) are checked against
  `additional data/MANIFEST.tsv` before use. Raw data is read in place and never copied into the repository.
- **Determinism:** seed 20261121, 2,000 SeBS and 1,000 Huawei bootstrap replicates.
- **Environment:** in `environment.json`; run time about 95 s.
- **Checksums:** `SHA256SUMS` lists every output in this folder.

This folder is the reference run. The CSVs one level up come from an earlier run of the same analysis, preserved
unchanged. That earlier run dropped the `custom-<cpu>-<mem>` Huawei pools as unparsed and had no same-day
sensitivity rows. Every row and column the two runs share is identical.

## What the results support for R1.2

1. **Eq. (3)'s size of effect is not supported for Lambda's reported init phase.** On AWS Lambda (2020) the
   reported init duration changes little with memory:
   - Medians are 0.01-0.19 s, and slopes run from -0.11 to +0.03, against Eq. (3)'s -0.27.
   - The large-package benchmark 411 is flat.
   - Of the two clear decreases, 503's disappears when only same-day sizes are kept. 120 and 311 decrease by about
     3% from 512 to 3008 MB.
   - Eq. (3)'s ratio lies inside the interval in only 2 of 31 cells (503 at 1536 and 2048 MB), and those two are
     day-confounded.
   - The one increase (Node.js thumbnailer) is not robust to the same-day check.
   - On this measure the data sit closest to PRISM's "constant" case.
2. **The cold-start penalty that includes first-call work falls with memory, at least as steeply as Eq. (3).** The
   cold-minus-warm client time decreases in 5 of 6 benchmarks (slopes -0.29 to -0.68), and is inconclusive for the
   Node.js thumbnailer.
   - The two measures disagree. In these benchmarks most of the cold cost sits in work done at the first
     invocation, not in Lambda's reported init phase. (For 411 the penalty is 9.67 s at 1024 MB against an init
     duration of 0.135 s.)
   - Which measure corresponds to PRISM's "initialisation" depends on where a pipeline does its start-up work. That
     is an author decision, and ideally a measurement of PRISM's own stages.
3. **No AWS evidence that init grows with memory,** including for the large-package benchmark (the reviewer's
   concern).
4. **The Huawei production cross-check is inconsistent across regions:**
   - **R1:** decreasing within functions (15 functions).
   - **R2:** inconclusive, leaning increasing (9 functions); inconclusive by runtime.
   - **R3-R5:** no within-function evidence.
   - Cross-sectional medians are confounded by function and runtime.

## What can also inform other comments (no status change)

- **R2.8, R4.3:**
  - **Initialisation constant:** Lambda's reported init (0.01-0.18 s at 1024 MB) is far below PRISM's assumed 6 s
    mean. Cold-minus-warm penalties are 0.6-1.0 s for five benchmarks and 9.7 s for the large-package one.
  - **Huawei:** standard-pool cold starts have function-weighted medians of 0.26-4.6 s at 1024 MB by region
    (R3 0.26, R5 0.32, R2 0.62, R4 1.12, R1 4.61). Custom pools have event medians of 10.4-27.2 s.
  - **Limits:** these inform the plausible range for the init constant, but none is PRISM's pipeline.
- **R3.1, R5.M2:** the Eq. (3) check above.
  - The data argue for running and reporting both the "constant" case (reported init) and an Eq. (3)-or-steeper
    case (first-call penalty).
  - They give no support for the "inverted" (growing) case on AWS.
  - The lag is not addressed by any of these data.
- **R6.2:** measured cold-start durations (SeBS) and production cold-start delays and composition (Huawei).
  Activation lag, concurrency on AWS and current billing remain unmeasured.

## Limits

- **Historical benchmarks:**
  - SeBS ran in November 2020 in one region (us-east-1), on Python 3.7 and Node.js 10.x (both since retired), with
    six benchmark functions.
  - The Lambda platform, its init behaviour and its billing (init billing since 2025) have changed since.
  - Memory sizes were run minutes apart in sequence, and some on a later day, so time effects cannot be fully
    separated (see the same-day rows).
  - 4-6 batches per size make the intervals approximate.
- **Field definitions:**
  - Lambda's reported init excludes environment creation.
  - Huawei's field is a platform provisioning delay whose coverage of runtime and user init is not documented.
- **Cross-platform:**
  - Huawei is a different platform; its memory pools also fix CPU, and both are user choices, so cross-sectional
    comparisons are confounded.
  - Within-function comparisons exist only in R1 and R2.
  - R2's runtime table lists `http` for 72 functions; treated as unknown.

## Corrections to the data audit (`additional data/README.md`, not edited)

- **SeBS runtimes:** the runtimes recorded with the results are Python 3.7 and Node.js 10.x, not Python 3.6. The
  experiment configs say 3.6.
- **Huawei memory range:** memory limits reach 10240 MB, not 4096.
- **Huawei custom pools:** pools named `custom-<cpu>-<mem>` exist alongside the standard `poolNN-<cpu>-<mem>`.

## Provenance and licensing (unresolved)

- **SeBS:** artifact DOI 10.5281/zenodo.5209001. There is **no license file** in the downloaded artifact; check
  the Zenodo record.
- **Huawei Public Cloud 2025:** arXiv 2410.06145. There is **no license** in the downloaded README; check the
  sir-lab/data-release repository terms.
- **Distribution:** until both are resolved, only these derived aggregate tables are in the repository. Raw data
  stays in `additional data/` (local, untracked).
