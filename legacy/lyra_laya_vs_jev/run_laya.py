#!/usr/bin/env python3
"""Laya local: multilingual (es+en) + english root (en). Same questions as Jev run."""
import os, json, time
os.environ["USE_TF"] = "0"
import laya

BASE = "/opt/data/laya_vs_jev"
cases = json.load(open(f"{BASE}/bench_cases.json"))

QUESTIONS = {
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

def parse_laya(res):
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

def score(p, exp):
    s = {}
    s["department"] = 1 if p["department"]==exp["department"] else 0
    lvl = min(2, max(0, round(p["urgency"])))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical","hostile","same_day"]:
        s[k] = 1 if (1 if p[k]>=0.5 else 0) == exp[k] else 0
    return s

results = {}
agent_ml = laya.load("convaiinnovations/laya", subfolder="multilingual")

for tag, agent, lang in [("laya_ml_es", agent_ml, "es"), ("laya_ml_en", agent_ml, "en")]:
    results[tag] = []
    for c in cases:
        t0=time.time()
        res = agent.predict(c[lang], QUESTIONS)
        ms=(time.time()-t0)*1000
        p = parse_laya(res); s = score(p, c["expected"])
        results[tag].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
        print(f"{tag} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms")

agent_en = laya.load("convaiinnovations/laya")  # english root
results["laya_en_en"] = []
for c in cases:
    t0=time.time()
    res = agent_en.predict(c["en"], QUESTIONS)
    ms=(time.time()-t0)*1000
    p = parse_laya(res); s = score(p, c["expected"])
    results["laya_en_en"].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
    print(f"laya_en_en {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms")

json.dump(results, open(f"{BASE}/laya_results.json","w"), ensure_ascii=False, indent=1)
print("--- laya done ---")
