#!/usr/bin/env python3
"""Jev on totally OOD non-medical inputs: does it confabulate or flag irrelevance?"""
import json, time, subprocess, urllib.request

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

for name, state in OOD.items():
    body = {"model":"~typesafe/jev-latest","state":state,"questions":QUESTIONS}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    a = out["answers"]
    print(f"{name}: rel={a['relevance']['score']:.2f} dom={a['domain']['choice']} (p={max(a['domain']['probabilities'].values()):.2f}) clinical={a['clinical']['noul']:.2f}")
    time.sleep(0.3)
