# R2.14: billing rules verified against AWS records, their effect on C1-C3, and the reconciliation table (23 Nov 2026)

No AWS call was made. `src/` is unchanged, so no stored or regenerated result changes. Every simulation figure is
PRE-CALIBRATION; C1-C3 ran on Windows.

## Reviewer request (R2.14, Reviewer 2, comment 14)

"Please provide a more complete billing implementation and verify the resulting cost calculations against actual
provider billing records where possible."

The comment names four approximated or omitted charges: provisioning initialisation, activation timing, recycling and
billing granularity. It notes that "differences of approximately 1-2% may materially affect conclusions".

## 1. (a) What is implemented, and what is not

| Component | Simulator before (`src/prism_repro/simulator.py`) | Verified rule and input | Status |
|---|---|---|---|
| Billing granularity, on-demand duration | continuous mean duration per minute | Billed Duration = floor(Duration + Init) + 1 ms. This holds in all 21,248 memcal-1 REPORT records: 21,154 equal ceil(Duration + Init), and in the other 94 the sum is already whole and one ms is added (`../aws_memcal_20261122/RESULTS.md`). | **Implemented and tested** (`billing_rules.py`, `test_billing_rules.py`), and its effect computed (section 2) |
| Initialisation, on-demand cold starts | billed at the on-demand rate (`cost_init`) | Init is included in Billed Duration in every REPORT that has an Init Duration (4,992 cold starts plus 128 in the smoke run) | Already in the model; confirmed |
| Provisioned concurrency: billing increment and activation timing | billed per minute of configured capacity, with no activation delay | No sourced rule in the repository (`docs/PRICING_PROVENANCE.md` lists prices only). No saved run configured provisioned concurrency (account quota; D7). | **Not implemented: rule and input missing** |
| Recycling of provisioned environments | not modelled | No sourced rule and no observed recycling | **Not implemented: rule and input missing** |
| Initialisation of provisioned environments | not charged | No PC run, so it is not observable | **Not implemented: input missing** |

`test_billing_rules.py`, 5 of 5 pass:
- hand-calculated billed durations, including the whole-millisecond case;
- charges at 1024, 2048 and 3008 MB, for example 1,624.37 ms at 1024 MB gives 1,625 ms, 1.625 GB-s and USD 2.72833875e-5
  including the request fee;
- increment bounds;
- the memcal-1 totals: 20,992 requests, 55,234.5 GB-s, USD 0.92478 at list price.

## 2. Effect on the cost comparisons (`rounding_effect_c1c3.py`, `rounding_effect_c1c3.json`; EXPLORATORY adjustment)

Each C1-C3 test week records `n_requests` (records per week, so 4 x n_requests stage invocations) and the share of
minutes at 2048 MB or more. For continuous durations the rule adds 0.5 ms per invocation on average, and 1 ms at most.

| Comparison | As run (Windows, pre-calibration) | Upper bound (1 ms, on-demand rate, 3008 MB for the >= 2048 MB share) | Shift |
|---|---|---|---|
| C1 PRISM vs QuantProv-q90 | +0.2970% [-1.4174, +2.0115] | +0.3005% [-1.4135, +2.0145] | +0.0035 points (mid +0.0009) |
| C2 PRISM vs Reactive | -26.4939% [-28.7601, -24.2277] | -26.4849% [-28.7515, -24.2183] | +0.0090 points |
| C3 PRISM vs MemAdapt-q90 | +13.0629% [+8.4962, +17.6296] | +13.0519% [+8.4891, +17.6148] | -0.0110 points |

- Per-week costs rise by 0.022-0.092% under the upper bound. Because both policies see the same invocations, paired
  differences move by at most 0.011 points.
- No classification changes. C1 stays not distinguishable and not a tie: its upper end is +2.0145% after adjustment,
  against +2.0115% as run.
- The granularity part of the reviewer's 1-2% concern is therefore two orders of magnitude smaller. The provisioned-
  concurrency components remain unquantified.

The "as run" figures reproduce `../confirmatory_20261122/RESULTS.md` exactly. The adjusted figures are a separate,
labelled estimate; the historical results are unchanged.

## 3. (b) Reconciliation table for the requested AWS billing report (actual charges pending)

Scope: memcal-1, three calibration blocks, 22 Nov 2026, us-east-2, from AWS's own REPORT records
(`../aws_memcal_20261122/tables/billing.csv`). The smoke run is listed separately and excluded from the 20,992.

| Line | Calibration blocks (0-2) | Smoke run | Source | Status |
|---|---|---|---|---|
| Lambda requests | 20,992 (6,968 + 7,064 + 6,960) | 256 | REPORT records, unique request IDs | measured |
| Lambda billed duration | 55,234.5 GB-s (18,302.88 + 18,565.42 + 18,366.20) | 687.37 GB-s | sum of Billed Duration x memory | measured |
| Duration charge at list price | USD 0.92058 | USD 0.01146 | GB-s x 1.66667e-5 | computed |
| Request charge at list price | USD 0.00420 | USD 0.00005 | requests x 2e-7 | computed |
| Lambda total at list price | **USD 0.92478 (about 0.92)** | USD 0.0115 | `billing.csv` | computed |
| Free-tier allowance applied | unknown | unknown | account-level; not assumed | **pending (AWS report)** |
| Credits or discounts | unknown | unknown | none visible in Cost Explorer | **pending (AWS report)** |
| Net billed Lambda charge | not available | not available | Cost Explorer at 21:44 and 21:59 UTC on 22 Nov 2026: Estimated, no line items | **pending (AWS report)** |

Mapping for when the report arrives:
- Match only the Lambda duration and request line items for us-east-2 on 22 Nov 2026 UTC against the two "measured" rows.
- The account's bill for that period also includes:
  - the live-test runs of 21-22 Nov;
  - the smoke run;
  - Step Functions, CloudWatch Logs and the Cost Explorer API (USD 0.01 per request).
  These are excluded from the match.
- A difference is explained only when the report's own detail shows its cause (free tier, credit, or another
  function).
- With daily, service-level detail only, the match is limited to the Lambda total for the day.

## 4. Remaining for R2.14

- (a) A sourced, verified rule for provisioned-concurrency billing (increment, activation timing, recycling,
  initialisation of provisioned environments), and a provisioned-concurrency measurement to supply the inputs (D7).
- (b) The AWS billing report with Lambda line items, then the table above.
