# R2.14(a): provisioned-concurrency billing components, implemented only where AWS states the rule (24 Nov 2026)

No AWS call. `src/` is unchanged. The verified on-demand rule of `../billing_r214_20261123/billing_rules.py` is reused
unchanged; its 5 tests still pass and its `SHA256SUMS` still verifies.

**Sources, read 24 Nov 2026** (public pages; the examples are priced in US East, N. Virginia; Ohio prices are not
shown there):
- https://aws.amazon.com/lambda/pricing/
- https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html

## 1. Components

| Component | AWS's rule (quoted) | Status |
|---|---|---|
| **Capacity** (configured concurrency) | "calculated from the time you enable it on your function until it is disabled, rounded up to the nearest five minutes"; "You pay for the amount of concurrency you configure, and for the period of time you configure it"; "$0.0000041667 per GB-s" | **Implemented** (`capacity_gb_s`, `capacity_charge`) |
| **Activation timing** | Billing runs "from the time you enable it", so the minute or two before READY (lambda-concurrency.html: "doesn't come online immediately") is billed | **Implemented** (billing starts at enabling; test `test_five_minute_rounding_and_activation_is_billed`) |
| **Invocations on provisioned environments** | "Compute charges while Provisioned Concurrency is enabled ... $0.0000097222 per GB-s"; "Duration is calculated from the time your code begins executing until it returns or otherwise terminates, rounded up to the nearest 1ms"; requests "$0.20 per 1 million" | **Implemented** (`invocation_charge(on_pc=True)`, `pc_invocation_billed_ms`) |
| **Overflow** above the configured concurrency | "If your function exceeds the configured concurrency, you will be billed for excess function execution at the rate outlined in the AWS Lambda Pricing section above" | **Implemented** at the on-demand rate, with the measured on-demand rule (floor(Duration + Init) + 1 ms, initialisation billed) |
| **Initialisation of provisioned environments** | "Lambda bills you for initialization even if the environment instance never processes a request. Provisioned concurrency runs continually and incurs separate billing from initialization and invocation costs." No amount or rate is given. | **Not implemented (U1)**: the rule is not stated |
| **Recycling** | "AWS Lambda periodically recycles the execution environments and re-runs your initialization code." The frequency and charge are not stated. | **Not implemented (U2)**: the rule is not stated |
| **Granularity, on-demand** | measured on 21,248 REPORT records (memcal-1) | Already implemented (`../billing_r214_20261123/`) |

## 2. Tests (`test_pc_billing_rules.py`, 9 of 9 pass)

- **AWS's "Cyber Monday" example:** PC 7 at 4,096 MB for 24 h is 2,419,200 GB-s, or USD 10.08. 2,000,000 x 280 ms on
  PC is 2,240,000 GB-s, or USD 21.78, and requests are USD 0.40. The total is **USD 32.26, as AWS states**.
- **AWS's "Mobile application launch" example:**
  - capacity 4,320,000 GB-s, USD 18.00;
  - PC compute 75,000 GB-s, USD 0.73;
  - non-PC compute after the example's free tier, USD 0.83;
  - requests USD 0.40;
  - total **USD 19.96, as AWS states**.

  The example computes the non-PC duration unrounded (120 ms). Under the measured on-demand rule, a whole 120 ms is
  billed as 121 ms, which gives 453,750 GB-s rather than 450,000. The test records this difference.
- **Hand cases:**
  - a 7-minute enablement is billed as 10 minutes;
  - amount changes on 5-minute boundaries bill the same under both readings of U3;
  - an off-boundary change bounds the U3 ambiguity;
  - PC and overflow invocations of 1,624.37 ms;
  - documented rounding against measured rounding;
  - the unresolved components refuse with `NotImplementedError`.

## 2a. The simulator's capacity billing against AWS's rule, on PRISM's schedules (`capacity_consistency.py`, `.json`)

**Input:** the stored E1 schedules of the E12-selected PRISM configuration, development traces 101-105, four test
scenarios, 20 weeks. There is no simulation.

**Mapping:** per stage, each run of epochs with P > 0 at one memory size is one enabled period. A memory change needs
a new published version, so it starts a new period.

**Agreement (verified):**
- The simulator's capacity GB-s (P x memory x 60 s per minute) equal AWS's rule ("from the time you enable it ...
  until it is disabled, rounded up to the nearest five minutes") **exactly in all 20 weeks**, under both readings of U3.
- The reason is that PRISM changes P only at 5-minute epoch boundaries, so no rounding remainder arises.
- Capacity GB-s x price reproduces the stored `cost_pc` (largest relative difference 1.9e-16).

**Activation lead, a bound (UNFAVOURABLE):**
- AWS says provisioned concurrency "doesn't come online immediately", with "a minute or two of preparation". The
  simulator makes new capacity available at the start of the epoch it is billed from.
- An operator who wants it READY then must enable each increase earlier.
- ASSUMPTION, not an AWS rule: each increase is enabled one epoch (5 minutes) early. That adds 10.7-12.0% to
  capacity GB-s, which is **6.19-7.44% of PRISM's weekly cost** (mean 6.67%; fast-simulator E1 costs,
  pre-calibration).
- This exceeds the 1-2% differences the reviewer is concerned about.
- Not computed: the same bound for the comparators that also provision capacity (QuantProv, PredHead, Reactive), and
  its effect on the paired comparisons C1-C3.
- A measured activation time (R6.1, the readiness polling) would replace the one-epoch assumption.

## 3. Unresolved billing assumptions

- **U1:** what initialising a provisioned environment costs.
- **U2:** recycling frequency and its charge.
- **U3:** when the configured amount changes within one enabled period, whether the period is rounded once, or each
  amount separately. Both are computed. They agree when changes fall on 5-minute boundaries, which PRISM's 5-minute
  epochs do if PC is enabled on an epoch boundary.
- **U4:** the PC duration rounding is documented ("rounded up to the nearest 1ms") but not measured. The measured
  on-demand rule adds 1 ms to whole-millisecond sums, so the two can differ by at most 1 ms per invocation.
- **U5:** the free tier. The page says it "does not apply to functions enabling Provisioned Concurrency", yet its first
  example applies it to the non-PC part. It is not modelled; it is account-level.
- **Prices:** the examples' N. Virginia prices; the us-east-2 prices are not shown on the pages read.

**Not done here:** applying these components to the simulator's costs, which would be a `src/` change and a rerun.
It would need U1 and U2 for a complete PC bill. U1 and U2 need either AWS's statement or a provisioned-concurrency
measurement: the R6.1 live check records readiness, but not billing per environment.

## 4. R2.14(b)

Pending. No usable AWS billing export is available locally: Cost Explorer returned no line items on 22 Nov 2026, and
no Cost and Usage Report exists.

## Files

- `pc_billing_rules.py`
- `test_pc_billing_rules.py`
- `capacity_consistency.py`, `capacity_consistency.json`
- `SHA256SUMS`

## 4. The activation-lead bound for every provisioning family, and its effect on the paired comparisons (24 Nov 2026)

`comparator_lead_bound.py`, run on the R3.6 release inputs:
- `linux/E1`, the Linux reference rows: `comparator_lead_bound_linux.json`;
- `windows/E1`: `comparator_lead_bound_windows.json`.

There is no simulation. Every family is at its validation-selected setting (the Section V-C rule), on development
traces 101-105 and the four test weeks. EXPLORATORY, PRE-CALIBRATION, fast simulator.

**Checks.** In all 160 test runs per platform:
- the simulator's capacity GB-s equal AWS's rule under both readings of U3;
- capacity GB-s x price reproduces each row's stored `cost_pc`.

So section 2a's agreement holds for every family, not only for PRISM.

**The bound** (same ASSUMPTION as section 2a: each increase enabled one epoch early). Share of weekly cost, on Linux;
Windows agrees within 0.1 points:

| Family | Added share of weekly cost |
|---|---|
| PRISM (main configuration) | 5.18-6.72% (mean 5.67%) |
| QuantProv-q90 | 5.25-6.77% (5.92%) |
| QuantProv-q99 | 3.28-4.74% (4.08%) |
| PredHead | 5.81-7.86% (6.76%) |
| PredHead+hyst | 4.76-5.92% (5.30%) |
| Reactive | 3.25-3.65% (3.49%) |
| Scheduled | 0.49-0.65% (0.55%) |
| Static | 0.02-0.03% (0.03%) |

Section 2a's 6.19-7.44% was for the E12-selected PRISM configuration on the stored rows. The table above uses each
family's E1 selection on the current code.

**Effect on the paired comparisons** (PRISM minus comparator, cost %, mean +/- 95% half-width over 5 traces, without
-> with the bound on both sides; Linux):
- **QuantProv-q90:** changes of −0.14 to −0.30 points. No sign change; every interval still includes 0, as before.
- **PredHead, PredHead+hyst:** changes of −1.3 to +0.6 points. Conclusions unchanged: PRISM is costlier, with the same
  intervals excluding 0.
- **QuantProv-q99, Reactive:** PRISM's saving shrinks by 1.3-1.7 points. No conclusion changes.
- **Static and Scheduled: UNFAVOURABLE.** PRISM's saving shrinks by 4.1-5.0 points, because these schedules rarely
  increase capacity and so incur almost no lead cost.
  - On Linux, three of eight intervals that excluded 0 no longer do: Static growth (−12.97 +/- 11.20 -> −8.17 +/-
    12.01%), Static new spike (−12.76 +/- 10.37 -> −7.79 +/- 11.13%) and Scheduled bursty (−12.17 +/- 11.07 -> −7.51
    +/- 12.26%).
  - On Windows, Static bursty loses significance, and Scheduled new spike changes sign (−3.66 -> +1.48%).
- **Compliance** is unchanged by construction: the bound adds cost only.

**Reading.** The bound matters for the savings over Static and Scheduled provisioning that the abstract cites
(R5.M7(a)). It does not matter for the comparison with QuantProv-q90. A measured activation time from the R6.1 live run
would replace the one-epoch assumption. AWS's five-minute rounding means any lead of up to five minutes before a
period starts adds a whole five-minute block, so the one-epoch bound is not a loose upper bound for a newly enabled
period.

Still open: U1 (initialisation of provisioned environments) and U2 (recycling), whose rules AWS does not state; and the
lead bound for the closed-loop C1-C3 schedules, which are not saved per epoch in the confirmatory outputs.

## 5. The verified components applied together to the saved records (24 Nov 2026; `integrated_estimate.py`)

**Do the saved records support the integration?** Yes, for the components with verified rules. Each E1 row stores
`cost_pc`, `cost_pcd`, `cost_od`, `cost_init` and `cost_req`, plus `overflow_share` and `share_mem_ge_2048`. Each term
maps to exactly one AWS charge, with no overlap:
- capacity;
- compute on provisioned concurrency;
- on-demand overflow duration;
- on-demand initialisation;
- requests.

An invocation is either on provisioned concurrency or overflow, and initialisation is billed only for on-demand cold
starts. Initialising provisioned environments (U1) and recycling them (U2) are not charged, because AWS states no rule.

**Checks:**
- The five terms sum to the stored `cost` exactly, in all 1,900 E1 rows on each platform (largest relative gap 0.0).
- The rows hold totals, not per-invocation durations, so the per-invocation rounding is applied in expectation: +0.5
  ms per invocation (mid), and at most +1 ms (upper). Provisioned-concurrency invocations are charged at the PCD rate,
  overflow at the on-demand rate, with 3008 MB for the share of minutes at 2048 MB or more in the upper case.
- `test_integrated_estimate.py`: 4 of 4 hand-calculated cases pass (`test_integrated_estimate.txt`). For example,
  10^6 invocations with 10% overflow at 1024 MB add USD 0.005208325 (mid) and 0.01041665 (upper).

**Result** (`integrated_estimate_linux.json`, `_windows.json`; the selected settings of 8 families, 5 traces, 4 test
weeks):
- Duration rounding raises weekly costs by 0.008-0.031%.
- Paired PRISM-minus-comparator cost differences move by at most 0.006 points (Linux) and 0.007 points (Windows).
- No interval changes its classification.
- The activation-lead bound of section 4 (an assumption) is reported beside it, unchanged. It is the only component
  with a material effect: on Static and Scheduled, as section 4 shows.

**Labels.** These are revised estimates, separate from the historical tables, which are unchanged. EXPLORATORY,
PRE-CALIBRATION, fast simulator.

**Still open:**
- U1, U2 and U4 (the provisioned-concurrency duration rounding is documented, not measured);
- final charges and campaign-level attribution: the estimated regional export reports USD 0 for Lambda without a
  stated reason. This is not taken to mean that the calibration blocks were free or that a particular credit applied.
