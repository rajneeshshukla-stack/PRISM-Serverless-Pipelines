# Runbook: the quota-10 on-demand campaign (for a separately authorised run)

**Nothing in this file has been executed.** Every AWS command below does nothing (it prints a plan) unless it gets
`--execute` **and** the shell has `PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES`. The workloads are PROXIES (`README.md`).

## Before the run

1. **Authorisation:** the author approves the run, the region and the cost ceiling, and sets a billing alarm.
2. **Prices:** check current Lambda and CloudWatch Logs prices for the region. The estimate below uses the
   manuscript's prices, which `prism_repro.config.Prices` states are not current.
3. **Client host:** prefer a small host **in the same region** (an EC2 instance or AWS CloudShell; CloudShell
   sessions time out when idle). That keeps the network share of `P` and `R` small. A laptop works too, but adds WAN
   latency and its variance to `P` and `R`, and a laptop that sleeps interrupts a block. The runner resumes at the
   interrupted visit, but the suspension is not recorded, so note it.
4. **Separate Python environment with boto3** (do not install into the project's `venv`):

   ```
   python -m venv .venv-aws && .venv-aws/Scripts/python -m pip install boto3 numpy
   ```

   The analysis also imports `prism_repro` from `../src`; run it with the project venv, or install `scipy pandas` too.
5. **IAM permissions** for the operator:
   - `iam:CreateRole`, `iam:GetRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:DeleteRole`,
     `iam:PassRole`;
   - `lambda:CreateFunction`, `GetFunctionConfiguration`, `UpdateFunctionConfiguration`, `InvokeFunction`,
     `ListFunctions`, `DeleteFunction`, `GetAccountSettings`;
   - `logs:CreateLogGroup`, `PutRetentionPolicy`, `FilterLogEvents`, `DeleteLogGroup`;
   - `sts:GetCallerIdentity`.
6. **Nothing else running:** no other function in the account should run during a block. The quota of 10 is per
   account and region, and the harness keeps at most 8 in flight.

## Commands (from `prism-repro/aws_measurement`, region example `us-east-1`)

```
export PRISM_AWS_AUTHORIZED=I-ACCEPT-CHARGES          # only once the run is authorised
PY=.venv-aws/Scripts/python
OUT=runs/$(date +%Y%m%d)                              # new directory per campaign; nothing is overwritten
mkdir -p $OUT

$PY -m prism_measure preflight --region us-east-1 --execute              # quota >= 10? leftovers? (read only)
$PY -m prism_measure design    --out $OUT/design.json                    # 696 visits, fixed seed 20261121
$PY -m prism_measure deploy    --region us-east-1 --manifest $OUT/manifest.json --execute   # role + 24 functions
$PY -m prism_measure calibrate --manifest $OUT/manifest.json --execute   # sets work units from a 1024 MB probe

# three blocks on three different days, at different times of day:
$PY -m prism_measure run --manifest $OUT/manifest.json --records $OUT/records.jsonl --block 0 --execute --host-note "<host, region, day>"
$PY -m prism_measure run --manifest $OUT/manifest.json --records $OUT/records.jsonl --block 1 --execute --host-note "..."
$PY -m prism_measure run --manifest $OUT/manifest.json --records $OUT/records.jsonl --block 2 --execute --host-note "..."
# an interrupted block: rerun the same command; completed visits are skipped, the broken visit reruns

$PY -m prism_measure collect --manifest $OUT/manifest.json --records $OUT/records.jsonl --out $OUT/cloudwatch.jsonl --execute
../venv/Scripts/python -m prism_measure analyse --records $OUT/records.jsonl --cloudwatch $OUT/cloudwatch.jsonl --out $OUT/analysis
$PY -m prism_measure teardown --region us-east-1 --manifest $OUT/manifest.json --execute
```

**Outputs in `$OUT/analysis`:**

- `cells.csv`: I, P, X, R, P_mean with intervals and counts.
- `trends.csv`: slopes against Eq. (3), the decision on P, and the `init_mean_measured` candidate.
- `missing.csv`: per cell; it counts throttles, errors, missing request IDs, REPORTs missing or recovered from
  CloudWatch, cold calls without Init Duration, unexpected warm or cold calls, ID mismatches and duplicates.
- `billing.csv`: GB-seconds, requests and cost at the given prices.
- `issues.json`.

## Stop conditions (stop the block, investigate, resume later)

- **Throttling:** any `throttled` count in `missing.csv`, which means something else used the quota.
- **Errors or failed updates:** repeated errors or function errors, or configuration updates that fail or time out.
- **Cold batches not cold:** a cold batch with more than one `unexpected_warm_in_cold_batch`, meaning the batch did
  not overlap; check the client host's load.
- **Spend:** above the authorised ceiling.

## Expected runtime and cost (`validation/dry_run_20261121-172542/estimate.json`)

23,168 invocations: 4 stage proxies x 4 sizes x (232 cold + 1,000 warm), plus 2 init proxies x 4 sizes x (232 cold +
200 warm). There are 696 configuration updates.

| Duration model | Billed GB-s | Cost at manuscript prices | If INIT is billed too | Active hours (per block) |
|---|---|---|---|---|
| CPU share proportional to memory | 43,772 | $0.73 | $0.91 | 3.7 (1.27 / 1.28 / 1.14) |
| Single vCPU plateau above 1,769 MB | 53,156 | $0.89 | $1.08 | 3.8 (1.32 / 1.32 / 1.18) |
| Simulator's Eq. (2) | 57,100 | $0.96 | **$1.15** | 3.7 (1.28 / 1.28 / 1.15) |

**What the figures leave out:**

- **Assumptions behind them:** 10 s per configuration update, 1.0 s platform cold start, 0.05 s client overhead,
  in-region. With a WAN client, add about 0.25 s per batch: 2,896 batches, so about +0.2 h, since a batch's 8 calls run
  concurrently.
- **Elapsed time:** add deploy and calibration (about 15 min) and teardown (a few minutes). The calendar span is at
  least 3 days.
- **Other charges:** CloudWatch Logs ingestion of about 10 MB, and the client host if EC2.
- **Free tier:** not assumed.
- **Use as a ceiling:** recompute with current prices before approval, using
  `prism_measure estimate --price-gb-s <current> --price-request <current>`.

**Limits:**
- Each init proxy carries 2 s of CPU start-up work at 1024 MB, about 4 s at 512 MB, which stays within Lambda's 10 s
  INIT limit.
- The stage proxies run at most about 8 s (transform at 512 MB) against a 60 s timeout.

## Cleanup and verification

1. **Delete everything:** `teardown --execute` deletes every function in the manifest and every `prism-meas-`
   function it finds, their log groups, and the role.
2. **Confirm nothing remains:** check in the console, or with `aws lambda list-functions`, that no `prism-meas-`
   function is left. Also check that `/aws/lambda/prism-meas-*` log groups and the `prism-meas-lambda-role` role are
   gone.
3. **Keep the raw files:** keep `$OUT/` (records, manifest, CloudWatch reports, analysis) outside Git like the other
   raw datasets, and commit only the aggregate analysis tables.
4. **Billing reconciliation:** after the bill settles, compare `billing.csv` with the bill or the Cost and Usage
   Report for the run's days (on-demand duration and request charges; R2.8 cost, R6.2 billing, R2.14).

## Not covered (blocked under the applied quota of 10)

- **Provisioned-concurrency activation lag:** R1.3, R3.1(b), R4.3, R6.1, R6.2.
- **Burst overflow beyond provisioned capacity:** R4.3, R6.2.

Both need provisioned concurrency, which cannot be configured at this quota (`notes/manuscript_proposals.md`
section G).
