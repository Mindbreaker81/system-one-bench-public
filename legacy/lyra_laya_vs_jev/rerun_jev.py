#!/usr/bin/env python3
"""RERUN 2026-09-23: repeat the exact original benchmarks against current
~typesafe/jev-latest. Saves to *_v2 files. Originals stay untouched."""
import os, json, time, subprocess, urllib.request, sys

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/rerun"
os.makedirs(OUT, exist_ok=True)

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

def run_jev(state, qs, retries=3):
    body = {"model":"~typesafe/jev-latest","state":state,"questions":qs}
    for attempt in range(retries):
        try:
            req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
                data=json.dumps(body).encode(),
                headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
            t0=time.time()
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read())
            return out, (time.time()-t0)*1000
        except Exception as e:
            if attempt == retries-1: raise
            time.sleep(2*(attempt+1))

# ============ ROUND 1+2: triage, 14 cases x 5 questions, ES + EN ============
cases = json.load(open(f"{BASE}/bench_cases.json"))

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

def parse_triage(res):
    a = res.get("answers", res)
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

def score_triage(p, exp):
    s = {}
    s["department"] = 1 if p["department"]==exp["department"] else 0
    lvl = min(2, max(0, round(p["urgency"])))
    if lvl == exp["urgency"]: s["urgency"] = 1
    elif abs(lvl - exp["urgency"]) == 1: s["urgency"] = 0.5
    else: s["urgency"] = 0
    for k in ["clinical","hostile","same_day"]:
        pred = 1 if p[k] >= 0.5 else 0
        s[k] = 1 if pred == exp[k] else 0
    return s

if "--triage" in sys.argv:
    results = {"jev_es":[], "jev_en":[]}
    cost = 0.0
    for lang in ["es","en"]:
        for c in cases:
            try:
                out, ms = run_jev(c[lang], QS_TRIAGE)
                cost += out.get("usage",{}).get("cost",0) or 0
                p = parse_triage(out); s = score_triage(p, c["expected"])
                results[f"jev_{lang}"].append({"case":c["name"],"ms":round(ms),"pred":p,"score":s})
                print(f"jev_{lang} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
            except Exception as e:
                results[f"jev_{lang}"].append({"case":c["name"],"error":str(e)[:200]})
                print(f"jev_{lang} {c['name']}: ERROR {str(e)[:100]}", flush=True)
            time.sleep(0.3)
    json.dump(results, open(f"{OUT}/jev_triage_v2.json","w"), ensure_ascii=False, indent=1)
    print(f"--- triage done, cost ${cost:.5f} ---")

# ============ ROUND 3+4: 32 papers x 5 dims ============
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

    results = []
    cost = 0.0
    for p in papers:
        try:
            out, ms = run_jev(state_for(p), QUESTIONS)
            cost += out.get("usage",{}).get("cost",0) or 0
            a = out["answers"]
            pr = {"relevance": round(float(a["relevance"]["score"]),2),
                  "domain": a["domain"]["choice"],
                  "design": a["design"]["choice"],
                  "depth": a["depth"]["choice"],
                  "practice": round(float(a["practice"]["noul"]),3)}
            results.append({"pid":p["pid"],"ms":round(ms),"pred":pr})
            print(f"jev {p['pid']}: rel={pr['relevance']} dom={pr['domain']} des={pr['design']} dep={pr['depth']} pra={pr['practice']}", flush=True)
        except Exception as e:
            results.append({"pid":p["pid"],"error":str(e)[:200]})
            print(f"jev {p['pid']}: ERROR {str(e)[:100]}", flush=True)
        time.sleep(0.3)
    json.dump(results, open(f"{OUT}/papers32_jev_v2.json","w"), indent=1)
    print(f"--- papers done, cost ${cost:.5f} ---")

# ============ ROUND 5: adversarial OOD, 10 cases ============
if "--adversarial" in sys.argv:
    acases = json.load(open(f"{BASE}/adversarial_cases.json"))
    results = []
    cost = 0.0
    for name, c in acases.items():
        try:
            out, ms = run_jev(c["state"], QS_TRIAGE)
            cost += out.get("usage",{}).get("cost",0) or 0
            a = out["answers"]
            pr = {"department":a["department"]["choice"],
                  "department_probs": a["department"].get("probabilities"),
                  "urgency":round(a["urgency"]["score"],2),
                  "clinical":round(a["clinical"]["noul"],2),
                  "hostile":round(a["hostile"]["noul"],2),
                  "same_day":round(a["same_day"]["noul"],2)}
            results.append({"case":name,"ms":round(ms),"pred":pr,"gt":{k:v for k,v in c.items() if k!="state"},
                            "model": out.get("model")})
            print(f"jev  {name}: dep={pr['department']} urg={pr['urgency']} clin={pr['clinical']} host={pr['hostile']} day={pr['same_day']}", flush=True)
        except Exception as e:
            results.append({"case":name,"error":str(e)[:200]})
            print(f"jev {name}: ERROR", flush=True)
        time.sleep(0.3)
    json.dump(results, open(f"{OUT}/adversarial_jev_v2.json","w"), indent=1)
    print(f"--- adversarial done, cost ${cost:.5f} ---")

# ============ OOD probe (receta/contrato/codigo) ============
if "--ood" in sys.argv:
    QUESTIONS_OOD = {
     "relevance": {"type":"score","instructions":"How relevant is this text to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging?",
       "criteria":["low: outside his clinical focus","medium: adjacent or general pulmonology","high: core topic - EBUS, bronchoscopy, lung cancer"]},
     "domain": {"type":"choice","instructions":"What is this text's main domain?",
       "criteria":{
         "ip":"interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy",
         "oncology":"lung cancer oncology: therapy, MRD, staging outcomes",
         "pulm_general":"general pulmonology: COPD, asthma, smoking, sleep",
         "other":"anything else: recipes, law, code, finance, other organs"}},
     "clinical": {"type":"noul","instructions":"Does this text contain clinical content requiring medical judgment?"},
    }
    OOD = {
     "receta": "Preheat oven to 200C. Season the chicken thighs with smoked paprika, garlic and salt. Roast 35 minutes with potatoes and rosemary until the skin is crisp. Rest 5 minutes before serving with lemon.",
     "contrato": "The Parties hereby agree that any dispute arising from this Agreement shall be settled by binding arbitration in the courts of Madrid. Clause 14.2: termination with sixty (60) days written notice. Severability: if any provision is held invalid, the remainder shall continue in full force.",
     "codigo": "def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    mid = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + mid + quicksort(right)",
    }
    results = []
    for name, state in OOD.items():
        out, ms = run_jev(state, QUESTIONS_OOD)
        a = out["answers"]
        pr = {"relevance": round(float(a["relevance"]["score"]),2),
              "domain": a["domain"]["choice"],
              "domain_probs": a["domain"].get("probabilities"),
              "clinical": round(float(a["clinical"]["noul"]),3)}
        results.append({"case":name,"pred":pr,"ms":round(ms)})
        print(f"ood {name}: rel={pr['relevance']} dom={pr['domain']} clinical={pr['clinical']}", flush=True)
        time.sleep(0.3)
    json.dump(results, open(f"{OUT}/ood_jev_v2.json","w"), indent=1)
    print("--- ood done ---")
