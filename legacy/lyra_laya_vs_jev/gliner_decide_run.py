#!/usr/bin/env python3
"""GLiNER2.5-Decide on our battery: triaje ES/EN 14x5, papers32 x5, adversarial 1+2.
Maps Jev question types to classify_text schemas:
  choice -> labels w/ descriptions; score 0-2 -> ordinal "0".."2"; noul -> yes/no.
Deterministic encoder: single pass, temp-free. GT and cases identical to Jev/Laya runs.
"""
import os, json, time, sys
from gliner2 import AutoExtractor

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/gliner_decide"
os.makedirs(OUT, exist_ok=True)

t0 = time.time()
model = AutoExtractor.from_pretrained("fastino/GLiNER2.5-Decide")
model.eval()
print(f"# model loaded {time.time()-t0:.1f}s", flush=True)

# ---------- schemas mirroring rerun_jev.py QS_TRIAGE ----------
DEPT_LABELS = {
  "bronchoscopia": "endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
  "consulta_externa": "outpatient clinic: results, symptoms, clinical questions, general appointments",
  "urgencias": "medical emergency or red-flag symptoms needing immediate care",
  "admin": "billing, invoices, refunds, insurance, reports copies, parking, non-clinical",
}
URG_LABELS = ["0", "1", "2"]  # low / medium / critical

def schema_triage():
    return {
      "department": list(DEPT_LABELS.keys()),
      "urgency": list(URG_LABELS),
      "clinical": ["yes", "no"],
      "hostile": ["yes", "no"],
      "same_day": ["yes", "no"],
    }

def schema_triage_desc():
    return {
      "department": {"labels": DEPT_LABELS},
      "urgency": ["0", "1", "2"],
      "clinical": ["yes", "no"],
      "hostile": ["yes", "no"],
      "same_day": ["yes", "no"],
    }

def parse_triage(r):
    return {
      "department": r["department"],
      "urgency": int(r["urgency"]),
      "clinical": r["clinical"],
      "hostile": r["hostile"],
      "same_day": r["same_day"],
    }

def score_triage(p, exp):
    s = {}
    s["department"] = 1 if p["department"] == exp["department"] else 0
    lvl = min(2, max(0, p["urgency"]))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical", "hostile", "same_day"]:
        pred = 1 if p[k] == "yes" else 0
        s[k] = 1 if pred == exp[k] else 0
    return s

# ============ TRIAGE 14 cases ES+EN ============
if "--triage" in sys.argv or not sys.argv[1:]:
    cases = json.load(open(f"{BASE}/bench_cases.json"))
    results = {"gliner_es": [], "gliner_en": []}
    for lang in ["es", "en"]:
        for c in cases:
            try:
                t1 = time.time()
                r = model.classify_text(c[lang], schema_triage())
                ms = (time.time() - t1) * 1000
                p = parse_triage(r)
                s = score_triage(p, c["expected"])
                results[f"gliner_{lang}"].append({"case": c["name"], "ms": round(ms), "pred": p, "score": s})
                print(f"gliner_{lang} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
            except Exception as e:
                results[f"gliner_{lang}"].append({"case": c["name"], "error": str(e)[:200]})
                print(f"gliner_{lang} {c['name']}: ERROR {str(e)[:100]}", flush=True)
    json.dump(results, open(f"{OUT}/gliner_triage.json", "w"), ensure_ascii=False, indent=1)
    tot = sum(sum(r.get("score", {}).values()) for r in results["gliner_es"]) + \
          sum(sum(r.get("score", {}).values()) for r in results["gliner_en"])
    n = sum(len(results[k]) for k in results)
    print(f"--- triage done: {tot:.1f}/{n*5} = {100*tot/(n*5):.1f}% ---", flush=True)

# ============ PAPERS 32 x 5 dims ============
if "--papers" in sys.argv or not sys.argv[1:]:
    papers = json.load(open(f"{BASE}/papers32.json"))
    GT = json.load(open(f"{BASE}/paper_gt32.json"))
    papers = [p for p in papers if p["pid"] in GT]

    PAPER_SCHEMA = {
      "relevance": ["0", "1", "2"],
      "domain": ["ip", "oncology", "ai_radiology", "pulm_general", "other"],
      "design": ["rct", "meta", "cohort", "review", "basic"],
      "depth": ["full", "abstract", "skip"],
      "practice": ["yes", "no"],
    }

    def state_for(p):
        return f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\nAbstract: {p['abstract']}"

    results = []
    for p in papers:
        try:
            t1 = time.time()
            r = model.classify_text(state_for(p), PAPER_SCHEMA)
            ms = (time.time() - t1) * 1000
            pr = {"relevance": int(r["relevance"]), "domain": r["domain"], "design": r["design"],
                  "depth": r["depth"], "practice": r["practice"]}
            results.append({"pid": p["pid"], "ms": round(ms), "pred": pr})
            print(f"gliner {p['pid']}: rel={pr['relevance']} dom={pr['domain']} des={pr['design']} dep={pr['depth']} pra={pr['practice']}", flush=True)
        except Exception as e:
            results.append({"pid": p["pid"], "error": str(e)[:200]})
            print(f"gliner {p['pid']}: ERROR {str(e)[:100]}", flush=True)
    json.dump(results, open(f"{OUT}/gliner_papers32.json", "w"), indent=1)
    print("--- papers done ---", flush=True)

# ============ ADVERSARIAL 1 + 2 ============
if "--adversarial" in sys.argv or not sys.argv[1:]:
    for fname, outname in [("adversarial_cases.json", "gliner_adversarial1.json"),
                           ("adversarial2_cases.json", "gliner_adversarial2.json")]:
        acases = json.load(open(f"{BASE}/{fname}"))
        results = []
        for name, c in acases.items():
            try:
                t1 = time.time()
                r = model.classify_text(c["state"], schema_triage())
                ms = (time.time() - t1) * 1000
                pr = parse_triage(r)
                results.append({"case": name, "ms": round(ms), "pred": pr,
                                "gt": {k: v for k, v in c.items() if k != "state"}})
                print(f"gliner {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}", flush=True)
            except Exception as e:
                results.append({"case": name, "error": str(e)[:200]})
                print(f"gliner {name}: ERROR", flush=True)
        json.dump(results, open(f"{OUT}/{outname}", "w"), ensure_ascii=False, indent=1)
    print("--- adversarial done ---", flush=True)
