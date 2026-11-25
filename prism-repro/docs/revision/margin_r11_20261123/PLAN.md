# R1.1(b): candidate operator safety-margin rule, checked out of sample (plan fixed before the analysis, 23 Nov 2026)

**Question.** What uniform margin on every stage's provisioned capacity should an operator add to PRISM's schedule so
that held-out weeks meet the 2% violating-window target in the event-level simulator?

**Input** (no new simulation): `../event_severity_resumed_20261122/rows_R24_*.jsonl`. These hold PRISM's stored
E12-selected schedules on development traces 101-105 in four scenarios (20 weeks), replayed at event level with
uniform margins m in {0, 10, 20, 30, 50}% (`variant == "event"`). Labels: PRE-CALIBRATION, OPEN LOOP, POST HOC replay,
development traces only. C1-C3 and the confirmatory seeds 106-130 are not used, because no margin replay exists for
them.

**Rule family, fixed here.** For a training set of weeks, the candidate margin is the smallest m in the grid at which
at least a fraction q of the training weeks meet 2% (violating-window rate at most 2%). Two criteria are fixed:
- **strict:** q = 1.0, every training week;
- **lenient:** q = 0.9.

**Out-of-sample check, fixed here.** Leave one trace out, five folds. In each fold the rule is chosen on the 16 weeks of
the other four traces and applied unchanged to the held-out trace's 4 weeks. Held-out outcomes never enter the
choice.

**Reported:**
- the chosen margin per fold;
- held-out weeks meeting 2%, out of 20, with a 95% Clopper-Pearson interval;
- the held-out weeks that fail, with trace and scenario;
- the cost of the margin, as the mean relative cost increase over the margin-0 replay of the same week.

**Not claimed.** This is not a margin for AWS Lambda. The event-level simulator uses assumed constants, notably the
modelled 6 s application start-up (P3), and the replay is open loop. A deployment recommendation needs the
calibrated closed-loop evaluation and a live check (R6.1).
