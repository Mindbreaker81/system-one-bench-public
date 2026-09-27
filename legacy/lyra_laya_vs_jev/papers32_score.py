#!/usr/bin/env python3
"""Final scoring on 32 papers: per-dimension + cascade with 2-fold CV thresholds."""
import json
BASE = "/opt/data/laya_vs_jev"
jev = {r["pid"]: r["pred"] for r in json.load(open(f"{BASE}/papers32_jev.json"))}
laya = {r["pid"]: r["pred"] for r in json.load(open(f"{BASE}/papers32_laya.json"))}
GT = json.load(open(f"{BASE}/paper_gt32.json"))
PIDS = [p for p in GT if p in jev and p in laya]

def score_dims(pred, gt):
    rl = min(2, max(0, round(pred["relevance"])))
    return {
      "relevance": 1.0 if rl == gt["relevance"] else (0.5 if abs(rl-gt["relevance"])==1 else 0.0),
      "domain": float(pred["domain"] == gt["domain"]),
      "design": float(pred["design"] == gt["design"]),
      "depth": float(pred["depth"] == gt["depth"]),
      "practice": float((1 if pred["practice"]>=0.5 else 0) == gt["practice"]),
    }

def depth_cascade(pred, skip_t):
    if pred["relevance"] < skip_t: return "skip"
    # full only if model explicitly chose full AND practice>=0.5 (consensus)
    if pred["depth"] == "full" and pred["practice"] >= 0.5: return "full"
    return "abstract"

def best_skip_threshold(preds, gts):
    rels = sorted(preds[p]["relevance"] for p in preds)
    cands = [0.0] + [(a+b)/2 for a,b in zip(rels, rels[1:])] + [2.0]
    best_t, best_ok = 0.0, -1
    for t in cands:
        ok = sum(depth_cascade(preds[p], t) == gts[p]["depth"] for p in preds)
        if ok > best_ok: best_ok, best_t = ok, t
    return best_t

for name, res in [("JEV", jev), ("LAYA", laya)]:
    dims = {k:0.0 for k in ["relevance","domain","design","depth","practice"]}
    for pid in PIDS:
        sc = score_dims(res[pid], GT[pid])
        for k in dims: dims[k] += sc[k]
    n = len(PIDS)
    print(f"\n=== {name} ({n} papers x 5 dims) ===")
    print(f"  direct: {sum(dims.values()):.1f}/{n*5} = {100*sum(dims.values())/(n*5):.1f}%  | rel {dims['relevance']:.1f} dom {dims['domain']:.0f} des {dims['design']:.0f} dep {dims['depth']:.0f} pra {dims['practice']:.0f}")

    # 2-fold CV cascade
    import random
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:len(shuffled)//2], shuffled[len(shuffled)//2:]]
    hits = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        tr_preds = {p: res[p] for p in train}
        tr_gts = {p: GT[p] for p in train}
        t = best_skip_threshold(tr_preds, tr_gts)
        hits += sum(depth_cascade(res[p], t) == GT[p]["depth"] for p in test)
    print(f"  cascade (2-fold CV, consensus full rule): {hits}/{n} = {100*hits/n:.1f}%")

# skip-gate quality alone (the safety-critical part): of GT-skip papers, how many skipped at CV thresholds?
print("\nSkip-gate recall (GT=skip papers actually skipped):")
for name, res in [("JEV", jev), ("LAYA", laya)]:
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:len(shuffled)//2], shuffled[len(shuffled)//2:]]
    tp = fn = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        t = best_skip_threshold({p:res[p] for p in train}, {p:GT[p] for p in train})
        for p in test:
            if GT[p]["depth"] == "skip":
                if depth_cascade(res[p], t) == "skip": tp += 1
                else: fn += 1
    print(f"  {name}: {tp}/{tp+fn} skipped correctly")
