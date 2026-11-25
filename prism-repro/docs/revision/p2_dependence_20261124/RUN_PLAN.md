# P2 sensitivity: independent against shared execution spread (plan fixed before any new simulation outcome, 24 Nov 2026)

EXPLORATORY. Development traces 101-105 only; seeds 106-130 are not used. Closed-loop event-level simulator.
PARTIALLY CALIBRATED: the per-size execution factors are used; start-up (6 s), activation lag, keep-alive and overhead
stay assumed. This is not a confirmatory run.

## Evidence already in hand (before this plan)

`dependence_audit.json`, from the archived live integration run (40 documents, 1,560-5,951 words):
- at 1024 MB, 34 all-warm records: handler time is proportional to document size at every stage (slopes 0.93-1.03),
  and size explains 99.3-99.9% of each stage's log-time variance;
- residual σ_log is 0.009-0.019, and the residuals are nearly uncorrelated across stages (mean 0.04, 95% bootstrap
  [−0.09, 0.14]);
- the total correlation of log stage times is 0.996 [0.993, 0.998].

The saved v_w values (0.24% independent, 3.33% common, at 1024 MB and 14.5 s) reproduce exactly
(`repro_p2_correlation_check.*`).

## Model change (opt-in, isolated calibration build only)

New field `exec_common_frac` = ρ in [0, 1]. Each stage's log multiplier is σ(√ρ·z_common + √(1−ρ)·z_stage) − σ²/2:
- the marginal σ (0.30) and mean (1) are unchanged;
- ρ = 0 is the existing model, **bit-identical** (the common normals come from separate random streams, and are not
  drawn at all when ρ = 0);
- applied at all four draw sites (event draws, fast-simulator draws, the attainment table and the miss table), so the
  world and PRISM's planning model agree.

**Configurations** (all with the per-size factors):
- **IND:** ρ = 0, the current model.
- **SHR:** ρ = 1, one shared factor (the mechanism under P2).
- **MEAS:** ρ = 1 − (σ_r/σ)², with σ_r = 0.0144 (the mean measured stage residual) and σ = 0.30, giving ρ = 0.9977.
  It is run in closed loop **only if** its Monte Carlo v_w at 1024 MB and 14.5 s differs from SHR's by more than 0.25
  points. Otherwise SHR stands for it.

## Runs, one group at a time (2 workers, resumable)

| Group | What it tests | Deadline | Policies and settings | Traces | Weeks |
|---|---|---|---|---|---|
| **G0: regression** | IND in the new build equals the earlier per-size run exactly | 14.5 s | PRISM at K's eps (0.01, 0.01, 0.03, 0.03, 0.03) | 101-105 | 5 (compared with `../calibration_final_20261124/` E14_meas) |
| **G1: fixed, 14.5 s** | Does sharing change outcomes at the default deadline, with settings fixed? | 14.5 s | PRISM at K's eps; MemAdapt-q90 at the closed-loop QuantProv-q90 selections (1.3, 1.5, 1.1, 1.2, 1.2; `../closed_loop_families_20261124/`) | 101-105 | SHR 10, plus IND MemAdapt 5 (IND PRISM is G0) = 15 |
| **G2: retuned, 14.5 s** | Do selections change when each configuration is retuned? | 14.5 s | PRISM over `GRIDS["PRISM"]`; MemAdapt-q90 over `GRIDS["QuantProv"]`; the same rule and edge expansion for IND and SHR | 101-103 | 2 x 3 x (6 + 10 + 2) = 108 (more if edges expand) |
| **G3: fixed, 13 s** | RQ4 and MemAdapt at short slack | 13 s | PRISM eps 0.01; MemAdapt a = 0.6 | 101-105 | SHR 10 (IND is F13 measured, reused from `../calibration_final_20261124/`; G0 shows the build reproduces it) |

**Matching:** the same traces, arrivals and event draws (draw keys by trace and week), the same per-size factors.

## Reported separately

- the warm per-record miss probability v_w(m) under IND, SHR and MEAS (Monte Carlo, 400,000 draws), per memory size and
  deadline;
- the closed-loop violating-window rate per test week.

**Per run:**
- cost;
- violating windows;
- weeks meeting 2%;
- memory shares;
- the selected setting.

**Paired (SHR minus IND):** cost % and violating windows in points, mean +/- 95% t half-width.

## Interpretation rules (fixed now)

- A conclusion changes if, under SHR:
  - a policy's weekly verdict (meets 2%) flips on at least 2 of 5 traces; or
  - a paired cost difference's 95% interval excludes 0; or
  - a selection changes on at least 2 of 3 traces (G2).
- Edge selections are flagged, not resolved.
- **The primary P2 configuration is chosen from the workload mechanism and the archived evidence, not from these
  outcomes.**
- **Checks:**
  - expected weeks present;
  - no failures or duplicates;
  - identical `counts_sha256` per trace, week and scenario;
  - G0 bit-identical.
