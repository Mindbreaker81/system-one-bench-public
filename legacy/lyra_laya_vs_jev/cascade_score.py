#!/usr/bin/env python3
"""Cascade re-scoring: skip-gate by relevance + full-vs-abstract rule. Both models, several variants."""
import json
BASE = "/opt/data/laya_vs_jev"
jev = {r["pid"]: r for r in json.load(open(f"{BASE}/papers_jev.json"))}
laya = {r["pid"]: r for r in json.load(open(f"{BASE}/papers_laya.json"))}
GT = json.load(open(f"{BASE}/paper_gt.json"))

def cascade(pred, skip_t, full_rule):
    """skip_t: relevance below this -> skip. full_rule: 'depth' (model's own), 'practice' (>=0.5), 'rel175' (>=1.75)."""
    rel = pred["relevance"]
    if rel < skip_t:
        return "skip"
    if full_rule == "depth":   return pred["depth"]
    if full_rule == "practice": return "full" if pred["practice"] >= 0.5 else "abstract"
    if full_rule == "rel175":  return "full" if rel >= 1.75 else "abstract"

def run(model_res, skip_t, full_rule):
    ok = 0; det = []
    for pid, gt in GT.items():
        p = cascade(model_res[pid]["pred"], skip_t, full_rule)
        hit = p == gt["depth"]
        ok += hit
        det.append(f"{pid}:{p}{'✓' if hit else '✗'}")
    return ok, det

print("=== Out-of-box: same threshold 0.5 for both ===")
for name, res in [("Jev ", jev), ("Laya", laya)]:
    for rule in ["depth", "practice", "rel175"]:
        ok, det = run(res, 0.5, rule)
        print(f"{name} skip<0.5 + {rule:8} -> {ok}/12 = {100*ok/12:.0f}%   {' '.join(det)}")

print("\n=== Best-tuned skip threshold per model (grid 0.1..1.6 step .05, best rule) ===")
for name, res in [("Jev ", jev), ("Laya", laya)]:
    best = (-1, None, None, None)
    for t10 in range(2, 33):  # 0.10 .. 1.60
        t = t10/20
        for rule in ["depth", "practice", "rel175"]:
            ok, det = run(res, t, rule)
            if ok > best[0]:
                best = (ok, t, rule, det)
    ok, t, rule, det = best
    # robustness: show the relevance values sorted to see margin
    rels = sorted((res[p]["pred"]["relevance"], p, GT[p]["depth"]) for p in GT)
    print(f"{name} best: skip<{t:.2f} + {rule:8} -> {ok}/12 = {100*ok/12:.0f}%")
    print(f"      relevance sorted: " + ", ".join(f"{p}={r:.2f}({d})" for r,p,d in rels))
