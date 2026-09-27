#!/usr/bin/env python3
"""Fetch 12 real PubMed abstracts: mix of interventional pulmonology + distractors."""
import json, time, urllib.request, urllib.parse, re

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()

queries = [
 ("P01", "EBUS-TBNA versus mediastinoscopy lung cancer staging randomized"),
 ("P02", "nivolumab non-small cell lung cancer five-year survival follow-up"),
 ("P03", "robotic bronchoscopy peripheral pulmonary nodule diagnostic yield"),
 ("P04", "circulating tumor DNA minimal residual disease NSCLC adjuvant"),
 ("P05", "deep learning lung cancer screening low-dose CT"),
 ("P06", "COPD exacerbation prednisone randomized controlled trial"),
 ("P07", "pediatric asthma exacerbation management children"),
 ("P08", "telomere length lung aging mouse model"),
 ("P09", "deep learning electrocardiogram atrial fibrillation screening"),
 ("P10", "EBUS-TBNA complications safety survey"),
 ("P11", "transbronchial cryobiopsy interstitial lung disease diagnostic"),
 ("P12", "smoking cessation behavioral intervention review"),
]

out = []
for pid, q in queries:
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=" + urllib.parse.quote(q) + "&retmode=json&retmax=3&sort=relevance"
    j = json.loads(get(u))
    ids = j["esearchresult"]["idlist"]
    if not ids:
        print(pid, "NO RESULTS", q); continue
    time.sleep(0.4)
    # summary
    us = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=" + ",".join(ids) + "&retmode=json"
    js = json.loads(get(us))
    best = None
    for pmid in ids:
        r = js["result"][pmid]
        if r.get("title","").strip():
            best = r; break
    time.sleep(0.4)
    ua = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=" + best["uid"] + "&rettype=abstract&retmode=text"
    abstract = get(ua).strip()
    abstract = re.sub(r"\s*\n\s*", " ", abstract)
    out.append({
        "pid": pid, "pmid": best["uid"], "title": best["title"].strip(),
        "journal": best.get("source",""), "pubtypes": best.get("pubtype",[]),
        "abstract": abstract
    })
    print(pid, best["uid"], "|", best["title"][:80], "|", ",".join(best.get("pubtype",[])[:3]))
    time.sleep(0.4)

json.dump(out, open("/opt/data/laya_vs_jev/papers.json","w"), ensure_ascii=False, indent=1)
print("saved", len(out), "papers")
