# R3.2: reproduction of the hybrid histogram policy, prespecified before any run (24 Nov 2026, 03:10 UTC)

This plan is fixed before the simulator is written or run. Its SHA-256 is recorded in `PLAN.sha256` at that time,
and any later change is listed at the end under "Changes after the run". EXPLORATORY. No AWS. The manuscript is not
touched.

## Sources

- **Method.** Shahrad et al., "Serverless in the Wild: Characterizing and Optimizing the Serverless Workload at a
  Large Cloud Provider", USENIX ATC 2020. PDF from usenix.org, read 24 Nov 2026. It is kept privately and is not in Git:
  `atc20-shahrad.pdf`, SHA-256 d6f71e84219f576b8f0c368781a274a2150214985795c9bafa73dd25a4081006.
  - Section 4.2: the policy.
  - Section 5.1: the simulator.
  - Section 5.2, Figures 14, 15 and 19: the published behaviour.
- **Data.** Azure Functions 2019 trace, from its official source: the GitHub release
  `dataset-functions-2019/azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz`, 142,968,140 bytes, SHA-256
  aff8b3ca7240a41a109e4ee598e0a96e45fcb92e7b8395ac19cb3748cd260d89, downloaded 24 Nov 2026 03:04 UTC.
  - Licence: "The data is made available and licensed under a CC-BY Attribution License" (AzureFunctionsDataset2019.md).
    The dataset page asks users to cite the ATC'20 paper. The LICENSE file returned HTTP 503 when fetched.
  - The data is kept privately (`prism-repro/private/`) and is not committed.
  - Only derived aggregates are reported, with the citation.
- **Reference [3].** No manuscript or bibliography exists in the repository, so this cannot be confirmed here. The
  reviewer names "the hybrid histogram policy of reference 3", and that policy is the one defined in the paper above.
  The author must confirm that [3] is this paper.

## The policy as published (Section 4.2), and the choices that the text leaves open

**Specified:**
- per application, a histogram of idle times (ITs) with 1-minute bins and a 4-hour range; longer ITs are out of
  bounds (OOB);
- pre-warming window = 5th percentile, rounded down to a bin edge, minus a 10% margin;
- keep-alive window from the 99th percentile, rounded up to a bin edge, plus a 10% margin;
- representativeness: the CV of the bin counts; if CV < 2 ("we opt for CV=2"), or before the histogram can be
  representative, the policy reverts to "pre-warming window = 0 and keep-alive window = range of the histogram";
- updated after each invocation (online);
- ARIMA with a 15% margin when there are "too many OOB ITs".

**Not specified, so these choices are fixed here:**
1. **ARIMA trigger.** "Too many OOB ITs" is given no threshold, and the published model (`pmdarima` auto_arima) is
   not installed. ARIMA is **not implemented**, so the reproduction is of the policy without ARIMA. The paper reports
   that ARIMA handled 0.64% of invocations and is used by 9.3% of applications at least once (Figure 19 text). On the
   Table V traces no IT reaches 4 hours, so ARIMA would never act there.
2. **Keep-alive window when pre-warm > 0.** The keep-alive window "starts after each pre-warming". It is not stated
   whether its length is the tail itself or the tail minus the pre-warm. Two interpretations are run:
   - **I (primary):** the image stays loaded until 1.1 x tail after the execution, so the keep-alive length is
     1.1 x tail − pre-warm;
   - **II:** the keep-alive length is 1.1 x tail, counted from the pre-warm load.

   With pre-warm = 0 the two are identical.
3. **Not enough ITs.** With no in-range IT, the histogram is not representative (standard keep-alive). Beyond that,
   the CV rule decides.

**Simulator (Section 5.1):**
- one image per application (HashOwner, HashApp), invocation counts summed over its functions, first week (days
  1-7, 10,080 minutes);
- execution time 0; equal memory per application; the first invocation is cold;
- wasted memory time = time loaded without executing, summed over applications, normalised to the fixed 10-minute
  keep-alive.

**Timing:** the trace is per minute, so every invocation of minute m is placed at time m. Same-minute invocations
have IT 0. The windows used for an invocation are those computed from the ITs observed before it. Same-minute
invocations after the first use the windows at the start of that minute, which is an approximation. A loaded window
that is still open at the end of the week is cut at the end.

**Metric:** per-application cold-start percentage, and its 75th percentile across applications ("From now on, we
will focus on this metric (i.e., 75th-percentile) to report cold starts").

## Pass criteria (from the paper's text; fixed now)

**Stage A: trace and simulator fidelity, fixed policies (Section 5.2, Figure 14 text).**

| | Published | Pass if |
|---|---|---|
| A1 | fixed 10-min, 75th-percentile app cold starts "50.3%" | 47.3-53.3% |
| A2 | fixed 1-hour: "goes down to 25%" | 22-28% |
| A3 | no unloading: "3.5% of applications with 100% cold starts" | 3.0-4.0% |
| A4 | fixed 2-hour: "almost 30% higher wasted memory time than the 10-minute baseline" | ratio 1.20-1.35 |

**Stage B: hybrid policy, 4-hour range, [5, 99], margin 10%, CV 2, no ARIMA (Figure 15 text).**

| | Published | Pass if |
|---|---|---|
| B1 | 4-hour hybrid uses "the same amount of memory" as fixed 10-min | wasted memory ratio, hybrid / fixed 10-min, 0.90-1.10 |
| B2 | fixed 10-min has "2.5x more cold starts at the 75th-percentile" | ratio, fixed 10-min / hybrid, 2.0-3.0 |
| B3 | fixed 2-hour gives "roughly the same percentage of cold starts" and "consumes about 50% more resources" | 75th percentiles within 5 points, and wasted memory ratio, fixed 2-h / hybrid, 1.30-1.70 |
| B4 (reported, not a criterion) | Figure 19, hybrid without ARIMA: 10.5% of applications always cold | — |

**Decision rule:**
- **The reproduction passes** if A1-A4 all hold, and B1-B3 all hold under interpretation I or II. If both pass, I
  is used downstream.
- **If Stage A fails,** the trace processing or simulator does not match the paper. Stage B is reported, but not
  used.
- **If Stage B fails under both interpretations,** the policy is not reproduced, and Stage C is not run as a Table V
  comparison.

Hybrid ranges of 1, 2 and 3 hours (Figure 15) are reported without criteria, because their published values are
only plotted.

## Stage C, only if the reproduction passes: Table V development traces

**What the policy controls.** Whether an application's image is loaded (one image per application), through its
pre-warm and keep-alive windows. It is a provider-side policy: users "do not pay for resources they do not use". It
sets no number of concurrent instances: load-spike cold starts are excluded ("we do not consider it in this
paper").

**Mapping to the pipeline.** Each stage is one application. A stage's invocation times are the record arrivals
(stages take seconds, below the trace's 1-minute resolution). The unchanged policy, as reproduced, runs per stage on
the minute-count series of the 25 Table V test weeks (development traces 101-105 x five scenarios). The policy is
compared with what Table V's On-demand row assumes: the platform keeps an idle environment for `keepalive_min` = 10
minutes, and instance scaling is the platform's.

**Measured per trace and stage:**
- the policy's windows over time;
- minutes in which the policy would hold the stage's image while the platform's 10-minute keep-alive would not, and
  the reverse;
- application cold starts under each.

**What it can support:**
- If the two never differ, the hybrid policy's decisions change no cold start and no cost in the Table V
  simulators, so its Table V row would equal the On-demand row on these traces. That is then a measured equivalence
  of decisions, not an assumption.
- If they differ, the minutes and stages are reported. A Table V row would then need the simulators extended with
  per-stage image state, which is not done in this pass.

**What it cannot support:**
- any statement about concurrency control;
- behaviour on sparse traces outside Table V;
- provisioned-concurrency comparisons.

## Changes after the run

(none yet)
