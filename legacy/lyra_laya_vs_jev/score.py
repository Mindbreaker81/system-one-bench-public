#!/usr/bin/env python3
import json
BASE = "/opt/data/laya_vs_jev"
cases = json.load(open(f"{BASE}/bench_cases.json"))
exp = {c["name"]: c["expected"] for c in cases}
jev = json.load(open(f"{BASE}/jev_results.json"))
laya = json.load(open(f"{BASE}/laya_results.json"))

def score_one(p, e):
    s = {}
    s["department"] = float(p["department"] == e["department"])
    lvl = min(2, max(0, round(p["urgency"])))
    s["urgency"] = 1.0 if lvl == e["urgency"] else (0.5 if abs(lvl - e["urgency"]) == 1 else 0.0)
    for k in ["clinical","hostile","same_day"]:
        s[k] = float((1 if p[k] >= 0.5 else 0) == e[k])
    return s

all_res = {}
all_res.update(jev); all_res.update(laya)

print(f"{'config':14} {'total':>6} {'%':>5} | dep urg clin host day  | urg_range")
summary = {}
for tag, rows in all_res.items():
    tot = 0.0; dims = {k:0.0 for k in ["department","urgency","clinical","hostile","same_day"]}
    urgs = []
    for r in rows:
        if "error" in r: continue
        sc = score_one(r["pred"], exp[r["case"]])
        tot += sum(sc.values())
        for k in dims: dims[k] += sc[k]
        urgs.append(r["pred"]["urgency"])
    n = len([r for r in rows if "error" not in r])
    summary[tag] = {"total": tot, "max": n*5, "pct": round(100*tot/(n*5),1), "dims": dims,
                    "urg_min": min(urgs), "urg_max": max(urgs),
                    "ms_avg": round(sum(r["ms"] for r in rows if "error" not in r)/n)}
    d = dims
    print(f"{tag:14} {tot:4.1f}/{n*5} {100*tot/(n*5):4.1f}% | {d['department']:.0f}/14 {d['urgency']:4.1f}/14 {d['clinical']:.0f}/14 {d['hostile']:.0f}/14 {d['same_day']:.0f}/14 | {min(urgs):.2f}-{max(urgs):.2f}  {summary[tag]['ms_avg']}ms")

# per-case department hits for detail
print("\nDepartment misses:")
for tag, rows in all_res.items():
    misses = [r["case"].split("_")[0] for r in rows if "error" not in r and r["pred"]["department"] != exp[r["case"]]["department"]]
    print(f"  {tag:14} ({len(misses)}/14 wrong): {','.join(misses)}")

json.dump(summary, open(f"{BASE}/summary.json","w"), indent=1)
