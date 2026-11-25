# R3.2 reply draft (24 Nov 2026; for the author's review; replaces the tracker reply only if the author agrees)

> We tried both routes. The hybrid histogram policy of [3] (Shahrad et al., USENIX ATC 2020) was implemented as
> specified and tested against its published behaviour on the public Azure Functions 2019 trace, with criteria fixed
> in advance. It reproduced five of seven checks, but not the always-cold share without unloading (2.8% against 3.5%)
> nor the memory comparison (12% less idle memory than the 10-minute keep-alive, instead of the same). The ARIMA
> trigger, the minute-level conversion and the full workload are not published, so we do not report it as a
> reproduced baseline. It also decides whether an application is loaded, not how many instances run: on every Table V
> week each stage is invoked every minute, so it keeps every stage loaded, as the platform keep-alive assumed by our
> On-demand row already does.
>
> We therefore added OptScaler [16], a published chance-constrained capacity controller evaluated on the Azure
> Functions trace. No code is released, so we implemented it from the paper. We mapped its utilization to
> provisioned-concurrency utilization per stage and gave it the same forecasts, traces, prices and SLA metric as
> every Table V row; the mapping, tests and commands are in the supplement. At its published target (c* = 0.5,
> alpha = 0.95) it met the 2% target on every trace and scenario, at 30-40% higher cost than PRISM (PRISM cost 23-28% less), with 1.2-1.9
> points fewer violating windows (paired 95% intervals exclude zero). The two are therefore not at the same
> compliance: this is a cost-compliance trade-off, not evidence that either controller is better. When tuned by our
> common rule, the selected targets (0.90-1.00) made its online estimator diverge, so we report no tuned row and say
> so. These results are from the fast simulator on five development traces, before calibration. [Row in Table V,
> supplement section and Section II scope statement: pending.]

**Before sending, the author confirms:**
- that [3] is the paper above (confirmed from the submitted reference list on 24 Nov 2026);
- the reporting platform for Table V.

The figures above must be regenerated from that table's result set.

*[Base corrected 24 Nov 2026: the paired figure is (PRISM − OptScaler) / OptScaler, so PRISM costs 23-28% less than OptScaler; OptScaler costs 30-40% more than PRISM (mean of per-trace ratios). The earlier '23-28% more expensive than PRISM' inverted the base.]*
