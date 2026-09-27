#!/usr/bin/env python3
"""EXPERIMENT C (free, existing data): error decorrelation Jev vs Laya.
If a disagreement gate ('escalate when models disagree on department') existed,
how many Jev errors would it catch, and at what false-alarm cost?"""
import json
B = "/opt/data/laya_vs_jev"; OUT = f"{B}/rerun"

def dept_acc(rows):
    ok = err = 0; errs = []
    for r in rows:
        gt = r["gt"]; p = r["pred"]["department"]
        if p == gt["department"]: ok += 1
        else: err += 1; errs.append(r["case"])
    return ok, err, errs

adv1 = json.load(open(f"{B}/adversarial_results.json"))
adv2j = json.load(open(f"{OUT}/adversarial_jev_v2.json"))
adv2l = json.load(open(f"{OUT}/adversarial_laya_v2.json"))
lj = {r["case"]: r for r in adv1["laya"]}
for r in adv2l: lj[r["case"]] = r

okJ, errJ, errsJ = dept_acc(adv2j)
okL, errL, errsL = dept_acc(adv2l)
print(f"Adversarial department: Jev {okJ}/10, Laya {okL}/10")
both_wrong = [c for c in errsJ if c in errsL]
laya_right = [c for c in errsJ if c not in errsL]
print(f"  Jev errors: {errsJ}")
print(f"  Laya errors: {errsL}")
print(f"  both wrong (uncatchable by disagreement): {both_wrong}")
print(f"  Jev wrong & Laya right (catchable): {laya_right}")

# disagreement gate analysis
disagree = []; false_alarms = 0
for r in adv2j:
    c = r["case"]
    dj = r["pred"]["department"]; dl = lj[c]["pred"]["department"]; gt = r["gt"]["department"]
    if dj != dl:
        disagree.append(c)
        if dj == gt: false_alarms += 1
print(f"  disagreements: {len(disagree)}/10 {disagree}")
print(f"  -> gate would escalate {len(disagree)}/10 cases; of those, Jev was right in {false_alarms} (unnecessary)")

# bench triage: ES (jev_es vs laya_ml_es), EN (jev_en vs laya_en_en) — department only
v1j = json.load(open(f"{B}/jev_results.json")); v1l = json.load(open(f"{B}/laya_results.json"))
v2j = json.load(open(f"{OUT}/jev_triage_v2.json")); v2l = json.load(open(f"{OUT}/laya_triage_v2.json"))
cases = json.load(open(f"{B}/bench_cases.json"))
exp = {c["name"]: c["expected"] for c in cases}
for lang, jl, ll in [("ES", v2j["jev_es"], v2l["laya_ml_es"]), ("EN", v2j["jev_en"], v2l["laya_en_en"])]:
    jd = {r["case"]: r["pred"]["department"] for r in jl}
    ld = {r["case"]: r["pred"]["department"] for r in ll}
    dis = [c for c in jd if jd[c]!=ld[c]]
    jev_err = [c for c in jd if jd[c]!=exp[c]["department"]]
    catch = [c for c in jev_err if c in dis and ld[c]==exp[c]["department"]]
    fa = [c for c in dis if jd[c]==exp[c]["department"]]
    print(f"\nBench {lang}: disagreements {len(dis)}/14 {dis}")
    print(f"  Jev dept errors: {jev_err} | catchable by gate (Laya right): {catch} | false alarms: {len(fa)} {fa}")
