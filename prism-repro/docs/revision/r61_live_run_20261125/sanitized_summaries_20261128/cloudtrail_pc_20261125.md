# Provisioned-concurrency configuration requests in CloudTrail, R6.1 replay (25 Nov 2026): sanitized summary

**Source.** CloudTrail management events of the account, us-east-2, lookup 03:30-05:15 UTC on 25 Nov 2026,
exported 18:34 UTC: 3,069 events between 03:31:58 and 05:13:51 UTC, all in us-east-2. The export
is private (it carries account data); its two files are identified by SHA-256 in `sources.sha256`. This summary keeps
event times, stages, requested units and error codes only. Built by `summarise_private_exports.py` (no AWS call).

**Configuration requests (`cloudtrail_pc_20261125.csv`):**

| Time (UTC) | Event | Stage | Requested units | Error code | Phase |
|---|---|---|---|---|---|
| 03:41:25 | DeleteProvisionedConcurrencyConfig | aggregate | - | none | reset before the OnDemand arm |
| 03:41:25 | DeleteProvisionedConcurrencyConfig | ingest | - | none | reset before the OnDemand arm |
| 03:41:25 | DeleteProvisionedConcurrencyConfig | load | - | none | reset before the OnDemand arm |
| 03:41:25 | DeleteProvisionedConcurrencyConfig | transform | - | none | reset before the OnDemand arm |
| 04:21:37 | DeleteProvisionedConcurrencyConfig | aggregate | - | none | reset before the PRISM arm |
| 04:21:37 | DeleteProvisionedConcurrencyConfig | ingest | - | none | reset before the PRISM arm |
| 04:21:37 | DeleteProvisionedConcurrencyConfig | load | - | none | reset before the PRISM arm |
| 04:21:37 | DeleteProvisionedConcurrencyConfig | transform | - | none | reset before the PRISM arm |
| 04:21:44 | PutProvisionedConcurrencyConfig | aggregate | 2 | none | PRISM decision epoch 0: initial allocation |
| 04:21:44 | PutProvisionedConcurrencyConfig | ingest | 1 | none | PRISM decision epoch 0: initial allocation |
| 04:21:44 | PutProvisionedConcurrencyConfig | load | 1 | none | PRISM decision epoch 0: initial allocation |
| 04:21:44 | PutProvisionedConcurrencyConfig | transform | 2 | none | PRISM decision epoch 0: initial allocation |
| 04:28:08 | PutProvisionedConcurrencyConfig | aggregate | 1 | none | PRISM decision epoch 1: decrease (aggregate 2 -> 1) |
| 05:04:20 | DeleteProvisionedConcurrencyConfig | aggregate | - | none | teardown |
| 05:04:20 | DeleteProvisionedConcurrencyConfig | ingest | - | none | teardown |
| 05:04:20 | DeleteProvisionedConcurrencyConfig | load | - | none | teardown |
| 05:04:20 | DeleteProvisionedConcurrencyConfig | transform | - | none | teardown |

- **5 PutProvisionedConcurrencyConfig requests, none with an error code**: four at 04:21:44 UTC (the initial
  allocation of 1/2/2/1 units at PRISM's first decision) and one at 04:28:08 UTC (the next decision, lowering
  aggregate from 2 to 1). They equal the PRISM arm's recorded requests (`pc_readiness` in `../r61_results.json`).
- 12 DeleteProvisionedConcurrencyConfig requests, none with an error code: the harness's reset of the four
  aliases before each arm and at teardown (`clear_pc` in `aws_pipeline/prism_pipeline/adapter.py`).
- 1,912 GetProvisionedConcurrencyConfig calls are the harness's read-only status reads (`poll_pc`, same file),
  not configuration requests: 976 during the PRISM arm (04:21:44-05:03:08 UTC) and 936 during
  the OnDemand arm (03:41:31-04:21:31 UTC), which returned `ProvisionedConcurrencyConfigNotFoundException` because no configuration existed.

**Acceptance is not readiness.** CloudTrail shows that AWS accepted each request. When the capacity became usable is
measured separately, by the harness polling the configuration status every 10 s (`pc_readiness` in
`../r61_results.json`; TR3): READY was first observed 82.8 s after the initial allocation and 20.1 s after the
later decrease. Two observations from one replay.
