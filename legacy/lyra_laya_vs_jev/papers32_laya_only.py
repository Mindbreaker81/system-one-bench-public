#!/usr/bin/env python3
import os, json, time
os.environ["USE_TF"] = "0"
import laya

BASE = "/opt/data/laya_vs_jev"
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

agent = laya.load("convaiinnovations/laya")

def state_for(p):
    return f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\nAbstract: {p['abstract']}"

results = []
for p in papers:
    t0=time.time()
    res = agent.predict(state_for(p), QUESTIONS)
    ms=(time.time()-t0)*1000
    a = res["answers"]
    pr = {
      "relevance": round(float(a["relevance"]["score"]),2),
      "domain": a["domain"]["choice"],
      "design": a["design"]["choice"],
      "depth": a["depth"]["choice"],
      "practice": round(float(a["practice"]["noul"]),3),
    }
    results.append({"pid":p["pid"],"ms":round(ms),"pred":pr})
    print(f"laya {p['pid']}: rel={pr['relevance']} dom={pr['domain']} des={pr['design']} dep={pr['depth']} pra={pr['practice']}", flush=True)
json.dump(results, open(f"{BASE}/papers32_laya.json","w"), indent=1)
print("LAYA done")
