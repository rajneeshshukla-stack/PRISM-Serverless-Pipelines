# R1.2: initialisation time vs memory, compact results

**Exploratory and post hoc. External historical data, not a PRISM measurement.** Produced by
`r12_init_vs_memory.py` (SHA-256 `ce47fa52...`) on 21 Nov 2026. All numbers come from the CSVs in this folder.

Eq. (3) as implemented: init factor `f(m) = 0.7 + 0.3*1024/m`, relative to 1024 MB. That gives x1.30 at 512 MB,
x0.85 at 2048, x0.80 at 3008, and a log-log slope of -0.273 over 512-3008 MB.

The slope is the elasticity of the median with memory (OLS of log median on log memory). Intervals are 95%
bootstrap intervals over cold batches (4-6 batches per size), so they are approximate.

## A. SeBS, AWS Lambda (us-east-1, November 2020), PRISM's sizes 512 / 1024 / 2048 / 3008 MB

| Benchmark (runtime) | Reported init, median at 1024 MB | Init slope [95%] | Init direction | Agreement with Eq. (3) | Cold-minus-warm at 1024 MB | Cold-minus-warm slope [95%] | Cross-check direction |
|---|---|---|---|---|---|---|---|
| 120 uploader (Python 3.7) | 0.144 s | -0.020 [-0.046, -0.002] | decreasing | direction only, much flatter | 0.79 s | -0.29 [-0.43, -0.17] | decreasing |
| 210 thumbnailer (Node.js 10.x) | 0.176 s | **+0.029 [+0.002, +0.055]** | **increasing** | **no** | 1.03 s | -0.46 [-0.54, +1.63] | inconclusive |
| 210 thumbnailer (Python 3.7) | 0.154 s | -0.025 [-0.061, +0.004] | inconclusive | inconclusive | 0.99 s | -0.43 [-0.51, -0.41] | decreasing |
| 311 compression (Python 3.7) | 0.013 s | -0.018 [-0.029, -0.001] | decreasing | direction only, much flatter | 0.89 s | -0.32 [-0.38, -0.26] | decreasing |
| **411 image recognition, large package (Python 3.7)** | 0.135 s | +0.009 [-0.009, +0.023] | **inconclusive (flat)** | inconclusive | **9.67 s** | -0.68 [-0.76, -0.32] | decreasing |
| 503 graph BFS (Python 3.7) | 0.152 s | -0.105 [-0.157, -0.075] | decreasing | direction only, flatter | 0.59 s | -0.35 [-0.53, -0.17] | decreasing |

**Same-day sensitivity.** Some sizes were run on 2020-11-18 instead of 2020-11-11. Keeping only same-day sizes:

- **503:** -0.002 [-0.013, +0.004], inconclusive. Its decrease coincides with the day change: the 2020-11-18
  sizes have init about 0.154 s, the 2020-11-11 sizes about 0.13 s.
- **210 Node.js:** +0.010 [-0.009, +0.020], inconclusive, so its increase is not robust either.
- **210 Python:** stays inconclusive.

Eq. (3)'s ratio to 1024 MB lies inside the bootstrap interval in only 2 of 31 non-reference cells: 503 at 1536
and 2048 MB. Both are ratios to a 1024 MB reference run on the later day, so even that agreement is
day-confounded. See `sebs_by_benchmark_memory.csv`.

**Sample and missingness** (`sebs_missingness.csv`):

- 8,464 cold invocations used; 8,165 carry an init duration and 299 lack it (0-13.3% per cell; the same records
  lack billing).
- 47 cold invocations billed at a different memory than their file's label were excluded.
- Warm baselines: 200-249 invocations per cell.

## B. Huawei Public Cloud 2025 (production, 5 regions, 31 days, standard pools)

**What the field measures.** `totalCost_cold_start` equals pod allocation + code deploy + dependency deploy +
scheduling in 100% of events in every region. Scheduling is the largest share (42-77% by region). The README does
not say the field includes language-runtime start or user init code, so it is a platform provisioning delay, not
Lambda's init duration.

| Region | Events (standard pools) | Within-function evidence (same function at >= 2 memory sizes, >= 20 cold starts each) | Median slope [95%] | Direction |
|---|---|---|---|---|
| R1 | 7,098,514 | 15 functions; 80% decreasing; sign test p = 0.035 | -0.45 [-0.52, -0.17] | decreasing |
| R2 | 1,873,127 | 9 functions; 78% increasing; p = 0.18 | +0.07 [-0.07, +0.74] | **inconclusive** |
| R2 by runtime | Java 6 functions, Python3 3; others 0 | Java +0.19 [-0.03, +0.86]; Python3 +0.04 [-2.28, +0.48] | | **inconclusive** |
| R3, R4, R5 | 308,605 / 1,603,769 / 804,237 | **no function qualifies** | | **no evidence** |

**Cross-sectional medians by memory are non-monotonic and confounded** (`huawei_region_memory.csv`). For example,
R1 at 3072 MB: 8 functions, function-weighted median 34.5 s. R1 at 2048 MB: event median 2.52 s but
function-weighted median 0.23 s.

Custom pools (`custom-<cpu>-<mem>`, 25,909 events) are reported separately. Event medians are 10.4-27.2 s at
every size; they exceed 15 s only in three cells (R2 2560 MB at 15.1 s, R2 10240 MB with 8 events, R4 512 MB with
7 events).
