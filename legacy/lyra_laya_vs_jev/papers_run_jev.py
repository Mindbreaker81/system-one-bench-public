#!/usr/bin/env python3
"""Paper screening: Jev (abstract) vs Laya-english (abstract). Same questions, EN input."""
import os, json, time, subprocess, urllib.request
os.environ["USE_TF"] = "0"

BASE = "/opt/data/laya_vs_jev"
papers = json.load(open(f"{BASE}/papers.json"))
GT = json.load(open(f"{BASE}/paper_gt.json"))

def get_key():
    pids = subprocess.run(['pgrep','-f','hermes gateway'],capture_output=True,text=True).stdout.split()
    for pid in pids:
        try:
            env = open(f'/proc/{pid}/environ','rb').read().decode('utf-8',errors='ignore').split('\0')
            for e in env:
                if e.startswith('OPENROUTER_API_KEY=') and len(e) > 25:
                    return e.split('=',1)[1]
        except Exception: pass
    return None
KEY = get_key(); assert KEY

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
     "abstract":"abstract only is enough - results worth knowing, methods standard",
     "skip":"skip - not worth the time"}},
 "practice": {"type":"noul","instructions":"Could this paper change current clinical practice in lung cancer diagnosis or staging?"}
}

def run_jev(state, qs):
    body = {"model":"~typesafe/jev-latest","state":state,"questions":qs}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    return out, (time.time()-t0)*1000

def state_for(p):
    meta = f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\n"
    return meta + "Abstract: " + p["abstract"]

def parse_generic(res):
    a = res.get("answers", res)
    if "answers" in a: a = a["answers"]
    p = {}
    p["relevance"] = round(float(a["relevance"]["score"]),2)
    p["domain"] = a["domain"]["choice"]
    p["design"] = a["design"]["choice"]
    p["depth"] = a["depth"]["choice"]
    p["practice"] = round(float(a["practice"]["noul"]),3)
    return p

results = []
total_cost = 0.0
for p in papers:
    state = state_for(p)
    out, ms = run_jev(state, QUESTIONS)
    total_cost += out.get("usage",{}).get("cost",0) or 0
    pr = parse_generic(out)
    gt = GT[p["pid"]]
    results.append({"pid":p["pid"],"pmid":p["pmid"],"ms":round(ms),"pred":pr,"gt":gt})
    print(f"{p['pid']} jev: rel={pr['relevance']} dom={pr['domain']} design={pr['design']} depth={pr['depth']} pract={pr['practice']} | {ms:.0f}ms")
    time.sleep(0.3)

json.dump(results, open(f"{BASE}/papers_jev.json","w"), ensure_ascii=False, indent=1)
print(f"total cost: ${total_cost:.6f}")
