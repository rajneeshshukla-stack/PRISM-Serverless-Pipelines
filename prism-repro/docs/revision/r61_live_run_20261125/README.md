# R6.1 paired live replay on AWS Lambda (25 Nov 2026, 03:38-05:05 UTC)

**Scope.** One authorised paid run, us-east-2, following `../r61_live_plan_20261123/RUN_SHEET_20261124.md`.
- **Arms:** PRISM's frozen controller against OnDemand, on the same 323-record thinned replay of trace 101
  (stationary, test week), 8 decision epochs of 5 minutes.
- **What it is:** a small-scale live demonstration of the controller and its actuation (run sheet section 6).
- **What it is not:** a validation of PRISM's compliance or cost results.

**Evidence handling.**
- The raw run folder stays private and untracked: `aws_pipeline/runs/r61_prism_replay_20261124-213827/`.
- This folder holds aggregates only: no ARNs, account IDs, request or execution IDs.

## Unfavourable and null findings first

1. **The frozen controller's warm-miss prediction is contradicted.**
   - **Prediction** (recorded before preflight, run sheet section 3a): 0.22% at 1024 MB under independent stages.
   - **Observed fully warm misses:**
     - OnDemand: 8 of 314 (2.55%, 95% CI 1.11-4.96%);
     - PRISM: 9 of 313 (2.88%, 1.32-5.39%).
   - Both intervals exclude 0.22% and include the P2 shared-stage prediction of 3.3%.
2. **The misses are document-size driven, and provisioning does not prevent them.**
   - Every fully warm miss is a large document: 4,976-7,120 words, against a median of 2,933.
   - Paired on identical records: 313 met in both arms, **9 missed in both**, and 1 missed only under PRISM (a 4,976-word
     document). No record was met only under PRISM.
   - Provisioned concurrency removes cold starts, but cannot shorten a long warm execution.
3. **No compliance or cost difference between the arms is supported.**
   - Arms: OnDemand 314 met / 9 missed; PRISM 313 / 10.
   - Paired median end-to-end difference −0.09 s (5th-95th percentile −0.57 to +0.40 s).
   - One run, one trace-week, unverified prices. The window-level SLA is not measurable here (2 windows per arm).
4. **The in-run teardown reported NOT CLEAN.** The state machine was still listed, in status DELETING, because
   Step Functions deletes asynchronously. A read-only `verify` reported **CLEAN** at 05:05:34Z: no function, state
   machine, log group or role remains. No manual deletion was needed.
5. **PRISM never left 1024 MB,** as the offline preview predicted. The run therefore exercises
   provisioned-concurrency decisions only, not memory adaptation.

## Validity criteria (PLAN.md section 9): all hold

| Criterion | Result |
|---|---|
| Code: `git_head` and pinned hashes | `92e3e68`; 9 of 9 `files_sha256` match `PINNED_FILES.sha256`. The only uncommitted path is `prism-repro/aws_pipeline/runs/`, as the run sheet expects. |
| Quota | Unreserved 400, at least 116 needed |
| `verified` and REPORT coverage | true: **2,596 of 2,596 matched, 0 missing**, 56 extra (calibration probes), 0 stage rows without a request ID, 0 duplicates |
| Outcomes | Every record has one; 0 failed, 0 shed at the client cap of 8 (most in flight 7); no adapter or monitor error |
| Matched inputs | Both arms ran the **identical 323 records** (IDs, offsets, documents); smoke 3 of 3 met |
| Memory actuation | `memory_applied` = `memory_requested` = 1024 MB in all 8 decisions |
| Provisioned concurrency | Requested, submitted and accepted are recorded; `pc_applied` is null by design; no refusal and no clipping (cap 4) |
| Readiness | From polls only. All 5 accepted changes are **ready**: the epoch-0 request (1/2/2/1 units) after 82.8 s, and the epoch-1 change (aggregate 2→1) after 20.1 s |
| Teardown | CLEAN after asynchronous deletion (finding 4) |

## Ready-to-expand criteria (PLAN.md section 9)

| Criterion | Result |
|---|---|
| Epoch-0 provisioned concurrency READY before the first record | **Met**, with a 3.0 s margin |
| Later changes READY within their epoch | **Met**: 20.1 s, against a 300 s epoch |
| Provisioned environments served PRISM executions; spill-over counted | **Met**: 259-291 of 323 executions per stage on provisioned concurrency, 32-64 on-demand |
| Measured end-to-end times at 1024 MB within the simulator's calibration range | **Not met for the frozen model's tail.** Mean end-to-end is 8.8 s, as modelled. The warm miss rate is about 12× the frozen model's 0.22%, but consistent with the P2 shared-stage model, so calibrate first (P2-DEP). |

## Measurements

**Activation lag:**
- 82.8 s for the initial allocation (4 functions, requested together);
- 20.1 s for a decrease on one function.

This is 2 distinct events, at 10 s polling resolution: far fewer than the about 9 observations the preview suggested,
because PRISM changed P only once after epoch 0.

**Cold starts:**

| Arm | Records with ≥ 1 cold stage | Cold stage executions |
|---|---|---|
| OnDemand | 9 of 323 | 16, all on-demand initialisation |
| PRISM | 10 of 323 | 18: 7 provisioned-concurrency, 11 on-demand |

The 7 provisioned-concurrency initialisations report no Init Duration, as expected.

**End-to-end, p50 / p95 / p99 / max:**
- OnDemand: 8.55 / 13.59 / 16.72 / 20.02 s;
- PRISM: 8.53 / 13.47 / 16.74 / 19.91 s.

**Fully warm 1024 MB misses (run sheet check 7):**
- **Denominator:** records succeeded, with 4 stages, none cold, all at 1024 MB.
- **Excluded:** OnDemand 9, PRISM 10, all for at least one cold stage. None were shed, failed or at another memory size.

| Arm | Denominator | Misses (end-to-end) | 95% CI | Misses (Step Functions billed duration) | Misses (first stage start to last stage end) |
|---|---|---|---|---|---|
| OnDemand | 314 | 8 (2.55%) | 1.11-4.96% | 8 | 8 |
| PRISM | 313 | 9 (2.88%) | 1.32-5.39% | 8 | 8 |

- The records carry no `service_s` field, so the AWS-side repeat uses the Step Functions billed execution duration
  and the stage wall-clock span.
- The PRISM-only miss is over 14.5 s end to end, but not on either AWS-side measure: the excess is on the client-side
  path.
- One further miss per arm falls in a record with a cold stage and is excluded from the denominator.

**Cross-stage dependence, re-estimated on the new documents** (`audit_dependence_r61.py`, a copy of the P2 script with
the arm name changed; `dependence_audit.json`):

| | Value | Bootstrap 95% |
|---|---|---|
| Fit records | 314 fully warm OnDemand records, 300 distinct sizes, 1,272-7,120 words | |
| sd of log size | 0.303 (the declared σ is 0.30) | |
| Slopes | 0.91-1.02 | |
| Size R² | 99.3-99.7% | |
| Residual σ_log | 0.017-0.025 | |
| Residual cross-stage correlation | 0.077 | 0.03-0.13 |
| **Total cross-stage correlation** | **0.996** | **0.995-0.997** |

- The P2 estimate (ρ ≈ 0.998, 34 records) replicates on about 9 times as many new documents.
- Check against the PRISM arm's 313 warm records (largely the same documents): mean absolute log error 0.020.

**Cost:** the harness estimate for the two arms' Lambda and Step Functions usage is about USD 0.10, at UNVERIFIED list
prices (`r61_results.json`), excluding provisioned concurrency. Actual charges need the billing export (R2.14(b)).

## Not measured by this run

- burst overflow (cap 8 in flight, P ≤ 4);
- application start-up (the handler does no start-up work);
- memory sizes other than 1024 MB;
- the window-level SLA.

## Files

- `analyse_r61.py`: run-sheet checks, aggregates only; `r61_results.json` and `analyse_stdout.txt` are its outputs.
- `audit_dependence_r61.py`: the dependence re-estimate; `dependence_audit.json` and `dependence_audit_stdout.txt`
  are its outputs.
- `raw_sources.sha256`: SHA-256 of the private raw files used (contents not included).
- `SHA256SUMS`: checksums for this folder.
