# Calibration sensitivity and independent per-quantile offsets (R2.11, R7.5)

PRE-CALIBRATION, EXPLORATORY: fast simulator, assumed constants, current code. Forecast-driven results depend on
the platform at identical package versions (NA-1); these come from one Windows machine (`environment.json`:
Windows 11, Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0), not the reference platform.

**Provenance.** `scripts/revision/calibration_sweep.py ... both`, run 21 Nov 2026 08:28:47Z to 09:33:15Z (`run.log`)
in a separate worktree whose `src/`, `tests/` and script are byte-identical to commit 38f0d67 (checked).
`summary.txt` is `python scripts/revision/calibration_sweep.py . docs/revision/calibration --analyse` and regenerates
identically from the committed rows. One row per simulated week: `rows_<part>_<setting>_<seed>.jsonl`.

**Design.** Seeds 101-105; validation week for tuning by the paper's rule (cheapest with validation violating-window
rate at most 2%), four held-out test weeks per trace (20 weeks). Part A varies one calibration setting at a time
around the submitted one (gamma 0.05, clip [-0.3, 0.8], delay 2 epochs, initial offset 0) and retunes PRISM and
QuantProv-q90 under it. Part B compares the submitted shared offset (Eq. (13), driven by q0.99 misses) with
independent offsets per quantile (`PrismConfig.conformal_per_quantile`), with every parameter value on every week,
so that the comparison is also made, post hoc, at matched compliance rather than at matched eps.

## Findings

1. **Clipping bounds do not bind.** Widening the clip to [-0.5, 1.2] gives runs identical to the submitted ones, so
   the offset never reaches the submitted bounds on these traces. Narrowing it to [-0.1, 0.5] caps the offset (mean
   0.364 against 0.392) and lowers test-week compliance (weeks meeting 2%: PRISM 11/20, QuantProv-q90 8/20, against
   12/20 and 11/20).
2. **Update rate and delay move costs by -4.2% to +1.4%** at the validation-selected settings, with weeks meeting
   2% between 8/20 and 14/20. gamma = 0.02 is the largest single effect: PRISM 4.2% cheaper, 8/20 weeks;
   QuantProv-q90 1.4% costlier, 14/20.
3. **The initial offset acts through the selection, not the test week.** It changes only where the replay starts
   (the start of validation); by the test week the offset has converged (mean 0.393 against 0.392). Starting at 0.4,
   close to the level the offset reaches out of sample, the validation week is replayed less conservatively, the
   rule selects cheaper settings (PRISM eps = 0.08 on all five traces), and test-week compliance falls: PRISM 4.9%
   cheaper with 2.26% violating windows and 8/20 weeks; QuantProv-q90 5.8% cheaper, 2.65%, 7/20. The submitted
   zero start therefore biases selection towards conservative settings; this bears on R4.6 / R5.M3 (warm-up before
   validation), see `docs/revision/provisional_split/`.
4. **Independent offsets: a move along the frontier, not a better frontier.** At the validation-selected settings
   they are 6.8% (PRISM) and 5.7% (QuantProv-q90) cheaper, but weeks meeting 2% fall from 12/20 to 6/20 and from
   11/20 to 6/20. At matched compliance (post hoc) they change cost by -1.18% to -0.10% for PRISM and -0.19% to
   +0.12% for QuantProv-q90 (targets 1.0%, 1.5%, 2.0%).
5. **PRISM against QuantProv-q90 at matched compliance (post hoc):** PRISM is 1.07-2.27% cheaper with the shared
   offset and 1.19-3.53% cheaper with independent offsets, negative in most traces where both frontiers reach the
   target. This is a post hoc comparison on test weeks; at the validation-selected settings PRISM is 0.7% costlier
   (1150.1 against 1141.8 USD/week).

**Caveats.** In most traces the rule selects PRISM's largest eps, 0.08, the edge of the paper's grid (3 to 5 of 5
traces in every setting of both parts), so these effects are partly bounded by the grid (KNOWN_ISSUES: grid-edge
audit; weekly compliance). Matched-compliance comparisons interpolate on the frontier over the family's parameter, per trace,
with cost and violating-window rate averaged over the four test weeks; "4/5" in `summary.txt` means both frontiers
reached the target in four traces.
