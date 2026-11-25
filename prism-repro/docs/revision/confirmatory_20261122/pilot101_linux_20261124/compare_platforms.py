#!/usr/bin/env python3
"""Compare the closed-loop pilot101 weeks run on Linux with the Windows run of the same set (../pilot101_check), week by
week (same family, week, parameter), on every result field, and the validation selections. Platform check only;
development trace 101; no confirmatory seed.
usage: python compare_platforms.py <linux weeks dir> <windows weeks dir> <out.json>"""
import glob
import json
import os
import sys

KEYS = ("cost", "violating_window_rate", "record_attainment", "cold_start_ratio", "overflow_share", "p99_latency",
        "n_requests", "share_mem_ge_2048")


def load(d):
    out = {}
    for p in glob.glob(os.path.join(d, "**", "*.json"), recursive=True):
        r = json.load(open(p, encoding="utf-8"))
        if "family" in r and "week" in r:
            out[(r["family"], r["week"], r.get("scenario"), json.dumps(r.get("param")))] = r
    return out


def main(lin, win, out):
    L, W = load(lin), load(win)
    common = sorted(set(L) & set(W))
    res = {"weeks_linux": len(L), "weeks_windows": len(W), "common": len(common), "per_family": {}, "weeks": []}
    for k in common:
        a, b = L[k], W[k]
        d = {f: (a.get(f), b.get(f)) for f in KEYS if f in a or f in b}
        same = all(x == y for x, y in d.values())
        rel = (a["cost"] - b["cost"]) / b["cost"] * 100 if b.get("cost") else 0.0
        dv = (a["violating_window_rate"] - b["violating_window_rate"]) * 100
        res["weeks"].append(dict(family=k[0], week=k[1], scenario=k[2], param=json.loads(k[3]), identical=same,
                                 cost_linux=a["cost"], cost_windows=b["cost"], cost_diff_pct=rel,
                                 viol_linux=a["violating_window_rate"], viol_windows=b["violating_window_rate"],
                                 viol_diff_pp=dv))
    for fam in sorted({w["family"] for w in res["weeks"]}):
        ws = [w for w in res["weeks"] if w["family"] == fam]
        res["per_family"][fam] = dict(weeks=len(ws), identical=sum(w["identical"] for w in ws),
                                      max_abs_cost_diff_pct=max(abs(w["cost_diff_pct"]) for w in ws),
                                      max_abs_viol_diff_pp=max(abs(w["viol_diff_pp"]) for w in ws))
    json.dump(res, open(out, "w", encoding="utf-8", newline="\n"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "weeks"}, indent=1))
    for w in res["weeks"]:
        if w["week"] != "val" or not w["identical"]:
            print(f"{w['family']:14s} {w['week']:5s} {str(w['param']):6s} cost {w['cost_windows']:.1f} -> {w['cost_linux']:.1f} "
                  f"({w['cost_diff_pct']:+.2f}%) viol {100*w['viol_windows']:.2f} -> {100*w['viol_linux']:.2f}% identical={w['identical']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
