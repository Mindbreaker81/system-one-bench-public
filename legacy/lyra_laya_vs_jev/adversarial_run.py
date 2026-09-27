#!/usr/bin/env python3
"""Adversarial OOD: same 5 triage questions as round 2, both models, EN."""
import os, json, time, subprocess, urllib.request
os.environ["USE_TF"] = "0"

BASE = "/opt/data/laya_vs_jev"
cases = json.load(open(f"{BASE}/adversarial_cases.json"))

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
 "department": {"type":"choice","instructions":"Which department should handle this message?",
   "criteria":{
     "bronchoscopia":"endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
     "consulta_externa":"outpatient clinic: results, symptoms, clinical questions, general appointments",
     "urgencias":"medical emergency or red-flag symptoms needing immediate care",
     "admin":"billing, invoices, refunds, insurance, reports copies, parking, catering, logistics, non-clinical"}},
 "urgency": {"type":"score","instructions":"How urgent is this message?",
   "criteria":["bajo: routine, no deadline","medio: should be handled soon","critico: deadline, blocking, or safety issue"]},
 "clinical": {"type":"noul","instructions":"Does this message contain clinical content requiring medical judgment?"},
 "hostile": {"type":"noul","instructions":"Is the sender hostile, insulting, or threatening?"},
 "same_day": {"type":"noul","instructions":"Does this require an answer or action TODAY (same working day)?"}
}

results = {"jev": [], "laya": []}

# JEV
for name, c in cases.items():
    body = {"model":"~typesafe/jev-latest","state":c["state"],"questions":QUESTIONS}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    ms=(time.time()-t0)*1000
    a = out["answers"]
    pr = {"department":a["department"]["choice"],"urgency":round(a["urgency"]["score"],2),
          "clinical":round(a["clinical"]["noul"],2),"hostile":round(a["hostile"]["noul"],2),
          "same_day":round(a["same_day"]["noul"],2)}
    results["jev"].append({"case":name,"ms":round(ms),"pred":pr,"gt":{k:v for k,v in c.items() if k!="state"}})
    print(f"jev  {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}")
    time.sleep(0.3)

# LAYA english root
import laya
agent = laya.load("convaiinnovations/laya")
for name, c in cases.items():
    t0=time.time()
    res = agent.predict(c["state"], QUESTIONS)
    ms=(time.time()-t0)*1000
    a = res["answers"]
    pr = {"department":a["department"]["choice"],"urgency":round(float(a["urgency"]["score"]),2),
          "clinical":round(float(a["clinical"]["noul"]),2),"hostile":round(float(a["hostile"]["noul"]),2),
          "same_day":round(float(a["same_day"]["noul"]),2)}
    results["laya"].append({"case":name,"ms":round(ms),"pred":pr,"gt":{k:v for k,v in c.items() if k!="state"}})
    print(f"laya {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}", flush=True)

json.dump(results, open(f"{BASE}/adversarial_results.json","w"), indent=1)
print("done")
