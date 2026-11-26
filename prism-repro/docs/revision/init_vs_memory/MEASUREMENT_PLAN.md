# Measurement plan: initialisation vs memory on PRISM's own stages (R1.2, R2.8, R3.1, R4.3, R5.M2, R6.2)

**Draft, 21 Nov 2026. Not run; no AWS resource has been created.** It is designed for the applied concurrency quota
of 10, with on-demand invocations only. It follows `notes/manuscript_proposals.md` section G and
`prism-repro/REPRODUCE.md` section 6.

## Why

The external analysis (`rerun_20261121-163247/RESULTS.md`) separates three quantities:

- **Lambda-reported initialisation** is nearly flat with memory in six 2020 benchmarks, including the
  large-package one.
- **The cold-minus-warm penalty** falls with memory in five of six.
- **Huawei's provisioning delay** is a different process, and its results are mixed across regions.

The data cannot say which of these Eq. (3) represents for PRISM, because that depends on where PRISM's stages do
their start-up work. Only PRISM's own stages can settle it.

## Prerequisite

Nothing in the repository deploys a function. The four stage functions have to be written and deployed first:

- **What they are:** the pipeline's real code and dependencies, with the start-up work where production code would
  put it.
- **What to record per stage:** runtime and version, architecture, region, deployment package size, and what runs
  at module scope versus inside the handler.

## Design (on demand, at most 8 concurrent invocations, leaving 2 of the quota of 10 as headroom)

| Item | Setting |
|---|---|
| Memory sizes | 512, 1024, 2048, 3008 MB (`mem_options`); add 1536 MB only if decision D6 adopts five sizes |
| Cold samples | per stage and size, at least 200 with a reported Init Duration; target 230 to absorb the up-to-13% loss seen in SeBS |
| Warm samples | per stage and size, about 1,000, on environments already warmed |
| Forcing cold starts | change the function configuration (for example an environment variable) before each batch; a record counts as cold only if its REPORT line has Init Duration |
| Batches | at most 8 concurrent invocations each; at least 25 batches per stage and size so batch-level intervals are meaningful |
| Order | sizes randomised within each block; blocks spread over at least 3 days and different times of day (in SeBS a later day posed as a memory effect); one region, one account |
| Volume | 4 stages x 4 sizes x (230 cold + 1,000 warm) = about 19,700 invocations |

**What is recorded for each invocation:**

- **Client:** synchronous invocation from a client in the same region, with send and receive timestamps
  (end-to-end time) and the request ID.
- **Lambda, from the CloudWatch REPORT line:** `Init Duration` (cold only), `Duration`, `Billed Duration`,
  `Memory Size`, `Max Memory Used`.
- **Function:** timestamps at handler entry and at the end of any first-call setup.

Records are joined on the request ID. Missing REPORT fields are counted per cell, and the counts are reported.

**Derived per stage and size:**

- `I` = median Init Duration.
- `P` = median cold end-to-end time minus median warm end-to-end time (the cold-minus-warm penalty).
- `X` = median cold Duration minus median warm Duration (first-invocation excess inside the handler).
- `R = P - I - X`: environment creation and other time Lambda does not report.

Uncertainty comes from a bootstrap over batches. The trend is the slope of each quantity on log memory over 512-3008
MB, as in `rerun_20261121-163247/r12_init_vs_memory.py`. Warm `Duration` per size also gives the warm service-time
inputs (`warm_mean_1024`, `exec_shape`, and the Eq. (2) `nonscaling` share).

## How the results feed Eq. (3)

In the model, initialisation is the time a new environment is occupied before it serves the request, so it
corresponds to `P` and not to `I` alone. `I`, `X` and `R` are reported separately so the text can say what Eq. (3)
represents.

The rule below is stated before any data, compared against Eq. (3)'s slope of -0.273 over 512-3008 MB. It applies
per stage and then pooled.

| Result | Decision |
|---|---|
| Interval for `P` contains -0.273 | keep Eq. (3), refit `init_mean_1024` and `init_nonscaling` |
| Interval below 0 but excluding -0.273 | keep the direction; refit the non-scaling share, which changes Eq. (3)'s shape |
| Interval contains 0 and excludes -0.273 | use `init_scaling = "constant"`, or `"measured"` |
| Interval above 0 | use `"inverted"` or `"measured"`; narrow the RQ4 memory claims |

In every case `init_mean_measured` is filled with the per-size means of `P`, which the existing `"measured"` mode
takes without any code change. The R1.2 sweep is then re-centred on it.

## Blocked under the current quota (separate measurements, not part of this campaign)

- **Provisioned-concurrency activation lag:** the time from a provisioned-concurrency configuration change until
  the environments are ready and serving.
- **Burst overflow beyond provisioned capacity:** where requests above the provisioned level go, and their cold-start
  delay.

Both need provisioned concurrency, which cannot be configured at the applied quota of 10 (proposal G; the increase
to 1,000 was denied on 20 Nov 2026). `lag_min` and the loss routing stay simulated, and the text must say so.

## Evidence check of the saved analysis (21 Nov 2026)

- **Checksums:** all 14 files in `rerun_20261121-163247/` match `SHA256SUMS`, and every figure cited in
  `notes/dispositions.md` was re-read from its CSVs.
- **Gap 1, wrong custom-pool count:** `RESULTS.md` gives the custom-pool event count as 25,909. The saved
  `huawei_quality.csv` gives **225,605** (R1 8,885; R2 199,696; R4 15,516; R5 1,508). The CSV is authoritative;
  `RESULTS.md` was left unedited because it is a checksummed output.
- **Gap 2, "first-call work" is an inference:** the saved tables do not split the cold-minus-warm penalty into
  first-invocation execution and environment creation. The README's "most of the cold cost is first-call work" is
  therefore an inference that the saved outputs do not verify. This plan measures `X` and `R` to settle it.
