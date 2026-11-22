# Event-level severity and modelling factors, completed (R2.4, R7.2; R1.1 evidence)

**Labels.**
- PRE-CALIBRATION: assumed constants (Table S1).
- POST HOC.
- OPEN LOOP: the stored E1 schedules are replayed through the current event-level code, as the paper's E9 (Table X)
  and E12 (Table XI) did.
- Simulation only.
- Seeds 101-105 only. The confirmatory seeds 106-130 are unused, and `../PRESPECIFICATION.md` is unchanged.

**Why this folder exists.** The original run in `../event_severity/` stopped at 01:44 CST on 22 Nov 2026, when the
laptop entered Modern Standby; a Windows Update restart followed (see
`../verification_20261122/VERIFICATION.md`). That folder is left untouched. This folder holds the resumed and combined
rows.

**Provenance.**
- **Copies.** All 24 row files of `../event_severity/` were copied here; `ORIGINAL_ROWS.sha256` is the hash list of
  the originals. After the run, each original file is a byte prefix of its copy here, so no saved row changed.
- **Inventory before resuming.** The expected design is 228 rows (`jobs_for` in
  `../../../scripts/revision/event_severity_factors.py`, with the stored E12 and E9 labels). Of these, 187 were saved
  and valid, with no duplicates and no truncated lines, and 41 were missing:
  - R24: trace 105 new spike, 30% and 50% margins;
  - R72: 39 replays.

  17 further rows come from the design before its trim at 06:28Z on 22 Nov (PredHead+S, Static, a combined
  counterfactual and 5% or 15% margins on trace 101). They are kept, and the analysis does not table them.
- **Compatibility.** Three saved rows were recomputed in a scratch folder with the current script: one pre-trim
  counterfactual (R24 101 stationary, initialisation instantaneous) and two post-trim rows (R24 104 bursty at a 20%
  margin; R72 101 stationary as is). Every field matched, except `runtime_s` and NaN (an empty-set mean) compared
  with NaN.
- **Run.** The 41 missing replays ran with `--workers=4`, from 12:53:22Z to 13:04:38Z on 22 Nov 2026, at HEAD
  78ba419 with `src/` and `experiments/` clean (`environment.json`, `run_resumed.log`). Each replay is written and
  flushed as it finishes. Afterwards, all 228 design rows are present exactly once.
- **Platform.** One Windows 11 laptop, Python 3.12.9, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0.

**Reproduce** (from `prism-repro/`):

```
python scripts/revision/event_severity_factors.py . docs/revision/event_severity_resumed_20261122 --workers=4
python scripts/revision/event_severity_factors.py . docs/revision/event_severity_resumed_20261122 --analyse
```

The first command skips every key already present. The second writes `summary.txt`.

## Results (`summary.txt`)

**Reproduction.** The current code reproduces the stored violating windows:
- Table XI (E12) in 60 of 60 replays;
- Table X (E9) in 12 of 12.

Costs are within USD 0.005.

**R2.4, the 20 Table XI weeks.**
- **Unchanged from the partial analysis**, which is kept in
  `../verification_20261122/event_severity_summary_partial_rows.txt`:
  - PRISM misses 7 of 20 weeks;
  - no two violating windows are consecutive;
  - the worst window's attainment is 93.8-98.1%;
  - 249 of the 271 violating windows contain a random burst;
  - with initialisation instantaneous, or keep-alive unlimited, all 20 weeks meet the target.
- **Completed here, uniform capacity margins** (ESTIMATED by counterfactual replay):

  | Margin | Weeks meeting 2% | Cost |
  |---|---|---|
  | 10% | 16/20 | +6.1% |
  | 20% | 17/20 | +11.8% |
  | 30% | 19/20 | +17.7% |
  | 50% | 20/20 | +29.2% |

**R7.2, the 12 Table X weeks.** PRISM's violating windows:

| Model | Violating windows |
|---|---|
| fast simulator (stored) | 1.44% |
| event level | 3.75% |
| event level, initialisation instantaneous | 0.00% |
| event level, keep-alive unlimited | 0.19% |
| event level, both | 0.00% |

Either factor alone removes more than the whole gap (162% and 154% of it). In the simulator, then, the event-level
excess comes from cold starts. The two factors are not additive shares, because both act through cold starts.

Three mechanisms were not separated from one another: environments occupied while initialising, the latency
initialisation adds to a request, and downstream dependency. Nothing here measures the effect on a real platform.
