#!/usr/bin/env python3
"""Compare GLiNER2.5-Decide vs Jev (rerun v2) vs Laya on identical GT/metrics."""
import json, random
BASE = "/opt/data/laya_vs_jev"
G = f"{BASE}/gliner_decide"

# ---- TRIAGE ----
gl = json.load(open(f"{G}/gliner_triage.json"))
jev = json.load(open(f"{BASE}/rerun/jev_triage_v2.json"))
cases = {c["name"]: c["expected"] for c in json.load(open(f"{BASE}/bench_cases.json"))}

def triage_metrics(res, prefix):
    per = {}
    for lang in ["es", "en"]:
        rows = [r for r in res[f"{prefix}_{lang}"] if "score" in r]
        tot = sum(sum(r["score"].values()) for r in rows)
        n = len(rows)
        per[lang] = {"pct": 100*tot/(n*5), "n": n}
        for k in ["department","urgency","clinical","hostile","same_day"]:
            per[lang][k] = sum(r["score"][k] for r in rows)
    return per

for name, res in [("GLINER", gl), ("JEV", jev)]:
    m = triage_metrics(res, "gliner" if name=="GLINER" else "jev")
    es, en = m["es"], m["en"]
    print(f"{name:7s} ES {es['pct']:5.1f}% (dep {es['department']}/14 urg {es['urgency']:.1f}/14) | EN {en['pct']:.1f}% (dep {en['department']}/14 urg {en['urgency']:.1f}/14)")

# ES vs EN gap for gliner (language sensitivity)
m = triage_metrics(gl, "gliner")
print(f"         gliner ES-EN gap: {abs(m['es']['pct']-m['en']['pct']):.1f} pts")

# ---- PAPERS ----
def load_pred(path, key):
    out = {}
    for r in json.load(open(path)):
        if "pred" in r: out[r[key]] = r["pred"]
    return out

GT = json.load(open(f"{BASE}/paper_gt32.json"))
gp = load_pred(f"{G}/gliner_papers32.json", "pid")
jp = load_pred(f"{BASE}/rerun/papers32_jev_v2.json", "pid")

def score_dims(pred, gt):
    rl = min(2, max(0, round(pred["relevance"])))
    return {
      "relevance": 1.0 if rl == gt["relevance"] else (0.5 if abs(rl-gt["relevance"])==1 else 0.0),
      "domain": float(pred["domain"] == gt["domain"]),
      "design": float(pred["design"] == gt["design"]),
      "depth": float(pred["depth"] == gt["depth"]),
      "practice": float((1 if (pred["practice"]=="yes" if isinstance(pred["practice"],str) else pred["practice"]>=0.5) else 0) == gt["practice"]),
    }

def depth_cascade(pred, skip_t):
    if pred["relevance"] < skip_t: return "skip"
    prac = (pred["practice"]=="yes") if isinstance(pred["practice"],str) else (pred["practice"]>=0.5)
    if pred["depth"] == "full" and prac: return "full"
    return "abstract"

def best_skip_threshold(preds, gts):
    rels = sorted(preds[p]["relevance"] for p in preds)
    cands = [0.0] + [(a+b)/2 for a,b in zip(rels, rels[1:])] + [2.0]
    best_t, best_ok = 0.0, -1
    for t in cands:
        ok = sum(depth_cascade(preds[p], t) == gts[p]["depth"] for p in preds)
        if ok > best_ok: best_ok, best_t = ok, t
    return best_t

for name, res in [("GLINER", gp), ("JEV", jp)]:
    PIDS = [p for p in GT if p in res]
    dims = {k:0.0 for k in ["relevance","domain","design","depth","practice"]}
    for pid in PIDS:
        sc = score_dims(res[pid], GT[pid])
        for k in dims: dims[k] += sc[k]
    n = len(PIDS)
    # cascade CV
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:n//2], shuffled[n//2:]]
    hits = 0; tp = fn = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        t = best_skip_threshold({p:res[p] for p in train}, {p:GT[p] for p in train})
        hits += sum(depth_cascade(res[p], t) == GT[p]["depth"] for p in test)
        for p in test:
            if GT[p]["depth"] == "skip":
                if depth_cascade(res[p], t) == "skip": tp += 1
                else: fn += 1
    spear = None
    try:
        import math
        xs = [res[p]["relevance"] for p in PIDS]; ys = [GT[p]["relevance"] for p in PIDS]
        def rank(v):
            s = sorted(range(len(v)), key=lambda i: v[i]); r=[0]*len(v); i=0
            while i < len(v):
                j=i
                while j+1 < len(v) and v[s[j+1]]==v[s[i]]: j+=1
                avg=(i+j)/2+1
                for k2 in range(i,j+1): r[s[k2]]=avg
                i=j+1
            return r
        rx, ry = rank(xs), rank(ys)
        mx, my = sum(rx)/n, sum(ry)/n
        num = sum((a-mx)*(b-my) for a,b in zip(rx,ry))
        den = math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))
        spear = num/den
    except Exception: pass
    print(f"{name:7s} papers {n}: direct {sum(dims.values()):.1f}/{n*5} = {100*sum(dims.values())/(n*5):.1f}% | rel {dims['relevance']:.1f} dom {dims['domain']:.0f} des {dims['design']:.0f} dep {dims['depth']:.0f} pra {dims['practice']:.0f} | cascade {hits}/{n} | Spearman {spear:.3f}" if spear else f"{name} err")
    print(f"         skip-gate recall: {tp}/{tp+fn}")

# ---- ADVERSARIAL ----
for setname, fgl in [("adv-1", f"{G}/gliner_adversarial1.json"), ("adv-2", f"{G}/gliner_adversarial2.json")]:
    rows = json.load(open(fgl))
    ok = sum(1 for r in rows if "pred" in r and r["pred"]["department"] == r["gt"]["department"])
    print(f"{setname}: GLINER routing {ok}/{len(rows)}")
    for r in rows:
        if "pred" in r and r["pred"]["department"] != r["gt"]["department"]:
            print(f"   MISS {r['case']}: pred={r['pred']['department']} gt={r['gt']['department']}")
