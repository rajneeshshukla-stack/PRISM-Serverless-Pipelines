# Four-stage pipeline: what the paper specifies, the proposed workload, and the author's decisions

**Prepared 21 Nov 2026. Not deployed: no AWS resource has been created and nothing has been charged.**
R6.1 (deployed four-stage pipeline), R2.20 (operational delays, small cloud test), R4.5 (named use case), R2.2
(closed loop), R6.2 and R2.8 (measured constants).

## Sources, and what could not be checked

- **The manuscript text is not in this repository**, so it was not read in this pass. "The paper specifies" below
  means what the repository records from it:
  - `src/prism_repro/config.py` reproduces Supplementary Table S1.
  - `des.py` has the event-level model, with section references in its comments.
  - `ASSUMPTIONS_AND_DECISIONS.md` lists what the manuscript leaves open.
  - `notes/manuscript_proposals.md` quotes and proposes text.
- **Check before relying on this.** Anything the manuscript states about the stages beyond Table S1 should be
  checked against this table. None is recorded in the repository.

## What the paper specifies (as encoded in the repository)

| Item | Specified value | Where | Status |
|---|---|---|---|
| Stage names | ingest, transform, aggregate, load | `config.STAGES` | names only |
| Topology | linear chain; each record runs once through every stage (phi = 1); stage s+1 starts at stage s's finish plus an orchestration delay | `des.py`, `config.stage_demand` | specified |
| What each stage computes | **not specified** | `aws_measurement/README.md` | **decision P1** |
| Record content and size (inputs) | **not specified**: a record is only a unit of arrival | — | **P1, P2** |
| Outputs, and the services read or written | **not specified** | — | **P1, P4** |
| Runtime, language, package, dependencies | **not specified** | — | **P8** |
| Warm execution time | log-normal, mean 0.8 / 4.0 / 2.5 / 1.2 s at 1024 MB, sigma of log 0.30 | Table S1, D01 | specified (statistical) |
| Memory scaling of warm time | Eq. (2), non-scaling share 0.5 | `config.nonscaling` | model |
| Orchestration delay | 0.1 s per stage, sigma 0.30, applied after every stage | `config.overhead_mean`, `des.py` | specified; **the orchestrator is not named (P7)** |
| Initialisation | one stage-independent log-normal, mean 6 s at 1024 MB; Eq. (3) scaling | Table S1, D03 | model; **what start-up code causes it is not specified (P3)** |
| Memory | one size for the whole pipeline, from {512, 1024, 2048, 3008} MB | `mem_options`, `PRISM.decide` | specified |
| Arrivals | synthetic, mean 600 executions/min, diurnal, weekly, spikes, bursts; plus five post hoc Huawei traces (R1) | §V-B, D14 | specified (synthetic) |
| **Deadline** | **14.5 s per record, end to end through all four stages** | `config.deadline` | specified |
| SLA, SLO | a 15-min window complies if attainment is at least 99%; SLO: at most 2% of windows violate | `window_min`, `sla_eps`, §V-C | specified |
| Controller timing | epoch 5 min; telemetry lag 2 min; memory re-chosen every 12 epochs (hourly); keep-alive 10 min | `PipelineConfig`, D05 | specified |
| Controller outputs | per-stage provisioned concurrency P_s and one memory size | `policies.py` | specified; **P cannot be applied at the account's quota of 10** |
| Orchestration fees | excluded from the cost model | D22 | specified |

**Conclusion.** The paper defines the pipeline's *timing* and its *control interface*. It does not define the
*application*: no stage's computation, data, inputs, outputs, services or code. Every handler that is deployed is
therefore a choice; none of them comes from the paper.

## Proposed representative workload: synchronous document ingestion

**Why this workload.** It is the use case drafted for R4.5 (`notes/manuscript_proposals.md` E8, not applied):
"a document-ingestion pipeline that must return a classified, redacted and indexed document to the requesting user
within seconds". It fits what the paper does specify:
- each record carries its own deadline;
- the caller waits for the result, so execution is synchronous;
- there are four sequential stages.

**Implementation.** The handlers are in `handlers/docpipe.py`: one package with four entry points, standard library
only, running as `python3.12` on `x86_64`.

| Stage | Input | Work (real operations) | Output | Paper target (warm, 1024 MB) |
|---|---|---|---|---|
| ingest | envelope: `record_id`, `doc_seed`, `n_words`, `deadline_s` | obtain the document (synthesised deterministically from the seed, standing in for a fetch, P4); NFKC normalise; tokenise; near-duplicate Bloom check with K hash functions; SHA-256 | normalised text (zlib + base64, about 10 KB at the mean size); token and character counts; checksum | 0.8 s |
| transform | ingest's envelope | redact e-mail addresses, phone numbers and ID numbers; MinHash signature with K permutations over word 3-shingles | redacted text; counts of each PII type; signature head and digest | 4.0 s |
| aggregate | transform's envelope | count-min sketch of term frequencies with K rows; 8-class linear classifier over hashed features; top terms | label, class scores, top 10 terms | 2.5 s |
| load | aggregate's envelope | positional inverted-index entry, serialised and zlib-9 compressed into K shards; one write per record to the sink (none / tmp / s3, P4) | index size and digests; the document itself is not returned | 1.2 s |

**Envelope.** Each stage appends a trace entry and logs one JSON line. The trace entry holds:
- the Lambda request ID and the environment ID;
- the cold flag (a new environment) and the module-scope init time;
- wall-clock start and end, and handler seconds;
- memory, input and output bytes.

A new environment also logs an `env_init` line. The envelope is checked against the 256 KB Step Functions payload
limit (fail loudly above 200 KB).

**Calibration.**
- K is fitted per stage on AWS at 1024 MB with a reference document of the mean size, so that handler time equals the
  paper's warm mean (`campaign.calibrate`). It is a linear fit of time against K.
- **K is a calibration multiplier with no meaning of its own.** Its values in the thousands, for example thousands of
  MinHash permutations, are not realistic settings for documents of about 3,000 words. The operations are real, but
  how heavy they are is set by the paper's timing. Pure-Python document processing is milliseconds, while the paper's
  stages take seconds.
- The work is fixed across memory sizes, so the measured durations at 512, 2048 and 3008 MB show Lambda's own
  scaling, as in the measurement harness.

**Spread.** The work is proportional to document length. A log-normal length (mean 3,000 words, sigma 0.30, P2)
therefore gives each stage the paper's log-normal warm-time spread by construction, not as a finding.

**What it adds over the harness's proxies (`aws_measurement/handlers/stage_proxy.py`):**
- data flowing between stages, through the orchestrator, with real payload sizes;
- data-dependent work, and a spread that comes from the input;
- a real per-transition orchestration delay to measure (the paper's 0.1 s);
- an optional I/O sink.

**What it does not add:**
- realistic start-up work, unless P3 sets it;
- realistic I/O, unless P4 adds S3;
- the authors' application.

## Orchestration (`prism_pipeline/asl.py`)

The pipeline runs as a Step Functions **Express** state machine `prism-pipe-docpipe`, started synchronously with
`StartSyncExecution`:
- four Task states, with Resource set to each function's ARN;
- no Retry, so a failure is recorded, not hidden;
- logging OFF, so no extra log group is created.

**Why Express, synchronous.** The caller waits for the result. Express is billed per request and duration, and its
5-minute limit covers the 14.5 s deadline.

**The client-chained executor (`driver.ChainExecutor`)** invokes the four functions in turn. It is used for
calibration and as an orchestration-free reference.

## Adapter to PRISM's controller (`prism_pipeline/adapter.py`)

**The controller interface is unchanged.** The simulator's `start(cfg, n_min, n_epochs)` and
`decide(k, tel) -> (P, memory)` are reused as they are. Three controllers plug in:
- `closed_loop.PolicyController(PRISM, bundle, ...)`;
- `ScheduleController`;
- `PolicyOnly(OnDemand())`, the paper's on-demand **baseline**.

**Telemetry** (`LiveTelemetry`) is built from finished records. For each bin and stage it holds:
- arrivals (stage start times);
- executions served on demand;
- cold starts;
- peak in flight;
- the applied P and memory.

Bins after k·E − L are NaN, so there is no lookahead, and this is tested. Records still running at decision time are
not counted, and their number is logged with each decision. `count_scale` rescales the counts of a thinned replay
(P5).

**Timing** (D05):
- decision k is taken at the end of bin kE − L;
- its configuration is applied at the start of bin kE;
- epoch 0 is applied before the first record;
- `bin_s` is 60 s in paper time, and 12 s in the compressed smallest test (P6).

**Actuation:**
- **Memory:** `UpdateFunctionConfiguration(MemorySize)` on all four functions. All four are polled until Successful,
  and the actuation delay is logged; this is a measured R2.20 overhead. A configuration change retires warm
  environments, so the next calls are cold. This is real Lambda behaviour, and its cold starts are logged.
- **Provisioned concurrency:** record only. The requested P is logged, scaled by `pc_scale` and rounded up.
  `pc_mode="apply"` is refused when the account's unreserved concurrency minus the request is below AWS's minimum of
  100, which a quota of 10 never allows. Applying P would also need published versions and aliases, which are not
  built.

**Tested locally:**
- PRISM itself (`policies.PRISM` through `PolicyController`, seasonal-naive forecaster) decides through the adapter
  from telemetry of a thinned trace replay. It returns finite levels and a valid memory size, and never sees a future
  bin.
- A schedule changes memory exactly at epoch boundaries, with four updates per change.

## Decisions needed from the author before the workload is used

| # | Decision | Prepared default | Why it matters |
|---|---|---|---|
| **P1** | Adopt the document-ingestion pipeline as the representative workload (and E8's text), or supply the real stage code or another application | document ingestion, labelled PROPOSED | Without P1 no result may be called "PRISM's pipeline on AWS". With real code: replace `handlers/docpipe.py`, keep everything else. |
| **P2** | Input size distribution | log-normal, mean 3,000 words, sigma 0.30 | It generates the warm-time spread. A fixed size would leave only platform jitter. |
| **P3** | Start-up work at module scope (`PRISM_INIT_ROWS`) | 0: runtime plus standard library (expected INIT well under 1 s; not measured) | The paper's 6 s mean comes from no code. Set it to approach 6 s, or keep the natural value and report the gap. Lambda's INIT is limited to 10 s (R4.8), and Eq. (3) scaling would put 512 MB near it. |
| **P4** | Source and sink | synthesised input, sink "none" (no S3) | S3 adds a bucket, IAM rights, I/O time and cleanup. The prepared code refuses any sink but "none". |
| **P5** | Arrivals for a PRISM-controlled live run | Poisson 12/min for the smallest test; a thinned trace replay (1/60 or less of 600/min) with counts rescaled for the controller | At quota 10 the paper's rate (about 90 executions in flight) is impossible. Is a thinned, rescaled replay acceptable evidence? |
| **P6** | Time base | compressed (12-s bins, 60-s epochs) for the smallest test | A PRISM-controlled run in paper time needs hours: memory is re-chosen hourly, and the forecasters need history. |
| **P7** | Orchestrator and its cost | Step Functions Express, synchronous; fees outside the paper's cost model (D22) | It decides what the measured per-transition delay means, and whether to report orchestration fees. |
| **P8** | Runtime and language | python3.12, x86_64, standard library | It drives init and CPU scaling. The prices assume x86. |
| **P9** | Which time the deadline applies to | client end to end, from an in-region client (recommended) | A WAN client adds its own latency. `service_s` (AWS clocks) is reported too. |

**What the smallest live test does not need decided.** P1-P3 do not block it: it verifies mechanics with the
prepared defaults. It does not produce numbers for the paper until P1-P3 are decided.
