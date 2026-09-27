#!/usr/bin/env python3
"""Fetch 32 real PubMed abstracts, balanced across categories."""
import json, time, urllib.request, urllib.parse, re

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()

queries = [
 ("P01","endobronchial ultrasound EBUS-TBNA mediastinal staging lung cancer meta-analysis"),
 ("P02","robotic bronchoscopy peripheral pulmonary nodule diagnostic yield randomized"),
 ("P03","navigation bronchoscopy systematic review meta-analysis diagnostic yield"),
 ("P04","transbronchial cryobiopsy interstitial lung disease diagnostic accuracy"),
 ("P05","EBUS elastography mediastinal lymph node differentiation"),
 ("P06","radial EBUS peripheral lung lesion diagnostic yield"),
 ("P07","bronchial thermoplasty severe asthma randomized controlled trial"),
 ("P08","indwelling pleural catheter malignant pleural effusion randomized"),
 ("P09","osimertinib adjuvant EGFR mutation non-small cell lung cancer ADAURA"),
 ("P10","circulating tumor DNA minimal residual detection NSCLC postoperative"),
 ("P11","sotorasib KRAS G12C non-small cell lung cancer"),
 ("P12","pembrolizumab PD-L1 biomarker first-line NSCLC"),
 ("P13","durvalumab consolidation chemoradiotherapy stage III NSCLC PACIFIC"),
 ("P14","deep learning lung cancer risk pulmonary nodule malignancy prediction"),
 ("P15","radiomics CT lung nodule histology prediction"),
 ("P16","deep learning electrocardiogram atrial fibrillation detection"),
 ("P17","artificial intelligence diabetic retinopathy screening"),
 ("P18","glucocorticoid acute exacerbation COPD randomized trial"),
 ("P19","omalizumab severe asthma exacerbation trial"),
 ("P20","CPAP obstructive sleep apnea cardiovascular outcomes trial"),
 ("P21","varenicline smoking cessation efficacy trial"),
 ("P22","D-dimer pulmonary embolism rule-out diagnostic strategy"),
 ("P23","telomerase TERT mouse model cellular aging"),
 ("P24","inflammatory bowel disease biologic therapy maintenance"),
 ("P25","transcatheter aortic valve implantation outcomes registry"),
 ("P26","renal cell carcinoma immune checkpoint inhibitor"),
 ("P27","endobronchial ultrasound training simulator competency"),
 ("P28","moderate sedation bronchoscopy randomized trial"),
 ("P29","lung cancer screening shared decision making low-dose CT"),
 ("P30","lung cancer screening LDCT mortality NELSON trial"),
 ("P31","EBUS needle sample cell block biomarker NSCLC precision oncology"),
 ("P32","molecular profiling lung cancer biopsy tissue next generation sequencing"),
]

out = []
for pid, q in queries:
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=" + urllib.parse.quote(q) + "&retmode=json&retmax=3&sort=relevance"
    try:
        j = json.loads(get(u))
    except Exception as e:
        print(pid, "ERR", e); continue
    ids = j["esearchresult"]["idlist"]
    if not ids:
        print(pid, "NO RESULTS", q); continue
    time.sleep(0.4)
    us = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=" + ",".join(ids) + "&retmode=json"
    js = json.loads(get(us))
    best = None
    for pmid in ids:
        r = js["result"][pmid]
        if r.get("title","").strip():
            best = r; break
    time.sleep(0.4)
    ua = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=" + best["uid"] + "&rettype=abstract&retmode=text"
    abstract = re.sub(r"\s*\n\s*", " ", get(ua).strip())
    out.append({
        "pid": pid, "pmid": best["uid"], "title": best["title"].strip(),
        "journal": best.get("source",""), "pubtypes": best.get("pubtype",[]),
        "abstract": abstract
    })
    print(pid, best["uid"], "|", best["title"][:75])
    time.sleep(0.4)

json.dump(out, open("/opt/data/laya_vs_jev/papers32.json","w"), ensure_ascii=False, indent=1)
print("saved", len(out))
