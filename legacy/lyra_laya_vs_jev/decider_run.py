#!/usr/bin/env python3
"""Battery adapter for Mapika/decider-2b: same cases, GT and question dicts
as rerun_jev.py, calling Decider.system_one() locally (same wire format).
Phases: --triage --papers --adv1 --adv2 --ood --all
Writes decider_results/decider_<phase>_<tag>.json
"""
import json, os, sys, time

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/decider_results"
os.makedirs(OUT, exist_ok=True)

MODEL = os.environ.get("DECIDER_MODEL", "Mapika/decider-2b")
TAG = os.environ.get("DECIDER_TAG", "2b_v11")

# ---- model init (once) ----
from decider.infer import Decider
t0 = time.time()
d = Decider(MODEL, device="cpu", dtype="bfloat16")
print(f"[decider] loaded {MODEL} in {time.time()-t0:.0f}s on CPU bf16", flush=True)

def run(state, qs):
    t1 = time.time()
    out = d.system_one(state, qs)
    return out["answers"], (time.time()-t1)*1000

# ---- question sets: VERBATIM from rerun_jev.py ----
def questions():
    dept = {"type":"choice","instructions":"Which department should handle this message?",
      "criteria":{
        "bronchoscopia":"endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
        "consulta_externa":"outpatient clinic: results, symptoms, clinical questions, general appointments",
        "urgencias":"medical emergency or red-flag symptoms needing immediate care",
        "admin":"billing, invoices, refunds, insurance, reports copies, parking, non-clinical"}}
    urg = {"type":"score","instructions":"How urgent is this message?",
      "criteria":["bajo: routine, no deadline","medio: should be handled soon","critico: deadline, blocking, or safety issue"]}
    clin = {"type":"noul","instructions":"Does this message contain clinical content requiring medical judgment?"}
    host = {"type":"noul","instructions":"Is the sender hostile, insulting, or threatening?"}
    sday = {"type":"noul","instructions":"Does this require an answer or action TODAY (same working day)?"}
    return {"department":dept,"urgency":urg,"clinical":clin,"hostile":host,"same_day":sday}
QS_TRIAGE = questions()

def parse_triage(a):
    p = {}
    dd = a.get("department",{})
    p["department"] = dd.get("choice")
    p["department_probs"] = dd.get("probabilities")
    u = a.get("urgency",{})
    p["urgency"] = round(float(u.get("score",0)),2)
    p["urgency_probs"] = u.get("probabilities")
    p["clinical"] = round(float(a.get("clinical",{}).get("noul",0)),3)
    p["hostile"] = round(float(a.get("hostile",{}).get("noul",0)),3)
    p["same_day"] = round(float(a.get("same_day",{}).get("noul",0)),3)
    return p

# ============ TRIAGE: 14 cases x 5 q, ES + EN ============
if any(x in sys.argv for x in ("--triage","--all")):
    cases = json.load(open(f"{BASE}/bench_cases.json"))
    results = {"decider_es":[], "decider_en":[]}
    for lang in ["es","en"]:
        for c in cases:
            try:
                a, ms = run(c[lang], QS_TRIAGE)
                p = parse_triage(a)
                results[f"decider_{lang}"].append({"case":c["name"],"ms":round(ms),"pred":p})
                print(f"decider_{lang} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
            except Exception as e:
                results[f"decider_{lang}"].append({"case":c["name"],"error":str(e)[:200]})
                print(f"decider_{lang} {c['name']}: ERROR {str(e)[:100]}", flush=True)
    json.dump(results, open(f"{OUT}/decider_triage_{TAG}.json","w"), ensure_ascii=False, indent=1)
    print("--- triage done ---", flush=True)

# ============ PAPERS32 ============
if any(x in sys.argv for x in ("--papers","--all")):
    papers = json.load(open(f"{BASE}/papers32.json"))
    GT = json.load(open(f"{BASE}/paper_gt32.json"))
    papers = [p for p in papers if p["pid"] in GT]

    QUESTIONS = {
     "relevance": {"type":"score","instructions":"How relevant is this paper to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging/precision medicine?",
       "criteria":["low: outside his clinical focus","medium: adjacent or general pulmonology","high: core topic - EBUS, bronchoscopy, lung cancer, nodules, staging, MRD"]},
     "domain": {"type":"choice","instructions":"What is the paper's main domain?",
       "criteria":{
         "ip":"interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy, pleural",
         "oncology":"lung cancer oncology: systemic therapy, immunotherapy, targeted therapy, MRD, staging outcomes",
         "ai_radiology":"AI or imaging methods: deep learning, radiomics, risk models, screening CT",
         "pulm_general":"general pulmonology: COPD, asthma, smoking, sleep, infections",
         "other":"anything else: basic science, other organs, non-pulmonary"}},
     "design": {"type":"choice","instructions":"What is the study design?",
       "criteria":{
         "rct":"randomized controlled trial",
         "meta":"systematic review or meta-analysis",
         "cohort":"prospective or retrospective cohort / registry / diagnostic accuracy study",
         "review":"narrative review, expert opinion, guideline",
         "basic":"basic science: animal, molecular, cell biology"}},
     "depth": {"type":"choice","instructions":"For a busy clinician building a reading pipeline: how deeply should this paper be read?",
       "criteria":{
         "full":"read full text - practice-changing or core-method paper",
         "abstract":"abstract only is enough",
         "skip":"skip - not worth the time"}},
     "practice": {"type":"noul","instructions":"Could this paper change current clinical practice in lung cancer diagnosis or staging?"}
    }

    def state_for(p):
        return f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\nAbstract: {p['abstract']}"

    results = []
    for i, p in enumerate(papers):
        try:
            a, ms = run(state_for(p), QUESTIONS)
            pr = {"relevance": round(float(a["relevance"]["score"]),2),
                  "domain": a["domain"]["choice"],
                  "design": a["design"]["choice"],
                  "depth": a["depth"]["choice"],
                  "practice": round(float(a["practice"]["noul"]),3)}
            results.append({"pid":p["pid"],"ms":round(ms),"pred":pr})
            print(f"decider {p['pid']}: rel={pr['relevance']} dom={pr['domain']} des={pr['design']} dep={pr['depth']} pra={pr['practice']}", flush=True)
        except Exception as e:
            results.append({"pid":p["pid"],"error":str(e)[:200]})
            print(f"decider {p['pid']}: ERROR {str(e)[:100]}", flush=True)
        if (i+1) % 8 == 0:
            json.dump(results, open(f"{OUT}/decider_papers32_{TAG}.json","w"), indent=1)
            print(f"--- papers checkpoint {i+1}/{len(papers)} ---", flush=True)
    json.dump(results, open(f"{OUT}/decider_papers32_{TAG}.json","w"), indent=1)
    print("--- papers done ---", flush=True)

# ============ ADVERSARIAL 1 + 2 ============
ADV_QS = QS_TRIAGE
for phase, fname, pref in [("--adv1","adversarial_cases.json","adv1"),
                            ("--adv2","adversarial2_cases.json","adv2")]:
    if phase in sys.argv or "--all" in sys.argv:
        acases = json.load(open(f"{BASE}/{fname}"))
        results = []
        for name, c in acases.items():
            try:
                a, ms = run(c["state"], QS_TRIAGE)
                pr = {"department":a["department"]["choice"],
                      "department_probs": a["department"].get("probabilities"),
                      "urgency":round(a["urgency"]["score"],2),
                      "clinical":round(a["clinical"]["noul"],2),
                      "hostile":round(a["hostile"]["noul"],2),
                      "same_day":round(a["same_day"]["noul"],2)}
                results.append({"case":name,"ms":round(ms),"pred":pr,"gt":{k:v for k,v in c.items() if k!="state"}})
                print(f"decider {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}", flush=True)
            except Exception as e:
                results.append({"case":name,"error":str(e)[:200]})
                print(f"decider {name}: ERROR", flush=True)
        json.dump(results, open(f"{OUT}/decider_{pref}_{TAG}.json","w"), ensure_ascii=False, indent=1)
        print(f"--- {pref} done ---", flush=True)

# ============ OOD ============
if "--ood" in sys.argv or "--all" in sys.argv:
    QUESTIONS_OOD = {
     "relevance": {"type":"score","instructions":"How relevant is this text to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging?",
       "criteria":["low: outside his clinical focus","medium: adjacent or general pulmonology","high: core topic - EBUS, bronchoscopy, lung cancer"]},
     "domain": {"type":"choice","instructions":"What is this text's main domain?",
       "criteria":{
         "ip":"interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy",
         "oncology":"lung cancer oncology: therapy, MRD, staging outcomes",
         "pulm_general":"general pulmonology: COPD, asthma, smoking, sleep",
         "other":"anything else: recipes, law, code, finance, other organs"}},
     "clinical": {"type":"noul","instructions":"Does this text contain clinical content requiring medical judgment?"}
    }
    OOD = {
     "receta": "Preheat oven to 200C. Season the chicken thighs with smoked paprika, garlic and salt. Roast 35 minutes with potatoes and rosemary until the skin is crisp. Rest 5 minutes before serving with lemon.",
     "contrato": "The Parties hereby agree that any dispute arising from this Agreement shall be settled by binding arbitration in the courts of Madrid. Clause 14.2: termination with sixty (60) days written notice. Severability: if any provision is held invalid, the remainder shall continue in full force.",
     "codigo": "def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    mid = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + mid + quicksort(right)"
    }
    results = []
    for name, state in OOD.items():
        try:
            a, ms = run(state, QUESTIONS_OOD)
            pr = {"relevance": round(float(a["relevance"]["score"]),2),
                  "domain": a["domain"]["choice"],
                  "domain_probs": a["domain"].get("probabilities"),
                  "clinical": round(float(a["clinical"]["noul"]),3)}
            results.append({"case":name,"pred":pr,"ms":round(ms)})
            print(f"ood {name}: rel={pr['relevance']} dom={pr['domain']} clinical={pr['clinical']}", flush=True)
        except Exception as e:
            results.append({"case":name,"error":str(e)[:200]})
            print(f"ood {name}: ERROR", flush=True)
    json.dump(results, open(f"{OUT}/decider_ood_{TAG}.json","w"), ensure_ascii=False, indent=1)
    print("--- ood done ---", flush=True)

print("[decider] ALL DONE", flush=True)
