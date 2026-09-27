#!/usr/bin/env python3
"""Benchmark Jev (OpenRouter decisions API) vs Laya (local) - ES & EN, 14 cases x 5 questions."""
import os, json, time, subprocess, urllib.request

os.environ["USE_TF"] = "0"

BASE = "/opt/data/laya_vs_jev"
cases = json.load(open(f"{BASE}/bench_cases.json"))

# ---------- key ----------
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
KEY = get_key(); assert KEY, "no OPENROUTER_API_KEY"

# ---------- questions ----------
def questions(lang):
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

# ---------- Jev ----------
def run_jev(state, qs):
    body = {"model":"~typesafe/jev-latest","state":state,"questions":qs}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    return out, (time.time()-t0)*1000

# ---------- parse ----------
def parse(res, qs):
    a = res.get("answers", res)  # laya returns {"answers":...}, jev top-level answers
    if "answers" in a: a = a["answers"]
    p = {}
    d = a.get("department",{})
    p["department"] = d.get("choice")
    p["department_probs"] = d.get("probabilities")
    u = a.get("urgency",{})
    p["urgency"] = round(float(u.get("score",0)),2)
    p["urgency_probs"] = u.get("probabilities")
    p["clinical"] = round(float(a.get("clinical",{}).get("noul",0)),3)
    p["hostile"] = round(float(a.get("hostile",{}).get("noul",0)),3)
    p["same_day"] = round(float(a.get("same_day",{}).get("noul",0)),3)
    return p

def score(p, exp):
    s = {}
    s["department"] = 1 if p["department"]==exp["department"] else 0
    # urgency: exact level (round score to nearest int of 0..2) counts 1, adjacent 0.5
    lvl = min(2, max(0, round(p["urgency"])))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical","hostile","same_day"]:
        pred = 1 if p[k] >= 0.5 else 0
        s[k] = 1 if pred == exp[k] else 0
    return s

# ---------- run jev ----------
results = {"jev_es":[], "jev_en":[]}
for lang in ["es","en"]:
    qs = questions(lang)
    for c in cases:
        try:
            out, ms = run_jev(c[lang], qs)
            p = parse(out, qs); s = score(p, c["expected"])
            results[f"jev_{lang}"].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
            print(f"jev_{lang} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms")
        except Exception as e:
            results[f"jev_{lang}"].append({"case":c["name"],"error":str(e)[:200]})
            print(f"jev_{lang} {c['name']}: ERROR {str(e)[:100]}")
        time.sleep(0.3)

json.dump(results, open(f"{BASE}/jev_results.json","w"), ensure_ascii=False, indent=1)
print("--- jev done ---")
