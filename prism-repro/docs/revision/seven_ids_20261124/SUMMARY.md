# Seven-ID pass (24 Nov 2026): R3.2, R4.4, R4.5, R6.1, R4.10, R5.m5, R7.6

**What was not done:**
- no AWS call, deployment, full confirmatory rerun, commit or push;
- no manuscript, supplement or submitted-figure edit.

**Baseline.** The tracker `PRISM_Tracker_dispositions_billing_recon_datefix_verified_20261124-010546.xlsx` (SHA-256
317081511b40e3cc...) has matching copies, and its totals are 0 Fixed, 52 Partially fixed, 20 Not fixed, 1 No change
warranted.

**Kinds of work:**
- **E**, experiment result;
- **R**, readiness check;
- **D**, draft waiting to be applied in the manuscript pass;
- **S**, source search.

| ID | Exact request | Verified this pass (kind) | Artifact | Remaining action |
|---|---|---|---|---|
| R3.2 | "Please add, for example, the hybrid histogram policy of reference 3 to Table V." | **S:** no bibliography in any Git ref, so [3] is unconfirmed. **S:** the paper releases only "a subset of our traces" and specifies neither the ARIMA trigger nor the minute-level conversion. The dataset pages call the public trace "small and unspecified" per-application sampling, and they do not address Figures 14-15. No authors' implementation was found. Two third-party reproductions chose uncited triggers (more than 3 out-of-bounds idle times; 50%), and one could not reproduce Figure 15's memory result. **E** (earlier, unchanged): 5 of 7 locked checks passed; A3 and B1 failed. **D:** a reply that keeps the decision-level equivalence separate from any cost or SLA claim, and an unsent inquiry to the authors. | `r32_blocker_20261124/NOTE.md`; `hybrid_reproduction_r32_20261124/` (its README's cost/SLA overstatement corrected) | Blocked. The author must confirm [3] and decide whether to send the inquiry; a faithful row needs the authors' trigger, conversion and workload. Then the scope statement (M11, M14) and the supplement |
| R4.4 | "Please narrow RQ4 or test it." The caption claim "goes beyond this evidence." | **R** against code and saved results: one shared size, re-decided hourly (`memory_every` 12), not every epoch; the 8-28% cost difference at identical compliance verified in 3 regimes; PRISM at 13 s used 2048 and 3008 MB; the C3 direction corrected. **D:** an edit checklist with 8 locations. | `notes/manuscript_edit_checklist_20261124.md`; M18(1)-(3) | Apply M1/M18(1), M18(2), M3 or M18(3), M4; a decision on whether to report the R2.7 exploratory test |
| R4.5 | "Please name a pipeline with per-record deadlines ..." | **R:** use case (SPEC.md), 14.5 s (`config.deadline`) and the AWS quotes verified. **D:** the M7 citation gap fixed (two pages). | checklist; M18(4) | Apply M7 with M18(4) in Section I, the references, and the evidence sentence |
| R6.1 | "Please validate PRISM on a real FaaS platform using an end-to-end four-stage pipeline." | **R:** current code equals the pinned hashes. The affected checks were rerun: self-test 26 of 26 with unclosed-file warnings treated as errors, and the botocore replay check (32 operations). The 81 unit tests were already run after the last change. Matched inputs, the actual PRISM controller, and requested versus readiness-confirmed versus applied settings are covered by named tests. **D:** the run sheet and a sample-size analysis, which shows the run supports only a small-scale demonstration (2 complete 15-minute windows per arm). | `r61_live_plan_20261123/RUN_SHEET_20261124.md`; `local_verification/*_20261124*` | Commit or freeze the 13 uncommitted harness paths; author authorisation; login and preflight; the live run. Live validation stays open |
| R4.10 | "The graphical abstract should show smoothed headroom at 3.24% next to the 6.67%." | **R:** the draft's inputs equal the Linux T5 new-spike rows exactly; units, intervals and one result set verified; values tabulated for submitted, Windows and Linux. | `graphical_abstract_20261123/`; checklist | The reporting-platform decision, then insert the figure |
| R5.m5 | (a) show 3.24%; (b) "The title on its image ... should match" the article title; (c) narrow the caption's memory claim | **R:** (a) as R4.10. (b) the title equals the `v1-submitted` CITATION.cff and README title; the older title in `__init__.py` is the likely image title. (c) the caption is narrowed; its last clause is conditional on R2.7 (M18(3)); "1 of 5 traces" is Linux-only. | same | Confirm the title in the submission system; the platform decision; insert |
| R7.6 | "... clarify which differences are statistically meaningful and avoid interpreting small numerical differences as established superiority." | **R:** every number in the reply and K7 checked against the full-precision Linux and Windows outputs (intervals, bracketing, trace counts, ±2%, the pooled and change statistics); the K7 C3 phrasing corrected. | checklist; M18(5) | Apply K7 in the Table VII discussion and caption, the abstract and the C3 sentence |

**Status.** No row advances under the tracker's rules. No previously open substantive request is newly satisfied:
- R3.2 is blocked.
- R6.1's live validation is unrun.
- R4.4, R4.5, R4.10, R5.m5 and R7.6 are drafts waiting for the manuscript, which stay at their current status by
  precedent.
