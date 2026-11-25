# R3.2: hybrid histogram policy, local reproduction attempt (24 Nov 2026). Result: NOT REPRODUCED within the prespecified criteria

EXPLORATORY. No AWS. The manuscript, the submitted results and the frozen protocol are untouched.

`PLAN.md` was fixed before any run, at 03:13:33 UTC, and is unchanged: `sha256sum -c PLAN.sha256` gives OK.

## 1. Result first

**The reproduction failed its own criteria**, under both readings of the keep-alive window (I and II give the same
verdict). Under the plan's decision rule, Stage C, a Table V comparison, was therefore **not run**.

Azure Functions 2019 trace, days 1-7, 21,546 applications; the paper's simulator (execution time 0, equal memory); the
policy without ARIMA (`stage_ab/reproduction.txt`):

| Criterion | Published (Shahrad et al. 2020, Section 5.2) | Here | |
|---|---|---|---|
| A1 fixed 10-min, 75th-percentile app cold starts | 50.3% | 52.60% | pass (band 47.3-53.3) |
| A2 fixed 1-h, same metric | 25% | 25.00% | pass (22-28) |
| A3 no unloading, applications always cold | 3.5% | **2.84%** | **FAIL** (3.0-4.0) |
| A4 fixed 2-h wasted memory / fixed 10-min | "almost 30% higher" | 1.299 | pass (1.20-1.35) |
| B1 hybrid 4-h wasted memory / fixed 10-min | "the same amount of memory" | **0.877 (I), 0.880 (II)** | **FAIL** (0.90-1.10) |
| B2 fixed 10-min / hybrid 4-h, 75th-percentile cold starts | "2.5x" | 2.10 (I and II) | pass, at the low edge (2.0-3.0) |
| B3 fixed 2-h vs hybrid 4-h: cold starts; memory | "roughly the same"; "about 50% more" | −5.0 points; 1.48 (I), 1.48 (II) | pass, at the edge (≤ 5 points; 1.30-1.70) |
| B4 (reported only) hybrid without ARIMA, applications always cold | 10.5% (Figure 19) | 10.29% | — |

**What was reproduced:**
- the fixed keep-alive behaviour (A1, A2, A4);
- the direction of the published result: the 4-hour hybrid policy cuts 75th-percentile application cold starts
  from 52.6% to 25.0% and uses less wasted memory than the fixed 10-minute keep-alive;
- the always-cold share without ARIMA (10.29% against 10.5%).

**What was not reproduced:**
- the magnitude at equal memory: here the hybrid policy uses 12% less memory and achieves a 2.1x reduction, while
  the paper reports 2.5x at the same memory;
- the single-invocation share of applications.

**Post hoc diagnostic (not a verdict).** Counting each active minute as one invocation
(`posthoc_active_minutes/reproduction.txt`) fits the paper much worse: A1 86.35%, A2 42.86%, and B1-B3 all fail. So
the prespecified per-invocation reading is the closer one.

## 2. The exact blocker

The published method leaves two points open. The dataset page offers the trace only, with no simulator or policy
code; no wider search for an implementation was made in this pass.
1. **ARIMA.** The trigger, "too many OOB ITs" (Figure 10), has no threshold, and ARIMA's input series is not
   specified. The published model, `pmdarima` auto_arima, is also not installed here. The paper says ARIMA handled
   0.64% of invocations and was used by 9.3% of applications at least once. Those are infrequently invoked
   applications, so its absence may affect B1 and the 75th percentile, but this was not tested.
2. **The simulator at the trace's 1-minute resolution.** The paper does not say how per-minute counts become
   invocation times, or which applications are included. A3's mismatch (2.84% against 3.5%) shows that the
   application set or the counting differs.

Closing the gap would need either the authors' simulator and policy code, or tuning these choices until the
published numbers appear. Tuning after seeing the results would not be a faithful reproduction, so it was not done.

## 3. Independent checks completed

- **Data availability.** The trace is available from its official source and may be used:
  - release `dataset-functions-2019`, 142,968,140 bytes, SHA-256 aff8b3ca7240a41a…;
  - licence "CC-BY Attribution License", and the dataset page asks users to cite the ATC'20 paper;
  - it is kept privately under `prism-repro/private/` and not committed; only aggregates are reported here.
- **Reference [3].** *Confirmed 24 Nov 2026 from the submitted manuscript's reference list: Shahrad et al., USENIX ATC
  2020, pp. 205-218 (`../r32_blocker_20261124/NOTE.md` section 2).* At the time of this run: not confirmable here, since no manuscript or bibliography is in the repository. The policy is
  the one the reviewer names ("the hybrid histogram policy of reference 3"), defined in Shahrad et al. 2020, Section
  4.2, which was read from the published PDF (SHA-256 d6f71e84…, kept privately).
- **What the policy controls.** Whether each application's image is loaded, through a pre-warm and a keep-alive
  window per application. In the paper's words, it governs "two parameters for each application: Pre-warming window
  … Keep-alive window". It sets no number of concurrent instances.
- **Decision check on the 25 Table V test weeks** (`tablev_decisions/tablev_decisions.txt`). This is not a Table V
  comparison.
  - Each stage is one application, invoked in every minute: at least 98 records per minute, no empty minute, and a
    largest idle time of 1 minute.
  - The policy keeps every stage loaded throughout (pre-warm 0; loaded until 1.1 minutes after each invocation).
  - The platform keep-alive of 10 minutes assumed by Table V's On-demand row never elapses either.
  - So the image-loading decisions are identical on all 25 weeks, with one application cold start each: the first
    invocation.
  - This holds for any keep-alive of at least one 1-minute bin. It therefore does not depend on the magnitudes that
    failed to reproduce, which concern infrequently invoked applications.

## 4. What this supports, and what it does not

**Supported:**
- On the Table V development traces, the cited policy's decisions coincide with the platform keep-alive that the
  On-demand row already assumes, and it decides nothing about instance counts.
- That is an equivalence of application-loading decisions on these traces. It was checked, not simulated.

**Not supported:**
- any claim that the policy was reproduced, since it failed the prespecified criteria;
- any claim of end-to-end cost or SLA equivalence with Table V's On-demand row, since no Table V row was simulated.
  *Corrected 24 Nov 2026: this section previously said the policy "would leave every input of the Table V simulators
  unchanged" and that a Table V row "would repeat the On-demand row's cost and violating windows". That goes beyond
  the decision check, which compared application-loading decisions only.*
- any comparison of PRISM with the policy on traces where idle gaps occur (for example the sparse Region 2 trace
  r2_00, where it unloads sooner than a 10-minute keep-alive);
- any concurrency-control comparison.

## 5. Files and how to rerun (from `prism-repro/`)

- **Policy and simulator:** `scripts/revision/hybrid_policy.py`, with hand-calculated tests in
  `scripts/revision/test_hybrid_policy.py`: 10 of 10 pass.
- **Stages A and B:** `venv/Scripts/python -I scripts/revision/hybrid_reproduction.py <week-1 invocation CSV dir> <out>`;
  add `active_minutes` for the post hoc diagnostic. About 3.5 minutes; Windows, Python 3.12.9, numpy 2.4.4, pandas 3.0.2.
- **Decision check:** `venv/Scripts/python scripts/revision/hybrid_tablev_decisions.py <out>`.
- **Checksums:** `SHA256SUMS`.

## Changes after the run

The criteria are unchanged. Added after the run, both labelled: the post hoc active-minute diagnostic, and the
decision check of section 3, which replaces Stage C because the reproduction failed.

*Checksum note, 24 Nov 2026 (R3.2-only pass): the four `scripts/revision/` lines of `SHA256SUMS` were blanked by a
faulty refresh and rewritten from the scripts as they stand. Their last modification (23 Nov, 21:14-21:23 local)
predates this folder's results and no later pass touched them. Check those four lines from `prism-repro/`, the rest
from this folder.*
