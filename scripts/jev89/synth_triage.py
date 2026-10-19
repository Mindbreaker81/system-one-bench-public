"""JEV-89 W3: mensajes de triaje sintéticos (ES/EN) con etiqueta fijada por construcción.

Especificación: docs/plan_modelo_propio.md §8. Qwen3.8-27B (SGLang, OpenAI-compatible) escribe un
mensaje para una tupla de etiquetas sorteada; una segunda pasada independiente lo etiqueta con las
mismas preguntas del banco (jevbench.battery.TRIAGE_QS, sin editarlo) y solo se acepta si coincide.
Nunca lee data/: los temas son catálogos propios y las semillas clínicas salen de CodiEsp (CC BY 4.0).

    python3 scripts/jev89/synth_triage.py --n 3000 \
        --endpoint http://<host-a>:8000/v1 --endpoint http://<host-b>:8000/v1 \
        --out /var/tmp/jev89/build/synth_triage.jsonl
"""
import argparse
import json
import random
import re
import sys
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jevbench.battery import TRIAGE_QS  # noqa: E402

MODEL = "qwen3.8-27b-sglang"
GEN_VERSION = "e1"  # enmienda E1: aceptación estricta y manipulación visible (§8.1)
CODIESP = "/var/tmp/jev89/datasets/zenodo/bsc/codiesp/codiesp.zip"
URG = ["bajo", "medio", "critico"]

# Catálogos propios de temas por departamento (no derivados de los casos del banco).
TOPICS = {
    "bronchoscopia": [
        "preparation and fasting instructions before a bronchoscopy",
        "rescheduling a planned endoscopic procedure",
        "anticoagulant or antiplatelet management before a procedure",
        "symptoms after a recent bronchoscopy or EBUS (fever, bleeding, chest pain)",
        "sedation questions or need for a companion after the procedure",
        "pathology or culture results pending from a recent biopsy",
        "referral request for navigation bronchoscopy or cryobiopsy",
        "device or stent follow-up after an interventional procedure",
        "consent form questions before a procedure",
        "transport or arrival time on the procedure day",
    ],
    "consulta_externa": [
        "interpretation of a recent CT scan or lab result",
        "persistent cough or breathlessness for weeks",
        "medication side effects or inhaler questions",
        "follow-up appointment request after a hospital stay",
        "question about a lung nodule surveillance schedule",
        "smoking cessation help",
        "second opinion request about a diagnosis",
        "chronic disease control (COPD, asthma, sleep apnea)",
        "work or travel fitness question related to a lung condition",
        "family member asking about a relative's treatment plan",
    ],
    "urgencias": [
        "sudden severe shortness of breath",
        "coughing up a significant amount of blood",
        "chest pain with fainting or confusion",
        "high fever and rigors after a procedure",
        "lips turning blue or oxygen saturation dropping at home",
        "suspected allergic reaction with throat swelling",
    ],
    "admin": [
        "invoice or billing error",
        "refund request",
        "insurance authorization paperwork",
        "request for a copy of medical reports",
        "parking or access problems at the hospital",
        "change of address or contact details",
        "certificate for an employer",
        "vendor or commercial offer",
        "complaint about waiting-room treatment (non-clinical)",
        "appointment confirmation letter not received",
    ],
}
ROLES = {
    "es": ["paciente", "familiar del paciente", "médico de atención primaria", "enfermera de planta",
           "otro servicio del hospital", "aseguradora", "proveedor comercial", "remitente desconocido"],
    "en": ["patient", "patient's relative", "primary care physician", "ward nurse",
           "another hospital department", "insurance company", "commercial vendor", "unknown sender"],
}


def sample_tuple(rng):
    dept = rng.choices(list(TOPICS), weights=[3, 4, 1.5, 2.5])[0]
    if dept == "urgencias":
        urg, clinical, same = 2, 1, 1
    else:
        urg = rng.choices([0, 1, 2], weights=[4, 4, 2])[0]
        clinical = 0 if dept == "admin" and rng.random() > 0.08 else (1 if dept != "admin" else 1)
        if dept == "bronchoscopia" and rng.random() < 0.25:
            clinical = 0  # logística pura del procedimiento
        same = 1 if urg == 2 else (1 if urg == 1 and rng.random() < 0.3 else 0)
    hostile = 1 if rng.random() < 0.15 else 0
    manip = dept in ("admin", "consulta_externa") and rng.random() < 0.10
    if manip:  # la urgencia que alega el remitente es fingida: la etiqueta real es baja
        urg, same = 0, 0
    return {"department": dept, "urgency": urg, "clinical": clinical, "hostile": hostile,
            "same_day": same}, manip


def load_seeds():
    seeds = {"es": [], "en": []}
    with zipfile.ZipFile(CODIESP) as z:
        for n in z.namelist():
            if n.endswith(".txt") and ("/train/" in n or "/dev/" in n):
                lang = "en" if "/text_files_en/" in n else "es"
                txt = z.read(n).decode("utf-8", "replace").strip()
                if len(txt) > 200:
                    seeds[lang].append((n.rsplit("/", 1)[1], txt[:1200]))
    return seeds


def describe(gt, lang):
    d = TRIAGE_QS["department"]["criteria"][gt["department"]]
    u = TRIAGE_QS["urgency"]["criteria"][gt["urgency"]]
    yn = (lambda b: "sí" if b else "no") if lang == "es" else (lambda b: "yes" if b else "no")
    return (f"- department: {gt['department']} ({d})\n- urgency: {u}\n"
            f"- clinical content requiring medical judgment: {yn(gt['clinical'])}\n"
            f"- sender hostile, insulting or threatening: {yn(gt['hostile'])}\n"
            f"- requires an answer or action TODAY: {yn(gt['same_day'])}")


FIRST = {"es": ["Lucía", "Javier", "Carmen", "Andrés", "Pilar", "Raúl", "Nuria", "Tomás", "Rocío", "Iker",
                 "Montse", "Álvaro", "Inés", "Joaquín", "Marisol", "Óscar", "Aitana", "Fermín"],
         "en": ["Priya", "Daniel", "Grace", "Omar", "Hannah", "Liam", "Mei", "Carlos", "Sophie", "Kwame",
                 "Ingrid", "Ravi", "Fiona", "Tobias", "Aisha", "Patrick", "Yuki", "Elena"]}
LAST = {"es": ["Ortega", "Sanz", "Iglesias", "Navarro", "Gil", "Rubio", "Molina", "Castro", "Vidal", "Pascual",
               "Herrera", "Domínguez", "Lorenzo", "Soler", "Prieto", "Calvo"],
        "en": ["Okafor", "Lindqvist", "Shah", "Brennan", "Nakamura", "Walsh", "Moreau", "Kowalski", "Reyes",
               "Fitzgerald", "Haddad", "Novak", "Osei", "Campbell", "Ferreira", "Larsen"]}
GUIDE = {
    "urgencias": "It must describe red-flag symptoms that need immediate emergency care.",
    "consulta_externa": ("It is an outpatient clinical matter and it is NOT about an endoscopic procedure "
                         "(no bronchoscopy/EBUS scheduling, preparation or complications). It must NOT describe red-flag symptoms "
                         "needing emergency care; if urgency is critical, it is because of a hard deadline "
                         "or a blocking issue (e.g. a result needed before a scheduled treatment), not an emergency."),
    "bronchoscopia": ("It is about an endoscopic procedure (scheduling, preparation, complications). It must NOT "
                      "describe an emergency needing immediate care."),
    "admin": "It is administrative/non-clinical; it must not ask for medical judgment unless the labels say so.",
}


def gen_prompt(gt, manip, lang, role, topic, seed, rng=random):
    lname = "Spanish (Spain)" if lang == "es" else "English"
    p = (f"Write ONE realistic message (email or web-form text) received by the shared inbox of a "
         f"hospital pulmonology service (it has a bronchoscopy/EBUS unit, an outpatient clinic, an "
         f"emergency line and an admin desk; the sender does not route it). Language: {lname}. Sender: {role}. "
         f"Topic: {topic}.\nThe message must objectively satisfy ALL of these labels:\n"
         f"{describe(gt, lang)}\n{GUIDE[gt['department']]}\n"
         f"If you need a person's name, use {rng.choice(FIRST[lang])} {rng.choice(LAST[lang])}; "
         f"if you need a date, use one within the next or past {rng.randint(1, 20)} days, written naturally.\n")
    if manip:
        p += ("The sender uses pressure or impersonation to get something (payment, credentials, "
              "personal data, a link to click, skipping a procedure). The deception MUST be visible in "
              "the text itself: e.g. a generic or inconsistent sender, a request to pay or log in via a "
              "link, a deadline with no real reason, contradictions with how a hospital works. The "
              "labels above describe what the message REALLY is (the claimed urgency is fake).\n")
    if seed:
        p += ("For the patient's health problem, take loose inspiration from this clinical case "
              "(do not copy sentences, names or numbers):\n<<<\n" + seed + "\n>>>\n")
    p += (f"Length: about {rng.choice([25, 40, 60, 80, 110, 140])} words. Invent plausible names, dates and details; do not use real "
          "people. Do not mention the labels or the word 'label'. Output only the message text.")
    return p


def check_prompt(text):
    qs = TRIAGE_QS
    crit = "\n".join(f"  - {k}: {v}" for k, v in qs["department"]["criteria"].items())
    return ("Read the message and answer the questions as a careful triage clerk.\n\nMESSAGE:\n<<<\n"
            f"{text}\n>>>\n\nQuestions:\n1. department — {qs['department']['instructions']}\n{crit}\n"
            f"2. urgency — {qs['urgency']['instructions']} 0={qs['urgency']['criteria'][0]}; "
            f"1={qs['urgency']['criteria'][1]}; 2={qs['urgency']['criteria'][2]}\n"
            f"3. clinical — {qs['clinical']['instructions']} (0/1)\n"
            f"4. hostile — {qs['hostile']['instructions']} (0/1)\n"
            f"5. same_day — {qs['same_day']['instructions']} (0/1)\n\n"
            'Reply with JSON only: {"department": "...", "urgency": 0|1|2, "clinical": 0|1, '
            '"hostile": 0|1, "same_day": 0|1}')


def chat(endpoint, prompt, temperature, max_tokens, tries=4):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temperature, "top_p": 0.8 if temperature else 1.0,
                       "presence_penalty": 1.5 if temperature else 0.0, "max_tokens": max_tokens,
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(endpoint + "/chat/completions", body,
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def parse_labels(s):
    """JSON del comprobador → etiquetas validadas (None si falta algo o está fuera de rango)."""
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        out = {"department": str(d["department"]).strip()}
        for q, hi in (("urgency", 2), ("clinical", 1), ("hostile", 1), ("same_day", 1)):
            v = d[q]
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= hi:
                return None
            out[q] = v
    except Exception:  # noqa: BLE001
        return None
    return out if out["department"] in TRIAGE_QS["department"]["criteria"] else None


def accept(gt, chk, manip=False):
    """Enmienda E1 (§8.1): coincidencia exacta en las cinco preguntas, sin excepción por manipulación."""
    return chk is not None and all(chk[q] == gt[q] for q in TRIAGE_QS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--endpoint", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=89)
    ap.add_argument("--workers", type=int, default=24, help="hilos por endpoint")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    seeds = load_seeds()
    out = Path(a.out)
    done = set()
    if out.exists():  # reanudable
        for line in out.open():
            done.add(json.loads(line)["meta"]["k"])
    jobs = []
    for k in range(a.n):
        lang = "es" if k % 2 == 0 else "en"
        gt, manip = sample_tuple(rng)
        role = rng.choice(ROLES[lang])
        topic = rng.choice(TOPICS[gt["department"]])
        seed = None
        if gt["clinical"] and gt["department"] != "admin" and rng.random() < 0.5:
            seed = rng.choice(seeds[lang])
        jobs.append((k, lang, gt, manip, role, topic, seed))
    jobs = [j for j in jobs if j[0] not in done]
    lock = threading.Lock()
    stats = {"ok": 0, "rej": 0, "err": 0}

    def run(job, endpoint):
        k, lang, gt, manip, role, topic, seed = job
        try:
            text = chat(endpoint, gen_prompt(gt, manip, lang, role, topic, seed and seed[1],
                                             random.Random(k * 7919 + 1)), 0.9, 600)
            raw = chat(endpoint, check_prompt(text), 0.0, 120)
        except Exception as e:  # noqa: BLE001
            with lock:
                stats["err"] += 1
                with open(str(out) + ".err.jsonl", "a") as f:
                    f.write(json.dumps({"k": k, "error": repr(e)[:300], "t": time.time()}) + "\n")
            return
        chk = parse_labels(raw)
        ok = accept(gt, chk)
        rec = {"id": f"syn-tri-{lang}-{k:05d}", "task": "triage", "lang": lang, "state": text,
               "gt": gt, "source": "synthetic_qwen38", "license": "propio (generado con Qwen3.8-27B, Apache-2.0)",
               "nc": False, "split": "", "accepted": ok,
               "meta": {"k": k, "gen_version": GEN_VERSION, "seed_run": a.seed, "role": role, "topic": topic, "manipulation": manip,
                        "seed_codiesp": seed and seed[0], "check": chk, "endpoint": endpoint.split("//")[1].split(":")[0][-3:]}}
        with lock:
            stats["ok" if ok else "rej"] += 1
            with out.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            t = sum(stats.values())
            if t % 50 == 0:
                print(f"{t}/{len(jobs)} {stats}", flush=True)

    with ThreadPoolExecutor(a.workers * len(a.endpoint)) as ex:
        for i, j in enumerate(jobs):
            ex.submit(run, j, a.endpoint[i % len(a.endpoint)])
    print("FIN", stats, flush=True)


if __name__ == "__main__":
    main()
