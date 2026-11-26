# Provisional AWS billing reconciliation: Lambda usage in us-east-2 on 22 Nov 2026 UTC (R2.14(b), R2.8, R6.2)

No AWS call was made for this note, which uses saved files only. The raw billing exports, REPORT records and run
records are private and not in Git. This folder holds aggregates only:
- `reconciliation.csv`: the aggregate table cited in the replies;
- `reconciliation.json`;
- `reconcile.py`: the script, which takes the private folders as arguments;
- `SHA256SUMS`.

## 1. Sources

**The billing export** (Cost Explorer, `get-cost-and-usage`):
- exported at 2026-11-24 06:39:28 UTC;
- two daily UTC periods, 2026-11-21 and 2026-11-22;
- **Estimated: true** for both periods in both files.

The two files used are:

| File | Scope | Grouping |
|---|---|---|
| `ohio_usage_and_cost.json` | us-east-2 only | service and usage type; metrics UnblendedCost (USD) and UsageQuantity (Lambda: `Requests`, `Lambda-GB-Second`) |
| `account_cost_by_record_type.json` | all regions | service and record type (Usage, Credit) |

The export folder is `PRISM_AWS_billing_20261121-22_20261124T063928Z`. Its file hashes are in `reconciliation.json`.

**Earlier queries.** These are cited only to document that the earlier queries returned no line items:
- Two Cost Explorer responses saved on 22 Nov 2026, at 21:44 and 21:59 UTC, are byte-identical. Both have Estimated
  true, no groups and totals of 0. The 21:59 query's command, a us-east-2 filter with exit code 0, is saved with it.
- A zero-byte file from 21:22 UTC is a failed export.
- No refresh archive of the newer export exists, so the 06:39:28 UTC export is the single populated snapshot cited.

**Saved records on the AWS side**, all inside 22 Nov 2026 UTC:
- **memcal-1:** Lambda REPORT records and invocation records.
  - The functions were created at 17:08:51 UTC.
  - REPORT collection started at 17:01 UTC, and the file was last written at 20:02:43 UTC.
- **Two live tests of the four-stage pipeline:**
  - 21 Nov 20:30 CST, which is 02:30-02:55 UTC on 22 Nov. Its REPORT lines were lost, as earlier documented, so its
    run records give request IDs only.
  - 22 Nov 09:02 CST, which is 15:02-15:08 UTC, with REPORT records.
- **No Lambda line on 21 Nov UTC** appears in the us-east-2 export.

## 2. Lambda, us-east-2, 22 Nov 2026 UTC (`reconciliation.csv`)

| Line | Requests | GB-s | Source |
|---|---|---|---|
| memcal-1 calibration blocks 0-2 (17:17-19:51 UTC) | 20,992 | 55,234.505812 | REPORT records |
| memcal-1 smoke run (17:11-17:13 UTC) | 256 | 687.370500 | REPORT records |
| memcal-1 log groups, REPORTs with no campaign record (17:01-20:03 UTC) | 24 | 77.059875 | REPORT records |
| live test, 22 Nov 09:02 CST | 100 | 168.197000 | REPORT records |
| **Subtotal from REPORT records** | **21,372** | **56,167.133187** | |
| live test, 21 Nov 20:30 CST: stage invocations with saved request IDs | 332 | not saved | run records |
| **Export: us-east-2 Lambda, 22 Nov UTC** | **21,784** | **57,005.562125** | Cost Explorer, Estimated |
| Residual after the REPORT-attributed lines | 412 | 838.428938 | |
| Residual after also counting the 332 saved request IDs | **80** | — | **unattributed** |

**Units and boundaries:**
- The units match: invocations and billed GB-s, the latter as Billed Duration x memory / 1024 from each REPORT line.
- Every attributed line lies inside the 22 Nov UTC day.
- The four sets of request IDs are disjoint, so nothing is counted twice.

**The calibration estimate:**
- Calibration blocks 0-2: 20,992 requests and 55,234.5 GB-s, which is USD 0.92478 at the list prices used in the paper.
  Of that, USD 0.92058 is duration and USD 0.00420 is requests. It excludes the smoke run.
- Export minus blocks: 792 requests and 1,771.06 GB-s (1,771.062125 with blocks rounded to 55,234.5; 1,771.056313
  exactly).
- **Explained by REPORT records:** 380 requests and 932.63 GB-s, made of the smoke run (256; 687.37), the 24 extra
  REPORTs (77.06) and the 09:02 CST live test (100; 168.20).
- **Explained by request IDs only:** 332 requests, from the 21 Nov 20:30 CST live test.
- **Unattributed:** 80 requests and 838.43 GB-s. The 21 Nov live test's calibration probes and billed duration were
  not saved, so its share of the 838.43 GB-s cannot be separated. No other saved record covers the rest. The residual
  stays unattributed.
- **The 24 extra REPORTs** come from three campaign log groups, are warm, and have no campaign record. Their purpose
  is not recorded.

**Cost:**
- The export reports USD 0 unblended cost for both Lambda usage types, and USD 0 account-wide for Lambda (Usage).
- It shows **no separate Lambda credit row**. The account-wide export lists credits for some other services, not for
  Lambda.
- The export does not say why the Lambda cost is zero, and nothing is inferred about it here (free tier, credits or
  otherwise).
- The export is estimated, not final.

## 3. Step Functions (separate scope; not part of the Lambda calibration estimate)

- us-east-2, 22 Nov UTC: 94 requests and 60.78 GB-s, at USD 0 unblended.
- The two live tests' saved records hold exactly 94 Step Functions executions:
  - 21 Nov: 3 smoke and 2 x 40 arm records;
  - 22 Nov: 3 smoke and 2 x 4 arm records.

## 4. What this establishes, and what it does not

**Established:**
- AWS's regional usage for the day includes the calibration campaign's REPORT-measured usage.
- 98.1% of the regional requests (21,372 of 21,784) and 98.5% of the regional GB-s (56,167 of 57,006) are matched to
  saved REPORT records.
- 332 more requests are matched to saved request IDs.

**Not established:**
- final charges (the export is estimated);
- a campaign-level or run-level charge (regional totals are not attributed to runs beyond the matched usage);
- the reason for the zero cost;
- the 80 unattributed requests and 838.43 GB-s.

**Still needed:**
- the final (non-estimated) billing data;
- the Cost and Usage Report (CUR), with resource-level line items if available, to attribute charges to the
  campaign's functions and explain the zero cost;
- the pending CUR case.
