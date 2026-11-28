# Sanitized summaries of two private sources of the R6.1 replay day (25 Nov 2026 UTC; added 28 Nov 2026)

Two sources behind published R6.1 statements are private because they carry account data: the AWS Cost Explorer
estimated export of 25 Nov 2026 (Supplementary Table S18, fourth row; TR5) and the CloudTrail management events of the
replay (the R6.1 reply's statement on provisioned-concurrency requests). This folder publishes their aggregates. No
request ID, ARN, account number, execution name or record content is included. No AWS call was made; no experiment
or simulation was run.

| File | Contents |
|---|---|
| `billing_export_20261125.md`, `.csv` | Lambda usage in us-east-2 (regional) and Lambda cost by record type (account-wide), estimated; the replay's REPORT populations beside them; the open difference |
| `report_populations_20261125.csv` | the replay's saved Lambda REPORT records by population, with billed GB-s |
| `cloudtrail_pc_20261125.md`, `.csv` | every provisioned-concurrency configuration request in the CloudTrail export, with its time, stage, requested units, error code and run phase |
| `summary.json` | all values above, machine-readable |
| `sources.sha256` | SHA-256 of the 10 private files read: the 3 billing-export files, the 2 CloudTrail-export files and 5 run files. The 5 run files are also listed in `../raw_sources.sha256`. |
| `summarise_private_exports.py` | the script that wrote every file above except this README, from the private replay folder |
| `SHA256SUMS` | every file in this folder except itself; `.gitattributes` keeps the files byte for byte |

## Count populations used in TR5 and Supplementary Table S18

| Count | What it is | Source |
|---|---|---|
| 2,584 | Lambda requests (stage executions) of the two replay arms, 323 records x 4 stages x 2 arms; 5,560.3 billed GB-s. This is the population of the harness estimate (USD 0.0927 for Lambda duration at an unverified list price). | `report_populations_20261125.csv`; `../r61_results.json` |
| 2,596 | REPORT records matched to recorded stage executions: the 2,584 plus 12 smoke-run executions | `report_coverage.matched` in `../r61_results.json` |
| 2,652 | every saved REPORT record of the replay: the 2,596 plus 56 calibration-probe REPORTs that match no run record | `report_coverage.extra_reports` in `../r61_results.json`; `report_populations_20261125.csv` |
| 2,568 | Lambda requests in the export: the account's us-east-2 usage for the UTC day | `billing_export_20261125.csv` |

The 84 is the numerical difference 2,652 - 2,568. The two populations have different scopes (one account-region-day of
billing against one run's saved logs), and the export is provisional. The difference is not reconciled. The final
charges attributable to the replay remain open, and so does what the export's credit is.

## Reproduce and verify

- **Inside this folder:** run `sha256sum -c SHA256SUMS` on any platform.
- **Against the private sources:** run `summarise_private_exports.py <private replay folder> <new folder>`, then
  compare the new folder with this one. This works only for holders of the private replay folder: checksums identify
  the private files but do not let anyone else check the numbers.
- **The GB-s derivation**, for anyone:
  - the public `lambda_duration` (USD 0.0926721186772 in `../r61_results.json`) divided by the harness price of
    USD 0.0000166667 per GB-s (`aws_pipeline/prism_pipeline/estimate.py`, `PRICES_UNVERIFIED`) gives 5,560.316 GB-s;
  - the arms' Lambda request cost divided by USD 0.20 per million gives 2,584 requests.
