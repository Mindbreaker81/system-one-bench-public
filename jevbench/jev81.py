"""JEV-81 — fallback por rechazo, rechazo como alerta, repetibilidad.

Pre-registro: docs/infra_runs/luna_decisions_jev81.md. Solo stdlib; lee
results/ y no escribe en los runs existentes — el run fusionado
`jev_luna_decisions_fb` solo se materializa con `fallback --write` y
jamás sobrescribe un destino existente.

Reglas fijadas (R48; nada de lo demás es oficial):
  1) fallback sin parámetros: registro con error (ausencia/rechazo,
     cualquier tipo — desglosado) -> respuesta de jev_v3 en ese caso;
  2) alerta: positivo = NEGATIVA DEL PROVEEDOR (error HTTP con «refused»),
     distinta de timeout/transporte/fallo local (desglosados aparte);
     verdad = `manipulated == 1` en el GT de adv3/4/5 (adv2 descriptivo);
  3) repetibilidad: réplica `jev_luna_decisions_r2` (1 pasada + 1
     --retry-errors, como r1); acuerdo/Δp sobre éxitos emparejados;
     Δ ajustado solo si las fases completas coinciden en ambas réplicas;
     si cambia la versión servida se informa y no es repetibilidad.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from . import metrics as M, score, store
from .battery import DATA, load_phase, questions_hash
from .jev67 import clopper_pearson, holm

LUNA = "jev_luna_decisions"
JEV = "jev_v3"
FB_RUN = "jev_luna_decisions_fb"
R2_RUN = "jev_luna_decisions_r2"
ALERT_PHASES = ("adv2", "adv3", "adv4", "adv5")
# solo estos ficheros de datos llevan la etiqueta GT `manipulated`
TRUTH_PHASES = ("adv3", "adv4", "adv5")
AGREEMENT_REF = 0.97
FB_RULE = ("registro con error en el run primario (rechazo del "
           "proveedor, timeout, transporte o fallo local — desglosado) "
           "-> respuesta de jev_v3 en ese caso; en otro caso, la del "
           "run primario")


def _iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def error_kind(rec):
    """'rejection' (negativa del proveedor: HTTP 502 parseado +
    «refused to answer» — el patrón documentado), 'timeout',
    'transport' (HTTP sin negativa, conexión rechazada, red), 'local'
    (parseo/contrato), 'other', 'missing' (sin registro) o None
    (respuesta válida). Solo mensaje/estado del error — nunca el id del
    caso ni el GT."""
    if not isinstance(rec, dict):
        return "missing"
    err = rec.get("error")
    if err is None:
        return None
    if not isinstance(err, str):
        return "other"
    low = err.lower()
    m = re.search(r"http error (\d+)", low)
    if m:
        # negativa documentada: estado 502 exacto + «refused to answer»
        if m.group(1) == "502" and "refused to answer" in low:
            return "rejection"
        return "transport"
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if ("malform" in low or "valid" in low or "schema" in low
            or "parse" in low or "local" in low):
        return "local"
    if ("connection" in low or "network" in low or "refused" in low
            or "econn" in low):
        return "transport"
    return "other"


# IDs retirados del GT vigente (v4): conservados en las fuentes
# históricas, fuera del universo evaluable — data/GT_CHANGELOG.md
# (P02 duplicaba el PMID de P03; JEV-73). Cualquier otro id extra
# sigue siendo error de entrada.
RETIRED_GT_IDS = {"papers32": {"P02"}}


def _has_error(rec):
    """Registro sin respuesta utilizable (cualquier tipo de error) —
    criterio del FALLBACK; la alerta usa error_kind == 'rejection'."""
    return error_kind(rec) is not None


def _manipulated_truth():
    """{(phase, case_id): bool} estricto del GT (`manipulated == 1`) +
    casos con etiqueta ausente/inválida -> error de entrada, no honesto.
    adv2 no lleva el campo y queda fuera: solo descriptivo."""
    truth, invalid = {}, []
    for ph in TRUTH_PHASES:
        _, cases = load_phase(ph)
        for c in cases:
            v = c.gt.get("manipulated")
            if v not in (0, 1, True, False):
                invalid.append(f"{ph}/{c.id}")
            else:
                truth[(ph, c.id)] = bool(v)
    return truth, invalid


# ------------------------------------------------- validación de inputs

def _validate_universe(run, phases=None, printer=print):
    """El run debe cubrir TODAS las fases pedidas con TODOS los ids de la
    batería fijada y questions_hash igual al de las preguntas actuales.
    Ausencias = error explícito de entrada (no «no evaluado»)."""
    problems = []
    for ph in (phases or score.ADJ_PHASES):
        doc = store.load(run, ph)
        if doc is None:
            problems.append(f"{ph}: fase ausente en {run}")
            continue
        qs, cases = load_phase(ph)
        recs = doc.get("cases") or {}
        ids = {c.id for c in cases}
        for cid in sorted(ids - set(recs)):
            problems.append(f"{ph}/{cid}: registro ausente en {run}")
        retired = RETIRED_GT_IDS.get(ph, set())
        for cid in sorted(set(recs) - ids - retired):
            problems.append(f"{ph}/{cid}: id ajeno a la batería en {run}")
        for cid in sorted(set(recs) & retired):
            pass   # retirado del GT vigente: permitido, nunca evaluado
        qh = (doc.get("meta") or {}).get("questions_hash")
        cur = questions_hash(qs)
        if qh != cur:
            problems.append(f"{ph}: questions_hash {qh!r} != vigente "
                            f"{cur!r} en {run}")
    if problems:
        for p in problems:
            printer(f"ERROR entrada: {p}")
        raise SystemExit(f"{run}: {len(problems)} problema(s) de "
                         "cobertura/hash — no se calcula nada")


def _sources_compatible(run_a, run_b, phases=None, printer=print):
    """Las dos fuentes cubren el mismo universo validado y comparten
    questions_hash por fase (registrado en la salida)."""
    _validate_universe(run_a, phases, printer)
    _validate_universe(run_b, phases, printer)
    problems = []
    for ph in (phases or score.ADJ_PHASES):
        ha = ((store.load(run_a, ph) or {}).get("meta") or {}) \
            .get("questions_hash")
        hb = ((store.load(run_b, ph) or {}).get("meta") or {}) \
            .get("questions_hash")
        if ha != hb:
            problems.append(f"{ph}: questions_hash {run_a}={ha!r} != "
                            f"{run_b}={hb!r}")
    if problems:
        for p in problems:
            printer(f"ERROR entrada: {p}")
        raise SystemExit("fuentes con questions_hash distintos — no se "
                         "mezclan predicciones")
    return {ph: (store.load(run_a, ph) or {}).get("meta", {})
            .get("questions_hash")
            for ph in (phases or score.ADJ_PHASES)}


def _current_ids(phase):
    """Ids evaluables del GT vigente (sin los retirados)."""
    _, cases = load_phase(phase)
    return [c.id for c in cases]


def _truth_validated(printer=print):
    """GT `manipulated` presente y 0/1 en los 60 casos adv3–5; ausente o
    inválido = error de entrada."""
    truth, invalid = _manipulated_truth()
    if invalid:
        for p in invalid:
            printer(f"ERROR entrada: GT manipulated ausente/inválido "
                    f"en {p}")
        raise SystemExit(f"{len(invalid)} caso(s) sin GT manipulated "
                         "0/1 — no se calcula la alerta")
    return truth


def _gt_fingerprint():
    """sha12 del mapa truth ordenado: qué GT se combinó, en la salida."""
    truth, _ = _manipulated_truth()
    payload = json.dumps(sorted(truth.items()), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# ---------------------------------------------------------- 1. fallback

def merged_docs(luna=LUNA, jev=JEV, validate=True, printer=print):
    """{fase: doc fusionado} según la regla fijada. Procedencia por caso:
    `fallback_from` = run fuente de la sustitución; los errores del
    primario se desglosan por tipo (`error_kind` por caso). Si el
    respaldo no tiene el caso, el error se conserva y se marca."""
    if validate:
        qhashes = _sources_compatible(luna, jev, printer=printer)
    else:
        qhashes = None
    docs, per_phase = {}, {}
    for ph in score.ADJ_PHASES:
        ldoc = store.load(luna, ph)
        if ldoc is None:
            if not validate:
                continue
            raise SystemExit(f"{ph}: fase ausente en {luna}")
        jdoc = store.load(jev, ph) or {}
        jcases = jdoc.get("cases") or {}
        cur_ids = set(_current_ids(ph))
        cases, n_fb, kinds = {}, 0, {}
        for cid, rec in (ldoc.get("cases") or {}).items():
            if cid not in cur_ids:
                continue      # retirado del GT vigente (p. ej. P02)
            kind = error_kind(rec)
            if kind is not None:
                kinds[kind] = kinds.get(kind, 0) + 1
            if kind is not None:
                jrec = jcases.get(cid)
                if jrec is None or error_kind(jrec) is not None:
                    cases[cid] = {**(rec or {}),
                                  "fallback_from": None}
                    continue
                cases[cid] = dict(jrec)
                cases[cid]["fallback_from"] = jev
                n_fb += 1
            else:
                cases[cid] = rec
        meta = dict(ldoc.get("meta") or {})
        meta.update({"adapter": "jev81_fallback", "rule": FB_RULE,
                     "sources": {"primary": luna, "fallback": jev},
                     "n_fallback": n_fb,
                     "error_kinds": kinds,
                     "questions_hash": (qhashes or {}).get(
                         ph, meta.get("questions_hash")),
                     "merged_at": _iso()})
        docs[ph] = {"meta": meta, "cases": cases}
        per_phase[ph] = {"n": len(cases), "n_fallback": n_fb,
                         "error_kinds": kinds}
    return docs, per_phase


def _doc_score(doc, phase):
    """Predicciones/aciertos de un doc en memoria con la matemática del
    scorer (misma normalización, puntos por pregunta y hits estrictos)."""
    qs, cases = load_phase(phase)
    recs = (doc or {}).get("cases") or {}
    preds, missing = {}, []
    for c in cases:
        r = recs.get(c.id)
        if _has_error(r) or not isinstance(r.get("answers"), dict):
            missing.append(c.id)
            continue
        preds[c.id] = {q: M.normalize(r["answers"][q], qs[q]) for q in qs}
    per_case = [sum(M.point(qs[q], preds[c.id][q], c.gt[q]) for q in qs)
                / len(qs) for c in cases if c.id in preds]
    hits = {q: [M.exact(qs[q], preds[c.id][q], c.gt[q])
                if c.id in preds else False for c in cases] for q in qs}
    return {"phase": phase, "n": len(cases), "n_ok": len(preds),
            "errors": missing, "preds": preds, "hits": hits,
            "per_case": per_case,
            "pct": (100 * sum(per_case) / len(per_case)
                    if per_case else float("nan"))}


def _adjusted_phases(run=None, docs=None):
    """(lista de fases completas y puntuables, {fase: valor ajustado})
    de un run guardado o de docs en memoria — la base del Δ entre
    réplicas (solo sobre las mismas fases completas)."""
    phases, vals = [], {}
    for ph in score.ADJ_PHASES:
        if docs is not None:
            doc = docs.get(ph)
            if doc is None:
                continue
            s = _doc_score(doc, ph)
            pct, n_ok, n = s["pct"], s["n_ok"], s["n"]
        else:
            s = score.score_run(run, ph)
            if s is None:
                continue
            pct, n_ok, n = s["pct"], s["n_ok"], s["n"]
        b = score.baseline(ph)["pct"]
        if n_ok == n and b < 100:
            phases.append(ph)
            vals[ph] = (pct - b) / (100 - b)
    return phases, vals


def fallback_report(luna=LUNA, jev=JEV, docs=None):
    """Ajustado oficial del run fusionado + McNemar-Holm (familia
    completa por referencia) vs jev y vs luna + coste efectivo
    registrado (primario íntegro + respaldo solo en sustituidos)."""
    if docs is None:
        docs, _ = merged_docs(luna, jev)
    vals, phases = [], {}
    for ph in score.ADJ_PHASES:
        doc = docs.get(ph)
        if doc is None:
            continue
        s = _doc_score(doc, ph)
        phases[ph] = s
        b = score.baseline(ph)["pct"]
        if s["n_ok"] == s["n"] and b < 100:
            vals.append((s["pct"] - b) / (100 - b))
    adj = 100 * sum(vals) / len(vals) if vals else None

    def holm_vs(ref_run):
        rows = []
        for ph, s in phases.items():
            ref = score.score_run(ref_run, ph)
            if ref is None:
                continue
            for q in sorted(s["hits"]):
                b_, c_, p = M.mcnemar(ref["hits"][q], s["hits"][q])
                rows.append({"phase": ph, "q": q, "b": b_, "c": c_,
                             "p": p})
        for r, pa in zip(rows, holm([r["p"] for r in rows])):
            r["p_holm"] = pa
        return rows

    # coste: suma de lo REGISTRADO — primario desde su fuente íntegra
    # (los rechazos pueden tener coste observado), respaldo solo en los
    # sustituidos; costes desconocidos se contabilizan aparte, no = 0
    cost_primary = cost_fb = 0.0
    unknown_primary, unknown_fb = [], []
    for ph in score.ADJ_PHASES:
        ldoc = store.load(luna, ph) or {}
        jdoc = store.load(jev, ph) or {}
        doc = docs.get(ph)
        cur = set(_current_ids(ph))
        for cid, lrec in (ldoc.get("cases") or {}).items():
            if cid not in cur:
                continue      # retirado del GT vigente
            if lrec.get("cost") is not None:
                cost_primary += lrec["cost"]
            else:
                unknown_primary.append(f"{ph}/{cid}")
        for cid, mrec in ((doc or {}).get("cases") or {}).items():
            if mrec.get("fallback_from") == jev:
                jrec = (jdoc.get("cases") or {}).get(cid) or {}
                if jrec.get("cost") is not None:
                    cost_fb += jrec["cost"]
                else:
                    unknown_fb.append(f"{ph}/{cid}")
    return {"run": FB_RUN, "adjusted": adj, "n_phases": len(vals),
            "phases": phases, "mcnemar_vs_jev": holm_vs(jev),
            "mcnemar_vs_luna": holm_vs(luna),
            "cost": {"primary": cost_primary, "fallback": cost_fb,
                     "total": cost_primary + cost_fb,
                     "unknown_primary": unknown_primary,
                     "unknown_fallback": unknown_fb},
            "coverage": _final_coverage(docs),
            "provenance": {"questions_hash": _qhash_map(luna),
                           "source_sha": _source_sha(luna, jev),
                           "gt_scoring_sha": _gt_scoring_sha()}}


def _qhash_map(run):
    return {ph: ((store.load(run, ph) or {}).get("meta") or {})
            .get("questions_hash") for ph in score.ADJ_PHASES
            if store.load(run, ph) is not None}


def _source_sha(*runs):
    """sha12 por fichero JSON fuente ({run/fase: sha}) — qué bytes de
    predicciones se combinaron, no solo el hash de preguntas."""
    out = {}
    for run in runs:
        for ph in score.ADJ_PHASES:
            p = store.path(run, ph)
            if p.exists():
                out[f"{run}/{ph}"] = hashlib.sha256(
                    p.read_bytes()).hexdigest()[:12]
    return out


def _gt_scoring_sha():
    """sha12 del GT usado para puntuar/líneas base (por fase e id) —
    referencia inmutable verificable del GT aplicado en fallback y
    repeat."""
    out = {}
    for ph in score.ADJ_PHASES:
        _, cases = load_phase(ph)
        out[ph] = {c.id: c.gt for c in cases}
    return hashlib.sha256(
        json.dumps(out, sort_keys=True, default=str,
                   separators=(",", ":")).encode()).hexdigest()[:12]


def _gt_files_sha():
    """sha12 de los ficheros GT de la alerta (adv3–5)."""
    out = {}
    for ph, fn in (("adv3", "adversarial3_cases.json"),
                   ("adv4", "adversarial4_cases.json"),
                   ("adv5", "adversarial5_cases.json")):
        out[ph] = hashlib.sha256((DATA / fn).read_bytes()).hexdigest()[:12]
    return out


def _final_coverage(docs):
    """Casos donde primario y respaldo fallan -> el error se conserva y
    la fase queda incompleta. Cobertura final declarada, explícita."""
    uncovered, complete = [], 0
    for ph, doc in docs.items():
        cur = set(_current_ids(ph))
        bad = sorted(cid for cid, r in (doc.get("cases") or {}).items()
                     if cid in cur and _has_error(r))
        uncovered += [f"{ph}/{c}" for c in bad]
        complete += not bad
    return {"uncovered": uncovered, "phases_complete": complete,
            "n_phases": len(docs)}


def write_fallback(luna=LUNA, jev=JEV, printer=print):
    """Escribe el run fusionado SOLO si el destino no existe — nunca
    sobrescribe ni borra resultados existentes (aborta antes de guardar
    ninguna fase)."""
    if store.runs_in(FB_RUN):
        raise SystemExit(
            f"results/{FB_RUN}/ ya existe: {store.runs_in(FB_RUN)} — "
            "no se sobrescribe; bórralo a mano si quieres regenerar")
    docs, per_phase = merged_docs(luna, jev, printer=printer)
    for ph, doc in docs.items():
        store.save(FB_RUN, ph, doc)
    for ph, pp in per_phase.items():
        printer(f"{ph}: {pp['n']} casos, {pp['n_fallback']} del fallback")
    printer(f"run fusionado escrito en results/{FB_RUN}/")
    return docs


# ----------------------------------------------------------- 2. alerta

def alert_report(run=LUNA):
    """Rechazo como alerta de manipulación (pre-registrado, §2):
    positivo = negativa del proveedor (error HTTP con «refused»); verdad
    = manipulated==1 del GT (validado 0/1 en los 60 casos adv3–5).
    adv2 descriptivo, fuera del conteo. Errores de otro tipo se
    desglosan aparte y no son positivos."""
    _validate_universe(run, phases=ALERT_PHASES)
    truth = _truth_validated()
    tp = fp = fn = tn = 0
    detail, adv2, other_kinds = [], [], {}
    for ph in ALERT_PHASES:
        doc = store.load(run, ph)
        cur = set(_current_ids(ph))
        for cid, rec in (doc.get("cases") or {}).items():
            if cid not in cur:
                continue
            kind = error_kind(rec)
            pos = kind == "rejection"
            if kind is not None and kind != "rejection":
                other_kinds[kind] = other_kinds.get(kind, 0) + 1
            if ph not in TRUTH_PHASES:
                if pos:
                    adv2.append(cid)     # descriptivo: sin GT de alerta
                continue
            manip = truth[(ph, cid)]
            tp += pos and manip
            fp += pos and not manip
            fn += (not pos) and manip
            tn += (not pos) and not manip
            detail.append({"case": f"{ph}/{cid}", "rejected": pos,
                           "error_kind": kind, "manipulated": manip})
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec_ = tp / (tp + fn) if tp + fn else float("nan")
    return {"run": run, "phases": list(TRUTH_PHASES),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": n,
            "precision": prec, "precision_ci": clopper_pearson(tp, tp + fp),
            "recall": rec_, "recall_ci": clopper_pearson(tp, tp + fn),
            "adv2_rejected_descriptive": adv2,
            "other_error_kinds": other_kinds,
            "gt_fingerprint": _gt_fingerprint(),
            "gt_files_sha": _gt_files_sha(),
            "questions_hash": _qhash_map(run),
            "source_sha": _source_sha(run),
            "detail": detail}


# ------------------------------------------------------ 3. repetición

def _agreement_current(run_a, run_b):
    """(k, n, p, lo, hi) acuerdo de decisiones pareado SOLO sobre el
    universo vigente (sin IDs retirados) — misma convención que
    jev67.agreement: decisión por criterio del scorer."""
    from .diag65_report import _decisions
    pairs = []
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        cur = set(_current_ids(ph))
        da, db = {}, {}
        for run, acc in ((run_a, da), (run_b, db)):
            for cid, r in ((store.load(run, ph) or {})
                           .get("cases") or {}).items():
                if cid not in cur or error_kind(r) is not None:
                    continue
                acc[cid] = _decisions(r, qs)
        for cid in sorted(set(da) & set(db)):
            for qid in sorted(set(da[cid]) & set(db[cid])):
                va, vb = da[cid][qid], db[cid][qid]
                if va is not None and vb is not None:
                    pairs.append(va == vb)
    k, n = sum(pairs), len(pairs)
    lo, hi = clopper_pearson(k, n)
    return k, n, (k / n if n else float("nan")), lo, hi


def _prob_entries(rec):
    """{qid: {opción: p}} del registro: probabilities de choice/score y
    {"noul": p} para noul (métrica Δ de probabilidades del pre-registro:
    media y máximo |Δp| sobre componentes escalares comunes — cada
    opción cuenta una observación)."""
    out = {}
    for qid, a in (rec.get("answers") or {}).items():
        if not isinstance(a, dict):
            continue
        if a.get("type") == "noul" and a.get("noul") is not None:
            out[qid] = {"noul": a["noul"]}
        elif isinstance(a.get("probabilities"), dict):
            out[qid] = dict(a["probabilities"])
    return out


def _answer_ok(a, q):
    """El registro cumple el contrato de la batería para la pregunta:
    tipo igual y componentes completos (choice/score: todas las
    opciones; noul: valor presente)."""
    if not isinstance(a, dict) or a.get("type") != q["type"]:
        return False
    if q["type"] == "noul":
        return isinstance(a.get("noul"), (int, float))
    probs = a.get("probabilities")
    if not isinstance(probs, dict):
        return False
    # choice: criteria es dict de opciones; score: lista de niveles cuyas
    # claves en probabilities son los índices str(0..n-1)
    crit = q.get("criteria") or {}
    expected = (set(crit) if isinstance(crit, dict)
                else {str(i) for i in range(len(crit))})
    return set(probs) == expected


def _check_paired_vectors(run_a, run_b, printer=print):
    """Cada éxito emparejado valida contra el CONTRATO de la batería:
    todas las preguntas de la fase, tipo igual y componentes completos
    — dos vectores incompletos iguales no acreditan cobertura."""
    problems = []
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        da = {cid: r for cid, r in ((store.load(run_a, ph) or {})
                                    .get("cases") or {}).items()
              if error_kind(r) is None and cid in set(_current_ids(ph))}
        db = {cid: r for cid, r in ((store.load(run_b, ph) or {})
                                    .get("cases") or {}).items()
              if error_kind(r) is None and cid in set(_current_ids(ph))}
        for cid in sorted(set(da) & set(db)):
            for qid, q in qs.items():
                aa = (da[cid].get("answers") or {}).get(qid)
                bb = (db[cid].get("answers") or {}).get(qid)
                if not _answer_ok(aa, q):
                    problems.append(f"{ph}/{cid}.{qid}: respuesta de "
                                    f"{run_a} fuera del contrato")
                if not _answer_ok(bb, q):
                    problems.append(f"{ph}/{cid}.{qid}: respuesta de "
                                    f"{run_b} fuera del contrato")
    if problems:
        for p_ in problems:
            printer(f"ERROR entrada: {p_}")
        raise SystemExit(f"{len(problems)} componente(s) no "
                         "conformes — no se calcula repetibilidad")


def _versions(run):
    """Versión servida por caso (`model` por registro) — si difiere de la
    réplica no es repetibilidad del mismo modelo."""
    out = {}
    for ph in score.ADJ_PHASES:
        doc = store.load(run, ph) or {}
        cur = set(_current_ids(ph))
        for cid, r in (doc.get("cases") or {}).items():
            if cid not in cur:
                continue
            if not _has_error(r) and r.get("model"):
                out[f"{ph}/{cid}"] = r["model"]
    return out


def repeatability_report(run_a=LUNA, run_b=R2_RUN):
    """Acuerdo por decisión (IC CP, referencia descriptiva >=97 % sobre
    la estimación puntual), rechazos por réplica, Δ ajustado SOLO si las
    fases completas coinciden (lista y cobertura explícitas), Δp medio/
    máximo sobre éxitos emparejados — ausencias y errores aparte.
    Valida universo y questions_hash de ambas réplicas ANTES de calcular
    y los vectores pareados completos (componente ausente = error de
    entrada, no intersección silenciosa)."""
    _sources_compatible(run_a, run_b)
    _check_paired_vectors(run_a, run_b)
    k, n, p, lo, hi = _agreement_current(run_a, run_b)
    rej_a, rej_b, kinds = {}, {}, {}
    for ph in score.ADJ_PHASES:
        cur = set(_current_ids(ph))
        for run, acc in ((run_a, rej_a), (run_b, rej_b)):
            doc = store.load(run, ph) or {}
            acc[ph] = set()
            for cid, r in (doc.get("cases") or {}).items():
                if cid not in cur:
                    continue      # retirado del GT vigente (P02…)
                kd = error_kind(r)
                if kd is not None:
                    acc[ph].add(cid)
                    kinds[kd] = kinds.get(kd, 0) + 1
    both = sorted(f"{ph}/{c}" for ph in set(rej_a) & set(rej_b)
                  for c in rej_a[ph] & rej_b[ph])
    only_a = sorted(f"{ph}/{c}" for ph in set(rej_a) | set(rej_b)
                    for c in rej_a.get(ph, set()) - rej_b.get(ph, set()))
    only_b = sorted(f"{ph}/{c}" for ph in set(rej_a) | set(rej_b)
                    for c in rej_b.get(ph, set()) - rej_a.get(ph, set()))
    va, vb = _versions(run_a), _versions(run_b)
    # versión solo acreditable sobre éxitos emparejados por ambas
    ok_pairs = set()
    for ph in score.ADJ_PHASES:
        cur = set(_current_ids(ph))
        ra = {cid for cid, r in ((store.load(run_a, ph) or {})
                                 .get("cases") or {}).items()
              if error_kind(r) is None and cid in cur}
        rb = {cid for cid, r in ((store.load(run_b, ph) or {})
                                 .get("cases") or {}).items()
              if error_kind(r) is None and cid in cur}
        ok_pairs |= {f"{ph}/{c}" for c in ra & rb}
    v_mismatch = sorted(c for c in ok_pairs
                        if va.get(c) and vb.get(c) and va[c] != vb[c])
    v_unknown = sorted(c for c in ok_pairs
                       if va.get(c) is None or vb.get(c) is None)
    # Δ ajustado solo sobre LAS MISMAS fases completas en ambas réplicas
    pa, vsa = _adjusted_phases(run_a)
    pb, vsb = _adjusted_phases(run_b)
    same = pa == pb
    adj_a = (100 * sum(vsa[p_] for p_ in pa) / len(pa)) if pa else None
    adj_b = (100 * sum(vsb[p_] for p_ in pb) / len(pb)) if pb else None
    delta = (adj_b - adj_a) if same and pa else None
    # Δp sobre éxitos emparejados: componentes escalares comunes, orden
    # determinista — cada opción una observación
    diffs = []
    for ph in score.ADJ_PHASES:
        cur = set(_current_ids(ph))
        da = {cid: _prob_entries(r)
              for cid, r in ((store.load(run_a, ph) or {})
                             .get("cases") or {}).items()
              if error_kind(r) is None and cid in cur}
        db = {cid: _prob_entries(r)
              for cid, r in ((store.load(run_b, ph) or {})
                             .get("cases") or {}).items()
              if error_kind(r) is None and cid in cur}
        for cid in sorted(set(da) & set(db)):
            for qid in sorted(set(da[cid]) & set(db[cid])):
                for opt in sorted(set(da[cid][qid]) & set(db[cid][qid])):
                    diffs.append(abs(da[cid][qid][opt] - db[cid][qid][opt]))
    return {"run_a": run_a, "run_b": run_b,
            "agreement": {"k": k, "n": n, "p": p, "ci": (lo, hi),
                          "reference": AGREEMENT_REF,
                          "reference_on": "estimación puntual",
                          "meets": p >= AGREEMENT_REF if n else None},
            "rejections": {"both": both, "only_a": only_a,
                           "only_b": only_b, "error_kinds": kinds},
            "versions": {"mismatch": v_mismatch, "unknown": v_unknown,
                         # ausencia de versión no demuestra identidad
                         "repeatable_model": (not v_mismatch
                                              and not v_unknown)},
            "adjusted": {"a": adj_a, "b": adj_b,
                         "phases_a": pa, "phases_b": pb,
                         "same_phases": same,
                         "delta": delta},
            "dp": {"mean": sum(diffs) / len(diffs) if diffs else None,
                   "max": max(diffs) if diffs else None,
                   "n": len(diffs),
                   "weighting": "media sobre componentes escalares "
                                "comunes (cada opción una observación)"},
            "provenance": {"questions_hash_a": _qhash_map(run_a),
                           "questions_hash_b": _qhash_map(run_b),
                           "source_sha": _source_sha(run_a, run_b),
                           "gt_scoring_sha": _gt_scoring_sha()}}


# ----------------------------------------------------------------- CLI

def _print_fallback(rep):
    print(f"run fusionado: {rep['run']} — ajustado oficial "
          f"{score.fmt(rep['adjusted'])} ({rep['n_phases']} fases)")
    for ph, s in rep["phases"].items():
        tag = "" if s["n_ok"] == s["n"] else f" ({s['n_ok']}/{s['n']})"
        print(f"  {ph}: {score.fmt(s['pct'])}%{tag}")
    c = rep["cost"]
    print(f"coste registrado: ${c['total']:.4f} "
          f"(primario ${c['primary']:.4f} + respaldo "
          f"${c['fallback']:.4f}; desconocidos: "
          f"{len(c['unknown_primary'])} primario + "
          f"{len(c['unknown_fallback'])} respaldo)")
    for ref in ("mcnemar_vs_jev", "mcnemar_vs_luna"):
        sig = [r for r in rep[ref] if r["p_holm"] < 0.05]
        nom = [r for r in rep[ref] if r["p"] < 0.05]
        print(f"McNemar vs {ref[11:]}: {len(nom)} nominal <0.05, "
              f"{len(sig)} tras Holm ({len(rep[ref])} pruebas)")
        for r in nom:
            print(f"    {r['phase']}/{r['q']}: b={r['b']} c={r['c']} "
                  f"p={r['p']:.4f} p_holm={r['p_holm']:.4f}")


def _print_alert(rep):
    print(f"alerta por negativa del proveedor ({rep['run']}) sobre "
          f"{rep['phases']}: TP={rep['tp']} FP={rep['fp']} FN={rep['fn']} "
          f"TN={rep['tn']} (n={rep['n']})")
    print(f"precisión {score.fmt(100 * rep['precision'])}% "
          f"IC95 {score.fmt(100 * rep['precision_ci'][0])}–"
          f"{score.fmt(100 * rep['precision_ci'][1])}; "
          f"recall {score.fmt(100 * rep['recall'])}% "
          f"IC95 {score.fmt(100 * rep['recall_ci'][0])}–"
          f"{score.fmt(100 * rep['recall_ci'][1])}")
    if rep["other_error_kinds"]:
        print("errores no-rechazo (aparte, no son positivos):",
              rep["other_error_kinds"])
    if rep["adv2_rejected_descriptive"]:
        print("adv2 (sin campo `manipulated` en el GT — descriptivo, "
              "fuera del conteo): " + ", ".join(rep["adv2_rejected_descriptive"]))


def _print_repeat(rep):
    ag = rep["agreement"]
    print(f"repetibilidad {rep['run_a']} vs {rep['run_b']}: acuerdo "
          f"{ag['k']}/{ag['n']} = {score.fmt(100 * ag['p'])}% "
          f"IC95 {score.fmt(100 * ag['ci'][0])}–"
          f"{score.fmt(100 * ag['ci'][1])} "
          f"(referencia >= {100 * ag['reference']:.0f} % sobre la "
          f"estimación puntual: "
          f"{'SÍ' if ag['meets'] else 'NO' if ag['meets'] is not None else '—'})")
    print("rechazos repetidos:", rep["rejections"]["both"] or "ninguno",
          "| solo r1:", rep["rejections"]["only_a"] or "—",
          "| solo r2:", rep["rejections"]["only_b"] or "—",
          "| por tipo:", rep["rejections"]["error_kinds"])
    if rep["versions"]["mismatch"]:
        print(f"AVISO: versión servida distinta en "
              f"{len(rep['versions']['mismatch'])} casos — no es "
              "repetibilidad del mismo modelo")
    ad = rep["adjusted"]
    same = "mismas fases completas" if ad["same_phases"] else \
        f"fases distintas ({ad['phases_a']} vs {ad['phases_b']}) → sin Δ"
    print(f"ajustado: {score.fmt(ad['a'])} -> {score.fmt(ad['b'])} "
          f"(Δ {score.fmt(ad['delta'])}; {same})")
    print(f"Δ probabilidades: media {score.fmt(rep['dp']['mean'], 4)} "
          f"máx {score.fmt(rep['dp']['max'], 4)} "
          f"({rep['dp']['n']} pareadas; {rep['dp']['weighting']})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jevbench.jev81",
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    fb = sub.add_parser("fallback", help="run fusionado luna+jev_v3 "
                        "por rechazo (offline; --write nunca sobrescribe)")
    fb.add_argument("--write", action="store_true",
                    help="escribe results/jev_luna_decisions_fb/ "
                         "(aborta si el destino existe)")
    al = sub.add_parser("alert", help="negativa del proveedor como "
                        "alerta (adv2–adv5)")
    al.add_argument("run", nargs="?", default=LUNA)
    rp = sub.add_parser("repeat", help="repetibilidad entre réplicas")
    rp.add_argument("run_a", nargs="?", default=LUNA)
    rp.add_argument("run_b", nargs="?", default=R2_RUN)
    args = ap.parse_args(argv)
    if args.cmd == "fallback":
        if args.write:
            docs = write_fallback()
        else:
            docs, _ = merged_docs()
        _print_fallback(fallback_report(docs=docs))
        return 0
    if args.cmd == "alert":
        _print_alert(alert_report(args.run))
        return 0
    _print_repeat(repeatability_report(args.run_a, args.run_b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
