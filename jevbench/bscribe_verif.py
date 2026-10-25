"""JEV-111 — set opt-in «bscribe_verif»: ¿sirve un decisor System One como
verificador de BroncoScribe?

Pre-registro: docs/experimentos/bscribe_verif.md. Este módulo **no** toca la
batería principal (`battery.py`, sus `questions_hash`, el marcador ni el sitio):
tiene sus propios casos, GT, preguntas y puntuación.

Tarea: dado un dictado ficticio de broncoscopia/EBUS (guion de referencia o
transcripción ASR ya medida en BroncoScribe) y una afirmación atómica sobre él,
¿la afirmación está respaldada por el texto? Una pregunta `noul` por hecho; todas
las de un caso van en una sola llamada (como lo haría el verificador en producción).

GT por construcción (data/drafts/bscribe_verif_facts.json):
  label 1  el guion lo afirma;  label 0  ausente, otro valor, negado o corregido.
Cada hecho lleva `evidence` (regex que deben aparecer) y `trap` (regex que no
deben aparecer) sobre el texto normalizado. En el guion de referencia todos los
hechos deben cumplirlas (lo comprueba `check`); en una transcripción ASR, si no
se cumplen, el hecho queda **excluido** de esa transcripción (el ASR perdió la
evidencia o escribió el valor falso) en vez de cambiar su etiqueta.

  python3 -m jevbench.bscribe_verif build --src ~/proyectos/broncoscribe   # estados → data/drafts/
  python3 -m jevbench.bscribe_verif check [--draft]                         # coherencia del GT
  python3 -m jevbench.bscribe_verif labels --draft --md docs/validacion_gt_bscribe_verif.md
  python3 -m jevbench.bscribe_verif run clef --run bv_clef_flash_9b_xpu --opt model=Cloudflare/clef-flash ...
  python3 -m jevbench.bscribe_verif score bv_clef_flash_9b_xpu [bv_clef_27b] [--vs bv_clef_27b]

`run` solo lee los ficheros promovidos a data/ (nunca los borradores): el GT se
valida y se congela con commit antes de ejecutar ningún modelo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

from . import adapters, metrics, store

PHASE = "bscribe_verif"
DATA = Path(__file__).resolve().parent.parent / "data"
FILES = {"facts": "bscribe_verif_facts.json", "states": "bscribe_verif_states.json"}

# Fijadas en el pre-registro: cambiarlas invalida la comparación.
INSTRUCTIONS = ("Does this Spanish bronchoscopy/EBUS dictation transcript explicitly support the "
                "following claim, as the final value stated by the operator? Claim: «{claim}»")
# Formato wire de `noul`: criterios por opción {"true", "false"} (enmienda E1: el texto es el
# mismo que la cadena pre-registrada, repartido entre las dos opciones).
CRITERIA = {"true": "yes only if the transcript states it explicitly (any wording; numbers in "
                    "digits or words)",
            "false": "no if it is absent, stated with a different value, negated, or corrected "
                     "later in the dictation"}

THRESHOLD = 0.5          # decisión primaria
CONFIDENT = (0.1, 0.9)   # avisos «seguros» (p < 0.1) y errores seguros (conf. ≥ 0.9)
CRITERION = {"sensitivity_min": 0.70, "fp_rate_max": 0.05}

# Transcripciones ASR ya medidas en BroncoScribe (benchmarks/asr/fictional_v1/runs).
# (run, proveedor) → etiqueta de fuente. Los textos idénticos se deduplican por sha256.
ASR_SOURCES = [
    ("dgx-large-v3-turbo-20260517", "local:faster-whisper", "whisper_turbo_dgx"),
    ("dgx-b5-large-v3-turbo-20260518", "local:faster-whisper", "whisper_turbo_dgx"),
    ("dgx-b6-large-v3-turbo-20260522", "local:faster-whisper", "whisper_turbo_dgx"),
    ("openai-20260517", "openai:gpt-4o-mini-transcribe", "gpt4o_mini_transcribe"),
    ("openai-b5-20260518", "openai:gpt-4o-mini-transcribe", "gpt4o_mini_transcribe"),
    ("openai-b6-20260522", "openai:gpt-4o-mini-transcribe", "gpt4o_mini_transcribe"),
    ("openai-20260517", "openai:gpt-4o-transcribe", "gpt4o_transcribe"),
    ("openai-b5-20260518", "openai:gpt-4o-transcribe", "gpt4o_transcribe"),
    ("jetson-small-cpu-20260517", None, "whisper_small_jetson"),
]
MANIFESTS = ["manifest.json", "manifest_b5.json", "manifest_b6.json"]
BENCH = Path("benchmarks/asr/fictional_v1")

# Copia congelada de TRANSCRIPT_NORMALIZATION_RULES de BroncoScribe
# (backend/app/services/ai.py, 2026-10-25): el verificador ve el mismo texto que
# el extractor en producción. (nombre, patrón, reemplazo, contexto requerido)
BSCRIBE_NORMALIZATION = [
    ("rose", r"\b(?:ROS|ROSS|ROWS|ROUSE|ROUS)\b", "ROSE", None),
    ("gauge", r"\b(\d{1,2})\s+gauch(?:e|o|es)\b", r"\1 gauge", None),
    ("pases", r"\bfases\b", "pases", r"\b(?:punci[oó]n|punciona|TBNA|estaci[oó]n|aguja)\b"),
    ("eusb", r"\beus\s*-?\s*b\b", "EUS-B", None),
]


def bscribe_normalize(text: str) -> str:
    for _, pat, rep, req in BSCRIBE_NORMALIZATION:
        if req and not re.search(req, text, re.IGNORECASE):
            continue
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------- datos
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(kind: str, draft: bool = False) -> dict:
    p = DATA / ("drafts" if draft else "") / FILES[kind]
    if not p.exists():
        sys.exit(f"falta {p.relative_to(DATA.parent)}"
                 + ("" if draft else " (¿GT sin validar? usa --draft o promueve el borrador)"))
    return json.loads(p.read_text(encoding="utf-8"))


def build_states(src: Path) -> dict:
    """Guiones de referencia + transcripciones ASR del repo BroncoScribe."""
    bench = src / BENCH
    states, seen = {}, set()
    for name in MANIFESTS:
        for c in json.loads((bench / name).read_text(encoding="utf-8"))["cases"]:
            sid = f"{c['case_id']}__reference"
            if sid in states:
                continue
            text = c["reference_transcript"]
            states[sid] = {"case": c["case_id"], "module": c["module"], "source": "reference",
                           "origin": f"{BENCH}/{name}", "sha256": _sha(text), "text": text}
            seen.add((c["case_id"], _sha(text)))
    for run, provider, label in ASR_SOURCES:
        doc = json.loads((bench / "runs" / run / "results.json").read_text(encoding="utf-8"))
        for r in doc.get("results") or []:
            if provider and r.get("provider") != provider:
                continue
            text = (r.get("transcript") or r.get("text") or "").strip()
            if not text or r.get("status") not in (None, "ok"):
                continue
            key = (r["case_id"], _sha(text))
            if key in seen:
                continue
            seen.add(key)
            sid = f"{r['case_id']}__{label}"
            assert sid not in states, f"fuente duplicada con texto distinto: {sid}"
            norm = bscribe_normalize(text)
            states[sid] = {"case": r["case_id"], "module": r.get("module") or r["case_id"][0],
                           "source": label, "origin": f"{BENCH}/runs/{run}/results.json",
                           "sha256": _sha(text), "raw_text": text, "text": norm}
    return {"set": PHASE, "created": dt.date.today().isoformat(),
            "note": "Textos ficticios/sintéticos de BroncoScribe; procedencia en `origin`. "
                    "`text` (el estado que se envía) = `raw_text` con las reglas de "
                    "BSCRIBE_NORMALIZATION; en los guiones de referencia no cambia nada.",
            "states": dict(sorted(states.items()))}


# ---------------------------------------------------------------- GT por estado
def status(fact: dict, text: str) -> str:
    """'included' o el motivo de exclusión en este texto."""
    norm = normalize(text)
    if not all(re.search(p, norm) for p in fact["evidence"]):
        return "evidence_lost"
    if any(re.search(p, norm) for p in fact["trap"]):
        return "trap_present"
    return "included"


def label_table(facts: dict, states: dict) -> list[dict]:
    rows = []
    for sid, st in states["states"].items():
        for f in facts["cases"].get(st["case"], []):
            rows.append({"state": sid, "case": st["case"], "source": st["source"], "fact": f["id"],
                         "label": f["label"], "family": f["family"], "status": status(f, st["text"])})
    return rows


def check(facts: dict, states: dict) -> list[str]:
    """Problemas de coherencia; vacío = GT utilizable."""
    probs = []
    ids = [f["id"] for fs in facts["cases"].values() for f in fs]
    if len(ids) != len(set(ids)):
        probs.append("ids de hecho repetidos")
    for case, fs in facts["cases"].items():
        for f in fs:
            if f["label"] not in (0, 1):
                probs.append(f"{f['id']}: label inválido")
            if f["label"] == 1 and not f["evidence"]:
                probs.append(f"{f['id']}: hecho verdadero sin evidencia")
            if f["label"] == 0 and not (f["trap"] or f["evidence"]):
                probs.append(f"{f['id']}: hecho falso sin trampa ni evidencia")
            for p in f["evidence"] + f["trap"]:
                try:
                    re.compile(p)
                except re.error as e:
                    probs.append(f"{f['id']}: regex inválida {p!r}: {e}")
    for row in label_table(facts, states):
        if row["source"] == "reference" and row["status"] != "included":
            probs.append(f"{row['fact']}: {row['status']} en el guion de referencia")
    cases = {st["case"] for st in states["states"].values()}
    probs += [f"caso sin hechos: {c}" for c in sorted(cases - set(facts["cases"]))]
    return probs


def questions_for(case_facts: list[dict]) -> dict:
    return {f"f_{f['id'].replace('-', '_')}": {"type": "noul",
                                                "instructions": INSTRUCTIONS.format(claim=f["claim"]),
                                                "criteria": CRITERIA}
            for f in case_facts}


def questions_hash(facts: dict) -> str:
    allq = {c: questions_for(fs) for c, fs in sorted(facts["cases"].items())}
    return hashlib.sha256(json.dumps(allq, sort_keys=True).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- ejecución
def run(adapter_name: str, run_name: str, opts: dict, limit: int | None = None,
        max_questions: int | None = None) -> Path:
    facts, states = load("facts"), load("states")
    probs = check(facts, states)
    if probs:
        sys.exit("GT incoherente:\n  " + "\n  ".join(probs))
    model = adapters.get(adapter_name)(**opts)
    doc = store.load(run_name, PHASE) or {"meta": {}, "cases": {}}
    doc["meta"].update({"adapter": adapter_name, **model.meta(), "phase": PHASE,
                        "questions_hash": questions_hash(facts),
                        "facts_sha256": _sha(json.dumps(facts, sort_keys=True)),
                        "states_sha256": _sha(json.dumps(states, sort_keys=True)),
                        "max_questions": max_questions,
                        "host": platform.node(), "arch": platform.machine(),
                        "updated": dt.datetime.now().isoformat(timespec="seconds")})
    todo = [s for s in states["states"] if s not in doc["cases"] or "error" in doc["cases"][s]]
    for sid in todo[:limit] if limit else todo:
        st = states["states"][sid]
        qs = questions_for(facts["cases"][st["case"]])
        t0 = time.time()
        try:
            # Variante E3: como mucho `max_questions` preguntas por llamada (mismo orden);
            # por defecto, todas las del caso en una sola llamada (pre-registro).
            items = list(qs.items())
            step = max_questions or len(items)
            answers, cost, model_id = {}, None, None
            for i in range(0, len(items), step):
                out = model.decide(st["text"], dict(items[i:i + step]))
                answers.update(out["answers"])
                if out.get("cost") is not None:
                    cost = (cost or 0) + out["cost"]
                model_id = out.get("model") or model_id
            doc["cases"][sid] = {"answers": answers, "ms": int((time.time() - t0) * 1000),
                                 "cost": cost, "model": model_id}
        except Exception as e:  # el caso queda con error y se reintenta en la siguiente pasada
            doc["cases"][sid] = {"error": f"{type(e).__name__}: {e}"}
        doc["meta"].update(model.meta())  # p. ej. la versión resuelta, que se conoce tras la 1.ª llamada
        store.save(run_name, PHASE, doc)
        print(sid, "error" if "error" in doc["cases"][sid] else f"{doc['cases'][sid]['ms']} ms", flush=True)
    return store.path(run_name, PHASE)


# ---------------------------------------------------------------- puntuación
def decisions(run_name: str, facts: dict, states: dict) -> list[dict]:
    doc = store.load(run_name, PHASE)
    if not doc:
        sys.exit(f"sin resultados: {run_name}")
    out = []
    for row in label_table(facts, states):
        if row["status"] != "included":
            continue
        rec = doc["cases"].get(row["state"]) or {}
        ans = (rec.get("answers") or {}).get(f"f_{row['fact'].replace('-', '_')}")
        if ans is None:
            continue
        p = metrics.normalize(ans, {"type": "noul"})["value"]
        out.append({**row, "p": p, "hit": (p >= THRESHOLD) == bool(row["label"])})
    return out


def _rates(ds: list[dict]) -> dict:
    neg = [d for d in ds if d["label"] == 0]
    pos = [d for d in ds if d["label"] == 1]
    def frac(xs, cond):
        return sum(1 for d in xs if cond(d)) / len(xs) if xs else float("nan")
    conf = [d for d in ds if max(d["p"], 1 - d["p"]) >= CONFIDENT[1]]
    return {"n": len(ds), "n_pos": len(pos), "n_neg": len(neg),
            "accuracy": frac(ds, lambda d: d["hit"]),
            "sensitivity": frac(neg, lambda d: d["p"] < THRESHOLD),
            "fp_rate": frac(pos, lambda d: d["p"] < THRESHOLD),
            "sensitivity_conf": frac(neg, lambda d: d["p"] < CONFIDENT[0]),
            "fp_rate_conf": frac(pos, lambda d: d["p"] < CONFIDENT[0]),
            "brier": sum((d["p"] - d["label"]) ** 2 for d in ds) / len(ds) if ds else float("nan"),
            "confident_errors_per100": 100 * sum(1 for d in conf if not d["hit"]) / len(ds) if ds else float("nan")}


def cluster_ci(ds: list[dict], key: str, iters: int = 2000, seed: int = 0) -> tuple[float, float]:
    """IC 95 % remuestreando casos clínicos (las decisiones de un caso no son independientes)."""
    by_case: dict[str, list[dict]] = {}
    for d in ds:
        by_case.setdefault(d["case"], []).append(d)
    cases, rng, vals = sorted(by_case), random.Random(seed), []
    for _ in range(iters):
        sample = [d for _ in cases for d in by_case[rng.choice(cases)]]
        v = _rates(sample)[key]
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(len(vals) * 0.025)], vals[int(len(vals) * 0.975) - 1]) if vals else (float("nan"),) * 2


def majority(ds: list[dict]) -> float:
    pos = sum(d["label"] for d in ds)
    return max(pos, len(ds) - pos) / len(ds) if ds else float("nan")


def verdict(r: dict) -> str:
    ok = r["sensitivity"] >= CRITERION["sensitivity_min"] and r["fp_rate"] <= CRITERION["fp_rate_max"]
    return "CUMPLE" if ok else "NO CUMPLE"


def report(runs: list[str], vs: str | None = None) -> str:
    facts, states = load("facts"), load("states")
    lines = []
    for name in runs:
        ds = decisions(name, facts, states)
        r = _rates(ds)
        lines += [f"## {name}", "",
                  f"Decisiones incluidas: {r['n']} ({r['n_pos']} verdaderas, {r['n_neg']} falsas); "
                  f"mayoría constante {majority(ds):.3f}.", "",
                  "| métrica | valor | IC 95 % (por caso) |", "|---|---|---|"]
        for k in ("accuracy", "sensitivity", "fp_rate"):
            lo, hi = cluster_ci(ds, k)
            lines.append(f"| {k} | {r[k]:.3f} | {lo:.3f}–{hi:.3f} |")
        for k in ("sensitivity_conf", "fp_rate_conf", "brier", "confident_errors_per100"):
            lines.append(f"| {k} | {r[k]:.3f} | |")
        lines += ["", f"**Criterio pre-registrado** (sensibilidad ≥ {CRITERION['sensitivity_min']}, "
                      f"FP ≤ {CRITERION['fp_rate_max']}): **{verdict(r)}**", "",
                  "| fuente | n | accuracy | sensibilidad | FP |", "|---|---|---|---|---|"]
        for src in sorted({d["source"] for d in ds}):
            s = _rates([d for d in ds if d["source"] == src])
            lines.append(f"| {src} | {s['n']} | {s['accuracy']:.3f} | {s['sensitivity']:.3f} | {s['fp_rate']:.3f} |")
        lines += ["", "| familia | n | accuracy | sensibilidad | FP |", "|---|---|---|---|---|"]
        for fam in sorted({d["family"] for d in ds}):
            s = _rates([d for d in ds if d["family"] == fam])
            lines.append(f"| {fam} | {s['n']} | {s['accuracy']:.3f} | {s['sensitivity']:.3f} | {s['fp_rate']:.3f} |")
        lines.append("")
    if vs:
        base = {(d["state"], d["fact"]): d["hit"] for d in decisions(vs, facts, states)}
        for name in runs:
            if name == vs:
                continue
            cur = {(d["state"], d["fact"]): d["hit"] for d in decisions(name, facts, states)}
            keys = sorted(set(base) & set(cur))
            b, c, p = metrics.mcnemar([cur[k] for k in keys], [base[k] for k in keys])
            lines.append(f"McNemar {name} vs {vs} (descriptivo; decisiones agrupadas por caso): "
                         f"n={len(keys)} b={b} c={c} p={p:.3f}")
    return "\n".join(lines)


def labels_md(facts: dict, states: dict) -> str:
    rows = label_table(facts, states)
    out = ["# Validación del GT — bscribe_verif (borrador)", "",
           "Generado con `python3 -m jevbench.bscribe_verif labels --draft --md …`. "
           "Pre-registro: `docs/experimentos/bscribe_verif.md` (JEV-111; validación JEV-112). "
           "Las dudas concretas para validar están en su sección «Dudas para la validación».", "",
           "## 1. Hechos por caso", ""]
    for case, fs in facts["cases"].items():
        out += [f"### {case}", "", "| id | etiqueta | familia | afirmación | nota |", "|---|---|---|---|---|"]
        for f in fs:
            out.append(f"| {f['id']} | {f['label']} | {f['family']} | {f['claim']} | "
                       f"{'⚠ ' + f['warn'] if f.get('warn') else ''} |")
        out.append("")
    excl = [r for r in rows if r["status"] != "included"]
    out += ["## 2. Exclusiones automáticas en transcripciones ASR", "",
            f"{len(rows)} pares estado×hecho; {len(rows) - len(excl)} incluidos, {len(excl)} excluidos. "
            "Revisar a mano que cada exclusión es real (el ASR perdió la evidencia o escribió el valor "
            "falso) y no un patrón demasiado estricto.", "",
            "| estado | hecho | etiqueta | motivo |", "|---|---|---|---|"]
    out += [f"| {r['state']} | {r['fact']} | {r['label']} | {r['status']} |" for r in excl]
    inc = [r for r in rows if r["status"] == "included"]
    pos = sum(r["label"] for r in inc)
    out += ["", "## 3. Reparto", "",
            f"Incluidos: {len(inc)} ({pos} verdaderos, {len(inc) - pos} falsos); "
            f"mayoría constante {max(pos, len(inc) - pos) / len(inc):.3f}.", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", required=True, type=Path, help="raíz del repo BroncoScribe")
    c = sub.add_parser("check")
    c.add_argument("--draft", action="store_true")
    lb = sub.add_parser("labels")
    lb.add_argument("--draft", action="store_true")
    lb.add_argument("--md", type=Path)
    r = sub.add_parser("run")
    r.add_argument("adapter", choices=sorted(adapters.REGISTRY))
    r.add_argument("--run", required=True)
    r.add_argument("--opt", action="append", default=[])
    r.add_argument("--limit", type=int)
    r.add_argument("--max-questions", type=int, help="preguntas por llamada (variante E3)")
    s = sub.add_parser("score")
    s.add_argument("runs", nargs="+")
    s.add_argument("--vs")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        p = DATA / "drafts" / FILES["states"]
        doc = build_states(a.src.expanduser())
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(doc['states'])} estados → {p.relative_to(DATA.parent)}")
    elif a.cmd == "check":
        probs = check(load("facts", a.draft), load("states", a.draft))
        print("\n".join(probs) if probs else "GT coherente")
        sys.exit(1 if probs else 0)
    elif a.cmd == "labels":
        md = labels_md(load("facts", a.draft), load("states", a.draft))
        if a.md:
            a.md.write_text(md + "\n", encoding="utf-8")
            print(f"→ {a.md}")
        else:
            print(md)
    elif a.cmd == "run":
        print(run(a.adapter, a.run, dict(o.split("=", 1) for o in a.opt), a.limit, a.max_questions))
    elif a.cmd == "score":
        print(report(a.runs, a.vs))


if __name__ == "__main__":
    main()
