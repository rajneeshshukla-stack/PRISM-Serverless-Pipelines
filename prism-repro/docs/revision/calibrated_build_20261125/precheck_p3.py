import json, sys
import numpy as np
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/revision")
import closed_loop_exploratory as X
from prism_repro import latency as L
C = X.C
FAC = tuple((int(m), tuple(f)) for m, f in json.load(open(sys.argv[1]))["exec_factor_measured"])
BASE = dict(exec_scaling="measured", exec_factor_measured=FAC, exec_common_frac=0.998, init_max_s=10.0)
old = {"CAL145": C.make_cfg(BASE), "CAL12": C.make_cfg(dict(BASE, deadline=12.0))}
new = {"CAL145C": C.make_cfg(dict(BASE, init_scaling="constant")), "CAL12C": C.make_cfg(dict(BASE, init_scaling="constant", deadline=12.0))}
mult = L.lognormal_mult(np.random.default_rng(7).standard_normal(200000), 0.30)
for (on, o), (nn, n) in zip(old.items(), new.items()):
    do, dn = o.to_dict(), n.to_dict()
    print(f"{nn} sha {C.cfg_sha(n)} vs {on} {C.cfg_sha(o)}; fields differing: {[k for k in do if do[k] != dn[k]]}")
    print("  init_scaling", n.init_scaling, "init_max_s", n.init_max_s, "init_shape", n.init_shape, "init_mean_1024", n.init_mean_1024)
    for m in n.mem_options:
        print(f"  {m} MB: mean new {L.init_mean(n, m):.4f} old {L.init_mean(o, m):.4f}; untrunc new {L._init_untruncated_mean(n, m):.4f}")
    a1024, a2048 = L.init_seconds(n, mult, 1024), L.init_seconds(n, mult, 2048)
    print("  new: draws at 2048 == draws at 1024 (same multipliers):", np.array_equal(a1024, a2048),
          "; quantiles 50/90/99/max", np.round(np.quantile(a2048, [.5, .9, .99, 1]), 3))
    print("  new vs old at 1024 MB identical draws:", np.array_equal(a1024, L.init_seconds(o, mult, 1024)),
          "; attainment table at 1024 identical:", np.array_equal(L.attainment_table(n, 1024), L.attainment_table(o, 1024)))
    print("  attainment k cold, 2048 MB new", np.round(L.attainment_table(n, 2048), 4), "old", np.round(L.attainment_table(o, 2048), 4))
    print("  init_factor(1024) eq3 =", L.init_factor(o, 1024))
