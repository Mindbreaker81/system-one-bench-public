#!/usr/bin/env python3
"""1) Verify Jev's option-count limit (255/256/300). 2) Hierarchical ICD-10 demo: chapter -> category."""
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

def decide(state, questions):
    body = {"model":"~typesafe/jev-latest","state":state,"questions":questions}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    t0=time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
        return out, (time.time()-t0)*1000, None
    except urllib.error.HTTPError as e:
        return None, (time.time()-t0)*1000, e.read().decode()[:300]

# ---- 1) option limit ----
print("=== OPTION COUNT LIMIT ===")
for n in [255, 256, 300]:
    crit = {f"opt_{i:03d}": f"syndrome variant number {i} of {n}" for i in range(n)}
    q = {"q": {"type":"choice","instructions":"Which option matches best?","criteria":crit}}
    state = "Patient presents with syndrome variant number 200 of the list below."
    out, ms, err = decide(state, q)
    if err: print(f"n={n}: HTTP ERROR -> {err}")
    else:
        a = out["answers"]["q"]
        print(f"n={n}: OK {ms:.0f}ms -> {a['choice']} | usage: {out.get('usage',{})}")
    time.sleep(0.4)
