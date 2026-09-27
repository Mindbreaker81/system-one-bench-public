#!/usr/bin/env python3
"""Laya-english on the same 12 papers, same questions."""
import os, json, time
os.environ["USE_TF"] = "0"
import laya

BASE = "/opt/data/laya_vs_jev"
papers = json.load(open(f"{BASE}/papers.json"))
GT = json.load(open(f"{BASE}/paper_gt.json"))

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
     "review":"narrative review, expert opinion, guideline summary",
     "basic":"basic science: animal, molecular, cell biology"}},
 "depth": {"type":"choice","instructions":"For a busy clinician building a reading pipeline: how deeply should this paper be read?",
   "criteria":{
     "full":"read full text - practice-changing or core-method paper",
     "abstract":"abstract only is enough - results worth knowing, results worth knowing, methods standard",
     "skip":"skip - not worth the time"}},
 "practice": {"type":"noul","instructions":"Could this paper change current clinical practice in lung cancer diagnosis or staging?"}
}

agent = laya.load("convaiinnovations/laya")  # english root

def state_for(p):
    meta = f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\n"
    return meta + "Abstract: " + p["abstract"]

results = []
for p in papers:
    state = state_for(p)
    t0=time.time()
    res = agent.predict(state, QUESTIONS)
    ms=(time.time()-t0)*1000
    a = res["answers"]
    pr = {
      "relevance": round(float(a["relevance"]["score"]),2),
      "domain": a["domain"]["choice"],
      "design": a["design"]["choice"],
      "depth": a["depth"]["choice"],
      "practice": round(float(a["practice"]["noul"]),3),
    }
    gt = GT[p["pid"]]
    results.append({"pid":p["pid"],"pmid":p["pmid"],"ms":round(ms),"pred":pr,"gt":gt})
    print(f"{p['pid']} laya: rel={pr['relevance']} dom={pr['domain']} design={pr['design']} depth={pr['depth']} pract={pr['practice']} | {ms:.0f}ms")

json.dump(results, open(f"{BASE}/papers_laya.json","w"), ensure_ascii=False, indent=1)
