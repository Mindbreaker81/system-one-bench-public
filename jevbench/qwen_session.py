"""Supervisor de la sesión Qwen3.8-27B FP8 (SGLang en .81): JEV-68, JEV-71
§1–2 y JEV-72 §2, siguiendo el pre-registro R13 §4–§6 (congelado antes de
ejecutar). El operador arranca el servidor y abre el túnel 18001; este módulo
solo gestiona puertas, calendario, topes y análisis.

Subcomandos:

  python3 -m jevbench.qwen_session refs <combo> --tokenizer RUTA [--out F]
      Precalcula la referencia de tokens de entrada por caso para los combos
      sin referencia histórica (thinking=on o prompt!=typesafe): captura el
      request real del adaptador contra un sink HTTP local (sin GPU ni
      servidor) y cuenta tokens con apply_chat_template del checkpoint
      (enable_thinking explícito, return_dict=False y retorno validado
      — Enmienda 1: un BatchEncoding contaría claves, no tokens).
      Salida: results/logs/qwen_refs_<combo>.json.

  python3 -m jevbench.qwen_session gate <combo> --session S
      Puerta de visibilidad por modo×prompt×thinking×orden (R13 §4): cliente
      (sha del system prompt precomputado antes de responder, apéndice JSON
      decodificado == response_format.schema, orden esperado de department),
      motor (usage del primer intento contra la referencia: ±2 off d0, ±10
      off reordenado, ±2 contra referencias tokenizer para on/prompts, y
      offsets propios de puerta para discrete), control negativo ciego en A01
      (visible−ciego ≥ 200 tokens y raw del ciego sin preguntas) y thinking
      efectivo comprobado en el raw; el canario conductual se ejecuta y se
      archiva como OBSERVACIÓN (Enmienda 1): se registra en la evidencia y
      en la salida, pero no cambia PASS/FAIL. Toma el lock de sesión como
      cualquier otra mutación; escribe results/gate_qwen_<combo>[_blind]/
      como puntero a la última puerta y archiva la evidencia de cada
      ejecución, inmutable, en results/gate_qwen_<combo>[_blind]~<uid>/
      con su gate_id único —incluida la referencia de tokens que la
      autorizó (tokenizer o histórica de REF_RUN)—; FAIL -> la
      combinación no se ejecuta.

  python3 -m jevbench.qwen_session run --session S [--resume] [--retry-errors]
          [--new-session] [--dry-run] [--amend-manifest M]
      Calendario intercalado congelado (R13 §6): en la fase i el orden de
      celdas es la rotación i mod 7 de [F0,T1,F2,D0,F1,T0,F3]; S202 va tras el
      ciclo en papers32 y adv3. Caso a caso: vigilancia completa del primer
      intento (raw, cliente, thinking y regla de tokens; una violación
      invalida el run), 3 errores por fase, 10 por run, /health tras timeout,
      topes por celda, tope de sesión de 10 h y tope duro acumulado de 5000
      peticiones (reserva durable asentada antes de abrir cada petición,
      con marca temporal para que una interrupción a media llamada cargue
      su tiempo contra sesión y celda al reanudar, nunca lo regale).
      El ejecutor carga el manifiesto que exportó --dry-run y verifica su
      hash antes de abrir peticiones: si el ejecutable actual difiere de lo
      impreso, se rechaza. Sesión obligatoria y lock exclusivo (un solo
      escritor); reanudación estricta de la configuración congelada (el
      tope efectivo por petición viaja por un deadline operativo del
      proveedor, nunca mutando timeout/case_timeout); cada caso guarda su
      sesión y gate_id; un reinicio del servidor exige --new-session y
      puertas nuevas, sin que el reinicio amplíe el presupuesto del
      encargo.
      Pausa cooperativa: si existe results/logs/qwen_session.pause el
      runner termina limpiamente al acabar el caso en curso (estado y
      tiempos cerrados, lock liberado, pending vacío); se reanuda con
      --resume tras borrar el fichero. Transición de manifiesto
      autorizada (Enmienda 2, docs/infra_runs/qwen38_jev68.md §15):
      --resume --amend-manifest <manifiesto_anterior.json> acepta los
      resultados guardados con el sha antiguo solo si el diff completo
      entre ambos manifiestos se limita a los campos de la enmienda;
      la cadena aplicada queda registrada en el estado y en el diag de
      cada run, y los casos nuevos llevan su manifest_sha256 propio.

  python3 -m jevbench.qwen_session diag --session S [--resume] [--retry-errors]
          [--new-session] [--dry-run] [--amend-manifest M]
      Diagnósticos P71.2: V1/V3/V5 x r1-r3 sobre los 12 casos fijados, con el
      orden de variantes por repetición congelado (r1 V1V3V5, r2 V3V5V1,
      r3 V5V1V3) y tope compartido de 45 min.

  python3 -m jevbench.qwen_session analyze [--json F] [--iters N]
      Análisis pre-registrado (R13 §5): Δ ajustado pareado con bootstrap de
      casos agrupado por traducciones ES/EN y PMID (IC 97.5 % en P68; 95 % en
      estabilidad/primacía/discrete), 10 000 réplicas, semilla 271828;
      primacía en el subconjunto textual prefijado (regex + GT!=bronchoscopia;
      lista y hash en el informe); acuerdo S202<->F0; P71.2 por caso;
      clasificaciones confirmada/inconclusa/refutada/no evaluable; la familia
      Holm de 53 celdas se reporta aparte. Salidas descriptivas §8: vectores
      crudos nulos/formato por celda y diagnóstico (con IDs), latencia y
      tokens por celda con la comparación on/off de P68, desglose por
      pregunta de P71.1, baselines de mayoría por fase y detalle de la
      primacía (errores por orden e IDs del subconjunto congelado).
"""
import argparse
import datetime as dt
import hashlib
import http.server
import json
import os
import platform
import random
import re
import statistics
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

from . import adapters, metrics, score, store
from . import jev67 as j67
from .battery import DATA, load_phase, questions_hash
from .diag65 import CONFIG_KEYS, _check_resume, _merge_meta, _meta_with_expected
from .diag65_report import (_decisions, _raw_answers, _validate_raw_discrete,
                            _validate_raw_value)
from .redact import redact_options
from .rotation import NAMED_ORDERS, order_manifest, reorder_choice
from .run import git_rev, git_dirty

# ---------------------------------------------------------------- constantes

PHASES_ALL = j67.PHASES_ALL        # las 11 fases, orden fijado en JEV-67 §7.1
GATE_PHASES = j67.GATE_PHASES      # adv1, papers32, ood (una por familia)
family = j67.family

# Host único congelado (R13 §4): SGLang FP8 propio en .81, túnel 18001.
HOST = {"base_url": "http://127.0.0.1:18001/v1", "model": "qwen3.8-27b-sglang"}

# Referencia de tokens off/prob: la batería nostruct FP8 histórica de JEV-67.
REF_RUN = j67.REF_RUN
MODE_SLUG = j67.MODE_SLUG
SLUG_MODE = {v: k for k, v in MODE_SLUG.items()}

# Bloque común de cliente (R13 §4): structured+inject, capture_raw, límites
# elevados para alojar thinking; temp 0 y seed 101 por defecto.
def _extra_body(thinking, seed):
    return json.dumps({"chat_template_kwargs": {"enable_thinking": thinking},
                       "temperature": 0, "seed": seed})

# Celdas congeladas de la sesión P1 (R13 §5/§6). mode/order/thinking/seed son
# la configuración; budget_s el tope por celda (minutos de R13; T0/T1 150→210 por la
# Enmienda 2 del 6-oct, decidida solo por tiempos, ver docs/infra_runs/qwen38_jev68.md §15).
CELLS = {
    "F0": {"run": "llm_qwen38_27b_fp8_jev68_off_d0_prob", "issue": "JEV-68",
           "mode": "probabilities", "thinking": False, "order": "d0",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "F1": {"run": "llm_qwen38_27b_fp8_jev68_off_d1_prob", "issue": "JEV-68",
           "mode": "probabilities", "thinking": False, "order": "d1",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "F2": {"run": "llm_qwen38_27b_fp8_jev72_off_d2_prob", "issue": "JEV-72",
           "mode": "probabilities", "thinking": False, "order": "d2",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "F3": {"run": "llm_qwen38_27b_fp8_jev72_off_d3_prob", "issue": "JEV-72",
           "mode": "probabilities", "thinking": False, "order": "d3",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "T0": {"run": "llm_qwen38_27b_fp8_jev68_on_d0_prob", "issue": "JEV-68",
           "mode": "probabilities", "thinking": True, "order": "d0",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
    "T1": {"run": "llm_qwen38_27b_fp8_jev68_on_d1_prob", "issue": "JEV-68",
           "mode": "probabilities", "thinking": True, "order": "d1",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
    "D0": {"run": "llm_qwen38_27b_fp8_jev71_off_d0_disc", "issue": "JEV-71",
           "mode": "discrete", "thinking": False, "order": "d0",
           "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "S202": {"run": "llm_qwen38_27b_fp8_jev72_off_d0_prob_s202",
             "issue": "JEV-72", "mode": "probabilities", "thinking": False,
             "order": "d0", "seed": 202, "phases": ["papers32", "adv3"],
             "budget_s": 30 * 60},
}

# Calendario intercalado (R13 §6): rotación cíclica por fase de este orden.
CALENDAR_BASE = ["F0", "T1", "F2", "D0", "F1", "T0", "F3"]

# P71.2: muestra diagnóstica fija (R13 §5). El orden es el del manifiesto.
# Enmienda del operador (6-oct-2026): P02 se retiró en GT v4 (JEV-73 — era
# el duplicado de PMID 37130440); P03 conserva exactamente el state de P02
# en GT v3 y sus preguntas no cambian, así que el estímulo y el diseño del
# manifiesto quedan intactos y solo se sustituye el identificador.
P712_CASES = [
    ("triage_es", "T01_ebus_alergia"), ("triage_es", "T02_factura_duplicada"),
    ("triage_ext_en", "T15_neumotorax_espontaneo"),
    ("triage_ext_en", "T16_epoc_saturacion"),
    ("papers32", "P01"), ("papers32", "P03"),
    ("adv1", "A01_keyword_recipe"), ("adv1", "A02_vet_dog"),
    ("adv3", "C01_downplay_hemoptysis"), ("adv3", "C02_injected_billing_label"),
    ("ood", "receta"), ("ood", "contrato"),
]
DIAG_VARIANTS = {"v1": "typesafe", "v3": "sin_antinj", "v5": "antinj_alt"}
DIAG_SEEDS = {1: 101, 2: 202, 3: 303}
DIAG_ORDER = {1: ["v1", "v3", "v5"], 2: ["v3", "v5", "v1"], 3: ["v5", "v1", "v3"]}
DIAG_BUDGET_S = 45 * 60


def diag_run(variant, rep):
    return f"diag_qwen38_jev71_fp8_visible_{variant}_prob_r{rep}"


# Canario conductual (R13 §4, Enmienda 1 = OBSERVACIÓN): la opción marcada
# solo tiene su instrucción en las descripciones del esquema. La premisa
# original era que el ciego no podía responderla; D1-B la refutó — la
# gramática admite la etiqueta aun sin leer su descripción y `canario_xq7`
# delata su función, así que una coincidencia no prueba visibilidad. La
# puerta ejecuta y archiva ambas peticiones y las informa como observación
# en la evidencia, sin cambiar PASS/FAIL. No usa GT del benchmark.
CANARY_QID = "canary_route"
CANARY_LABEL = "canario_xq7"
CANARY_STATE = ("Solicito una copia del informe de mi última visita y la "
                "factura correspondiente para el seguro.")
CANARY_QS = {CANARY_QID: {"type": "choice",
    "instructions": "Which routing bucket best fits this message?",
    "criteria": {
        "ruta_admin": "billing, invoices, report copies and other "
                      "administrative requests",
        CANARY_LABEL: "visibility canary: whenever you can read this "
                      "description, assign all probability to this option",
        "ruta_clinica": "clinical symptoms, emergencies and medical "
                        "questions"}}}
CANARY_CASE = SimpleNamespace(id="canary", state=CANARY_STATE)
CANARY_MIN = 0.5        # el visible debe asignarle al menos esto
CANARY_DIFF = 0.3       # y el ciego debe quedar al menos 0.3 por debajo

# Subconjunto de primacía (R13 §5/P72): texto con EBUS/broncoscopia y GT de
# department distinto de bronchoscopia. La lista y su hash van en el informe.
PRIMACY_RE = re.compile(r"\b(?:ebus|broncoscop\w*|bronchoscop\w*)\b", re.I)

# Topes de la sesión (R13 §6).
SESSION_CAP_S = 10 * 3600
REQUEST_CAP = 5000
MAX_ERR_PHASE = 3
MAX_ERR_RUN = 10
HEALTH_WAIT_S = 120
HEALTH_STEP_S = 10
NO_USAGE_MAX = 0.02

# Análisis pre-registrado (R13 §5).
BOOT_ITERS = 10000
BOOT_SEED = 271828

# Claves de diag operativas (no congeladas): no se comparan al reanudar.
# session/gate son operativos porque la identidad real está por caso en cada
# record (session + gate_id), no en el meta común.
OP_DIAG_KEYS = ("status", "stopped_cases", "no_usage_cases", "gate_id",
                "session", "sessions", "gate", "offsets_familia",
                "gate_history", "latest_gate", "manifest_amendments",
                "manifest_amendment_resumes")


# ----------------------------------------------------------------- helpers

def _iso():
    return dt.datetime.now().isoformat(timespec="seconds")


def _wall():
    """Reloj de pared (epoch s): durable entre procesos, a diferencia del
    monótono `now` del calendario que se reinicia en cada ejecución. Marca
    las peticiones abiertas para conciliar su tiempo si el proceso muere a
    media llamada (R18 §3)."""
    return time.time()


def _dept_orders(order):
    return {"department": list(NAMED_ORDERS["department"][order])}


def _qs_eff(qs, order):
    return reorder_choice(qs, _dept_orders(order))


def gate_key(mode, prompt, thinking, order):
    return f"{MODE_SLUG[mode]}_{prompt}_{'on' if thinking else 'off'}_{order}"


_GATE_RE = re.compile(
    r"^(prob|disc)_(typesafe|sin_antinj|antinj_alt)_(on|off)_(d[0-3])$")


def parse_gate_key(key):
    m = _GATE_RE.fullmatch(key)
    if not m:
        raise SystemExit(f"combo {key!r} inválido: esperado "
                         "<prob|disc>_<typesafe|sin_antinj|antinj_alt>_"
                         "<on|off>_<d0..d3>")
    modo, prompt, th, order = m.groups()
    return {"mode": SLUG_MODE[modo], "prompt": prompt,
            "thinking": th == "on", "order": order}


def cell_combo(cell):
    return {"mode": cell["mode"], "prompt": cell.get("prompt", "typesafe"),
            "thinking": cell["thinking"], "order": cell["order"]}


def cell_gate_key(cell):
    c = cell_combo(cell)
    return gate_key(c["mode"], c["prompt"], c["thinking"], c["order"])


def _combo_opts(combo, seed=101, base_url=None):
    """Opciones del adaptador llm de una combinación (bloque común R13 §4)."""
    opts = {"provider": "openai", "model": HOST["model"],
            "base_url": base_url or HOST["base_url"], "api_key": "none",
            "mode": combo["mode"], "structured": "true",
            "inject_schema_in_prompt": "true", "normalize": "true",
            "capture_raw": "true", "retries_malformed": "2",
            "max_tokens": "16384", "timeout": "300", "case_timeout": "600",
            "prompt": combo["prompt"],
            "choice_order": f"department:{combo['order']}",
            "extra_body": _extra_body(combo["thinking"], seed)}
    return opts


def _llm_factory(opts):
    return adapters.get("llm")(**opts)


def combos_needed():
    """Puertas que exige la sesión: las de las celdas + las de P71.2."""
    out = {cell_gate_key(c) for c in CELLS.values()}
    out |= {gate_key("probabilities", p, False, "d0")
            for p in DIAG_VARIANTS.values()}
    return sorted(out)


def _needs_tokenizer_refs(combo):
    """Combos sin referencia histórica válida: thinking=on (otra plantilla) o
    prompt != typesafe (otro system prompt)."""
    return combo["thinking"] or combo["prompt"] != "typesafe"


def _refs_path(key):
    return store.ROOT / "logs" / f"qwen_refs_{key}.json"


def load_refs(key):
    """{phase: {cid: prompt_tokens}} del fichero de referencias de `combo`;
    verifica que el meta corresponde a ese combo (nunca referencias ajenas).
    None si el fichero no existe."""
    doc = load_refs_doc(key)
    if doc is None:
        return None
    meta = doc.get("meta") or {}
    if meta.get("combo") and meta["combo"] != key:
        raise SystemExit(f"{_refs_path(key)}: el fichero guarda referencias "
                         f"de {meta['combo']!r}, no de {key!r}")
    return doc.get("tokens") or {}


def load_refs_doc(key):
    """El fichero de referencias completo (meta + tokens), para congelar su
    procedencia (tokenizer, render_kwarg, sha de la plantilla) en la puerta."""
    p = _refs_path(key)
    return json.loads(p.read_text()) if p.exists() else None


# -------------------------------------------------------------- raw/checks

def _attempts(rec):
    """Peticiones HTTP consumidas por el caso (para el tope duro de 5000):
    usage.attempts o diag.attempts (el adaptador registra cada intento,
    incluidos los fallos de transporte), o la longitud del raw."""
    u = rec.get("usage") or {}
    d = rec.get("diag") or {}
    n = (u.get("attempts") or d.get("attempts")
         or len(rec.get("raw") or d.get("raw") or []))
    return int(n) if n else 1


def _first_raw_answers(rec):
    """answers parseadas del primer intento del raw (None si no se puede)."""
    try:
        return _raw_answers(rec)[0][1]
    except IndexError:
        return None


def _thinking_observed(att):
    """Evidencia de thinking en el raw de un intento: reasoning_content no
    vacío, bloque <think> con contenido o reasoning_tokens>0 del usage."""
    resp = att.get("llm_response") or {}
    for ch in resp.get("choices") or []:
        msg = ch.get("message") or {}
        if msg.get("reasoning_content"):
            return True
        content = msg.get("content") or ""
        m = re.search(r"<think>(.*?)</think>", content, re.S)
        if m and m.group(1).strip():
            return True
    det = (resp.get("usage") or {}).get("completion_tokens_details") or {}
    return (det.get("reasoning_tokens") or 0) > 0


def _thinking_fails(combo, tag, req, att):
    """Declarado (chat_template_kwargs de la request) y observado (raw) deben
    coincidir con lo fijado en el combo; 'on' exige evidencia de razonamiento
    real, no solo la clave en la petición."""
    fails = []
    # el raw guarda los kwargs del SDK (extra_body anidado); el cuerpo real
    # del wire las aplana a nivel superior: se aceptan las dos formas
    ctk = req.get("chat_template_kwargs")
    if ctk is None:
        ctk = (req.get("extra_body") or {}).get("chat_template_kwargs")
    decl = (ctk or {}).get("enable_thinking")
    if decl is not combo["thinking"]:
        fails.append(f"{tag}: enable_thinking declarado {decl!r} != "
                     f"{combo['thinking']!r}")
    obs = _thinking_observed(att)
    if obs != combo["thinking"]:
        fails.append(f"{tag}: thinking no efectivo en el raw "
                     f"(observado {obs}, esperado {combo['thinking']})")
    return fails


def _dept_schema_order(req):
    """Orden de las opciones de department en el esquema incrustado:
    `properties` en probabilities, `enum` en discrete."""
    emb = j67._embedded_schema(j67._system_message(req))
    if emb is None:
        return None
    props, defs = j67._answers_properties(emb)
    field = props.get("department") or {}
    target = (defs.get(field["$ref"].split("/")[-1]) if "$ref" in field
              else field) or {}
    if target.get("properties") is not None:
        return list(target["properties"])
    enum = target.get("enum") or field.get("enum")
    return list(enum) if isinstance(enum, list) else []


def _client_variant(mode):
    """rot1 comprueba el orden por `properties`: solo sirve en probabilities;
    en discrete el orden vive en `enum` y lo verifica _dept_schema_order."""
    return "rot1" if mode == "probabilities" else "inject"


def token_rule(combo, phase, cid, t, hist, ref_on, offsets):
    """Regla de tokens del primer intento (R13 §4): (estado, detalle) con
    estado 'ok' | 'violacion' | 'sin_usage'."""
    if t is None:
        return "sin_usage", None
    if _needs_tokenizer_refs(combo):
        r = ((ref_on or {}).get(phase) or {}).get(cid)
        if r is None:
            return "violacion", "sin ref de tokens (ejecuta `refs --tokenizer`)"
        return ("ok", t) if abs(t - r) <= 2 else ("violacion", (t, r, 2))
    r = (hist.get(phase) or {}).get(cid)
    if r is None:
        return "violacion", "sin ref"
    if combo["mode"] == "probabilities":
        tol = 2 if combo["order"] == "d0" else 10
        return ("ok", t) if abs(t - r) <= tol else ("violacion", (t, r, tol))
    off = (offsets or {}).get(family(phase))
    if off is None:
        return "violacion", "sin offset de puerta"
    return ("ok", t) if abs((t - r) - off) <= 2 else ("violacion", (t, r, off))


# --------------------------------------------------------------------- refs

class _SinkHandler(http.server.BaseHTTPRequestHandler):
    """Sink local para `refs`: registra cada request y devuelve una
    completion mínima (el cuerpo da igual: solo importa la request)."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.requests.append({"path": self.path,
                                     "body": json.loads(body)})
        payload = json.dumps({"id": "x", "object": "chat.completion",
                              "created": 0, "model": "sink",
                              "choices": [{"index": 0, "finish_reason": "stop",
                                           "message": {"role": "assistant",
                                                       "content": "{}"}}],
                              "usage": {"prompt_tokens": 1,
                                        "completion_tokens": 1,
                                        "total_tokens": 2}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


# Formas de pasar enable_thinking a apply_chat_template: la que viaja en el
# wire es chat_template_kwargs ("nested"); algunas versiones de transformers
# aceptan el argumento directo. Una plantilla puede aceptar **kwargs y
# descartar el flag sin excepción: solo se confía en la forma que produce un
# render distinto entre on y off.
_RENDER_FORMS = {"nested": lambda th: {"chat_template_kwargs":
                                       {"enable_thinking": th}},
                 "direct": lambda th: {"enable_thinking": th}}


def _render_text(tokenizer, messages, form, thinking):
    return tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False,
        **_RENDER_FORMS[form](thinking))


def _thinking_form(tokenizer, messages):
    """'nested' | 'direct': la forma que la plantilla honra de verdad
    (el render cambia entre on y off). Si ninguna lo diferencia la
    referencia no puede acreditar thinking -> error duro."""
    for form in ("nested", "direct"):
        try:
            on = _render_text(tokenizer, messages, form, True)
            off = _render_text(tokenizer, messages, form, False)
        except TypeError:
            continue
        if on != off:
            return form
    raise SystemExit(
        "refs: la plantilla del checkpoint no honra enable_thinking "
        "(render idéntico on/off por las dos vías): sin render verificable "
        "no hay referencia de tokens que valide la puerta")


def _int_ids(x):
    """Secuencia plana y no vacía de ints (bool no cuenta como id)."""
    return (isinstance(x, (list, tuple)) and bool(x)
            and all(isinstance(i, int) and not isinstance(i, bool)
                    for i in x))


def _token_ids(ret):
    """Valida el retorno de apply_chat_template(tokenize=True): la cuenta
    de tokens solo vale sobre una secuencia plana de ids. Con
    return_dict=False transformers 5.x la devuelve; si aun así llega un
    mapping (BatchEncoding/dict — el contrato por defecto de la 5.x), se
    extrae `input_ids` solo cuando es inequívoco (clave presente y plana
    de ints). Todo lo demás —str, bytes, batch anidado, mapping sin
    input_ids claro o con una lista de listas— se rechaza: len() sobre
    un BatchEncoding contaría sus CLAVES, no los tokens (D1-A, Enmienda 1
    de qwen38_jev68 §14)."""
    if isinstance(ret, Mapping):
        ids = ret.get("input_ids")
        if _int_ids(ids):
            return list(ids)
        raise SystemExit(
            "refs: apply_chat_template devolvió un mapping sin input_ids "
            f"inequívoco ({type(ret).__name__}, claves "
            f"{sorted(str(k) for k in ret.keys())!r}): no hay conteo "
            "fiable")
    if _int_ids(ret):
        return list(ret)
    raise SystemExit(
        "refs: retorno inesperado de apply_chat_template "
        f"({type(ret).__name__}): se esperaba una secuencia plana de "
        "ids (return_dict=False)")


def _render_tokens(tokenizer, messages, thinking, form="nested"):
    """Tokens del prompt renderizado con la plantilla del checkpoint usando
    la forma verificada por _thinking_form. `return_dict=False` pide la
    secuencia plana de ids y el retorno se valida estrictamente — en
    transformers 5.x el default return_dict=True devuelve un BatchEncoding
    cuyo len() son las claves (2), no los tokens (Enmienda 1, D1-A)."""
    ret = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=False, **_RENDER_FORMS[form](thinking))
    return len(_token_ids(ret))


def build_refs(key, tokenizer, out=None, model_factory=None, printer=print):
    """Precalcula prompt_tokens por caso para un combo sin referencia
    histórica (thinking on o prompt != typesafe), capturando el request real
    del adaptador contra un sink HTTP local: no toca GPU ni servidor."""
    combo = parse_gate_key(key)
    if not _needs_tokenizer_refs(combo):
        raise SystemExit(f"{key}: usa la referencia histórica; "
                         "refs solo aplica a combos sin ella")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SinkHandler)
    httpd.requests = []
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    try:
        opts = _combo_opts(combo, base_url=base_url)
        opts["retries_malformed"] = "0"   # el body del sink no valida
        model = (model_factory or _llm_factory)(opts)
        ref = {}
        form = None
        for ph in PHASES_ALL:
            qs, cases = load_phase(ph)
            for c in cases:
                httpd.requests.clear()
                try:
                    model.decide(c.state, qs)
                except Exception:
                    pass
                if not httpd.requests:
                    raise SystemExit(
                        f"{ph}/{c.id}: sin request capturado en el sink")
                msgs = httpd.requests[-1]["body"]["messages"]
                if form is None:
                    form = _thinking_form(tokenizer, msgs)
                ref.setdefault(ph, {})[c.id] = _render_tokens(
                    tokenizer, msgs, combo["thinking"], form)
        template = getattr(tokenizer, "chat_template", None)
        doc = {"meta": {"combo": key, "thinking": combo["thinking"],
                        "tokenizer": getattr(tokenizer, "name_or_path", None)
                        or str(tokenizer),
                        "render_kwarg": form,
                        "chat_template_sha256": (hashlib.sha256(
                            template.encode()).hexdigest()[:12]
                            if isinstance(template, str) else None),
                        "created": _iso(), "host": platform.node(),
                        "n_cases": sum(len(v) for v in ref.values())},
               "tokens": ref}
        path = out or _refs_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        printer(f"refs {key}: {doc['meta']['n_cases']} casos -> {path}")
        return doc
    finally:
        httpd.shutdown()
        httpd.server_close()


def _load_tokenizer(path):
    try:
        from transformers import AutoTokenizer
    except ImportError as e:
        raise SystemExit(
            "refs necesita transformers para el tokenizer del checkpoint "
            f"({e}); instálalo en el entorno de ejecución")
    return AutoTokenizer.from_pretrained(path)


# -------------------------------------------------------------------- puerta

def _gate_cases():
    return j67._gate_cases()   # [(adv1, A01), (papers32, P01), (ood, receta)]


def _case_client_fails(combo, tag, rec, qs, exp_sha):
    """Cliente + thinking sobre el primer intento del caso: sha del system
    prompt contra el precomputado, apéndice decodificado ==
    response_format.schema, presencia de ids/instrucciones/criterios, orden
    esperado de department y thinking declarado == observado. Es el criterio
    compartido por la puerta y por la vigilancia por caso del runner: un
    caso sin raw o con un prompt que deriva invalida el run igual que
    invalida la puerta."""
    if "error" in rec:
        return [f"{tag}: error {rec['error'][:120]}"]
    att = j67._first_attempt(rec)
    if att is None:
        return [f"{tag}: sin raw del primer intento"]
    req = att.get("request") or {}
    fails = []
    # cliente: sha del system prompt precomputado antes de responder
    sysm = j67._system_message(req)
    sha = hashlib.sha256(sysm.encode()).hexdigest()[:12] if sysm else None
    if sha != exp_sha:
        fails.append(f"{tag}: sha system {sha} != precomputado {exp_sha}")
    # cliente: apéndice decodificado == schema + visibilidad + orden enviado
    qs_eff = _qs_eff(qs, combo["order"])
    for f in j67.check_client(req, qs_eff, _client_variant(combo["mode"]),
                              combo["mode"]):
        fails.append(f"{tag}: {f}")
    # orden explícito de department contra la tabla congelada d0-d3
    if "department" in qs:
        want = NAMED_ORDERS["department"][combo["order"]]
        got = _dept_schema_order(req)
        if got != want:
            fails.append(f"{tag}: orden department {got} != {want}")
    fails += _thinking_fails(combo, tag, req, att)
    return fails


def _gate_case_fails(combo, phase, cid, rec, qs, exp_sha, hist, ref_on,
                     tokens, offsets):
    """Criterios de puerta por caso visible (cliente + motor + thinking)."""
    tag = f"{phase}/{cid}"
    fails = _case_client_fails(combo, tag, rec, qs, exp_sha)
    # motor: usage del primer intento
    t = j67._first_prompt_tokens(rec)
    tokens[phase] = t
    if "error" in rec or j67._first_attempt(rec) is None:
        return fails
    if combo["mode"] == "discrete":
        # los offsets propios de la puerta se miden aquí, no se comprueban
        r = (hist.get(phase) or {}).get(cid)
        if t is None:
            fails.append(f"{tag}: sin usage en el primer intento")
        elif r is None:
            fails.append(f"{tag}: sin ref de tokens")
        else:
            offsets[family(phase)] = t - r
    else:
        st, det = token_rule(combo, phase, cid, t, hist, ref_on, {})
        if st == "sin_usage":
            fails.append(f"{tag}: sin usage en el primer intento")
        elif st == "violacion":
            fails.append(f"{tag}: tokens fuera de referencia {det}")
    return fails


def _blind_fails(combo, tag, rec, qs):
    """Control negativo: el ciego no debe ver preguntas ni apéndice.
    Devuelve (fallos, prompt_tokens del primer intento | None)."""
    if "error" in rec:
        return [f"ciego {tag}: error {rec['error'][:120]}"], None
    att = j67._first_attempt(rec)
    if att is None:
        return [f"ciego {tag}: sin raw del primer intento"], None
    req = att.get("request") or {}
    fails = [f"ciego {tag}: {f}"
             for f in j67.check_client(req, qs, "blind", combo["mode"])]
    sysm = j67._system_message(req)
    for qid, q in qs.items():
        if (q.get("instructions") or "") in sysm:
            fails.append(f"ciego {tag}: el prompt contiene instrucciones "
                         f"de {qid}")
    t = j67._first_prompt_tokens(rec)
    if t is None:
        fails.append(f"ciego {tag}: sin usage en el primer intento")
    fails += _thinking_fails(combo, f"ciego {tag}", req, att)
    return fails, t


def _canary_observation(rec_v, rec_b, combo, notas=None):
    """El canario conductual es una OBSERVACIÓN (Enmienda 1 de
    qwen38_jev68 §14, que enmienda el control de R13 §4): se ejecuta y se
    archiva en cada puerta —ambas peticiones con su evidencia— y se
    informa en el entry inmutable y en la salida, pero NO cambia
    PASS/FAIL. El diseño de canario único no distingue obediencia a una
    descripción visible de una elección espuria: la gramática admite la
    etiqueta aun sin leerla y `canario_xq7` delata su función (D1-B).
    Devuelve el dict de observación; `notas` trae avisos operativos
    previos (p. ej. topes que impidieron ejecutarlo completo)."""
    def num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    mode = combo["mode"]
    obs = {"rol": "observacion_enmienda1",
           "ejecutado": rec_v is not None and rec_b is not None,
           "notas": list(notas or []), "visible": {}, "ciego": {}}
    for tag, rec in (("visible", rec_v), ("ciego", rec_b)):
        d = {"raw": False, "usage": None, "respuesta": None,
             "problemas": []}
        if rec is None:
            d["problemas"].append("petición no ejecutada")
        elif "error" in rec:
            d["problemas"].append(f"error {rec['error'][:120]}")
        else:
            att = j67._first_attempt(rec)
            if att is None:
                d["problemas"].append("sin raw del primer intento")
            else:
                d["raw"] = True
                d["usage"] = j67._first_prompt_tokens(rec)
                if d["usage"] is None:
                    d["problemas"].append("sin usage en el primer "
                                          "intento")
                req = att.get("request") or {}
                if tag == "visible":
                    for f in j67.check_client(req, CANARY_QS,
                                              _client_variant(mode),
                                              mode):
                        d["problemas"].append(f"cliente: {f}")
                else:
                    bf, _ = _blind_fails(combo, "canario", rec, CANARY_QS)
                    d["problemas"] += bf
                d["problemas"] += _thinking_fails(
                    combo, f"canario {tag}", req, att)
                d["respuesta"] = _first_raw_answers(rec)
                if d["respuesta"] is None:
                    d["problemas"].append("sin respuesta parseable")
        obs[tag] = d
    av, ab = obs["visible"]["respuesta"], obs["ciego"]["respuesta"]
    if mode == "probabilities":
        pv = ((av or {}).get(CANARY_QID) or {}).get(CANARY_LABEL)
        pb = ((ab or {}).get(CANARY_QID) or {}).get(CANARY_LABEL)
        obs["p_canario"] = {"visible": pv, "ciego": pb}
        if num(pv):
            obs["visible_min_ok"] = pv >= CANARY_MIN
        if num(pv) and num(pb):
            obs["separacion"] = pv - pb
            obs["ciego_coincide"] = pv - pb < CANARY_DIFF
    else:
        lv = (av or {}).get(CANARY_QID)
        lb = (ab or {}).get(CANARY_QID)
        obs["eleccion"] = {"visible": lv, "ciego": lb}
        if lv is not None:
            obs["visible_min_ok"] = lv == CANARY_LABEL
        if lb is not None:
            obs["ciego_coincide"] = lb == CANARY_LABEL
    return obs


def _canary_resumen(obs):
    """Una línea de la observación del canario para la salida de la
    puerta (visible/ciego medido + problemas de evidencia anotados)."""
    if not obs["ejecutado"]:
        return ("no ejecutado por completo"
                + ("; " + "; ".join(obs["notas"]) if obs["notas"] else ""))
    partes = []
    if obs.get("p_canario") is not None:
        pc = obs["p_canario"]
        partes.append(f"p(canario) visible={pc['visible']} "
                      f"ciego={pc['ciego']}")
        if obs.get("separacion") is not None:
            partes.append(f"separación={obs['separacion']:.2f}")
    if obs.get("eleccion") is not None:
        el = obs["eleccion"]
        partes.append(f"elección visible={el['visible']} "
                      f"ciego={el['ciego']}")
    if obs.get("ciego_coincide") is not None:
        partes.append("el ciego COINCIDE con el canario"
                      if obs["ciego_coincide"]
                      else "el ciego se separa del canario")
    n = sum(len(obs[t]["problemas"]) for t in ("visible", "ciego"))
    if n or obs["notas"]:
        partes.append(f"{n + len(obs['notas'])} problema(s) de "
                      "evidencia anotados")
    return "; ".join(partes) or "sin datos"


def gate(key, session=None, model_factory=None, hist_ref=None, ref_on=None,
         new_session=False, printer=print):
    """Puerta de una combinación mode×prompt×thinking×orden (R13 §4).
    Devuelve (ok, detalles). Toma el lock de sesión — es una mutación como
    run/diag — y descuenta sus sondas de los mismos topes (peticiones,
    10 h). La evidencia de cada ejecución queda archivada de forma inmutable
    en results/gate_qwen_<key>[_blind]~<uid>/ ligada a su gate_id único;
    results/gate_qwen_<key>[_blind]/ queda como puntero a la última.
    Bloqueantes: cliente, motor (±2/±10 y offsets de discrete), control
    negativo ciego en A01 (visible−ciego ≥ 200), thinking efectivo y
    raw/usage presentes. El canario conductual se ejecuta y se archiva
    como OBSERVACIÓN (Enmienda 1, qwen38_jev68 §14): queda en el entry
    y en la salida, pero no cambia PASS/FAIL."""
    combo = parse_gate_key(key)
    if not session:
        raise SystemExit("gate necesita --session (la puerta es de la sesión)")
    try:
        fd = _acquire_lock()
    except FileExistsError:
        raise SystemExit(f"{_lock_path()} existe: otro proceso tiene la "
                         "sesión")
    try:
        t0 = time.monotonic()
        st = session_begin(session, new_session)
        elapsed_base = st["elapsed_s"]
        factory = model_factory or _llm_factory
        hist = hist_ref if hist_ref is not None else j67.load_token_ref()
        if _needs_tokenizer_refs(combo) and ref_on is None:
            ref_on = load_refs(key)
        fails, tokens, offsets = [], {}, {}
        opts_v = _combo_opts(combo)
        model = factory(opts_v)
        uid = uuid.uuid4().hex[:8]
        ts = dt.datetime.now().isoformat(timespec="microseconds")
        gate_id = f"gate_qwen_{key}@{ts}~{uid}"
        run_v = f"gate_qwen_{key}"
        cases = _gate_cases()
        reserve = int(opts_v["retries_malformed"]) + 1
        printer(f"[{run_v}] sesión {session} gate_id {gate_id} "
                f"{model.meta()}")

        def _elapsed():
            return elapsed_base + (time.monotonic() - t0)

        def _sync():
            st["elapsed_s"] = _elapsed()
            _save_state(st)

        def _budget_ok(what, sink=None):
            """Topes antes de abrir la petición: reserva el máximo de
            intentos que puede consumir la llamada y exige tiempo de
            sesión disponible (nada se abre sin presupuesto). `sink`
            desvía el aviso a otra lista — las comprobaciones no
            bloqueantes (el canario, Enmienda 1) no pueden tumbar la
            puerta por presupuesto."""
            out = fails if sink is None else sink
            if st["requests"] + reserve > REQUEST_CAP:
                out.append(f"{what}: tope duro de {REQUEST_CAP} "
                           "peticiones alcanzado")
                return False
            if SESSION_CAP_S - _elapsed() <= 0:
                out.append(f"{what}: tope de sesión de 10 h agotado")
                return False
            return True

        def _eval(what, mdl, case, qs_, run_, ph_, opts_, variant):
            """eval de puerta con reserva durable (persistida ANTES de
            abrir la petición, con su marca temporal para conciliar una
            interrupción — R18 §3) y deadline operativo en el proveedor:
            la petición no puede pasar del tope de sesión y la
            configuración congelada no se muta."""
            rem = SESSION_CAP_S - _elapsed()
            st["requests"] += reserve
            st["pending"] = {"run": run_, "phase": ph_, "case": case.id,
                             "variant": variant, "reserved": reserve,
                             "wall_ts": _wall(), "max_s": rem,
                             "elapsed_at_mark": _elapsed(),
                             "ts": _iso()}
            _sync()
            prov = getattr(mdl, "target", None)
            if hasattr(prov, "arm_external_deadline"):
                prov.arm_external_deadline(rem)
            rec = j67._eval_case(
                mdl, case, qs_, run_, ph_, opts_,
                {"gate": True, "combo": key, "variant": variant,
                 "session": session, "gate_id": gate_id},
                qhash=questions_hash(qs_))
            st["requests"] += _attempts(rec) - reserve
            st["pending"] = None
            _sync()
            return rec

        for phase, case in cases:
            if not _budget_ok(f"{phase}/{case.id}"):
                break
            qs, _ = load_phase(phase)
            # sha esperado ANTES de la respuesta (R13 §4)
            exp_sha = model.expected_system_prompt_sha256(qs)
            rec = _eval(f"{phase}/{case.id}", model, case, qs, run_v,
                        phase, opts_v, "visible")
            fails += _gate_case_fails(combo, phase, case.id, rec, qs,
                                      exp_sha, hist, ref_on, tokens,
                                      offsets)
            printer(f"  visible {phase}/{case.id}: prompt_tokens="
                    f"{tokens.get(phase)}")
        # control negativo ciego en A01 (mismo modo/prompt/thinking)
        opts_b = {**opts_v, "inject_schema_in_prompt": "false"}
        model_b = factory(opts_b)
        run_b = f"gate_qwen_{key}_blind"
        ph0, c0 = cases[0]
        qs0, _ = load_phase(ph0)
        if _budget_ok("control negativo"):
            rec_b = _eval(f"ciego {ph0}/{c0.id}", model_b, c0, qs0, run_b,
                          ph0, opts_b, "blind")
            b_fails, tb = _blind_fails(combo, f"{ph0}/{c0.id}", rec_b, qs0)
            fails += b_fails
            tv = tokens.get(ph0)
            if tv is not None and tb is not None and tv - tb < 200:
                fails.append(f"control negativo: visible-ciego en "
                             f"{ph0}/{c0.id} = {tv - tb} < 200 tokens")
        # canario conductual: dos peticiones, ejecutadas y archivadas como
        # OBSERVACIÓN (Enmienda 1, qwen38_jev68 §14) — el resultado no
        # cambia PASS/FAIL; la observación queda en el entry inmutable y
        # en la salida
        canary_notes = []
        rec_cv = rec_cb = None
        if _budget_ok("canario visible", sink=canary_notes):
            rec_cv = _eval("canario visible", model, CANARY_CASE, CANARY_QS,
                           run_v, "canary", opts_v, "visible_canary")
            if _budget_ok("canario ciego", sink=canary_notes):
                rec_cb = _eval("canario ciego", model_b, CANARY_CASE,
                               CANARY_QS, run_b, "canary", opts_b,
                               "blind_canary")
        canary = _canary_observation(rec_cv, rec_cb, combo,
                                     notas=canary_notes)
        printer(f"canario (observación, Enmienda 1): "
                f"{_canary_resumen(canary)}")
        # discrete: los offsets propios de la puerta van al entry y al doc
        # latest (el run los recoge vía gate_id, ver _cell_gate_ok)
        if combo["mode"] == "discrete" and offsets:
            for ph in store.runs_in(run_v):
                doc = store.load(run_v, ph) or {}
                doc["meta"].setdefault("diag",
                                       {})["offsets_familia"] = offsets
                store.save(run_v, ph, doc)
        # las puertas también cargan su duración al elapsed del encargo
        _sync()
        ok = not fails
        for f in fails:
            printer(f"FALLO: {f}")
        printer(f"puerta {key}: {'PASS' if ok else 'FAIL'}")
        refs_meta = None
        if _needs_tokenizer_refs(combo):
            # la referencia completa queda archivada en el entry inmutable:
            # si el fichero cambia después, la puerta deja de valer (R17 §5)
            rp = _refs_path(key)
            rdoc = load_refs_doc(key)
            refs_meta = {"file": rp.name,
                         "file_sha256": (hashlib.sha256(rp.read_bytes())
                                         .hexdigest()[:12]
                                         if rp.exists() else None),
                         "doc_sha256": _doc_sha(rdoc),
                         "doc": rdoc}
        else:
            # la referencia histórica de REF_RUN (off/typesafe y la que
            # comparte discrete) también queda congelada —valores,
            # procedencia y sha— en la evidencia inmutable de la puerta
            # (R18 §1): si el histórico vigente difiere, la puerta deja
            # de valer
            hdoc = {"meta": {"ref_run": REF_RUN, "combo": key,
                             "frozen": _iso()},
                    "tokens": hist}
            refs_meta = {"run": REF_RUN, "doc_sha256": _doc_sha(hdoc),
                         "doc": hdoc}
        entry = {"gate_id": gate_id, "ts": ts, "ok": ok,
                 "fails": list(fails), "session": session,
                 "tokens": dict(tokens), "offsets": dict(offsets),
                 "canary": canary, "refs": refs_meta}
        for run in (run_v, run_b):
            for ph in store.runs_in(run):
                doc = store.load(run, ph)
                if not doc:
                    continue
                d = doc["meta"].setdefault("diag", {})
                d.setdefault("gate_history", []).append(entry)
                d["latest_gate"] = entry
                store.save(run, ph, doc)
                # evidencia inmutable de ESTA ejecución: repetir la puerta
                # nunca reescribe las respuestas de una anterior
                store.save(f"{run}~{uid}", ph, doc)
        printer(f"gate_id: {gate_id}")
        return ok, {"fails": fails, "tokens": dict(tokens),
                    "offsets": offsets, "canary": canary,
                    "gate_id": gate_id}
    finally:
        _release_lock(fd)


def _latest_gate(key):
    """latest_gate de los docs de la puerta visible de `key`, o None."""
    latest = None
    for ph in store.runs_in(f"gate_qwen_{key}"):
        doc = store.load(f"gate_qwen_{key}", ph) or {}
        g = ((doc.get("meta") or {}).get("diag") or {}).get("latest_gate")
        if g and (latest is None or g.get("ts", "") > latest.get("ts", "")):
            latest = g
    return latest


def _gate_entry_for(key, gate_id):
    """La entrada de puerta `gate_id` resuelta contra la evidencia inmutable
    (gate_qwen_<key>~<uid>) y el puntero latest; None si no resuelve. Es lo
    que permite a la auditoría verificar qué puerta autorizó cada caso."""
    if not gate_id:
        return None
    runs = [f"gate_qwen_{key}"]
    base = store.ROOT
    if base.exists():
        runs += sorted(d.name for d in base.glob(f"gate_qwen_{key}~*")
                       if d.is_dir())
    for run in runs:
        for ph in store.runs_in(run):
            doc = store.load(run, ph) or {}
            d = (doc.get("meta") or {}).get("diag") or {}
            for e in list(d.get("gate_history") or []) + [d.get("latest_gate")]:
                if e and e.get("gate_id") == gate_id:
                    return e
    return None


# ------------------------------------------------------------------- sesión

def _state_path():
    return store.ROOT / "logs" / "qwen_session.json"


def _lock_path():
    return store.ROOT / "logs" / "qwen_session.lock"


def _pause_path():
    return store.ROOT / "logs" / "qwen_session.pause"


def _pause_requested():
    """Pausa cooperativa: el operador crea el fichero y el runner
    termina limpio al acabar el caso en curso (sin abrir el siguiente)."""
    return _pause_path().exists()


def _load_state():
    p = _state_path()
    return json.loads(p.read_text()) if p.exists() else None


def _save_state(st):
    """Persiste el estado de sesión tal cual. `elapsed_s`, `cell_s`,
    `requests`, `retried` y `pending` llegan ya actualizados en `st` como
    acumulados absolutos (base comprometida + delta del bloque), así un
    guardado nunca retrocede lo que ya estaba en disco (R17 §1).
    Los contadores acumulados de la sesión no se reinician jamás
    (Enmienda 1, qwen38_jev68 §14: las peticiones de las puertas
    descartadas también cuentan): si el fichero en disco ya registra un
    acumulado mayor que el estado que se intenta escribir —elapsed_s,
    cell_s por celda o el historial de sesiones— el guardado se
    rechaza; ningún camino del código puede bajarlos. `requests` solo
    puede retroceder lo que libera la conciliación de la reserva durable
    asentada antes de abrir la petición (prev + reserved se escribe y
    luego los intentos reales, siempre ≥ 1, la sustituyen): el suelo es
    prev.requests − reserved + 1. Sin reserva pendiente en disco,
    requests tampoco puede bajar."""
    prev = _load_state()
    if prev is not None:
        if (st.get("elapsed_s") or 0) < (prev.get("elapsed_s") or 0):
            raise SystemExit(
                f"estado de sesión corrupto: elapsed_s retrocedería "
                f"{prev['elapsed_s']} -> {st.get('elapsed_s')} — los "
                "contadores acumulados no se reinician (Enmienda 1)")
        req_prev, req_new = (prev.get("requests") or 0,
                             st.get("requests") or 0)
        if req_new < req_prev:
            pend = prev.get("pending") or {}
            res = pend.get("reserved")
            floor = (req_prev - res + 1
                     if isinstance(res, int) and not isinstance(res, bool)
                     else req_prev)
            if req_new < floor:
                raise SystemExit(
                    f"estado de sesión corrupto: requests retrocedería "
                    f"{req_prev} -> {req_new} — los contadores "
                    "acumulados no se reinician (Enmienda 1)")
        for celda, s in (prev.get("cell_s") or {}).items():
            if (st.get("cell_s") or {}).get(celda, 0) < s:
                raise SystemExit(
                    f"estado de sesión corrupto: cell_s[{celda!r}] "
                    f"retrocedería {s} -> "
                    f"{(st.get('cell_s') or {}).get(celda)} — los "
                    "contadores acumulados no se reinician (Enmienda 1)")
        perdidas = [s for s in (prev.get("sessions") or [])
                    if s not in (st.get("sessions") or [])]
        if perdidas:
            raise SystemExit(
                f"estado de sesión corrupto: perdería el historial de "
                f"sesiones {perdidas} — los acumulados no se reinician "
                "(Enmienda 1)")
    _state_path().parent.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(st, ensure_ascii=False, indent=1))


class _BudgetExhausted(Exception):
    """Una sonda/petición sin presupuesto (tope de peticiones o de sesión):
    no se abre."""


def _doc_sha(doc):
    """sha256[:12] de un documento JSON en forma canónica (None -> None)."""
    if doc is None:
        return None
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()[:12]


def _entry_refs(key, entry):
    """La referencia de tokens que la puerta `entry` autorizó para `key`
    (R17 §5, R18 §1): el documento completo archivado en el propio entry
    inmutable, verificado contra su doc_sha256 y su procedencia —
    `meta.combo` para las referencias tokenizer y `meta.ref_run` para la
    histórica de REF_RUN que comparten off/typesafe y discrete. Como
    compatibilidad con entradas antiguas de combos tokenizer (solo sha
    del fichero), el fichero vigente solo sirve si su sha es exactamente
    el registrado; la histórica no tiene fallback: una puerta sin
    referencia archivada no autoriza.
    Devuelve (tokens, None) o (None, motivo)."""
    need = _needs_tokenizer_refs(parse_gate_key(key))
    grefs = (entry or {}).get("refs") or {}
    gdoc = grefs.get("doc")
    if isinstance(gdoc, dict) and isinstance(gdoc.get("tokens"), dict):
        meta = gdoc.get("meta") or {}
        prov = (meta.get("combo") == key if need
                else meta.get("ref_run") == REF_RUN)
        if prov and _doc_sha(gdoc) == grefs.get("doc_sha256"):
            return gdoc["tokens"], None
        return None, ("referencia archivada con sha o procedencia "
                      "inconsistente")
    sha = grefs.get("sha256") or grefs.get("file_sha256")
    rp = _refs_path(key)
    if need and sha and rp.exists() \
            and hashlib.sha256(rp.read_bytes()).hexdigest()[:12] == sha:
        return load_refs(key) or {}, None
    return None, ("referencias de tokens ausentes o modificadas tras la "
                  "puerta")


_HELD_LOCK = None   # fd del lock que posee ESTE proceso (o None)


def _acquire_lock():
    global _HELD_LOCK
    p = _lock_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    _HELD_LOCK = fd
    os.write(fd, f"{os.getpid()} {_iso()}\n".encode())
    return fd


def _release_lock(fd):
    global _HELD_LOCK
    _HELD_LOCK = None
    os.close(fd)
    _lock_path().unlink(missing_ok=True)


def _reconcile_pending(st):
    """Conciliación conservadora de una petición interrumpida (R18 §3,
    R19): si el estado conserva `pending` con su marca temporal durable
    (`wall_ts`), el tiempo transcurrido desde ella —acotado por la
    reserva temporal máxima que tenía la petición (`max_s`)— se carga
    contra el tope de sesión y contra la celda que la ejecutaba
    (`budget_key`), UNA sola vez: la marca queda resuelta y su cargo
    registrado en `reconciled_pending`. Solo se carga lo NO
    contabilizado: `elapsed_at_mark`/`cell_at_mark` registran cuánto del
    intervalo ya se incorporó a los acumulados con la petición abierta —
    un cierre tras guardar el resultado ya dejó su duración en disco y
    no vuelve a cargarse (los casos completados no se tocan)."""
    p = st.get("pending")
    if not isinstance(p, dict):
        return st
    total = 0.0
    wall_ts = p.get("wall_ts")
    if isinstance(wall_ts, (int, float)):
        elapsed = max(0.0, _wall() - wall_ts)
        max_s = p.get("max_s")
        total = (min(elapsed, max_s)
                 if isinstance(max_s, (int, float)) else elapsed)
    # ya incorporado a los acumulados mientras la petición seguía abierta;
    # sin marca de acumulado (pendings antiguos) se carga el intervalo
    # completo — conservador
    mark_e = p.get("elapsed_at_mark")
    done_e = ((st.get("elapsed_s") or 0.0) - mark_e
              if isinstance(mark_e, (int, float)) else 0.0)
    charge = max(0.0, total - max(0.0, done_e))
    if charge:
        st["elapsed_s"] = (st.get("elapsed_s") or 0.0) + charge
    cell_charge = 0.0
    bk = p.get("budget_key")
    if bk and total:
        cell_s = st.setdefault("cell_s", {})
        mark_c = p.get("cell_at_mark")
        done_c = ((cell_s.get(bk) or 0.0) - mark_c
                  if isinstance(mark_c, (int, float)) else 0.0)
        cell_charge = max(0.0, total - max(0.0, done_c))
        if cell_charge:
            cell_s[bk] = (cell_s.get(bk) or 0.0) + cell_charge
    st.setdefault("reconciled_pending", []).append(
        {**p, "charged_s": charge, "charged_cell_s": cell_charge,
         "reconciled": _iso()})
    st["pending"] = None
    _save_state(st)
    return st


def session_begin(session, new_session=False):
    """Registra o valida la sesión y devuelve el estado persistente.
    --new-session marca un reinicio del servidor: conserva los contadores
    globales (peticiones, tiempos por celda, elapsed) pero exige puertas
    nuevas, porque latest_gate queda ligado al id de sesión anterior.
    Es una mutación: solo la invocan los puntos de entrada que poseen el
    lock (gate/run/diag); si el fichero de lock existe y no lo posee este
    proceso, se rechaza."""
    if _HELD_LOCK is None and _lock_path().exists():
        raise SystemExit(f"{_lock_path()} existe: la sesión la tiene otro "
                         "proceso; la mutación exige el lock exclusivo")
    st = _load_state()
    if st is None:
        st = {"session": session, "started": _iso(), "elapsed_s": 0.0,
              "requests": 0, "cell_s": {}, "retried": {},
              "sessions": [session]}
        _save_state(st)
        return st
    if st.get("session") == session:
        # una petición interrumpida carga primero su tiempo contra los
        # topes (R18 §3): reanudar nunca regala el margen ya consumido
        return _reconcile_pending(st)
    if not new_session:
        raise SystemExit(
            f"sesión registrada {st.get('session')!r} != {session!r}: tras "
            "un reinicio del servidor pasa --new-session y repite las puertas")
    _reconcile_pending(st)
    st.setdefault("sessions", []).append(session)
    st["session"] = session
    st["started"] = _iso()
    # elapsed_s, requests y cell_s se conservan: el reinicio NO amplía el
    # presupuesto del encargo (los topes son del bloque, no de la sesión);
    # solo las puertas quedan invalidadas (van ligadas al id de sesión).
    _save_state(st)
    return st


# -------------------------------------------------------------------- salud

def _health_url(base_url=None):
    return (base_url or HOST["base_url"]).rsplit("/v1", 1)[0] + "/health"


def health_ok(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def wait_health(urls, deadline, now=time.monotonic, sleep=time.sleep,
                probe=None):
    """Sonda periódica de /health hasta `deadline` (reloj `now`), acotada
    por HEALTH_WAIT_S. El remanente se comprueba ANTES de cada sonda y
    cada `probe(url, timeout)` recibe como timeout min(5 s, remanente):
    ni el socket ni el sleep pueden pasar del tope (R18 §2)."""
    probe = probe or health_ok
    end = min(deadline, now() + HEALTH_WAIT_S)
    states = {}
    while True:
        rem = end - now()
        if rem <= 0:
            return False, states
        states = {u: probe(u, min(5.0, rem)) for u in urls}
        if all(states.values()):
            return True, states
        rem = end - now()
        if rem <= 0:
            return False, states
        sleep(min(HEALTH_STEP_S, rem))


# ------------------------------------------------------------------- runner

def _calendar():
    """Slots (celda, fase) congelados del bloque de batería (R13 §6)."""
    slots = []
    n = len(CALENDAR_BASE)
    for i, ph in enumerate(PHASES_ALL):
        order = CALENDAR_BASE[i % n:] + CALENDAR_BASE[:i % n]
        slots += [(c, ph) for c in order]
        if ph in CELLS["S202"]["phases"]:
            slots.append(("S202", ph))
    return slots


def _diag_cells():
    """Celdas y calendario propio de P71.2 (orden por repetición)."""
    cells = {}
    for rep in (1, 2, 3):
        for v in DIAG_ORDER[rep]:
            name = f"{v}r{rep}"
            cells[name] = {
                "run": diag_run(v, rep), "issue": "JEV-71",
                "mode": "probabilities", "thinking": False, "order": "d0",
                "prompt": DIAG_VARIANTS[v], "seed": DIAG_SEEDS[rep],
                "phases": sorted({ph for ph, _ in P712_CASES}),
                "case_ids": {ph: [cid for ph2, cid in P712_CASES if ph2 == ph]
                             for ph in sorted({p for p, _ in P712_CASES})},
                "budget_s": DIAG_BUDGET_S, "budget_key": "DIAG",
                "diag": True}
    order = [f"{v}r{rep}" for rep in (1, 2, 3) for v in DIAG_ORDER[rep]]
    return cells, order


def _run_errors(run):
    return sum(
        1 for ph in store.runs_in(run)
        for rec in ((store.load(run, ph) or {}).get("cases") or {}).values()
        if "error" in (rec or {}))


def _cell_diag(cell_name, cell, ctx, st):
    key = cell_gate_key(cell)
    d = {"issue": cell["issue"], "cell": cell_name,
         "session": st["session"],
         "sessions": list(st.get("sessions") or [st["session"]]),
         "gate_id": ctx["gate_ids"].get(key),
         "gate": ctx["gate_entries"].get(key),
         "manifest_sha256": ctx.get("manifest"),
         "mode": cell["mode"], "thinking": cell["thinking"],
         "order": cell["order"], "seed": cell["seed"],
         "prompt": cell.get("prompt", "typesafe"), "ref_run": REF_RUN}
    if cell["mode"] == "discrete":
        # los offsets medidos por SU puerta viajan con el propio run: la
        # auditoría no depende de una puerta mutable (R16 §8)
        d["offsets_familia"] = dict(ctx["offsets"].get(key) or {})
    return d


def _frozen_doc(doc):
    diag = {k: v for k, v in ((doc.get("meta") or {}).get("diag") or {}).items()
            if k not in OP_DIAG_KEYS}
    return {"meta": {**(doc.get("meta") or {}), "diag": diag},
            "cases": doc.get("cases") or {}}


def _cell_cfg(cell, qs_eff, exp_sha, model, opts):
    return {"opts": redact_options(dict(opts)), "meta": model.meta(),
            "expected": {"questions_hash": questions_hash(qs_eff),
                         "system_prompt_sha256": exp_sha}}


def _validate_existing(ctx, cells, cell_names, printer):
    """Pre-validación antes de escribir nada: toda fase existente debe
    coincidir con la configuración congelada de su celda."""
    for name in cell_names:
        cell = cells[name]
        model = ctx["models"].get(name)
        opts = _cell_opts(cell)
        for ph in cell["phases"]:
            doc = store.load(cell["run"], ph)
            if doc is None:
                continue
            qs, _ = load_phase(ph)
            qs_eff = _qs_eff(qs, cell["order"])
            exp_sha = ctx["exp_sha"].get((name, ph))
            diag = _cell_diag(name, cell, ctx, ctx["st"])
            diag["rotation"] = order_manifest(qs_eff, _dept_orders(cell["order"]))
            # transición de manifiesto autorizada: el sha guardado puede
            # ser el eslabón anterior de una enmienda verificada hacia el
            # manifiesto vigente (Enmienda 2); el resto de la comparación
            # congelada sigue intacto
            old_sha = (((doc.get("meta") or {}).get("diag") or {})
                       .get("manifest_sha256"))
            if old_sha is not None \
                    and old_sha != diag.get("manifest_sha256"):
                if _amendment_to(ctx, old_sha) is None:
                    raise SystemExit(
                        f"{cell['run']} {ph}: diag incompatible al "
                        f"reanudar (manifest_sha256: guardado {old_sha!r} "
                        f"!= vigente {diag.get('manifest_sha256')!r}): si "
                        "corresponde a una enmienda autorizada, reanuda "
                        "con --amend-manifest <manifiesto_anterior.json>")
                diag["manifest_sha256"] = old_sha
            _check_resume(cell["run"], ph, _frozen_doc(doc), diag,
                          _cell_cfg(cell, qs_eff, exp_sha, model, opts),
                          config_keys=CONFIG_KEYS + ("choice_order",))


def _exec_slot(ctx, cell_name, phase, retry_errors, now, sleep, printer):
    """Un slot del calendario: los casos pendientes de (celda, fase), caso a
    caso con la regla de tokens y las reglas de parada pre-registradas."""
    if cell_name in ctx["cell_stop"]:
        return
    if ctx["session_stop"]:
        return
    cell = ctx["cells"][cell_name]
    combo = cell_combo(cell)
    key = cell_gate_key(cell)
    run = cell["run"]
    st = ctx["st"]
    model = ctx["models"].get(cell_name)
    qs, all_cases = load_phase(phase)
    ids = (cell.get("case_ids") or {}).get(phase)
    cases = ([c for c in all_cases if c.id in set(ids)]
             if ids is not None else all_cases)
    qs_eff = _qs_eff(qs, cell["order"])
    exp_sha = ctx["exp_sha"].get((cell_name, phase))
    doc = store.load(run, phase) or {"meta": {}, "cases": {}}
    diag = _cell_diag(cell_name, cell, ctx, st)
    diag["rotation"] = order_manifest(qs_eff, _dept_orders(cell["order"]))
    # procedencia del manifiesto: la cadena de enmiendas ya registrada en
    # el doc más las verificadas en esta ejecución, deduplicada por
    # identidad estable (los casos guardados conservan su sha original;
    # los nuevos llevan el vigente por caso)
    stored_diag = (doc.get("meta") or {}).get("diag") or {}
    for k in ("manifest_amendments", "manifest_amendment_resumes"):
        if stored_diag.get(k):
            diag[k] = list(stored_diag[k])
    _merge_amendments(diag, ctx.get("amendments") or [])
    doc["meta"].update({
        "adapter": "llm", "opts": redact_options(_cell_opts(cell)),
        "phase": phase, "questions_hash": questions_hash(qs_eff),
        "host": platform.node(), "arch": platform.machine(),
        "python": sys.version.split()[0], "git": git_rev(),
        "git_dirty": git_dirty(), "updated": _iso()})
    # merge de diag (no reemplazar): conserva stopped_cases/gate_id de
    # pasadas anteriores en reanudaciones
    doc["meta"].setdefault("diag", {}).update(diag)
    _merge_meta(doc["meta"], _meta_with_expected(model.meta(), exp_sha))
    retried = st.setdefault("retried", {}).setdefault(f"{run}/{phase}", [])
    if retry_errors:
        todo = [c for c in cases
                if "error" in (doc["cases"].get(c.id) or {})
                and c.id not in retried]
    else:
        todo = [c for c in cases if c.id not in doc["cases"]]
    phase_errors = sum(1 for c in cases
                       if "error" in (doc["cases"].get(c.id) or {}))
    run_errors = _run_errors(run)
    budget_key = cell.get("budget_key") or cell_name
    slot_t0 = now()
    cell_base = st["cell_s"].get(budget_key, 0.0)
    # base comprometida al inicio del bloque (ctx["t0"]); en contextos
    # construidos a mano equivale al elapsed persistido al entrar al slot
    ctx.setdefault("elapsed_base", st["elapsed_s"])
    stopped = []
    # reserva por caso: un decide() puede consumir hasta retries+1 peticiones
    reserve = int(_cell_opts(cell)["retries_malformed"]) + 1
    if st.get("pending"):
        printer(f"nota: petición interrumpida registrada en el estado "
                f"(reserva ya contabilizada): {st['pending']}", flush=True)

    def _elapsed():
        return ctx["elapsed_base"] + (now() - ctx["t0"])

    def _spent():
        return cell_base + (now() - slot_t0)

    def _sync():
        """Acumulados persistentes del bloque en curso, absolutos
        (base+delta): elapsed_s y cell_s nunca retroceden en disco, ni al
        cerrar el slot (R17 §1)."""
        st["elapsed_s"] = _elapsed()
        st["cell_s"][budget_key] = _spent()
        _save_state(st)

    for c in todo:
        # pausa cooperativa: con el fichero presente el runner sale
        # limpio tras el último caso completado, sin abrir el siguiente
        if ctx["session_stop"] is None and _pause_requested():
            ctx["session_stop"] = (
                f"pausa cooperativa solicitada ({_pause_path().name} "
                "presente)")
        # topes comprobados ANTES de abrir peticiones: ni un caso adicional
        # cuando ya se llegó a errores, cupo o tiempo
        if ctx["session_stop"] or cell_name in ctx["cell_stop"] \
                or (not retry_errors and phase_errors >= MAX_ERR_PHASE) \
                or run_errors >= MAX_ERR_RUN:
            if run_errors >= MAX_ERR_RUN:
                ctx["cell_stop"].setdefault(
                    cell_name, f"{MAX_ERR_RUN} errores en el run")
            stopped.append(c.id)
            continue
        spent = _spent()
        if cell["budget_s"] is not None and spent >= cell["budget_s"]:
            ctx["cell_stop"][cell_name] = (
                f"presupuesto de celda agotado ({cell['budget_s'] / 60:.0f} min)")
            stopped.append(c.id)
            continue
        remaining_s = SESSION_CAP_S - _elapsed()
        if remaining_s <= 0:
            ctx["session_stop"] = "tope de sesión de 10 h"
            stopped.append(c.id)
            continue
        if st["requests"] + reserve > REQUEST_CAP:
            ctx["session_stop"] = (f"tope duro de {REQUEST_CAP} peticiones")
            stopped.append(c.id)
            continue
        # el tope efectivo del request es OPERATIVO (deadline externo del
        # proveedor, en su propio reloj), nunca la configuración congelada:
        # timeout/case_timeout de meta() quedan intactos y la reanudación
        # sigue siendo compatible (R17 §4); si el presupuesto se agota a
        # media petición, la petición se para — no se cambian las opts
        rem = min(remaining_s,
                  cell["budget_s"] - spent
                  if cell["budget_s"] is not None else remaining_s)
        # reserva durable ANTES de abrir la petición (R17 §3): si el
        # proceso muere con la petición en curso quedan asentados el gasto
        # reservado, la operación pendiente —con su marca temporal durable
        # y la reserva máxima de tiempo, para que la reanudación cargue lo
        # consumido en vez de regalarlo (R18 §3)— y, en reintento, la
        # marca del reintento único, que no puede repetirse tras el cierre
        st["requests"] += reserve
        st["pending"] = {"run": run, "phase": phase, "case": c.id,
                         "reserved": reserve, "retry": bool(retry_errors),
                         "budget_key": budget_key, "ts": _iso(),
                         "wall_ts": _wall(), "max_s": rem,
                         "elapsed_at_mark": _elapsed(),
                         "cell_at_mark": _spent()}
        if retry_errors:
            retried.append(c.id)
        _sync()
        prov = getattr(model, "target", None)
        if hasattr(prov, "arm_external_deadline"):
            prov.arm_external_deadline(rem)
        t1 = now()
        try:
            out = model.decide(c.state, qs)
            rec = {"answers": out["answers"],
                   "ms": round((now() - t1) * 1000),
                   "cost": out.get("cost"), "model": out.get("model")}
            if "usage" in out:
                rec["usage"] = {k: v for k, v in out["usage"].items()
                                if isinstance(v, (int, float, str, bool,
                                                  type(None)))}
            if "raw" in out:
                rec["raw"] = out["raw"]
        except Exception as e:
            traceback.print_exc()
            rec = {"error": f"{type(e).__name__}: {e}"[:300],
                   "ms": round((now() - t1) * 1000)}
            diag_e = getattr(e, "diag", None)
            if isinstance(diag_e, dict) and diag_e:
                rec["diag"] = diag_e
            printer(f"{run} {phase} {c.id}: ERROR {rec['error'][:100]}",
                    flush=True)
        # conciliación ANTES de cualquier sonda: los intentos reales del
        # caso (incluidos los fallos de transporte) sustituyen a la reserva
        st["requests"] += _attempts(rec) - reserve
        _sync()
        if "error" in rec and "timeout" in rec["error"].lower():
            printer(f"{run} {phase}: timeout; probando /health…",
                    flush=True)
            # el deadline de las sondas queda acotado por AMBOS
            # presupuestos (celda y sesión), recalculados tras el caso
            cell_rem = (cell["budget_s"] - _spent()
                        if cell["budget_s"] is not None else HEALTH_WAIT_S)
            sess_rem = SESSION_CAP_S - _elapsed()
            deadline = now() + max(0.0, min(HEALTH_WAIT_S, cell_rem,
                                            sess_rem))

            def _probe(u, timeout):
                # las sondas de /health también son peticiones: cupo
                # verificado y gasto persistido antes de abrir cada una,
                # con el remanente de AMBOS presupuestos (R18 §2) — el
                # socket recibe ese remanente como timeout
                if st["requests"] >= REQUEST_CAP:
                    raise _BudgetExhausted("peticiones")
                if SESSION_CAP_S - _elapsed() <= 0:
                    raise _BudgetExhausted("sesión")
                if cell["budget_s"] is not None \
                        and cell["budget_s"] - _spent() <= 0:
                    raise _BudgetExhausted("celda")
                st["requests"] += 1
                _sync()
                return health_ok(u, timeout=timeout)
            exhausted = None
            try:
                ok, states = wait_health([_health_url()], deadline,
                                         now=now, sleep=sleep, probe=_probe)
            except _BudgetExhausted as e:
                ok, states, exhausted = False, {}, str(e)
            if not ok:
                if exhausted == "celda" or (
                        exhausted is None
                        and cell["budget_s"] is not None
                        and _spent() >= cell["budget_s"]):
                    ctx["cell_stop"][cell_name] = (
                        f"presupuesto de celda agotado "
                        f"({cell['budget_s'] / 60:.0f} min)")
                elif exhausted == "peticiones" \
                        or st["requests"] >= REQUEST_CAP:
                    ctx["session_stop"] = (
                        f"tope duro de {REQUEST_CAP} peticiones")
                elif exhausted == "sesión" \
                        or SESSION_CAP_S - _elapsed() <= 0:
                    ctx["session_stop"] = "tope de sesión de 10 h"
                else:
                    ctx["session_stop"] = (f"health no responde tras "
                                           f"{HEALTH_WAIT_S} s: {states}")
        # recuento: un reintento sobre un error no lo duplica y un reintento
        # con éxito lo corrige
        prev = doc["cases"].get(c.id)
        if "error" in rec:
            if not (retry_errors and isinstance(prev, dict)
                    and "error" in prev):
                phase_errors += 1
                run_errors += 1
        elif retry_errors and isinstance(prev, dict) and "error" in prev:
            phase_errors -= 1
            run_errors -= 1
        # identidad por caso: cada record lleva su sesión y la puerta que lo
        # autorizó; el meta común nunca relabela casos de otra sesión
        rec["session"] = st["session"]
        if ctx.get("manifest"):
            # el sha del manifiesto que autoriza ESTE caso: en una
            # transición los casos anteriores conservan el suyo
            rec["manifest_sha256"] = ctx["manifest"]
        if ctx["gate_ids"].get(key):
            rec["gate_id"] = ctx["gate_ids"][key]
        # vigilancia por caso (R13 §4): la misma evidencia que exige la
        # puerta — raw, cliente (sha/apéndice/orden) y thinking — más la
        # regla de tokens del primer intento; sin ella el run se invalida
        if "error" not in rec:
            vf = _case_client_fails(combo, f"{phase}/{c.id}", rec, qs,
                                    exp_sha)
            if vf:
                ctx["cell_stop"][cell_name] = (
                    f"{phase}/{c.id}: visibilidad no acreditada ({vf[0]})")
                diag["status"] = "invalid_visibility"
                printer(f"RUN INVALIDO {run}: {ctx['cell_stop'][cell_name]}",
                        flush=True)
            else:
                t = j67._first_prompt_tokens(rec)
                status, detail = token_rule(
                    combo, phase, c.id, t, ctx["hist"],
                    ctx["refs_on"].get(key), ctx["offsets"].get(key))
                if status == "violacion":
                    ctx["cell_stop"][cell_name] = (
                        f"{phase}/{c.id}: visibilidad no acreditada "
                        f"({detail})")
                    diag["status"] = "invalid_visibility"
                    printer(f"RUN INVALIDO {run}: "
                            f"{ctx['cell_stop'][cell_name]}", flush=True)
                elif status == "sin_usage":
                    ctx["no_usage"].setdefault(run, []).append(
                        f"{phase}/{c.id}")
                    printer(f"{run} {phase} {c.id}: sin usage", flush=True)
        doc["cases"][c.id] = rec
        _merge_meta(doc["meta"], _meta_with_expected(model.meta(), exp_sha))
        store.save(run, phase, doc)
        # el caso ya está a salvo: la petición deja de estar pendiente y el
        # estado persiste resultado + contadores
        st["pending"] = None
        _sync()
        if run_errors >= MAX_ERR_RUN:
            ctx["cell_stop"][cell_name] = f"{MAX_ERR_RUN} errores en el run"
    if stopped:
        doc["meta"].setdefault("diag", {})["stopped_cases"] = stopped
        store.save(run, phase, doc)
        printer(f"{run} {phase}: {len(stopped)} casos no ejecutados por "
                "regla de parada", flush=True)
    _sync()


def _cell_gate_ok(ctx, cell):
    """Puerta aprobada y vigente DE ESTA SESIÓN para el combo de la celda.
    Se relee en cada llamada (sin caché): una puerta repetida durante el
    bloque no queda encubierta por un resultado anterior. Los offsets de
    discrete se toman del propio entry (inmutable, ligado al gate_id); el
    barrido de los docs latest queda solo como compatibilidad con puertas
    anteriores a los entries embebidos."""
    key = cell_gate_key(cell)
    latest = _latest_gate(key)
    ok = bool(latest and latest.get("ok")
              and latest.get("session") == ctx["st"]["session"])
    if not ok:
        return False
    combo = cell_combo(cell)
    if _needs_tokenizer_refs(combo):
        # la referencia que autorizó la puerta va archivada en su entry
        # inmutable; si el fichero vigente ya no es ese documento exacto, la
        # puerta deja de valer (R17 §5). El run se vigila contra la
        # referencia autorizada, no contra el fichero mutable.
        toks, _why = _entry_refs(key, latest)
        doc_sha = (latest.get("refs") or {}).get("doc_sha256")
        if toks is None or (doc_sha is not None
                            and _doc_sha(load_refs_doc(key)) != doc_sha):
            return False
        ctx["refs_on"][key] = toks
    else:
        # la referencia histórica de REF_RUN también va archivada en el
        # entry inmutable de la puerta (R18 §1): si el histórico vigente
        # difiere del que autorizó su gate_id, la puerta deja de valer y
        # el ejecutor se niega. La vigilancia corre contra la referencia
        # autorizada, no contra el histórico mutable.
        toks, _why = _entry_refs(key, latest)
        if toks is None:
            return False
        try:
            cur = j67.load_token_ref()
        except SystemExit:
            cur = ctx.get("hist")
        if toks != cur:
            return False
        ctx["hist"] = toks
    ctx["gate_ids"][key] = latest["gate_id"]
    ctx["gate_entries"][key] = latest
    if cell["mode"] == "discrete":
        off = dict(latest.get("offsets") or {})
        if not off:
            for ph in store.runs_in(f"gate_qwen_{key}"):
                doc = store.load(f"gate_qwen_{key}", ph) or {}
                off.update(((doc.get("meta") or {}).get("diag") or {})
                           .get("offsets_familia") or {})
        ctx["offsets"][key] = off
    return True


def _build_ctx(session, cells, model_factory, st=None):
    st = st or _load_state()
    # configuración inválida detectada temprano: cada pregunta nombrada en
    # choice_order debe existir en alguna fase de su celda
    for name, c in cells.items():
        for qid in _dept_orders(c["order"]):
            if not any(qid in load_phase(ph)[0] for ph in c["phases"]):
                raise SystemExit(
                    f"celda {name}: choice_order nombra {qid!r}, ausente en "
                    f"todas sus fases {c['phases']}")
    hist = j67.load_token_ref()
    refs_on = {}
    for c in cells.values():
        combo = cell_combo(c)
        if _needs_tokenizer_refs(combo):
            refs_on[cell_gate_key(c)] = load_refs(cell_gate_key(c))
    models = {name: model_factory(_cell_opts(c)) for name, c in cells.items()}
    exp_sha = {}
    for name, c in cells.items():
        for ph in c["phases"]:
            qs, _ = load_phase(ph)
            exp_sha[(name, ph)] = models[name].expected_system_prompt_sha256(qs)
    return {"st": st, "hist": hist, "refs_on": refs_on, "offsets": {},
            "models": models, "exp_sha": exp_sha, "gate_ids": {},
            "gate_entries": {}, "cell_stop": {}, "session_stop": None,
            "no_usage": {}, "cells": cells, "t0": time.monotonic(),
            "elapsed_base": (st or {}).get("elapsed_s") or 0.0,
            "manifest": None}


def _cell_opts(cell):
    return _combo_opts(cell_combo(cell), seed=cell["seed"])


def _finish_runs(cells, ctx, printer):
    """Estado final por run en el diag de cada fase."""
    for name, cell in cells.items():
        run = cell["run"]
        status = ("invalid_visibility"
                  if "visibilidad" in (ctx["cell_stop"].get(name) or "")
                  else "stopped" if name in ctx["cell_stop"]
                  or ctx["session_stop"] else "complete")
        for ph in store.runs_in(run):
            doc = store.load(run, ph) or {"meta": {}}
            d = doc["meta"].setdefault("diag", {})
            d["status"] = status
            if ctx["no_usage"].get(run):
                d["no_usage_cases"] = ctx["no_usage"][run]
            store.save(run, ph, doc)
        printer(f"{run}: estado={status} errores={_run_errors(run)} "
                f"sin_usage={len(ctx['no_usage'].get(run, []))}")


def run(session=None, resume=False, retry_errors=False, new_session=False,
        dry_run=False, amend_manifest=None, model_factory=None,
        now=time.monotonic, sleep=time.sleep, printer=print):
    """Supervisor del bloque de batería (F0-F3, T0-T1, D0, S202)."""
    if dry_run:
        plan(printer)
        return 0
    if not session:
        printer("ERROR: --session <id> es obligatorio")
        return 1
    try:
        fd = _acquire_lock()
    except FileExistsError:
        printer(f"ERROR: {_lock_path()} existe: otro proceso tiene la sesión")
        return 1
    try:
        st = session_begin(session, new_session)
        # el ejecutor consume el manifiesto que congeló el dry-run (R17 §6):
        # si lo que hay que ejecutar difiere de lo impreso, se rechaza ANTES
        # de abrir peticiones
        man_err, man = _verify_manifest()
        if man_err:
            printer(f"ERROR: {man_err}")
            return 1
        existing = [c["run"] for c in CELLS.values() if store.runs_in(c["run"])]
        if existing and not (resume or retry_errors):
            printer(f"ERROR: ya existen runs {existing}: --resume para "
                    "continuarlos, --retry-errors para el reintento único")
            return 1
        if _pause_requested():
            printer(f"pausa cooperativa: {_pause_path().name} presente; "
                    "salida limpia sin abrir casos (bórralo y --resume)")
            return 2
        # transición de manifiesto autorizada: el manifiesto ANTERIOR
        # archivado se verifica contra la cadena congelada y el vigente
        amendments = []
        if amend_manifest:
            try:
                amendments.append(_resolve_amendment(amend_manifest, man))
            except SystemExit as e:
                printer(f"ERROR: {e}")
                return 1
        factory = model_factory or _llm_factory
        ctx = _build_ctx(session, CELLS, factory, st)
        ctx["t0"] = now()
        ctx["elapsed_base"] = st["elapsed_s"]
        ctx["manifest"] = man["manifest_sha256"]
        ctx["amendments"] = amendments
        _validate_existing(ctx, CELLS, list(CELLS), printer)
        if amendments:
            _merge_amendments(st, amendments)
            _save_state(st)
        for cell_name, phase in _calendar():
            if ctx["session_stop"]:
                break
            cell = CELLS[cell_name]
            if cell_name in ctx["cell_stop"]:
                continue
            if not _cell_gate_ok(ctx, cell):
                ctx["session_stop"] = (
                    f"sin puerta vigente de esta sesión para "
                    f"{cell_gate_key(cell)}: ejecuta `qwen_session gate`")
                break
            _exec_slot(ctx, cell_name, phase, retry_errors, now, sleep,
                       printer)
        _finish_runs(CELLS, ctx, printer)
        st["elapsed_s"] = ctx["elapsed_base"] + (now() - ctx["t0"])
        st["pending"] = None
        _save_state(st)
        if ctx["session_stop"]:
            printer(f"PARADA DE SESIÓN: {ctx['session_stop']}")
            return 2
        for name, why in ctx["cell_stop"].items():
            printer(f"celda {name} detenida: {why}")
        return 0 if not ctx["cell_stop"] else 2
    finally:
        _release_lock(fd)


def diag(session=None, resume=False, retry_errors=False, new_session=False,
         dry_run=False, amend_manifest=None, model_factory=None,
         now=time.monotonic, sleep=time.sleep, printer=print):
    """Diagnósticos P71.2: 9 runs (V1/V3/V5 x r1-r3) sobre los 12 casos."""
    if dry_run:
        plan(printer, diag_only=True)
        return 0
    if not session:
        printer("ERROR: --session <id> es obligatorio")
        return 1
    missing = [(ph, cid) for ph, cid in P712_CASES
               if cid not in {c.id for c in load_phase(ph)[1]}]
    if missing:
        printer(f"ERROR: el manifiesto P71.2 fija casos que ya no existen "
                f"en la batería: {missing} (el manifiesto está congelado: "
                "cualquier ausencia exige una enmienda pre-registrada, "
                "nunca una sustitución silenciosa)")
        return 1
    try:
        fd = _acquire_lock()
    except FileExistsError:
        printer(f"ERROR: {_lock_path()} existe: otro proceso tiene la sesión")
        return 1
    try:
        st = session_begin(session, new_session)
        man_err, man = _verify_manifest()
        if man_err:
            printer(f"ERROR: {man_err}")
            return 1
        cells, order = _diag_cells()
        existing = [c["run"] for c in cells.values() if store.runs_in(c["run"])]
        if existing and not (resume or retry_errors):
            printer(f"ERROR: ya existen runs {existing}: --resume para "
                    "continuarlos, --retry-errors para el reintento único")
            return 1
        if _pause_requested():
            printer(f"pausa cooperativa: {_pause_path().name} presente; "
                    "salida limpia sin abrir casos (bórralo y --resume)")
            return 2
        amendments = []
        if amend_manifest:
            try:
                amendments.append(_resolve_amendment(amend_manifest, man))
            except SystemExit as e:
                printer(f"ERROR: {e}")
                return 1
        factory = model_factory or _llm_factory
        ctx = _build_ctx(session, cells, factory, st)
        ctx["t0"] = now()
        ctx["elapsed_base"] = st["elapsed_s"]
        ctx["manifest"] = man["manifest_sha256"]
        ctx["amendments"] = amendments
        _validate_existing(ctx, cells, order, printer)
        if amendments:
            _merge_amendments(st, amendments)
            _save_state(st)
        for name in order:
            if ctx["session_stop"]:
                break
            cell = cells[name]
            if name in ctx["cell_stop"]:
                continue
            if not _cell_gate_ok(ctx, cell):
                ctx["session_stop"] = (
                    f"sin puerta vigente de esta sesión para "
                    f"{cell_gate_key(cell)}: ejecuta `qwen_session gate`")
                break
            for ph in cell["phases"]:
                _exec_slot(ctx, name, ph, retry_errors, now, sleep, printer)
                if ctx["session_stop"] or name in ctx["cell_stop"]:
                    break
        _finish_runs(cells, ctx, printer)
        st["elapsed_s"] = ctx["elapsed_base"] + (now() - ctx["t0"])
        st["pending"] = None
        _save_state(st)
        if ctx["session_stop"]:
            printer(f"PARADA DE SESIÓN: {ctx['session_stop']}")
            return 2
        return 0 if not ctx["cell_stop"] else 2
    finally:
        _release_lock(fd)


# ------------------------------------------------------------------- dry-run

def _plan_manifest():
    """El manifiesto exacto que consume el ejecutor: combinaciones y sus
    referencias, opciones efectivas de cada celda, calendario con los casos
    de cada slot y los 12 ids de P71.2 con el orden de fases de cada run.
    Es lo que certifica el --dry-run; lleva su propio sha256."""
    combos = {}
    # la referencia histórica también se congela en el manifiesto
    # (R18 §1): valores, procedencia (REF_RUN) y sha256 — si difiere del
    # dry-run, el ejecutor se niega
    try:
        hist = j67.load_token_ref()
    except SystemExit:
        hist = None
    hist_sha = _doc_sha(hist) if hist is not None else None
    for key in combos_needed():
        combo = parse_gate_key(key)
        need = _needs_tokenizer_refs(combo)
        entry = {**combo, "gate": f"gate_qwen_{key}",
                 "token_ref": REF_RUN if not need else _refs_path(key).name}
        if need:
            rp = _refs_path(key)
            entry["refs_present"] = rp.exists()
            entry["refs_sha256"] = (hashlib.sha256(rp.read_bytes())
                                    .hexdigest()[:12] if rp.exists()
                                    else None)
        else:
            entry["token_ref_sha256"] = hist_sha
        combos[key] = entry
    slots = []
    for i, (name, ph) in enumerate(_calendar(), 1):
        cell = CELLS[name]
        qs, cases = load_phase(ph)
        qs_eff = _qs_eff(qs, cell["order"])
        slots.append({"i": i, "cell": name, "run": cell["run"],
                      "phase": ph, "n": len(cases),
                      "case_ids": [c.id for c in cases],
                      "gate": cell_gate_key(cell),
                      "budget_s": cell["budget_s"],
                      "questions_hash": questions_hash(qs_eff),
                      "opts": _cell_opts(cell)})
    dcells, dorder = _diag_cells()
    diags = [{"i": i, "cell": name, "run": dcells[name]["run"],
              "phases": dcells[name]["phases"],
              "case_ids": dcells[name]["case_ids"],
              "gate": cell_gate_key(dcells[name]),
              "budget_s": dcells[name]["budget_s"],
              "budget_key": dcells[name]["budget_key"],
              "opts": _cell_opts(dcells[name])}
             for i, name in enumerate(dorder, 1)]
    man = {"host": dict(HOST), "ref_run": REF_RUN,
           "historical_ref": {"run": REF_RUN,
                              "present": hist is not None,
                              "tokens": hist, "sha256": hist_sha},
           "caps": {"session_s": SESSION_CAP_S, "requests": REQUEST_CAP,
                    "max_err_phase": MAX_ERR_PHASE,
                    "max_err_run": MAX_ERR_RUN,
                    "no_usage_max": NO_USAGE_MAX},
           "calendar_base": list(CALENDAR_BASE), "combos": combos,
           "cells": {n: {"run": c["run"], "issue": c["issue"],
                         "opts": _cell_opts(c), "budget_s": c["budget_s"],
                         "phases": c["phases"]}
                     for n, c in CELLS.items()},
           "slots": slots, "diag": diags,
           "p712_cases": [list(pc) for pc in P712_CASES],
           "canary": {"qid": CANARY_QID, "label": CANARY_LABEL,
                      "min": CANARY_MIN, "diff": CANARY_DIFF,
                      "rol": "observacion_enmienda1"}}
    man["manifest_sha256"] = hashlib.sha256(
        json.dumps(man, sort_keys=True, ensure_ascii=False)
        .encode()).hexdigest()[:16]
    return man


def _manifest_path():
    return store.ROOT / "logs" / "qwen_manifest.json"


def _verify_manifest():
    """Carga el manifiesto que congeló el dry-run y comprueba que el
    ejecutable actual (combinaciones, celdas, calendario, diagnósticos,
    referencias) es exactamente ese — comparando manifest_sha256 contra el
    manifiesto recalculado ahora (R17 §6). Devuelve (error|None, man)."""
    p = _manifest_path()
    if not p.exists():
        return (f"manifiesto del dry-run ausente ({p}): ejecuta antes "
                "`qwen_session run --dry-run` o `diag --dry-run` para "
                "congelarlo", None)
    try:
        frozen = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        return f"manifiesto ilegible ({e})", None
    man = _plan_manifest()
    if frozen.get("manifest_sha256") != man["manifest_sha256"]:
        return (f"el ejecutable actual difiere del manifiesto congelado "
                f"({frozen.get('manifest_sha256')} != "
                f"{man['manifest_sha256']}): repite el dry-run y recongela "
                "antes de ejecutar", None)
    return None, man


# ------------------------------------------------- enmiendas de manifiesto
#
# Transición autorizada old→new (Enmienda 2, qwen38_jev68 §15): los
# resultados guardados con el sha antiguo se aceptan al reanudar solo si
# el diff completo entre el manifiesto anterior archivado y el vigente se
# limita a los campos de la enmienda — `apply(viejo)` debe reproducir el
# manifiesto vigente salvo la propia clave de sha. Cualquier otra
# diferencia (opts, IDs, fases, refs, calendario, puertas) rechaza la
# transición. La comprobación general de hash no se relaja: lo que cambia
# es que el sha guardado puede ser el eslabón anterior de UNA cadena
# autorizada, nunca otro.

def _manifest_content_sha(doc):
    """sha256[:16] del contenido del manifiesto — la misma forma
    canónica que fija `manifest_sha256` (todo el doc salvo esa clave)."""
    return hashlib.sha256(json.dumps(
        {k: v for k, v in doc.items() if k != "manifest_sha256"},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _amend_budget_t0t1(old):
    """Enmienda 2 (qwen38_jev68 §15): budget_s de T0/T1 9000→12600 en
    `cells` y en sus slots. Devuelve el doc transformado, o None si la
    entrada no es el manifiesto esperado."""
    try:
        if (old["cells"]["T0"]["budget_s"] != 9000
                or old["cells"]["T1"]["budget_s"] != 9000):
            return None
        new = json.loads(json.dumps(old))
        new["cells"]["T0"]["budget_s"] = 12600
        new["cells"]["T1"]["budget_s"] = 12600
        for s in new["slots"]:
            if s["cell"] in ("T0", "T1"):
                if s["budget_s"] != 9000:
                    return None
                s["budget_s"] = 12600
        return new
    except (KeyError, TypeError):
        return None


# Cadena autorizada: old_sha -> {new_sha256, motivo, fecha, apply}.
MANIFEST_AMENDMENTS = {
    "428456d0e43b92eb": {
        "new_sha256": "26bbda7c05059d26",
        "motivo": ("Enmienda 2 (qwen38_jev68 §15): presupuesto de T0/T1 "
                   "150→210 min, decidido solo por tiempos (6-oct-2026)"),
        "fecha": "2026-10-06",
        "apply": _amend_budget_t0t1,
    }
}


def _resolve_amendment(path, man):
    """Verifica la transición de manifiesto pedida con --amend-manifest:
    el archivo es el manifiesto ANTERIOR íntegro (su sha propio cuadra),
    su sha es el eslabón viejo de una enmienda congelada cuyo new_sha256
    es el manifiesto vigente `man`, y apply(viejo) == vigente salvo sha —
    el diff se limita a los campos autorizados. Si todo cuadra archiva
    una copia inmutable en results/logs/ y devuelve la entrada de
    procedencia a registrar; si no, SystemExit."""
    p = Path(path)
    try:
        raw = p.read_bytes()
        old = json.loads(raw)
    except (OSError, ValueError) as e:
        raise SystemExit(f"--amend-manifest {p}: manifiesto ilegible ({e})")
    if not isinstance(old, dict):
        raise SystemExit(f"--amend-manifest {p}: no es un manifiesto")
    old_sha = old.get("manifest_sha256")
    if old_sha != _manifest_content_sha(old):
        raise SystemExit(f"--amend-manifest {p}: su manifest_sha256 "
                         "declarado no cuadra con el contenido")
    spec = MANIFEST_AMENDMENTS.get(old_sha)
    if spec is None:
        raise SystemExit(
            f"--amend-manifest {p}: {old_sha} no figura como eslabón "
            "anterior de ninguna enmienda autorizada")
    if man["manifest_sha256"] != spec["new_sha256"]:
        raise SystemExit(
            f"--amend-manifest: el manifiesto vigente "
            f"{man['manifest_sha256']} no es el declarado por la enmienda "
            f"({spec['new_sha256']})")
    patched = spec["apply"](old)
    strip = lambda d: {k: v for k, v in d.items()
                       if k != "manifest_sha256"}
    if not isinstance(patched, dict) or strip(patched) != strip(man):
        raise SystemExit(
            "--amend-manifest: el diff entre el manifiesto anterior y el "
            "vigente excede los campos de la enmienda "
            f"({spec['motivo']})")
    dst = store.ROOT / "logs" / f"qwen_manifest_{old_sha}.json"
    if dst.exists():
        if dst.read_bytes() != raw:
            raise SystemExit(f"{dst}: ya existe un manifiesto anterior "
                             "distinto con ese nombre")
    else:
        dst.write_bytes(raw)
    return {"old_sha256": old_sha, "new_sha256": spec["new_sha256"],
            "motivo": spec["motivo"], "fecha": spec["fecha"],
            "manifiesto_anterior": dst.name,
            "manifiesto_anterior_sha256":
                hashlib.sha256(raw).hexdigest()[:12],
            "aplicada": _iso()}


def _amendment_key(am):
    """Identidad estable del eslabón de enmienda (old→new + sha del
    manifiesto anterior archivado): dos aplicaciones de la misma
    transición difieren solo en `aplicada` y son el MISMO eslabón —
    deduplicar conserva la primera `aplicada`; las reanudaciones
    posteriores se registran como eventos aparte, no como eslabones."""
    return (am.get("old_sha256"), am.get("new_sha256"),
            am.get("manifiesto_anterior_sha256"))


def _amendment_resume(am):
    """Evento de reanudación con una enmienda ya registrada: no es un
    eslabón nuevo de la cadena, solo la marca temporal de la aplicación
    repetida."""
    return {"old_sha256": am.get("old_sha256"),
            "new_sha256": am.get("new_sha256"),
            "aplicada": am.get("aplicada")}


def _merge_amendments(store_dict, amendments):
    """Fusiona las enmiendas verificadas de esta ejecución en un
    contenedor persistente (estado de sesión o meta.diag de un doc):
    `manifest_amendments` = cadena de eslabones deduplicada por
    identidad estable (se conserva la primera `aplicada`);
    `manifest_amendment_resumes` = eventos de las reanudaciones
    posteriores con la misma enmienda. Sin nada que añadir no crea
    claves."""
    chain = list(store_dict.get("manifest_amendments") or [])
    keys = {_amendment_key(a) for a in chain}
    resumes = None
    for am in amendments:
        k = _amendment_key(am)
        if k in keys:
            if resumes is None:
                resumes = list(
                    store_dict.get("manifest_amendment_resumes") or [])
            resumes.append(_amendment_resume(am))
        else:
            chain.append(am)
            keys.add(k)
    if chain:
        store_dict["manifest_amendments"] = chain
    if resumes:
        store_dict["manifest_amendment_resumes"] = resumes


def _amendment_to(ctx, old_sha):
    """La enmienda ya verificada que enlaza `old_sha` con el manifiesto
    vigente de ctx, o None si no hay transición autorizada."""
    for am in ctx.get("amendments") or []:
        if am.get("old_sha256") == old_sha \
                and am.get("new_sha256") == ctx.get("manifest"):
            return am
    return None


def _manifest_allowed(diag):
    """(allowed, origin, error): los shas de manifiesto que autorizan
    casos en un doc — el vigente (manifest_sha256) más la cadena de
    enmiendas registrada, cada eslabón verificado contra la tabla
    congelada old→new. `origin` es el sha bajo el que quedaron los casos
    sin marca propia (el primero de la cadena). (None, None, None) si el
    doc no registra procedencia de manifiesto."""
    cur = diag.get("manifest_sha256")
    ams = diag.get("manifest_amendments") or []
    if cur is None and not ams:
        return None, None, None
    allowed = {cur} if cur else set()
    prev = cur
    for am in reversed(ams):
        if not isinstance(am, dict) or not am.get("old_sha256") \
                or am.get("new_sha256") != prev:
            return None, None, "cadena de enmiendas de manifiesto rota"
        spec = MANIFEST_AMENDMENTS.get(am["old_sha256"])
        if spec is None or spec.get("new_sha256") != am["new_sha256"]:
            return None, None, (
                "enmienda de manifiesto no autorizada "
                f"{am.get('old_sha256')}→{am.get('new_sha256')}")
        allowed.add(am["old_sha256"])
        prev = am["old_sha256"]
    return allowed, prev, None


def plan(printer=print, diag_only=False):
    """Imprime y exporta el manifiesto congelado que ejecuta el runner:
    puertas por combinación con su referencia, opciones efectivas completas
    por celda, calendario intercalado con casos por slot, los ids exactos de
    P71.2 y el manifiesto JSON íntegro — todo lo que se congela queda
    impreso. El ejecutor verifica `manifest_sha256` antes de abrir
    peticiones (`_verify_manifest`)."""
    man = _plan_manifest()
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(man, ensure_ascii=False, indent=1,
                               sort_keys=True) + "\n")
    printer("# plan congelado de la sesión Qwen3.8-27B FP8 (R13 §4-§6)")
    printer(f"# manifest_sha256={man['manifest_sha256']}  "
            f"host={HOST['base_url']}  model={HOST['model']}  "
            f"ref_run={REF_RUN}")
    printer(f"# manifiesto exportado a {path} — run/diag lo cargan y "
            "verifican su hash antes de abrir peticiones")
    hr = man["historical_ref"]
    printer(f"# referencia histórica {REF_RUN}: "
            + (f"sha256={hr['sha256']} "
               f"({sum(len(v) for v in hr['tokens'].values())} casos; "
               "congelada también en la evidencia de cada puerta)"
               if hr["present"]
               else "AUSENTE: sin referencia histórica de tokens"))
    printer("# 1) combinaciones mode×prompt×thinking×orden: puerta propia al"
            " inicio de la sesión y tras cualquier reinicio; las marcadas "
            "necesitan `refs` ANTES de la puerta:")
    for key, c in man["combos"].items():
        printer(f"#   {key}: mode={c['mode']} prompt={c['prompt']} "
                f"thinking={c['thinking']} order={c['order']} "
                f"token_ref={c['token_ref']}"
                + (f" refs_sha256={c.get('refs_sha256')}"
                   if c.get("token_ref") != REF_RUN
                   else f" hist_sha256={c.get('token_ref_sha256')}"))
        if c["token_ref"] != REF_RUN:
            estado = (f"presente sha={c['refs_sha256']}"
                      if c["refs_present"] else "AUSENTE: ejecutar refs")
            printer(f"python3 -m jevbench.qwen_session refs {key} "
                    "--tokenizer <checkpoint-qwen3.8-27b-fp8>   "
                    f"# {c['token_ref']} {estado}")
        printer(f"python3 -m jevbench.qwen_session gate {key} --session <S>")
    if not diag_only:
        printer("# 2) celdas: opciones efectivas completas (lo que recibe "
                "el adaptador, sin valores por omisión implícitos):")
        for name, c in man["cells"].items():
            printer(f"#   {name:4s} {c['run']} issue={c['issue']} "
                    f"tope={c['budget_s'] // 60}min fases={c['phases']}")
            printer(f"#     {json.dumps(c['opts'], sort_keys=True)}")
        printer("# 3) bloque de batería (calendario intercalado por fase; "
                f"base={man['calendar_base']}):")
        printer("python3 -m jevbench.qwen_session run --session <S>")
        for s in man["slots"]:
            printer(f"  slot {s['i']:03d} {s['cell']:4s} {s['run']:45s} "
                    f"{s['phase']:14s} n={s['n']} puerta={s['gate']} "
                    f"tope={s['budget_s'] // 60}min "
                    f"qhash={s['questions_hash']}")
            printer(f"         casos={s['case_ids']}")
    printer("# 4) diagnósticos P71.2 (calendario propio, tope compartido "
            f"{DIAG_BUDGET_S // 60} min; orden de fases e ids exactos por "
            "run):")
    printer("python3 -m jevbench.qwen_session diag --session <S>")
    for d in man["diag"]:
        printer(f"  diag {d['i']} {d['run']:46s} prompt="
                f"{d['opts']['prompt']} seed="
                f"{json.loads(d['opts']['extra_body'])['seed']} "
                f"puerta={d['gate']} tope={d['budget_s'] // 60}min")
        printer(f"         fases={d['phases']}")
        printer(f"         casos={d['case_ids']}")
        printer(f"         opts={json.dumps(d['opts'], sort_keys=True)}")
    printer(f"# P71.2 manifiesto: {[tuple(pc) for pc in man['p712_cases']]}")
    printer(f"# canario (observación, Enmienda 1 — no bloqueante): "
            f"{json.dumps(man['canary'], sort_keys=True)}")
    printer(f"# topes: sesión {SESSION_CAP_S // 3600} h; {REQUEST_CAP} "
            f"peticiones duras; {MAX_ERR_PHASE} errores/fase; "
            f"{MAX_ERR_RUN} errores/run; reintento único por caso; "
            f"no_usage_max={NO_USAGE_MAX}")
    printer("# manifiesto íntegro congelado (lo que verifica el ejecutor):")
    printer(json.dumps(man, ensure_ascii=False, sort_keys=True, indent=1))


# ------------------------------------------------------------------ análisis

def _case_scores(run, phase):
    """{cid: puntos medios del caso} de los casos sin error."""
    doc = store.load(run, phase) or {}
    qs, cases = load_phase(phase)
    recs = doc.get("cases") or {}
    out = {}
    for c in cases:
        rec = recs.get(c.id)
        if not isinstance(rec, dict) or "error" in rec or "answers" not in rec:
            continue
        preds = {q: metrics.normalize(rec["answers"][q], qs[q]) for q in qs}
        out[c.id] = sum(metrics.point(qs[q], preds[q], c.gt[q])
                        for q in qs) / len(qs)
    return out


def _papers_pmid():
    try:
        data = json.loads((DATA / "papers32.json").read_text())
    except FileNotFoundError:
        return {}
    return {p["pid"]: p.get("pmid") or p["pid"] for p in data}


def _clusters(phases):
    """{cluster: [(phase, cid)]}: las traducciones ES/EN comparten id entre
    fases y los papers con el mismo PMID quedan ligados (duplicados
    conocidos)."""
    pmid = _papers_pmid()
    clusters = {}
    for ph in phases:
        _, cases = load_phase(ph)
        for c in cases:
            key = (f"pmid:{pmid[c.id]}" if ph == "papers32"
                   and c.id in pmid else c.id)
            clusters.setdefault(key, []).append((ph, c.id))
    return clusters


def _paired_setup(runs):
    """Fases completas en TODOS los runs con baseline<100, scores por caso y
    unidades de remuestreo agrupadas por cluster."""
    phases, per = [], {}
    for ph in score.ADJ_PHASES:
        b = score.baseline(ph)["pct"]
        if b >= 100:
            continue
        sc = [_case_scores(r, ph) for r in runs]
        _, cases = load_phase(ph)
        if any(len(s) < len(cases) for s in sc):
            continue
        per[ph] = sc
        phases.append((ph, b))
    if not phases:
        return None
    pmap = {ph: i for i, (ph, _) in enumerate(phases)}
    units = []
    for members in _clusters([ph for ph, _ in phases]).values():
        u = [(pmap[ph], cid) for ph, cid in members
             if ph in pmap and cid in per[ph][0]]
        if u:
            units.append(u)
    return phases, per, units


def _pct(reps, level):
    reps = sorted(reps)
    a = (1 - level) / 2
    return reps[int(len(reps) * a)], reps[int(len(reps) * (1 - a)) - 1]


def paired_delta(run_a, run_b, iters=BOOT_ITERS, seed=BOOT_SEED, level=0.975):
    """Δ ajustado pareado (B−A) con bootstrap de clusters (traducciones y
    papers por PMID ligados), percentil del `level` dado, semilla fija.
    None si no hay fases pareadas completas."""
    setup = _paired_setup([run_a, run_b])
    if setup is None:
        return None
    phases, per, units = setup
    n_ph = len(phases)

    def adj(which, draw=None):
        if draw is None:
            vals = [(100 * sum(per[ph][which].values())
                     / len(per[ph][which]) - b) / (100 - b)
                    for ph, b in phases]
            return 100 * sum(vals) / len(vals)
        s = [0.0] * n_ph
        n = [0] * n_ph
        for u in draw:
            for pi, cid in u:
                s[pi] += per[phases[pi][0]][which][cid]
                n[pi] += 1
        if 0 in n:
            return None
        return 100 * sum((100 * s[i] / n[i] - phases[i][1])
                         / (100 - phases[i][1]) for i in range(n_ph)) / n_ph

    delta = adj(1) - adj(0)
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units))
        va, vb = adj(0, draw), adj(1, draw)
        if va is not None and vb is not None:
            reps.append(vb - va)
    if not reps:
        return None
    lo, hi = _pct(reps, level)
    return {"delta": delta, "lo": lo, "hi": hi, "reps": len(reps),
            "adj_a": adj(0), "adj_b": adj(1),
            "phases": [ph for ph, _ in phases]}


def range_boot(runs, iters=BOOT_ITERS, seed=BOOT_SEED, level=0.95):
    """Bootstrap conjunto del rango del ajustado entre `runs` (mismos draws
    en todos) y de la media de los ajustados."""
    setup = _paired_setup(list(runs))
    if setup is None:
        return None
    phases, per, units = setup
    k, n_ph = len(runs), len(phases)

    def adj(w, draw=None):
        if draw is None:
            vals = [(100 * sum(per[ph][w].values())
                     / len(per[ph][w]) - b) / (100 - b)
                    for ph, b in phases]
            return 100 * sum(vals) / len(vals)
        s = [0.0] * n_ph
        n = [0] * n_ph
        for u in draw:
            for pi, cid in u:
                s[pi] += per[phases[pi][0]][w][cid]
                n[pi] += 1
        if 0 in n:
            return None
        return 100 * sum((100 * s[i] / n[i] - phases[i][1])
                         / (100 - phases[i][1]) for i in range(n_ph)) / n_ph

    obs = [adj(w) for w in range(k)]
    rng = random.Random(seed)
    r_range, r_mean = [], []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units))
        vals = [adj(w, draw) for w in range(k)]
        if any(v is None for v in vals):
            continue
        r_range.append(max(vals) - min(vals))
        r_mean.append(sum(vals) / k)
    if not r_range:
        return None
    rlo, rhi = _pct(r_range, level)
    mlo, mhi = _pct(r_mean, level)
    return {"range": max(obs) - min(obs), "lo": rlo, "hi": rhi,
            "mean": sum(obs) / k, "mean_lo": mlo, "mean_hi": mhi,
            "adj": obs, "reps": len(r_range),
            "phases": [ph for ph, _ in phases]}


def primacy_subset():
    """[(phase, cid)] prefijados por regla: el texto menciona EBUS/
    broncoscopia y GT department != bronchoscopia (R13 §5/P72)."""
    out = []
    for ph in PHASES_ALL:
        qs, cases = load_phase(ph)
        if "department" not in qs:
            continue
        for c in cases:
            if c.gt.get("department") == "bronchoscopia":
                continue
            if PRIMACY_RE.search(c.state or ""):
                out.append((ph, c.id))
    return out


def primacy_sha(subset):
    return hashlib.sha256(
        json.dumps(sorted(subset)).encode()).hexdigest()[:12]


def _dept_hits(run):
    """{(phase, cid): acierto department} de los casos sin error."""
    out = {}
    for ph in PHASES_ALL:
        qs, cases = load_phase(ph)
        if "department" not in qs:
            continue
        doc = store.load(run, ph) or {}
        recs = doc.get("cases") or {}
        for c in cases:
            rec = recs.get(c.id)
            if not isinstance(rec, dict) or "error" in rec:
                continue
            dec = _decisions(rec, qs).get("department")
            out[(ph, c.id)] = (dec == c.gt["department"])
    return out


def _es_subset(pairs):
    """Una versión por caso traducido, con la convención ES fijada en R13 §5
    (las fases adv* solo existen en un idioma), deduplicado por id."""
    out, seen = [], set()
    for ph, cid in pairs:
        if not (ph.endswith("_es") or ph.startswith("adv")):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        out.append((ph, cid))
    return out


def primacy_analysis(runs_by_order, iters=BOOT_ITERS, seed=BOOT_SEED,
                     level=0.95):
    """Primacía de department (R13 §5/P72): error con bronchoscopia primera
    (d0) menos error con bronchoscopia última (d1), en pp; bootstrap por
    clusters sobre el subconjunto; McNemar con una versión por traducción
    (ES); familia Holm de 7 contrastes (6 pares sobre todos los casos +
    primacía)."""
    orders = sorted(runs_by_order)
    hits = {o: _dept_hits(runs_by_order[o]) for o in orders}
    subset = primacy_subset()
    pair = [pc for pc in subset
            if pc in hits["d0"] and pc in hits["d1"]]
    err = {o: [0 if hits[o][pc] else 1 for pc in pair] for o in orders}
    delta = 100 * (sum(err["d0"]) - sum(err["d1"])) / len(pair) if pair else None
    # bootstrap por clusters (es/en comparten id)
    units = {}
    for pc in pair:
        units.setdefault(pc[1], []).append(pc)
    units = list(units.values())
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units))
        d0 = d1 = n = 0
        for u in draw:
            for pc in u:
                d0 += 0 if hits["d0"][pc] else 1
                d1 += 0 if hits["d1"][pc] else 1
                n += 1
        if n:
            reps.append(100 * (d0 - d1) / n)
    lo = hi = None
    if reps:
        lo, hi = _pct(reps, level)
    # McNemar (primacía y los seis pares de órdenes): una versión por caso
    # traducido, convención ES prefijada — las traducciones ES/EN no son
    # réplicas independientes (R13 §5). El bootstrap del agregado sí mantiene
    # las dos traducciones agrupadas por cluster.
    es = _es_subset(pair)
    b_, c_, p_prim = metrics.mcnemar([hits["d0"][pc] for pc in es],
                                   [hits["d1"][pc] for pc in es])
    # familia de 7: los seis pares de órdenes sobre todos los casos + primacía
    pvals, labels = [], []
    for i, o1 in enumerate(orders):
        for o2 in orders[i + 1:]:
            common = _es_subset([pc for pc in hits[o1] if pc in hits[o2]])
            _, _, p = metrics.mcnemar([hits[o1][pc] for pc in common],
                                    [hits[o2][pc] for pc in common])
            pvals.append(p)
            labels.append(f"{o1}vs{o2} todos")
    pvals.append(p_prim)
    labels.append("primacía")
    adj = j67.holm(pvals)
    return {"subset": subset, "subset_sha": primacy_sha(subset),
            "n_paired": len(pair), "delta_pp": delta, "lo": lo, "hi": hi,
            "errors": {o: sum(err[o]) for o in orders},
            "error_ids": {o: [f"{pc[0]}/{pc[1]}"
                              for pc, e in zip(pair, err[o]) if e]
                          for o in orders},
            "mcnemar_primacy": {"b": b_, "c": c_, "p": p_prim, "n": len(es)},
            "holm": sorted(zip(labels, pvals, adj), key=lambda x: x[2]),
            "p_holm_primacy": adj[-1]}


def s202_agreement(run_f0, run_s202):
    """Acuerdo de decisiones S202<->F0 con IC de Clopper-Pearson (95 %)."""
    return j67.agreement(run_f0, run_s202)


def _diag_case_score(run, ph, cid):
    doc = store.load(run, ph) or {}
    rec = (doc.get("cases") or {}).get(cid)
    if not isinstance(rec, dict) or "error" in rec or "answers" not in rec:
        return None
    qs, cases = load_phase(ph)
    case = next((c for c in cases if c.id == cid), None)
    if case is None:
        return None
    preds = {q: metrics.normalize(rec["answers"][q], qs[q]) for q in qs}
    return sum(metrics.point(qs[q], preds[q], case.gt[q])
               for q in qs) / len(qs)


def p712_cases():
    """El manifiesto fijo de P71.2 resuelto contra la batería actual."""
    out = []
    missing = []
    for ph, cid in P712_CASES:
        _, cases = load_phase(ph)
        by_id = {c.id: c for c in cases}
        if cid not in by_id:
            missing.append(f"{ph}/{cid}")
        else:
            out.append((ph, by_id[cid]))
    if missing:
        raise SystemExit(f"P71.2: casos del manifiesto ausentes en la "
                         f"batería: {missing}")
    return out


def _diag_rec(run, ph, cid):
    doc = store.load(run, ph) or {}
    rec = (doc.get("cases") or {}).get(cid)
    return rec if isinstance(rec, dict) else None


def p712_analysis(iters=BOOT_ITERS, seed=BOOT_SEED, level=0.975):
    """Δ de acierto diagnóstico por caso de V3/V5 frente a V1 (R13 §5):
    puntos oficiales por pregunta, media dentro del caso, emparejado por
    semilla y bootstrap sobre los casos del manifiesto. El mismo protocolo
    de incertidumbre declarado que el resto del análisis (iters=BOOT_ITERS).
    `complete` es False si falta cualquier caso×semilla×variante: el
    bootstrap no descarta pares en silencio, la cobertura válida se hace
    explícita y la clasificación queda NO EVALUABLE."""
    pcs = p712_cases()
    sc = {}
    recs = {}
    for rep in (1, 2, 3):
        for v in DIAG_VARIANTS:
            run = diag_run(v, rep)
            for ph, case in pcs:
                rec = _diag_rec(run, ph, case.id)
                recs[(v, rep, ph, case.id)] = rec
                s = _diag_case_score(run, ph, case.id)
                if s is not None:
                    sc[(v, rep, ph, case.id)] = s
    out = {"n_cases": len(pcs), "reps": {}, "cases": {}, "delta": {}}
    out["complete"] = all(
        (v, r, ph, case.id) in sc
        for v in DIAG_VARIANTS for r in (1, 2, 3) for ph, case in pcs)
    for v in ("v3", "v5"):
        deltas = []
        for ph, case in pcs:
            d = [sc[(v, r, ph, case.id)] - sc[("v1", r, ph, case.id)]
                 for r in (1, 2, 3)
                 if (v, r, ph, case.id) in sc and ("v1", r, ph, case.id) in sc]
            deltas.append(100 * sum(d) / len(d) if d else None)
        out["delta"][v] = deltas
    # baseline mayoritaria sobre esos mismos casos (por fase del manifiesto)
    bscores = []
    for ph in sorted({p for p, _ in pcs}):
        qs, _ = load_phase(ph)
        sub = [c for p, c in pcs if p == ph]
        base = metrics.majority_baseline(qs, sub)
        for c in sub:
            bscores.append(sum(metrics.point(
                qs[q], ({"label": base[q]["answer"]}
                        if qs[q]["type"] == "choice"
                        else {"value": float(base[q]["answer"])}),
                c.gt[q]) for q in qs) / len(qs))
    out["baseline"] = 100 * sum(bscores) / len(bscores)
    for v in DIAG_VARIANTS:
        vals = []
        for ph, case in pcs:
            s = [sc[(v, r, ph, case.id)] for r in (1, 2, 3)
                 if (v, r, ph, case.id) in sc]
            vals.append(100 * sum(s) / len(s) if s else None)
        out["cases"][v] = vals
    out["mean_v1"] = (sum(x for x in out["cases"]["v1"] if x is not None)
                      / max(1, sum(x is not None for x in out["cases"]["v1"])))
    # diagnósticos secundarios exigidos por R13 §5: cambios de etiqueta
    # respecto a V1 (misma semilla), raw ausente/errores de formato, Brier y
    # detecciones adversariales por caso — reportarlos, no solo almacenarlos
    decs = {}
    for (v, r, ph, cid), rec in recs.items():
        if isinstance(rec, dict) and "error" not in rec and "answers" in rec:
            qs, _ = load_phase(ph)
            decs[(v, r, ph, cid)] = _decisions(rec, qs)
    sec = {}
    for v in DIAG_VARIANTS:
        n_err = n_noraw = 0
        briers, det, changes = [], {}, {}
        for ph, case in pcs:
            qs, _ = load_phase(ph)
            for r in (1, 2, 3):
                rec = recs[(v, r, ph, case.id)]
                if not isinstance(rec, dict) or "error" in rec:
                    n_err += 1
                    continue
                if j67._first_attempt(rec) is None:
                    n_noraw += 1
                if all(q in (rec.get("answers") or {}) for q in qs):
                    preds = {q: metrics.normalize(rec["answers"][q], qs[q])
                             for q in qs}
                    per_q, _ = metrics.calibration(qs, {case.id: preds},
                                                   [case])
                    briers += [b["brier"] for b in per_q.values()]
                if ph.startswith("adv") or ph == "ood":
                    det.setdefault(f"{ph}/{case.id}", {})[f"{v}r{r}"] = \
                        decs.get((v, r, ph, case.id))
                if v != "v1":
                    dv = decs.get((v, r, ph, case.id))
                    d1 = decs.get(("v1", r, ph, case.id))
                    if dv and d1:
                        changes.setdefault(f"{ph}/{case.id}", []).append(
                            sum(1 for q in dv if dv[q] != d1.get(q)))
        sec[v] = {"errors": n_err, "sin_raw": n_noraw,
                  "brier": (sum(briers) / len(briers)) if briers else None,
                  "label_changes_vs_v1": {
                      k: round(sum(x) / len(x), 3)
                      for k, x in changes.items()},
                  "detections": det}
    out["secondary"] = sec
    rng = random.Random(seed)
    for v in ("v3", "v5"):
        ds = [d for d in out["delta"][v] if d is not None]
        if len(ds) < 2:
            out.setdefault("boot", {})[v] = None
            continue
        reps = []
        for _ in range(iters):
            reps.append(sum(ds[rng.randrange(len(ds))]
                            for _ in range(len(ds))) / len(ds))
        lo, hi = _pct(reps, level)
        out.setdefault("boot", {})[v] = {"delta": sum(ds) / len(ds),
                                         "lo": lo, "hi": hi}
    return out


def holm_cells(run_a, run_b):
    """Las 53 celdas fase×pregunta con McNemar crudo y corrección de Holm,
    reportadas aparte (R13 §5)."""
    rows = []
    for ph in PHASES_ALL:
        qs, cases = load_phase(ph)
        da = store.load(run_a, ph) or {}
        db = store.load(run_b, ph) or {}
        ra, rb = da.get("cases") or {}, db.get("cases") or {}
        for qid, q in qs.items():
            ha, hb = [], []
            for c in cases:
                x, y = ra.get(c.id), rb.get(c.id)
                if not isinstance(x, dict) or not isinstance(y, dict) \
                        or "error" in x or "error" in y:
                    continue
                pa = metrics.normalize(x["answers"][qid], q)
                pb = metrics.normalize(y["answers"][qid], q)
                ha.append(metrics.exact(q, pa, c.gt[qid]))
                hb.append(metrics.exact(q, pb, c.gt[qid]))
            b_, c_, p = metrics.mcnemar(ha, hb)
            rows.append({"cell": f"{ph}.{qid}", "b": b_, "c": c_,
                         "p": p, "n": len(ha)})
    for r, a in zip(rows, j67.holm([r["p"] for r in rows])):
        r["p_holm"] = a
    return rows


# ------------------------------------------------- salidas descriptivas §8
# Requeridas por el pre-registro (§8, hallazgo R28 §2): son descriptivas,
# no cambian clasificaciones ni la política de normalización del scorer.

def _raw_scan(run, phases, mode, case_ids=None):
    """Vectores crudos nulos/formato del `raw` guardado, ANTES de la
    normalización del adaptador: clase de cada respuesta por caso×pregunta
    (ok/zero/uniform/invalid en probabilities; ok/invalid en discrete —
    misma validación que diag65_report), intentos sin respuesta parseable y
    casos sin raw capturado. Las listas llevan IDs explícitos
    `fase/caso.pregunta`: «cero nulos» se demuestra con la lista vacía, y
    `sin_raw` deja constancia de la cobertura — raw ausente no cuenta como
    cero nulos."""
    validate = (_validate_raw_discrete if mode == "discrete"
                else _validate_raw_value)
    out = {"run": run, "n_casos": 0, "intentos": 0, "ok": 0,
           "nulos": [], "uniformes": [], "invalidos": [],
           "sin_respuesta": [], "sin_raw": [], "sin_registro": []}
    for ph in phases:
        qs, cases = load_phase(ph)
        doc = store.load(run, ph) or {}
        recs = doc.get("cases") or {}
        ids = (case_ids or {}).get(ph)
        for c in cases:
            if ids is not None and c.id not in set(ids):
                continue
            out["n_casos"] += 1
            rec = recs.get(c.id)
            if not isinstance(rec, dict) or "error" in rec:
                out["sin_registro"].append(f"{ph}/{c.id}")
                continue
            if j67._first_attempt(rec) is None:
                out["sin_raw"].append(f"{ph}/{c.id}")
                continue
            for i, (_fin, answers) in enumerate(_raw_answers(rec)):
                out["intentos"] += 1
                if answers is None:
                    out["sin_respuesta"].append(f"{ph}/{c.id}#{i + 1}")
                    continue
                for qid, val in answers.items():
                    kind, _ = validate(qs, qid, val)
                    tag = f"{ph}/{c.id}.{qid}"
                    if kind == "zero":
                        out["nulos"].append(tag)
                    elif kind == "uniform":
                        out["uniformes"].append(tag)
                    elif kind == "ok":
                        out["ok"] += 1
                    else:
                        out["invalidos"].append(tag)
    return out


def _usage_stats(run, phases, case_ids=None):
    """Latencia y tokens por celda a partir de los registros: media y
    mediana de `ms` por caso y tokens del `usage` del servidor en cada
    intento del raw (prompt/completion/razonamiento). `coste_api` es 0 por
    ejecución local sin facturación — tiempo y tokens son uso del servidor,
    nunca un «coste total» (el tiempo contabilizado de sesión tampoco mide
    consumo energético ni horas GPU)."""
    ms, n = [], 0
    pt = ct = rt = 0
    for ph in phases:
        _, cases = load_phase(ph)
        doc = store.load(run, ph) or {}
        recs = doc.get("cases") or {}
        ids = (case_ids or {}).get(ph)
        for c in cases:
            if ids is not None and c.id not in set(ids):
                continue
            rec = recs.get(c.id)
            if not isinstance(rec, dict) or "error" in rec:
                continue
            n += 1
            if rec.get("ms") is not None:
                ms.append(rec["ms"])
            raw = rec.get("raw") or (rec.get("diag") or {}).get("raw") or []
            for att in raw:
                u = (att.get("llm_response") or {}).get("usage") or {}
                pt += u.get("prompt_tokens") or 0
                ct += u.get("completion_tokens") or 0
                det = u.get("completion_tokens_details") or {}
                rt += u.get("reasoning_tokens") \
                    or det.get("reasoning_tokens") or 0
    return {"run": run, "n": n,
            "ms_media": (sum(ms) / len(ms)) if ms else None,
            "ms_mediana": statistics.median(ms) if ms else None,
            "ms_total": sum(ms), "prompt_tokens": pt,
            "completion_tokens": ct, "razonamiento_tokens": rt,
            "coste_api": 0}


def _rule_preds(q, a):
    """Predicciones por regla de decisión sobre la respuesta normalizada
    de una pregunta: noul → 'prob>=0.5' (la prob cruda umbralizada); score
    → 'score' (valor declarado, E[x]) y 'argmax' (moda del vector);
    choice → 'choice' (etiqueta declarada) y 'argmax'. En discrete el
    `noul`/`score`/`choice` normalizados son el literal emitido."""
    t, probs = q["type"], a.get("probabilities")
    out = {}
    if t == "noul":
        if a.get("noul") is not None:
            out["prob>=0.5"] = {"value": float(a["noul"])}
    elif t == "score":
        if a.get("score") is not None:
            out["score"] = {"value": float(a["score"])}
        if probs:
            out["argmax"] = {"value": float(max(probs, key=probs.get))}
    elif t == "choice":
        if a.get("choice") is not None:
            out["choice"] = {"label": a["choice"]}
        if probs:
            out["argmax"] = {"label": max(probs, key=probs.get)}
    return out


def _p711_breakdown(run_f0, run_d0):
    """Desglose por pregunta del contraste P71.1 (§8: same_day, urgency y
    department con prob cruda/umbral 0.5 y score/argmax por separado):
    aciertos estrictos y puntos oficiales de F0 y D0 sobre los casos donde
    la pregunta existe y ambos runs tienen registro válido."""
    acc = {}
    for ph in PHASES_ALL:
        qs, cases = load_phase(ph)
        qids = [q for q in ("same_day", "urgency", "department") if q in qs]
        if not qids:
            continue
        da = (store.load(run_f0, ph) or {}).get("cases") or {}
        db = (store.load(run_d0, ph) or {}).get("cases") or {}
        for c in cases:
            ra, rb = da.get(c.id), db.get(c.id)
            if not isinstance(ra, dict) or not isinstance(rb, dict) \
                    or "error" in ra or "error" in rb:
                continue
            for qid in qids:
                q, gt = qs[qid], c.gt[qid]
                e = acc.setdefault(qid, {"tipo": q["type"], "n": 0,
                                         "F0": {}, "D0": {}})
                e["n"] += 1
                for cell_name, rec in (("F0", ra), ("D0", rb)):
                    a = (rec.get("answers") or {}).get(qid)
                    if not isinstance(a, dict):
                        continue
                    if q["type"] == "noul" and a.get("noul") is not None:
                        e.setdefault(f"prob_media_{cell_name}",
                                     []).append(float(a["noul"]))
                    for rule, pred in _rule_preds(q, a).items():
                        d = e[cell_name].setdefault(
                            rule, {"aciertos": 0, "puntos": 0.0, "n": 0})
                        d["n"] += 1
                        p = metrics.point(q, pred, gt)
                        d["puntos"] += p
                        d["aciertos"] += int(p == 1.0)
    for e in acc.values():
        for k in ("prob_media_F0", "prob_media_D0"):
            if k in e:
                e[k] = sum(e[k]) / len(e[k])
    return acc


def _baseline_table(used=None):
    """Baselines de mayoría por fase sobre el GT vigente (oráculo ajustado
    sobre el propio set): pct, n y respuesta mayoritaria por pregunta.
    `baseline_saturada` marca la exclusión de ood del agregado;
    `usada_en_agregado`, si se pasa la lista de fases del contraste."""
    out = {}
    for ph in PHASES_ALL:
        b = score.baseline(ph)
        out[ph] = {"n": b["n"], "pct": b["pct"],
                   "baseline_saturada": b["pct"] >= 100,
                   "usada_en_agregado": (None if used is None
                                       else ph in used),
                   "mayoria": {q: {"respuesta": a, "puntos": b["per_q"][q]}
                               for q, a in b["answers"].items()}}
    return out


def _audit_cell(name, cell):
    """Evaluabilidad y auditoría del run de una celda: cobertura completa
    (los errores no son casos válidos), evidencia por caso (raw + cliente +
    thinking + regla de tokens) y la puerta que autorizó cada caso
    (rec.gate_id resuelto contra la evidencia inmutable de su sesión). Sin
    evidencia no hay visibilidad acreditada: la celda es NO EVALUABLE, nunca
    un éxito por omisión."""
    run = cell["run"]
    combo = cell_combo(cell)
    key = cell_gate_key(cell)
    rep = {"run": run, "errors": {}, "no_usage": [], "no_raw": [],
           "client_violations": [], "token_violations": [], "gate_bad": [],
           "manifest_bad": [], "missing": [], "n_ok": 0, "n": 0,
           "status": None}
    try:
        hist = j67.load_token_ref()
    except SystemExit as e:
        rep["evaluable"] = False
        rep["note"] = f"sin referencia histórica de tokens ({e})"
        return rep
    ref_on = load_refs(key) if _needs_tokenizer_refs(combo) else None
    needs_refs = _needs_tokenizer_refs(combo)
    offsets_doc, gate_cache = {}, {}
    for ph in cell["phases"]:
        doc = store.load(run, ph)
        qs, cases = load_phase(ph)
        ids = (cell.get("case_ids") or {}).get(ph)
        todo = [c for c in cases if ids is None or c.id in set(ids)]
        rep["n"] += len(todo)
        if doc is None:
            rep["missing"] += [f"{ph}/{c.id}" for c in todo]
            continue
        meta = doc.get("meta") or {}
        diag = meta.get("diag") or {}
        rep["status"] = diag.get("status") or rep["status"]
        offsets_doc.update(diag.get("offsets_familia") or {})
        exp_sha = meta.get("system_prompt_sha256")
        # cadena de manifiesto del doc: cada eslabón registrado debe ser
        # una enmienda autorizada old→new; un doc sin procedencia de
        # manifiesto (anterior a esta marca) no exige sha por caso
        allowed_sha, origin_sha, m_err = _manifest_allowed(diag)
        if m_err:
            rep["manifest_bad"].append(f"{ph}: {m_err}")
        for c in todo:
            rec = (doc.get("cases") or {}).get(c.id)
            tag = f"{ph}/{c.id}"
            if rec is None:
                rep["missing"].append(tag)
                continue
            if "error" in rec:
                kind = ("timeout" if "timeout" in rec["error"].lower()
                        else "other")
                rep["errors"][kind] = rep["errors"].get(kind, 0) + 1
                # un caso con error no es cobertura válida: cuenta como
                # evidencia ausente, no como caso descartado en silencio
                rep["missing"].append(f"{tag} (error)")
                continue
            rep["n_ok"] += 1
            gid = rec.get("gate_id")
            if gid not in gate_cache:
                gate_cache[gid] = _gate_entry_for(key, gid)
            ge = gate_cache[gid]
            gate_bad = not (gid and ge and ge.get("ok")
                            and ge.get("session") == rec.get("session"))
            # la regla de tokens corre contra la referencia y los offsets
            # que autorizó LA puerta de este caso (archivados en su entry
            # inmutable), nunca contra el fichero/meta/histórico mutable
            # actual (R17 §5, R18 §1): si cambiaron después del gate, el
            # caso queda invalidado
            rec_ref, rec_off, rec_hist = ref_on, None, hist
            if needs_refs:
                rec_ref, _why = _entry_refs(key, ge)
                if rec_ref is None:
                    gate_bad = True
                    rec_ref = ref_on
            else:
                rec_hist, _why = _entry_refs(key, ge)
                if rec_hist is None:
                    gate_bad = True
                    rec_hist = hist
            if combo["mode"] == "discrete":
                rec_off = (ge or {}).get("offsets") or offsets_doc
            if gate_bad:
                rep["gate_bad"].append(tag)
            # el sha que autorizó el caso: el suyo propio o, si se
            # escribió antes de la marca por caso, el eslabón inicial de
            # la cadena del doc — cualquier otro hash no autoriza
            if allowed_sha is not None and rec.get(
                    "manifest_sha256", origin_sha) not in allowed_sha:
                rep["manifest_bad"].append(tag)
            rep["client_violations"] += _case_client_fails(
                combo, tag, rec, qs, exp_sha)
            if j67._first_attempt(rec) is None:
                rep["no_raw"].append(tag)
                continue
            t = j67._first_prompt_tokens(rec)
            st, det = token_rule(combo, ph, c.id, t, rec_hist, rec_ref,
                                 rec_off)
            if st == "sin_usage":
                rep["no_usage"].append(tag)
            elif st == "violacion":
                rep["token_violations"].append(f"{tag} {det}")
    n = rep["n"]
    no_eval = None
    if rep["token_violations"]:
        no_eval = f"{len(rep['token_violations'])} violaciones de tokens"
    elif rep["client_violations"]:
        no_eval = (f"{len(rep['client_violations'])} violaciones de "
                   "cliente/thinking")
    elif rep["missing"]:
        no_eval = f"{len(rep['missing'])} casos sin ejecutar o con error"
    elif rep["gate_bad"]:
        no_eval = f"{len(rep['gate_bad'])} casos sin puerta válida"
    elif rep["manifest_bad"]:
        no_eval = (f"{len(rep['manifest_bad'])} casos/fases bajo "
                   "manifiesto no autorizado")
    elif n and len(rep["no_usage"]) / n > NO_USAGE_MAX:
        no_eval = f"{len(rep['no_usage'])}/{n} casos sin usage"
    elif rep["status"] == "invalid_visibility":
        no_eval = "status invalid_visibility"
    rep["evaluable"] = no_eval is None
    rep["note"] = no_eval
    return rep


def _cls(cond_ok, cond_bad):
    return "CONFIRMADA" if cond_ok else ("REFUTADA" if cond_bad
                                         else "INCONCLUSA")


def _no_eval(note):
    return f"NO EVALUABLE ({note})"


def analyze(out_json=None, iters=BOOT_ITERS, seed=BOOT_SEED, printer=print):
    """Análisis pre-registrado R13 §5 sobre los runs presentes en results/."""
    rep = {"runs": {}, "classification": {}, "holm53": {}}
    have = {k: c for k, c in CELLS.items() if store.runs_in(c["run"])}
    for name, cell in have.items():
        aud = _audit_cell(name, cell)
        aud["adjusted"], _ = score.adjusted(cell["run"])
        rep["runs"][name] = aud
        printer(f"{name} {aud['run']}: ajustado "
                f"{aud['adjusted'] and round(aud['adjusted'], 2)}, "
                f"n_ok {aud['n_ok']}/{aud['n']}, "
                f"evaluable={aud['evaluable']} {aud['note'] or ''}")
    ev = lambda n: rep["runs"].get(n, {}).get("evaluable")
    cls = rep["classification"]
    # ---- P68: thinking a dos órdenes (IC 97.5 % por contraste)
    if ev("F0") and ev("T0"):
        rep["d0"] = paired_delta(CELLS["F0"]["run"], CELLS["T0"]["run"],
                                 iters=iters, seed=seed, level=0.975)
    if ev("F1") and ev("T1"):
        rep["d1"] = paired_delta(CELLS["F1"]["run"], CELLS["T1"]["run"],
                                 iters=iters, seed=seed, level=0.975)
    d0, d1 = rep.get("d0"), rep.get("d1")
    if d0 and d1:
        cls["P68 thinking >=+5 en ambos órdenes"] = _cls(
            d0["lo"] >= 5 and d1["lo"] >= 5,
            d0["hi"] < 5 or d1["hi"] < 5) + (
            f" (Δ0={d0['delta']:+.1f} [{d0['lo']:+.1f},{d0['hi']:+.1f}], "
            f"Δ1={d1['delta']:+.1f} [{d1['lo']:+.1f},{d1['hi']:+.1f}], "
            f"Δ1−Δ0={d1['delta'] - d0['delta']:+.1f})")
    else:
        cls["P68 thinking >=+5 en ambos órdenes"] = _no_eval(
            "faltan runs evaluables F0/T0/F1/T1")
    # ---- P72 estabilidad de rango d0-d3 (IC 95 %)
    if all(ev(n) for n in ("F0", "F1", "F2", "F3")):
        rb = range_boot([CELLS[n]["run"] for n in ("F0", "F1", "F2", "F3")],
                        iters=iters, seed=seed, level=0.95)
        rep["range"] = rb
        if rb:
            cls["P72 rango d0-d3 <=5"] = _cls(
                rb["hi"] <= 5, rb["lo"] > 5) + (
                f" (rango={rb['range']:.1f} [{rb['lo']:.1f},{rb['hi']:.1f}], "
                f"media={rb['mean']:.1f} [{rb['mean_lo']:.1f},"
                f"{rb['mean_hi']:.1f}])")
    else:
        cls["P72 rango d0-d3 <=5"] = _no_eval("faltan F0-F3 evaluables")
    # ---- P72 primacía
    if all(ev(n) for n in ("F0", "F1", "F2", "F3")):
        pa = primacy_analysis({o: CELLS[n]["run"] for o, n in
                               (("d0", "F0"), ("d1", "F1"), ("d2", "F2"),
                                ("d3", "F3"))},
                              iters=iters, seed=seed)
        rep["primacy"] = pa
        d, lo, hi = pa["delta_pp"], pa["lo"], pa["hi"]
        sig = pa["p_holm_primacy"] < 0.05
        if d is None or lo is None:
            cls["P72 primacía >=5pp"] = _no_eval("sin pares en el subconjunto")
        else:
            cls["P72 primacía >=5pp"] = _cls(
                d >= 5 and lo > 0 and sig, hi < 5) + (
                f" (Δ={d:+.1f}pp [{lo:+.1f},{hi:+.1f}], "
                f"n={pa['n_paired']}, sha={pa['subset_sha']}, "
                f"Holm p={pa['p_holm_primacy']:.4f})")
    else:
        cls["P72 primacía >=5pp"] = _no_eval("faltan F0-F3")
    # ---- P71.1 discrete vs F0 (umbral 10, IC 95 %)
    if ev("F0") and ev("D0"):
        dd = paired_delta(CELLS["F0"]["run"], CELLS["D0"]["run"],
                          iters=iters, seed=seed, level=0.95)
        rep["disc"] = dd
        if dd:
            cls["P71.1 discrete >=+10 sobre F0"] = _cls(
                dd["lo"] >= 10, dd["hi"] < 10) + (
                f" (Δ={dd['delta']:+.1f} [{dd['lo']:+.1f},{dd['hi']:+.1f}])")
    else:
        cls["P71.1 discrete >=+10 sobre F0"] = _no_eval("faltan F0/D0")
    # ---- S202 suelo de ruido (L95>=97 % confirma): exige AMBOS runs
    # evaluables — existir en disco no acredita nada
    if ev("F0") and ev("S202"):
        k, n, p, lo, hi = s202_agreement(CELLS["F0"]["run"],
                                         CELLS["S202"]["run"])
        rep["s202"] = {"k": k, "n": n, "p": p, "lo": lo, "hi": hi}
        cls["S202 acuerdo >=97%"] = _cls(lo >= 0.97, hi < 0.97) + (
            f" ({k}/{n} p={p:.3f} IC95 [{lo:.3f},{hi:.3f}])")
    else:
        cls["S202 acuerdo >=97%"] = _no_eval("faltan F0/S202 evaluables")
    # ---- P71.2 diagnósticos: los nueve runs deben existir Y ser
    # evaluables (gates, raw, tokens, cobertura completa de los 12 casos)
    dcells, dorder = _diag_cells()
    dauds = {nm: _audit_cell(nm, dcells[nm]) for nm in dorder
             if store.runs_in(dcells[nm]["run"])}
    rep["diag_audit"] = dauds
    diag_evaluable = (len(dauds) == len(dorder)
                      and all(a["evaluable"] for a in dauds.values()))
    if not diag_evaluable:
        det = "; ".join(f"{nm}:{a['note']}" for nm, a in dauds.items()
                        if not a["evaluable"])
        cls["P71.2 frases visibles >=10pp"] = _no_eval(
            f"runs diag incompletos o no evaluables ({det or 'faltan'})")
    else:
        try:
            pa = p712_analysis(iters=iters, seed=seed)
        except SystemExit as e:
            cls["P71.2 frases visibles >=10pp"] = _no_eval(str(e))
        else:
            rep["p712"] = pa
            for v in ("v3", "v5"):
                b = (pa.get("boot") or {}).get(v)
                if not pa.get("complete"):
                    cls[f"P71.2 {v.upper()} >=10pp"] = _no_eval(
                        "cobertura incompleta: faltan casos o semillas del "
                        "manifiesto")
                elif b is None:
                    cls[f"P71.2 {v.upper()} >=10pp"] = _no_eval(
                        "sin pares por semilla")
                else:
                    cls[f"P71.2 {v.upper()} >=10pp"] = _cls(
                        b["lo"] >= 10, b["hi"] < 10) + (
                        f" (Δ={b['delta']:+.1f}pp "
                        f"[{b['lo']:+.1f},{b['hi']:+.1f}])")
    # ---- Holm 53 celdas, aparte
    for a, b in (("F0", "T0"), ("F1", "T1"), ("F0", "D0")):
        if store.runs_in(CELLS[a]["run"]) and store.runs_in(CELLS[b]["run"]):
            rep["holm53"][f"{a}_vs_{b}"] = holm_cells(CELLS[a]["run"],
                                                     CELLS[b]["run"])
    # ---- salidas descriptivas exigidas por el pre-registro (§8, hallazgo
    # R28 §2): se calculan sobre todo run presente en disco, evaluable o
    # no; ninguna cambia clasificaciones ni la política del scorer
    desc, scan, lat = {}, {}, {}
    for name, cell in have.items():
        scan[name] = _raw_scan(cell["run"], cell["phases"], cell["mode"],
                               cell.get("case_ids"))
        lat[name] = _usage_stats(cell["run"], cell["phases"],
                                 cell.get("case_ids"))
    for nm in dorder:
        dc = dcells[nm]
        if store.runs_in(dc["run"]):
            scan[nm] = _raw_scan(dc["run"], dc["phases"], dc["mode"],
                                 dc.get("case_ids"))
            lat[nm] = _usage_stats(dc["run"], dc["phases"],
                                   dc.get("case_ids"))
    desc["vectores_crudos"] = scan
    desc["latencia_tokens"] = lat
    onoff = {}
    for tag, off, on in (("d0", "F0", "T0"), ("d1", "F1", "T1")):
        a, b = lat.get(off), lat.get(on)
        if a and b:
            onoff[tag] = {
                "off": off, "on": on,
                "ms_media_off": a["ms_media"], "ms_media_on": b["ms_media"],
                "ms_mediana_off": a["ms_mediana"],
                "ms_mediana_on": b["ms_mediana"],
                "ms_ratio": (b["ms_media"] / a["ms_media"]
                             if a["ms_media"] else None),
                "prompt_off": a["prompt_tokens"],
                "prompt_on": b["prompt_tokens"],
                "completion_off": a["completion_tokens"],
                "completion_on": b["completion_tokens"],
                "completion_delta": (b["completion_tokens"]
                                     - a["completion_tokens"]),
                "razonamiento_on": b["razonamiento_tokens"]}
    if onoff:
        desc["p68_on_off"] = onoff
    if store.runs_in(CELLS["F0"]["run"]) and store.runs_in(
            CELLS["D0"]["run"]):
        desc["p711_por_pregunta"] = _p711_breakdown(CELLS["F0"]["run"],
                                                    CELLS["D0"]["run"])
    agg_phases = (rep.get("d0") or rep.get("range") or {}).get("phases")
    desc["baselines"] = _baseline_table(agg_phases)
    rep["descriptivos"] = desc
    printer("\n## Clasificación pre-registrada (R13 §5)")
    for k, v in cls.items():
        printer(f"- {k}: {v}")
    if rep["holm53"]:
        printer("\n## Holm 53 celdas (aparte, descriptivo)")
        for pair, rows in rep["holm53"].items():
            sig = [r for r in rows if r["p_holm"] < 0.05]
            printer(f"- {pair}: {len(sig)} celdas significativas tras Holm "
                    f"de {len(rows)}")
            for r in sig:
                printer(f"    {r['cell']}: b={r['b']} c={r['c']} "
                        f"p={r['p']:.4g} Holm={r['p_holm']:.4g}")
    # ---- impresión de las salidas descriptivas (§8)
    def _fmt_ids(v):
        return f"{len(v)} [{', '.join(v)}]" if v else "0"
    printer("\n## Vectores crudos nulos/formato (del raw, antes de "
            "normalizar; la política oficial del scorer no cambia)")
    for name, s in scan.items():
        printer(f"- {name} ({s['run']}): ok={s['ok']}, "
                f"nulos={_fmt_ids(s['nulos'])}, "
                f"uniformes={_fmt_ids(s['uniformes'])}, "
                f"invalidos={_fmt_ids(s['invalidos'])}, "
                f"sin_respuesta={_fmt_ids(s['sin_respuesta'])}, "
                f"sin_raw={_fmt_ids(s['sin_raw'])}, "
                f"sin_registro={_fmt_ids(s['sin_registro'])} "
                f"(casos={s['n_casos']}, intentos={s['intentos']})")
    printer("\n## Latencia y tokens por celda (coste API = 0: ejecución "
            "local sin facturación — ms y tokens son uso del servidor, "
            "no «coste total»)")
    printer("| celda | n | ms media | ms mediana | tokens prompt | "
            "tokens completion | tokens razonamiento |")
    printer("|---|---:|---:|---:|---:|---:|---:|")
    for name, s in lat.items():
        printer(f"| {name} | {s['n']} | {score.fmt(s['ms_media'], 0)} | "
                f"{score.fmt(s['ms_mediana'], 0)} | {s['prompt_tokens']} | "
                f"{s['completion_tokens']} | {s['razonamiento_tokens']} |")
    for tag, o in onoff.items():
        printer(f"- P68 on/off {tag} ({o['on']} vs {o['off']}): "
                f"ms media {score.fmt(o['ms_media_off'], 0)} → "
                f"{score.fmt(o['ms_media_on'], 0)}"
                + (f" (×{o['ms_ratio']:.2f})" if o["ms_ratio"] else "")
                + f", mediana {score.fmt(o['ms_mediana_off'], 0)} → "
                f"{score.fmt(o['ms_mediana_on'], 0)}; "
                f"completion {o['completion_off']} → {o['completion_on']} "
                f"(Δ {o['completion_delta']:+d}; razonamiento on = "
                f"{o['razonamiento_on']}), prompt {o['prompt_off']} → "
                f"{o['prompt_on']}")
    if desc.get("p711_por_pregunta"):
        printer("\n## P71.1 — desglose por pregunta (F0 prob vs D0 "
                "discrete; aciertos estrictos y puntos oficiales por "
                "regla de decisión)")
        for qid, e in desc["p711_por_pregunta"].items():
            parts = []
            for cell_name in ("F0", "D0"):
                for rule, d in (e.get(cell_name) or {}).items():
                    parts.append(f"{cell_name} {rule}: {d['aciertos']}/"
                                 f"{d['n']} ({d['puntos']:g} ptos)")
            extra = (f"; prob media F0={e['prob_media_F0']:.3f}"
                     if "prob_media_F0" in e else "")
            printer(f"- {qid} ({e['tipo']}, n={e['n']}): "
                    + " | ".join(parts) + extra)
    printer("\n## Baselines de mayoría por fase (GT v4; ood excluida del "
            "agregado por baseline saturada)")
    printer("| fase | n | mayoría % | respuestas mayoritarias |")
    printer("|---|---:|---:|---|")
    for ph, b in desc["baselines"].items():
        ans = ", ".join(f"{q}={v['respuesta']}"
                        for q, v in b["mayoria"].items())
        printer(f"| {ph} | {b['n']} | {score.fmt(b['pct'])} | {ans} |")
    if rep.get("primacy"):
        pa = rep["primacy"]
        errs = pa.get("errors") or {}
        printer("\n## P72 primacía — detalle sobre el subconjunto "
                f"congelado (sha {pa['subset_sha']}, {pa['n_paired']} "
                "registros pareados)")
        printer("- errores `department` por orden: "
                + ", ".join(f"{o}={errs.get(o)}"
                            for o in ("d0", "d1", "d2", "d3")))
        printer("- IDs del subconjunto: "
                + ", ".join(f"{p}/{c}" for p, c in pa["subset"]))
        for o in ("d0", "d1", "d2", "d3"):
            ids = (pa.get("error_ids") or {}).get(o) or []
            printer(f"- errores {o} ({len(ids)}): {', '.join(ids)}")
    if out_json:
        with open(out_json, "w") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    return rep


# ---------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refs", help="referencia de tokens vía tokenizer local")
    r.add_argument("combo")
    r.add_argument("--tokenizer", required=True,
                   help="ruta del checkpoint (AutoTokenizer)")
    r.add_argument("--out", default=None)
    g = sub.add_parser(
        "gate", help="puerta de visibilidad de una combinación "
                     "(canario: observación, Enmienda 1)")
    g.add_argument("combo")
    g.add_argument("--session", required=True)
    g.add_argument("--new-session", action="store_true",
                   help="tras un reinicio del servidor: nueva sesión y puertas")
    rn = sub.add_parser(
        "run", help="bloque de batería (calendario intercalado; pausa "
                    "cooperativa: crear results/logs/qwen_session.pause "
                    "termina el run limpio tras el caso en curso)")
    rn.add_argument("--session", required=False)
    rn.add_argument("--resume", action="store_true")
    rn.add_argument("--retry-errors", action="store_true")
    rn.add_argument("--new-session", action="store_true")
    rn.add_argument("--dry-run", action="store_true")
    rn.add_argument("--amend-manifest", default=None, metavar="JSON",
                    help="manifiesto ANTERIOR archivado: autoriza al "
                         "reanudar la transición congelada old→new solo "
                         "si el diff se limita a los campos de la "
                         "enmienda (Enmienda 2: budget_s T0/T1 "
                         "9000→12600); los casos ya guardados conservan "
                         "su sha")
    dg = sub.add_parser(
        "diag", help="diagnósticos P71.2 (misma pausa cooperativa y "
                     "transición de manifiesto que run)")
    dg.add_argument("--session", required=False)
    dg.add_argument("--resume", action="store_true")
    dg.add_argument("--retry-errors", action="store_true")
    dg.add_argument("--new-session", action="store_true")
    dg.add_argument("--dry-run", action="store_true")
    dg.add_argument("--amend-manifest", default=None, metavar="JSON",
                    help="igual que en run: manifiesto anterior "
                         "archivado para la transición autorizada")
    an = sub.add_parser("analyze", help="análisis pre-registrado")
    an.add_argument("--json", default=None)
    an.add_argument("--iters", type=int, default=BOOT_ITERS)
    args = ap.parse_args()
    if args.cmd == "refs":
        build_refs(args.combo, _load_tokenizer(args.tokenizer),
                   out=Path(args.out) if args.out else None)
        return 0
    if args.cmd == "gate":
        ok, _ = gate(args.combo, session=args.session,
                     new_session=args.new_session)
        return 0 if ok else 1
    if args.cmd == "run":
        return run(session=args.session, resume=args.resume,
                   retry_errors=args.retry_errors,
                   new_session=args.new_session, dry_run=args.dry_run,
                   amend_manifest=args.amend_manifest)
    if args.cmd == "diag":
        return diag(session=args.session, resume=args.resume,
                    retry_errors=args.retry_errors,
                    new_session=args.new_session, dry_run=args.dry_run,
                    amend_manifest=args.amend_manifest)
    if args.cmd == "analyze":
        analyze(out_json=args.json, iters=args.iters)
        return 0


if __name__ == "__main__":
    sys.exit(main())
