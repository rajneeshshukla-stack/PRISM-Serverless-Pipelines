# R3.2: the cited hybrid histogram policy, checked against its source and against the paper's workloads (22 Nov 2026)

**Reviewer 3, comment 2 (verbatim).** "Published baselines. Section V(C) uses no published controller. Please add, for
example, the hybrid histogram policy of reference 3 to Table V."

The manuscript's reference list is not in the repository, so it is assumed that [3] is Shahrad et al., "Serverless in
the Wild: Characterizing and Optimizing the Serverless Workload at a Large Cloud Provider", USENIX ATC 2020. **The
author must confirm this.** Checked 22 Nov 2026: the submitted manuscript and its bibliography are not in the working tree, in `review-inputs/` or in any Git ref (`v1-submitted`, `main`, `closed-loop`), so the identity of [3] is **unverified**. Nothing here
reproduces the published baseline.

**Source.** The public PDF from usenix.org (`atc20-shahrad.pdf`), fetched 22 Nov 2026, SHA-256
d6f71e84219f576b8f0c368781a274a2150214985795c9bafa73dd25a4081006. It is not stored in the repository (copyright).
The text was extracted with `pdftotext`, and the quotations below are taken from it.

## What the source specifies (verified)

**What it decides (Section 4.2).** "Ultimately, the policy defines the pre-warming and keep-alive windows for each
application." It "removes/unloads the application right after each function execution ends, reloads/pre-warms the
application right before a potential next invocation ... and keeps it alive for a period".

**Histogram (Section 4.2):**
- "We use 1-minute bins".
- It tracks "ITs of up to a configurable duration (e.g., 4 hours)".
- Head and tail are "the 5th- and 99th-percentiles of the IT distribution", rounded down and up respectively.
- There is a "10% 'margin' by default".

**Fallbacks (Sections 4.2 and 5.2):**
- If the CV of the bin counts is below a threshold, the policy uses "pre-warming window = 0 and keep-alive window =
  range of the histogram". The default threshold is "CV=2".
- ARIMA, with a 15% margin, handles out-of-bounds idle times.

**Concurrency (Section 2).** "Cold starts can also happen if there is a spike in the load to an application, and new
instances have to be allocated quickly. ... only a tiny percentage (<1%) of applications would experience this type
of cold start. For this reason, we do not consider it in this paper."

**Whose cost (Section 1).** "FaaS users do not pay for resources they do not use." The provider bills "users just for
their actual function executions". "Providers seek to achieve high function performance at the lowest possible
resource cost."

**Evaluation (Section 5):**
- A simulator that "generates an array of invocation times for each unique application". It simulates "function
  execution times equal to 0" and gives every application the same memory.
- Input: "the first week of the trace from Section 3" (the Azure Functions trace).
- Metric: application cold-start percentage against "wasted memory time", normalised to a 10-minute keep-alive.
- Published result: "the 10-minute fixed keep-alive policy involves 2.5x more cold starts at the 75th-percentile while
  using the same amount of memory as our histogram with a range of 4 hours" (Figure 15).

**Motivation (Section 3, Figure 5a).** 81% of applications average at most one invocation per minute, and 45% at most
one per hour.

## The policy on the paper's workloads (`hybrid_windows.txt`, `.json`)

**Script.** `scripts/revision/hybrid_histogram_check.py` implements the window rule above offline, at minute
resolution, on 40 traces:
- the development synthetic traces 101-105 in all 5 scenarios;
- the five Huawei Private 2023 R1 traces;
- the ten Region 2 traces of `../less_structured_r29_20261122/`.

**Approximation.** Inter-arrival times inside active minutes count as under one minute, and the histogram is built
over the whole trace rather than online. ARIMA is not reproduced, because no idle time reaches the 4-hour range.

**Reproduce** (from `prism-repro/`):

```
python scripts/revision/hybrid_histogram_check.py . "../additional data/derived/region2_r29" docs/revision/hybrid_histogram_r32_20261122/hybrid_windows.txt
```

**Results:**
- **Synthetic traces:** every minute has at least 98 arrivals, and no idle time reaches one minute.
- **R1 traces:** no empty minute.
- **Region 2 traces:** up to 9 empty minutes per trace, except trace r2_00, which has 6,512.
- **Policy decision:** identical on all 40 traces: pre-warm 0 and keep-alive 1.1 minutes, from a representative
  histogram.
- **App-level cold starts:** at most 0.005% under the policy, and at most 0.0005% under a fixed 10-minute keep-alive.

On the 35 traces with no idle minute the policy therefore never unloads the application, which is the paper's "No
Unloading" case. On the sparse Region 2 trace r2_00 (6,512 empty minutes, idle gaps up to 240 minutes) it does unload
it, and application cold starts occur: 0.0049% under the policy against 0.0005% under a fixed 10-minute keep-alive. On
the other four Region 2 traces (idle gaps of 2-3 minutes) the application cold-start rate is 0.0000% at the reported
precision. On every trace the policy decides nothing about how many concurrent instances to provision, which is the
decision PRISM and every Table V family make.

*Corrected 23 Nov 2026: this paragraph previously said that the policy never unloads the application on these
workloads, which the sparse trace r2_00 contradicts.*

## Disposition

**Faithful reproduction is blocked by the specification, not by effort.**
- The policy excludes the scale-out cold starts that provisioned concurrency addresses, and specifies no rule for
  multiple instances.
- It minimises the provider's wasted memory, which the customer bill in the paper's cost model does not contain.
- Its published characteristic needs the Azure Functions 2019 trace, which is not in the repository.

**What an implementation would amount to.** Applying its keep-alive window to each Lambda environment would be our own
extension, not the cited method. With windows of 1.1 minutes, the only effect would be to shorten keep-alive relative
to Lambda's.

**Recommended.**
- Option (c) of D2: a scope statement in Section II.
- Option (d)(1): present Reactive as the provider's target-tracking rule, if that is checked against the AWS
  documentation. This has not been checked.

The comparison R3.2 asks for stays open, pending the author's decision.
