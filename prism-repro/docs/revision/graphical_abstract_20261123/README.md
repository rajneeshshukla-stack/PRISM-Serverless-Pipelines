# Graphical-abstract draft from one labelled result set (R4.10, R5.m5; 23 Nov 2026)

A standalone draft, not the manuscript figure: `graphical_abstract_draft.svg` and `.png`, with `caption_draft.txt` and
`inputs.csv`. Built by `make_graphical_abstract.py`, which reads every value from its source table and asserts it
before drawing. The build log is in `build_output.txt`.

**Result set.**
- Code: current (fd8b01a plus 6e0f05c).
- Platform: Linux x86-64, Python 3.12.3, the pinned packages. This is the platform on which the submitted results
  reproduce exactly (`../label_fix_20261123/`).
- Fast simulator, PRE-CALIBRATION, five development traces, new-spike test week.
- One platform and one code version for the headline and the caption.

| Value | Source | Value used |
|---|---|---|
| Violating windows: PRISM, smoothed headroom, unsmoothed headroom | `../label_fix_20261123/outputs/linux_tables/T5_test_weeks.md` (Table V), new_spike | 2.62 +/- 1.50, 4.02 +/- 2.67, 7.62 +/- 2.31% |
| Weekly cost, same rows | same | USD 1,241 +/- 135, 1,157 +/- 74, 1,082 +/- 66 |
| PRISM meets 2% | same, "SLO met" | 1 of 5 traces (20%) |
| 2048 MB headroom against PRISM's best setting, short-slack regimes (13, 12 and 11 s at non-scaling 0.5; 12 s at 0.15) | `linux_e4b/E4b_fixed_memory_summary.json` (Table S14 analogue) | 13.03-27.21% cheaper |
| Default deadline (14.5 s) | same | headroom costs 32.04% more (non-scaling 0.5) and 1.89% more (0.15) |
| PRISM's best settings at 2048 MB or more | same, `share_ge2048` | 100% of epochs in every short-slack regime |

**Linux E4 and E4b (run 23 Nov 2026 for this draft; `linux_e4b/`).**
- E4 for seeds 101-102, then `e4b_fixed_memory.py`, `e4b_ondemand.py` and `e4b_prism_eps.py` per seed, in the fixed
  tree on Linux; every step exited 0 (`linux_e4b/run.log`).
- Row counts equal the Windows regeneration and the submitted ones: E4 172; E4b 232, 12 and 36 per seed. The input
  hashes are in `linux_e4b/inputs.sha256`.
- `analyze_e4b.py` selects PRISM by the literal `'PRISM'`, so it first failed on the raw `PRISM_EB` rows (a known
  limit of `scripts/revision/`). It ran on a copy relabelled by `../label_fix_20261123/tools/normalize_labels.py`: 9
  files, 308 strings (`linux_e4b/raw_normalization_manifest.json`).

**Title.** The image title is the article title in `prism-repro/CITATION.cff`. Check it against the submission system.

**Colour.** The reference palette's first three categorical slots: blue `#2a78d6`, orange `#eb6834`, aqua `#1baf7a`.
These are documented as passing the all-pairs colour-vision checks in light mode. The palette validator could not be
re-run here, because Node.js is not installed. The figure is a static print draft, so it has no hover layer, and
`inputs.csv` is its table view.

**What would change:**

| Change | Effect |
|---|---|
| Reporting on Windows instead | 2.11 / 4.11 / 7.92%, USD 1,270 / 1,150 / 1,077, caption range 13-27% (`../graphical_abstract_20261122/`) |
| Reporting the submitted values | 1.55 / 3.24 / 6.67%, 14-29% |
| The calibrated rerun (measured constants) | every value |

The ordering, both headroom rules cheaper and PRISM least violating but above 2% on average, is the same in the Linux
and Windows regenerations. In the submitted values PRISM was below 2% (1.55%).
