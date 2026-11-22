# R2.9: less-structured real arrival traces, the plan fixed before any trace was selected or run (22 Nov 2026)

**Labels.**
- EXPLORATORY and POST HOC: designed after the reviews; not part of `../PRESPECIFICATION.md`.
- PRE-CALIBRATION: assumed constants, Table S1.
- Fast simulator: the paper's R1 real-trace protocol.

No confirmatory seed (106-130) is used, and the prespecification is unchanged.

**Reviewer request (R2.9).** "Please evaluate less structured traffic patterns, irregular bursts, unexpected
periodicity changes, and workloads with different levels of temporal predictability."

**Why these traces.**
- **Source:** the Huawei Public Cloud Trace 2025, Region 2, requests per function per minute over 31 days. It is
  described in arXiv 2410.06145 ("Serverless Cold Starts and Where to Find Them", EuroSys 2025) and was downloaded to
  `additional data/huawei_public_2025/R2_minute_metrics/R2/requests/` (listed in `additional data/MANIFEST.tsv`).
- **What they are:** real production arrivals from functions other than the five Huawei Private 2023 traces already
  replayed (R1). They have no designed spikes and no trigger minutes known to the forecaster, and their structure
  varies from function to function.
- **Licence:** none is stated in the downloaded README. The derived traces therefore stay local, in
  `additional data/derived/region2_r29/`, and are not committed. Only counts, hashes and aggregate results are saved
  here.

## Trace selection, fixed now

**Unit.** One `funcID`: funcName---userID---poolName, which the data release says "uniquely identifies a function".

**Window.** Days 0-27, 28 consecutive days. Days 28-30 are unused.

**Eligible.** A function qualifies if:
- its mean is at least 600 requests per minute over the window (thinning to 600 per minute needs a source mean of at
  least 600);
- it has at least 1 request in at least 95% of the minutes.

**Selection.** If more than 10 functions qualify, take the 10 whose `sha256(funcID)` is smallest. This choice is blind
to the outcomes. If 10 or fewer qualify, take all of them.

**Thinning.** Binomial, to a mean of 600 per minute, with seed 20261122 + rank, exactly as `data/real/make_csvs.py`
does for R1.

**Simulator draws.** Seeds 301-310, in selection order; none is in 106-130.

## Protocol: the R1 protocol, unchanged

- The GBM forecaster is trained on days 0-13, with trigger features at zero.
- Every family is tuned on the validation week, days 14-20, by `experiment.select_by_rule` over `experiment.GRIDS`:
  the cheapest setting with at most 2% violating windows, else the least violating. The families are OnDemand,
  Static, Scheduled, Reactive, PredHead, PredHead+S, QuantProv-q90, QuantProv-q99 and PRISM.
- The selection is frozen and run on the test week, days 21-27.
- Every policy sees the same trace, the same draws and the same split.

## Metrics, reported together

**Per trace and family, on the test week:**
- cost (USD/week);
- violating-window rate;
- whether the 2% target is met.

**Paired, PRISM minus each comparator over the 10 traces:**
- cost (%) and violating windows (points);
- mean with a 95% t interval (df 9), and direction counts.

**Per-trace structure and predictability:**
- coefficient of variation of the minute counts;
- daily autocorrelation (lag 1440);
- 99.9th-percentile-to-median ratio;
- the GBM test-week median absolute percentage error and pinball loss at 0.9.

**Exploratory association:** the Spearman rank correlation between forecast error and PRISM's paired cost advantage
over Reactive.

**Reading rules.** A difference is called a difference only if its interval excludes zero. Cost is never reported
without compliance. Adverse outcomes are reported first.
