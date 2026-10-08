"""Supervisor de las sesiones Qwen3.8-27B FP8 (SGLang en .81): JEV-68, JEV-71
§1–2 y JEV-72 §2 (perfil `jev68`, pre-registro R13 §4–§6 congelado antes de
ejecutar) y el factorial discrete × thinking de JEV-76 (perfil `jev76`:
ocho celdas frescas d0+d1 con estado, manifiesto, puertas, referencias y
nombres de run propios — la sesión de JEV-68 no se reanuda ni se toca).
El operador arranca el servidor y abre el túnel 18001; este módulo solo
gestiona puertas, calendario, topes y análisis. Todos los subcomandos
aceptan `--profile jev68|jev76` (por defecto `jev68`).

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
      topes por celda, tope de sesión del perfil (10 h en jev68, ~14 h
      en jev76) y tope duro acumulado de 5000
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
      Pausa cooperativa: si existe el fichero de pausa del perfil
      (results/logs/qwen_session.pause en jev68) el
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
from .adapters.jev import PROVIDERS as _JEV_PROVIDERS
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
    # thinking=None: familia sin modo thinking configurable (Gemma en
    # JEV-77 §3.4): la petición no declara enable_thinking en absoluto
    if thinking is None:
        return json.dumps({"temperature": 0, "seed": seed})
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


# ------------------------------------------------- perfil JEV-76 (factorial)
#
# Factorial discrete × thinking, alcance (b) decidido por el usuario en
# JEV-76 (comentario del 7-oct-2026, diseño revisado en R30): OCHO celdas
# frescas d0+d1 ejecutadas e intercaladas en una sesión NUEVA — F0′/T0′/D0′
# son controles repetidos adrede en la misma sesión (los runs de JEV-68/71
# quedan solo como referencia descriptiva) y D1/DT0/DT1 son celdas nuevas.
# Mismos topes por celda que JEV-68 tras su Enmienda 2 (off 90 min,
# on 210 min); tope de sesión ~14 h y el mismo tope duro de peticiones.
# Estado, manifiesto, pausa, referencias tokenizer y directorios de
# puerta son PROPIOS del perfil: la sesión JEV-68 (qwen_session.json,
# qwen_manifest*.json, gate_qwen_*) queda intacta; solo se comparte el
# lock (un solo escritor sobre el mismo servidor) y la referencia
# histórica de tokens off de REF_RUN.
CELLS_76 = {
    "F0p": {"run": "llm_qwen38_27b_fp8_jev76_off_d0_prob", "issue": "JEV-76",
            "mode": "probabilities", "thinking": False, "order": "d0",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "T0p": {"run": "llm_qwen38_27b_fp8_jev76_on_d0_prob", "issue": "JEV-76",
            "mode": "probabilities", "thinking": True, "order": "d0",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
    "D0p": {"run": "llm_qwen38_27b_fp8_jev76_off_d0_disc", "issue": "JEV-76",
            "mode": "discrete", "thinking": False, "order": "d0",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "DT0": {"run": "llm_qwen38_27b_fp8_jev76_on_d0_disc", "issue": "JEV-76",
            "mode": "discrete", "thinking": True, "order": "d0",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
    "F1p": {"run": "llm_qwen38_27b_fp8_jev76_off_d1_prob", "issue": "JEV-76",
            "mode": "probabilities", "thinking": False, "order": "d1",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "T1p": {"run": "llm_qwen38_27b_fp8_jev76_on_d1_prob", "issue": "JEV-76",
            "mode": "probabilities", "thinking": True, "order": "d1",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
    "D1":  {"run": "llm_qwen38_27b_fp8_jev76_off_d1_disc", "issue": "JEV-76",
            "mode": "discrete", "thinking": False, "order": "d1",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 90 * 60},
    "DT1": {"run": "llm_qwen38_27b_fp8_jev76_on_d1_disc", "issue": "JEV-76",
            "mode": "discrete", "thinking": True, "order": "d1",
            "seed": 101, "phases": PHASES_ALL, "budget_s": 210 * 60},
}

# Rotación por fase del factorial: alterna orden (d0/d1), modo y thinking
# para repartir la deriva temporal entre las ocho celdas (88 slots).
CALENDAR_76 = ["F0p", "DT1", "D0p", "T1p", "F1p", "DT0", "D1", "T0p"]

# --------------------------------------------------------------- JEV-77
# MedGemma/Gemma/Qwen en .80 (medgemma_jev77.md): 18 celdas sobre 5
# checkpoints, un modelo cargado a la vez, calendario por BLOQUES de
# checkpoint con rotación por fase (§8.3-8.4). thinking=None en la
# familia Gemma = sin flag configurable (§3.4: el razonamiento emergente
# solo se registra); en Qwen es False = enable_thinking=false declarado
# Y observado.
#
# Congelado A4 (medgemma_jev77.md §A3/A4, evidencia a3_smoke.jsonl):
# `served` = nombre servido en /v1/models de la rama A; `args` = argv
# efectivo del servidor (Gemma: rama A común con
# --disable-prefill-cuda-graph — sin él el warmup falla; Qwen: los de
# qwen38_jev76/server_identity.json con el peso montado en
# /mnt/ai-models de .80); `max_tokens` = tope de generación (≥60× el
# output máximo observado en A3: 123 tokens); `a01_margin` = margen del
# control negativo ciego, medido por TOKENIZACIÓN (render visible−ciego
# de adv1/A01, nunca por aciertos) menos 64 tokens de holgura — la
# familia Gemma comparte plantilla/tokenizer idénticos (sha
# 7de1c58e208eda46).
_GEMMA77_ARGS_TAIL = ["--dtype", "bfloat16", "--grammar-backend",
                      "xgrammar", "--mem-fraction-static", "0.70",
                      "--context-length", "32768",
                      "--max-running-requests", "1",
                      "--trust-remote-code", "--disable-prefill-cuda-graph",
                      "--constrained-json-disable-any-whitespace"]
CKPTS_77 = {
    "medgemma27b": {"checkpoint": "google/medgemma-27b-it",
                    "sha": "2d3e00ea38b50018bf5dd3aa1009457cd2d5a48f",
                    "served": "medgemma-27b-it", "thinking": None,
                    "max_tokens": "8192", "a01_margin": 304,
                    "args": ["--model-path",
                             "/mnt/ai-models/hf/google/medgemma-27b-it",
                             "--served-model-name", "medgemma-27b-it"]
                            + _GEMMA77_ARGS_TAIL},
    "gemma3_27b": {"checkpoint": "google/gemma-3-27b-it",
                   "sha": "005ad3404e59d6023443cb575daa05336842228a",
                   "served": "gemma-3-27b-it", "thinking": None,
                   "max_tokens": "8192", "a01_margin": 304,
                   "args": ["--model-path",
                            "/mnt/ai-models/hf/google/gemma-3-27b-it",
                            "--served-model-name", "gemma-3-27b-it"]
                           + _GEMMA77_ARGS_TAIL},
    "qwen38fp8": {"checkpoint": "Qwen/Qwen3.8-27B-FP8",
                  "sha": "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a",
                  "served": "qwen3.8-27b-sglang", "thinking": False,
                  "max_tokens": "16384", "a01_margin": 292,
                  "args": ["--model-path", "Qwen/Qwen3.8-27B-FP8",
                           "--served-model-name", "qwen3.8-27b-sglang",
                           "--trust-remote-code", "--mem-fraction-static",
                           "0.95", "--sleep-on-idle",
                           "--attention-backend", "flashinfer",
                           "--chunked-prefill-size", "8192",
                           "--disable-prefill-cuda-graph",
                           "--kv-cache-dtype", "fp8_e4m3",
                           "--mamba-ssm-dtype", "bfloat16",
                           "--mamba-full-memory-ratio", "4.21",
                           "--mamba-radix-cache-strategy",
                           "extra_buffer_lazy",
                           "--max-mamba-cache-size", "40",
                           "--max-running-requests", "10",
                           "--context-length", "262144",
                           "--speculative-algorithm", "EAGLE",
                           "--speculative-num-steps", "3",
                           "--speculative-eagle-topk", "1",
                           "--speculative-num-draft-tokens", "4",
                           "--reasoning-parser", "qwen3",
                           "--tool-call-parser", "qwen3_coder",
                           "--sampling-defaults", "model",
                           "--enable-metrics", "--enable-cache-report",
                           "--host", "0.0.0.0", "--port", "8000",
                           "--model-path",
                           "/mnt/ai-models/hf/Qwen/Qwen3.8-27B-FP8",
                           "--constrained-json-disable-any-whitespace"]},
    "medgemma4b": {"checkpoint": "google/medgemma-1.5-4b-it",
                   "sha": "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
                   "served": "medgemma-1.5-4b-it", "thinking": None,
                   "max_tokens": "8192", "a01_margin": 304,
                   "args": ["--model-path",
                            "/mnt/ai-models/hf/google/medgemma-1.5-4b-it",
                            "--served-model-name", "medgemma-1.5-4b-it"]
                           + _GEMMA77_ARGS_TAIL},
    "gemma3_4b": {"checkpoint": "google/gemma-3-4b-it",
                  "sha": "093f9f388b31de276ce2de164bdc2081324b9767",
                  "served": "gemma-3-4b-it", "thinking": None,
                  "max_tokens": "8192", "a01_margin": 304,
                  "args": ["--model-path",
                           "/mnt/ai-models/hf/google/gemma-3-4b-it",
                           "--served-model-name", "gemma-3-4b-it"]
                          + _GEMMA77_ARGS_TAIL},
}


def _cell77(run, mode, order, ckpt, budget_s):
    return {"run": run, "issue": "JEV-77", "mode": mode, "order": order,
            "seed": 101, "phases": PHASES_ALL, "budget_s": budget_s,
            "ckpt": ckpt, "thinking": CKPTS_77[ckpt]["thinking"]}


# Topes por celda calibrados por LATENCIA A3 (nunca por aciertos):
# regla común M/G y d0/d1 — tope ≥ 194 × peor latencia A3 del modo con
# ≥30 % de holgura, y en probabilities además cobertura de los prompts
# largos de papers32 (hasta 6.693 tokens en las refs, por encima del
# máximo 2.196 que midió el smoke A3): 27B prob 150 min (peor A3 34,4 s
# → 111 min; 150 = +34,9 %), 27B disc 45 min (8,4 s → ~27 min), Qwen
# disc 90 min (12 s/caso → ~39 min), 4B prob/disc 45 min (9,4 s →
# ~30 min). Suma = 22 h ≤ 40 h del encargo (medgemma_jev77.md §A3/A4).
CELLS_77 = {
    # bloque MedGemma 27B (puertas 1-4): M-D0 = candidato H1/H2 y entrada
    # de la cascada
    "MD0": _cell77("llm_medgemma_27b_it_bf16_jev77_d0_disc",
                   "discrete", "d0", "medgemma27b", 45 * 60),
    "MP0": _cell77("llm_medgemma_27b_it_bf16_jev77_d0_prob",
                   "probabilities", "d0", "medgemma27b", 150 * 60),
    "MD1": _cell77("llm_medgemma_27b_it_bf16_jev77_d1_disc",
                   "discrete", "d1", "medgemma27b", 45 * 60),
    "MP1": _cell77("llm_medgemma_27b_it_bf16_jev77_d1_prob",
                   "probabilities", "d1", "medgemma27b", 150 * 60),
    # bloque Gemma 3 27B (puertas 5-8): control de H1
    "GD0": _cell77("llm_gemma3_27b_it_bf16_jev77_d0_disc",
                   "discrete", "d0", "gemma3_27b", 45 * 60),
    "GP0": _cell77("llm_gemma3_27b_it_bf16_jev77_d0_prob",
                   "probabilities", "d0", "gemma3_27b", 150 * 60),
    "GD1": _cell77("llm_gemma3_27b_it_bf16_jev77_d1_disc",
                   "discrete", "d1", "gemma3_27b", 45 * 60),
    "GP1": _cell77("llm_gemma3_27b_it_bf16_jev77_d1_prob",
                   "probabilities", "d1", "gemma3_27b", 150 * 60),
    # bloque Qwen FP8 (puertas 9-10): control de H2, thinking off
    "QD0p": _cell77("llm_qwen38_27b_fp8_jev77_d0_disc",
                    "discrete", "d0", "qwen38fp8", 90 * 60),
    "QD1p": _cell77("llm_qwen38_27b_fp8_jev77_d1_disc",
                    "discrete", "d1", "qwen38fp8", 90 * 60),
    # bloque MedGemma 1.5 4B (puertas 11-14)
    "M4D0": _cell77("llm_medgemma_1_5_4b_it_bf16_jev77_d0_disc",
                    "discrete", "d0", "medgemma4b", 45 * 60),
    "M4P0": _cell77("llm_medgemma_1_5_4b_it_bf16_jev77_d0_prob",
                    "probabilities", "d0", "medgemma4b", 45 * 60),
    "M4D1": _cell77("llm_medgemma_1_5_4b_it_bf16_jev77_d1_disc",
                    "discrete", "d1", "medgemma4b", 45 * 60),
    "M4P1": _cell77("llm_medgemma_1_5_4b_it_bf16_jev77_d1_prob",
                    "probabilities", "d1", "medgemma4b", 45 * 60),
    # bloque Gemma 3 4B (puertas 15-18)
    "G4D0": _cell77("llm_gemma3_4b_it_bf16_jev77_d0_disc",
                    "discrete", "d0", "gemma3_4b", 45 * 60),
    "G4P0": _cell77("llm_gemma3_4b_it_bf16_jev77_d0_prob",
                    "probabilities", "d0", "gemma3_4b", 45 * 60),
    "G4D1": _cell77("llm_gemma3_4b_it_bf16_jev77_d1_disc",
                    "discrete", "d1", "gemma3_4b", 45 * 60),
    "G4P1": _cell77("llm_gemma3_4b_it_bf16_jev77_d1_prob",
                    "probabilities", "d1", "gemma3_4b", 45 * 60),
}

# Bloques por checkpoint en el orden del manifiesto (§8.3); dentro de
# cada bloque la lista L rota por fase: en la fase i el orden es
# L[(j+i) mod len(L)] para j=0..len(L)-1 (§8.4).
BLOCKS_77 = [
    ("medgemma27b", ["MD0", "MP0", "MD1", "MP1"]),
    ("gemma3_27b", ["GD0", "GP0", "GD1", "GP1"]),
    ("qwen38fp8", ["QD0p", "QD1p"]),
    ("medgemma4b", ["M4D0", "M4P0", "M4D1", "M4P1"]),
    ("gemma3_4b", ["G4D0", "G4P0", "G4D1", "G4P1"]),
]

# Topes operativos del encargo JEV-77 (§8.1-8.2): preparación A3 con
# reloj y cupo propios que CUENTAN en las 12.000 duras pero no en las
# 40 h de evaluación; distinción durable transición/recarga/reinicio
# (máx. 4 extraordinarios, reserva de 288 intentos de puertas sobre la
# reserva total de 612); transición de checkpoint ≤ 60 min.
PREP_MAX_REQUESTS = 150
PREP_MAX_WALL_S = 4 * 3600
RESTART_EXTRA_MAX = 4
RESTART_GATE_RESERVE = 288
GATE_RESERVE_TOTAL = 612
TRANSITION_CAP_S = 3600
JEV77_CASCADE_REQUESTS = 800
JEV77_CASCADE_WALL_S = 3 * 3600

PROFILES = {
    "jev68": {"cells": CELLS, "calendar_base": CALENDAR_BASE,
              "calendar_extra": {"papers32": ("S202",), "adv3": ("S202",)},
              "session_cap_s": SESSION_CAP_S, "request_cap": REQUEST_CAP,
              "paths": {"state": "qwen_session.json",
                        "pause": "qwen_session.pause",
                        "manifest": "qwen_manifest.json",
                        "manifest_archive": "qwen_manifest_{sha}.json",
                        "refs": "qwen_refs_{key}.json",
                        "gate_run": "gate_qwen_{key}"},
              "diag": True, "analysis": "jev68"},
    "jev76": {"cells": CELLS_76, "calendar_base": CALENDAR_76,
              "calendar_extra": {},
              "session_cap_s": 14 * 3600, "request_cap": REQUEST_CAP,
              "paths": {"state": "qwen_session_jev76.json",
                        "pause": "qwen_session_jev76.pause",
                        "manifest": "qwen_manifest_jev76.json",
                        "manifest_archive": "qwen_manifest_jev76_{sha}.json",
                        "refs": "qwen_refs_jev76_{key}.json",
                        "gate_run": "gate_qwen76_{key}"},
              "diag": False, "analysis": "factorial"},
    "jev77": {"cells": CELLS_77, "calendar_base": None,
              "calendar_extra": {}, "blocks": BLOCKS_77,
              "ckpts": CKPTS_77,
              # 40 h WALL con pausas desde el primer arranque de
              # evaluación (§8.2: otro reloj que el acumulado de
              # jev68/jev76); subsesiones ≤ 12 h continuas; 12.000
              # peticiones duras locales
              "session_cap_s": 40 * 3600, "request_cap": 12000,
              "clock": "wall", "subsession_cap_s": 12 * 3600,
              "all_tokenizer_refs": True, "blind_sha": True,
              "paths": {"state": "qwen_session_jev77.json",
                        "pause": "qwen_session_jev77.pause",
                        "manifest": "qwen_manifest_jev77.json",
                        "manifest_archive": "qwen_manifest_jev77_{sha}.json",
                        "refs": "qwen_refs_jev77_{key}.json",
                        "gate_run": "gate_jev77_{key}"},
              "diag": False, "analysis": "medgemma"},
}
_PROFILE = "jev68"


def _prof():
    return PROFILES[_PROFILE]


def _set_profile(name):
    """Selecciona el perfil de la sesión: reasigna las celdas, el
    calendario base y los topes que el resto del módulo lee como
    constantes (los tests los siguen pudiendo sustituir por mock); las
    rutas se resuelven por _prof() en cada punto de acceso."""
    if name not in PROFILES:
        raise SystemExit(f"perfil {name!r} desconocido "
                         f"(hay {sorted(PROFILES)})")
    global _PROFILE, CELLS, CALENDAR_BASE, SESSION_CAP_S, REQUEST_CAP
    _PROFILE = name
    p = PROFILES[name]
    CELLS = p["cells"]
    CALENDAR_BASE = p["calendar_base"]
    SESSION_CAP_S = p["session_cap_s"]
    REQUEST_CAP = p["request_cap"]


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


def gate_key(mode, prompt, thinking, order, ckpt=None):
    """Clave de combo: en perfiles multi-checkpoint (jev77) lleva el slug
    del checkpoint como quinto campo (`…_d0_medgemma27b`)."""
    k = f"{MODE_SLUG[mode]}_{prompt}_{'on' if thinking else 'off'}_{order}"
    return f"{k}_{ckpt}" if ckpt else k


_GATE_RE = re.compile(
    r"^(prob|disc)_(typesafe|sin_antinj|antinj_alt)_(on|off)_(d[0-3])"
    r"(?:_([a-z0-9]+(?:_[a-z0-9]+)*))?$")


def parse_gate_key(key):
    m = _GATE_RE.fullmatch(key)
    if not m:
        raise SystemExit(f"combo {key!r} inválido: esperado "
                         "<prob|disc>_<typesafe|sin_antinj|antinj_alt>_"
                         "<on|off>_<d0..d3>[_<checkpoint>]")
    modo, prompt, th, order, ckpt = m.groups()
    combo = {"mode": SLUG_MODE[modo], "prompt": prompt,
             "thinking": th == "on", "order": order}
    if ckpt:
        spec = (_prof().get("ckpts") or {}).get(ckpt)
        if spec is None:
            raise SystemExit(f"combo {key!r}: checkpoint {ckpt!r} no es "
                             f"del perfil {_PROFILE}")
        if spec["thinking"] is None:
            if th == "on":
                raise SystemExit(f"combo {key!r}: {ckpt} no tiene modo "
                                 "thinking configurable")
            combo["thinking"] = None     # sin flag (familia Gemma)
        combo["ckpt"] = ckpt
        combo["checkpoint"] = spec["checkpoint"]
        combo["a01_margin"] = spec.get("a01_margin", 200)
    return combo


def cell_combo(cell):
    c = {"mode": cell["mode"], "prompt": cell.get("prompt", "typesafe"),
         "thinking": cell["thinking"], "order": cell["order"]}
    if cell.get("ckpt"):
        c["ckpt"] = cell["ckpt"]
    return c


def cell_gate_key(cell):
    c = cell_combo(cell)
    return gate_key(c["mode"], c["prompt"], c["thinking"], c["order"],
                    c.get("ckpt"))


def _combo_opts(combo, seed=101, base_url=None):
    """Opciones del adaptador llm de una combinación (bloque común R13 §4);
    en jev77 el modelo servido y max_tokens vienen del checkpoint del
    combo (medgemma_jev77 §4: provisional hasta A4)."""
    spec = (_prof().get("ckpts") or {}).get(combo.get("ckpt")) or {}
    opts = {"provider": "openai",
            "model": spec.get("served", HOST["model"]),
            "base_url": base_url or HOST["base_url"], "api_key": "none",
            "mode": combo["mode"], "structured": "true",
            "inject_schema_in_prompt": "true", "normalize": "true",
            "capture_raw": "true", "retries_malformed": "2",
            "max_tokens": spec.get("max_tokens", "16384"),
            "timeout": "300", "case_timeout": "600",
            "prompt": combo["prompt"],
            "choice_order": f"department:{combo['order']}",
            "extra_body": _extra_body(combo["thinking"], seed)}
    if spec.get("checkpoint"):
        opts["checkpoint"] = spec["checkpoint"]
    return opts


def _llm_factory(opts):
    return adapters.get("llm")(**opts)


def combos_needed():
    """Puertas que exige la sesión: las de las celdas + las de P71.2
    (solo en perfiles con diagnósticos; jev76 es solo el bloque de
    batería del factorial)."""
    out = {cell_gate_key(c) for c in CELLS.values()}
    if _prof()["diag"]:
        out |= {gate_key("probabilities", p, False, "d0")
                for p in DIAG_VARIANTS.values()}
    return sorted(out)


def _needs_tokenizer_refs(combo):
    """Combos sin referencia histórica válida: thinking=on (otra plantilla) o
    prompt != typesafe (otro system prompt). En jev77 TODOS los combos
    llevan refs tokenizer propias por checkpoint (§7.1: refs propias por
    combo, sin reciclar entre familias)."""
    if _prof().get("all_tokenizer_refs"):
        return True
    return combo["thinking"] or combo["prompt"] != "typesafe"


def _load_hist():
    """Referencia histórica off de REF_RUN; {} en perfiles donde TODOS los
    combos llevan refs tokenizer propias (jev77): no hay histórico
    aplicable y su ausencia no tumba la sesión."""
    try:
        return j67.load_token_ref()
    except SystemExit:
        if _prof().get("all_tokenizer_refs"):
            return {}
        raise


def _refs_path(key):
    return (store.ROOT / "logs"
            / _prof()["paths"]["refs"].format(key=key))


def _gate_run(key):
    """Directorio de la puerta de `key` bajo results/ — propio de cada
    perfil (gate_qwen_* en jev68, gate_qwen76_* en jev76), para que la
    evidencia de una sesión no se mezcle nunca con la de la otra."""
    return _prof()["paths"]["gate_run"].format(key=key)


def _manifest_archive_path(sha):
    return (store.ROOT / "logs"
            / _prof()["paths"]["manifest_archive"].format(sha=sha))


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
    # del wire las aplana a nivel superior: la flag se busca en las dos
    # formas, anidada y aplanada (R36: cualquier presencia cuenta)
    decls = []
    for src in (req, req.get("extra_body") or {}):
        if not isinstance(src, dict):
            continue
        ctk = src.get("chat_template_kwargs") or {}
        if "enable_thinking" in ctk:
            decls.append(ctk["enable_thinking"])
        if "enable_thinking" in src:
            decls.append(src["enable_thinking"])
    decl = decls[0] if decls else None
    want = combo["thinking"]
    if want is None:
        # familia sin modo thinking configurable (Gemma en jev77 §3.4):
        # la petición NO declara enable_thinking EN ABSOLUTO — ni on ni
        # off — y el razonamiento que emerja solo se registra en la
        # evidencia, nunca bloquea
        if decls:
            fails.append(f"{tag}: enable_thinking declarado {decl!r} en "
                         "un combo sin modo thinking")
        return fails
    if decl is not want:
        fails.append(f"{tag}: enable_thinking declarado {decl!r} != "
                     f"{want!r}")
    obs = _thinking_observed(att)
    if obs != want:
        fails.append(f"{tag}: thinking no efectivo en el raw "
                     f"(observado {obs}, esperado {want})")
    return fails


def _dept_order_in(schema):
    """Orden de las opciones de department en un esquema dado:
    `properties` en probabilities, `enum` en discrete."""
    if schema is None:
        return None
    props, defs = j67._answers_properties(schema)
    field = props.get("department") or {}
    target = (defs.get(field["$ref"].split("/")[-1]) if "$ref" in field
              else field) or {}
    if target.get("properties") is not None:
        return list(target["properties"])
    enum = target.get("enum") or field.get("enum")
    return list(enum) if isinstance(enum, list) else []


def _dept_schema_order(req):
    """Orden de las opciones de department en el esquema incrustado:
    `properties` en probabilities, `enum` en discrete."""
    return _dept_order_in(
        j67._embedded_schema(j67._system_message(req)))


def _doc_payloads(req):
    """Contenidos de los payloads <document>…</document> del request
    (el estado del caso viaja serializado en JSON ahí dentro)."""
    out = []
    for m in req.get("messages") or []:
        c = m.get("content")
        if not isinstance(c, str) or "<document>" not in c:
            continue
        inner = c.split("<document>", 1)[1]
        inner = (inner.rsplit("</document>", 1)[0]
                 if "</document>" in inner else inner)
        out.append(inner.strip("\n"))
    return out


def _non_doc_text(content):
    """El mensaje sin los payloads <document>…</document>: el estado del
    caso es contenido legítimo; la exclusión de inyección del ciego se
    verifica en el RESTO del mensaje (R36)."""
    parts = content.split("<document>")
    out = [parts[0]]
    for part in parts[1:]:
        out.append(part.split("</document>", 1)[-1])
    return "".join(out)


def _state_in_request(req, state):
    """El payload <document> del usuario decodifica EXACTAMENTE al estado
    del caso (serialización JSON del adaptador): un estado sustituido o
    truncado no pasa la vigilancia aunque los tokens cuadren (R36)."""
    for inner in _doc_payloads(req):
        if inner == state:
            return True
        try:
            if json.loads(inner) == state:
                return True
        except (ValueError, TypeError):
            pass
    return False


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
                 "direct": lambda th: {"enable_thinking": th},
                 # combos sin modo thinking (Gemma en jev77): la
                 # referencia se calcula sin pasar el flag a la plantilla
                 "plain": lambda th: {}}


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
                    # solo los combos con flag thinking necesitan
                    # verificar qué forma honra la plantilla; en los
                    # sin flag (Gemma, jev77) el render va "plain"
                    form = ("plain" if combo["thinking"] is None
                            else _thinking_form(tokenizer, msgs))
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


def _case_client_fails(combo, tag, rec, qs, exp_sha, state=None):
    """Cliente + thinking sobre el primer intento del caso: sha del system
    prompt contra el precomputado, apéndice decodificado ==
    response_format.schema, presencia de ids/instrucciones/criterios, orden
    esperado de department, estado del caso preservado en el payload
    <document> (R36: sustitución o truncado invalidan aunque el resto
    cuadre) y thinking declarado == observado. Es el criterio
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
    # estado del caso completo en el payload <document> (R36)
    if state is not None and not _state_in_request(req, state):
        fails.append(f"{tag}: estado del caso no preservado en el "
                     "payload <document>")
    fails += _thinking_fails(combo, tag, req, att)
    return fails


def _gate_case_fails(combo, phase, cid, rec, qs, exp_sha, hist, ref_on,
                     tokens, offsets, state=None):
    """Criterios de puerta por caso visible (cliente + motor + thinking)."""
    tag = f"{phase}/{cid}"
    if state is None:
        # sin estado explícito se resuelve contra la batería (la puerta,
        # la vigilancia y la auditoría siempre lo pasan)
        state = next((c.state for c in load_phase(phase)[1]
                      if c.id == cid), None)
    fails = _case_client_fails(combo, tag, rec, qs, exp_sha, state=state)
    # motor: usage del primer intento
    t = j67._first_prompt_tokens(rec)
    tokens[phase] = t
    if "error" in rec or j67._first_attempt(rec) is None:
        return fails
    if combo["mode"] == "discrete" and not _needs_tokenizer_refs(combo):
        # discrete/OFF: los offsets por familia se miden aquí contra la
        # referencia histórica y viajan con la puerta (no se comprueban).
        # discrete/ON no pasa por aquí: su prompt es otro render y tiene
        # referencia tokenizer propia — aplicarle el histórico+offset de
        # off mediría la puerta contra el prompt equivocado (R30).
        r = (hist.get(phase) or {}).get(cid)
        if t is None:
            fails.append(f"{tag}: sin usage en el primer intento")
        elif r is None:
            fails.append(f"{tag}: sin ref de tokens")
        else:
            offsets[family(phase)] = t - r
    else:
        # prob (off/on) y discrete+ON: la puerta aplica la misma
        # token_rule que luego vigila la batería — DT contra SU
        # referencia tokenizer (±2), nunca contra offsets de off (R30)
        st, det = token_rule(combo, phase, cid, t, hist, ref_on, {})
        if st == "sin_usage":
            fails.append(f"{tag}: sin usage en el primer intento")
        elif st == "violacion":
            fails.append(f"{tag}: tokens fuera de referencia {det}")
    return fails


def _attempt_finish_reason(att):
    """finish_reason del intento (debug_info o choice); None si ausente."""
    if not att:
        return None
    fr = (att.get("debug_info") or {}).get("finish_reason")
    if fr:
        return fr
    ch = ((att.get("llm_response") or {}).get("choices") or [{}])[0]
    return ch.get("finish_reason")


def _attempt_assistant_content(att):
    """Texto del assistant en el intento (content del choice[0])."""
    if not att:
        return None
    ch = ((att.get("llm_response") or {}).get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    return msg.get("content")


def _schema_resolve(schema, root):
    """Resuelve `$ref` locales `#/$defs/...` sobre el schema raíz."""
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return schema
    name = ref.rsplit("/", 1)[-1]
    resolved = (root.get("$defs") or {}).get(name)
    return resolved if isinstance(resolved, dict) else schema


def _value_matches_json_schema(val, schema, root):
    """Valida val contra un subconjunto de JSON Schema (type, required,
    properties, additionalProperties, enum, minimum/maximum, $ref).
    No inventa restricciones ausentes en el esquema archivado."""
    schema = _schema_resolve(schema, root)
    if not isinstance(schema, dict):
        return False, "schema inválido"
    t = schema.get("type")
    if t == "object":
        if not isinstance(val, dict):
            return False, "se esperaba object"
        req = schema.get("required") or []
        for k in req:
            if k not in val:
                return False, f"falta clave requerida {k!r}"
        props = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            extra = set(val) - set(props)
            if extra:
                return False, f"claves ajenas {sorted(extra)}"
        for k, v in val.items():
            if k not in props:
                continue
            ok, why = _value_matches_json_schema(v, props[k], root)
            if not ok:
                return False, f"{k}: {why}"
        return True, None
    if t == "integer":
        # bool es subclase de int en Python: excluirlo
        if not isinstance(val, int) or isinstance(val, bool):
            return False, "se esperaba integer"
        if "minimum" in schema and val < schema["minimum"]:
            return False, f"integer < minimum {schema['minimum']}"
        if "maximum" in schema and val > schema["maximum"]:
            return False, f"integer > maximum {schema['maximum']}"
        return True, None
    if t == "boolean":
        if not isinstance(val, bool):
            return False, "se esperaba boolean"
        return True, None
    if t == "string":
        if not isinstance(val, str):
            return False, "se esperaba string"
        enum = schema.get("enum")
        if enum is not None and val not in enum:
            return False, f"string no está en enum"
        return True, None
    if t == "number":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return False, "se esperaba number"
        return True, None
    if t == "array":
        if not isinstance(val, list):
            return False, "se esperaba array"
        return True, None
    if t == "null":
        if val is not None:
            return False, "se esperaba null"
        return True, None
    # sin type: solo $ref ya resuelto u objeto vacío
    return True, None


def _blind_response_matches_request_grammar(data, req):
    """La respuesta cumple el response_format.json_schema de ESA petición."""
    root = ((req.get("response_format") or {}).get("json_schema")
            or {}).get("schema")
    if not isinstance(root, dict):
        return False, "sin schema en request"
    return _value_matches_json_schema(data, root, root)


# Errores terminales que NUNCA son rechazo de valores del SDK, aunque el
# primer intento fuera JSON+stop (Enmienda 2 / R59).
_BLIND_TERMINAL_NON_VALUE = re.compile(
    r"(?i)\b(TimeoutError|timed?\s*out|ConnectionError|ConnectionReset|"
    r"ConnectionRefused|URLError|RemoteDisconnected|BrokenPipeError|"
    r"OSError|HTTPError|connection reset|connection refused)\b")


def _is_sdk_answers_value_error(err):
    """Reconocimiento positivo: TypeSafeAPIResponseValidationError por
    datos de `answers` (rango/etiqueta), no por transporte."""
    s = str(err or "")
    if "TypeSafeAPIResponseValidationError" not in s:
        return False
    return ("answers" in s.lower()
            or "Invalid response data at 'answers'" in s
            or "Invalid response data" in s)


def _blind_grammar_stop_ok(rec):
    """Primer intento con finish=stop, usage.prompt_tokens y JSON que
    cumple el response_format archivado de esa petición (objeto, required,
    types, additionalProperties, enum/min/max si constan). Usado por
    Enmienda 2 de jev77: un integer sin min/max (p. ej. urgency=1300)
    sigue siendo gramática OK; answers=null / {} / tipos rotos no."""
    att = j67._first_attempt(rec)
    if att is None:
        return False, "sin raw del primer intento"
    fr = _attempt_finish_reason(att)
    if fr != "stop":
        return False, f"finish_reason={fr!r}"
    if j67._first_prompt_tokens(rec) is None:
        return False, "sin usage en el primer intento"
    content = _attempt_assistant_content(att)
    if not isinstance(content, str) or not content.strip():
        return False, "sin content JSON"
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return False, "JSON inválido"
    req = att.get("request") or {}
    ok, why = _blind_response_matches_request_grammar(data, req)
    if not ok:
        return False, f"fuera de gramática: {why}"
    return True, None


def _blind_error_is_value_contract(rec):
    """Enmienda 2 (medgemma_jev77): error del SDK por valores fuera de
    contrato (rango/etiqueta) tras un intento con gramática OK y
    finish=stop. Solo perfil jev77. Reconoce positivamente
    TypeSafeAPIResponseValidationError sobre answers; excluye timeout /
    transporte y demás causas terminales aunque el primer intento fuera
    JSON+stop."""
    if _PROFILE != "jev77" or "error" not in rec:
        return False
    err = rec.get("error") or ""
    if _BLIND_TERMINAL_NON_VALUE.search(str(err)):
        return False
    if not _is_sdk_answers_value_error(err):
        return False
    ok, _ = _blind_grammar_stop_ok(rec)
    return ok


def _blind_fails(combo, tag, rec, qs, exp_sha=None, state=None,
                 exp_schema=None):
    """Control negativo: el ciego no debe ver preguntas ni apéndice EN
    NINGÚN mensaje (R36 — antes solo se miraba system), el estado del
    caso viaja intacto en el payload <document> y la gramática conserva
    el esquema esperado del combo (checkpoint×modo×orden — con
    `exp_schema`, el esquema que generó el propio combo en la pasada
    visible; sin ella, cobertura completa de preguntas y orden de
    department). Devuelve (fallos, prompt_tokens del primer intento |
    None). Con `exp_sha` (jev77 §7.3 sonda 4) el hash del prompt ciego
    precomputado debe igualar el observado — es un prompt distinto del
    visible.

    Enmienda 2 (perfil jev77 solamente): si el ciego responde con JSON
    válido para la gramática y finish=stop pero el SDK rechaza valores
    fuera de contrato (p. ej. urgency=1300), eso NO es fallo de
    visibilidad — se acredita con hash, ausencia de inyección y margen
    de prompt_tokens del primer intento. jev68/jev76 sin cambio."""
    if "error" in rec and not _blind_error_is_value_contract(rec):
        return [f"ciego {tag}: error {rec['error'][:120]}"], None
    att = j67._first_attempt(rec)
    if att is None:
        return [f"ciego {tag}: sin raw del primer intento"], None
    req = att.get("request") or {}
    fails = [f"ciego {tag}: {f}"
             for f in j67.check_client(req, qs, "blind", combo["mode"])]
    sysm = j67._system_message(req)
    if exp_sha is not None:
        sha = (hashlib.sha256(sysm.encode()).hexdigest()[:12]
               if sysm else None)
        if sha != exp_sha:
            fails.append(f"ciego {tag}: sha system {sha} != "
                         f"precomputado {exp_sha}")
    # inyección excluida en TODOS los mensajes efectivos: ni instrucciones
    # ni criterios ni el apéndice de esquema pueden viajar fuera de la
    # gramática (el payload <document> se excluye: es el estado del caso)
    for m in req.get("messages") or []:
        content = m.get("content")
        if not isinstance(content, str):
            continue
        text = _non_doc_text(content)
        if j67.SCHEMA_MARKER in text:
            fails.append(f"ciego {tag}: apéndice de esquema en mensaje "
                         f"{m.get('role')}")
        for qid, q in qs.items():
            instr = q.get("instructions") or ""
            if instr and instr in text:
                fails.append(f"ciego {tag}: instrucciones de {qid} en "
                             f"mensaje {m.get('role')}")
            crit = q.get("criteria") or {}
            ctexts = crit.values() if isinstance(crit, dict) else crit
            for ct in ctexts:
                if ct and ct in text:
                    fails.append(f"ciego {tag}: criterio de {qid} en "
                                 f"mensaje {m.get('role')}")
                    break
    # el estado viaja completo en el payload <document>
    if state is not None and not _state_in_request(req, state):
        fails.append(f"ciego {tag}: estado del caso no preservado en el "
                     "payload <document>")
    # la gramática conserva el esquema del combo: response_format queda
    # intacto con las preguntas y el orden del modo×orden del combo
    rf_schema = ((req.get("response_format") or {})
                 .get("json_schema") or {}).get("schema")
    if exp_schema is not None:
        if rf_schema != exp_schema:
            fails.append(f"ciego {tag}: schema de response_format != "
                         "el esperado del combo")
    else:
        qs_eff = _qs_eff(qs, combo["order"])
        fails += [f"ciego {tag}: {f}" for f in
                  j67.check_question_visibility(
                      rf_schema if isinstance(rf_schema, dict) else {},
                      qs_eff, combo["mode"])]
    if "department" in qs and isinstance(rf_schema, dict):
        want = NAMED_ORDERS["department"][combo["order"]]
        got = _dept_order_in(rf_schema)
        if got != want:
            fails.append(f"ciego {tag}: orden department en schema "
                         f"{got} != {want}")
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
                    bf, _ = _blind_fails(combo, "canario", rec, CANARY_QS,
                                         state=CANARY_STATE)
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
         new_session=False, reason=None, printer=print):
    """Puerta de una combinación mode×prompt×thinking×orden (R13 §4).
    Devuelve (ok, detalles). Toma el lock de sesión — es una mutación como
    run/diag — y descuenta sus sondas de los mismos topes (peticiones,
    tope de sesión del perfil). La evidencia de cada ejecución queda archivada de forma inmutable
    en results/gate_qwen_<key>[_blind]~<uid>/ ligada a su gate_id único;
    results/gate_qwen_<key>[_blind]/ queda como puntero a la última.
    Bloqueantes: cliente, motor (±2/±10, offsets de discrete/off y
    referencia tokenizer propia en los combos `on` — discrete+thinking
    incluido, R30), control negativo ciego en A01 (visible−ciego ≥ 200),
    thinking efectivo y raw/usage presentes. El canario conductual se
    ejecuta y se archiva como OBSERVACIÓN (Enmienda 1, qwen38_jev68 §14):
    queda en el entry y en la salida, pero no cambia PASS/FAIL."""
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
        st = session_begin(session, new_session, reason=reason,
                           ckpt=combo.get("ckpt"))
        gate_bucket = None
        if _prof().get("blocks"):
            # jev77 §8.1: las puertas son SOLO de los combos del
            # checkpoint activo — el de la instancia servida ahora
            if combo.get("ckpt") != st.get("active_ckpt"):
                raise SystemExit(
                    f"puerta {key}: el checkpoint {combo.get('ckpt')!r} "
                    f"no es el activo {st.get('active_ckpt')!r}: declara "
                    "la transición o la recarga con --new-session "
                    "primero")
            inst = (st.get("instances") or [{}])[-1]
            gate_bucket = ("planned" if inst.get("reason")
                           in (None, "initial", "transition")
                           else inst["reason"])
        elapsed_base = st["elapsed_s"]
        factory = model_factory or _llm_factory
        hist = hist_ref if hist_ref is not None else _load_hist()
        if _needs_tokenizer_refs(combo) and ref_on is None:
            ref_on = load_refs(key)
        fails, tokens, offsets = [], {}, {}
        opts_v = _combo_opts(combo)
        model = factory(opts_v)
        uid = uuid.uuid4().hex[:8]
        ts = dt.datetime.now().isoformat(timespec="microseconds")
        gate_id = f"{_gate_run(key)}@{ts}~{uid}"
        run_v = _gate_run(key)
        cases = _gate_cases()
        reserve = int(opts_v["retries_malformed"]) + 1
        printer(f"[{run_v}] sesión {session} gate_id {gate_id} "
                f"{model.meta()}")

        def _elapsed():
            return _sess_elapsed(st, elapsed_base, t0)

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
                out.append(f"{what}: tope de sesión de "
                           f"{SESSION_CAP_S // 3600} h agotado")
                return False
            sub_rem = _sub_remaining(st)
            if sub_rem is not None and sub_rem <= 0:
                out.append(f"{what}: tope de subsesión de "
                           f"{_prof()['subsession_cap_s'] // 3600} h "
                           "agotado")
                return False
            if gate_bucket is not None:
                # jev77 §8.1: reserva de puertas — 612 en total y 288
                # como máximo bajo reinicios extraordinarios
                spend = st.get("gate_spend") or {}
                if sum(spend.values()) + reserve > GATE_RESERVE_TOTAL:
                    out.append(f"{what}: reserva total de puertas "
                               f"{GATE_RESERVE_TOTAL} agotada")
                    return False
                if gate_bucket == "restart" \
                        and (spend.get("restart", 0) + reserve
                             > RESTART_GATE_RESERVE):
                    out.append(f"{what}: reserva de puertas de "
                               "reinicios extraordinarios "
                               f"({RESTART_GATE_RESERVE}) agotada")
                    return False
            return True

        def _eval(what, mdl, case, qs_, run_, ph_, opts_, variant):
            """eval de puerta con reserva durable (persistida ANTES de
            abrir la petición, con su marca temporal para conciliar una
            interrupción — R18 §3) y deadline operativo en el proveedor:
            la petición no puede pasar del remanente de sesión NI de
            subsesión (R36: el mínimo de ambos) y la configuración
            congelada no se muta."""
            rem = SESSION_CAP_S - _elapsed()
            sub_rem = _sub_remaining(st)
            if sub_rem is not None:
                rem = min(rem, sub_rem)
            st["requests"] += reserve
            if gate_bucket is not None:
                gsp = st.setdefault("gate_spend", {})
                gsp[gate_bucket] = gsp.get(gate_bucket, 0) + reserve
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
            if gate_bucket is not None:
                st["gate_spend"][gate_bucket] += _attempts(rec) - reserve
            st["pending"] = None
            _sync()
            return rec

        vis_schema = None
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
                                      offsets, state=case.state)
            if vis_schema is None:
                # la gramática del combo — referencia con la que el ciego
                # debe coincidir en response_format (R36)
                att0 = j67._first_attempt(rec) or {}
                vis_schema = (((att0.get("request") or {})
                              .get("response_format") or {})
                             .get("json_schema") or {}).get("schema")
            printer(f"  visible {phase}/{case.id}: prompt_tokens="
                    f"{tokens.get(phase)}")
        # control negativo ciego en A01 (mismo modo/prompt/thinking)
        opts_b = {**opts_v, "inject_schema_in_prompt": "false"}
        model_b = factory(opts_b)
        run_b = _gate_run(key) + "_blind"
        ph0, c0 = cases[0]
        qs0, _ = load_phase(ph0)
        if _budget_ok("control negativo"):
            # jev77 §7.3 sonda 4: el prompt ciego lleva sha propio
            # precomputado (distinto del visible), como los visibles
            exp_sha_b = (model_b.expected_system_prompt_sha256(qs0)
                         if _prof().get("blind_sha") else None)
            rec_b = _eval(f"ciego {ph0}/{c0.id}", model_b, c0, qs0, run_b,
                          ph0, opts_b, "blind")
            b_fails, tb = _blind_fails(combo, f"{ph0}/{c0.id}", rec_b, qs0,
                                       exp_sha=exp_sha_b, state=c0.state,
                                       exp_schema=vis_schema)
            fails += b_fails
            tv = tokens.get(ph0)
            margin = combo.get("a01_margin", 200)
            if tv is not None and tb is not None and tv - tb < margin:
                fails.append(f"control negativo: visible-ciego en "
                             f"{ph0}/{c0.id} = {tv - tb} < {margin} "
                             "tokens")
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
    for ph in store.runs_in(_gate_run(key)):
        doc = store.load(_gate_run(key), ph) or {}
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
    runs = [_gate_run(key)]
    base = store.ROOT
    if base.exists():
        runs += sorted(d.name for d in base.glob(_gate_run(key) + "~*")
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
    return store.ROOT / "logs" / _prof()["paths"]["state"]


def _lock_path():
    # compartido entre perfiles a propósito: un solo escritor/supervisor
    # sobre el mismo servidor, sea cual sea la sesión
    return store.ROOT / "logs" / "qwen_session.lock"


def _pause_path():
    return store.ROOT / "logs" / _prof()["paths"]["pause"]


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


def _sess_elapsed(st, base, t0, now=time.monotonic):
    """Reloj del tope de sesión del perfil:
    - jev68/jev76: tiempo ACUMULADO del supervisor — `base` es la lectura
      congelada al entrar en la invocación (persistida en elapsed_s) +
      el delta de esta invocación;
    - jev77: WALL desde el primer arranque de evaluación (st['wall_t0'])
      — las pausas entre comandos cuentan dentro de las 40 h
      (medgemma_jev77 §8.2; R35 lo exige explícito)."""
    if _prof().get("clock") == "wall":
        wt0 = st.get("wall_t0")
        if isinstance(wt0, (int, float)):
            return _wall() - wt0
    return base + (now() - t0)


def _sub_elapsed(st):
    """Segundos de la subsesión en curso (jev77 §8.2: 12 h de operación
    continua de la INSTANCIA servida). `sub_t0` es durable y nace con la
    carga de la instancia — ni `gate`, ni `run`, ni un `--resume`
    posteriores la reinician (R36 §2); solo la renueva una recarga
    declarada (--new-session)."""
    t0 = st.get("sub_t0")
    return _wall() - t0 if isinstance(t0, (int, float)) else None


def _sub_remaining(st):
    """Remanente de la subsesión de la instancia (None si el perfil no
    tiene subsesión o el estado aún no la fijó)."""
    cap = _prof().get("subsession_cap_s")
    if not cap:
        return None
    e = _sub_elapsed(st)
    return cap - e if e is not None else None


def _cell_exhausted(name, cell, st):
    """La celda no puede aceptar más trabajo: su tope persistido está
    agotado o el run quedó invalidado por visibilidad (§10.4)."""
    if cell.get("budget_s") is not None:
        bk = cell.get("budget_key") or name
        if (st.get("cell_s") or {}).get(bk, 0.0) >= cell["budget_s"]:
            return True
    return any((((store.load(cell["run"], ph) or {}).get("meta") or {})
                .get("diag") or {}).get("status") == "invalid_visibility"
               for ph in cell["phases"])


def _slot_todo(cell, phase):
    """Casos ejecutables pendientes del slot (celda, fase): en su ámbito,
    sin registro en el doc. Los `stopped_cases` NO son cierre — son
    casos que un tope dejó sin ejecutar y siguen pendientes."""
    doc = store.load(cell["run"], phase) or {}
    have = doc.get("cases") or {}
    _, cases = load_phase(phase)
    ids = (cell.get("case_ids") or {}).get(phase)
    return [c for c in cases
            if (ids is None or c.id in set(ids)) and c.id not in have]


def _slot_retryable(cell, phase, st):
    """Casos del slot elegibles para el REINTENTO ÚNICO (--retry-errors):
    registrados con error y aún no reintentados en este encargo."""
    doc = store.load(cell["run"], phase) or {}
    recs = doc.get("cases") or {}
    ret = (st.get("retried") or {}).get(f"{cell['run']}/{phase}") or []
    _, cases = load_phase(phase)
    ids = (cell.get("case_ids") or {}).get(phase)
    return [c for c in cases
            if (ids is None or c.id in set(ids))
            and "error" in (recs.get(c.id) or {}) and c.id not in ret]


def _block_pending(ckpt, st, retry_errors=False):
    """¿Queda trabajo ejecutable en el bloque del checkpoint? Los casos
    sin registro de celdas agotadas (tope persistido) o invalidadas no
    lo bloquean: quedan pendientes pero no ejecutables (§10.4). Con
    `retry_errors` los errores elegibles para el reintento único también
    mantienen el bloque abierto: un reintento nunca abandona el
    checkpoint que lo contiene (R38 §1)."""
    names = dict(_prof()["blocks"]).get(ckpt) or []
    for name in names:
        cell = CELLS[name]
        if _cell_exhausted(name, cell, st):
            continue
        for ph in cell["phases"]:
            if _slot_todo(cell, ph):
                return True
            if retry_errors and _slot_retryable(cell, ph, st):
                return True
    return False


def _classify_instance(st, session, reason, ckpt):
    """Clasifica el cambio de instancia de jev77 (§8.2, R36 §3) y lo
    persiste: 'transition' planificada (al SIGUIENTE bloque, solo con el
    activo cerrado — no consume la reserva de reinicios), 'subsession'
    (recarga al llegar a las 12 h del mismo checkpoint) o 'restart'
    (reinicio extraordinario del mismo checkpoint, máx. 4 y con reserva
    propia de puertas). En todos los casos la recarga es real y renueva
    `sub_t0`; los contadores del encargo nunca retroceden."""
    order = [ck for ck, _ in _prof()["blocks"]]
    active = st.get("active_ckpt") or order[0]
    if reason is None:
        # clasificación automática por señal durable: un checkpoint
        # distinto del activo o el bloque cerrado implican transición;
        # una subsesión agotada, recarga de subsesión; si no, reinicio
        if (ckpt is not None and ckpt != active) \
                or (ckpt is None and not _block_pending(active, st)):
            reason = "transition"
        elif _sub_remaining(st) is not None and _sub_remaining(st) <= 0:
            reason = "subsession"
        else:
            reason = "restart"
    if reason == "subsession" \
            and not (_sub_remaining(st) is not None
                     and _sub_remaining(st) <= 0):
        # una recarga anticipada NO es una recarga de subsesión: ésta
        # solo renueva cuando las 12 h están acreditadas (sub_t0
        # durable agotado); en cualquier otro caso cuenta como reinicio
        # extraordinario (R38 §2 — no elude el máximo de 4 ni la
        # reserva de 288 de puertas)
        reason = "restart"
    if reason == "transition":
        try:
            nxt = order[order.index(active) + 1]
        except (ValueError, IndexError):
            raise SystemExit(
                f"transición planificada imposible: {active!r} es el "
                "último bloque")
        if _block_pending(active, st):
            raise SystemExit(
                f"transición rechazada: el bloque activo {active!r} "
                "tiene casos pendientes — una transición planificada "
                "solo se declara con el bloque cerrado")
        if ckpt is not None and ckpt != nxt:
            raise SystemExit(
                f"la transición planificada es {active} → {nxt}, no "
                f"{ckpt!r}")
        ckpt = nxt
        done = st.setdefault("blocks_done", [])
        if active not in done:
            done.append(active)
        st["active_ckpt"] = ckpt
    elif reason == "restart":
        if ckpt is not None and ckpt != active:
            raise SystemExit(
                f"reinicio extraordinario rechazado: sirve {ckpt!r} y el "
                f"checkpoint activo es {active!r} — un cambio de modelo "
                "es una transición planificada")
        ckpt = active
        st["restart_extra"] = (st.get("restart_extra") or 0) + 1
        if st["restart_extra"] > RESTART_EXTRA_MAX:
            raise SystemExit(
                f"más de {RESTART_EXTRA_MAX} reinicios extraordinarios "
                "no están presupuestados (§8.2): el encargo no puede "
                "continuar")
    elif reason == "subsession":
        if ckpt is not None and ckpt != active:
            raise SystemExit(
                f"recarga de subsesión rechazada: sirve {ckpt!r} y el "
                f"checkpoint activo es {active!r}")
        ckpt = active
    else:
        raise SystemExit(f"clasificación de instancia {reason!r} "
                         "inválida (transition|restart|subsession)")
    st["sub_t0"] = _wall()
    st.setdefault("instances", []).append(
        {"session": session, "reason": reason, "ckpt": ckpt,
         "wall_ts": st["sub_t0"], "ts": _iso()})
    return st


def session_begin(session, new_session=False, reason=None, ckpt=None):
    """Registra o valida la sesión y devuelve el estado persistente.
    --new-session marca un reinicio del servidor: conserva los contadores
    globales (peticiones, tiempos por celda, elapsed) pero exige puertas
    nuevas, porque latest_gate queda ligado al id de sesión anterior.
    Es una mutación: solo la invocan los puntos de entrada que poseen el
    lock (gate/run/diag/begin); si el fichero de lock existe y no lo
    posee este proceso, se rechaza.
    jev77 añade (§8.2, R36): el primer arranque exige la preparación A3
    registrada (prep), fija wall_t0 (inicio A6 del encargo — ANTES de la
    primera carga del servidor) y sub_t0 (subsesión durable de la
    instancia), y cada --new-session se clasifica duramente como
    transición planificada, recarga de subsesión o reinicio
    extraordinario (máx. 4)."""
    if _HELD_LOCK is None and _lock_path().exists():
        raise SystemExit(f"{_lock_path()} existe: la sesión la tiene otro "
                         "proceso; la mutación exige el lock exclusivo")
    st = _load_state()
    if st is None or st.get("session") is None:
        if _prof().get("blocks") and not (st or {}).get("prep"):
            raise SystemExit(
                "preparación A3 no registrada: ejecuta antes "
                "`qwen_session prep --requests N --wall-s S` (§9)")
        base = st or {}
        st = {"session": session, "started": _iso(),
              "elapsed_s": base.get("elapsed_s", 0.0),
              "requests": base.get("requests", 0),
              "cell_s": base.get("cell_s") or {},
              "retried": base.get("retried") or {},
              "sessions": (base.get("sessions") or []) + [session]}
        for k in ("prep", "gate_spend", "restart_extra", "blocks_done",
                  "instances", "reconciled_pending"):
            if k in base:
                st[k] = base[k]
        if _prof().get("clock") == "wall":
            # jev77: inicio A6 del encargo — el reloj wall nace con el
            # primer arranque de evaluación (antes de cargar el
            # servidor, R36 §2) y no se resetea ni con --new-session
            # (las pausas y reinicios cuentan dentro de las 40 h); la
            # subsesión durable de la primera instancia nace aquí
            st["wall_t0"] = _wall()
            st["sub_t0"] = st["wall_t0"]
            st["active_ckpt"] = ckpt or _prof()["blocks"][0][0]
            st.setdefault("instances", []).append(
                {"session": session, "reason": "initial",
                 "ckpt": st["active_ckpt"], "wall_ts": st["wall_t0"],
                 "ts": _iso()})
        _save_state(st)
        return st
    if st.get("session") == session:
        if _prof().get("clock") == "wall" and st.get("sub_t0") is None:
            # estados previos a la subsesión durable: la instancia lleva
            # cargada desde wall_t0 — conservador
            st["sub_t0"] = st.get("wall_t0") or _wall()
            _save_state(st)
        # una petición interrumpida carga primero su tiempo contra los
        # topes (R18 §3): reanudar nunca regala el margen ya consumido
        return _reconcile_pending(st)
    if not new_session:
        raise SystemExit(
            f"sesión registrada {st.get('session')!r} != {session!r}: tras "
            "un reinicio del servidor pasa --new-session y repite las puertas")
    _reconcile_pending(st)
    if _prof().get("blocks"):
        st = _classify_instance(st, session, reason, ckpt)
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
    """Slots (celda, fase) congelados del bloque de batería (R13 §6 en
    jev68 — rotación de 7 celdas + S202; la rotación del factorial en
    jev76, sin celda extra; bloques por checkpoint en jev77)."""
    slots = []
    blocks = _prof().get("blocks")
    if blocks:
        # jev77 §8.3-8.4: un checkpoint a la vez; dentro de cada bloque
        # la lista L rota por fase i como L[(j+i) mod len(L)]
        for _ck, names in blocks:
            n = len(names)
            for i, ph in enumerate(PHASES_ALL):
                slots += [(names[(j + i) % n], ph) for j in range(n)]
        return slots
    n = len(CALENDAR_BASE)
    extra = _prof()["calendar_extra"]
    for i, ph in enumerate(PHASES_ALL):
        order = CALENDAR_BASE[i % n:] + CALENDAR_BASE[:i % n]
        slots += [(c, ph) for c in order]
        slots += [(c, ph) for c in extra.get(ph, ())]
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
        return _sess_elapsed(st, ctx["elapsed_base"], ctx["t0"], now)

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
            ctx["session_stop"] = (f"tope de sesión de "
                                   f"{SESSION_CAP_S // 3600} h")
            stopped.append(c.id)
            continue
        if st["requests"] + reserve > REQUEST_CAP:
            ctx["session_stop"] = (f"tope duro de {REQUEST_CAP} peticiones")
            stopped.append(c.id)
            continue
        sub_rem = _sub_remaining(st)
        if sub_rem is not None and sub_rem <= 0:
            ctx["session_stop"] = (
                f"tope de subsesión de "
                f"{_prof()['subsession_cap_s'] // 3600} h "
                "(operación continua; descarga y reanuda)")
            stopped.append(c.id)
            continue
        # el tope efectivo del request es OPERATIVO (deadline externo del
        # proveedor, en su propio reloj), nunca la configuración congelada:
        # timeout/case_timeout de meta() quedan intactos y la reanudación
        # sigue siendo compatible (R17 §4); el deadline es el mínimo de los
        # TRES remanentes vivos: sesión global (40 h), celda y subsesión
        # durable de la instancia (R36 §2) — si el presupuesto se agota a
        # media petición, la petición se para — no se cambian las opts
        rem = min(remaining_s,
                  cell["budget_s"] - spent
                  if cell["budget_s"] is not None else remaining_s,
                  sub_rem if sub_rem is not None else remaining_s)
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
            # el deadline de las sondas queda acotado por los TRES
            # presupuestos (celda, sesión global y subsesión durable),
            # recalculados tras el caso (R36)
            cell_rem = (cell["budget_s"] - _spent()
                        if cell["budget_s"] is not None else HEALTH_WAIT_S)
            sess_rem = SESSION_CAP_S - _elapsed()
            sub_rem = _sub_remaining(st)
            deadline = now() + max(0.0, min(
                HEALTH_WAIT_S, cell_rem, sess_rem,
                sub_rem if sub_rem is not None else HEALTH_WAIT_S))

            def _probe(u, timeout):
                # las sondas de /health también son peticiones: cupo
                # verificado y gasto persistido antes de abrir cada una,
                # con el remanente de los TRES presupuestos (R18 §2, R36)
                # — el socket recibe ese remanente como timeout
                if st["requests"] >= REQUEST_CAP:
                    raise _BudgetExhausted("peticiones")
                if SESSION_CAP_S - _elapsed() <= 0:
                    raise _BudgetExhausted("sesión")
                if _sub_remaining(st) is not None \
                        and _sub_remaining(st) <= 0:
                    raise _BudgetExhausted("subsesión")
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
                elif exhausted == "subsesión" \
                        or (_sub_remaining(st) is not None
                            and _sub_remaining(st) <= 0):
                    ctx["session_stop"] = (
                        f"tope de subsesión de "
                        f"{_prof()['subsession_cap_s'] // 3600} h")
                elif exhausted == "sesión" \
                        or SESSION_CAP_S - _elapsed() <= 0:
                    ctx["session_stop"] = (f"tope de sesión de "
                                           f"{SESSION_CAP_S // 3600} h")
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
        # identidad por caso: cada record lleva su sesión, su checkpoint
        # (jev77: la instancia que lo sirvió) y la puerta que lo autorizó;
        # el meta común nunca relabela casos de otra sesión
        rec["session"] = st["session"]
        if cell.get("ckpt"):
            rec["ckpt"] = cell["ckpt"]
        if ctx.get("manifest"):
            # el sha del manifiesto que autoriza ESTE caso: en una
            # transición los casos anteriores conservan el suyo
            rec["manifest_sha256"] = ctx["manifest"]
        if ctx["gate_ids"].get(key):
            rec["gate_id"] = ctx["gate_ids"][key]
        # vigilancia por caso (R13 §4): la misma evidencia que exige la
        # puerta — raw, cliente (sha/apéndice/orden), estado preservado
        # (R36) y thinking — más la regla de tokens del primer intento;
        # sin ella el run se invalida
        if "error" not in rec:
            vf = _case_client_fails(combo, f"{phase}/{c.id}", rec, qs,
                                    exp_sha, state=c.state)
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
            for ph in store.runs_in(_gate_run(key)):
                doc = store.load(_gate_run(key), ph) or {}
                off.update(((doc.get("meta") or {}).get("diag") or {})
                           .get("offsets_familia") or {})
        ctx["offsets"][key] = off
    return True


def prep(requests=0, wall_s=0.0, note=None, printer=print):
    """Registro de la preparación A3 (jev77 §8.2/§9, R36 §3): smoke tests,
    health y pruebas de puerta previas al arranque — con reloj PROPIO de
    4 h y cupo PROPIO de 150 peticiones locales que CUENTAN en las 12.000
    duras pero NO en las 40 h de evaluación. Se puede invocar varias
    veces mientras dura A3; el primer session_begin la exige registrada
    (la carga de checkpoints y su primera petición válida también)."""
    if not _prof().get("blocks"):
        printer(f"ERROR: el perfil {_PROFILE} no tiene preparación A3")
        return 1
    if requests < 0 or wall_s < 0:
        printer("ERROR: --requests/--wall-s no pueden ser negativos")
        return 1
    try:
        fd = _acquire_lock()
    except FileExistsError:
        printer(f"ERROR: {_lock_path()} existe: otro proceso tiene la "
                "sesión")
        return 1
    try:
        st = _load_state() or {}
        if st.get("session"):
            printer("ERROR: la evaluación ya empezó (A6 registrado): "
                    "A3 está cerrada")
            return 1
        p = dict(st.get("prep")
                 or {"requests": 0, "wall_s": 0.0, "events": []})
        p.setdefault("events", [])
        if p["requests"] + requests > PREP_MAX_REQUESTS:
            printer(f"ERROR: la preparación superaría "
                    f"{PREP_MAX_REQUESTS} peticiones "
                    f"({p['requests']}+{requests})")
            return 1
        if p["wall_s"] + wall_s > PREP_MAX_WALL_S:
            printer(f"ERROR: la preparación superaría "
                    f"{PREP_MAX_WALL_S // 3600} h "
                    f"({p['wall_s']}+{wall_s})")
            return 1
        p["requests"] += requests
        p["wall_s"] += wall_s
        p["events"].append({"requests": requests, "wall_s": wall_s,
                            "note": note, "ts": _iso()})
        st["prep"] = p
        # las peticiones de A3 cuentan en las 12.000 duras (§8.1)
        st["requests"] = (st.get("requests") or 0) + requests
        _save_state(st)
        printer(f"A3 registrada: {p['requests']}/{PREP_MAX_REQUESTS} "
                f"peticiones, {p['wall_s'] / 3600:.2f}/"
                f"{PREP_MAX_WALL_S // 3600} h")
        return 0
    finally:
        _release_lock(fd)


def begin(session=None, printer=print):
    """Registro del inicio A6 (jev77 §9): crea el estado de la sesión
    ANTES de cargar el primer servidor — fija wall_t0 (reloj de 40 h del
    encargo) y sub_t0 (subsesión durable de 12 h de la instancia). Exige
    la preparación A3 registrada (prep)."""
    if not session:
        printer("ERROR: --session <id> es obligatorio")
        return 1
    try:
        fd = _acquire_lock()
    except FileExistsError:
        printer(f"ERROR: {_lock_path()} existe: otro proceso tiene la "
                "sesión")
        return 1
    try:
        st = session_begin(session)
        printer(f"A6 registrado: sesión {session}, "
                f"wall_t0={st.get('wall_t0')}, "
                f"checkpoint activo {st.get('active_ckpt')}")
        return 0
    except SystemExit as e:
        printer(f"ERROR: {e}")
        return 1
    finally:
        _release_lock(fd)


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
    hist = _load_hist()
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
        reason=None, now=time.monotonic, sleep=time.sleep, printer=print):
    """Supervisor del bloque de batería (F0-F3, T0-T1, D0, S202).
    jev77 corre por BLOQUES (§8.1-8.4): solo el checkpoint activo tiene
    slots, solo él exige puertas y solo él construye clientes; la
    transición planificada se sella con el bloque cerrado (parada limpia
    con instrucciones) y la reanudación retoma el bloque que marque el
    progreso durable, nunca una posición por calendario."""
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
        st = session_begin(session, new_session, reason=reason)
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
        blocks = _prof().get("blocks")
        if blocks:
            # jev77: el bloque ejecutable viene del progreso durable —
            # nunca se retrocede, nunca se exige una puerta de un
            # checkpoint que no está servido y el checkpoint activo NO
            # avanza solo: un run que encuentra su bloque cerrado
            # anuncia la transición pendiente y espera la instancia
            # declarada (--new-session / begin), que es la única vía
            # que mueve active_ckpt con registro durable (R38 §1)
            order_ck = [ck for ck, _ in blocks]
            cur_ck = st.get("active_ckpt")
            if cur_ck not in order_ck:
                cur_ck = order_ck[0]
            done_l = st.setdefault("blocks_done", [])
            nxt_pending = next(
                (ck for ck in order_ck if ck not in done_l
                 and _block_pending(ck, st, retry_errors)), None)
            for ck in order_ck:
                if ck == nxt_pending:
                    break
                if ck not in done_l \
                        and not _block_pending(ck, st, retry_errors):
                    done_l.append(ck)
            _save_state(st)
            if nxt_pending is None:
                printer("encargo JEV-77 completo: los 5 bloques "
                        "ejecutados")
                return 0
            if nxt_pending != cur_ck:
                printer(f"TRANSICIÓN PENDIENTE {cur_ck} → {nxt_pending}: "
                        f"el bloque {cur_ck} está cerrado — descarga el "
                        "checkpoint, declara la nueva instancia con "
                        "`qwen_session begin`/`gate --new-session`, "
                        "ejecuta sus puertas y reanuda con --resume "
                        f"(transición ≤ {TRANSITION_CAP_S // 60} min)")
                return 2
            active = cur_ck
            run_names = dict(blocks)[active]
            cells_run = {n: CELLS[n] for n in run_names}
        else:
            active = None
            cells_run = CELLS
        factory = model_factory or _llm_factory
        ctx = _build_ctx(session, cells_run, factory, st)
        ctx["t0"] = now()
        ctx["elapsed_base"] = st["elapsed_s"]
        ctx["manifest"] = man["manifest_sha256"]
        ctx["amendments"] = amendments
        _validate_existing(ctx, cells_run, list(cells_run), printer)
        if amendments:
            _merge_amendments(st, amendments)
            _save_state(st)
        for cell_name, phase in _calendar():
            if ctx["session_stop"]:
                break
            if blocks and cell_name not in cells_run:
                continue   # solo el bloque activo (R36 §1)
            cell = cells_run[cell_name]
            if cell_name in ctx["cell_stop"]:
                continue
            if blocks:
                # slots sin trabajo se saltan ANTES de exigir la
                # puerta: una puerta solo se exige para abrir casos
                # nuevos — en reintento, solo los errores elegibles
                if retry_errors:
                    if not _slot_retryable(cell, phase, st):
                        continue
                elif not _slot_todo(cell, phase):
                    continue
            if not _cell_gate_ok(ctx, cell):
                ctx["session_stop"] = (
                    f"sin puerta vigente de esta sesión para "
                    f"{cell_gate_key(cell)} (checkpoint "
                    f"{cell.get('ckpt')}): ejecuta `qwen_session gate`")
                break
            _exec_slot(ctx, cell_name, phase, retry_errors, now, sleep,
                       printer)
        _finish_runs(cells_run, ctx, printer)
        st["elapsed_s"] = _sess_elapsed(st, ctx["elapsed_base"],
                                      ctx["t0"], now)
        st["pending"] = None
        _save_state(st)
        if ctx["session_stop"]:
            printer(f"PARADA DE SESIÓN: {ctx['session_stop']}")
            return 2
        for name, why in ctx["cell_stop"].items():
            printer(f"celda {name} detenida: {why}")
        if blocks:
            # bloque cerrado → transición planificada sellada; la
            # instancia nueva se declara con --new-session/begin — nunca
            # se avanza el checkpoint sin registro durable (R38 §1)
            if _block_pending(active, st, retry_errors):
                return 2
            done = st.setdefault("blocks_done", [])
            if active not in done:
                done.append(active)
                _save_state(st)
            order_ck = [ck for ck, _ in blocks]
            nxt = (order_ck[order_ck.index(active) + 1]
                   if active in order_ck
                   and order_ck.index(active) + 1 < len(order_ck)
                   else None)
            if nxt:
                printer(f"TRANSICIÓN {active} → {nxt}: descarga "
                        f"{active}, carga {nxt}, ejecuta `qwen_session "
                        f"gate` de sus combos con --new-session y "
                        "reanuda con --resume (transición ≤ "
                        f"{TRANSITION_CAP_S // 60} min)")
                return 2
            printer("encargo JEV-77 completo: los 5 bloques ejecutados")
            return 0
        return 0 if not ctx["cell_stop"] else 2
    finally:
        _release_lock(fd)


def diag(session=None, resume=False, retry_errors=False, new_session=False,
         dry_run=False, amend_manifest=None, model_factory=None,
         now=time.monotonic, sleep=time.sleep, printer=print):
    """Diagnósticos P71.2: 9 runs (V1/V3/V5 x r1-r3) sobre los 12 casos."""
    if not _prof()["diag"]:
        printer(f"ERROR: el perfil {_PROFILE} no tiene diagnósticos "
                "P71.2 (pertenecen a JEV-68)")
        return 1
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
        st["elapsed_s"] = _sess_elapsed(st, ctx["elapsed_base"],
                                      ctx["t0"], now)
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
        entry = {**combo, "gate": _gate_run(key),
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
    if _prof()["diag"]:
        dcells, dorder = _diag_cells()
        diags = [{"i": i, "cell": name, "run": dcells[name]["run"],
                  "phases": dcells[name]["phases"],
                  "case_ids": dcells[name]["case_ids"],
                  "gate": cell_gate_key(dcells[name]),
                  "budget_s": dcells[name]["budget_s"],
                  "budget_key": dcells[name]["budget_key"],
                  "opts": _cell_opts(dcells[name])}
                 for i, name in enumerate(dorder, 1)]
    else:
        diags = []
    man = {"host": dict(HOST), "ref_run": REF_RUN,
           "historical_ref": {"run": REF_RUN,
                              "present": hist is not None,
                              "tokens": hist, "sha256": hist_sha},
           "caps": {"session_s": SESSION_CAP_S, "requests": REQUEST_CAP,
                    "max_err_phase": MAX_ERR_PHASE,
                    "max_err_run": MAX_ERR_RUN,
                    "no_usage_max": NO_USAGE_MAX},
           "calendar_base": (list(CALENDAR_BASE) if CALENDAR_BASE
                             else None), "combos": combos,
           "cells": {n: {"run": c["run"], "issue": c["issue"],
                         "opts": _cell_opts(c), "budget_s": c["budget_s"],
                         "phases": c["phases"]}
                     for n, c in CELLS.items()},
           "slots": slots, "diag": diags,
           "p712_cases": ([list(pc) for pc in P712_CASES]
                          if _prof()["diag"] else []),
           "canary": {"qid": CANARY_QID, "label": CANARY_LABEL,
                      "min": CANARY_MIN, "diff": CANARY_DIFF,
                      "rol": "observacion_enmienda1"}}
    if _prof().get("blocks"):
        # jev77: el calendario se organiza por bloques de checkpoint
        # (§8.3), no por una rotación plana de celdas
        man["blocks"] = {ck: list(names) for ck, names in
                         _prof()["blocks"]}
        # jev77: las POLÍTICAS del encargo quedan congeladas también
        # (R36 §6): un cambio en el reloj wall, la subsesión, la
        # preparación A3, la clasificación de instancias, la reserva de
        # puertas o la cascada cambia el sha del manifiesto y exige
        # recongelar — nunca se altera en silencio
        man["policies"] = {
            "clock": _prof().get("clock"),
            "subsession_cap_s": _prof().get("subsession_cap_s"),
            "prep": {"max_requests": PREP_MAX_REQUESTS,
                     "max_wall_s": PREP_MAX_WALL_S},
            "instances": {"restart_extra_max": RESTART_EXTRA_MAX,
                          "restart_gate_reserve": RESTART_GATE_RESERVE,
                          "gate_reserve_total": GATE_RESERVE_TOTAL,
                          "transition_cap_s": TRANSITION_CAP_S},
            "cascade": {"requests": JEV77_CASCADE_REQUESTS,
                        "wall_s": JEV77_CASCADE_WALL_S,
                        "raw": JEV77_CASCADE_RAW,
                        "audit": JEV77_CASCADE_AUDIT,
                        "reviewer": dict(JEV77_CASCADE_REVIEWER)}}
    if _prof().get("ckpts"):
        man["checkpoints"] = _prof()["ckpts"]
    if _PROFILE != "jev68":
        man["profile"] = _PROFILE
    man["manifest_sha256"] = hashlib.sha256(
        json.dumps(man, sort_keys=True, ensure_ascii=False)
        .encode()).hexdigest()[:16]
    return man


def _manifest_path():
    return store.ROOT / "logs" / _prof()["paths"]["manifest"]


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


def _amend_jev77_ws_args(old):
    """Enmienda 1 (medgemma_jev77 §Enmienda-1, incidente de la puerta
    ciega 7-oct): añade `--constrained-json-disable-any-whitespace` a los
    args de servidor de los 5 checkpoints — el render gramatical JSON de
    la sonda ciega degeneró en relleno hasta el timeout del cliente.
    Cambia solo `checkpoints.*.args`; devuelve None si la entrada no es
    el manifiesto anterior esperado."""
    flag = "--constrained-json-disable-any-whitespace"
    try:
        new = json.loads(json.dumps(old))
        for spec in new["checkpoints"].values():
            args = spec["args"]
            if not isinstance(args, list) or flag in args:
                return None
            args.append(flag)
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
    },
    "008c1cdd499b6f92": {
        "new_sha256": "8b201bfb8b6bd5a7",
        "motivo": ("Enmienda 1 (medgemma_jev77 §Enmienda-1): "
                   "--constrained-json-disable-any-whitespace en los 5 "
                   "checkpoints — incidente de la puerta ciega de "
                   "MedGemma27 (degeneración de la gramática JSON hasta "
                   "el timeout, 7-oct-2026)"),
        "fecha": "2026-10-07",
        "apply": _amend_jev77_ws_args,
    },
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
    dst = _manifest_archive_path(old_sha)
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
    pflag = f" --profile {_PROFILE}" if _PROFILE != "jev68" else ""
    printer("# plan congelado de la sesión Qwen3.8-27B FP8 (R13 §4-§6)"
            + ("" if _PROFILE == "jev68"
               else f" — perfil {_PROFILE}, factorial discrete×thinking "
                    "(docs/infra_runs/qwen38_jev76.md)"))
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
                    f"--tokenizer <checkpoint-qwen3.8-27b-fp8>{pflag}   "
                    f"# {c['token_ref']} {estado}")
        printer(f"python3 -m jevbench.qwen_session gate {key} "
                f"--session <S>{pflag}")
    if not diag_only:
        printer("# 2) celdas: opciones efectivas completas (lo que recibe "
                "el adaptador, sin valores por omisión implícitos):")
        for name, c in man["cells"].items():
            printer(f"#   {name:4s} {c['run']} issue={c['issue']} "
                    f"tope={c['budget_s'] // 60}min fases={c['phases']}")
            printer(f"#     {json.dumps(c['opts'], sort_keys=True)}")
        if man.get("blocks"):
            printer("# 3) bloque de batería (bloques por checkpoint en "
                    "orden, rotación de celdas por fase §8.4):")
            for ck, names in man["blocks"].items():
                printer(f"#   bloque {ck}: {names}")
        else:
            printer("# 3) bloque de batería (calendario intercalado por "
                    f"fase; base={man['calendar_base']}):")
        printer(f"python3 -m jevbench.qwen_session run --session <S>{pflag}")
        for s in man["slots"]:
            printer(f"  slot {s['i']:03d} {s['cell']:4s} {s['run']:45s} "
                    f"{s['phase']:14s} n={s['n']} puerta={s['gate']} "
                    f"tope={s['budget_s'] // 60}min "
                    f"qhash={s['questions_hash']}")
            printer(f"         casos={s['case_ids']}")
    if man["diag"]:
        printer("# 4) diagnósticos P71.2 (calendario propio, tope "
                f"compartido {DIAG_BUDGET_S // 60} min; orden de fases e "
                "ids exactos por run):")
        printer(f"python3 -m jevbench.qwen_session diag "
                f"--session <S>{pflag}")
        for d in man["diag"]:
            printer(f"  diag {d['i']} {d['run']:46s} prompt="
                    f"{d['opts']['prompt']} seed="
                    f"{json.loads(d['opts']['extra_body'])['seed']} "
                    f"puerta={d['gate']} tope={d['budget_s'] // 60}min")
            printer(f"         fases={d['phases']}")
            printer(f"         casos={d['case_ids']}")
            printer(f"         opts={json.dumps(d['opts'], sort_keys=True)}")
        printer(f"# P71.2 manifiesto: "
                f"{[tuple(pc) for pc in man['p712_cases']]}")
    else:
        printer("# 4) sin diagnósticos P71.2 en este perfil")
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


def _setup_adj(setup):
    """El ajustado por celda de un _paired_setup: adj(w, draw=None) da el
    ajustado del run w observado o sobre el remuestreo `draw` (None si la
    réplica deja alguna fase sin casos). Compartido por paired_delta,
    range_boot y el bootstrap conjunto de la interacción."""
    phases, per, units = setup
    n_ph = len(phases)

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

    return phases, adj


def paired_delta(run_a, run_b, iters=BOOT_ITERS, seed=BOOT_SEED, level=0.975):
    """Δ ajustado pareado (B−A) con bootstrap de clusters (traducciones y
    papers por PMID ligados), percentil del `level` dado, semilla fija.
    None si no hay fases pareadas completas."""
    setup = _paired_setup([run_a, run_b])
    if setup is None:
        return None
    phases, adj = _setup_adj(setup)
    _, _, units = setup

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
    phases, adj = _setup_adj(setup)
    _, _, units = setup
    k = len(runs)

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


def joint_stat_boot(runs, stat, iters=BOOT_ITERS, seed=BOOT_SEED,
                    level=0.95):
    """Bootstrap CONJUNTO de una estadística sobre `runs`: en cada réplica
    se remuestrean los mismos clusters (ES/EN/PMID) para TODAS las celdas
    y `stat([ajustados])` se calcula sobre ellos. Es la forma correcta del
    IC de la interacción I=(DT−T)−(D−F) de JEV-76 — nunca la resta de
    extremos de ICs calculados por separado (R30 §JEV-76 punto 4)."""
    setup = _paired_setup(list(runs))
    if setup is None:
        return None
    phases, adj = _setup_adj(setup)
    _, _, units = setup
    k = len(runs)

    obs = [adj(w) for w in range(k)]
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units))
        vals = [adj(w, draw) for w in range(k)]
        if any(v is None for v in vals):
            continue
        reps.append(stat(vals))
    if not reps:
        return None
    lo, hi = _pct(reps, level)
    return {"stat": stat(obs), "lo": lo, "hi": hi, "adj": obs,
            "reps": len(reps), "phases": [ph for ph, _ in phases]}


def _case_scores_qid(run, phase, qid):
    """{cid: puntos de UNA pregunta} — subgrupo descriptivo de jev77
    (p. ej. department en las fases con TRIAGE_QS)."""
    doc = store.load(run, phase) or {}
    qs, cases = load_phase(phase)
    if qid not in qs:
        return {}
    recs = doc.get("cases") or {}
    out = {}
    for c in cases:
        rec = recs.get(c.id)
        if not isinstance(rec, dict) or "error" in rec \
                or "answers" not in rec or qid not in rec["answers"]:
            continue
        out[c.id] = metrics.point(qs[qid],
                                  metrics.normalize(rec["answers"][qid],
                                                    qs[qid]),
                                  c.gt[qid])
    return out


def _subset_setup(runs, phases, qid=None):
    """Como _paired_setup pero sobre fases dadas (y, si qid, solo esa
    pregunta): sin filtro de baseline<100 — es descriptivo, no ajustado."""
    phases_ok, per = [], {}
    for ph in phases:
        sc = ([_case_scores_qid(r, ph, qid) for r in runs]
              if qid else [_case_scores(r, ph) for r in runs])
        _, cases = load_phase(ph)
        if any(len(s) < len(cases) for s in sc):
            continue
        per[ph] = sc
        phases_ok.append(ph)
    if not phases_ok:
        return None
    pmap = {ph: i for i, ph in enumerate(phases_ok)}
    units = []
    for members in _clusters(phases_ok).values():
        u = [(pmap[ph], cid) for ph, cid in members
             if ph in pmap and cid in per[ph][0]]
        if u:
            units.append(u)
    return phases_ok, per, units


def subset_delta(run_a, run_b, phases, qid=None, iters=BOOT_ITERS,
                 seed=BOOT_SEED, level=0.95):
    """Δ pareado de puntos medios (B−A) sobre un subconjunto de fases o
    una sola pregunta (jev77 §6.3: papers32 sola, department en las 9
    fases con TRIAGE_QS, adv1–adv5). Descriptivo: sin ajuste de baseline;
    peso igual por fase y bootstrap pareado por clusters, misma
    remuestra en ambos runs."""
    setup = _subset_setup([run_a, run_b], phases, qid)
    if setup is None:
        return None
    phs, per, units = setup
    n_ph = len(phs)

    def mean(w, draw=None):
        if draw is None:
            return 100 * sum(sum(per[ph][w].values()) / len(per[ph][w])
                             for ph in phs) / n_ph
        s = [0.0] * n_ph
        n = [0] * n_ph
        for u in draw:
            for pi, cid in u:
                s[pi] += per[phs[pi]][w][cid]
                n[pi] += 1
        if 0 in n:
            return None
        return 100 * sum(s[i] / n[i] for i in range(n_ph)) / n_ph

    delta = mean(1) - mean(0)
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units))
        va, vb = mean(0, draw), mean(1, draw)
        if va is not None and vb is not None:
            reps.append(vb - va)
    if not reps:
        return None
    lo, hi = _pct(reps, level)
    return {"delta": delta, "lo": lo, "hi": hi, "reps": len(reps),
            "phases": phs, "qid": qid}


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
        if not _prof().get("all_tokenizer_refs"):
            rep["evaluable"] = False
            rep["note"] = f"sin referencia histórica de tokens ({e})"
            return rep
        hist = {}   # jev77: todos los combos llevan refs propias
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
                combo, tag, rec, qs, exp_sha, state=c.state)
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
    """Análisis pre-registrado sobre los runs presentes en results/:
    R13 §5 en el perfil jev68; el factorial H1/H2/I en jev76."""
    if _prof()["analysis"] == "factorial":
        return analyze_factorial(out_json=out_json, iters=iters,
                                 seed=seed, printer=printer)
    if _prof()["analysis"] == "medgemma":
        return analyze_medgemma(out_json=out_json, iters=iters,
                                seed=seed, printer=printer)
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


# ---------------------------------------------------- análisis JEV-76
#
# Factorial discrete × thinking fresco en una sesión (R30 §JEV-76):
# cuatro contrastes primarios H1=DT−D≥5 y H2=DT−T≥5 por orden (d0 y d1),
# IC98.75 por contraste (Bonferroni sobre 4 ⇒ cobertura familiar ≥95 % —
# corrección simple y auditable; una corrección simultánea daría margen
# pero obligaría a congelar un método más complejo por la misma familia).
# Clasificación por contraste: CONFIRMADA si L≥5, REFUTADA si U<5,
# INCONCLUSA en otro caso y NO EVALUABLE si alguna celda no es evaluable.
# La interacción I=(DT−T)−(D−F) se publica con bootstrap conjunto de las
# cuatro celdas como DESCRIPTIVA (nunca resta de extremos de ICs y sin
# concluir aditividad porque cruce cero); los runs de JEV-68/71 se listan
# solo como referencia descriptiva, nunca como control de los contrastes.
JEV68_DESCR = {
    "d0": {"F": "llm_qwen38_27b_fp8_jev68_off_d0_prob",
           "T": "llm_qwen38_27b_fp8_jev68_on_d0_prob",
           "D": "llm_qwen38_27b_fp8_jev71_off_d0_disc"},
    "d1": {"F": "llm_qwen38_27b_fp8_jev68_off_d1_prob",
           "T": "llm_qwen38_27b_fp8_jev68_on_d1_prob"},
}
FACTORIAL_IC = 0.9875
INTERACTION_IC = 0.95


def analyze_factorial(out_json=None, iters=BOOT_ITERS, seed=BOOT_SEED,
                      printer=print):
    """Análisis pre-registrado del factorial JEV-76 sobre los runs del
    perfil presentes en results/ (H1/H2/I, Holm53 aparte, descriptivos)."""
    rep = {"profile": _PROFILE, "runs": {}, "classification": {},
           "holm53": {}}
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

    def _contrast(a, b):
        """Δ ajustado pareado (B−A) con IC98.75 — los 4 contrastes
        primarios del factorial comparten familia ≥95 % por Bonferroni."""
        if not (ev(a) and ev(b)):
            return None, _no_eval(f"faltan runs evaluables {a}/{b}")
        dd = paired_delta(CELLS[a]["run"], CELLS[b]["run"],
                          iters=iters, seed=seed, level=FACTORIAL_IC)
        if dd is None:
            return None, _no_eval("sin fases pareadas completas")
        return dd, None

    # H1: DT−D ≥ 5 en cada orden; H2: DT−T ≥ 5 en cada orden
    for h, tag, a, b in (("H1", "d0", "D0p", "DT0"),
                         ("H1", "d1", "D1", "DT1"),
                         ("H2", "d0", "T0p", "DT0"),
                         ("H2", "d1", "T1p", "DT1")):
        key = f"{h} {tag}: DT−{'D' if h == 'H1' else 'T'} >=+5"
        dd, err = _contrast(a, b)
        rep[f"{h.lower()}_{tag}"] = dd
        cls[key] = (err if err is not None
                    else _cls(dd["lo"] >= 5, dd["hi"] < 5) + (
                        f" (Δ={dd['delta']:+.1f} "
                        f"[{dd['lo']:+.1f},{dd['hi']:+.1f}] IC98.75)"))
    # Interacción I=(DT−T)−(D−F) por orden: bootstrap conjunto de las
    # cuatro celdas con los mismos clusters — DESCRIPTIVA, sin afirmar
    # aditividad por cruzar cero ni por margen de equivalencia no fijado
    for tag, quad in (("d0", ("F0p", "T0p", "D0p", "DT0")),
                      ("d1", ("F1p", "T1p", "D1", "DT1"))):
        if all(ev(n) for n in quad):
            rep[f"interaccion_{tag}"] = joint_stat_boot(
                [CELLS[n]["run"] for n in quad],
                lambda a: (a[3] - a[1]) - (a[2] - a[0]),
                iters=iters, seed=seed, level=INTERACTION_IC)
        else:
            rep[f"interaccion_{tag}"] = None
    # ---- Holm 53 celdas, aparte (los cuatro pares de los primarios)
    for a, b in (("D0p", "DT0"), ("D1", "DT1"),
                 ("T0p", "DT0"), ("T1p", "DT1")):
        if store.runs_in(CELLS[a]["run"]) and store.runs_in(
                CELLS[b]["run"]):
            rep["holm53"][f"{a}_vs_{b}"] = holm_cells(CELLS[a]["run"],
                                                      CELLS[b]["run"])
    # ---- descriptivos (misma mecánica que el análisis de jev68)
    desc, scan, lat = {}, {}, {}
    for name, cell in have.items():
        scan[name] = _raw_scan(cell["run"], cell["phases"], cell["mode"],
                               cell.get("case_ids"))
        lat[name] = _usage_stats(cell["run"], cell["phases"],
                                 cell.get("case_ids"))
    desc["vectores_crudos"] = scan
    desc["latencia_tokens"] = lat
    onoff = {}
    for tag, off, on in (("prob_d0", "F0p", "T0p"),
                         ("prob_d1", "F1p", "T1p"),
                         ("disc_d0", "D0p", "DT0"),
                         ("disc_d1", "D1", "DT1")):
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
        desc["on_off"] = onoff
    jev68_ref = {}
    for tag, runs in JEV68_DESCR.items():
        for k, run in runs.items():
            if store.runs_in(run):
                adj68, _ = score.adjusted(run)
                jev68_ref[f"{tag}/{k}"] = {"run": run, "adjusted": adj68}
    if jev68_ref:
        desc["jev68_descriptivo"] = jev68_ref
    agg = next((rep[k] for k in ("h1_d0", "h2_d0", "interaccion_d0")
                if isinstance(rep.get(k), dict) and rep[k].get("phases")),
               None)
    desc["baselines"] = _baseline_table(agg["phases"] if agg else None)
    rep["descriptivos"] = desc
    printer("\n## Clasificación pre-registrada (factorial JEV-76, "
            "IC98.75 por contraste; I descriptiva con IC95 conjunto)")
    for k, v in cls.items():
        printer(f"- {k}: {v}")
    for tag in ("d0", "d1"):
        ib = rep.get(f"interaccion_{tag}")
        if ib:
            printer(f"- I {tag} (descriptiva): "
                    f"{ib['stat']:+.1f} [{ib['lo']:+.1f},{ib['hi']:+.1f}] "
                    "IC95 conjunto")
        else:
            printer(f"- I {tag} (descriptiva): sin celdas evaluables")
    if rep["holm53"]:
        printer("\n## Holm 53 celdas (aparte, descriptivo)")
        for pair, rows in rep["holm53"].items():
            sig = [r for r in rows if r["p_holm"] < 0.05]
            printer(f"- {pair}: {len(sig)} celdas significativas tras "
                    f"Holm de {len(rows)}")
            for r in sig:
                printer(f"    {r['cell']}: b={r['b']} c={r['c']} "
                        f"p={r['p']:.4g} Holm={r['p_holm']:.4g}")
    printer("\n## Latencia y tokens por celda (coste API = 0: ejecución "
            "local sin facturación)")
    printer("| celda | n | ms media | ms mediana | tokens prompt | "
            "tokens completion | tokens razonamiento |")
    printer("|---|---:|---:|---:|---:|---:|---:|")
    for name, s in lat.items():
        printer(f"| {name} | {s['n']} | {score.fmt(s['ms_media'], 0)} | "
                f"{score.fmt(s['ms_mediana'], 0)} | {s['prompt_tokens']} | "
                f"{s['completion_tokens']} | {s['razonamiento_tokens']} |")
    for tag, o in onoff.items():
        printer(f"- on/off {tag} ({o['on']} vs {o['off']}): ms media "
                f"{score.fmt(o['ms_media_off'], 0)} → "
                f"{score.fmt(o['ms_media_on'], 0)}"
                + (f" (×{o['ms_ratio']:.2f})" if o["ms_ratio"] else "")
                + f", mediana {score.fmt(o['ms_mediana_off'], 0)} → "
                f"{score.fmt(o['ms_mediana_on'], 0)}; "
                f"completion {o['completion_off']} → "
                f"{o['completion_on']} (Δ {o['completion_delta']:+d}; "
                f"razonamiento on = {o['razonamiento_on']}), prompt "
                f"{o['prompt_off']} → {o['prompt_on']}")
    if jev68_ref:
        printer("\n## Referencia descriptiva JEV-68/71 (nunca control)")
        for k, v in jev68_ref.items():
            printer(f"- {k} {v['run']}: ajustado "
                    f"{v['adjusted'] and round(v['adjusted'], 2)}")
    printer("\n## Baselines de mayoría por fase (GT v4; ood excluida del "
            "agregado por baseline saturada)")
    printer("| fase | n | mayoría % | respuestas mayoritarias |")
    printer("|---|---:|---:|---|")
    for ph, b in desc["baselines"].items():
        ans = ", ".join(f"{q}={v['respuesta']}"
                        for q, v in b["mayoria"].items())
        printer(f"| {ph} | {b['n']} | {score.fmt(b['pct'])} | {ans} |")
    if out_json:
        with open(out_json, "w") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    return rep


# ---------------------------------------------------- análisis JEV-77
#
# MedGemma-27B frente a Gemma 3-27B-IT y Qwen FP8 (medgemma_jev77 §6):
# exactamente DOS contrastes confirmatorios, ambos en d0, con IC97,5 por
# contraste (Bonferroni sobre 2 ⇒ cobertura familiar nominal ≥ 95 %;
# compartir M-D0 no invalida Bonferroni). H1 = superioridad M−G ≥ +5;
# H2 = no inferioridad M−Q con margen −5. d1/4B/cascada y los subgrupos
# (papers32, department en las 9 fases, adv1–adv5) son descriptivos con
# IC95 nominal, sin cobertura conjunta con los primarios. Holm53 en diez
# familias separadas, también descriptivo.
JEV77_IC = 0.975
JEV77_PRIMARIES = (("H1", "GD0", "MD0", 5.0, "M-D0−G-D0 ≥+5"),
                   ("H2", "QD0p", "MD0", -5.0,
                    "M-D0−Q-D0′ ≥−5 (no inferioridad)"))
JEV77_DESCR = [  # (tag, a, b): Δ ajustado B−A, IC95 descriptivo
    ("prob_d0", "GP0", "MP0"),
    ("disc_d1_M_G", "GD1", "MD1"),
    ("disc_d1_M_Q", "QD1p", "MD1"),
    ("prob_d1", "GP1", "MP1"),
    ("b4_d0_disc", "G4D0", "M4D0"),
    ("b4_d0_prob", "G4P0", "M4P0"),
    ("b4_d1_disc", "G4D1", "M4D1"),
    ("b4_d1_prob", "G4P1", "M4P1"),
]
JEV77_HOLM = [("MD0", "GD0"), ("MP0", "GP0"), ("MD0", "QD0p"),
              ("MD1", "GD1"), ("MP1", "GP1"), ("MD1", "QD1p"),
              ("M4D0", "G4D0"), ("M4P0", "G4P0"),
              ("M4D1", "G4D1"), ("M4P1", "G4P1")]
JEV77_DEPT_PHASES = ["triage_es", "triage_en", "triage_ext_es",
                     "triage_ext_en", "adv1", "adv2", "adv3", "adv4",
                     "adv5"]
JEV77_ADV_PHASES = ["adv1", "adv2", "adv3", "adv4", "adv5"]
JEV77_CASCADE_AUDIT = "medgemma_27b_jev77_jevrev_audit"
JEV77_CASCADE_RAW = "medgemma_27b_jev77_jevrev_raw"
# el modelo efectivo del proveedor elegido se toma de la MISMA fuente
# que el adaptador Jev — OpenRouter sirve el alias ~typesafe/jev-latest
# (R40 §1); cambiar de proveedor en A4 exige enmienda del manifiesto
JEV77_CASCADE_REVIEWER = {"adapter": "jev", "provider": "openrouter",
                        "model": _JEV_PROVIDERS["openrouter"][2]}


def _audit_cascade77():
    """Cobertura y procedencia de la cascada híbrida jev77 (§5.3, R36
    §7): el contraste solo es evaluable con las 11 fases del audit
    COMPLETAS (cada caso con answers, sin errores), sin parada
    persistida en el registro durable del cupo y con la procedencia
    congelada — d1 == M-D0, revisor/host/manifest registrados en el raw
    y una única versión resuelta del revisor en todas las fases/casos.
    Cualquier falta se publica como NO EVALUABLE con su nota, nunca
    como un contraste sobre cobertura parcial."""
    rep = {"phases_ok": [], "missing": [], "errors": [], "bad_meta": [],
           "stopped": None, "versions": [], "evaluable": False,
           "note": None}
    audit, raw = JEV77_CASCADE_AUDIT, JEV77_CASCADE_RAW
    d1_run = CELLS_77["MD0"]["run"]
    bfile = store.ROOT / "logs" / "jev77_cascade.json"
    budget_version, budget_session, budget_rev = None, None, None
    if not bfile.exists():
        rep["bad_meta"].append("sin registro durable del cupo de cascada")
    else:
        try:
            bst = json.loads(bfile.read_text())
        except (OSError, ValueError):
            rep["bad_meta"].append("registro de cupo de cascada ilegible")
        else:
            if bst.get("stopped"):
                rep["stopped"] = bst["stopped"]
            rep["budget_requests"] = bst.get("requests")
            # el gasto declarado se valida contra el cupo congelado —
            # contador entero, no negativo y dentro de política (R39 §3)
            if not isinstance(rep["budget_requests"], int) \
                    or not (0 <= rep["budget_requests"]
                            <= JEV77_CASCADE_REQUESTS):
                rep["bad_meta"].append(
                    f"registro de cupo de cascada fuera de política: "
                    f"{rep['budget_requests']!r} (tope "
                    f"{JEV77_CASCADE_REQUESTS})")
            if not isinstance(bst.get("started_wall"), (int, float)):
                rep["bad_meta"].append(
                    "registro de cascada sin reloj de arranque")
            # la versión congelada en el presupuesto forma parte de la
            # comparación de versiones; proveedor/modelo y sesión son
            # la procedencia acreditada (R39 §3)
            budget_rev = bst.get("reviewer") or {}
            budget_version = budget_rev.get("resolved")
            budget_session = bst.get("session")
            if not budget_session:
                rep["bad_meta"].append(
                    "presupuesto de cascada sin sesión acreditada")
            # la identidad A4 del revisor es OBLIGATORIA y debe ser la
            # del contrato congelado (R40 §2): sin ella no hay
            # procedencia que auditar
            for k in ("adapter", "provider", "model", "resolved"):
                if not budget_rev.get(k):
                    rep["bad_meta"].append(
                        f"presupuesto de cascada sin revisor.{k} "
                        "congelado")
            for k, v in JEV77_CASCADE_REVIEWER.items():
                if budget_rev.get(k) and budget_rev[k] != v:
                    rep["bad_meta"].append(
                        f"revisor del presupuesto {k}={budget_rev[k]!r} "
                        f"!= contrato {v!r}")
    man_sha, man = None, None
    man_file = store.ROOT / "logs" / "qwen_manifest_jev77.json"
    try:
        man = json.loads(man_file.read_text())
    except (OSError, ValueError):
        rep["bad_meta"].append("manifiesto jev77 ausente o ilegible")
    else:
        man_sha = man.get("manifest_sha256")
        # hash obligatorio e íntegro: el declarado debe reproducirse
        # del contenido (R39 §3)
        if not man_sha or man_sha != _manifest_content_sha(man):
            rep["bad_meta"].append(
                "manifiesto jev77 sin sha válido o con sha que no "
                "cuadra con su contenido")
            man_sha = None
        mcaps = (man.get("policies") or {}).get("cascade") or {}
        # las políticas congeladas deben ser exactamente las efectivas
        if mcaps.get("requests") != JEV77_CASCADE_REQUESTS \
                or mcaps.get("wall_s") != JEV77_CASCADE_WALL_S \
                or mcaps.get("raw") != raw or mcaps.get("audit") != audit \
                or mcaps.get("reviewer") != JEV77_CASCADE_REVIEWER:
            rep["bad_meta"].append(
                "políticas de cascada del manifiesto divergen de las "
                "vigentes")
    from . import cascade as _casc
    versions = set()
    for ph in PHASES_ALL:
        qs, cases = load_phase(ph)
        adoc = store.load(audit, ph)
        rdoc = store.load(raw, ph)
        if adoc is None or rdoc is None:
            rep["missing"].append(ph)
            continue
        am, rm = adoc.get("meta") or {}, rdoc.get("meta") or {}
        if rm.get("d1") != d1_run:
            rep["bad_meta"].append(
                f"{ph}: raw d1 {rm.get('d1')!r} != {d1_run!r}")
        if am.get("d1") != d1_run or am.get("raw") != raw:
            rep["bad_meta"].append(
                f"{ph}: audit d1={am.get('d1')!r} raw={am.get('raw')!r}")
        # procedencia completa exigida en raw Y en fusión (R38 §7)
        for k in ("reviewer", "host", "manifest_sha256",
                  "questions_hash", "provider", "model", "session"):
            if not rm.get(k):
                rep["bad_meta"].append(f"{ph}: raw sin {k}")
        for k in ("host", "manifest_sha256", "session"):
            if not am.get(k):
                rep["bad_meta"].append(f"{ph}: fusión sin {k}")
        # y COMPATIBLE, no solo presente (R39 §3): hash del encargo en
        # raw y fusión, preguntas de revisión recalculadas, identidad y
        # sesión acreditadas por el presupuesto
        if man_sha is not None:
            if rm.get("manifest_sha256") != man_sha:
                rep["bad_meta"].append(
                    f"{ph}: manifiesto del raw "
                    f"{rm.get('manifest_sha256')!r} != el vigente "
                    f"{man_sha!r}")
            if am.get("manifest_sha256") != man_sha:
                rep["bad_meta"].append(
                    f"{ph}: manifiesto de la fusión "
                    f"{am.get('manifest_sha256')!r} != el vigente "
                    f"{man_sha!r}")
        if rm.get("questions_hash") is not None and \
                rm["questions_hash"] != questions_hash(
                    _casc.review_questions(qs, ph)):
            rep["bad_meta"].append(
                f"{ph}: questions_hash del raw incompatible con las "
                "preguntas de revisión vigentes")
        for k in ("provider", "model"):
            if budget_rev.get(k) is not None \
                    and rm.get(k) is not None and rm[k] != budget_rev[k]:
                rep["bad_meta"].append(
                    f"{ph}: {k} del raw {rm[k]!r} != el revisor "
                    f"acreditado {budget_rev[k]!r}")
        # el adaptador registrado en el raw debe ser el congelado en el
        # presupuesto (R40 §2)
        if budget_rev.get("adapter") is not None \
                and rm.get("reviewer") is not None \
                and rm["reviewer"] != budget_rev["adapter"]:
            rep["bad_meta"].append(
                f"{ph}: adaptador del raw {rm['reviewer']!r} != el "
                f"acreditado {budget_rev['adapter']!r}")
        if budget_session:
            if rm.get("session") != budget_session:
                rep["bad_meta"].append(
                    f"{ph}: sesión del raw {rm.get('session')!r} != "
                    f"la acreditada {budget_session!r}")
            if am.get("session") != budget_session:
                rep["bad_meta"].append(
                    f"{ph}: sesión de la fusión "
                    f"{am.get('session')!r} != la acreditada "
                    f"{budget_session!r}")
        v = rm.get("reviewer_resolved") or rm.get("resolved")
        if not v:
            rep["bad_meta"].append(
                f"{ph}: sin versión resuelta del revisor")
        else:
            versions.add(v)
        bad = [c.id for c in cases
               if "answers" not in ((adoc.get("cases") or {})
                                    .get(c.id) or {})]
        rep["errors"] += [f"{ph}/{i}" for i in bad]
        rbad = [c.id for c in cases
                if "answers" not in ((rdoc.get("cases") or {})
                                     .get(c.id) or {})]
        rep["errors"] += [f"{ph}/{i} (raw)" for i in rbad]
        for c in cases:
            # versión obligatoria POR CASO y coherente con la resuelta
            # de la fase (R38 §7): ausente o distinta = NO EVALUABLE
            rv = (((rdoc.get("cases") or {}).get(c.id) or {})
                  .get("reviewer_version"))
            if not rv:
                rep["bad_meta"].append(
                    f"{ph}/{c.id}: raw sin reviewer_version")
            else:
                versions.add(rv)
                if v and rv != v:
                    rep["bad_meta"].append(
                        f"{ph}/{c.id}: reviewer_version {rv} != "
                        f"resuelta de fase {v}")
        if not bad and not rbad:
            rep["phases_ok"].append(ph)
    if budget_version:
        versions.add(budget_version)
    if len(versions) > 1:
        rep["bad_meta"].append(
            f"versiones del revisor mezcladas {sorted(versions)}")
    rep["versions"] = sorted(versions)
    if rep["missing"]:
        rep["note"] = (f"cobertura parcial: faltan "
                       f"{len(rep['missing'])}/{len(PHASES_ALL)} fases")
    elif rep["stopped"]:
        rep["note"] = (f"parada persistida: "
                       f"{rep['stopped'].get('reason')}")
    elif rep["errors"]:
        rep["note"] = f"{len(rep['errors'])} casos sin fusión"
    elif rep["bad_meta"]:
        rep["note"] = f"procedencia incompleta ({rep['bad_meta'][0]})"
    rep["evaluable"] = rep["note"] is None and bool(rep["phases_ok"])
    return rep


def analyze_medgemma(out_json=None, iters=BOOT_ITERS, seed=BOOT_SEED,
                     printer=print):
    """Análisis pre-registrado de JEV-77 (medgemma_jev77 §6): H1/H2 en
    d0 con IC97,5, descriptivos IC95, subgrupos, Holm53 ×10 familias y
    la cascada híbrida aparte."""
    rep = {"profile": _PROFILE, "runs": {}, "classification": {},
           "holm53": {}}
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
    # primarios confirmatorios (§6.2): NO EVALUABLE ante cobertura,
    # visibilidad inválida o tope — nunca "refutada" por defecto
    for h, a, b, thr, etiqueta in JEV77_PRIMARIES:
        key = f"{h}: {etiqueta}"
        if not (ev(a) and ev(b)):
            rep[h.lower()] = None
            cls[key] = _no_eval(f"faltan runs evaluables {a}/{b}")
            continue
        dd = paired_delta(CELLS[a]["run"], CELLS[b]["run"], iters=iters,
                          seed=seed, level=JEV77_IC)
        rep[h.lower()] = dd
        if dd is None:
            cls[key] = _no_eval("sin fases pareadas completas")
        else:
            cls[key] = (_cls(dd["lo"] >= thr, dd["hi"] < thr)
                        + f" (Δ={dd['delta']:+.1f} "
                          f"[{dd['lo']:+.1f},{dd['hi']:+.1f}] IC97.5)")
    desc = {}
    deltas = {}
    for tag, a, b in JEV77_DESCR:
        deltas[tag] = (paired_delta(CELLS[a]["run"], CELLS[b]["run"],
                                    iters=iters, seed=seed, level=0.95)
                       if ev(a) and ev(b) else None)
    desc["deltas"] = deltas
    # subgrupos descriptivos (§6.3): delta de puntos medios, IC95, sin
    # ajuste de baseline — para los dos pares primarios d0
    subs = {}
    for htag, a, b in (("M_G", "GD0", "MD0"), ("M_Q", "QD0p", "MD0")):
        if not (ev(a) and ev(b)):
            subs[htag] = None
            continue
        ra, rb = CELLS[a]["run"], CELLS[b]["run"]
        subs[htag] = {
            "papers32": subset_delta(ra, rb, ["papers32"], iters=iters,
                                     seed=seed),
            "department": subset_delta(ra, rb, JEV77_DEPT_PHASES,
                                       qid="department", iters=iters,
                                       seed=seed),
            "adv1_5": subset_delta(ra, rb, JEV77_ADV_PHASES, iters=iters,
                                   seed=seed),
            "adv_por_fase": {ph: subset_delta(ra, rb, [ph], iters=iters,
                                              seed=seed)
                             for ph in JEV77_ADV_PHASES}}
    desc["subgrupos"] = subs
    # cascada híbrida M-D0 → Jev audit (§5.3): descriptiva; el contador
    # de red la ejecuta jevbench.jev77_cascade con cupo propio
    casc = {}
    for run in (JEV77_CASCADE_AUDIT, JEV77_CASCADE_RAW):
        if store.runs_in(run):
            adj, _ = score.adjusted(run)
            casc[run] = {"adjusted": adj}
    if store.runs_in(JEV77_CASCADE_AUDIT):
        # la parcialidad se publica como tal (R36 §7): el contraste
        # exige auditoría de cobertura+procedencia de las 11 fases —
        # un audit parcial no produce delta pareado
        casc["auditoria"] = _audit_cascade77()
        if casc["auditoria"]["evaluable"] and ev("MD0"):
            casc["vs_M_D0"] = paired_delta(CELLS["MD0"]["run"],
                                           JEV77_CASCADE_AUDIT,
                                           iters=iters, seed=seed,
                                           level=0.95)
        else:
            casc["vs_M_D0"] = None
            casc["note"] = (f"cascada NO EVALUABLE: "
                            f"{casc['auditoria']['note']}"
                            if casc["auditoria"]["note"]
                            else "cascada NO EVALUABLE: M-D0 no evaluable"
                            if not ev("MD0") else None)
    if casc:
        desc["cascada"] = casc
    # Holm53: diez familias separadas (§6.4), descriptivas
    for a, b in JEV77_HOLM:
        if store.runs_in(CELLS[a]["run"]) and store.runs_in(
                CELLS[b]["run"]):
            rep["holm53"][f"{a}_vs_{b}"] = holm_cells(CELLS[a]["run"],
                                                      CELLS[b]["run"])
    scan, lat = {}, {}
    for name, cell in have.items():
        scan[name] = _raw_scan(cell["run"], cell["phases"], cell["mode"],
                               cell.get("case_ids"))
        lat[name] = _usage_stats(cell["run"], cell["phases"],
                                 cell.get("case_ids"))
    desc["vectores_crudos"] = scan
    desc["latencia_tokens"] = lat
    agg = next((x for x in (rep.get("h1"), rep.get("h2"))
                if isinstance(x, dict) and x.get("phases")), None)
    desc["baselines"] = _baseline_table(agg["phases"] if agg else None)
    rep["descriptivos"] = desc
    printer("\n## Clasificación pre-registrada (JEV-77, IC97.5 por "
            "contraste — familia ≥95 % por Bonferroni sobre 2)")
    for k, v in cls.items():
        printer(f"- {k}: {v}")
    if rep["holm53"]:
        printer("\n## Holm 53 celdas (diez familias, descriptivo)")
        for pair, rows in rep["holm53"].items():
            sig = [r for r in rows if r["p_holm"] < 0.05]
            printer(f"- {pair}: {len(sig)} celdas significativas tras "
                    f"Holm de {len(rows)}")
    printer("\n## Latencia y tokens por celda (coste API = 0 en batería; "
            "la cascada API se contabiliza aparte)")
    printer("| celda | n | ms media | ms mediana | tokens prompt | "
            "tokens completion | tokens razonamiento |")
    printer("|---|---:|---:|---:|---:|---:|---:|")
    for name, s in lat.items():
        printer(f"| {name} | {s['n']} | {score.fmt(s['ms_media'], 0)} | "
                f"{score.fmt(s['ms_mediana'], 0)} | {s['prompt_tokens']} | "
                f"{s['completion_tokens']} | {s['razonamiento_tokens']} |")
    for tag, dd in deltas.items():
        if dd:
            printer(f"- {tag} (descriptivo IC95): "
                    f"{dd['delta']:+.1f} [{dd['lo']:+.1f},{dd['hi']:+.1f}]")
    for htag, sub in subs.items():
        if not sub:
            continue
        for k, v in sub.items():
            if k == "adv_por_fase":
                for ph, d in v.items():
                    if d:
                        printer(f"- {htag}/{ph} (descriptivo): "
                                f"{d['delta']:+.1f} "
                                f"[{d['lo']:+.1f},{d['hi']:+.1f}] IC95")
            elif v:
                printer(f"- {htag}/{k} (descriptivo): {v['delta']:+.1f} "
                        f"[{v['lo']:+.1f},{v['hi']:+.1f}] IC95")
    if casc:
        printer("\n## Cascada híbrida (descriptiva)")
        for run, c in casc.items():
            if "adjusted" in c:
                printer(f"- {run}: ajustado "
                        f"{c['adjusted'] and round(c['adjusted'], 2)}")
        if "vs_M_D0" in casc:
            d = casc["vs_M_D0"]
            if d:
                printer(f"- cascada−M-D0: {d['delta']:+.1f} "
                        f"[{d['lo']:+.1f},{d['hi']:+.1f}] IC95")
    printer("\n## Baselines de mayoría por fase (GT v4; ood excluida del "
            "agregado por baseline saturada)")
    printer("| fase | n | mayoría % | respuestas mayoritarias |")
    printer("|---|---:|---:|---|")
    for ph, b in desc["baselines"].items():
        ans = ", ".join(f"{q}={v['respuesta']}"
                        for q, v in b["mayoria"].items())
        printer(f"| {ph} | {b['n']} | {score.fmt(b['pct'])} | {ans} |")
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
    pr = sub.add_parser("prep", help="registro de preparación A3 (jev77): "
                                     "smoke/health previos — cupo propio "
                                     "de 150 peticiones en las 12.000 "
                                     "duraderas, sin abrir las 40 h")
    pr.add_argument("--requests", type=int, required=True)
    pr.add_argument("--wall-s", type=float, required=True)
    pr.add_argument("--note", default=None)
    bg = sub.add_parser("begin", help="registro del inicio A6 (jev77): "
                                      "crea la sesión antes de cargar el "
                                      "servidor — fija wall_t0 y la "
                                      "subsesión durable")
    bg.add_argument("--session", required=True)
    g = sub.add_parser(
        "gate", help="puerta de visibilidad de una combinación "
                     "(canario: observación, Enmienda 1)")
    g.add_argument("combo")
    g.add_argument("--session", required=True)
    g.add_argument("--new-session", action="store_true",
                   help="tras un reinicio del servidor: nueva sesión y puertas")
    g.add_argument("--instance", default=None,
                   choices=["transition", "restart", "subsession"],
                   help="jev77: clasificación declarada de la nueva "
                        "instancia (auto si se omite)")
    rn = sub.add_parser(
        "run", help="bloque de batería (calendario intercalado; pausa "
                    "cooperativa: crear el fichero .pause del perfil "
                    "termina el run limpio tras el caso en curso)")
    rn.add_argument("--session", required=False)
    rn.add_argument("--resume", action="store_true")
    rn.add_argument("--retry-errors", action="store_true")
    rn.add_argument("--new-session", action="store_true")
    rn.add_argument("--instance", default=None,
                    choices=["transition", "restart", "subsession"],
                    help="jev77: clasificación declarada de la nueva "
                         "instancia (auto si se omite)")
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
    an = sub.add_parser("analyze", help="análisis pre-registrado "
                                      "(factorial con --profile jev76)")
    an.add_argument("--json", default=None)
    an.add_argument("--iters", type=int, default=BOOT_ITERS)
    for sp in (r, pr, bg, g, rn, dg, an):
        sp.add_argument("--profile", default=None,
                        choices=sorted(PROFILES),
                        help="perfil de sesión (defecto jev68; jev76 usa "
                             "celdas, estado, manifiesto, puertas y "
                             "referencias propios del factorial)")
    args = ap.parse_args()
    if args.profile:
        _set_profile(args.profile)
    if args.cmd == "refs":
        build_refs(args.combo, _load_tokenizer(args.tokenizer),
                   out=Path(args.out) if args.out else None)
        return 0
    if args.cmd == "prep":
        return prep(requests=args.requests, wall_s=args.wall_s,
                    note=args.note)
    if args.cmd == "begin":
        return begin(session=args.session)
    if args.cmd == "gate":
        ok, _ = gate(args.combo, session=args.session,
                     new_session=args.new_session,
                     reason=args.instance)
        return 0 if ok else 1
    if args.cmd == "run":
        return run(session=args.session, resume=args.resume,
                   retry_errors=args.retry_errors,
                   new_session=args.new_session, dry_run=args.dry_run,
                   amend_manifest=args.amend_manifest,
                   reason=args.instance)
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
