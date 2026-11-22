# Grid-edge audit of the stored selections (R4.7, R5.M4(c))

**Scope.** This audits the stored submitted rows, read-only. It applies `scripts/revision/grid_edge_audit.py` (commit
fb8b360), and its output reproduces the counts recorded in `notes/number_audit.md` and `KNOWN_ISSUES.md`.

**Reproduce:**

```
python scripts/revision/grid_edge_audit.py . <rows> --week val|test --out <file>
```

The four audits are listed in `stored_audit.txt`, with one JSON record per selection in `stored_*.json`.

| Stored analysis | Selections at a grid edge | Edges |
|---|---|---|
| E1 validation (paper's selections) | 0 of 40 | none |
| E1 test weeks, POST HOC (test-week knowledge) | 23 of 160 | PRISM eps 0.08 (high) 5x; Scheduled 2.0 (high) 9x; PredHead h 2.0 (high) 6x (5 under the new spike, 1 bursty), with no grid point meeting 2% in any of the six; PredHead+S 2.0 once; QuantProv-q99 0.6 (low) 2x |
| E12 event-level validation retuning (reduced grids) | 6 of 30 | PRISM eps 0.005 (low) on 101-102; PredHead / PredHead+S 2.0 with no point meeting 2% (3x); QuantProv-q90 1.5 (high) |
| R1 real-trace replay, validation | 25 of 40 | PRISM eps 0.08 (high) in 4 of 5 traces; PredHead and PredHead+S h 1.0 (low) in 4 of 5; Static 50 (low) 3x and 99.9 (high) 1x; Reactive 0.9 (high) 3x and 0.4 (low) 1x; Scheduled 1.0 (low) 3x and 2.0 (high) 1x; QuantProv-q99 0.6 (low) 1x |

**Original boundaries** (`experiment.GRIDS`):
- Static 50-99.9;
- Scheduled 1.0-2.0;
- Reactive 0.40-0.90;
- PredHead 1.0-2.0;
- PRISM eps 0.005-0.08;
- QuantProv 0.6-1.5.

**Widened boundaries** (`experiment.GRIDS_WIDE`, fb8b360, which extends both edges of every family):
- Static 30-99.99;
- Scheduled 0.6-3.0;
- Reactive 0.30-1.0;
- PredHead 0.8-3.0;
- PRISM eps 0.002-0.20;
- QuantProv 0.4-2.0.

Reruns on the widened grids are in `../grid_studies/`.
