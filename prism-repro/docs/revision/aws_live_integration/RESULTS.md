# Live AWS integration test of the four-stage pipeline (run livetest_20261121-203051)

**What this run is:**
- A live integration test of the four-stage pipeline prototype (`prism-repro/aws_pipeline`), run on AWS in us-east-2 on 21 Nov 2026 between 20:30:56 and 20:55:22 CST (02:30:56-02:55:22 UTC on 22 Nov).
- It ran a **fixed memory schedule** on the **proposed synthetic document-ingestion workload**. That workload was chosen for the prototype; it is not the authors' application, and author decision P1 in `prism-repro/aws_pipeline/SPEC.md` is open.

**What it is not:**
- **PRISM's adaptive controller was not evaluated live.** The controller adapter applied a schedule fixed in advance: 1024, 512, 2048 and then 1024 MB. No forecast was made, and provisioned concurrency was neither requested nor applied.
- **Lambda Init Duration and billed duration remain unverified.** CloudWatch REPORT collection saved zero entries, and teardown then deleted the log groups. Lambda Max Memory Used and Lambda cost are unverified for the same reason.

**Limits on the evidence:**
- **Scale:** one run, with 40 records per arm, from one Windows laptop client.
- **Separate tests:** this run is distinct from the manual Hello World Lambda test and from the local rehearsal on fakes (`prism-repro/aws_pipeline/validation/prep_20261121/`). Neither of those is evidence for this run, and this run is not evidence for them.

## Unfavourable items first

1. **CloudWatch REPORT collection saved 0 entries.** `cloudwatch_reports.jsonl` is 0 bytes. The collection step failed at 02:55:10 UTC with a connection error to the AWS sign-in token endpoint, and teardown deleted the four log groups about 9 s later (CloudTrail, 02:55:19-02:55:20 UTC). So:
   - 0 of 160 stage rows per arm have a REPORT line;
   - Init Duration, Billed Duration, Max Memory Used and Lambda GB-s cannot be recovered from this run.
2. **The 60-s log-settle wait took about 13 minutes of wall time** before collection began. The cause is not established.
3. **The run fails its own pass criteria** in `prism-repro/aws_pipeline/LIVE_TEST.md`:
   - REPORT lines are missing for every stage row;
   - the run's own post-teardown check still listed the state machine.
   
   Deletion is supported only by CloudTrail and by a later author-run CLI check, whose output was not saved (see "Later AWS CLI check" below).
4. **The code revision is not recorded in the run files.** It is ea32370 by inference: the tracked files equal that commit, every code file predates it, and the commit predates the run.
5. **The third memory change (2048 to 1024 MB) is evidenced at the API level only.** The last record was submitted 165.4 s into the arm and finished at 172.6 s, while the change took effect at 183.3 s.
6. **Log streams and environments do not fully match.** In the schedule arm's window CloudTrail shows 33 log streams created, but the stage records contain 31 environments. The two extra streams, on the aggregate and load functions, cannot be explained from the saved files. The baseline matches exactly (13 and 13).
7. **Gaps in the CloudTrail exports:**
   - **IAM events are not included.** Creation and deletion of the two roles rest only on the run's own post-teardown listing, which reported no remaining roles.
   - **Data events are not included.** The exports have no Lambda Invoke or Step Functions StartSyncExecution events.
   - **Coverage is unknown.** The exports cover 02:30:11-02:55:23 UTC, and the export filter was not recorded.

## Sources

Neither source is in Git. Both are private, and their SHA-256 hashes are in `sources.sha256`.

**Run folder:** `AWS Live Implementation Log/AWS_livetest_20261121-203051/`.
- Two identical copies exist, with every file's hash matching: `prism-repro/aws_pipeline/runs/livetest_20261121-203051/` and `PRISM_tracker_backups/AWS_livetest_20261121-203051/`.
- Files used:
  - `records_plan.jsonl`;
  - `baseline_ondemand/records.jsonl` and `baseline_ondemand/decisions.jsonl`;
  - `adapter_schedule/records.jsonl`, `adapter_schedule/decisions.jsonl` and `adapter_schedule/arm.json`;
  - `smoke/records.jsonl`;
  - `livetest.log` and `livetest.json`;
  - `manifest.json`;
  - `cloudwatch_reports.jsonl` (empty).

**CloudTrail exports:** `PRISM_tracker_backups/AWS_livetest_20261121-203051_cloudtrail_KD9ijx/` (`lambda.json`, `logs.json`, `states.json`). These are `lookup-events` exports holding 219, 89 and 3 events, all in us-east-2.

**What this package contains:** only aggregates. It holds no account ID, ARN, access-key ID, IP address, request ID, full CloudTrail event or invocation record. `build_evidence.py` regenerates `tables/`, `sources.sha256` and `build_output.txt` from the two private sources, using the standard library only. It then scans its own outputs for those identifiers and fails if it finds any. The last build reported `sanitization scan: clean`.

```
python prism-repro/docs/revision/aws_live_integration/build_evidence.py \
  --run "AWS Live Implementation Log/AWS_livetest_20261121-203051" \
  --cloudtrail "../PRISM_tracker_backups/AWS_livetest_20261121-203051_cloudtrail_KD9ijx" \
  --out prism-repro/docs/revision/aws_live_integration
```

## Timeline (UTC, 22 Nov 2026)

| Time | Step | Evidence |
|---|---|---|
| 02:30:56 | Preflight: no leftover resources | `livetest.log` |
| 02:30:58-02:31:27 | Deploy: 4 log groups (7-day retention), 4 functions (1024 MB, python3.12), Express state machine (logging off) | CloudTrail |
| 02:32:30-02:32:37 | Calibration done; calibrated K set on all four functions | `livetest.log`, CloudTrail |
| 02:32:37-02:33:46 | Smoke: 3 records, all met | `smoke/records.jsonl` |
| 02:33:47-02:37:50 | Forced cold start, then the baseline arm (OnDemand, 1024 MB) | CloudTrail, `baseline_ondemand/` |
| 02:37:52-02:41:54 | Forced cold start, then the fixed-schedule arm; memory changes at 02:38:56, 02:39:56 and 02:40:56 | CloudTrail, `adapter_schedule/` |
| 02:55:10 | REPORT collection fails with 0 entries saved | `livetest.log`, `cloudwatch_reports.jsonl` |
| 02:55:16-02:55:23 | Teardown | CloudTrail, `livetest.json` |

Client timestamps and AWS timestamps differ by an offset. Timings in this package therefore come from a single clock wherever possible; the clock used is stated in `tables/overhead.csv`.

## CloudTrail verification

The checks below are in `tables/cloudtrail_lifecycle.csv`, and the event counts are in `tables/cloudtrail_events.csv`.

**Step Functions:**
- **Creation.** One CreateStateMachine for `prism-pipe-docpipe`, at 02:31:27. It was an Express state machine with logging off, and returned no error.
- **Deletion.** One DeleteStateMachine at 02:55:16, with no error.
- **Same resource.** The deleted state machine is the one created in this run: the identifier in the delete request equals the one in the creation response and in the run manifest. The comparison was done inside the build script, and neither identifier is reproduced here.

**Lambda:**
- **Creation.** Four successful CreateFunction calls, for `prism-pipe-ingest`, `-transform`, `-aggregate` and `-load`. All four are tagged, at 1024 MB, and unpublished (no versions), and the functions match the manifest.
- **One expected failure.** The first CreateFunction for `prism-pipe-ingest` returned InvalidParameterValueException because the new role could not yet be assumed. The deploy step retried it 11 s later, and the retry succeeded.
- **Environment updates.** Twelve UpdateFunctionConfiguration calls without a memory change, in three batches of four: the calibrated K, then one forced-cold nonce before each arm. All returned no error.
- **Memory updates.** Twelve UpdateFunctionConfiguration calls with MemorySize: four functions each at 512 MB (02:38:56), 2048 MB (02:39:56) and 1024 MB (02:40:56-57).
  - Every response's memory size equals the requested size, and none returned an error.
  - No memory update falls outside the schedule arm, which means the baseline stayed at 1024 MB.
- **Cleanup.** Four DeleteFunction calls, covering all four pipeline functions, with no error.
- **No provisioned concurrency.** There is no PutProvisionedConcurrencyConfig, PublishVersion or alias event.

**CloudWatch Logs:**
- **Creation.** Four CreateLogGroup and four PutRetentionPolicy calls, with no error.
- **Cleanup.** Four successful DeleteLogGroup calls. Four further DeleteLogGroup calls returned ResourceNotFoundException; this is teardown's second pass over the manifest's list, which treats "not found" as done.
- **Log streams.** The Lambda service created 54 log streams. See `tables/log_streams.csv` and item 6 above.

**API errors:**
- **Calls made by the run:** the one CreateFunction that was retried and succeeded, and the four repeat DeleteLogGroup calls.
- **Calls not made by the run:** AWS Resource Explorer's indexing made 20 GetPolicy calls that returned ResourceNotFoundException, because the functions have no resource policy.
- **Everything else:** no other create, update or delete call returned an error.

## Later AWS CLI check

After the run, the author ran an AWS CLI listing of Step Functions state machines in us-east-2. It returned no remaining pipeline workflow.
- The output was not saved, and the CloudTrail exports end at 02:55:23 UTC, so this package records the check as author-reported.
- Together with CloudTrail's error-free DeleteStateMachine, the check is consistent with the deletion having completed after the run's own check, which ran a few seconds after the delete request (the last teardown listing is at 02:55:23 UTC) and still listed the state machine.

## Results

### Paired deadline results (14.5 s per record, same 40 records in both arms)

Both arms processed the same 40 records, with identical document digests (`tables/arms.csv`, `tables/paired_deadlines.csv`).

| Arm | Met | Missed | Execution failures | Shed at cap | Max in flight | e2e p50 / p95 / max (s) |
|---|---|---|---|---|---|---|
| Baseline, OnDemand at fixed 1024 MB | 39 | 1 | 0 | 0 | 5 | 9.08 / 12.33 / 17.18 |
| Fixed schedule, through the adapter | 29 | 11 | 0 | 0 | 8 | 10.47 / 19.61 / 24.89 |

| Baseline / schedule outcome | met / met | met / missed | missed / met | missed / missed |
|---|---|---|---|---|
| Records | 28 | 11 | 1 | 0 |

### Observed memory and transition groups

Records are grouped by the memory size that each stage reported itself (`tables/memory_groups.csv`). A miss is attributed to a memory size only when every stage of that record ran at that size.

| Arm | Memory every stage reported | Records | Met | Missed | e2e median (s) |
|---|---|---|---|---|---|
| Baseline | 1024 MB | 40 | 39 | 1 | 9.08 |
| Schedule | 1024 MB | 11 | 11 | 0 | 9.85 |
| Schedule | 512 MB | 11 | 2 | 9 | 16.84 |
| Schedule | 2048 MB | 11 | 11 | 0 | 5.64 |
| Schedule | crossed 1024 to 512 MB | 2 | 1 | 1 | not attributed |
| Schedule | crossed 512 to 2048 MB | 5 | 4 | 1 | not attributed |

The baseline's one miss ran warm at 1024 MB in all four stages. It took 17.2 s, and its document was the run's largest, at 5,951 words.

**Warm handler time per 1,000 words** (`tables/memory_scaling.csv`; 10-14 warm stage rows per stage at each of 512 and 2048 MB):
- at 512 MB it was **2.01-2.07 times** the 1024 MB time;
- at 2048 MB it was **1.71-1.74 times faster** than at 1024 MB.

This covers one workload in one run.

### Memory-update timings (`tables/memory_updates.csv`)

| Change | Update duration (s) | In effect after epoch start (s) | CloudTrail requests / errors | Seen in stage records |
|---|---|---|---|---|
| 1024 to 512 MB | 3.27 | 3.26 | 4 / 0 | yes |
| 512 to 2048 MB | 3.33 | 3.32 | 4 / 0 | yes |
| 2048 to 1024 MB | 3.31 | 3.31 | 4 / 0 | no record ran after it |

**How the two timing columns differ:**
- **Update duration** runs from the first of four sequential UpdateFunctionConfiguration requests until all four functions reported the update successful. The client polled every 1 s, using the client's monotonic clock.
- **In effect after epoch start** is how long after the epoch boundary the new size applied. The adapter starts each change at the boundary, so this is almost the same figure. Each change was in effect well before the next boundary, 60 s later.

**CloudTrail timing check:** CloudTrail times are whole seconds. The first CloudTrail request of each change is 1.49 s after the client's recorded start, consistently. That figure includes request latency and the offset between the client and AWS clocks.

### Measured overhead (`tables/overhead.csv`, medians)

| Quantity | Baseline | Schedule | Clock |
|---|---|---|---|
| Client overhead: e2e minus the service span | 0.096 s | 0.110 s | client e2e minus Lambda host clocks |
| Stage transition, warm next stage | 23-27 ms | 24-27 ms | Lambda host clocks of two environments |
| Stage transition, cold next stage | 250-260 ms | 250-258 ms | same |
| Handler-module initialisation, cold stages | 5 ms | 5 ms | Lambda host clock |
| Decision time (fixed schedule or OnDemand, not PRISM) | at most 9 µs | at most 5 µs | client |

**About the cold-start figures:**
- The cold transition gap is the latency between stages when the next stage starts cold.
- Start-up work was set to zero (decision P3), so these figures are not comparable to the paper's assumed mean initialisation of 6 s.
- They are not Lambda Init Duration.

**Step Functions billing:** the billed Express duration and memory returned with each execution total 22.9 GB-s for the baseline and 27.55 GB-s for the schedule arm. Lambda billing is unverified.

**Integrity** (`tables/integrity.csv`):
- All 160 stage rows per arm carry unique Lambda request IDs.
- Cold stage rows equal distinct environments: 13 in the baseline and 31 in the schedule arm.
- Zero REPORT lines are joined.

## What the evidence supports

| Comment | Supported by this run | Not supported or still open |
|---|---|---|
| **R6.1** (validate PRISM on a real FaaS platform with an end-to-end four-stage pipeline) | The four-stage pipeline ran live end to end on Lambda and Step Functions Express. A baseline ran on the same 40 records: 39/40 met at 1024 MB against 29/40 under the fixed schedule, with no execution failures. Creation and cleanup of the functions, log groups and state machine are in CloudTrail | Validating PRISM itself: its controller was not in the loop, and the workload is the proposed one (P1). The run fails its own REPORT criterion. Role cleanup is not in CloudTrail |
| **R2.20** (evaluate operational delays; a small cloud deployment) | Memory reconfiguration of four functions takes about 3.3 s (three changes, 1-s polling), confirmed request by request in CloudTrail. Stage transitions take about 25 ms when warm. Client overhead is about 0.1 s. A small cloud deployment ran | Provisioned-concurrency activation delay, telemetry collection from CloudWatch, forecasting integration, and PRISM's own decision path running live |
| **R2.8** (measure warm times, initialisation, activation and cost; calibrate the simulators) | Live warm handler times per stage and size. Their scaling with memory: about 2.0 times slower at 512 MB and about 1.7 times faster at 2048 MB, relative to 1024 MB. Deadline outcomes by observed memory. Times at 1024 MB match the paper's targets by construction, because the stage work was calibrated to them | Initialisation delays (no Init Duration), billed duration and cost, activation behaviour, and calibrating the simulators |
| **R6.2** (measure cold starts, activation lag, concurrency, service times and billing) | Service times per stage and end to end. Cold starts as flags and counts. Up to 8 concurrent pipelines with no failures or shedding. Step Functions billed amounts | Init Duration and Lambda billed duration are unverified because 0 REPORT lines were saved. Activation lag and overflow are not measured, because no provisioned concurrency was used. There are no billing records |

**Status changes:** this package changes no reviewer status. R2.20 has been proposed to the author as Not fixed to Partially fixed, for review; that change is not applied.

**Quota:** the run's preflight recorded an account concurrency limit of 400 in us-east-2. That conflicts with the quota-of-10 blocker recorded elsewhere, which may apply to another Region, and needs confirming before either figure is relied on.
