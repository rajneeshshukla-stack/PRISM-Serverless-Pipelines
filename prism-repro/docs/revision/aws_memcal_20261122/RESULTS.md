# memcal-1: multi-memory Lambda calibration, 22 Nov 2026 (R2.8, R3.1, R6.2)

## What this was

| Item | Detail |
|---|---|
| Run | `AWS_memcal_20261122-110627`, us-east-2 |
| Who ran it | the author, outside this session |
| Analysis | from the saved files only, with no AWS call |
| Workload | docpipe-1 four-stage document pipeline (ingest, transform, aggregate, load) |
| Work units K | frozen at 373 / 4908 / 2264 / 1966 (`PRISM_CALIBRATION=0`) |
| Start-up work | none: `INIT_ROWS = 0` (decision P3) |
| Input | one reference document |
| Platform | python3.12, x86_64 |

**Memory:** 512, 1024, 2048 and 3008 MB, one function per stage and size (16 functions).

**Invocation:** on demand, from a Windows laptop client, with at most 8 invocations in flight.

**Design:**
- 39 visits per stage and size: 312 cold invocations (forced-cold batches of 8) and 1,000 warm ones.
- Visits run in randomised order in three blocks.
- In total, 624 visits and 20,992 invocations, plus a 256-invocation smoke run.

**Plan:** `prism-repro/aws_pipeline/MEMCAL_PLAN.md`.
- SHA-256 3dd2ef98...08c4, committed in 3bf7958 at 10:56 CST.
- That was before the first smoke invocation, at 11:11 CST.
- The design and split code are unchanged since that commit.

**Not tested here** (each needs its own evidence):
- provisioned-concurrency activation or its lag;
- overflow under a burst, or scale beyond 8 concurrent invocations;
- actual AWS charges (no bill reconciliation);
- PRISM's adaptive controller, which did not run. The memory size was fixed per function.

## Deviations and flags (read first)

1. **The three blocks ran on the same afternoon, not on three days as planned.** All times are CST (UTC−6), with gaps of 7 and 14 minutes:

   | Block | Time | Invocations |
   |---|---|---|
   | 0 | 11:17:59-12:02:06 | 6,968 |
   | 1 | 12:08:59-12:50:59 | 7,064 |
   | 2 | 13:05:06-13:50:45 | 6,960 |

   Repeatability is therefore within one afternoon. Day-to-day variation is not measured.
2. **The runtime version was not recorded.** None of the 21,248 invocation records carries it, so whether the
   runtime changed during the run cannot be checked.
3. **Laptop client stalls.**
   - 38 invocations, in 5 warm FIT batches, had more than 5 s of client time beyond Lambda Duration + Init. The
     worst was 216.8 s, against at most 5.1 s of Lambda Duration (`client_stalls.csv`).
   - Median client overhead was 0.081 s (p99 0.585 s).
   - Medians are robust to the stalls; means are not. The mean-based penalty `P_mean` is not estimable for
     transform, aggregate, load or pooled.
4. **24 CloudWatch REPORTs match no recorded invocation.**
   - All are warm: 8 each for aggregate at 3008 MB, load at 2048 MB and transform at 512 MB.
   - The REPORT rows carry no timestamp, so their origin is unknown.
   - They are kept in the private archive and excluded here.
5. **Billed Duration has a 1 ms quirk.** In 94 of 21,248 invocations, Billed Duration is ceil(Duration + Init) + 1 ms. In every one of the 94, the printed sum is a whole number of ms, which fits REPORT values rounded to 0.01 ms. No case is unexplained.

## Coverage and integrity (`build_output.txt`, `tables/coverage.csv`)

All 22 checks pass.

| Check | Result |
|---|---|
| Invocations per block | 6,968 / 7,064 / 6,960, as design.json implies; 208 visits each, all completed, no retries |
| Calibration + smoke | 20,992 + 256 = 21,248, each with a unique request ID |
| REPORTs matched by request ID | 21,248 matched, 0 missing; the REPORT log group equals the invoked function in all |
| Log-tail copy against CloudWatch | 7 fields compared, 0 differ |
| Saved coverage files | both complete and in agreement |
| Errors | 0 invocation errors, 0 throttles, 0 function errors, all status 200 (`errors_throttling.csv`) |
| Cold/warm | every cold-batch invocation was cold with an Init Duration; every warm-batch invocation was warm with none |
| Concurrency | max in flight 8 (cap 8) in every block |
| Configuration | the payload's memory, stage, frozen K and `INIT_ROWS = 0` agree in all 21,248 |
| Design and workload | design and workload hashes match the manifest and all run metadata |
| Smoke run | the repository's smoke check passes |

## Calibration data and held-out data (`tables/split.csv`)

The split is by visit, so an invocation belongs either to FIT or to CHECK, never to both.

| Split | Visits per stage and size | Invocations |
|---|---|---|
| FIT | 29 | 15,592 |
| CHECK | 10 (4/3/3 over the three blocks, block order random per cell) | 5,400 |

- The split is stored in design.json and was fixed before any data, as stated under **Plan** above.
- **Every fitted parameter comes from FIT only:** the Eq. (2) and Eq. (3) forms, the "measured" mode, the I/P/X/R
  decomposition and the trend decision.
- **CHECK is used only to test those fits:** each prediction is compared with CHECK's own 95% batch-bootstrap
  interval.
- `timings.csv`, `repeatability.csv` and `billing.csv` are descriptive and use all invocations.

## Measured findings

### Warm Lambda Duration

Median ms over all blocks; n = 1,000 per cell (`timings.csv`, block = all).

| Stage | 512 | 1024 | 2048 | 3008 |
|---|---|---|---|---|
| ingest | 1624.3 | 800.9 | 463.0 | 462.9 |
| transform | 8038.9 | 3993.6 | 2291.6 | 2286.8 |
| aggregate | 5092.5 | 2529.5 | 1451.3 | 1451.1 |
| load | 2453.3 | 1205.4 | 689.0 | 688.4 |

Duration is inversely proportional to memory up to 1024 MB (2.01-2.04× faster). It is 1.73-1.75× faster at 2048 MB,
and no faster at 3008 MB. This fits single-threaded work capped at one vCPU.

### Cold start: Lambda Init Duration and the client-observed first-call penalty

These are reported separately (`decomposition_fit.csv`, FIT split medians, s):

| Quantity | Definition |
|---|---|
| **I** | Lambda-reported Init Duration: the platform's INIT phase, here the runtime and module import only |
| **P** | median cold end-to-end minus median warm end-to-end at the client: the full first-call penalty |
| **X** | cold minus warm Lambda Duration |
| **R** | P − I − X: environment creation and the network |

| Stage | I | X | R | P |
|---|---|---|---|---|
| ingest | 0.114-0.115 | 0.000-0.003 | 0.111-0.117 | 0.226-0.233 |
| transform | 0.114-0.115 | 0.004-0.028 | 0.112-0.119 | 0.234-0.254 |
| aggregate | 0.114-0.116 | 0.286 / 0.146 / 0.081 / 0.080 | 0.111-0.119 | 0.514 / 0.371 / 0.315 / 0.311 |
| load | 0.114-0.115 | 0.002-0.010 | 0.111-0.117 | 0.228-0.241 |

- The aggregate X and P values are listed for 512 / 1024 / 2048 / 3008 MB; the other cells are ranges over the four
  sizes.
- **Lambda Init Duration does not fall with memory in any stage.**
- P falls with memory only in aggregate, and slightly in load. There, X does: the handler's first-call work inside
  Duration is CPU-bound.

### Within-day repeatability

Descriptive, not prespecified (`repeatability.csv`).

| Quantity | Spread across the three blocks |
|---|---|
| Warm median Duration | within 0.41% |
| Init median | 1.0-4.1% apart; block 2 above block 0 in all 16 cells, by 1-5 ms |
| P median | max/min 1.01-1.23. P is measured at the client, so it includes the network |

### Billing

Computed at list price; not the bill (`billing.csv`).

| Item | Value |
|---|---|
| Campaign | 55,234.5 billed GB-s and 20,992 requests |
| Lambda cost at the public us-east-2 list price | USD 0.92 (free tier not assumed) |
| Smoke run | USD 0.012 |
| Excluded | CloudWatch Logs and data transfer |

## Comparison with Eq. (3) (`eq3_comparison.csv`, `trend_compare.csv`, `fits.json`)

**What Eq. (3) models in the simulator:**
- `init_mean(m) = init_mean_1024 × (ns + (1 − ns)·1024/m)`, with `ns = 0.7` and `init_mean_1024 = 6 s`.
- It is the mean initialisation occupancy before service: application start-up included, as a mean.

**Which assumptions match the measurements:**

| Aspect | Matches? | Reason |
|---|---|---|
| Shape against memory (factor relative to 1024 MB) | yes | can be compared for I, P and P_mean |
| Magnitude | no | the workload does no start-up work (`INIT_ROWS = 0`). The submitted 6 s is neither tested nor contradicted |
| I as Eq. (3)'s quantity | no | I is a median of the platform INIT phase only |
| P as Eq. (3)'s quantity | closest | it is the occupancy-like quantity, but a median that includes the laptop's wide-area latency |
| P_mean as Eq. (3)'s quantity | would match the definition | it is the mean, but stalls make it not estimable outside ingest |

**Shape, factor relative to 1024 MB (FIT):**

| Size (MB) | Eq. (3) | I, pooled | P, pooled | P, aggregate | P, ingest / transform / load |
|---|---|---|---|---|---|
| 512 | 1.30 | 1.00 | 1.15 | 1.39 | 0.98 / 1.05 / 1.04 |
| 2048 | 0.85 | 1.00 | 0.93 | 0.85 | 0.99 / 0.97 / 0.98 |
| 3008 | 0.80 | 1.01 | 0.94 | 0.84 | 0.97 / 1.01 / 0.99 |

**Prespecified trend decision on P.** It uses the slope of log P on log memory, from the FIT split with 2,000
batch-bootstrap replicates. Eq. (3) has a slope of −0.273.

| Stage | I slope [95% CI] | P slope [95% CI] | Decision by the plan's rule | P and I trends |
|---|---|---|---|---|
| ingest | +0.005 [−0.003, +0.011] | −0.004 [−0.028, +0.015] | constant (or measured) | no detectable difference |
| transform | +0.007 [0.000, +0.013] | −0.027 [−0.074, +0.034] | constant (or measured) | no detectable difference |
| aggregate | +0.008 [0.000, +0.015] | −0.288 [−0.309, −0.269] | keep Eq. (3); refit | differ |
| load | +0.001 [−0.006, +0.008] | −0.031 [−0.057, −0.002] | keep direction; refit non-scaling share | differ |
| pooled | +0.005 [+0.001, +0.008] | −0.116 [−0.131, −0.100] | keep direction; refit non-scaling share | differ |

**Held-out test (`heldout_check.csv`): 37 of 56 predictions lie inside the CHECK interval.**

| Fit | Result on CHECK |
|---|---|
| Eq. (2) form, warm Duration | **fails at all 16 cells.** Fitted non-scaling share 0.22-0.23; prediction error −10.1% to +13.1%. It cannot follow the plateau at 2048-3008 MB |
| Eq. (3) form for I | fits only at the boundary `init_nonscaling = 1.0`, which is constant (0.114-0.115 s at 1024 MB). Passes for ingest and aggregate; fails at one size each for transform and load |
| "Measured" mode (FIT means per size) for I | passes for ingest, transform and load; fails at one size for aggregate |
| `P_mean` | ingest passes (a constant fit); the other stages are not estimable (flag 3) |

## What the evidence supports

This holds for the declared workload only: on demand, us-east-2, at most 8 in flight, laptop client, one afternoon.

| ID | Supported | Not supported by this evidence |
|---|---|---|
| **R2.8** | (a1) Measured warm execution time against memory. (a2) I, P, X and R per size, separately. (a4) Billed GB-s and requests, measured. (b) Eq. (2) and Eq. (3) forms fitted on FIT and tested on held-out CHECK data. Eq. (2) fails at every size; Eq. (3) holds for Init only as a constant | (a3) provisioned-concurrency activation. Actual charges. Day-to-day variation. Runtime version. Input-size spread. The simulator recalibration itself, which is a separate step: no constant has been changed |
| **R3.1 (a)** | Eq. (3)'s direction on a real platform. Lambda Init Duration is flat in memory. The client-observed penalty P falls at Eq. (3)'s rate only where CPU-bound first-call work dominates (aggregate). Pooled, P falls at −0.116, and the interval excludes −0.273. Eq. (3) must state which quantity it models | (b) the 2-minute activation lag. Start-up behaviour of real applications (no start-up work here). The 6 s magnitude |
| **R6.2** | Cold starts: 4,992 + 128 smoke, all with Init Duration. Per-stage and per-size service times. REPORT billing fields: the Billed Duration rule holds in all 21,248, including the 94 explained +1 ms cases. On-demand concurrency up to 8 with 0 throttles and 0 errors | Activation lag. Provisioned-concurrency behaviour. Overflow or scale beyond 8. The adaptive controller |

**No simulator constant, reviewer status, tracker entry or manuscript text was changed by this package.**

## Files

**Sanitized aggregates only:** no request ID, account number, ARN, raw record or CloudTrail content.

| File | Content |
|---|---|
| `RESULTS.md` | this file |
| `analyse_memcal_run.py` | rebuilds every file below from the private run folder |
| `build_output.txt` | the integrity checks (PASS/FAIL), block times, the prespecified analysis summary and the scan result |
| `sources.sha256` | SHA-256 of the 10 private source files read. The CloudTrail export and the derived archive files are not read |
| `tables/coverage.csv` | coverage and billing-rule counts per block, smoke and total, plus the 24 unmatched REPORTs |
| `tables/errors_throttling.csv` | non-200 status, errors, throttles, function errors and REPORT flags per block × stage × memory (block = 0, 1, 2, all) |
| `tables/timings.csv` | per block × stage × memory: cold and warm counts and batches; Init median, p05 and p95; cold and warm Duration; billed; e2e; P; max memory |
| `tables/repeatability.csv` | warm Duration, Init and P medians for each block, with range and max/min |
| `tables/split.csv` | FIT/CHECK visits and invocations per block |
| `tables/decomposition_fit.csv`, `tables/decomposition_check.csv` | I, P, X, R and P_mean with 95% batch-bootstrap intervals (repository output) |
| `tables/heldout_check.csv`, `tables/trend_compare.csv`, `tables/fits.json` | the prespecified fits and held-out tests (repository output) |
| `tables/eq3_comparison.csv` | measured I, P and P_mean factors relative to 1024 MB against the Eq. (3) factor |
| `tables/billing.csv` | billed GB-s, requests and USD at list price per block, campaign and smoke |
| `tables/client_stalls.csv` | batches with more than 5 s of client overhead |
| `tables/unmatched_reports.csv` | the 24 excluded REPORTs, by function |

## Reproduce

Run this from the repository root. The run folder is private and stays outside Git; any copy whose files match
`sources.sha256` will do.

```
prism-repro/venv/Scripts/python prism-repro/docs/revision/aws_memcal_20261122/analyse_memcal_run.py \
    --run "AWS Live Implementation Log/AWS_memcal_20261122-110627/run" \
    --out <output dir>
```

- **Arguments:** `--run` (the run folder), `--out` (the output folder) and `--boot` (default 2000, as prespecified).
- **What it reads:** only the files named in `sources.sha256`, read-only.
- **What it runs:** the repository's prespecified analysis, `memcal.analyse(run, tmp, n_boot=2000, seed=1)`, into a
  temporary folder.
- **Exit status:** 1 if any integrity check or the sanitization scan fails.
- **Time:** about 3.5 min.
- **Verification:** a rebuild into a fresh directory on 22 Nov 2026 reproduced all 16 generated files byte for byte.
- **Line endings:** the repository's analysis writes `decomposition_fit.csv` and `decomposition_check.csv` with
  CRLF line endings. Git stores them with LF (`core.autocrlf`), so compare a rebuild with a checkout ignoring line
  endings for those two files.
