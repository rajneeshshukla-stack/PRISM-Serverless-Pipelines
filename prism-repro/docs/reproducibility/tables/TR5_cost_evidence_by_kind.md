# TR5. Cost evidence, by kind (kept distinct; no figure here is a final replay-attributable charge)

| Kind | Scope | Requests | GB-s | Amount | Status | Source |
|---|---|---|---|---|---|---|
| Usage-based estimate at public list price | memcal-1 calibration blocks (22 Nov 2026 UTC), Lambda duration + requests, free tier not assumed | 20,992 | 55,234.5 | USD 0.92 | estimate from REPORT records, not a bill | `aws_memcal_20261122/tables/billing.csv` |
| Harness estimate at UNVERIFIED list prices | R6.1 replay, both arms, Lambda + Step Functions, excludes provisioned concurrency | - | - | USD 0.10 | estimate, not a bill | `r61_live_run_20261125/r61_results.json` |
| AWS estimated billing export (Cost Explorer) | us-east-2, 22 Nov 2026 UTC, full day, all resources | 21,784 | 57,005.6 | USD 0 (no reason stated) | ESTIMATED, provisional; 21,372 requests / 56,167.1 GB-s matched to saved REPORT records, 80 requests / 838.4 GB-s unattributed | `billing_reconciliation_20261124/reconciliation.csv` |
| AWS estimated billing export (Cost Explorer) | us-east-2, 25 Nov 2026 UTC (R6.1 replay day), full day, all resources | 2,568 | 3,255.4 on demand + 2,219.8 on provisioned environments | USD 0 by usage type; account-wide Lambda usage USD 0.0216 offset by an equal credit | ESTIMATED, provisional; no separate provisioned-concurrency capacity line; 2,568 requests against 2,596 matched REPORT records (28 fewer), NOT RECONCILED | private AWS billing export (not published: it carries account data) |
| Final charges attributable to the runs | memcal-1 and the R6.1 replay | - | - | open | requires the final bill / Cost and Usage Report | pending |
