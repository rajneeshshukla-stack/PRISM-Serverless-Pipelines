# R3.2: the hybrid histogram baseline. What the sources establish, why faithful reproduction is blocked, the reply draft and an inquiry to the authors (24 Nov 2026)

No experiment was run for this note. It reuses `../hybrid_reproduction_r32_20261124/`, whose plan, criteria and
results are unchanged, and adds a source search. **The inquiry in section 6 is a draft. It has not been sent.**

## 1. The request

Reviewer 3, comment 2: "Published baselines. Section V(C) uses no published controller. Please add, for example, the
hybrid histogram policy of reference 3 to Table V."

Reviewer 3's question 4 adds: "The closest published controllers are discussed but not used as comparison methods."

## 2. Reference [3]

**Not confirmable here.** Rechecked 24 Nov 2026:
- no `.bib`, `.tex` or manuscript file exists in the working tree, in `review-inputs/`, or in any Git ref
  (`v1-submitted`, `main`, `closed-loop`, `phase-e-review` and their remotes).

The reviewer names "the hybrid histogram policy". That policy is defined in Shahrad et al., "Serverless in the Wild",
USENIX ATC 2020, Section 4.2. The author must confirm that [3] is that paper.

**Confirmed later on 24 Nov 2026 (R3.2-only pass).** The author's local copy of the submitted manuscript (the Atypon ReX
PDF of the initial submission, generated 31 Oct 2026; SHA-256 93084205...61962ddf8; not in the repository) lists:
"[3] M. Shahrad et al., ``Serverless in the wild: Characterizing and optimizing the serverless workload at a large
cloud provider,'' in Proc. USENIX Annu. Tech. Conf. (USENIX ATC), 2020, pp. 205-218." Its Table I lists "Hybrid
histogram [3]" with decision "keep-alive, pre-warm". So [3] is the paper used here.

**Also checked then:** arXiv 2003.03423 v1 and v2 (PDFs, text extracted; kept privately). Like v3, they give no
threshold for "Too many OOB ITs" and no minute-level conversion. The alternative published baseline is in
`../optscaler_r32_20261124/`.

## 3. The saved reproduction (locked before running; `../hybrid_reproduction_r32_20261124/`)

**Setup:**
- public Azure Functions 2019 trace, days 1-7, 21,546 applications;
- the paper's simulator: execution time 0, equal memory;
- the policy without ARIMA.

| Check (published value) | Result | |
|---|---|---|
| A1: fixed 10-min, 75th-percentile app cold starts (50.3%) | 52.60% | pass |
| A2: fixed 1-h (25%) | 25.00% | pass |
| A3: no unloading, always-cold apps (3.5%) | 2.84% | **fail** |
| A4: fixed 2-h wasted memory against 10-min ("almost 30% higher") | 1.299 | pass |
| B1: hybrid 4-h wasted memory against fixed 10-min ("the same amount of memory") | 0.877 | **fail** |
| B2: fixed 10-min against hybrid 4-h cold starts ("2.5x") | 2.10 | pass, at the band's low edge |
| B3: fixed 2-h against hybrid 4-h ("roughly the same"; "about 50% more") | −5.0 points; 1.48 | pass, at the band's edge |
| B4: always-cold without ARIMA (10.5%), reported only | 10.29% | — |

**Verdict under the locked rule: not reproduced.** No Table V row was produced.

## 4. What the sources establish (searched 24 Nov 2026)

**The paper (published PDF, Sections 3, 4.2, 5.1; kept privately):**
- ARIMA is used "for applications that have many ITs outside the range of the histogram", and "Too many OOB ITs"
  appears in its Figure 10. **No threshold, and no definition of the series ARIMA is fitted to, is given.**
- The simulation input is "the first week of the trace from Section 3", i.e. the characterisation dataset, which is
  the provider's workload.
- On the released data: "we are releasing a subset of our traces", and "the invocation counts are binned in 1-minute
  intervals, i.e. our dataset does not allow the precise reconstruction of interarrival times that are smaller than
  one minute".
- **The paper does not say how its simulator turned per-minute counts into invocations,** or how it counted
  same-minute invocations.

**The official dataset pages** (github.com/Azure/AzurePublicDataset: `AzureFunctionsDataset2019.md` and
`analysis/AzureFunctionsDataset2019-Trace_Analysis.md`):
- The released trace is "a subset of the data described in, and analyzed, in the USENIX ATC 2020 paper", sampled "per
  application", at a rate that is "small and unspecified".
- The paper's dataset is "in most graphs, the whole workload".
- The trace-analysis notebook shows that the release is "representative" for the characterisation figures (Figures
  1-8). **It does not address Figures 14-15 or the policy.** No policy or simulator code is offered.

**No authors' implementation was found.** Searched: the paper (no code link), the dataset pages, and web search for
an official or author repository. The OpenWhisk implementation described in Section 4.3 is not published with the
paper or dataset.

**Third-party reproductions.** These show what others had to assume. They are not authoritative.
- *andreaskuster/reproducing-serverless-in-the-wild* (GitHub, GPL-3.0):
  - uses ARIMA when an application has more than 3 out-of-bounds idle times, a threshold given no source;
  - takes each invocation's arrival time as its minute index;
  - reports no reproduction numbers.
- *Jounaid, "OpenDC Serverless"* (BSc thesis, Vrije Universiteit Amsterdam, 2020, Zenodo record 4046675, CC-BY 4.0):
  - "Since the OOB threshold parameter is not specified in the original experiment, we arbitrarily set it to a default
    value of 50%";
  - "we have not been able to reproduce the positive memory waste values from Figure 15";
  - it also tracked functions rather than applications.

**Second search (24 Nov 2026, author-controlled sources):**
- **arXiv 2003.03423 v3**, the latest, "Corrected and published in USENIX ATC": the HTML was read in full. It gives no
  ARIMA threshold, no fitted series, and no method for turning counts into invocation times.
- **The USENIX presentation page:** no code or artifact link. The slides were too large to fetch.
- **The ;login: winter 2020 article** (text extracted locally): it repeats the policy's description and gives no
  threshold or conversion. Its one new quantitative claim concerns the CV check ("improved the 3rd-quartile
  application cold starts by nearly 49% with only a 3% increase in memory time wastage").
- **FaaSProfiler** (PrincetonUniversity/faas-profiler; the paper's replay tool): the README and file list show an
  OpenWhisk profiling tool. They show no hybrid policy, no keep-alive simulator, and no conversion of Azure counts. Its
  subdirectories were not opened.
- **Apache OpenWhisk pull requests:** a search for "hybrid histogram" returned none. This is one query, not an
  exhaustive search.

**The closest textual guidance on the trigger.** The paper lists the ARIMA component as being "for when the histogram
does not capture most ITs". Read literally, that means the out-of-bounds share exceeds one half. This is an
interpretation, not a stated rule; the OpenDC thesis's 50% matches it. Even if adopted, the fitted series, the minute
conversion and the workload remain unspecified. So it does not unblock a faithful reproduction, and it was not
implemented.

## 5. The blocker, exactly

A faithful reproduction of the published behaviour needs three things that no public source provides:
1. **The ARIMA trigger and its input:** the threshold for "too many OOB ITs", and the series that is forecast.
2. **The minute-level simulator convention:** how per-minute counts become invocations, and how applications enter
   the evaluation. A3, the share of single-invocation applications, is sensitive to this.
3. **The workload behind Figures 14-15:** the published numbers come from the whole workload. The public trace is an
   unspecified per-application sample of it, so even a perfect implementation may not reproduce the published
   numbers within the locked bands.

The memory comparison (B1) failed here and in the independent OpenDC reproduction. Tuning the open choices until the
published numbers appear would not be a faithful reproduction, so it was not done.

**Still valid, and kept separate:** on the 25 Table V test weeks (`../hybrid_reproduction_r32_20261124/tablev_decisions/`):
- every stage is invoked in every minute;
- the policy keeps each stage's application image loaded throughout;
- that is the same decision as the fixed 10-minute keep-alive the On-demand row assumes, in every week.

This is an equivalence of application-loading decisions only. **It is not a simulated end-to-end comparison, and it
supports no claim of cost or SLA equivalence with the On-demand row.**

**What the policy controls, and how it maps to the pipeline:**
- It sets, per application, a pre-warm window and a keep-alive window for the application's image. It is a provider
  policy, and it sets no instance count.
- Mapped onto the pipeline, each stage would be one application. Its decision is whether that stage keeps a loaded
  image between invocations.
- Instance scaling, and so Table V's quantity, stays the platform's.

## 6. Drafts

*Superseded later on 24 Nov 2026 by `../optscaler_r32_20261124/REPLY_DRAFT.md`, which adds the OptScaler [16]
comparison. The inquiry below is unchanged: final and NOT SENT.*

**Reply draft (R3.2).** This replaces the tracker's current reply only if the author agrees.

> [Identity of [3] to be confirmed by the author.] We implemented the hybrid histogram policy of [3] as specified
> (1-minute bins, 4-hour range, 5th and 99th percentiles, 10% margin, CV threshold 2) and first tested it against its
> published behaviour on the public Azure Functions 2019 trace, with pass criteria fixed in advance. Five of seven
> criteria passed, including the fixed keep-alive behaviour and the direction and approximate size of the
> cold-start reduction (2.1 times fewer cold starts at the 75th percentile, against 2.5 published). Two failed: the
> share of always-cold applications without unloading (2.8% against 3.5%) and the memory comparison, where the policy
> used 12% less idle memory than the 10-minute keep-alive instead of the same amount. An independent reproduction
> also could not reproduce that memory result. Three details are not available from the paper or its dataset: the
> rule that triggers the ARIMA component, how per-minute counts are turned into invocations, and the full workload
> behind the published figures (the public trace is an unspecified sample of it). We therefore do not report a Table V
> row as a reproduced baseline. On every Table V test week each stage is invoked every minute, so the policy keeps
> every stage loaded, the same decision as the platform keep-alive assumed by our On-demand baseline. Because the
> policy decides whether an application is loaded, not how many instances run, it does not address the
> concurrency-provisioning problem that Table V compares. We say this in Section II and give the reproduction attempt
> in the supplement. [Scope statement and supplement: pending; inquiry to the authors: not sent.]

**Inquiry to the authors of "Serverless in the Wild" (final draft, NOT SENT, 24 Nov 2026).** Whether, when and to whom
to send it is the author's decision. Recipient details are deliberately left out.

> Subject: Hybrid histogram policy (USENIX ATC 2020): request for the ARIMA trigger, the simulator's minute-level
> conversion, and the implementation
>
> Dear authors,
>
> We are using the hybrid histogram policy of "Serverless in the Wild: Characterizing and Optimizing the Serverless
> Workload at a Large Cloud Provider" (USENIX ATC 2020) as a published baseline in the revision of a paper on
> serverless provisioning. Following Sections 4.2 and 5.1, we implemented the policy (1-minute bins, 4-hour range,
> 5th and 99th percentiles, 10% margin, CV threshold 2) and the simulator (execution time 0, equal memory, first week)
> on the public Azure Functions 2019 trace, and checked it against criteria fixed in advance. It reproduces the fixed
> keep-alive results of Section 5.2 and the direction of Figure 15, but not the share of always-cold applications under
> no unloading (2.8% against 3.5%), nor the 4-hour hybrid policy's memory equal to the 10-minute keep-alive (we obtain
> 0.88 of it). Three details we could not find in the paper, the arXiv version, the ;login: article or the dataset
> pages are:
> 1. **The ARIMA trigger:** the exact condition for "too many out-of-bounds idle times" (we read "does not capture
>    most ITs" as a majority of ITs out of bounds; is that right?), and the series ARIMA is fitted to (all of an
>    application's idle times, or only the out-of-bounds ones, and over what window).
> 2. **The minute-level conversion:** how the simulator turned per-minute invocation counts into invocation times
>    (all at the start of the minute, spread within it, or otherwise), how invocations in the same minute were counted,
>    and which applications were included (for example, applications with a single invocation in the week).
> 3. **The workload:** whether Figures 14 and 15 can be reproduced from the public sample, or only from the full
>    workload used in the paper.
> 4. **The implementation:** whether the simulator, or the OpenWhisk implementation of the policy, can be shared, or
>    the exact method described, so that we can report the baseline faithfully.
>
> With these, we would rerun our prespecified checks and report the result either way.
>
> Thank you for your time.
