# Estimated billing export of 25 Nov 2026 (UTC): sanitized summary

**Source.** AWS Cost Explorer export, taken 2026-11-25 18:31 UTC;
period 2026-11-25 00:00 to 2026-11-26 00:00 UTC (one full UTC day); **Estimated: true**. The export is private (it
carries account data); its three files are identified by SHA-256 in `sources.sha256`. A checksum identifies the file;
checking these numbers against it still needs access to the export. Built by `summarise_private_exports.py` (no AWS
call).

**Scope.** The usage lines are **regional**: all of the account's Lambda usage in us-east-2 on that UTC day, not only
the replay. The record-type lines are **account-wide** (all regions). The export files do not store their query
filters; these scopes follow the export's file names (`ohio_usage_and_cost.json`, `account_cost_by_record_type.json`)
and the method documented for the 22 Nov export (`../../billing_reconciliation_20261124/README.md`).

| Scope | Line | Quantity | Unit | Unblended cost (USD) |
|---|---|---|---|---|
| regional (us-east-2) | usage type USE2-Request | 2568 | Requests | 0.000000 |
| regional (us-east-2) | usage type USE2-Lambda-GB-Second (on-demand duration) | 3255.3560 | Lambda-GB-Second | 0.000000 |
| regional (us-east-2) | usage type USE2-Lambda-Provisioned-GB-Second (duration on provisioned environments) | 2219.7920 | Lambda-GB-Second | 0.000000 |
| account-wide (all regions) | record type Usage | - | - | 0.021581 |
| account-wide (all regions) | record type Credit | - | - | -0.021581 |

There is no separate provisioned-concurrency capacity line. Every regional Lambda line is priced at USD 0; the
account-wide Lambda usage of USD 0.021581 is offset by a credit of the same size. The export names only the
record type `Credit`; it does not say what the credit is.

**The replay's own REPORT records** (`report_populations_20261125.csv`; every run phase lies between 03:38:34 and
05:04:26 UTC on 25 Nov, inside the export's day):

| Population | REPORT records | Billed GB-s |
|---|---|---|
| replay arms (PRISM + OnDemand): stage executions | 2,584 | 5,560.3 |
| of which served by provisioned concurrency (PRISM arm) | 1,112 | 2,372.0 |
| smoke run: stage executions | 12 | 26.5 |
| matched REPORT records (replay arms + smoke) | 2,596 | 5,586.8 |
| calibration-probe REPORTs (unmatched extras) | 56 | 57.7 |
| all saved REPORT records of the replay | 2,652 | 5,644.5 |

- **2,584** is the replay arms' Lambda requests (stage executions); with **5,560.3** billed GB-s it is the population
  of the harness estimate: 5,560.316 GB-s x USD 0.0000166667 = USD 0.0926721 (`lambda_duration` in
  `../r61_results.json`; price from `aws_pipeline/prism_pipeline/estimate.py`, `PRICES_UNVERIFIED`). The estimate is
  at unverified list prices, counts all duration at the on-demand rate, adds 646 Step Functions executions and
  excludes provisioned-concurrency capacity. It is not a bill.
- **2,596** is the matched REPORT records: the replay arms plus 12 smoke-run stage executions.
- **2,652** is every saved REPORT record: the 2,596 plus 56 calibration-probe REPORTs that match no run record.
- **2,568** is the export's us-east-2 Lambda requests. The saved REPORT records exceed it by 84
  (2,652 - 2,568), and their billed GB-s exceed the export's 5,475.148 by 169.3. The populations
  have different scopes (one account-region-day of billing against one run's saved logs), and the export is
  provisional. **The difference is not reconciled.**
- Informational, not a reconciliation: the PRISM arm's stage executions served by provisioned concurrency bill
  2,372.0 GB-s in their REPORT records; the export lists 2,219.792 GB-s on provisioned environments.

**Still open.** The final charges attributable to the replay (they need the final bill or a Cost and Usage Report),
and what the credit is.
