#!/usr/bin/env python3
import json
BASE = "/opt/data/laya_vs_jev"
jev = {r["pid"]: r for r in json.load(open(f"{BASE}/papers_jev.json"))}
laya = {r["pid"]: r for r in json.load(open(f"{BASE}/papers_laya.json"))}
GT = json.load(open(f"{BASE}/paper_gt.json"))

def score(pred, gt):
    s = {}
    rl = min(2, max(0, round(pred["relevance"])))
    s["relevance"] = 1.0 if rl == gt["relevance"] else (0.5 if abs(rl-gt["relevance"])==1 else 0.0)
    s["domain"] = float(pred["domain"] == gt["domain"])
    s["design"] = float(pred["design"] == gt["design"])
    s["depth"] = float(pred["depth"] == gt["depth"])
    s["practice"] = float((1 if pred["practice"]>=0.5 else 0) == gt["practice"])
    return s

for name, res in [("jev", jev), ("laya", laya)]:
    tot = 0.0; dims = {k:0.0 for k in ["relevance","domain","design","depth","practice"]}
    rows = []
    for pid in GT:
        sc = score(res[pid]["pred"], GT[pid])
        tot += sum(sc.values())
        for k in dims: dims[k] += sc[k]
        rows.append(f"  {pid} rel={sc['relevance']:.1f} dom={sc['domain']:.0f} des={sc['design']:.0f} dep={sc['depth']:.0f} pra={sc['practice']:.0f}  (pred depth={res[pid]['pred']['depth']}, gt={GT[pid]['depth']})")
    n = len(GT)
    print(f"\n=== {name.upper()} ===  {tot:.1f}/{n*5} = {100*tot/(n*5):.1f}%")
    print(f"  relevance {dims['relevance']:.1f}/12 | domain {dims['domain']:.0f}/12 | design {dims['design']:.0f}/12 | depth {dims['depth']:.0f}/12 | practice {dims['practice']:.0f}/12")
    for r in rows: print(r)

# key: skips that matter (did model skip what should be skipped / not skip what matters)
print("\nDepth decisions (the pipeline question):")
print(f"{'pid':5} {'gt':9} {'jev':9} {'laya':9}")
for pid in GT:
    print(f"{pid:5} {GT[pid]['depth']:9} {jev[pid]['pred']['depth']:9} {laya[pid]['pred']['depth']:9}")
