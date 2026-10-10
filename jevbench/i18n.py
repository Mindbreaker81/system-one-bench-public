"""Traducción EN de las etiquetas generadas por el harness para la web y el sitio (JEV-91).

El texto editorial vive en fuentes paralelas (`docs/web/template.en.html`,
`docs/site_src/en/*.html`); este módulo cubre lo que el código genera: etiquetas de
`RUNS` en `web.py`/`site.py`, `env`, `cost_scope`, `output_modes`, notas de cobertura,
etiquetas de fase, fechas de versión y la copia EN de `assets/common.js`
(`assets/common.en.js`).

Los datos (cifras, ids de run, nombres de modelo y de fase) son idénticos en ambos
idiomas; solo se traducen los fragmentos de texto. `tr()` aplica, en orden,
coincidencias exactas de `STRINGS` y después los fragmentos de `FRAGMENTS`
(los más largos primero, para que «regla audit» gane a «audit»).
"""
import re

LANGS = ("es", "en")
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PHASE_LABEL_EN = {
    "triage_es": "Triage ES", "triage_en": "Triage EN",
    "triage_ext_es": "Extended triage ES", "triage_ext_en": "Extended triage EN",
    "papers32": "Papers", "adv1": "Adversarial 1", "adv2": "Adversarial 2",
    "adv3": "Adversarial 3", "adv4": "Adversarial 4", "adv5": "Adversarial 5",
}

# Nombre visible de los niveles score ("bajo: routine, no deadline" → "low: …").
LEVEL_NAME_EN = {"bajo": "low", "medio": "medium", "critico": "critical"}

# Coincidencia exacta de cadena completa (env / cost_scope largos, donde la traducción
# por fragmentos daría una gramática pobre).
STRINGS = {
    # web.RUN_EXTRA extra["env"]
    "API OpenRouter (respuestas luna-decisions + Jev; recombinación offline)":
        "OpenRouter API (luna-decisions answers + Jev; offline recombination)",
    "API OpenAI Decisions (SDK nativo)":
        "OpenAI Decisions API (native SDK)",
    "API OpenRouter (endpoint de decisiones)":
        "OpenRouter API (decisions endpoint)",
    "194 registros (coste registrado del endpoint; no factura del proveedor)":
        "194 records (endpoint-recorded cost; not the provider invoice)",

    "Decider-4B (DGX Spark GB10 · bf16) + revisor Claude Haiku 5.5 (API Anthropic · thinking adaptive)":
        "Decider-4B (DGX Spark GB10 · bf16) + reviewer Claude Haiku 5.5 (Anthropic API · adaptive thinking)",
    "Jev (API) + revisor Claude Haiku 5.5 (API Anthropic · thinking adaptive)":
        "Jev (API) + reviewer Claude Haiku 5.5 (Anthropic API · adaptive thinking)",
    "Decider-4B (DGX Spark GB10 · bf16) + revisor Clef-Flash (Intel Arc Pro B70 · XPU bf16)":
        "Decider-4B (DGX Spark GB10 · bf16) + reviewer Clef-Flash (Intel Arc Pro B70 · XPU bf16)",
    # web.RUN_EXTRA extra["cost_scope"]
    "188 éxitos homogéneos (no el subconjunto publicado de 6 fases)":
        "188 homogeneous successes (not the published 6-phase subset)",
    "194 respuestas del fusionado (costes registrados; no factura de los rechazos)":
        "194 merged-run answers (recorded costs; refused-attempt billing unavailable)",
    "194 registros (costes registrados, incluidos los intentos con refusal; no factura del proveedor)":
        "194 records (recorded costs, including refusal attempts; not the provider invoice)",
    "194 registros retenidos (costes registrados; no factura del proveedor)":
        "194 retained records (recorded costs; not the provider invoice)",
    "194 registros retenidos; COTA INFERIOR: la primera respuesta de E11 (desviación) no tiene coste recuperado":
        "194 retained records; LOWER BOUND: E11's first answer (deviation) has no recovered cost",
    "coste API no registrado (endpoint local sin tarifa; electricidad y hardware no medidos); "
    "latencia = mediana del resumen del scorer sobre las 9 fases base+nuevas (154 registros)":
        "API cost not recorded (local endpoint with no API pricing; electricity and hardware not measured); "
        "latency = upper median of the scorer summary over the 9 base+new phases (154 records)",
}

# Fragmentos recurrentes, ordenados de más largo a más corto en la aplicación.
FRAGMENTS = [
    # etiquetas de runs
    ("regla audit", "audit rule"),
    ("regla review", "review rule"),
    ("si rechaza", "on refusal"),
    ("réplica r2", "replica r2"),
    ("sin preguntas", "blind"),
    ("sin esquema forzado", "no forced schema"),
    ("sin esquema", "no schema"),
    ("sin structured", "structured=false"),
    ("sin thinking", "thinking off"),
    ("esquema en prompt", "schema in prompt"),
    ("discrete+esquema", "discrete+schema"),
    ("discrete vía adapter", "discrete via adapter"),
    ("1 lectura", "1 read"),
    ("(trunc)", "(truncated)"),
    ("(primario; cobertura incompleta; desviación de parada)",
     "(primary; incomplete coverage; stopping-rule deviation)"),
    ("(secundario descriptivo; cobertura incompleta)",
     "(descriptive secondary; incomplete coverage)"),
    # env
    ("API Anthropic", "Anthropic API"),
    ("API OpenRouter", "OpenRouter API"),
    ("API OpenAI", "OpenAI API"),
    ("API Cerebras", "Cerebras API"),
    ("API TypeSafe", "TypeSafe API"),
    ("API Respan", "Respan API"),
    ("API openai", "OpenAI API"),
    ("API anthropic", "Anthropic API"),
    ("API cerebras", "Cerebras API"),
    ("API nativa OpenAI", "native OpenAI API"),
    ("API openrouter", "OpenRouter API"),
    ("API typesafe", "TypeSafe API"),
    ("API respan", "Respan API"),
    ("(versiones mixtas)", "(mixed versions)"),
    ("Endpoint compatible OpenAI", "OpenAI-compatible endpoint"),
    ("Endpoint SystemOne · hardware no registrado", "SystemOne endpoint · unrecorded hardware"),
    ("CPU local", "local CPU"),
    ("esquema no inyectado", "schema not injected"),
    ("lecturas estructuradas", "structured reads"),
    ("gramática restringida", "constrained grammar"),
    ("FP8 oficial", "official FP8"),
    ("NVFP4 comunidad", "community NVFP4"),
    ("+ revisor ", "+ reviewer "),
    ("revisor ", "reviewer "),
    # env compuesto en site.build
    ("coste/latencia:", "cost/latency:"),
    (" · salida: ", " · output: "),
    # llm_output_modes
    (" · estructurada (structured=true)", " · structured (structured=true)"),
    (" · sin esquema forzado (structured=false)", " · no forced schema (structured=false)"),
    (" · no registrada", " · not recorded"),
    ("modo no registrado", "unrecorded mode"),
]


def tr(text, lang="en"):
    """Traduce una etiqueta generada (run, env, cost_scope, output mode) al inglés."""
    if lang == "es" or text is None:
        return text
    if text in STRINGS:
        return STRINGS[text]
    for es, en in FRAGMENTS:
        if es in text:
            text = text.replace(es, en)
    return text


def phase_label(ph, lang="en"):
    """Etiqueta pública de una fase; el ES está en web.PHASE_LABEL."""
    return PHASE_LABEL_EN.get(ph, ph)


def coverage_note(kind, n_ok, n_total, n_errors, n_incomplete, n_missing, n_phases, adj_scored,
                  lang="en"):
    """Nota de cobertura de run_coverage, con las mismas cifras en ambos idiomas."""
    if lang == "es":
        return None
    parts = [f"{n_ok}/{n_total}"]
    if n_errors:
        parts.append(f"{n_errors} provider refusal" + ("s" if n_errors != 1 else ""))
    if kind == "unmeasured":
        parts.append(f"not measured in {n_missing} of {n_phases} sets")
    elif kind == "errors":
        parts.append(f"{n_incomplete} incomplete phase" + ("s" if n_incomplete != 1 else ""))
    elif kind == "mixed":
        parts.append(f"{n_incomplete} incomplete · {n_missing} not measured")
    parts.append(f"mean over {adj_scored} phases")
    return " · ".join(parts)


# --- assets/common.js → assets/common.en.js ---------------------------------
# Sustituciones exactas de literales JS (con sus comillas) para generar la copia EN.
# Los literales entre comillas se sustituyen con comillas incluidas para no tocar
# subcadenas («no» no debe romper «noul»). Las claves de localStorage no cambian.
JS_STRINGS = {
    # rutas de datos: la copia EN vive en site/en/ y comparte site/data/ con el ES
    '"data/meta.json"': '"../data/meta.en.json"',
    '"data/cases.json"': '"../data/cases.json"',
    "data/answers/": "../data/answers/",
    "`No se pudo cargar ${path} (${r.status})`": "`Could not load ${path} (${r.status})`",
    '"Todo el triaje (ES + EN, normal y ampliado)"': '"All triage (ES + EN, standard and extended)"',
    '"Adversarial 3 + 4 + 5 (equilibrados)"': '"Adversarial 3 + 4 + 5 (balanced)"',
    '"Departamento"': '"Department"',
    '"Urgencia"': '"Urgency"',
    '"Clínico"': '"Clinical"',
    '"Hostil"': '"Hostile"',
    '"Responder hoy"': '"Answer today"',
    '"Relevancia"': '"Relevance"',
    '"Dominio"': '"Domain"',
    '"Diseño"': '"Design"',
    '"Profundidad de lectura"': '"Reading depth"',
    '"Cambia la práctica"': '"Practice change"',
    '"Broncoscopia"': '"Bronchoscopy"',
    '"Consulta externa"': '"Outpatient clinic"',
    '"Urgencias"': '"Emergency"',
    '"Admin"': '"Admin"',
    '"Neumo. intervencionista"': '"Interventional pulm."',
    '"Oncología"': '"Oncology"',
    '"IA / radiología"': '"AI / radiology"',
    '"Neumología general"': '"General pulmonology"',
    '"Otro"': '"Other"',
    '"Ensayo aleatorizado"': '"Randomized trial"',
    '"Metaanálisis / RS"': '"Meta-analysis / SR"',
    '"Cohorte / diagnóstico"': '"Cohort / diagnostic"',
    '"Revisión narrativa"': '"Narrative review"',
    '"Ciencia básica"': '"Basic science"',
    '"Texto completo"': '"Full text"',
    '"Solo abstract"': '"Abstract only"',
    '"Saltar"': '"Skip"',
    '"rechazo"; // pregunta rechazada (JEV-78): sin decisión, 0 puntos':
        '"rejection"; // rejected question (JEV-78): no decision, 0 points',
    '"sí"': '"yes"',
    '"acierto"': '"correct"',
    '"a un nivel"': '"off by one"',
    '"fallo"': '"wrong"',
    '" · desequilibrado"': '" · unbalanced"',
    '`No se pudieron cargar los datos: ${err.message}. Si abres el sitio como fichero local, '
    'sírvelo con "python3 -m http.server" desde la carpeta site/.`':
        '`Could not load the data: ${err.message}. If you open the site as a local file, '
        'serve it with "python3 -m http.server" from the site/ folder.`',
}


# Inventario explícito de literales compartidos de common.js (claves de datos,
# identificadores, rutas, eventos DOM, variables CSS, valores wire, símbolos):
# se publican iguales en ambos idiomas. Todo literal nuevo en la salida debe
# estar aquí o ser un valor de JS_STRINGS — si no, la generación se detiene.
JS_SHARED = frozenset({
    '${levelName(q, e[0])} (${e[0].toFixed(2)})',
    '${ph.label} (${ph.n})${p === "adv1" || p === "adv2" ? " · unbalanced" : ""}',
    '(prefers-color-scheme: dark)',
    '--f-anyjev',
    '--f-clef',
    '--f-clm',
    '--f-decider',
    '--f-diffusiongemma',
    '--f-gliner',
    '--f-jev',
    '--f-julia',
    '--f-laya',
    '--f-llm',
    '--f-medgemma',
    '--f-microsoft',
    '--f-nimble',
    '--f-respan',
    '--f-strands',
    '--f-tev1',
    '../data/answers/${encodeURIComponent(id)}.json',
    ':',
    '< 0.001',
    'adv1',
    'adv2',
    'adv3',
    'adv4',
    'adv5',
    'aria-hidden',
    'bancojev:',
    'blur',
    'change',
    'choice',
    'class',
    'data-theme',
    'div',
    'focus',
    'http://www.w3.org/2000/svg',
    'ic',
    'k',
    'no',
    'note warn',
    'noul',
    'on',
    'option',
    'p',
    'papers32',
    'pointerleave',
    'pointermove',
    'px',
    'resize',
    'score',
    'span',
    'text',
    'tip',
    'tooltip',
    'triage_en',
    'triage_es',
    'triage_ext_en',
    'triage_ext_es',
    'true',
    'v bad',
    'v half',
    'v ok',
    '—',
    '≈',
    '✓',
    '✗',
})
# Palabras inequívocamente españolas: un literal nuevo con cualquiera de ellas en la
# salida EN es un texto visible sin traducir y rompe la generación.
_JS_ES_WORDS = re.compile(
    r"\b(un|una|unos|unas|los|las|el|del|al|lo|que|con|sin|para|pero|porque|"
    r"sobre|entre|hasta|desde|donde|cuando|mientras|también|aunque|según|hacia|"
    r"tras|ante|todo|toda|todos|todas|otro|otra|otros|otras|mismo|misma|este|"
    r"esta|estos|estas|ese|esa|eso|aquí|así|sí|más|menos|muy|solo|sólo|hay|"
    r"están|está|son|ser|tiene|tienen|puede|pueden|debe|deben|cada|ningún|"
    r"ninguna|ni|ya|aún|su|sus|se|nos|caso|casos|dato|datos|fichero|cargar|"
    r"cargado|respuesta|respuestas|pregunta|preguntas|fase|fases|conjunto|"
    r"página|gráfico|revisor|revisores|regla|reglas|triaje|cascada|pasada|"
    r"pasadas|mayoría|cifra|cifras|hito|hitos|manipulación|manipulado|"
    r"desequilibrado|salida|entrada|nombre|versión|mensaje|sitio|carpeta|"
    r"éxito|éxitos|nuevo|nueva|detalle|resumen|correcto|incorrecto|nulo|"
    r"verdadero|falso|rechazo|rechazado|rechazada|acierto|fallo|discreta|"
    r"probabilidades|estructurada|inyectado|esquema|comunidad|oficial|"
    r"restringida|lectura|lecturas|primario|secundario|descriptivo|etiqueta)\b",
    re.I)
_JS_LITERAL = re.compile(r'"([^"\\\n]*(?:\\.[^"\\\n]*)*)"|'
                         r"'([^'\\\n]*(?:\\.[^'\\\n]*)*)'|"
                         r"`([^`\\]*(?:\\.[^`\\]*)*)`")


def _literal_content(quoted):
    """Contenido interno de un literal de JS_STRINGS (sin las comillas exteriores)."""
    q = quoted.strip()
    if q and q[0] in '"\'`':
        inner = q[1:]
        return inner[:inner.find(q[0])]
    return q


# Literales que sí pueden salir en la copia EN: los valores ya traducidos.
_JS_OUT_VALUES = {_literal_content(v) for v in JS_STRINGS.values()}


def translate_js(src):
    """Genera la variante EN de assets/common.js aplicando JS_STRINGS.

    Contrato estricto (R86/R87): cada literal registrado debe estar presente en la
    fuente y, tras sustituir, todo literal de la salida debe estar en el inventario
    explícito JS_SHARED (datos/identificadores compartidos) o ser un valor de
    JS_STRINGS. Un literal nuevo —español o no— detiene la generación hasta que se
    registre; no es una excepción heurística por forma de la cadena.
    """
    out = src
    for es, en in JS_STRINGS.items():
        if es not in out:
            raise SystemExit(f"i18n: literal de common.js sin encontrar: {es[:60]!r}")
        out = out.replace(es, en)
    for m in _JS_LITERAL.finditer(out):
        lit = next(g for g in m.groups() if g is not None)
        if not lit.strip() or lit in JS_SHARED or lit in _JS_OUT_VALUES:
            continue
        if ES_ACCENTS.search(lit) or _JS_ES_WORDS.search(lit):
            raise SystemExit(f"i18n: literal de common.js sin traducir: {lit[:60]!r}")
        raise SystemExit(f"i18n: literal nuevo de common.js sin registrar "
                         f"(añadir a JS_STRINGS o JS_SHARED): {lit[:60]!r}")
    return out


# Palabras españolas frecuentes que no deben quedar en el texto visible EN.
# Las excepciones de tests/test_i18n_paridad.py las documenta el propio test.
ES_STOPWORDS = re.compile(
    r"\b(del|frente|sin|según|ajustado|ajustada|revisor|revisores|revisora|pasada|pasadas|"
    r"mayoría|casos|caso|pregunta|preguntas|respuesta|respuestas|regla|reglas|triaje|"
    r"cascada|hito|hitos|conjunto|cifra|cifras|gráfico|página|después|también|pero|porque|"
    r"aunque|sobre|entre|hasta|desde|donde|cuando|mientras|todos|todas|cada|otro|otra|"
    r"mismo|misma|este|esta|estos|estas|ese|esa|aquí|así|sí|más|menos|muy|solo|hay|los|las|"
    r"una|unos|unas|para|por|con|que|al|su|sus|lo|la|el|de|en|y|o)\b", re.I)
ES_ACCENTS = re.compile(r"[áéíóúñ¿¡]")
