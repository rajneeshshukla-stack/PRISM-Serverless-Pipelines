# R2.9: all families on ten less-structured real arrival traces (22 Nov 2026)

**Labels.**
- EXPLORATORY and POST HOC.
- PRE-CALIBRATION: assumed constants, Table S1.
- Fast simulator, under the paper's R1 real-trace protocol.

Only simulator draw seeds 301-310 were used, never 106-130. `../PRESPECIFICATION.md` is unchanged.

**Plan.** `PLAN.md` fixed the selection rule, protocol and metrics before any trace was selected or run. Its SHA-256 and
timestamp (2026-11-22T15:43:30Z) are in `PLAN.sha256`. The run followed it.

**Code and run.**
- `scripts/revision/less_structured_region2.py`, at HEAD ee24766 with `src/` and `experiments/` clean.
- Run 15:44-15:54 UTC, 4 workers, on one Windows laptop (`run.log`).
- One fix to the analysis only: the forecast median APE was first printed multiplied by 100 twice (`metrics.mape`
  already returns a percentage). The rows were not affected, and `summary.txt` is the corrected output.
- `--analyse` also writes `tables/per_trace.csv`, the grid-edge count in `summary.txt` and `selection_public.json`.
  It was extended on 22 Nov 2026 after the run, and re-running it on the saved rows reproduced the earlier table byte
  for byte. No simulation was re-run.

**Reproduce** (from `prism-repro/`; the Region 2 files must be in `../additional data/`):

```
python scripts/revision/less_structured_region2.py . --select "../additional data/huawei_public_2025/R2_minute_metrics/R2/requests" "../additional data/derived/region2_r29" docs/revision/less_structured_r29_20261122
python scripts/revision/less_structured_region2.py . --run "../additional data/derived/region2_r29" docs/revision/less_structured_r29_20261122 --workers=4
python scripts/revision/less_structured_region2.py . --analyse "../additional data/derived/region2_r29" docs/revision/less_structured_r29_20261122
```

**Traces** (`selection_public.json`).
- **Source.** Huawei Public Cloud Trace 2025, Region 2, requests per function per minute (arXiv 2410.06145, EuroSys
  2025). The 28 source files' SHA-256 are in `selection_public.json`.
- **Selection.** 2,418 functions were present on all 28 days. 11 had a mean of at least 600 per minute and requests
  in at least 95% of minutes. The 10 with the smallest sha256(funcID) were taken.
- **Thinning.** Binomial, to 600 per minute.
- **Storage.** The source states no licence, so the following stay local and out of Git:
  - the derived count series, in `../additional data/derived/region2_r29/`;
  - `selection.json`, which names the source function identifiers (funcID).

  `selection_public.json` is the same record without funcID. It keeps the rule, the counts, the source-file hashes and,
  per rank, the thinning, mean, empty minutes and the SHA-256 of the derived counts.

**How the traces meet the request.**
- **No structure is known to the forecaster.** The traces have no designed spikes and no trigger minutes.
- **Irregular bursts.** The 99.9th-percentile-to-median ratio ranges from 2.3 to 39.4.
- **Gaps.** One trace (r2_00) has 6,512 empty minutes, and the minute-count CV ranges from 0.49 to 2.13.
- **Different predictability.** The GBM test-week median APE ranges from 4.8% to 55.8%, against about 12% on the
  synthetic traces (E2) and 4.5-9.7% on the R1 traces.

## Results (`summary.txt`, `tables/per_trace.csv`)

**Unfavourable first:**
- PRISM meets 2% on 7 of 10 test weeks (pooled 1.37%). It misses on r2_00 (3.42%), r2_02 (5.51%) and r2_07 (2.38%).
  QuantProv-q90 misses on the same three.
- On the most irregular trace (r2_00), Static meets the target (0.60%) at USD 255, against USD 563 for PRISM.
- Weeks meeting 2%:

  | Family | Weeks meeting 2% |
  |---|---|
  | Static | 10/10 |
  | Scheduled | 9/10 |
  | Reactive, PredHead, PredHead+S | 8/10 each |
  | QuantProv-q90, QuantProv-q99, PRISM | 7/10 each |
  | OnDemand | 6/10 |

- No cost advantage of PRISM is established. Against every comparator except Scheduled, the paired cost interval
  includes zero:
  - QuantProv-q90: -6.5 +/- 11.3%;
  - Reactive: -7.4 +/- 17.2%;
  - Static: -0.5 +/- 33.9%;
  - PredHead+S: +13.8 +/- 36.7%.
- Against Scheduled, PRISM is 20.5 +/- 10.6% cheaper but has more violating windows (+0.89 +/- 0.79 points; fewer on
  none of the 10 traces), so that comparison is confounded by compliance.
- Forecast difficulty is not associated with PRISM's cost relative to Reactive: Spearman -0.03, p = 0.93, n = 10.
- 55 of 80 validation selections sit at an edge of the paper's grid, which the plan fixed, as in R1. Widened grids
  were not run.

**Reading.** On real traffic that is less structured and differently predictable than the synthetic generator, the
calibrated-quantile families and PRISM behave alike, and none is consistently cheapest at equal compliance. The
predictive cost advantage reported on the synthetic traces is not established here.
