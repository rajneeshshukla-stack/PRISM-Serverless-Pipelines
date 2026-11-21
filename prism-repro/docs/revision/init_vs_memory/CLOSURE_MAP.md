# Closure map: R1.2, R2.8, R3.1, R4.3, R5.M2, R6.2 (21 Nov 2026)

**Sources:**
- Status reference: `PRISM_Tracker_dispositions_init_memory_verified_20261121-170452.xlsx`.
- Reviewer wording: `review-inputs/detailed review comments.txt`.
- External-data evidence: commit 58da2ff (`rerun_20261121-163247/RESULTS.md`).
- Measurement tools: `prism-repro/aws_measurement/`, prepared and **not run**.

**No status changes:** preparing tools verifies no measurement, so every status below is unchanged.

**Paths to closure:**

| Code | Meaning |
|---|---|
| **V** | already verified; credit kept |
| **OD** | needs PRISM-specific **on-demand** AWS measurement, feasible at the quota of 10 (harness ready; uses proxy workloads until real stage code exists) |
| **PC** | needs **provisioned concurrency**, which cannot be configured at the applied quota of 10 (blocked) |
| **AN** | needs only analysis of existing evidence or simulation, with no AWS |
| **MS** | needs manuscript text (not in this pass) |

## R1.2 (Partially fixed, unchanged)

The reviewer asked about sensitivity to init shortening with memory, and whether memory co-optimisation holds if init
were constant or increasing.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| (a) sensitivity to the init-memory assumption | sweep with every direction | resolved in simulation, pre-calibration (131f024, a4187f7) | final figures at the regeneration | V |
| (b) does co-optimisation hold if init is constant or growing | same sweep, three directions | resolved in simulation, pre-calibration | as (a) | V |
| (c) ground the direction on measurements | measured direction of the cold penalty on PRISM's stages; decision rule applied; `init_mean_measured` filled; sweep re-centred | external data (58da2ff): AWS 2020 reported init flat, cold-minus-warm penalty falling in 5 of 6; Huawei mixed | measurement on PRISM's stages (proxies, since the stages are underspecified); the choice of which start-up placement represents PRISM; then the re-centred sweep | **OD**, then **AN** |

## R2.8 (Not fixed, unchanged)

The reviewer asked to measure warm execution times, initialisation delays, concurrency activation behaviour and
actual cost, and calibrate the model.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| (a1) warm execution times | per-size warm Duration distributions | parameters ready for measured values | warm Duration by memory; with proxies, CPU-bound memory scaling only, not the stages' own distributions | **OD** |
| (a2) initialisation delays | per-size I, P, X, R | external bounds only (58da2ff) | as R1.2 (c) | **OD** |
| (a3) concurrency activation behaviour | provisioned-concurrency activation timing | none | blocked | **PC** |
| (a4) actual cost | measured billed GB-s and requests reconciled with the bill | none | on-demand and request charges measurable; provisioned-concurrency charges blocked | **OD** (partial) + **AN** (reconciliation) + **PC** |
| (b) calibrate the simulators | constants replaced by measured values; regenerated results | parameters ready (`init_scaling='measured'`, `init_max_s`, `lag_min`) | needs (a1) and (a2) | **AN** after **OD** |

## R3.1 (Not fixed, unchanged)

The reviewer asked for a small real run checking Eq. (3)'s direction against reference [8], and the 2-minute lag.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| (a) Eq. (3) direction on a real platform | measured slope of P against Eq. (3) (-0.273) by the stated rule | external: reported init not following Eq. (3)'s size, cold penalty decreasing (historical, not PRISM) | PRISM-specific run | **OD** |
| (b) the 2-minute activation lag | measured provisioned-concurrency readiness time | none | blocked | **PC** |

## R4.3 (Partially fixed, unchanged)

The reviewer asked to ground the constants (init per memory size, activation time, overflow under a burst), and to
run L = 5 and 10.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| (a1) initialisation per memory size | measured per-size I and P | external range only | PRISM-specific run | **OD** |
| (a2) activation time | as R3.1 (b) | none | blocked | **PC** |
| (a3) overflow under a burst | requests above provisioned capacity measured | none | blocked | **PC** |
| (b) L = 5 and 10 minutes | sweep with every family retuned | resolved, pre-calibration (be7a912, a4187f7) | final figures at the regeneration | V |

## R5.M2 (Partially fixed, unchanged)

The reviewer asked for longer lags, init constant or growing, the effect on RQ1, RQ3 and RQ4, or else narrowed
conclusions.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| (a) longer lags | sweep at L = 5, 10 | resolved, pre-calibration | none | V |
| (b) init constant or growing | sweep per direction | resolved, pre-calibration (two traces) | more traces | V, more traces by **AN** |
| (c) effect on RQ1, RQ3, RQ4 | all three reported per lag and direction | partly: cost and weekly compliance per lag; memory choice and cost per direction | **RQ3's matched-compliance comparison per lag and direction has not been run.** It needs only the existing simulator | **AN** |
| (d) otherwise limit the conclusions | not needed if (a)-(c) are reported; else text | as recorded | depends on (c) and on the measured centre | **MS** |
| measured centre (Remaining) | sweeps centred on measured init and lag | none | init: **OD**; lag: **PC** (until measured, the text limits claims to the simulated lag range) | **OD** + **PC** |

## R6.2 (Not fixed, unchanged)

The reviewer asked to measure actual cold starts, activation lag, concurrency, service times and billing.

| Subrequest | Closure criterion | Verified credit | Remaining gap | Path |
|---|---|---|---|---|
| cold starts | per-size I, P, X, R on PRISM's stages | external, historical only | PRISM-specific run | **OD** |
| activation lag | as R3.1 (b) | none | blocked | **PC** |
| concurrency | on-demand concurrency up to the quota; provisioned concurrency behaviour | none | on-demand up to 8 in flight is measurable; scaling beyond the quota and provisioned concurrency are blocked | **OD** (partial) + **PC** |
| service times | per-size warm Duration | none | as R2.8 (a1) | **OD** |
| billing | measured and reconciled | none | as R2.8 (a4) | **OD** (partial) + **AN** + **PC** |

## Summary by path

- **OD**, ready to run once authorised (`prism-repro/aws_measurement/RUNBOOK.md`; about 23,200 invocations, about
  3.8 active hours over 3 days, about $1.15 at the manuscript's non-current prices):
  - R1.2 (c), R2.8 (a1, a2, a4 partial), R3.1 (a), R4.3 (a1), R5.M2 measured init centre, and R6.2 (cold starts,
    service times, on-demand concurrency, billing partial).
  - A proxy run grounds them per start-up placement. Closing them for PRISM's own stages needs real stage code, or an
    author decision that the proxies are the stage model.
- **PC**, blocked at the quota of 10: R2.8 (a3, provisioned-concurrency charges), R3.1 (b), R4.3 (a2, a3), R5.M2 lag
  centre, and R6.2 (activation lag, provisioned-concurrency concurrency).
- **AN**, possible now without AWS: R5.M2 (c), RQ3 matched-compliance per lag and init direction (not run in this
  pass), and more traces for R5.M2 (b). After an OD run: R2.8 (b) calibration, R1.2 (c) re-centred sweep, and bill
  reconciliation.
