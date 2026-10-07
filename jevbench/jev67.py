"""JEV-67: Qwen3.8-27B local con preguntas visibles (thinking off, temp 0).

Pre-registro: descripción de la issue JEV-67 y docs/infra_runs/qwen38_jev67.md.

Subcomandos:

  python3 -m jevbench.jev67 gate <80|81|70> <prob|disc> <inject|nostruct|rot1>
      Puerta de visibilidad §5.1: evalúa la variante principal (3 casos, uno
      por familia de esquema) + el control negativo blind en A01 (+ las tres
      variantes si celda=rot1) y sale con código != 0 si algún criterio
      bloqueante falla. Los resultados se guardan en results/gate67_*.

  python3 -m jevbench.jev67 run <a1|a2|a3|a4|b1|b2|c1|c2> [--retry-errors]
      Supervisor de batería §5.2/5.3: reanudación protegida, regla de tokens
      del primer intento por caso (§8.1; aborta el run si falla), parada por
      fase a los 3 errores, parada del run a los 10 o al agotar el presupuesto
      de tiempo. Escribe el mismo formato que jevbench.run.

  python3 -m jevbench.jev67 report [--json out.json]
      Auditoría §5.4, ajustados, acuerdos con IC de Clopper-Pearson, métricas
      de rotación A3 (cambios, «conserva posición» Poisson-binomial, Newcombe),
      errores discrete, auditoría offline de normalize (§8.5) y tabla de
      clasificación §8.2.

Solo stdlib: los IC exactos se implementan aquí (beta incompleta regularizada,
convolución Poisson-binomial, Wilson/Newcombe).
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import platform
import statistics
import sys
import time
import traceback

from . import adapters, metrics, store
from .battery import load_phase, questions_hash
from .diag65 import (POST_CALL_KEYS, _check_resume, _merge_meta,
                     _meta_with_expected)
from .diag65 import CONFIG_KEYS
from .diag65_report import (_accuracy, _decisions, _raw_answers,
                            _validate_raw_discrete, _validate_raw_value)
from .redact import redact_options
from .rotation import rotate_choice, rotation_manifest
from .run import git_rev, git_dirty
from .score import adjusted, score_run

# ---------------------------------------------------------------- constantes

# Las 11 fases de la batería completa (194 casos con GT v4, JEV-73), orden fijado en §7.1.
PHASES_ALL = ["triage_es", "triage_en", "papers32", "adv1", "adv2", "ood",
              "triage_ext_es", "triage_ext_en", "adv3", "adv4", "adv5"]

# Identidad de servidores congelada en §7.2 (bloque -> endpoint por túnel).
HOSTS = {
    "80": {"block": "nvfp4", "base_url": "http://127.0.0.1:18000/v1",
           "model": "qwen3.8-27b-sglang"},
    "81": {"block": "fp8", "base_url": "http://127.0.0.1:18001/v1",
           "model": "qwen3.8-27b-sglang"},
    "70": {"block": "arcgguf", "base_url": "http://127.0.0.1:18002/v1",
           "model": "Qwen3.8-27B-UD-Q4_K_M.gguf"},
}

# Celdas de batería de §4.1 (nombre de run congelado).
CELLS = {
    "a1": {"run": "llm_qwen38_27b_fp8_inject_prob", "host": "81",
           "mode": "probabilities", "structured": True, "inject": True,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "a2": {"run": "llm_qwen38_27b_fp8_nostruct_t0_prob", "host": "81",
           "mode": "probabilities", "structured": False, "inject": False,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "a3": {"run": "llm_qwen38_27b_fp8_inject_rot1_prob", "host": "81",
           "mode": "probabilities", "structured": True, "inject": True,
           "rot": 1, "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "a4": {"run": "llm_qwen38_27b_fp8_inject_prob_s202", "host": "81",
           "mode": "probabilities", "structured": True, "inject": True,
           "rot": 0, "seed": 202, "phases": ["papers32", "adv3"],
           "budget_s": 30 * 60},
    "b1": {"run": "llm_qwen38_27b_nvfp4_inject_prob", "host": "80",
           "mode": "probabilities", "structured": True, "inject": True,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "b2": {"run": "llm_qwen38_27b_nvfp4_inject_disc", "host": "80",
           "mode": "discrete", "structured": True, "inject": True,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 120 * 60},
    "c1": {"run": "llm_qwen38_27b_arcgguf_inject_prob", "host": "70",
           "mode": "probabilities", "structured": True, "inject": True,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "c2": {"run": "llm_qwen38_27b_arcgguf_inject_disc", "host": "70",
           "mode": "discrete", "structured": True, "inject": True,
           "rot": 0, "seed": 101, "phases": PHASES_ALL, "budget_s": 120 * 60},
}

MODE_SLUG = {"probabilities": "prob", "discrete": "disc"}

# Referencia de tokens del primer intento (§8.1): la batería nostruct FP8
# histórica (195/195 casos, un único intento cada uno).
REF_RUN = "llm_qwen38_27b_fp8_nostruct_prob"

# Casos de la puerta §5.1: uno por familia de esquema (triaje/adv, papers, ood)
# + el control negativo en A01. Se resuelven de la batería, no se hardcodean.
GATE_PHASES = ["adv1", "papers32", "ood"]

# Familia de esquema por fase (los tres questions_hash de §7.3).
def family(phase):
    return {"papers32": "papers", "ood": "ood"}.get(phase, "triageadv")

# sha256[:12] del system prompt congelado (§7.3), por (modo, variante) y familia.
PROMPT_SHA = {
    ("probabilities", "inject"): {"triageadv": "da8dc56b75f7",
                                  "papers": "2915492ffaee", "ood": "5dbace8178de"},
    ("discrete", "inject"):    {"triageadv": "9edd553f6f42",
                                "papers": "487c9f69683b", "ood": "427ddd505638"},
    ("probabilities", "rot1"):  {"triageadv": "64191fd2a4fb",
                                 "papers": "e8761e9f8246", "ood": "a9c6380e1962"},
    ("probabilities", "blind"): {f: "388de09c70e7" for f in
                                 ("triageadv", "papers", "ood")},
    ("discrete", "blind"):      {f: "01bc74cc0141" for f in
                                 ("triageadv", "papers", "ood")},
}
# nostruct es, por construcción, el mismo system prompt que prob inject (test
# byte a byte del adaptador); la puerta lo comprueba sobre raw[0].
PROMPT_SHA[("probabilities", "nostruct")] = PROMPT_SHA[("probabilities", "inject")]

SCHEMA_MARKER = "Return one JSON object that matches this schema exactly:\n\n"
SCHEMA_TAIL = "Do not include text or Markdown fencing before or after the JSON object."


# ---------------------------------------------------------------- referencias

def load_token_ref(ref_run=REF_RUN):
    """{phase: {case_id: input_tokens}} de la batería de referencia §8.1."""
    ref = {}
    for ph in store.runs_in(ref_run):
        doc = store.load(ref_run, ph) or {}
        for cid, rec in (doc.get("cases") or {}).items():
            u = (rec.get("usage") or {}).get("input_tokens")
            if u is not None:
                ref.setdefault(ph, {})[cid] = u
    if not ref:
        raise SystemExit(f"no hay referencia de tokens en {ref_run}")
    return ref


def _gate_cases():
    """Los tres casos de la puerta: A01 + primer caso de papers32 + de ood."""
    out = []
    for ph in GATE_PHASES:
        _, cases = load_phase(ph)
        if not cases:
            raise SystemExit(f"{ph}: sin casos")
        out.append((ph, cases[0]))
    return out


def _cell_opts(cell):
    """Opciones del adaptador llm de una celda (§7.1 común + tabla de celdas)."""
    host = HOSTS[cell["host"]]
    eb = {"chat_template_kwargs": {"enable_thinking": False},
          "temperature": 0, "seed": cell["seed"]}
    return {
        "provider": "openai", "model": host["model"], "base_url": host["base_url"],
        "api_key": "none", "mode": cell["mode"],
        "structured": "true" if cell["structured"] else "false",
        "inject_schema_in_prompt": "true" if cell["inject"] else "false",
        "rotate_choice": str(cell["rot"]),
        "prompt": "typesafe", "normalize": "true", "retries_malformed": "2",
        "capture_raw": "true", "max_tokens": "8192", "timeout": "300",
        "case_timeout": "600", "extra_body": json.dumps(eb),
    }


# ----------------------------------------------------------- helpers del raw

def _first_attempt(rec):
    """raw[0] del caso (en errores, diag.raw[0]); None si no hay captura."""
    raw = rec.get("raw") or (rec.get("diag") or {}).get("raw") or []
    return raw[0] if raw else None


def _first_prompt_tokens(rec):
    """prompt_tokens del PRIMER intento; None si el servidor no da usage."""
    att = _first_attempt(rec)
    if not att:
        return None
    return ((att.get("llm_response") or {}).get("usage") or {}).get("prompt_tokens")


def _first_cached_tokens(rec):
    att = _first_attempt(rec)
    if not att:
        return None
    u = (att.get("llm_response") or {}).get("usage") or {}
    det = u.get("prompt_tokens_details") or {}
    return det.get("cached_tokens")


def _system_message(request):
    for m in request.get("messages") or []:
        if m.get("role") == "system":
            return m.get("content") or ""
    return ""


def _embedded_schema(system_msg):
    """JSON incrustado en el apéndice de esquema del system prompt; None si no."""
    if SCHEMA_MARKER not in system_msg:
        return None
    tail = system_msg.split(SCHEMA_MARKER, 1)[1]
    if not tail.endswith("\n\n" + SCHEMA_TAIL):
        return None
    try:
        return json.loads(tail[: -len("\n\n" + SCHEMA_TAIL)])
    except json.JSONDecodeError:
        return None


def _answers_properties(schema):
    """(properties por qid, $defs) resolviendo el $ref de `answers`."""
    try:
        ans = schema["properties"]["answers"]
        if "$ref" in ans:
            ans = schema["$defs"][ans["$ref"].split("/")[-1]]
        return ans.get("properties") or {}, schema.get("$defs") or {}
    except (KeyError, TypeError):
        return {}, {}


def check_question_visibility(schema, qs, mode):
    """Criterio §5.1(c): cada pregunta es propiedad de `answers` con sus
    instrucciones y sus opciones/criterios en description (cadenas
    decodificadas del JSON). Devuelve la lista de fallos."""
    fails = []
    props, defs = _answers_properties(schema)
    for qid, q in qs.items():
        field = props.get(qid)
        if field is None:
            fails.append(f"{qid}: no es propiedad de answers")
            continue
        target = field
        if "$ref" in (field or {}):
            target = defs.get(field["$ref"].split("/")[-1]) or {}
        instr = q.get("instructions") or ""
        desc = target.get("description") or ""
        if instr not in desc:
            fails.append(f"{qid}: instrucciones ausentes en description")
        qtype = q.get("type")
        if qtype == "choice":
            crit = q.get("criteria") or {}
            sub = target.get("properties") or {}
            if mode == "probabilities":
                if sorted(sub.keys()) != sorted(crit.keys()):
                    fails.append(f"{qid}: opciones del esquema != criteria")
                else:
                    for label, criterion in crit.items():
                        if (sub.get(label) or {}).get("description") != criterion:
                            fails.append(f"{qid}/{label}: criterio distinto")
            else:
                for label, criterion in crit.items():
                    if f"{label} = {criterion}" not in desc:
                        fails.append(f"{qid}/{label}: criterio ausente")
        elif qtype == "score":
            crit = q.get("criteria") or []
            if mode == "probabilities":
                sub = target.get("properties") or {}
                if set(sub.keys()) != {str(i) for i in range(len(crit))}:
                    fails.append(f"{qid}: niveles del esquema != criteria")
                else:
                    for i, criterion in enumerate(crit):
                        if (sub.get(str(i)) or {}).get("description") != criterion:
                            fails.append(f"{qid}/{i}: criterio distinto")
            else:
                for i, criterion in enumerate(crit):
                    if f"{i} = {criterion}" not in desc:
                        fails.append(f"{qid}/{i}: criterio ausente")
    return fails


def check_client(request, qs, variant, mode):
    """Criterio §5.1(1) sobre raw[0].request. Devuelve la lista de fallos."""
    fails = []
    sysm = _system_message(request)
    rf = (request.get("response_format") or {}).get("json_schema") or {}
    embedded = _embedded_schema(sysm)
    if variant == "blind":
        if embedded is not None or SCHEMA_TAIL in sysm:
            fails.append("blind: el system prompt contiene el apéndice de esquema")
        if not rf.get("schema"):
            fails.append("blind: falta response_format.json_schema.schema")
        return fails
    # variantes con esquema visible: apéndice completo al final del system prompt
    if embedded is None:
        fails.append("el system prompt no termina en el apéndice de esquema")
        return fails
    if variant in ("inject", "rot1"):
        if embedded != (rf.get("schema") or {}):
            fails.append("el esquema incrustado != response_format.json_schema.schema")
    else:  # nostruct: el incrustado debe ser el esquema que construye la librería
        from jevbench.adapters.llm import _openai_internals
        i = _openai_internals()
        prepared = i["convert_question_collection_to_validated_api_question_models"](qs)
        local = i["create_raw_output_schema"](
            i["create_llm_output_model"](prepared, mode))
        if embedded != local:
            fails.append("nostruct: esquema incrustado != esquema de la librería")
    fails += check_question_visibility(embedded, qs, mode)
    if variant == "rot1":
        _, defs = _answers_properties(embedded)
        props, _ = _answers_properties(embedded)
        for qid, q in qs.items():
            if q.get("type") != "choice":
                continue
            field = props.get(qid) or {}
            target = defs.get(field["$ref"].split("/")[-1]) if "$ref" in field else field
            order = list((target or {}).get("properties") or [])
            if order != list(q["criteria"].keys()):
                fails.append(f"{qid}: orden de propiedades != rotate_choice")
    return fails


# ------------------------------------------------------------------- stats

def _betacf(a, b, x):
    """Continued fraction de la beta incompleta (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-14:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) \
        else 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _beta_quantile(a, b, p, lo=0.0, hi=1.0):
    for _ in range(80):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    """IC exacto de Clopper-Pearson para k éxitos en n pruebas."""
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else _beta_quantile(k, n - k + 1, alpha / 2)
    hi = 1.0 if k == n else _beta_quantile(k + 1, n - k, 1 - alpha / 2)
    return (lo, hi)


def wilson(k, n, z=1.959964):
    """IC de Wilson para una proporción."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (center - half, center + half)


def newcombe_paired(a, b, c, d):
    """IC de Newcombe (método 10) para la diferencia pareada p1 - p2 sobre la
    tabla 2x2 [[a, b], [c, d]] (b = solo p1+, c = solo p2+)."""
    n = a + b + c + d
    if n == 0:
        return (0.0, float("nan"), float("nan"))
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    denom = math.sqrt((a + b) * (c + d) * (a + c) * (b + d)) if min(a + b, c + d, a + c, b + d) > 0 else 0
    psi = 0.0 if denom == 0 else max(0.0, (a * d - b * c - n / 2) / denom)
    delta = p1 - p2
    lo = delta - math.sqrt(max(0.0, (p1 - l1) ** 2 + (u2 - p2) ** 2
                                   - 2 * psi * (p1 - l1) * (u2 - p2)))
    hi = delta + math.sqrt(max(0.0, (u1 - p1) ** 2 + (p2 - l2) ** 2
                                   - 2 * psi * (u1 - p1) * (p2 - l2)))
    return (delta, lo, hi)


def poisson_binomial_sf(probs, k_obs):
    """P(X >= k_obs) para X = suma de Bernoullis heterogéneas (convolución)."""
    dist = [1.0]
    for p in probs:
        dist = [dist[i - 1] * p + (dist[i] * (1 - p) if i < len(dist) else 0.0)
                if i > 0 else dist[0] * (1 - p)
                for i in range(len(dist) + 1)]
    return sum(dist[k_obs:])


def holm(pvals):
    """Corrección de Holm: devuelve p ajustadas en el orden de entrada."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, prev = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        prev = max(prev, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = prev
    return adj


# ------------------------------------------------------------------- puerta

def _gate_run_name(host, modo, variant):
    return f"gate67_{host}_{modo}_{variant}"


def _save_gate_eval(run, phase, case, rec, model, cell_opts, diag_extra,
                    qhash=None):
    doc = store.load(run, phase) or {"meta": {}, "cases": {}}
    doc["meta"].update({
        "adapter": "llm", "opts": redact_options(cell_opts), **model.meta(),
        "phase": phase,
        "questions_hash": qhash or doc["meta"].get("questions_hash"),
        "host": platform.node(), "arch": platform.machine(),
        "python": sys.version.split()[0], "git": git_rev(),
        "git_dirty": git_dirty(),
        "diag": {**(doc["meta"].get("diag") or {}), **diag_extra},
        "updated": dt.datetime.now().isoformat(timespec="seconds")})
    doc["cases"][case.id] = rec
    store.save(run, phase, doc)


def _eval_case(model, case, qs, run, phase, cell_opts, diag_extra,
               qhash=None):
    """Una evaluación con captura de raw; devuelve el record guardado."""
    t1 = time.time()
    try:
        out = model.decide(case.state, qs)
        rec = {"answers": out["answers"], "ms": round((time.time() - t1) * 1000),
               "cost": out.get("cost"), "model": out.get("model")}
        if "usage" in out:
            rec["usage"] = {k: v for k, v in out["usage"].items()
                            if isinstance(v, (int, float, str, bool, type(None)))}
        if "raw" in out:
            rec["raw"] = out["raw"]
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {e}"[:300],
               "ms": round((time.time() - t1) * 1000)}
        diag_e = getattr(e, "diag", None)
        if isinstance(diag_e, dict) and diag_e:
            rec["diag"] = diag_e
    _save_gate_eval(run, phase, case, rec, model, cell_opts, diag_extra,
                    qhash)
    return rec


def gate(host, modo, celda, printer=print):
    """Puerta §5.1. Devuelve (ok, detalles) y escribe results/gate67_*.
    celda: inject | nostruct | rot1 (el bloque que se va a correr)."""
    if host not in HOSTS:
        raise SystemExit(f"host {host!r} desconocido: {sorted(HOSTS)}")
    if modo not in ("prob", "disc"):
        raise SystemExit("modo debe ser prob|disc")
    if celda not in ("inject", "nostruct", "rot1"):
        raise SystemExit("celda debe ser inject|nostruct|rot1")
    mode = {"prob": "probabilities", "disc": "discrete"}[modo]
    if celda == "nostruct" and modo == "disc":
        raise SystemExit("nostruct solo tiene sentido en prob")
    if celda == "rot1" and modo == "disc":
        raise SystemExit("rot1 solo está pre-registrado en prob")

    cases = _gate_cases()
    plan = [("blind", cases[:1])]
    if celda == "inject":
        plan.insert(0, ("inject", cases))
    elif celda == "nostruct":
        plan.insert(0, ("nostruct", cases))
    else:
        plan = [("rot1", cases), ("inject", cases), ("blind", cases[:1])]

    ref = load_token_ref()
    fails, notes = [], []
    tokens = {}          # (variant, phase) -> prompt_tokens primer intento
    offsets = {}         # familia -> offset (disc inject)
    for variant, todo in plan:
        v_cell = {"host": host, "mode": mode, "seed": 101,
                  "structured": variant != "nostruct",
                  "inject": variant in ("inject", "rot1"),
                  "rot": 1 if variant == "rot1" else 0}
        opts = _cell_opts(v_cell)
        model = adapters.get("llm")(**opts)
        run = _gate_run_name(host, modo, variant)
        printer(f"[{run}] {model.meta()}")
        for phase, case in todo:
            qs, _ = load_phase(phase)
            qs_eff = rotate_choice(qs, 1) if variant == "rot1" else qs
            rec = _eval_case(model, case, qs, run, phase, opts,
                             {"issue": "JEV-67", "gate": True, "host": host,
                              "variant": variant, "mode": mode},
                             qhash=questions_hash(qs_eff))
            if "error" in rec:
                printer(f"  {phase}/{case.id}: ERROR {rec['error'][:100]}")
            att = _first_attempt(rec)
            req = (att or {}).get("request") or {}
            # 1a: sha del system prompt == congelado
            sysm = _system_message(req)
            sha = hashlib.sha256(sysm.encode()).hexdigest()[:12] if sysm else None
            expected = PROMPT_SHA[(mode, variant)][family(phase)]
            if sha != expected:
                fails.append(f"{variant} {phase}/{case.id}: sha system "
                             f"{sha} != congelado {expected}")
            # 1b/1c/1d: comprobaciones de cliente sobre el esquema
            for f in check_client(req, qs_eff, variant, mode):
                fails.append(f"{variant} {phase}/{case.id}: {f}")
            if variant == "rot1":
                perm = rotation_manifest(qs_eff)["perm_sha256"]
                notes.append(f"rot1 {phase}: perm_sha256={perm}")
            # 4: usage presente + 2/3: regla de tokens
            t = _first_prompt_tokens(rec)
            tokens[(variant, phase)] = t
            if t is None:
                fails.append(f"{variant} {phase}/{case.id}: sin usage en el "
                             "primer intento (servidor no monitorizable)")
            else:
                r = (ref.get(phase) or {}).get(case.id)
                if r is None:
                    fails.append(f"{variant} {phase}/{case.id}: sin ref de tokens")
                elif variant in ("inject", "nostruct") and mode == "probabilities":
                    if abs(t - r) > 2:
                        fails.append(f"{variant} {phase}/{case.id}: tokens {t} "
                                     f"fuera de ref {r}±2")
                elif variant == "rot1":
                    if abs(t - r) > 10:
                        fails.append(f"{variant} {phase}/{case.id}: tokens {t} "
                                     f"fuera de ref {r}±10")
                elif variant == "inject" and mode == "discrete":
                    offsets[family(phase)] = t - r
                printer(f"  {variant} {phase}/{case.id}: prompt_tokens={t} "
                        f"(ref {r})")
    # reglas cruzadas
    a01 = GATE_PHASES[0]
    if modo == "prob":
        tb, r = tokens.get(("blind", a01)), (ref.get(a01) or {}).get(
            _gate_cases()[0][1].id)
        if tb is not None and r is not None and tb > r - 200:
            fails.append(f"control negativo no sale ciego: blind A01 {tb} > "
                         f"{r}-200 (el servidor inyecta por su cuenta)")
    else:
        ti, tb = tokens.get(("inject", a01)), tokens.get(("blind", a01))
        if ti is not None and tb is not None and ti - tb < 200:
            fails.append(f"disc: tokens(inject)-tokens(blind) en A01 = "
                         f"{ti - tb} < 200")
        for fam, off in offsets.items():
            if off >= 0:
                fails.append(f"disc: offset {fam} = {off} no es negativo")
        notes.append(f"offsets disc por familia: {offsets}")
        # persistir offsets para `run` (los consume el supervisor)
        run = _gate_run_name(host, modo, "inject")
        for ph in GATE_PHASES:
            doc = store.load(run, ph)
            if doc:
                doc["meta"].setdefault("diag", {})["offsets_familia"] = offsets
                store.save(run, ph, doc)
    for n in notes:
        printer(f"  {n}")
    ok = not fails
    for f in fails:
        printer(f"FALLO: {f}")
    printer(f"puerta {host}/{modo}/{celda}: {'PASS' if ok else 'FAIL'}")
    # identidad única + historial: la batería referencia esta puerta (§5.1)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    gate_id = f"{_gate_run_name(host, modo, celda)}@{ts}"
    entry = {"gate_id": gate_id, "ts": ts, "ok": ok, "fails": list(fails)}
    for ph in GATE_PHASES:
        run = _gate_run_name(host, modo, celda)
        doc = store.load(run, ph)
        if doc:
            d = doc["meta"].setdefault("diag", {})
            d.setdefault("gate_history", []).append(entry)
            d["latest_gate"] = entry
            store.save(run, ph, doc)
    printer(f"gate_id: {gate_id}")
    return ok, {"fails": fails, "tokens": {f"{v}/{p}": t for (v, p), t in
                                           tokens.items()}, "offsets": offsets,
                "gate_id": gate_id}


def _latest_gate(host, modo, celda):
    """(run, latest_gate|None) de la puerta celda para ese host/modo."""
    run = _gate_run_name(host, modo, celda)
    for ph in GATE_PHASES:
        doc = store.load(run, ph) or {}
        g = ((doc.get("meta") or {}).get("diag") or {}).get("latest_gate")
        if g:
            return run, g
    return run, None


# ----------------------------------------------------------- supervisor run

def _token_rule_ok(cell, phase, rec, ref, offsets):
    """Regla §8.1 sobre el primer intento del caso.

    Devuelve (estado, detalle): 'ok' | 'violacion' | 'sin_usage' | 'sin_raw'.
    Para casos con error y sin primer intento no hay nada que comprobar."""
    att = _first_attempt(rec)
    if att is None:
        return ("sin_raw", None) if "error" not in rec else ("ok", "error sin intento")
    t = _first_prompt_tokens(rec)
    if t is None:
        return "sin_usage", None
    r = (ref.get(phase) or {}).get(_rec_case_id(rec))
    if r is None:
        # sin referencia del caso: la visibilidad no es verificable
        return "violacion", "sin ref"
    mode = cell["mode"]
    if mode == "probabilities" and not cell["rot"]:
        if abs(t - r) <= 2:
            return "ok", t
        return "violacion", (t, r, 2)
    if cell["rot"]:
        if abs(t - r) <= 10:
            return "ok", t
        return "violacion", (t, r, 10)
    off = offsets.get(family(phase))
    if off is None:
        # referencia ausente: la visibilidad no es verificable en discrete
        return "violacion", "sin offset de puerta"
    if abs((t - r) - off) <= 2:
        return "ok", t
    return "violacion", (t, r, off)


def _rec_case_id(rec):
    return rec.get("_cid")


# claves operativas del diag: estado de la ejecución, no configuración
# congelada — no se comparan al reanudar (JEV-67, revisión codex F4)
OP_DIAG_KEYS = ("status", "stopped_cases", "no_usage_cases")


def _frozen_doc(doc):
    """doc con el diag reducido a su configuración congelada, para
    _check_resume (que exige igualdad estricta en ambas direcciones)."""
    diag = {k: v for k, v in ((doc.get("meta") or {}).get("diag") or {}).items()
            if k not in OP_DIAG_KEYS}
    return {"meta": {**(doc.get("meta") or {}), "diag": diag},
            "cases": doc.get("cases") or {}}


def _cell_diag(cell_name, cell, gate_id):
    diag = {"issue": "JEV-67", "cell": cell_name, "mode": cell["mode"],
            "structured": cell["structured"],
            "inject_schema_in_prompt": cell["inject"],
            "rotate_choice": cell["rot"], "seed": cell["seed"],
            "ref_run": REF_RUN, "gate_id": gate_id}
    return diag


def run_cell(cell_name, retry_errors=False, printer=print):
    """Supervisor §5.2/5.3 para una celda de batería."""
    if cell_name not in CELLS:
        raise SystemExit(f"celda {cell_name!r} desconocida: {sorted(CELLS)}")
    cell = CELLS[cell_name]
    run = cell["run"]
    opts = _cell_opts(cell)
    ref = load_token_ref()
    # puerta aprobada obligatoria (§5.1): sin ella no hay batería
    modo = MODE_SLUG[cell["mode"]]
    gate_celda = "rot1" if cell["rot"] else (
        "inject" if cell["inject"] else "nostruct")
    gate_run, latest = _latest_gate(cell["host"], modo, gate_celda)
    if not (latest and latest.get("ok")):
        raise SystemExit(
            f"sin puerta aprobada para {gate_run}: ejecuta primero "
            f"`jev67 gate {cell['host']} {modo} {gate_celda}`")
    offsets = {}
    if cell["mode"] == "discrete":
        for ph in GATE_PHASES:
            doc = store.load(gate_run, ph) or {}
            gate_diag = (doc.get("meta") or {}).get("diag") or {}
            offsets.update(gate_diag.get("offsets_familia") or {})
        if len(offsets) < 3:
            raise SystemExit(f"faltan offsets de la puerta disc en {gate_run}: "
                             "ejecuta primero `jev67 gate {host} disc inject`")
    model = adapters.get("llm")(**opts)
    printer(f"[{run}] {model.meta()}")
    diag = _cell_diag(cell_name, cell, latest["gate_id"])
    if offsets:
        diag["offsets_familia"] = offsets
    # pre-validación: TODAS las fases antes de escribir nada (codex F4)
    prepared = {}
    for phase in cell["phases"]:
        qs, _ = load_phase(phase)
        qs_sent = rotate_choice(qs, cell["rot"]) if cell["rot"] else qs
        exp_sha = model.expected_system_prompt_sha256(qs)
        cfg = {"opts": redact_options(opts), "meta": model.meta(),
               "expected": {"questions_hash": questions_hash(qs_sent),
                            "system_prompt_sha256": exp_sha}}
        doc = store.load(run, phase) or {"meta": {}, "cases": {}}
        diag_ph = dict(diag)
        if cell["rot"]:
            diag_ph["rotation"] = rotation_manifest(qs_sent)
        _check_resume(run, phase, _frozen_doc(doc), diag_ph, cfg,
                      config_keys=CONFIG_KEYS)
        prepared[phase] = (qs, qs_sent, exp_sha)
    t_run = time.time()
    # reconstruye acumulados al reanudar
    total_errors = sum(
        1 for phase in cell["phases"]
        for rec in ((store.load(run, phase) or {}).get("cases") or {}).values()
        if "error" in (rec or {}))
    no_usage_cases = list(next(
        (d for phase in cell["phases"]
         for d in [((store.load(run, phase) or {}).get("meta") or {})
                   .get("diag", {}).get("no_usage_cases")] if d), []))
    aborted = None
    stop_run = None
    for phase in cell["phases"]:
        if aborted or stop_run:
            break
        qs, cases = load_phase(phase)
        qs_sent, exp_sha = prepared[phase][1], prepared[phase][2]
        doc = store.load(run, phase) or {"meta": {}, "cases": {}}
        if cell["rot"]:
            diag["rotation"] = rotation_manifest(qs_sent)
        elif "rotation" in diag:
            del diag["rotation"]
        meta_now = _meta_with_expected(model.meta(), exp_sha)
        doc["meta"].update({
            "adapter": "llm", "opts": redact_options(opts),
            "phase": phase, "questions_hash": questions_hash(qs_sent),
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0], "git": git_rev(),
            "git_dirty": git_dirty(), "diag": diag,
            "updated": dt.datetime.now().isoformat(timespec="seconds")})
        _merge_meta(doc["meta"], meta_now)
        if retry_errors:
            todo = [c for c in cases if c.id not in doc["cases"]
                    or "error" in doc["cases"][c.id]]
        else:
            todo = [c for c in cases if c.id not in doc["cases"]]
        phase_errors = sum(1 for c in cases
                       if "error" in (doc["cases"].get(c.id) or {}))
        stopped = []
        for c in todo:
            if aborted or stop_run:
                stopped.append(c.id)
                continue
            if phase_errors >= 3:
                stopped.append(c.id)
                continue
            t1 = time.time()
            try:
                out = model.decide(c.state, qs)
                rec = {"answers": out["answers"], "ms": round((time.time() - t1) * 1000),
                       "cost": out.get("cost"), "model": out.get("model")}
                if "usage" in out:
                    rec["usage"] = {k: v for k, v in out["usage"].items()
                                    if isinstance(v, (int, float, str, bool, type(None)))}
                if "raw" in out:
                    rec["raw"] = out["raw"]
            except Exception as e:
                traceback.print_exc()
                rec = {"error": f"{type(e).__name__}: {e}"[:300],
                       "ms": round((time.time() - t1) * 1000)}
                diag_e = getattr(e, "diag", None)
                if isinstance(diag_e, dict) and diag_e:
                    rec["diag"] = diag_e
                phase_errors += 1
                total_errors += 1
                printer(f"{run} {phase} {c.id}: ERROR {rec['error'][:100]}",
                        flush=True)
            # regla de tokens del primer intento (§8.1) tras cada caso
            rec["_cid"] = c.id
            state, detail = _token_rule_ok(cell, phase, rec, ref, offsets)
            if state == "violacion":
                aborted = (f"{phase}/{c.id}: visibilidad perdida "
                           f"(tokens {detail})")
                printer(f"ABORTANDO {run}: {aborted}", flush=True)
            elif state == "sin_usage":
                no_usage_cases.append(f"{phase}/{c.id}")
                # sin usage: aplica solo la comprobación de cliente
                att = _first_attempt(rec)
                for f in check_client((att or {}).get("request") or {},
                                      qs_sent, "rot1" if cell["rot"] else
                                      ("inject" if cell["inject"] else
                                       "nostruct" if not cell["structured"]
                                       else "blind"), cell["mode"]):
                    aborted = f"{phase}/{c.id}: cliente {f}"
                if not aborted:
                    printer(f"{run} {phase} {c.id}: sin usage (solo check "
                            "cliente)", flush=True)
            rec.pop("_cid", None)
            doc["cases"][c.id] = rec
            _merge_meta(doc["meta"], _meta_with_expected(model.meta(), exp_sha))
            store.save(run, phase, doc)
            if total_errors >= 10:
                stop_run = "10 errores totales"
            elif time.time() - t_run > cell["budget_s"]:
                stop_run = "presupuesto de tiempo agotado"
        if stopped:
            doc["meta"].setdefault("diag", {})["stopped_cases"] = stopped
            store.save(run, phase, doc)
            printer(f"{run} {phase}: {len(stopped)} casos no ejecutados por "
                    "regla de parada", flush=True)
    doc_status = ("invalid_visibility" if aborted else
                  "stopped" if stop_run else "complete")
    for phase in store.runs_in(run):
        d = store.load(run, phase) or {"meta": {}}
        d["meta"].setdefault("diag", {})["status"] = doc_status
        if no_usage_cases:
            d["meta"]["diag"]["no_usage_cases"] = no_usage_cases
        store.save(run, phase, d)
    if aborted:
        printer(f"RUN INVALIDO por visibilidad: {aborted}")
    if stop_run:
        printer(f"RUN DETENIDO: {stop_run}")
    if no_usage_cases:
        printer(f"casos sin usage: {len(no_usage_cases)} "
                f"(>2% => no evaluable: {len(no_usage_cases) >= 4})")
    printer(f"{run} fin: estado={doc_status} errores={total_errors} "
            f"sin_usage={len(no_usage_cases)}")
    return doc_status


# ------------------------------------------------------------------- informe

def _decisions_run(run):
    """{phase/case_id: {qid: decisión}} de todos los casos sin error."""
    out = {}
    for ph in store.runs_in(run):
        doc = store.load(run, ph) or {}
        qs, _ = load_phase(ph)
        for cid, rec in (doc.get("cases") or {}).items():
            if "error" in rec:
                continue
            out[f"{ph}/{cid}"] = _decisions(rec, qs)
    return out


def paired_decisions(run_a, run_b):
    """Itera (pc, qid, dec_a, dec_b) sobre decisiones presentes en ambos runs."""
    da, db = _decisions_run(run_a), _decisions_run(run_b)
    for pc in sorted(set(da) & set(db)):
        for qid, va in da[pc].items():
            vb = db[pc].get(qid)
            if va is not None and vb is not None:
                yield pc, qid, va, vb


def agreement(run_a, run_b):
    """(k, n, p, L, U): acuerdo de decisiones pareado con IC Clopper-Pearson."""
    pairs = [(pc, q, a == b) for pc, q, a, b in paired_decisions(run_a, run_b)]
    k = sum(1 for *_, e in pairs if e)
    n = len(pairs)
    lo, hi = clopper_pearson(k, n)
    return k, n, (k / n if n else float("nan")), lo, hi


def _run_ok_counts(run):
    """(n_ok, n_cases) por fase y totales."""
    per_ph, tot_ok, tot_n = {}, 0, 0
    for ph in store.runs_in(run):
        doc = store.load(run, ph) or {}
        _, cases = load_phase(ph)
        recs = doc.get("cases") or {}
        ok = sum(1 for c in cases
                 if isinstance(recs.get(c.id), dict)
                 and "error" not in recs[c.id])
        per_ph[ph] = (ok, len(cases))
        tot_ok += ok
        tot_n += len(cases)
    return per_ph, tot_ok, tot_n


def _offsets_for(run, diag):
    """(offsets, fuente) para la regla de tokens de discrete: la batería los
    guarda en su diag; en runs anteriores a ese cambio se recuperan de la
    puerta del host (fuente documentada)."""
    if diag.get("offsets_familia"):
        return dict(diag["offsets_familia"]), "bateria"
    cell = next((c for c in CELLS.values() if c["run"] == run), None)
    if not cell or cell["mode"] != "discrete":
        return {}, None
    gate_run = _gate_run_name(cell["host"], "disc", "inject")
    off = {}
    for ph in GATE_PHASES:
        doc = store.load(gate_run, ph) or {}
        off.update(((doc.get("meta") or {}).get("diag") or {})
                   .get("offsets_familia") or {})
    return off, ("puerta" if off else None)


def audit_run(run, phases=None):
    """Auditoría §5.4 de un run: regla de tokens en primeros intentos, casos
    sin usage, nulos/uniformes crudos, errores por tipo/fase, reintentos,
    constancia de opts, hashes por fase."""
    phases = phases or store.runs_in(run)
    ref = load_token_ref()
    rep = {"run": run, "phases": {}, "raw_cases": 0, "cases": 0,
           "no_usage": [], "token_violations": [], "errors": {},
           "malformed_retries": 0, "raw_zero": 0, "raw_uniform": 0,
           "opts_variants": set(), "shas": {}, "qhash": {}}
    discrete = None
    for ph in phases:
        doc = store.load(run, ph) or {}
        meta = doc.get("meta") or {}
        diag = meta.get("diag") or {}
        discrete = (meta.get("mode") == "discrete") if discrete is None else discrete
        rep["opts_variants"].add(json.dumps(meta.get("opts"), sort_keys=True))
        rep["qhash"][ph] = meta.get("questions_hash")
        rep["shas"][ph] = meta.get("system_prompt_sha256")
        run_offsets, offs_src = _offsets_for(run, diag)
        if run_offsets:
            rep["offsets"] = run_offsets
            rep["offsets_source"] = offs_src
        qs, cases = load_phase(ph)
        ph_e = {"n": len(cases), "ok": 0, "errors": [], "missing": [],
                "stopped": (diag.get("stopped_cases") or [])}
        for c in cases:
            raw_rec = (doc.get("cases") or {}).get(c.id)
            if raw_rec is None:
                # ausente (no ejecutado o borrado): no es un acierto
                ph_e["missing"].append(c.id)
                rep.setdefault("missing", []).append(f"{ph}/{c.id}")
                continue
            rec = dict(raw_rec)
            rec["_cid"] = c.id
            if "error" in rec:
                kind = ("timeout" if "timeout" in rec["error"].lower()
                        else "length" if "length" in rec["error"].lower()
                        else "malformed" if "malform" in rec["error"].lower()
                        or "validation" in rec["error"].lower()
                        else "transport/other")
                ph_e["errors"].append((c.id, kind, rec["error"][:80]))
                rep["errors"][kind] = rep["errors"].get(kind, 0) + 1
                continue
            rep["cases"] += 1
            ph_e["ok"] += 1
            u = rec.get("usage") or {}
            rep["malformed_retries"] += u.get("n_retries_malformed") or 0
            if _first_attempt(rec) is None:
                continue
            rep["raw_cases"] += 1
            st, det = _token_rule_ok({"mode": meta.get("mode") or "probabilities",
                                      "rot": diag.get("rotate_choice") or 0},
                                     ph, rec, ref, run_offsets)
            if st == "sin_usage":
                rep["no_usage"].append(f"{ph}/{c.id}")
            elif st == "violacion":
                rep["token_violations"].append(f"{ph}/{c.id} {det}")
            validate = _validate_raw_discrete if meta.get("mode") == "discrete" \
                else _validate_raw_value
            for finish, answers in _raw_answers(rec):
                if answers is None:
                    continue
                for qid, val in answers.items():
                    kind, _ = validate(qs, qid, val)
                    if kind == "zero":
                        rep["raw_zero"] += 1
                    elif kind == "uniform":
                        rep["raw_uniform"] += 1
        rep["phases"][ph] = ph_e
    rep["opts_variants"] = len(rep["opts_variants"])
    return rep


def choice_changes(run_base, run_rot):
    """Para A3: cambios de etiqueta choice rot0->rot1 pareados.

    Devuelve (cambios, n_pareadas) y detalle por cambio con la info de
    «conserva posición» y k."""
    da, db = _decisions_run(run_base), _decisions_run(run_rot)
    changes, tot = [], 0
    for pc in sorted(set(da) & set(db)):
        ph = pc.split("/", 1)[0]
        qs, _ = load_phase(ph)
        rot_qs = rotate_choice(qs, 1)
        for qid, va in da[pc].items():
            vb = db[pc].get(qid)
            q = qs.get(qid) or {}
            if q.get("type") != "choice" or va is None or vb is None:
                continue
            tot += 1
            if va != vb:
                base_order = list(q["criteria"].keys())
                rot_order = list(rot_qs[qid]["criteria"].keys())
                # «conserva posición» según el pre-registro: la NUEVA etiqueta
                # en el orden rotado ocupa la posición que la antigua tenía
                # en el orden original (no comparar la posición de va)
                conserva = (vb in rot_order and va in base_order
                            and rot_order.index(vb) == base_order.index(va))
                changes.append({"pc": pc, "qid": qid, "base": va, "rot": vb,
                                "k": len(base_order), "conserva": conserva})
    return changes, tot


def pfix_check():
    """P+fix determinista: la rotación produce el orden esperado y el scorer
    lee la primera clave del orden enviado cuando el vector es nulo→uniforme.
    La verificación extremo a extremo (adaptador+proveedor falso) está en
    tests/test_jev67.py."""
    qs = {"q": {"type": "choice",
                "criteria": {"a": "A", "b": "B", "c": "C", "d": "D"}}}
    for shift in (0, 1):
        qq = rotate_choice(qs, shift)
        first = next(iter(qq["q"]["criteria"]))
        rec = {"answers": {"q": {"choice": first,
                                 "probabilities": {k: 0.25
                                                   for k in qq["q"]["criteria"]}}}}
        if _decisions(rec, qq).get("q") != first:
            return False
    return True


def _null_qids(rec, qs):
    """Preguntas choice con vector crudo nulo (todas las opciones 0.0) en el
    raw del record."""
    nulls = set()
    for _, answers in _raw_answers(rec):
        if not answers:
            continue
        for qid, q in qs.items():
            if q.get("type") != "choice":
                continue
            v = answers.get(qid)
            if (isinstance(v, dict) and v and all(
                    isinstance(x, (int, float)) and not isinstance(x, bool)
                    and x == 0 for x in v.values())):
                nulls.add(qid)
    return nulls


def _plive_evidence():
    """P+live: en los runs a ciegas rot0/rot1, cada vector nulo común debe
    dejar la decisión en la primera clave del orden enviado (rot1 espera la
    primera clave rotada)."""
    base = "diag_qwen38_jev67_fp8_rot0_typesafe_struct_r1"
    rot = "diag_qwen38_jev67_fp8_rot1_typesafe_struct_r1"
    common = hits = 0
    for ph in store.runs_in(base):
        da = store.load(base, ph) or {}
        db = store.load(rot, ph) or {}
        qs, _ = load_phase(ph)
        rqs = rotate_choice(qs, 1)
        for cid, ra in (da.get("cases") or {}).items():
            rb = (db.get("cases") or {}).get(cid)
            if not rb:
                continue
            for qid in _null_qids(ra, qs) & _null_qids(rb, qs):
                common += 1
                # rot0: primera clave del orden base; rot1: del rotado
                for rec, order in ((ra, qs[qid]["criteria"]),
                                   (rb, rqs[qid]["criteria"])):
                    first = next(iter(order))
                    a = (rec.get("answers") or {}).get(qid) or {}
                    choice = a.get("choice")
                    if choice is None and a.get("probabilities"):
                        choice = max(a["probabilities"],
                                     key=a["probabilities"].get)
                    if choice == first:
                        hits += 1
    return {"common_nulls": common, "first_key_hits": hits,
            "expected": common * 2}


def normalize_audit(runs):
    """§8.5 (RQ7): reproduce las tres rutas con y sin normalización sobre el
    último intento válido del raw; decisiones que cambian, distribución de
    |suma-1|, Brier/NLL/ECE crudos y sensibilidad «nulo=error»."""
    from jevbench.diag65_report import _raw_answers
    try:
        from system_one_adapter._utils.probability_normalization import (
            rescale_probabilities)
    except ImportError:
        def rescale_probabilities(probs):
            tot = sum(probs.values())
            if tot <= 0:
                u = 1.0 / len(probs)
                return {k: u for k in probs}
            return {k: v / tot for k, v in probs.items()}
    out = {}
    for run in runs:
        rep = {"zeros": 0, "changed_decisions": 0, "sum_dev": {},
               "score_mismatch": 0, "noul_mismatch": 0,
               "brier": [], "nll": [], "conf_hits": [], "null_as_error_pts": 0,
               "n_questions": 0}
        devs = {"choice": [], "score": [], "noul": []}
        for ph in store.runs_in(run):
            doc = store.load(run, ph) or {}
            meta = doc.get("meta") or {}
            rot = (meta.get("diag") or {}).get("rotate_choice") or 0
            qs, cases = load_phase(ph)
            if rot:
                qs_sent = rotate_choice(qs, rot)
            else:
                qs_sent = qs
            case_by_id = {c.id: c for c in cases}
            for cid, rec in (doc.get("cases") or {}).items():
                if "error" in rec or cid not in case_by_id:
                    continue
                attempts = _raw_answers(rec)
                valid = next((a for _, a in reversed(attempts)
                              if a is not None), None)
                if valid is None:
                    continue
                gt = case_by_id[cid].gt
                for qid, raw_val in valid.items():
                    q = qs_sent.get(qid)
                    if q is None:
                        continue
                    qtype = q["type"]
                    rep["n_questions"] += 1
                    if qtype == "noul":
                        v = raw_val if isinstance(raw_val, (int, float)) else None
                        if v is None:
                            continue
                        devs["noul"].append(0.0)
                        # noul no se normaliza: decisión idéntica en ambas rutas
                        g = gt.get(qid)
                        if g is not None:
                            rep["brier"].append((v - g) ** 2)
                            rep["nll"].append(-math.log(max(
                                1e-6, v if g == 1 else 1 - v)))
                            rep["conf_hits"].append(
                                (max(v, 1 - v), (v >= 0.5) == (g == 1)))
                        continue
                    if not isinstance(raw_val, dict):
                        continue
                    nums = {k: x for k, x in raw_val.items()
                            if isinstance(x, (int, float))}
                    s = sum(nums.values())
                    devs[qtype].append(abs(s - 1))
                    if all(x == 0 for x in nums.values()):
                        rep["zeros"] += 1
                        rep["null_as_error_pts"] += 1
                    order = (list(q["criteria"]) if qtype == "choice"
                             else [str(i) for i in range(len(q["criteria"]))])
                    if qtype == "choice":
                        if abs(s - 1) > 1e-6:
                            normed = rescale_probabilities(nums)
                        else:
                            normed = nums
                        dec_norm = max(order, key=lambda k: normed.get(k, 0)) \
                            if normed else None
                        dec_raw = max(order, key=lambda k: nums.get(k, 0)) \
                            if nums else None
                        if dec_norm != dec_raw:
                            rep["changed_decisions"] += 1
                        g = gt.get(qid)
                        if g in order:
                            rep["brier"].append(sum(
                                (nums.get(o, 0) - (o == g)) ** 2 for o in order))
                            rep["nll"].append(-math.log(
                                max(1e-6, nums.get(g, 0))))
                            top = max(order, key=lambda k: nums.get(k, 0))
                            rep["conf_hits"].append((nums.get(top, 0), top == g))
                    else:  # score: la librería reescala siempre
                        rescaled = rescale_probabilities(nums)
                        ev = sum(int(k) * rescaled.get(k, 0)
                                 for k in rescaled)
                        stored = ((rec.get("answers") or {}).get(qid) or {})
                        if stored.get("score") is not None and \
                                abs(stored["score"] - ev) > 1e-9:
                            rep["score_mismatch"] += 1
                        g = gt.get(qid)
                        if g is not None:
                            probs = {str(k): rescaled.get(str(k), 0)
                                     for k in range(len(q["criteria"]))}
                            rep["brier"].append(sum(
                                (probs[str(i)] - (str(i) == str(g))) ** 2
                                for i in range(len(q["criteria"]))))
                            rep["nll"].append(-math.log(
                                max(1e-6, probs.get(str(g), 0))))
                            top = max(probs, key=probs.get)
                            rep["conf_hits"].append((probs[top], top == str(g)))
        for t, ds in devs.items():
            if ds:
                ds = sorted(ds)
                rep["sum_dev"][t] = {"med": ds[len(ds) // 2],
                                     "p95": ds[int(len(ds) * 0.95) - 1
                                               if len(ds) else 0],
                                     "max": ds[-1],
                                     "n>0.05": sum(1 for x in ds if x > 0.05)}
        n = max(1, len(rep["brier"]))
        rep["brier_mean"] = sum(rep["brier"]) / n
        rep["nll_mean"] = sum(rep["nll"]) / n
        rep["ece"] = metrics.ece(rep["conf_hits"])
        rep.pop("brier"), rep.pop("nll"), rep.pop("conf_hits")
        out[run] = rep
    return out


# ---------------------------------------------------------- clasificación §8.2

def _cls(cond_ok, cond_bad):
    return "CONFIRMADA" if cond_ok else ("REFUTADA" if cond_bad else "INCONCLUSA")


def _eval_note(r):
    """Motivo de NO EVALUABLE por visibilidad (§5.2/5.4): violaciones de la
    regla de tokens o >2 % de casos sin usage. None si el run es evaluable."""
    if r.get("token_violations"):
        return f"{len(r['token_violations'])} violaciones de tokens"
    n = r.get("n_total") or 0
    if n and len(r.get("no_usage") or []) / n > 0.02:
        return f"{len(r['no_usage'])}/{n} casos sin usage"
    return None


def _mask(c, prefix, r):
    """Sustituye los componentes prefix.* por NO EVALUABLE si el run no es
    verificable por visibilidad."""
    note = _eval_note(r)
    if note:
        for k in list(c):
            if k.startswith(prefix):
                c[k] = f"NO EVALUABLE ({note})"


def classify(results):
    """Tabla §8.2 componente a componente. `results` es el dict que produce
    build_results(): ajustados, acuerdos, conteos y denominadores."""
    c = {}
    a1 = results["a1"]
    adj, n_ok, n_tot = a1["adjusted"], a1["n_ok"], a1["n_total"]
    c["A1.a ajustado"] = ("NO EVALUABLE (n_ok<190)" if n_ok < 190 else
                        _cls(47 <= adj <= 60, adj < 44 or adj > 63) + f" ({adj:.0f}, n_ok={n_ok})")
    c["A1.b nulos crudos"] = ("NO EVALUABLE (raw<98%)" if a1["raw_cov"] < 0.98 else
                              _cls(a1["raw_zero"] == 0, a1["raw_zero"] >= 1)
                              + f" ({a1['raw_zero']})")
    c["A1.c errores"] = _cls(a1["errors"] <= 2, a1["errors"] >= 5) + f" ({a1['errors']})"
    if "a2" in results:
        a2 = results["a2"]
        k, n, p, lo, _ = a2["agreement"]
        c["A2.a acuerdo A1↔A2"] = ("NO EVALUABLE (<900 dec.)" if n < 900 else
                                   _cls(p >= 0.97 and lo >= 0.95, p < 0.95)
                                   + f" ({k}/{n} p={p:.3f} L={lo:.3f})")
        d = a2["adj"] - adj
        c["A2.b Δ ajustado A2−A1"] = (
            "NO EVALUABLE" if min(a2["n_ok"], n_ok) < 190 else
            _cls(abs(d) <= 3, abs(d) > 6) + f" ({d:+.0f})")
        c["A2.c reintentos malformados"] = _cls(
            a2["malformed"] >= a1["malformed"], a2["malformed"] < a1["malformed"]
        ) + f" (A2={a2['malformed']}, A1={a1['malformed']})"
        c["A2.d vs 49 histórico"] = f"descriptivo (A2={a2['adj']:.0f})"
    if "a4" in results:
        k, n, p, lo, _ = results["a4"]["agreement"]
        c["A4 acuerdo A1↔A4 (ruido)"] = (
            "NO EVALUABLE (<240 dec.)" if n < 240 else
            _cls(p >= 0.98, p < 0.95) + f" ({k}/{n} p={p:.3f})")
    if "a3" in results:
        a3 = results["a3"]
        n = a3["paired_choice"]
        if n < 240:
            c["A3.a cambios de etiqueta"] = f"NO EVALUABLE (<240: {n})"
        else:
            k = a3["changes"]
            lo, hi = clopper_pearson(k, n)
            c["A3.a cambios de etiqueta"] = _cls(
                hi <= 0.10, lo > 0.10) + f" ({k}/{n} U={hi:.3f})"
        if a3["n_changes"] < 10:
            c["A3.b dirección posición"] = (
                f"NO EVALUABLE (<10 cambios: {a3['n_changes']}; manda A3.a)")
        else:
            pv = a3["poisson_p"]
            c["A3.b dirección posición"] = (
                "CONFIRMADA (exceso no significativo)" if pv >= 0.05 else
                f"REFUTADA (sesgo de posición, p={pv:.4f})") + f" [p={pv:.4f}]"
        d, lo, hi = a3["newcombe"]
        c["A3.c Δ acierto choice A3−A1"] = (
            ("CONFIRMADA" if -0.05 <= lo and hi <= 0.05 else
             "REFUTADA (IC excluye 0)" if lo > 0 or hi < 0 else
             "INCONCLUSA") + f" ({d:+.3f} [{lo:+.3f},{hi:+.3f}] pp*100)")
    pfix = results.get("pfix")
    c["P+fix"] = ("NO EVALUABLE (sin evidencia)" if pfix is None else
                  "CONFIRMADA" if pfix else "REFUTADA")
    if "plive" in results:
        pl = results["plive"]
        if pl["common_nulls"] < 5:
            c["P+live"] = f"NO EVALUABLE (<5 nulos comunes: {pl['common_nulls']})"
        else:
            ok = pl["first_key_hits"] == pl.get("expected", pl["common_nulls"])
            c["P+live"] = ("CONFIRMADA" if ok else "REFUTADA") + \
                (f" ({pl['first_key_hits']}/{pl.get('expected', pl['common_nulls'])}"
                 " eligen 1ª clave)")
    for name, comp in (("B1", "b1"), ("C1", "c1")):
        if comp in results:
            r = results[comp]
            d = r["adj"] - adj
            margen = 5 if comp == "b1" else 6
            c[f"{name}.a ajustado vs A1"] = (
                "NO EVALUABLE" if min(r["n_ok"], n_ok) < 190 else
                _cls(abs(d) <= margen, abs(d) > 10) + f" ({d:+.0f})")
            c[f"{name}.b nulos crudos"] = (
                "NO EVALUABLE (raw<98%)" if r["raw_cov"] < 0.98 else
                _cls(r["raw_zero"] == 0, r["raw_zero"] >= 1)
                + f" ({r['raw_zero']})")
    for name, comp, prob_comp in (("B2", "b2", "b1"), ("C2", "c2", "c1")):
        if comp in results:
            r = results[comp]
            pe = r["papers_errors"]
            c[f"{name}.a fallos papers32"] = _cls(
                pe == 0, pe >= 2) + f" ({pe})"
            if prob_comp in results:
                d = r["adj"] - results[prob_comp]["adj"]
                c[f"{name}.b ajustado disc vs prob"] = (
                    "NO EVALUABLE" if min(r["n_ok"], results[prob_comp]["n_ok"]) < 190
                    else _cls(abs(d) <= 4, abs(d) > 8) + f" ({d:+.0f})")
            c[f"{name}.c errores totales"] = _cls(
                r["errors"] <= 1, r["errors"] >= 5) + f" ({r['errors']})"
    # máscaras de evaluabilidad por visibilidad (§5.2/5.4): un run que no
    # verifica no aporta componentes evaluados
    for comp in ("a1", "a2", "a3", "a4", "b1", "b2", "c1", "c2"):
        if comp in results:
            _mask(c, comp.upper() + ".", results[comp])
    return c


def build_results():
    """Reúne métricas de todos los runs JEV-67 presentes en results/."""
    res = {}
    key_of = {"a1": "a1", "a2": "a2", "a3": "a3", "a4": "a4",
              "b1": "b1", "b2": "b2", "c1": "c1", "c2": "c2"}
    runs = {}
    for k, cell in CELLS.items():
        if store.runs_in(cell["run"]):
            runs[k] = cell["run"]
    for k, run in runs.items():
        per_ph, n_ok, n_tot = _run_ok_counts(run)
        aud = audit_run(run)
        adj, _ = adjusted(run)
        entry = {"run": run, "adjusted": adj, "adj": adj or 0.0,
                 "n_ok": n_ok, "n_total": n_tot,
                 "raw_zero": aud["raw_zero"], "raw_uniform": aud["raw_uniform"],
                 "raw_cov": (aud["raw_cases"] / aud["cases"]
                             if aud["cases"] else 0),
                 "errors": sum(aud["errors"].values()),
                 "malformed": aud["malformed_retries"],
                 "no_usage": aud["no_usage"],
                 "token_violations": aud["token_violations"],
                 "per_phase": per_ph}
        pe = sum(1 for cid, kind, _ in (aud["phases"].get("papers32") or {})
                 .get("errors", []) if kind in ("timeout", "length"))
        entry["papers_errors"] = pe
        res[k] = entry
    if "a1" in res and "a2" in res:
        res["a2"]["agreement"] = agreement(res["a1"]["run"], res["a2"]["run"])
    if "a1" in res and "a4" in res:
        res["a4"]["agreement"] = agreement(res["a1"]["run"], res["a4"]["run"])
    if "a1" in res and "a3" in res:
        changes, tot = choice_changes(res["a1"]["run"], res["a3"]["run"])
        probs = [1.0 / (c["k"] - 1) for c in changes if c["k"] > 2]
        obs = sum(1 for c in changes if c["conserva"] and c["k"] > 2)
        p = poisson_binomial_sf(probs, obs) if changes else float("nan")
        res["a3"].update({
            "changes": len(changes), "n_changes": len(changes),
            "paired_choice": tot, "poisson_p": p,
            "conserved": obs})
        # Newcombe sobre aciertos choice pareados
        a = b = cc = d = 0
        for pc in sorted(set(_decisions_run(res["a1"]["run"])) &
                         set(_decisions_run(res["a3"]["run"]))):
            ph = pc.split("/", 1)[0]
            qs, cases = load_phase(ph)
            gt_by_id = {c.id: c.gt for c in cases}
            cid = pc.split("/", 1)[1]
            da = _decisions_run(res["a1"]["run"])[pc]
            db = _decisions_run(res["a3"]["run"])[pc]
            for qid in da:
                if (qs.get(qid) or {}).get("type") != "choice":
                    continue
                va, vb = da[qid], db.get(qid)
                g = gt_by_id.get(cid, {}).get(qid)
                if va is None or vb is None or g is None:
                    continue
                h1, h3 = (va == g), (vb == g)
                a += h1 and h3
                b += h3 and not h1
                cc += h1 and not h3
                d += not h1 and not h3
        # delta orientado A3−A1 (positivo = rot1 acierta más)
        res["a3"]["newcombe"] = newcombe_paired(a, b, cc, d)
        res["a3"]["choice_table"] = (a, b, cc, d)
    res["pfix"] = pfix_check()
    if store.runs_in("diag_qwen38_jev67_fp8_rot0_typesafe_struct_r1"):
        res["plive"] = _plive_evidence()
    return res


def report(out_json=None, printer=print):
    res = build_results()
    printer("# jev67 report")
    for k in ("a1", "a2", "a3", "a4", "b1", "b2", "c1", "c2"):
        if k not in res:
            continue
        r = res[k]
        printer(f"\n## {k}: {r['run']}")
        printer(f"ajustado {r['adjusted'] and round(r['adjusted'])}, "
                f"n_ok {r['n_ok']}/{r['n_total']}, errores {r['errors']}, "
                f"nulos crudos {r['raw_zero']}, uniformes {r['raw_uniform']}, "
                f"sin usage {len(r['no_usage'])}, "
                f"violaciones token {len(r['token_violations'])}, "
                f"cobertura raw {r['raw_cov']:.0%}")
        if "agreement" in r:
            k_, n, p, lo, hi = r["agreement"]
            printer(f"acuerdo pareado con A1: {k_}/{n} p={p:.3f} "
                    f"IC95 [{lo:.3f},{hi:.3f}]")
        if "changes" in r:
            printer(f"rotación: {r['changes']} cambios de etiqueta choice en "
                    f"{r['paired_choice']} pareadas; conserva posición "
                    f"{r['conserved']}; p Poisson-binomial {r['poisson_p']:.4f}; "
                    f"Newcombe {r['newcombe']}")
        if "papers_errors" in r:
            printer(f"fallos papers32 (timeout/length): {r['papers_errors']}")
    cls = classify(res)
    printer("\n## Clasificación §8.2")
    for comp, verdict in cls.items():
        printer(f"- {comp}: {verdict}")
    norm = normalize_audit([res[k]["run"] for k in
                            ("a1", "a2", "a3", "b1", "c1") if k in res])
    printer("\n## §8.5 normalize (auditoría offline)")
    for run, r in norm.items():
        printer(f"- {run}: nulos {r['zeros']}, decisiones que cambian "
                f"{r['changed_decisions']}, score_mismatch {r['score_mismatch']}, "
                f"Brier {r['brier_mean']:.4f}, NLL {r['nll_mean']:.4f}, "
                f"ECE {r['ece']}, desv. {r['sum_dev']}")
    if out_json:
        with open(out_json, "w") as f:
            json.dump({"results": res, "classification": cls,
                       "normalize_audit": norm}, f, ensure_ascii=False,
                      indent=1, default=str)
    return res, cls, norm


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="puerta de visibilidad §5.1")
    g.add_argument("host", choices=sorted(HOSTS))
    g.add_argument("modo", choices=["prob", "disc"])
    g.add_argument("celda", choices=["inject", "nostruct", "rot1"])
    r = sub.add_parser("run", help="supervisor de batería §5.2/5.3")
    r.add_argument("celda", choices=sorted(CELLS))
    r.add_argument("--retry-errors", action="store_true")
    rep = sub.add_parser("report", help="auditoría + clasificación §8.2")
    rep.add_argument("--json", default=None, help="vuelca resultados a JSON")
    args = ap.parse_args()
    if args.cmd == "gate":
        ok, _ = gate(args.host, args.modo, args.celda)
        sys.exit(0 if ok else 1)
    if args.cmd == "run":
        status = run_cell(args.celda, args.retry_errors)
        sys.exit(0 if status in ("complete", "stopped") else 2)
    if args.cmd == "report":
        report(args.json)


if __name__ == "__main__":
    main()
