#!/usr/bin/env python3
"""Score AnyJev battery results against GT with the SAME math as the incumbent
scorers (score.py triage, papers32_score.py dims+cascade+skip-gate, adversarial
one_hot scoring from rerun workflow). Compares vs Jev v2 rerun + Laya + GLiNER.
"""
import json, math, random, sys
from collections import Counter

BASE = "/opt/data/laya_vs_jev"
AJ = f"{BASE}/anyjev_results"

TAG = sys.argv[1] if len(sys.argv) > 1 else "qwen3_1.7b"

# ---------------- triage (same math as score.py / rerun_jev.py) ----------------
def score_one(p, e):
    s = {}
    s["department"] = float(p["department"] == e["department"])
    lvl = min(2, max(0, round(p["urgency"])))
    s["urgency"] = 1.0 if lvl == e["urgency"] else (0.5 if abs(lvl - e["urgency"]) == 1 else 0.0)
    for k in ["clinical", "hostile", "same_day"]:
        s[k] = float((1 if p[k] >= 0.5 else 0) == e[k])
    return s

cases = json.load(open(f"{BASE}/bench_cases.json"))
exp = {c["name"]: c["expected"] for c in cases}

tri = json.load(open(f"{AJ}/anyjev_triage_{TAG}.json"))
print(f"=== TRIAGE ({TAG}) ===")
for lang in ["es", "en"]:
    rows = tri[f"anyjev_{lang}"]
    n = len([r for r in rows if "error" not in r])
    tot = 0.0; dims = {k: 0.0 for k in ["department","urgency","clinical","hostile","same_day"]}
    ms = []
    for r in rows:
        if "error" in r:
            print(f"  ERR {r['case']}: {r['error'][:80]}"); continue
        sc = score_one(r["pred"], exp[r["case"]])
        tot += sum(sc.values())
        for k in dims: dims[k] += sc[k]
        ms.append(r["ms"])
    print(f"  {lang}: {tot:.1f}/{n*5} = {100*tot/(n*5):.1f}% | dep {dims['department']:.0f}/14 urg {dims['urgency']:.1f}/14 clin {dims['clinical']:.0f}/14 host {dims['hostile']:.0f}/14 day {dims['same_day']:.0f}/14 | {sum(ms)/len(ms):.0f} ms/estado")
    misses = [r["case"] for r in rows if "error" not in r and r["pred"]["department"] != exp[r["case"]]["department"]]
    print(f"  dep misses {lang}: {misses}")

# ---------------- papers (same math as papers32_score.py) ----------------
GT = json.load(open(f"{BASE}/paper_gt32.json"))
try:
    papers = json.load(open(f"{AJ}/anyjev_papers32_{TAG}.json"))
except FileNotFoundError:
    papers = None
    print("no papers results")

if papers:
    print(f"\n=== PAPERS32 ({TAG}) ===")
    preds = {r["pid"]: r["pred"] for r in papers if "error" not in r}
    PIDS = [p for p in GT if p in preds]
    n = len(PIDS)
    dims = {k: 0.0 for k in ["relevance","domain","design","depth","practice"]}
    rel_vals = []
    for pid in PIDS:
        pred = preds[pid]; gt = GT[pid]
        rl = min(2, max(0, round(pred["relevance"])))
        dims["relevance"] += 1.0 if rl == gt["relevance"] else (0.5 if abs(rl-gt["relevance"])==1 else 0.0)
        dims["domain"] += float(pred["domain"] == gt["domain"])
        dims["design"] += float(pred["design"] == gt["design"])
        dims["depth"] += float(pred["depth"] == gt["depth"])
        dims["practice"] += float((1 if pred["practice"]>=0.5 else 0) == gt["practice"])
        rel_vals.append(pred["relevance"])
    tot = sum(dims.values())
    print(f"  direct: {tot:.1f}/{n*5} = {100*tot/(n*5):.1f}% | rel {dims['relevance']:.1f} dom {dims['domain']:.0f} des {dims['design']:.0f} dep {dims['depth']:.0f} pra {dims['practice']:.0f}")
    # variance check (GLiNER lesson: variance zero => Spearman undefined)
    print(f"  relevance values: {sorted(Counter([round(v,1) for v in rel_vals]).items())}")

    # Spearman vs GT relevance (same as papers battery)
    def spearman(a, b):
        def rank(x):
            idx = sorted(range(len(x)), key=lambda i: x[i])
            r = [0.0]*len(x); i = 0
            while i < len(idx):
                j = i
                while j+1 < len(idx) and x[idx[j+1]] == x[idx[i]]: j += 1
                avg = (i + j)/2 + 1
                for k2 in range(i, j+1): r[idx[k2]] = avg
                i = j+1
            return r
        ra, rb = rank(a), rank(b)
        ma, mb = sum(ra)/len(ra), sum(rb)/len(rb)
        num = sum((x-ma)*(y-mb) for x, y in zip(ra, rb))
        da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((y-mb)**2 for y in rb))
        return num/(da*db) if da > 0 and db > 0 else float("nan")

    gt_rel = [GT[p]["relevance"] for p in PIDS]
    pred_rel = [preds[p]["relevance"] for p in PIDS]
    print(f"  Spearman relevance: {spearman(pred_rel, gt_rel):.3f}")

    # cascade with 2-fold CV (same protocol)
    def depth_cascade(pred, skip_t):
        if pred["relevance"] < skip_t: return "skip"
        if pred["depth"] == "full" and pred["practice"] >= 0.5: return "full"
        return "abstract"
    def best_skip_threshold(preds_, gts):
        rels = sorted(preds_[p]["relevance"] for p in preds_)
        cands = [0.0] + [(a+b)/2 for a,b in zip(rels, rels[1:])] + [2.0]
        best_t, best_ok = 0.0, -1
        for t in cands:
            ok = sum(depth_cascade(preds_[p], t) == gts[p]["depth"] for p in preds_)
            if ok > best_ok: best_ok, best_t = ok, t
        return best_t
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:len(shuffled)//2], shuffled[len(shuffled)//2:]]
    hits = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        t = best_skip_threshold({p: preds[p] for p in train}, {p: GT[p] for p in train})
        hits += sum(depth_cascade(preds[p], t) == GT[p]["depth"] for p in test)
    print(f"  cascade (2-fold CV): {hits}/{n} = {100*hits/n:.1f}%")
    skips = [p for p in PIDS if GT[p]["depth"] == "skip"]
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:len(shuffled)//2], shuffled[len(shuffled)//2:]]
    recalled = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        t = best_skip_threshold({p: preds[p] for p in train}, {p: GT[p] for p in train})
        recalled += sum(1 for p in test if GT[p]["depth"]=="skip" and depth_cascade(preds[p], t)=="skip")
    print(f"  skip-gate recall: {recalled}/{len(skips)}")

# ---------------- adversarial (same as adversarial workflow: 2 pts/case) -------
for phase, f in [("adv1", f"{AJ}/anyjev_adv1_{TAG}.json"), ("adv2", f"{AJ}/anyjev_adv2_{TAG}.json")]:
    try:
        rows = json.load(open(f))
    except FileNotFoundError:
        print(f"\nno {phase} results"); continue
    print(f"\n=== {phase.upper()} ({TAG}) ===")
    pts = 0.0; n = 0; routing_ok = 0
    fails = []
    for r in rows:
        if "error" in r:
            print(f"  ERR {r['case']}: {r['error'][:60]}"); continue
        n += 1
        sc = score_one(r["pred"], r["gt"])
        pts += sum(sc.values())
        routing_ok += int(r["pred"]["department"] == r["gt"]["department"])
        if sum(sc.values()) < 5: fails.append((r["case"], {k: v for k, v in sc.items() if v < 1}))
    print(f"  routing departamental: {routing_ok}/{n}")
    print(f"  full 5-question: {pts:.1f}/{n*5} = {100*pts/(n*5):.1f}%")
    for c, f2 in fails: print(f"  fail {c}: {f2}")

# ---------------- OOD ----------------
try:
    ood = json.load(open(f"{AJ}/anyjev_ood_{TAG}.json"))
    print(f"\n=== OOD ({TAG}) ===")
    for r in ood:
        if "error" in r: print(f"  {r['case']}: ERROR"); continue
        p = r["pred"]
        print(f"  {r['case']}: rel={p['relevance']} dom={p['domain']} clin={p['clinical']}")
except FileNotFoundError:
    print("\nno ood results")
