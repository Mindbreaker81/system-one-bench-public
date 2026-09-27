#!/usr/bin/env python3
"""Compare v1 (2026-09-20) vs v2 (2026-09-23) results: same metrics + per-item diffs."""
import json, random

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/rerun"

def load(p): return json.load(open(p))

def spearman(xs, ys):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); r=[0]*len(v)
        for i,j in enumerate(s): r[j]=i
        # average ranks for ties
        i=0
        while i < len(r):
            j=i
            while j+1 < len(r) and v[s[j+1]]==v[s[i]]: j+=1
            avg=(i+j)/2
            for k in range(i,j+1): r[s[k]]=avg
            i=j+1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx)/len(rx), sum(ry)/len(ry)
    num = sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den = (sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

def triage_metrics(results):
    """results: list of {case, pred, score} -> aggregate score over 5 dims."""
    tot = 0.0; n = 0; errs = 0
    per_q = {}
    for r in results:
        if "error" in r: errs += 1; continue
        for k, v in r["score"].items():
            tot += v; n += 1
            per_q.setdefault(k, [0.0,0])
            per_q[k][0] += v; per_q[k][1] += 1
    return {"pct": 100*tot/n if n else 0, "n_items": n, "errors": errs,
            "per_q": {k: (round(100*v/c,1), c) for k,(v,c) in per_q.items()}}

def score_dims(pred, gt):
    rl = min(2, max(0, round(pred["relevance"])))
    return {
      "relevance": 1.0 if rl == gt["relevance"] else (0.5 if abs(rl-gt["relevance"])==1 else 0.0),
      "domain": float(pred["domain"] == gt["domain"]),
      "design": float(pred["design"] == gt["design"]),
      "depth": float(pred["depth"] == gt["depth"]),
      "practice": float((1 if pred["practice"]>=0.5 else 0) == gt["practice"]),
    }

def papers_metrics(path):
    res = {r["pid"]: r["pred"] for r in load(path) if "pid" in r}
    GT = load(f"{BASE}/paper_gt32.json")
    PIDS = [p for p in GT if p in res]
    dims = {k:0.0 for k in ["relevance","domain","design","depth","practice"]}
    for pid in PIDS:
        sc = score_dims(res[pid], GT[pid])
        for k in dims: dims[k] += sc[k]
    n = len(PIDS)
    rho = spearman([res[p]["relevance"] for p in PIDS], [GT[p]["relevance"] for p in PIDS])
    # bottom-10 recall of GT-relevance-0
    bottom = sorted(PIDS, key=lambda p: res[p]["relevance"])[:10]
    n0_total = sum(1 for p in PIDS if GT[p]["relevance"]==0)
    n0_bottom = sum(1 for p in bottom if GT[p]["relevance"]==0)
    # 2-fold CV cascade (same as original: seed 7)
    def depth_cascade(pred, skip_t):
        if pred["relevance"] < skip_t: return "skip"
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
    random.seed(7)
    shuffled = PIDS[:]; random.shuffle(shuffled)
    folds = [shuffled[:len(shuffled)//2], shuffled[len(shuffled)//2:]]
    hits = 0
    for i in range(2):
        test, train = folds[i], folds[1-i]
        t = best_skip_threshold({p:res[p] for p in train}, {p:GT[p] for p in train})
        hits += sum(depth_cascade(res[p], t) == GT[p]["depth"] for p in test)
    return {"n": n, "dims": {k:(v, round(100*v/n)) for k,v in dims.items()},
            "direct_pct": round(100*sum(dims.values())/(n*5),1),
            "spearman": round(rho,3), "bottom10_rel0": f"{n0_bottom}/{n0_total}",
            "cascade_cv_pct": round(100*hits/n,1)}

def adversarial_metrics(path):
    rows = load(path)
    tot = 0.0; n = 0
    for r in rows:
        if "error" in r or "pred" not in r: continue
        gt = r["gt"]
        tot += 1 if r["pred"]["department"]==gt["department"] else 0
        lvl = min(2, max(0, round(r["pred"]["urgency"])))
        tot += 1 if lvl==gt["urgency"] else (0.5 if abs(lvl-gt["urgency"])==1 else 0)
        for k in ["clinical","hostile","same_day"]:
            tot += 1 if (1 if r["pred"][k]>=0.5 else 0)==gt[k] else 0
        n += 5
    return {"pct": round(100*tot/n,1) if n else None, "n_cases": len(rows)}

print("="*70)
print("ROUND 1+2 — TRIAGE 14 casos x 5 preguntas")
print("="*70)
v1_j = load(f"{BASE}/jev_results.json"); v2_j = load(f"{OUT}/jev_triage_v2.json")
v1_l = load(f"{BASE}/laya_results.json"); v2_l = load(f"{OUT}/laya_triage_v2.json")
rows = []
for name, v1, v2 in [
    ("Jev ES", v1_j["jev_es"], v2_j["jev_es"]),
    ("Jev EN", v1_j["jev_en"], v2_j["jev_en"]),
    ("Laya-ml ES", v1_l["laya_ml_es"], v2_l.get("laya_ml_es",[])),
    ("Laya-ml EN", v1_l["laya_ml_en"], v2_l.get("laya_ml_en",[])),
    ("Laya-en EN", v1_l["laya_en_en"], v2_l.get("laya_en_en",[])),
]:
    m1 = triage_metrics(v1); m2 = triage_metrics(v2)
    rows.append((name, m1["pct"], m2["pct"]))
    print(f"{name:12s}  v1 {m1['pct']:5.1f}%  ->  v2 {m2['pct']:5.1f}%   (errores v2: {m2['errors']})")
    # per-item diffs
    diffs = []
    idx2 = {r["case"]: r for r in v2 if "case" in r}
    for r1 in v1:
        if r1["case"] in idx2 and "score" in idx2[r1["case"]] and "score" in r1:
            s1 = r1["score"]; s2 = idx2[r1["case"]]["score"]
            ch = [k for k in s1 if s1[k]!=s2[k]]
            if ch:
                diffs.append((r1["case"], ch,
                              {k:(r1["pred"][k], idx2[r1["case"]]["pred"][k]) for k in ch if k in r1["pred"]}))
    if diffs:
        print(f"   cambios v1->v2 en {len(diffs)} casos:")
        for case, ch, vals in diffs:
            print(f"     {case}: {ch} {vals}")

print()
print("="*70)
print("ROUND 3+4 — PAPERS 32 x 5 dims")
print("="*70)
for name, v1p, v2p in [("JEV", f"{BASE}/papers32_jev.json", f"{OUT}/papers32_jev_v2.json"),
                        ("LAYA", f"{BASE}/papers32_laya.json", f"{OUT}/papers32_laya_v2.json")]:
    m1 = papers_metrics(v1p); m2 = papers_metrics(v2p)
    print(f"\n{name}:")
    print(f"  direct    v1 {m1['direct_pct']}%  ->  v2 {m2['direct_pct']}%")
    for k in ["relevance","domain","design","depth","practice"]:
        print(f"  {k:10s} v1 {m1['dims'][k][1]:3d}%  ->  v2 {m2['dims'][k][1]:3d}%   ({m2['dims'][k][0]:.1f}/{m2['n']})")
    print(f"  spearman  v1 {m1['spearman']}  ->  v2 {m2['spearman']}")
    print(f"  bottom10 tiene GT-rel-0: v1 {m1['bottom10_rel0']}  ->  v2 {m2['bottom10_rel0']}")
    print(f"  cascade CV v1 {m1['cascade_cv_pct']}%  ->  v2 {m2['cascade_cv_pct']}%")
    # per-paper diffs
    r1 = {r["pid"]: r.get("pred") for r in load(v1p)}
    r2 = {r["pid"]: r.get("pred") for r in load(v2p)}
    nch = 0
    for pid in r1:
        if pid in r2 and r1[pid] and r2[pid]:
            ch = [k for k in ["relevance","domain","design","depth","practice"] if r1[pid][k]!=r2[pid][k]]
            if ch:
                nch += 1
                print(f"     diff {pid}: " + ", ".join(f"{k}: {r1[pid][k]}->{r2[pid][k]}" for k in ch))
    if nch==0: print("  sin cambios en ningún paper")

print()
print("="*70)
print("ROUND 5 — ADVERSARIAL OOD (10 casos x 5)")
print("="*70)
for name, v1p, v2p in [("JEV", f"{BASE}/adversarial_results.json", None),
                        ("LAYA", None, None)]:
    pass
# adversarial v1 was stored differently: dict {jev:[], laya:[]}
adv1 = load(f"{BASE}/adversarial_results.json")
adv2j = load(f"{OUT}/adversarial_jev_v2.json") if __import__('os').path.exists(f"{OUT}/adversarial_jev_v2.json") else []
adv2l = load(f"{OUT}/adversarial_laya_v2.json") if __import__('os').path.exists(f"{OUT}/adversarial_laya_v2.json") else []

def adv_pct(rows):
    tot=0.0; n=0
    for r in rows:
        if "error" in r or "pred" not in r: continue
        gt=r["gt"]; p=r["pred"]
        tot += 1 if p["department"]==gt["department"] else 0
        lvl=min(2,max(0,round(p["urgency"])))
        tot += 1 if lvl==gt["urgency"] else (0.5 if abs(lvl-gt["urgency"])==1 else 0)
        for k in ["clinical","hostile","same_day"]:
            tot += 1 if (1 if p[k]>=0.5 else 0)==gt[k] else 0
        n+=5
    return (round(100*tot/n,1) if n else None, n//5)

p1j = adv_pct(adv1["jev"]); p2j = adv_pct(adv2j)
p1l = adv_pct(adv1["laya"]); p2l = adv_pct(adv2l)
print(f"Jev  adversarial: v1 {p1j[0]}% (n={p1j[1]})  ->  v2 {p2j[0]}% (n={p2j[1]})")
print(f"Laya adversarial: v1 {p1l[0]}% (n={p1l[1]})  ->  v2 {p2l[0]}% (n={p2l[1]})")
# per-case diffs
for nm, v1rows, v2rows in [("JEV", adv1["jev"], adv2j), ("LAYA", adv1["laya"], adv2l)]:
    idx2 = {r["case"]: r for r in v2rows if "case" in r}
    for r1 in v1rows:
        c = r1["case"]
        if c in idx2 and "pred" in idx2[c]:
            p1, p2 = r1["pred"], idx2[c]["pred"]
            ch = [k for k in ["department","urgency","clinical","hostile","same_day"] if p1[k]!=p2[k]]
            if ch:
                print(f"   {nm} {c}: " + ", ".join(f"{k} {p1[k]}->{p2[k]}" for k in ch))

print()
print("OOD probe Jev v2 (receta/contrato/codigo):")
ood2 = load(f"{OUT}/ood_jev_v2.json") if __import__('os').path.exists(f"{OUT}/ood_jev_v2.json") else []
for r in ood2:
    print(f"  {r['case']}: rel={r['pred']['relevance']} dom={r['pred']['domain']} clinical={r['pred']['clinical']}")
