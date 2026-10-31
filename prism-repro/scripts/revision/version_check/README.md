# Version-sensitivity check (post hoc, Stage 2 correction)

Added during the Stage 2 correction of the manuscript (issues P6 and M15). Not part of the original
evaluation; nothing in `results/raw` was changed.

## 1. Re-simulation under the newer software release (P6)

`resim_check.py` re-simulates the stored E1 test-week runs of the new-spike scenario for traces
(seeds) 101–104 with the current code, in the current environment, and compares each run with its
stored row (cost, violating-window rate, record attainment, late records).

```
python scripts/revision/version_check/resim_check.py --seeds 101,102,103,104 --scenario new_spike
```

Run on 2026-10-30 in the environment of the revision runs (`RUN_MANIFEST_REVISION.json`): Python 3.13.18,
numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, scikit-learn 1.9.1. The stored runs were produced under
`requirements.txt` (Python 3.12.3, scikit-learn 1.8.0). Result (`resim_new_spike_101-102-103-104.json`,
304 runs, about 4 minutes on one core):

| Runs | Number | Bit-identical | Change |
|---|---|---|---|
| Without a learned forecaster (on-demand, static, scheduled, reactive) | 112 | 112 | none |
| Forecast-driven (PredHead, PredHead+S, QuantProv, PRISM) | 192 | 0 | cost: median 0.084%, max 1.490%; violating-window rate changed in 103 runs, by at most 0.744 points |

Exact reproduction of forecast-driven runs therefore requires the pinned versions of `requirements.txt`.
The file reproduced byte for byte the output of the same check made during the Stage 1 audit.

## 2. Source equivalence after the comment update (M15)

M15 updated comments and docstrings in `src/prism_repro` to the V2.6 manuscript numbering. That changes
the source hash that `experiments/run_experiments.py` records with every run (`source_sha256`): the
final code is `8c1710f74c3d…` (E1 seeds 101–103 ran on the earlier source `af08337…`), the commented code is
`d4bad4e2b096…`.
`check_source_equivalence.py` shows that the program is unchanged: with docstrings removed, the syntax
tree of every module is identical.

```
python scripts/revision/version_check/check_source_equivalence.py <root of the 8c1710f code> <root of this package>
```
