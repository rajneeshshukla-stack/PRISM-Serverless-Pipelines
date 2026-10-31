# Pricing provenance

| Quantity | Value used | Source |
|---|---|---|
| On-demand duration | 1.66667e-5 USD/GB-s | Manuscript §3.4 (stated as published x86 rates "at the time of writing" in a major US region) |
| Provisioned-concurrency fee | 4.1667e-6 USD/GB-s | Manuscript §3.4 |
| Provisioned duration | 9.7222e-6 USD/GB-s | Manuscript §3.4 |
| Requests | 2e-7 USD/request | Manuscript §3.4 |

**Verification status.** These values were *not* re-verified against the live AWS price list in this session (the pricing page was not fetched). They are used exactly as stated in the manuscript so that the reimplementation evaluates the same cost model. Any reuse should check current regional prices.

**INIT-phase billing (manuscript assumption (i)).** Checked on 2026-10-29 against the AWS Compute Blog post "AWS Lambda standardizes billing for INIT Phase" (https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/). It states that, effective 1 August 2025, INIT-phase duration is billed for all function configurations at the Region's standard on-demand duration rate; previously it was unbilled only for on-demand invocations of ZIP-packaged functions on managed runtimes. This supports billing initialisation at π_od, as the manuscript and this code do. The same post describes a 10-second maximum for the INIT phase; the simulators here do not cap initialisation time (mean 6 s at 1024 MB, 7.8 s at 512 MB, log-normal tail), which is a modelling simplification.

**Historical vs current conditions.** All costs reported in this repository are simulated with the fixed price list above; they are not invoices, measurements or estimates of any real deployment.
