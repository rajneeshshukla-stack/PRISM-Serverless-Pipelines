# R2.7 and R3.2 checked against the locked scope (section M); R2.6 wording (23 Nov 2026)

No new runs. Sources are the saved outputs cited per item.

## R2.7: what the narrowed RQ4 answers, and what still needs a controlled test

The reviewer's comment (Reviewer 2, comment 7) has two parts:
- (i) "Please investigate scenarios where the application workload changes during execution, including shifts in CPU
  intensity, memory demand, function execution time, or initialization latency".
- (ii) "Such experiments would directly test whether dynamic memory optimization provides benefits that cannot be
  achieved through a one-time configuration decision".

**Answered, for fixed regimes only** (`../memadapt/summary.txt`, 7980b69; fast simulator, development traces 101-105,
stationary weeks, Windows, pre-calibration, exploratory):
- **Load-driven memory changes are observed.** PRISM changes memory within a run in response to load: 1.8 changes per
  week at 13 s and 0.2 at 12 s (non-scaling 0.5), none in the other regimes.
- **The baseline is effectively a one-time configuration.** MemAdapt picks one warm-feasible size per regime and
  changes it 0 times per week in every regime.
- **No benefit in those regimes.** At 12-13 s both meet 2% in 5 of 5 weeks with identical violating windows, and PRISM
  costs +27.9%, +19.8% and +8.3% more. MemAdapt sits at the bottom of its grid, so its cost is an upper bound. So, in
  these fixed regimes, PRISM's within-run memory changes give no benefit over a one-time configuration decision.
- **C3** (closed-loop event level, 12 s, Windows, pre-calibration) agrees on cost, but compliance confounds it: PRISM
  +13.06% [+8.50, +17.63], and weeks meeting 2% are 24 against 17 of 25.

**Still needing a controlled test.** Part (i), shifts in execution characteristics within a run, is untested.
Adaptation to changing execution or initialisation times cannot occur in the current method: PRISM and MemAdapt read
those times from the configured latency model (`../r27_within_run_20261123/NOTE.md`, which also gives the prerequisites
and design). Part (ii) is therefore answered only for load-driven changes in fixed regimes, not for changing execution
characteristics.

## R2.6: "It adapts as intended" overstates the evidence

The reply says: "It adapts as intended (1024 MB at the default deadline, 2048 MB in every short-slack regime)". The
baseline never changes memory within a run (0 changes per week in every regime), so "adapts" can be read as within-run
adaptation, which did not happen.

Proposed precise wording: "It selects the intended size in each regime (1024 MB at the default deadline, 2048 MB in
every short-slack regime) and keeps that size for the whole run (no memory change in any test week)."

The same applies to R7.4's "verified to adapt". Proposed: "verified to select the intended size in each regime".

## R3.2: what the cited policy would do on the evaluated traces

**Identity of [3].** The manuscript's reference list is not available locally. No `.bib`, `.tex`, manuscript or
bibliography file exists in the repository or `review-inputs/`, so [3] cannot be confirmed here. The policy the
reviewer names, the hybrid histogram policy, is the one specified in Shahrad et al., "Serverless in the Wild"
(USENIX ATC 2020), as checked against the source PDF on 22 Nov 2026 (`../hybrid_histogram_r32_20261122/README.md`).
The author must confirm that [3] is that paper.

**On the 40 evaluated traces** (`../hybrid_histogram_r32_20261122/hybrid_windows.txt`, reproduced byte for byte on 23
Nov 2026):
- **35 of 40 have no idle minute.** All inter-arrival times fall in bin 0, so the policy sets pre-warm 0 and keep-alive
  1.1 min and never unloads the application. It equals "no unloading".
- **4 Region 2 traces** have idle gaps of at most 2-3 minutes and 0.0000% application cold starts at the reported
  precision. With a 1.1-min keep-alive the application can be unloaded in those gaps, so "never unloads" is not
  claimed for them.
- **1 sparse trace (r2_00)** has 6,512 empty minutes and gaps up to 240 min. The 1.1-min keep-alive unloads the
  application sooner than a fixed 10-min keep-alive, and application cold starts occur: 0.0049% against 0.0005%.
- **On every trace** the policy decides nothing about concurrent instances. The paper's cold starts and costs come from
  instance scaling, which the source excludes ("we do not consider it in this paper").

**Is a head-to-head comparison still called for?** The comment asks to "add ... the hybrid histogram policy of reference
3 to Table V". On every evaluated trace the faithful policy leaves instance scaling to the platform, and it keeps the
application loaded except where requests pause, notably on the sparse trace r2_00, where application cold starts occur.
Table V's On-demand row (no provisioned concurrency, the platform's own instance scaling) is its nearest counterpart,
but the two have not been compared directly, so equivalence is not claimed. A scope statement answers the comment
unless the author prefers the explicit row.

*Corrected 23 Nov 2026 (R6.1 pass): this paragraph previously said the policy "reduces to on-demand execution with the
application always loaded" and that the row would be "identical in kind"; the sparse trace contradicts the first, and
no direct comparison supports the second.*

**Smallest faithful test, if the author wants the explicit row** (not run):
1. **Reproduce the published behaviour first, on its own setting.** Implement the policy as specified:
   - an online per-application histogram with 1-minute bins and a 4-hour range;
   - 5th and 99th percentiles, a 10% margin and a CV threshold of 2;
   - ARIMA with a 15% margin for out-of-range idle times.

   Run it on the first week of the Azure Functions 2019 trace with execution time 0 and equal memory, as in the source.
   Pass if it reproduces the published Figure 15 relation: about 2.5 times fewer application cold starts at the 75th
   percentile than a 10-min fixed keep-alive, at the same wasted memory, for the 4-hour range. The Azure trace is not
   in the repository and must be obtained under its licence.
2. **Then apply the same implementation to PRISM's evaluation**, unchanged:
   - application-level pre-warm and keep-alive windows per stage;
   - instance scaling by the platform's on-demand rule;
   - no tuned parameter, so the common tuning rule selects nothing;
   - the same traces, weeks and simulator as Table V, with cost under the customer bill and violating windows.
3. **Report it as exploratory,** with the expected result stated in advance, as a hypothesis to be tested: the same
   instance decisions as the On-demand row and no application cold start on the 35 traces without idle minutes, and on
   r2_00 more application cold starts than a 10-min keep-alive.

**Remaining.** The author's confirmation of [3]; the choice between the scope statement and the explicit row; and, for
the row, the Azure trace and step 1.
