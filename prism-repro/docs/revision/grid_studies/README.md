# Grid studies in the fast simulator (R2.19, R4.7, R5.M4(c))

**Labels.** PRE-CALIBRATION (assumed constants, Table S1). POST HOC: the test-week analyses use test-week knowledge.
EXPLORATORY.

**Code.** `scripts/revision/fast_grid_studies.py` (new in this pass, uncommitted) on the code of HEAD 78ba419, with
`src/` and `experiments/` clean (`environment_*.json`).

**Platform.** One Windows 11 laptop: 4 cores, Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0.

**Traces.** Seeds 101-105, the paper's five development traces, and the five Huawei arrival traces of R1 (seeds
201-205). The confirmatory seeds 106-130 are not used, and `PRESPECIFICATION.md` is unchanged.

**Why everything is re-run on the current code.** The stored submitted rows (`results/raw`) are not reproduced by
the current code. The causes are exact attainment (1ab053c), the corrections of 33d1000, and the platform (NA-1;
`../table6_versions/`). Mixing stored and new points would therefore mix code versions. The paper's grid (`GRIDS`)
is a subset of the widened grid (`GRIDS_WIDE`), so both are evaluated in the same runs.

**Provenance.**
- The synthetic suite: `--suite=posthoc`, started 22 Nov 2026 05:41:57Z with 3 workers, alongside the event-level
  job. Both jobs were stopped at 05:56Z because seven CPU-bound processes on 4 physical cores ran about 4x slow. The
  synthetic suite then resumed with 5 workers, skipping completed rows (`run_posthoc.log`).
- The real-trace suite: `--suite=real`, started 06:06Z with 3 workers (`run_real.log`).
- The summaries: `--analyse` output on the saved rows, in `summary_posthoc.txt` and `summary_real.txt`.

**Rows.** One JSON row per simulated week, in `rows_posthoc_<seed>.jsonl` and `rows_real_<seed>.jsonl`.

## Design

**R2.19, Reviewer 2's comment 19** ("evaluating additional actual configurations near the relevant SLA targets to
validate the interpolated cost differences ... particularly important for static provisioning").

The paper's matched-compliance method (`matched_compliance_pertrace.py`) works per trace:
- take the mean cost and violating-window rate over the four test weeks for each setting;
- form the lower envelope;
- interpolate linearly at 1.0, 1.5 and 2.0%.

It is applied to the paper's grid for PRISM, QuantProv-q90, PredHead+S, Static and Reactive. Every envelope segment
that brackets a target is then evaluated at five evenly spaced interior settings (for Static, percentiles between 97
and 99) on all four test weeks. Each interpolated cost is compared with two quantities:
- **(i) Refined interpolation:** the same method applied to the refined frontier.
- **(ii) Achievable cost:** the cheapest evaluated setting whose four-week mean rate is at or below the target, that
  is, a configuration that actually exists.

**R5.M4(c), post hoc test-week selections.** Every family is run on `GRIDS_WIDE` in all 20 test weeks. The post hoc
rule (cheapest within 2% on the test week) is then applied twice, with the paper's grid and with the widened grid,
and edges are audited for both.

**R4.7(b), real-trace replay.** The R1 protocol is rerun with every family on `GRIDS_WIDE`:
- forecaster trained on days 1-14;
- the common validation rule on days 15-21;
- test on days 22-28.

Selections with the paper's grid and with the widened grid are audited for edges and compared with the stored R1
selections of the submitted code.

## Results

**Unfavourable and inconsistent items first.**
- **Static's cost was overstated.** The paper's interpolation overstates Static's matched-compliance cost, by up to 6.2%
  against the refined frontier. PRISM's advantage over Static is therefore smaller than the paper-grid interpolation
  says (below).
- **Edges remain on the real traces after widening.** 14 of 40 real-trace validation selections still sit at an edge
  of the widened grid:
  - Static at the 30th percentile (2 traces);
  - Scheduled at 0.6 (3) and 3.0 (1, where no setting met 2%);
  - Reactive at 1.0 (3) and 0.3 (1);
  - PredHead and PredHead+S at 0.8 (1 each);
  - QuantProv-q99 at 0.4 (1);
  - PRISM at eps 0.2 (1, trace 205).

  On these traces the cheapest compliant settings lie beyond even the widened ranges.
- **The post hoc test-week audit does not converge everywhere.** PRISM still sits at the widened grid's top edge
  (eps 0.2) in two weeks (trace 105, stationary and growth).
- **The current code disagrees with the stored submitted rows**, by more edge selections and by a different
  PRISM-against-QuantProv result at 1.0%:
  - edge selections, current code: 28 of 40 in the real-trace validation, 29 of 160 in the post hoc test weeks;
  - edge selections, stored submitted rows: 25 and 23 (`../grid_edges/`);
  - PRISM against QuantProv-q90 at the 1.0% target: 1.9-2.3% cheaper, with an interval that excludes zero, in all
    three estimates; the submitted result is -0.4 +/- 3.3%
    (`../../results/tables/revision/matched_compliance_pertrace.txt`).

  The refinement does not cause these differences; the code version does.

### R2.19: interpolated against evaluated configurations (`summary_posthoc.txt`)

The refinement added 1,140 test weeks: five interior settings per bracketing segment, four weeks each.

Deviation of each estimate from the paper-grid interpolation, range over the five traces:

| Family | Refined interpolation | Cheapest evaluated setting meeting the target |
|---|---|---|
| PRISM | -1.25 to +0.20% | -0.90 to +1.64% |
| QuantProv-q90 | -1.79 to +0.37% | -1.49 to +1.37% |
| PredHead+S | -1.26 to +0.40% | -0.79 to +1.39% |
| Reactive | -1.34 to +0.33% | -0.68 to +0.84% |
| **Static** (grid points 97 and 99 bracket every target) | **-6.24 to -0.27%** | **-5.19 to +1.97%** |

Paired PRISM minus comparator (per trace; mean +/- 95% half-width; paper interpolation -> refined interpolation ->
cheapest evaluated setting):

| Target | vs QuantProv-q90 | vs PredHead+S | vs Static | vs Reactive |
|---|---|---|---|---|
| 1.0% | -2.3 +/- 2.0 -> -1.9 +/- 1.7 -> -2.0 +/- 1.4 | -1.3 +/- 2.7 -> -1.3 +/- 2.7 -> -0.8 +/- 2.4 | -13.0 +/- 6.6 -> -11.0 +/- 7.7 -> -12.3 +/- 8.5 | -23.5 -> -23.6 -> -23.3 |
| 1.5% | -1.2 +/- 1.9 -> -1.4 +/- 2.6 -> -0.8 +/- 2.1 | -0.2 +/- 3.4 -> -0.3 +/- 3.9 -> +0.2 +/- 3.0 | -15.2 +/- 6.5 -> -12.1 +/- 6.6 -> -14.3 +/- 5.7 | -24.0 -> -24.1 -> -25.5 |
| 2.0% | -1.1 +/- 1.9 -> -1.4 +/- 1.5 -> -0.8 +/- 1.7 | +0.4 +/- 3.0 -> +0.1 +/- 3.2 -> +0.5 +/- 3.1 | -16.8 +/- 5.9 -> -13.3 +/- 6.0 -> -15.3 +/- 5.0 | -25.5 -> -25.8 -> -26.5 |

**Sample sizes.** n = 5 traces, except n = 4 for the interpolations at 1.5% and 2.0%: PRISM's frontier on trace 105
does not reach those rates within the paper's grid, while a setting meeting them exists, so the cheapest-evaluated
column keeps n = 5.

**Reading.**
- Interpolated points correspond to achievable configurations to within about 2% for the four adaptive families.
- Static's coarse grid makes the interpolation overstate its cost by up to about 6%, and PRISM's advantage over Static
  shrinks by up to 3.5 points, but its interval still excludes zero at every target.
- No ordering changes. QuantProv-q90 and PredHead+S remain indistinguishable from PRISM at 1.5% and 2.0%.

### R5.M4(c): post hoc test-week selections on the widened grid (`summary_posthoc.txt`)

Edge selections fall from 29 of 160 on the paper's grid to 2 of 160 on the widened grid. Of the 29:
- 18 become interior with the same setting, because the edge value was the optimum: QuantProv-q99 at 0.6 (12),
  PredHead at 2.0 (3), and PredHead+S at 1.0, QuantProv-q90 at 0.6 and PRISM at 0.08 (1 each);
- 9 move to a new interior setting: PRISM eps 0.08 -> 0.15 (5 weeks, 0.9-2.1% cheaper), PredHead 2.0 -> 2.2 (2 weeks,
  where no paper-grid setting met 2%; both meet it now), PredHead and PredHead+S 1.0 -> 0.9 (1 week each);
- 2 move to the new top edge: PRISM eps 0.08 -> 0.2 on trace 105.

The event-level retuning (E12) was not widened. That needs current-code fast-simulator schedules for every grid point
and an event-level replay of each, about 4-9 CPU-hours.

### R4.7(b): real-trace replay on the widened grid (`summary_real.txt`)

- **Edge selections.** Stored R1: 25 of 40. Current code with the paper's grid: 28 of 40. Widened grid: 14 of 40.
- **PRISM.** It moves from eps 0.08 to an interior 0.10-0.15 in three traces (201-203), stays interior at 0.03 on
  trace 204, and reaches the new 0.2 edge on trace 205.
- **Headroom (PredHead+S).** It moves from h 1.0 to interior settings, but sits at the new 0.8 edge on trace 203.
- **Test-week outcomes barely move:**
  - every provisioned family meets the 2% target in 5 of 5 traces except Scheduled (4 of 5), with Reactive moving
    from 4 to 5 of 5;
  - on-demand still meets it in 3 of 5;
  - PRISM's test costs change by at most USD 2.

The replay still cannot separate the families, and the grid edges were not the reason.
