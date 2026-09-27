#!/usr/bin/env python3
"""AnyJev battery adapter (2026-09-25). Runs the EXISTING battery against the
AnyJev framework (Nokia Applied Research) at L0 (zero labels) with a local
HF model on CPU. Mirrors rerun_jev.py questions, GT and output format.

Usage: anyjev_run.py --model Qwen/Qwen3-1.7B --phase triage|papers|adv1|adv2|ood|all
"""
import argparse, json, os, sys, time

BASE = "/opt/data/laya_vs_jev"
OUT = f"{BASE}/anyjev_results"
os.makedirs(OUT, exist_ok=True)

from anyjev import Decider, Question
from anyjev.backends.hf import HFBackend

# ---------------- triage questions (mirrors rerun_jev.py QS_TRIAGE) ------------
DEPT_OPTS = ["bronchoscopia", "consulta_externa", "urgencias", "admin"]
DEPT_DESC = {
    "bronchoscopia": "endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
    "consulta_externa": "outpatient clinic: results, symptoms, clinical questions, general appointments",
    "urgencias": "medical emergency or red-flag symptoms needing immediate care",
    "admin": "billing, invoices, refunds, insurance, reports copies, parking, non-clinical",
}

URG_LEVELS = ["bajo: routine, no deadline",
              "medio: should be handled soon",
              "critico: deadline, blocking, or safety issue"]

def triage_questions():
    dept = Question.choice("Which department should handle this message?",
                           [f"{o} - {DEPT_DESC[o]}" for o in DEPT_OPTS], name="department")
    urg = Question.score("How urgent is this message?", levels=URG_LEVELS, name="urgency")
    clin = Question.noul("Does this message contain clinical content requiring medical judgment?", name="clinical")
    host = Question.noul("Is the sender hostile, insulting, or threatening?", name="hostile")
    sday = Question.noul("Does this require an answer or action TODAY (same working day)?", name="same_day")
    return [dept, urg, clin, host, sday]

# ---------------- papers questions (mirrors rerun_jev.py QUESTIONS) ------------
REL_LEVELS = ["low: outside his clinical focus",
              "medium: adjacent or general pulmonology",
              "high: core topic - EBUS, bronchoscopy, lung cancer, nodules, staging, MRD"]
DOM_OPTS = ["ip", "oncology", "ai_radiology", "pulm_general", "other"]
DOM_DESC = {
    "ip": "interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy, pleural",
    "oncology": "lung cancer oncology: systemic therapy, immunotherapy, targeted therapy, MRD, staging outcomes",
    "ai_radiology": "AI or imaging methods: deep learning, radiomics, risk models, screening CT",
    "pulm_general": "general pulmonology: COPD, asthma, smoking, sleep, infections",
    "other": "anything else: basic science, other organs, non-pulmonary",
}
DES_OPTS = ["rct", "meta", "cohort", "review", "basic"]
DES_DESC = {
    "rct": "randomized controlled trial",
    "meta": "systematic review or meta-analysis",
    "cohort": "prospective or retrospective cohort / registry / diagnostic accuracy study",
    "review": "narrative review, expert opinion, guideline",
    "basic": "basic science: animal, molecular, cell biology",
}
DEPTH_OPTS = ["full", "abstract", "skip"]
DEPTH_DESC = ["read full text - practice-changing or core-method paper",
              "abstract only is enough",
              "skip - not worth the time"]

def papers_questions():
    rel = Question.score("How relevant is this paper to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging/precision medicine?",
                         levels=REL_LEVELS, name="relevance")
    dom = Question.choice("What is the paper's main domain?",
                          [f"{o} - {DOM_DESC[o]}" for o in DOM_OPTS], name="domain")
    des = Question.choice("What is the study design?",
                          [f"{o} - {DES_DESC[o]}" for o in DES_OPTS], name="design")
    dep = Question.choice("For a busy clinician building a reading pipeline: how deeply should this paper be read?",
                          [f"{o} - {d}" for o, d in zip(DEPTH_OPTS, DEPTH_DESC)], name="depth")
    pra = Question.noul("Could this paper change current clinical practice in lung cancer diagnosis or staging?", name="practice")
    return [rel, dom, des, dep, pra]

# ---------------- OOD questions (mirrors rerun_jev.py QUESTIONS_OOD) -----------
def ood_questions():
    rel = Question.score("How relevant is this text to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging?",
                         levels=["low: outside his clinical focus",
                                 "medium: adjacent or general pulmonology",
                                 "high: core topic - EBUS, bronchoscopy, lung cancer"],
                         name="relevance")
    dom = Question.choice("What is this text's main domain?",
                          ["ip - interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy",
                           "oncology - lung cancer oncology: therapy, MRD, staging outcomes",
                           "pulm_general - general pulmonology: COPD, asthma, smoking, sleep",
                           "other - anything else: recipes, law, code, finance, other organs"],
                          name="domain")
    cli = Question.noul("Does this text contain clinical content requiring medical judgment?", name="clinical")
    return [rel, dom, cli]

# ---------------- parse helpers -------------------------------------------------
def parse_choice(dec, opts_with_desc, clean_opts):
    """Map option text back to clean label; dec.distribution keys carry desc."""
    dist = dec.distribution
    # options in Question order = clean_opts order, so argmax by index
    probs = [dist.get(o, 0.0) for o in opts_with_desc]
    import numpy as np
    idx = int(np.argmax(probs))
    dist_clean = {clean_opts[i]: round(float(probs[i]), 4) for i in range(len(clean_opts))}
    return clean_opts[idx], dist_clean

def run_state(decider, state, questions):
    """One decide() call; returns dict name -> raw Decision."""
    t0 = time.time()
    ds = decider.decide(state, questions)
    ms = (time.time() - t0) * 1000
    return ds, ms

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--phase", default="all", choices=["triage", "papers", "adv1", "adv2", "ood", "all"])
    ap.add_argument("--level", default="L0")
    ap.add_argument("--tag", default=None, help="output file tag (default: model shortname)")
    args = ap.parse_args()

    tag = args.tag or args.model.split("/")[-1].replace("-", "_").lower()
    print(f"loading {args.model} on cpu ...", flush=True)
    backend = HFBackend(args.model, device="cpu", dtype="float32", batch_size=8)
    decider = Decider(backend, level=args.level)
    print("model loaded", flush=True)

    dept_opts_desc = [f"{o} - {DEPT_DESC[o]}" for o in DEPT_OPTS]
    rel_opts_desc = REL_LEVELS

    def parse_triage(ds):
        dep, dep_dist = parse_choice(ds["department"], dept_opts_desc, DEPT_OPTS)
        urg_dec = ds["urgency"]
        urg_dist_raw = urg_dec.distribution  # keys = level descriptions
        urg_dist = {k: round(float(urg_dist_raw[URG_LEVELS[i]]), 4)
                    for i, k in enumerate(["low", "medium", "high"])}
        return {
            "department": dep,
            "department_probs": dep_dist,
            "urgency": round(float(urg_dec.value), 2),   # 0..2 via bin centers
            "urgency_probs": urg_dist,
            "clinical": round(float(ds["clinical"].p_true), 3),
            "hostile": round(float(ds["hostile"].p_true), 3),
            "same_day": round(float(ds["same_day"].p_true), 3),
        }

    # ============ TRIAGE: 14 cases x 5 questions, ES + EN ============
    if args.phase in ("triage", "all"):
        cases = json.load(open(f"{BASE}/bench_cases.json"))
        qs = triage_questions()
        results = {"anyjev_es": [], "anyjev_en": []}
        for lang in ["es", "en"]:
            for c in cases:
                try:
                    ds, ms = run_state(decider, c[lang], qs)
                    p = parse_triage(ds)
                    results[f"anyjev_{lang}"].append({"case": c["name"], "ms": round(ms), "pred": p})
                    print(f"anyjev_{lang} {c['name']}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']} | {ms:.0f}ms", flush=True)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    results[f"anyjev_{lang}"].append({"case": c["name"], "error": str(e)[:200]})
        json.dump(results, open(f"{OUT}/anyjev_triage_{tag}.json", "w"), ensure_ascii=False, indent=1)
        print("--- triage done ---", flush=True)

    # ============ PAPERS: 32 papers x 5 dims ============
    if args.phase in ("papers", "all"):
        papers = json.load(open(f"{BASE}/papers32.json"))
        GT = json.load(open(f"{BASE}/paper_gt32.json"))
        papers = [p for p in papers if p["pid"] in GT]
        qs = papers_questions()
        dom_opts_desc = [f"{o} - {DOM_DESC[o]}" for o in DOM_OPTS]
        des_opts_desc = [f"{o} - {DES_DESC[o]}" for o in DES_OPTS]
        dep_opts_desc = [f"{o} - {d}" for o, d in zip(DEPTH_OPTS, DEPTH_DESC)]
        results = []
        for p in papers:
            state = f"Title: {p['title']}\nJournal: {p['journal']}\nPublication types: {', '.join(p['pubtypes'])}\n\nAbstract: {p['abstract']}"
            try:
                ds, ms = run_state(decider, state, qs)
                rel_dec = ds["relevance"]
                dom, _ = parse_choice(ds["domain"], dom_opts_desc, DOM_OPTS)
                des, _ = parse_choice(ds["design"], des_opts_desc, DES_OPTS)
                dep, _ = parse_choice(ds["depth"], dep_opts_desc, DEPTH_OPTS)
                pr = {"relevance": round(float(rel_dec.value), 2),
                      "domain": dom, "design": des, "depth": dep,
                      "practice": round(float(ds["practice"].p_true), 3)}
                results.append({"pid": p["pid"], "ms": round(ms), "pred": pr})
                print(f"anyjev {p['pid']}: rel={pr['relevance']} dom={dom} des={des} dep={dep} pra={pr['practice']}", flush=True)
            except Exception as e:
                import traceback; traceback.print_exc()
                results.append({"pid": p["pid"], "error": str(e)[:200]})
        json.dump(results, open(f"{OUT}/anyjev_papers32_{tag}.json", "w"), indent=1)
        print("--- papers done ---", flush=True)

    # ============ ADVERSARIAL 1 + 2 (triage questions) ============
    for adv_file, phase in [(f"{BASE}/adversarial_cases.json", "adv1"),
                            (f"{BASE}/adversarial2_cases.json", "adv2")]:
        if args.phase in (phase, "all"):
            acases = json.load(open(adv_file))
            qs = triage_questions()
            results = []
            for name, c in acases.items():
                try:
                    ds, ms = run_state(decider, c["state"], qs)
                    p = parse_triage(ds)
                    results.append({"case": name, "ms": round(ms), "pred": p,
                                    "gt": {k: v for k, v in c.items() if k != "state"}})
                    print(f"anyjev {name}: dep={p['department']} urg={p['urgency']} clin={p['clinical']} host={p['hostile']} day={p['same_day']}", flush=True)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    results.append({"case": name, "error": str(e)[:200]})
            json.dump(results, open(f"{OUT}/anyjev_{phase}_{tag}.json", "w"), ensure_ascii=False, indent=1)
            print(f"--- {phase} done ---", flush=True)

    # ============ OOD probe ============
    if args.phase in ("ood", "all"):
        OOD = {
            "receta": "Preheat oven to 200C. Season the chicken thighs with smoked paprika, garlic and salt. Roast 35 minutes with potatoes and rosemary until the skin is crisp. Rest 5 minutes before serving with lemon.",
            "contrato": "The Parties hereby agree that any dispute arising from this Agreement shall be settled by binding arbitration in the courts of Madrid. Clause 14.2: termination with sixty (60) days written notice. Severability: if any provision is held invalid, the remainder shall continue in full force.",
            "codigo": "def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    mid = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + mid + quicksort(right)",
        }
        qs = ood_questions()
        dom_opts_desc = ["ip - interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy",
                         "oncology - lung cancer oncology: therapy, MRD, staging outcomes",
                         "pulm_general - general pulmonology: COPD, asthma, smoking, sleep",
                         "other - anything else: recipes, law, code, finance, other organs"]
        dom_clean = ["ip", "oncology", "pulm_general", "other"]
        results = []
        for name, state in OOD.items():
            try:
                ds, ms = run_state(decider, state, qs)
                dom, dom_dist = parse_choice(ds["domain"], dom_opts_desc, dom_clean)
                rel_dec = ds["relevance"]
                pr = {"relevance": round(float(rel_dec.value), 2),
                      "domain": dom, "domain_probs": dom_dist,
                      "clinical": round(float(ds["clinical"].p_true), 3)}
                results.append({"case": name, "pred": pr, "ms": round(ms)})
                print(f"ood {name}: rel={pr['relevance']} dom={dom} clinical={pr['clinical']}", flush=True)
            except Exception as e:
                import traceback; traceback.print_exc()
                results.append({"case": name, "error": str(e)[:200]})
        json.dump(results, open(f"{OUT}/anyjev_ood_{tag}.json", "w"), ensure_ascii=False, indent=1)
        print("--- ood done ---", flush=True)

if __name__ == "__main__":
    main()
