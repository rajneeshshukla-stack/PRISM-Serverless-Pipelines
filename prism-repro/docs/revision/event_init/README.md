# Event-level initialisation protocol (R2.2)

SENSITIVITY, PRE-CALIBRATION; supersedes at recalibration. `scripts/revision/event_init_sensitivity.py`, current code,
one Windows machine; `summary.txt` and `rows.json` here.

**Protocol (one for every policy, open and closed loop).** The event-level week starts with provisioned capacity
ready at minute 0 and no warm on-demand environment or request in flight. Before the week, every policy receives the
same past information: the trace's arrival history (forecasters, conformal state carried from the validation week)
and the fast simulator's history concurrency at the default memory (Static and Scheduled percentiles; Reactive's first
two decisions, whose five-minute look-back reaches before the week). Nothing from the simulated week is available
before it is observed. The fast simulator differs only in warming its on-demand pool from the ten pre-week minutes
(D24); it is not changed.

**Sensitivity.** Stored E1 test-week schedules (seeds 101-103 x {stationary, new_spike} x {PRISM-0.02,
QuantProv_q90-1.0, Reactive-0.6}, 18 trace-policy days) replayed over the first day twice: as the simulator runs it,
and after a 60-minute event-level warm-up in which the trace's last pre-week hour is routed under the first-epoch
decision. The week's requests keep identical draws in both runs. Violating 15-minute windows of the day: identical in
all 18 cases (difference 0 of 96). Cold starts in the week's first hour: +26 on average with the cold start (range -51
to +274). The empty start does not move window compliance; it is kept, and stated.

**Reactive's pre-week look-back** concerns two of 2,016 decisions per week and reads the same history every policy
receives; it is documented, not changed.
