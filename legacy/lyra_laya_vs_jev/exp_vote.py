#!/usr/bin/env python3
"""EXPERIMENT B: majority vote of 3 independent Jev passes on triage (ES+EN).
Uses v2 (today) + 2 fresh passes. Majority on binaries/department, median on urgency."""
import json, time, subprocess, urllib.request, os, statistics

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/rerun"

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

def run_jev(state, qs):
    body = {"model":"~typesafe/jev-latest","state":state,"questions":qs}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    return out, (time.time()-t0)*1000

QS = {
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

cases = json.load(open(f"{BASE}/bench_cases.json"))

def parse(res):
    a = res.get("answers", res)
    if "answers" in a: a = a["answers"]
    return {"department": a["department"]["choice"],
            "urgency": round(float(a["urgency"]["score"]),2),
            "clinical": round(float(a["clinical"]["noul"]),3),
            "hostile": round(float(a["hostile"]["noul"]),3),
            "same_day": round(float(a["same_day"]["noul"]),3)}

# 2 fresh passes
fresh = {"es":[], "en":[]}
cost = 0.0
for rep in range(2):
    for lang in ["es","en"]:
        for c in cases:
            out, ms = run_jev(c[lang], QS)
            cost += out.get("usage",{}).get("cost",0) or 0
            fresh[lang].append({"case":c["name"],"pred":parse(out)})
            time.sleep(0.25)
json.dump({"pass3_es":fresh["es"][:14], "pass3_en":fresh["en"][:14],
           "pass4_es":fresh["es"][14:], "pass4_en":fresh["en"][14:]},
          open(f"{OUT}/jev_triage_v3v4.json","w"), ensure_ascii=False, indent=1)

# combine v2 + fresh
v2 = json.load(open(f"{OUT}/jev_triage_v2.json"))
v34 = json.load(open(f"{OUT}/jev_triage_v3v4.json"))
passes = {
 "es": [ {r["case"]:r["pred"] for r in v2["jev_es"]},
         {r["case"]:r["pred"] for r in v34["pass3_es"]},
         {r["case"]:r["pred"] for r in v34["pass4_es"]} ],
 "en": [ {r["case"]:r["pred"] for r in v2["jev_en"]},
         {r["case"]:r["pred"] for r in v34["pass3_en"]},
         {r["case"]:r["pred"] for r in v34["pass4_en"]} ],
}

def score_item(p, exp):
    s = {}
    s["department"] = 1 if p["department"]==exp["department"] else 0
    lvl = min(2, max(0, round(p["urgency"])))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical","hostile","same_day"]:
        s[k] = 1 if (1 if p[k]>=0.5 else 0) == exp[k] else 0
    return s

print(f"vote-of-3 built from 3 passes | extra cost ${cost:.5f}\n")
for lang in ["es","en"]:
    tot_single = [0.0,0.0,0.0]; tot_fused = 0.0; n = 0
    borderline_flips = []
    for c in cases:
        exp = c["expected"]
        ps = [P[c["name"]] for P in passes[lang]]
        # fused: majority dept, median urgency, majority binary
        fused = {}
        depts = [p["department"] for p in ps]
        fused["department"] = max(set(depts), key=depts.count)
        fused["urgency"] = statistics.median([p["urgency"] for p in ps])
        for k in ["clinical","hostile","same_day"]:
            votes = sum(1 for p in ps if p[k]>=0.5)
            fused[k] = votes/3.0  # >=2/3 -> >=0.667 >= 0.5 threshold
        sf = score_item(fused, exp)
        tot_fused += sum(sf.values()); n += 5
        for i,p in enumerate(ps):
            tot_single[i] += sum(score_item(p, exp).values())
        # track borderline cases where vote changed a binary outcome
        for k in ["clinical","hostile","same_day"]:
            votes = [1 if p[k]>=0.5 else 0 for p in ps]
            if len(set(votes))>1:  # disagreement
                maj = 1 if sum(votes)>=2 else 0
                single0 = votes[0]
                if maj != single0:
                    borderline_flips.append((c["name"], k, votes, exp[k]))
    print(f"{lang.upper()}: single passes {[round(100*t/n,1) for t in tot_single]}% -> vote-of-3 {100*tot_fused/n:.1f}%")
    if borderline_flips:
        for name, q, votes, gtval in borderline_flips:
            maj = 1 if sum(votes) >= 2 else 0
            tag = "FIXED" if (maj == gtval and votes[0] != gtval) else ("BROKEN" if (maj != gtval and votes[0] == gtval) else "pass0-wrong-anyway")
            print(f"   flip {name} {q}: votes={votes} gt={gtval} -> {tag}")
