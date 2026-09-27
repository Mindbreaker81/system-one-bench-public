#!/usr/bin/env python3
"""RERUN 2026-09-23: Laya local reruns. Same questions, same cases as originals.
Saves to rerun/*_v2.json. Originals untouched."""
import os, json, time, sys
os.environ["USE_TF"] = "0"
import laya

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/rerun"
os.makedirs(OUT, exist_ok=True)

QS_TRIAGE = {
 "department": {"type":"choice","instructions":"Which department should handle this message?",
   "criteria":{
     "bronchoscopia":"endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
     "consulta_externa":"outpatient clinic: results, symptoms, clinical questions, general appointments",
     "urgencias":"medical emergency or red-flag symptoms needing immediate care",
     "admin":"billing, invoices, refunds, insurance, reports copies, parking, non-clinical"}},
 "urgency": {"type":"score","instructions":"How urgent is this message?",
   "criteria":["bajo: routine, no deadline","medio: should be handled soon","critico: deadline, blocking, or safety issue"]},
 "clinical": {"type":"noul","instructions":"Does this message contain clinical content requiring medical judgment?"},
 "hostile": {"type":"noul","instructions":"Is the sender hostile, insulting, or threatening?"},
 "same_day": {"type":"noul","instructions":"Does this require an answer or action TODAY (same working day)?"}
}

def parse_laya_triage(res):
    a = res["answers"]
    p = {}
    d = a["department"]
    p["department"] = d["choice"]
    p["department_probs"] = d.get("probabilities")
    p["urgency"] = round(float(a["urgency"]["score"]),2)
    p["urgency_probs"] = a["urgency"].get("probabilities")
    for k in ["clinical","hostile","same_day"]:
        p[k] = round(float(a[k]["noul"]),3)
    return p

def score_triage(p, exp):
    s = {}
    s["department"] = 1 if p["department"]==exp["department"] else 0
    lvl = min(2, max(0, round(p["urgency"])))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical","hostile","same_day"]:
        s[k] = 1 if (1 if p[k]>=0.5 else 0) == exp[k] else 0
    return s

# ============ TRIAGE: multilingual ES/EN + english root EN ============
if "--triage" in sys.argv:
    cases = json.load(open(f"{BASE}/bench_cases.json"))
    results = {}
    agent_ml = laya.load("convaiinnovations/laya", subfolder="multilingual")
    for tag, lang in [("laya_ml_es","es"), ("laya_ml_en","en")]:
        results[tag] = []
        for c in cases:
            t0=time.time()
            res = agent_ml.predict(c[lang], QS_TRIAGE)
            ms=(time.time()-t0)*1000
            p = parse_laya_triage(res); s = score_triage(p, c["expected"])
            results[tag].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
            print(f"{tag} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
    agent_en = laya.load("convaiinnovations/laya")
    results["laya_en_en"] = []
    for c in cases:
        t0=time.time()
        res = agent_en.predict(c["en"], QS_TRIAGE)
        ms=(time.time()-t0)*1000
        p = parse_laya_triage(res); s = score_triage(p, c["expected"])
        results["laya_en_en"].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
        print(f"laya_en_en {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
    json.dump(results, open(f"{OUT}/laya_triage_v2.json","w"), ensure_ascii=False, indent=1)
    print("--- laya triage done ---")

# ============ PAPERS 32 ============
if "--papers" in sys.argv:
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

    agent = laya.load("convaiinnovations/laya")
    results_l = []
    for p in papers:
        t0=time.time()
        res = agent.predict(state_for(p), QUESTIONS)
        ms=(time.time()-t0)*1000
        a = res["answers"]
        pr = {"relevance": round(float(a["relevance"]["score"]),2),
              "domain": a["domain"]["choice"],
              "design": a["design"]["choice"],
              "depth": a["depth"]["choice"],
              "practice": round(float(a["practice"]["noul"]),3)}
        results_l.append({"pid":p["pid"],"ms":round(ms),"pred":pr})
        print(f"laya {p['pid']}: rel={pr['relevance']} dom={pr['domain']} des={pr['design']} dep={pr['depth']} pra={pr['practice']}", flush=True)
    json.dump(results_l, open(f"{OUT}/papers32_laya_v2.json","w"), indent=1)
    print("--- laya papers done ---")

# ============ ADVERSARIAL 10 ============
if "--adversarial" in sys.argv:
    acases = json.load(open(f"{BASE}/adversarial_cases.json"))
    agent = laya.load("convaiinnovations/laya")
    results = []
    for name, c in acases.items():
        t0=time.time()
        res = agent.predict(c["state"], QS_TRIAGE)
        ms=(time.time()-t0)*1000
        a = res["answers"]
        pr = {"department":a["department"]["choice"],
              "department_probs": a["department"].get("probabilities"),
              "urgency":round(float(a["urgency"]["score"]),2),
              "clinical":round(float(a["clinical"]["noul"]),2),
              "hostile":round(float(a["hostile"]["noul"]),2),
              "same_day":round(float(a["same_day"]["noul"]),2)}
        results.append({"case":name,"ms":round(ms),"pred":pr,"gt":{k:v for k,v in c.items() if k!="state"}})
        print(f"laya {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}", flush=True)
    json.dump(results, open(f"{OUT}/adversarial_laya_v2.json","w"), indent=1)
    print("--- laya adversarial done ---")
