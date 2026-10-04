"""Single source of truth for the battery: cases, ground truth and questions.

Questions are in TypeSafe wire format (the one Jev, Decider and Laya accept).
They are copied verbatim from legacy/lyra_laya_vs_jev/rerun_jev.py; do not edit
them without re-running every model (the scorer records a hash of each set).
"""
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

DEPT_CRITERIA = {
    "bronchoscopia": "endoscopic procedures (EBUS, bronchoscopy), their scheduling, preparation and complications",
    "consulta_externa": "outpatient clinic: results, symptoms, clinical questions, general appointments",
    "urgencias": "medical emergency or red-flag symptoms needing immediate care",
    "admin": "billing, invoices, refunds, insurance, reports copies, parking, non-clinical",
}

TRIAGE_QS = {
    "department": {"type": "choice", "instructions": "Which department should handle this message?",
                   "criteria": DEPT_CRITERIA},
    "urgency": {"type": "score", "instructions": "How urgent is this message?",
                "criteria": ["bajo: routine, no deadline", "medio: should be handled soon",
                             "critico: deadline, blocking, or safety issue"]},
    "clinical": {"type": "noul", "instructions": "Does this message contain clinical content requiring medical judgment?"},
    "hostile": {"type": "noul", "instructions": "Is the sender hostile, insulting, or threatening?"},
    "same_day": {"type": "noul", "instructions": "Does this require an answer or action TODAY (same working day)?"},
}

PAPERS_QS = {
    "relevance": {"type": "score",
                  "instructions": "How relevant is this paper to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging/precision medicine?",
                  "criteria": ["low: outside his clinical focus", "medium: adjacent or general pulmonology",
                               "high: core topic - EBUS, bronchoscopy, lung cancer, nodules, staging, MRD"]},
    "domain": {"type": "choice", "instructions": "What is the paper's main domain?",
               "criteria": {
                   "ip": "interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy, pleural",
                   "oncology": "lung cancer oncology: systemic therapy, immunotherapy, targeted therapy, MRD, staging outcomes",
                   "ai_radiology": "AI or imaging methods: deep learning, radiomics, risk models, screening CT",
                   "pulm_general": "general pulmonology: COPD, asthma, smoking, sleep, infections",
                   "other": "anything else: basic science, other organs, non-pulmonary"}},
    "design": {"type": "choice", "instructions": "What is the study design?",
               "criteria": {
                   "rct": "randomized controlled trial",
                   "meta": "systematic review or meta-analysis",
                   "cohort": "prospective or retrospective cohort / registry / diagnostic accuracy study",
                   "review": "narrative review, expert opinion, guideline",
                   "basic": "basic science: animal, molecular, cell biology"}},
    "depth": {"type": "choice",
              "instructions": "For a busy clinician building a reading pipeline: how deeply should this paper be read?",
              "criteria": {
                  "full": "read full text - practice-changing or core-method paper",
                  "abstract": "abstract only is enough",
                  "skip": "skip - not worth the time"}},
    "practice": {"type": "noul",
                 "instructions": "Could this paper change current clinical practice in lung cancer diagnosis or staging?"},
}

OOD_QS = {
    "relevance": {"type": "score",
                  "instructions": "How relevant is this text to an interventional pulmonologist specializing in EBUS, bronchoscopy and lung cancer staging?",
                  "criteria": ["low: outside his clinical focus", "medium: adjacent or general pulmonology",
                               "high: core topic - EBUS, bronchoscopy, lung cancer"]},
    "domain": {"type": "choice", "instructions": "What is this text's main domain?",
               "criteria": {
                   "ip": "interventional pulmonology: bronchoscopy, EBUS, navigation, cryobiopsy",
                   "oncology": "lung cancer oncology: therapy, MRD, staging outcomes",
                   "pulm_general": "general pulmonology: COPD, asthma, smoking, sleep",
                   "other": "anything else: recipes, law, code, finance, other organs"}},
    "clinical": {"type": "noul", "instructions": "Does this text contain clinical content requiring medical judgment?"},
}

OOD_CASES = {
    "receta": "Preheat oven to 200C. Season the chicken thighs with smoked paprika, garlic and salt. Roast 35 minutes with potatoes and rosemary until the skin is crisp. Rest 5 minutes before serving with lemon.",
    "contrato": "The Parties hereby agree that any dispute arising from this Agreement shall be settled by binding arbitration in the courts of Madrid. Clause 14.2: termination with sixty (60) days written notice. Severability: if any provision is held invalid, the remainder shall continue in full force.",
    "codigo": "def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    mid = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + mid + quicksort(right)",
}
OOD_GT = {"relevance": 0, "domain": "other", "clinical": 0}

PHASES = ["triage_es", "triage_en", "papers32", "adv1", "adv2", "ood"]
# New sets (26-sep). Loaded only once their GT is validated and promoted from data/drafts/.
EXTRA_PHASES = ["triage_ext_es", "triage_ext_en", "adv3"]
# adversarial-4 (27-sep): rule validation set; opt-in until its GT is validated (JEV-30)
RULES_PHASES = ["adv4"]
# adversarial-5 (27-sep): validation of the manipulation alert (docs/experimentos/alerta_manipulacion.md)
ALERT_PHASES = ["adv5"]


@dataclass
class Case:
    id: str
    state: str
    gt: dict


# Ground-truth revisions. JEVBENCH_GT=v1 loads the original Lyra files (used by the
# regression tests); the default is the current, corrected GT. See data/GT_CHANGELOG.md.
# Read at call time: a test module may set the variable before the first load
# even if this module was already imported by an earlier test.
GT_VERSION = os.environ.get("JEVBENCH_GT", "current")


def _load(name):
    version = os.environ.get("JEVBENCH_GT", GT_VERSION)
    if version != "current":
        versioned = DATA / name.replace(".json", f".{version}.json")
        if versioned.exists():
            return json.loads(versioned.read_text())
    return json.loads((DATA / name).read_text())


NO_ABSTRACT = "[abstract no descargado]"


def paper_state(p):
    # The public mirror ships papers32.json without abstracts (only their sha256):
    # scoring does not need them; `python3 -m jevbench.fetch_abstracts` restores them.
    return (f"Title: {p['title']}\nJournal: {p['journal']}\n"
            f"Publication types: {', '.join(p['pubtypes'])}\n\nAbstract: {p.get('abstract') or NO_ABSTRACT}")


def missing_abstracts(phase="papers32"):
    """Case ids whose source paper has no abstract downloaded."""
    if phase != "papers32":
        return []
    return [p["pid"] for p in _load("papers32.json") if not p.get("abstract")]


def load_phase(phase):
    """Return (questions, [Case]) for a phase."""
    if phase in ("triage_es", "triage_en", "triage_ext_es", "triage_ext_en"):
        lang = phase[-2:]
        fname = "triage_ext_cases.json" if "ext" in phase else "bench_cases.json"
        _require(fname)
        return TRIAGE_QS, [Case(c["name"], c[lang], c["expected"]) for c in _load(fname)]
    if phase == "papers32":
        # GT key order matters: the legacy cascade CV shuffles ids in this order
        gt = _load("paper_gt32.json")
        papers = {p["pid"]: p for p in _load("papers32.json")}
        return PAPERS_QS, [Case(pid, paper_state(papers[pid]), g) for pid, g in gt.items() if pid in papers]
    if phase in ("adv1", "adv2", "adv3", "adv4", "adv5"):
        fname = {"adv1": "adversarial_cases.json", "adv2": "adversarial2_cases.json",
                 "adv3": "adversarial3_cases.json", "adv4": "adversarial4_cases.json",
                 "adv5": "adversarial5_cases.json"}[phase]
        _require(fname)
        return TRIAGE_QS, [Case(k, v["state"], {q: a for q, a in v.items() if q not in ("state", "family", "rule_target")})
                           for k, v in _load(fname).items()]
    if phase == "ood":
        return OOD_QS, [Case(k, s, dict(OOD_GT)) for k, s in OOD_CASES.items()]
    raise ValueError(f"unknown phase {phase!r}; expected one of {PHASES + EXTRA_PHASES + RULES_PHASES + ALERT_PHASES}")


def _require(fname):
    if not (DATA / fname).exists():
        raise SystemExit(f"data/{fname} does not exist yet: its GT is pending validation "
                         f"(draft in data/drafts/, see docs/validacion_gt*.md)")


def gt_problems(phase):
    """GT values that are not a valid answer for their question (unwinnable items)."""
    qs, cases = load_phase(phase)
    bad = []
    for name, q in qs.items():
        valid = options(q) if q["type"] != "noul" else ["0", "1"]
        bad += [(c.id, name, c.gt[name]) for c in cases if str(c.gt[name]) not in valid]
    return bad


def questions_hash(qs):
    return hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest()[:12]


def options(q):
    """Ordered option labels of a choice question, or level indices of a score question."""
    if q["type"] == "choice":
        return list(q["criteria"].keys())
    if q["type"] == "score":
        return [str(i) for i in range(len(q["criteria"]))]
    return ["0", "1"]
