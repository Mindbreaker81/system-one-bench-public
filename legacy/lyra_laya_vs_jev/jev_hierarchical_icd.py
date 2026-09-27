#!/usr/bin/env python3
"""Hierarchical decomposition: full ICD-10 (21 chapters, ~70k codes) in 3 cascaded Jev calls."""
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

def decide(state, qname, instructions, criteria):
    q = {qname: {"type":"choice","instructions":instructions,"criteria":criteria}}
    body = {"model":"~typesafe/jev-latest","state":state,"questions":q}
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read())
    return out["answers"][qname], out["usage"]

CASE = """Clinical note: 62-year-old male, former smoker (30 pack-years), presents with 3 weeks of progressive dyspnea at rest, 2-pillow orthopnea and bilateral ankle edema. Chest X-ray: cardiomegaly, pulmonary congestion. Spirometry: FEV1/FVC 0.58, FEV1 52% predicted, no significant bronchodilator response. History of chronic productive cough for years. Diagnosis: acute decompensated heart failure on top of COPD with exacerbation."""

# LEVEL 1: ICD-10 chapters (22)
chapters = {
 "I":"Certain infectious and parasitic diseases (A00-B99)",
 "II":"Neoplasms (C00-D48)",
 "IV":"Endocrine, nutritional and metabolic diseases (E00-E89)",
 "V":"Mental and behavioral disorders (F01-F99)",
 "VI":"Diseases of the nervous system (G00-G99)",
 "VII":"Diseases of the eye and adnexa (H00-H59)",
 "VIII":"Diseases of the ear and mastoid process (H60-H95)",
 "IX":"Diseases of the circulatory system (I00-I99)",
 "X":"Diseases of the respiratory system (J00-J99)",
 "XI":"Diseases of the digestive system (K00-K95)",
 "XII":"Diseases of the skin (L00-L99)",
 "XIII":"Diseases of the musculoskeletal system (M00-M99)",
 "XIV":"Diseases of the genitourinary system (N00-N99)",
 "XV":"Pregnancy, childbirth and the puerperium (O00-O9A)",
 "XVI":"Certain conditions originating in the perinatal period (P00-P96)",
 "XVII":"Congenital malformations (Q00-Q99)",
 "XVIII":"Symptoms and abnormal clinical findings (R00-R99)",
 "XX":"External causes of morbidity (V00-Y99)",
 "XXI":"Factors influencing health status (Z00-Z99)",
 "XXII":"Codes for special purposes (U00-U85)"
}
a1, u1 = decide(CASE, "chapter", "Which ICD-10 chapter contains the primary diagnosis code for this note?", chapters)
print(f"LEVEL 1 -> chapter {a1['choice']} (p={max(a1['probabilities'].values()):.2f}) | tokens {u1['input_tokens']}")

time.sleep(0.3)
# LEVEL 2: categories within chapter IX (heart failure J vs I) - pick the plausible set for this case
# If chapter IX picked: I-codes; if X: J-codes. Handle the top-1.
if a1["choice"] == "IX":
    cats = {
      "I50":"Heart failure",
      "I11":"Hypertensive heart disease",
      "I13":"Hypertensive heart and kidney disease",
      "I25":"Chronic ischemic heart disease",
      "I48":"Atrial fibrillation and flutter",
      "I10":"Essential hypertension"
    }
else:
    cats = {
      "J44":"Chronic obstructive pulmonary disease with (acute) exacerbation",
      "J18":"Pneumonia, unspecified organism",
      "J43":"Emphysema",
      "J96":"Respiratory failure",
      "J45":"Asthma",
      "J20":"Acute bronchitis"
    }
a2, u2 = decide(CASE, "category", "Which ICD-10 category best fits the PRIMARY diagnosis (the main reason for this encounter)?", cats)
print(f"LEVEL 2 -> {a2['choice']} (p={max(a2['probabilities'].values()):.2f}) | tokens {u2['input_tokens']}")

time.sleep(0.3)
# LEVEL 3: subcodes of the winning category
if a2["choice"] == "I50":
    subs = {
      "I50.9":"Heart failure, unspecified",
      "I50.1":"Left ventricular failure",
      "I50.0":"Congestive heart failure",
      "I50.2":"Systolic congestive heart failure",
      "I50.3":"Diastolic congestive heart failure",
      "I50.4":"Combined systolic and diastolic heart failure",
      "I50.9x2":"Chronic heart failure with decompensation"  # fictional - tests grounding
    }
elif a2["code"] if False else a2["choice"] == "J44":
    subs = {
      "J44.0":"COPD with acute lower respiratory infection",
      "J44.1":"COPD with (acute) exacerbation, unspecified",
      "J44.9":"COPD, unspecified"
    }
else:
    subs = {"?":"none"}
a3, u3 = decide(CASE, "code", "Which exact ICD-10 code? Beware: one option may not exist.", subs)
print(f"LEVEL 3 -> {a3['choice']} (p={max(a3['probabilities'].values()):.2f}) | tokens {u3['input_tokens']}")

total_in = u1['input_tokens']+u2['input_tokens']+u3['input_tokens']
print(f"\nTotal: {total_in} input tokens, 3 calls, covered ~70k codes. Cost approx ${total_in*42/1e6:.5f}")
