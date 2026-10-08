"""JEV-78 — análisis del run nativo `oai_luna_decisions` (Decisions API de
OpenAI vía SDK oficial, POST /v1/decisions) frente a `jev_luna_decisions`
(la misma API por OpenRouter, JEV-80) y a `jev_v3` (referencia del banco).

Pre-registro: docs/infra_runs/openai_decisions_jev78.md. Solo stdlib; lee
results/ y no escribe en los runs existentes.

Lo específico de este contrato frente a JEV-81/82:

- La negativa de la API nativa es POR PREGUNTA, dentro de un HTTP 200
  (answers[] con type "refusal"), no un estado. A nivel de caso: un
  registro con TODAS las preguntas rechazadas es el error ProviderRefusal
  (`ProviderRefusal:` -> `rejection`); un registro con negativas parciales
  NO es un error — el caso se conserva con las preguntas marcadas
  {"type": "refusal"} y listadas en `refusals`, y cada una puntúa 0 como
  error en su pregunta (metrics.point). `question_refusals` las lista.
- `ContractError:` (la validación de contrato del adaptador: nombres
  duplicados, vectores incompletos, etiquetas ajenas, escalares fuera de
  rango) clasifica `local`.
- El resto de clases (502 + «refused to answer», timeout, transport,
  local, other, missing) reutiliza `jev81.error_kind` sin tocarlo.
"""
import argparse
import json
import re
import sys

from . import jev81, jev82, metrics as M, score, store
from . import qwen_session as qs_
from .battery import load_phase
from .jev67 import clopper_pearson, holm

NATIVE = "oai_luna_decisions"        # Decisions API nativa de OpenAI (SDK)
OPENROUTER = "jev_luna_decisions"    # misma API por OpenRouter (JEV-80)
JEV = "jev_v3"                       # referencia del banco (jev-1.13)
LLM_PROB = "llm_gpt6luna_prob"       # mismo modelo vía system-one-adapter
PROVIDER_REFUSAL_PREFIX = "ProviderRefusal:"
CONTRACT_ERROR_PREFIX = "ContractError:"
AGREEMENT_REF = 0.97                 # referencia descriptiva (convención JEV-81/82)


def error_kind(rec):
    """Clasificador del contrato nativo (pre-registro §0): el prefijo
    `ProviderRefusal:` (rechazo de TODAS las preguntas del caso) es
    negativa del proveedor (`rejection`); el prefijo `ContractError:` es
    error local de validación del contrato (`local`). Las negativas
    parciales por pregunta no producen registro con error — se leen con
    `question_refusals`. Todo lo demás delega en `jev81.error_kind` tal
    cual: HTTP 502 + «refused to answer» -> rejection, timeout/transport/
    local/other/missing iguales. Solo mensaje/estado del error — nunca el
    id del caso ni el GT."""
    err = rec.get("error") if isinstance(rec, dict) else None
    if isinstance(err, str):
        if err.startswith(PROVIDER_REFUSAL_PREFIX):
            return "rejection"
        if err.startswith(CONTRACT_ERROR_PREFIX):
            return "local"
    return jev81.error_kind(rec)


def answer_states(rec, qs):
    """{qid: 'ok' | 'refused' | 'invalid' | 'missing'} — estado de cada
    componente de un registro frente al contrato de la fase. 'refused' es
    la negativa por pregunta nativa: válida como marca, sin respuesta."""
    out = {}
    ans = rec.get("answers") or {}
    for qid, q in qs.items():
        a = ans.get(qid)
        if isinstance(a, dict) and a.get("type") == "refusal":
            out[qid] = "refused"
        elif jev81._answer_ok(a, q):
            out[qid] = "ok"
        elif a is None:
            out[qid] = "missing"
        else:
            out[qid] = "invalid"
    return out


def question_refusals(run):
    """{phase: {cid: [qids]}} de las negativas por pregunta del run
    (universo vigente) — marcadas en `answers` y/o listadas en `refusals`
    del registro, sobre casos SIN error de registro."""
    out = {}
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        cur = set(jev81._current_ids(ph))
        doc = store.load(run, ph) or {}
        out[ph] = {}
        for cid, r in (doc.get("cases") or {}).items():
            if cid not in cur or error_kind(r) is not None:
                continue
            ref = [qid for qid, st in answer_states(r, qs).items()
                   if st == "refused"]
            if ref:
                out[ph][cid] = ref
    return out


def _rejections(run):
    """{phase: {cid: kind}} de los registros con error (universo vigente),
    clasificados con `error_kind` de este módulo — para los registros de la
    ruta OpenRouter coincide con jev81.error_kind, que no produce los
    prefijos específicos del contrato nativo."""
    out = {}
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        doc = store.load(run, ph) or {}
        out[ph] = {cid: error_kind(r)
                   for cid, r in (doc.get("cases") or {}).items()
                   if cid in cur and error_kind(r) is not None}
    return out


def rejections_paired(native=NATIVE, openrouter=OPENROUTER):
    """Listas explícitas del §3.1 sobre los registros con error de ambos
    runs (universo vigente): `both` / `only_openrouter` / `only_native`,
    más el desglose `error_kinds`. Lectura factual acotada: un éxito nativo
    sobre un caso rechazado por OpenRouter muestra que pudo responderse por
    esa ruta — NO prueba qué capa produjo la negativa histórica (alias sin
    snapshot = versión subyacente desconocida, ejecuciones separadas)."""
    rej_nat, rej_or = _rejections(native), _rejections(openrouter)
    both, only_or, only_nat, kinds = [], [], [], {}
    for ph in score.ADJ_PHASES:
        for cid, k in rej_or.get(ph, {}).items():
            kinds[k] = kinds.get(k, 0) + 1
            (both if cid in rej_nat.get(ph, {}) else only_or).append(
                f"{ph}/{cid}")
        for cid, k in rej_nat.get(ph, {}).items():
            if cid not in rej_or.get(ph, {}):
                kinds[k] = kinds.get(k, 0) + 1
                only_nat.append(f"{ph}/{cid}")
    return {"both": sorted(both), "only_openrouter": sorted(only_or),
            "only_native": sorted(only_nat), "error_kinds": kinds}


def agreement_paired(native=NATIVE, openrouter=OPENROUTER):
    """Acuerdo de decisiones pareado (criterio del scorer, convención
    JEV-81/82) entre éxitos de ambos runs: (k, n, p, lo, hi) + la lista
    `no_pair` de componentes sin par — una pregunta rechazada no tiene
    decisión y NO entra ni al numerador ni al denominador; se lista aparte
    (nunca contada como acuerdo ni desacuerdo)."""
    from .diag65_report import _decisions
    pairs, no_pair = [], []
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        cur = set(jev81._current_ids(ph))
        da, db = {}, {}
        for run, acc in ((native, da), (openrouter, db)):
            for cid, r in ((store.load(run, ph) or {})
                           .get("cases") or {}).items():
                if cid not in cur or error_kind(r) is not None:
                    continue
                acc[cid] = _decisions(r, qs)
        for cid in sorted(set(da) & set(db)):
            for qid in sorted(set(da[cid]) | set(db[cid])):
                va, vb = da[cid].get(qid), db[cid].get(qid)
                if va is None or vb is None:
                    no_pair.append(f"{ph}/{cid}.{qid}")
                else:
                    pairs.append(va == vb)
    k, n = sum(pairs), len(pairs)
    lo, hi = clopper_pearson(k, n)
    return {"k": k, "n": n, "p": (k / n if n else float("nan")),
            "ci95": (lo, hi), "no_pair": sorted(no_pair)}


def _check_paired(native=NATIVE, openrouter=OPENROUTER, printer=print):
    """§1: sobre los éxitos PAREADOS (universo vigente, sin error de
    registro en ninguno de los dos runs) cada componente debe ser
    conforme al contrato de la batería — en el run nativo `refused` es
    además un estado declarado de adquisición (negativa por pregunta
    del proveedor, puntuada 0): no es conformidad ni error de entrada;
    va aparte en `question_refusals`/`no_pair`."""
    problems = []
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        cur = set(jev81._current_ids(ph))
        recs = [{cid: r for cid, r in ((store.load(run, ph) or {})
                     .get("cases") or {}).items()
                 if cid in cur and error_kind(r) is None}
                for run in (native, openrouter)]
        for cid in sorted(set(recs[0]) & set(recs[1])):
            states = answer_states(recs[0][cid], qs)
            for qid, q in qs.items():
                if states[qid] in ("invalid", "missing"):
                    problems.append(f"{ph}/{cid}.{qid}: componente "
                                    f"{states[qid]} en {native}")
                bb = (recs[1][cid].get("answers") or {}).get(qid)
                if not jev81._answer_ok(bb, q):
                    problems.append(f"{ph}/{cid}.{qid}: respuesta de "
                                    f"{openrouter} fuera del contrato")
    if problems:
        for p in problems:
            printer(f"ERROR entrada: {p}")
        raise SystemExit(f"{len(problems)} componente(s) no conformes "
                         "— no se calcula nada")
    return True


_SNAPSHOT_DATE = re.compile(r"\d{8}")   # fecha yyyymmdd en el id servido


def _snapshot_version(model):
    """Versión ACREDITADA del literal `model` observado: un id con fecha
    de snapshot (…-YYYYMMDD) identifica la versión servida; un alias sin
    fecha (`gpt-6-luna`) no discrimina el snapshot — None (desconocido).
    El literal se conserva aparte para procedencia (`observed`)."""
    return model if isinstance(model, str) and _SNAPSHOT_DATE.search(
        model) else None


def _version_pairs(ids, va, vb):
    """Contraste de versión sobre los éxitos pareados: compara las
    versiones ACREDITADAS (snapshot fechado), no los literales. `unknown`
    lista los pares sin snapshot acreditado en algún lado; `mismatch` los
    que teniéndolo discrepan; `same_model` exige >= 1 par conocido e
    igual y CERO ausencias ni discrepancias (convención JEV-82 §3.6).
    `observed` conserva los literales servidos por lado (procedencia)."""
    sa = {c: _snapshot_version(va.get(c)) for c in ids}
    sb = {c: _snapshot_version(vb.get(c)) for c in ids}
    mismatch = sorted(c for c in ids
                      if sa[c] is not None and sb[c] is not None
                      and sa[c] != sb[c])
    unknown = sorted(c for c in ids if sa[c] is None or sb[c] is None)
    known = sum(1 for c in ids
                if sa[c] is not None and sb[c] is not None)
    return {"paired_successes": len(ids), "known_pairs": known,
            "mismatch": mismatch, "unknown": unknown,
            "same_model": bool(known >= 1 and not mismatch and not unknown),
            "observed": {"native": sorted({va[c] for c in ids
                                           if va[c] is not None}),
                         "openrouter": sorted({vb[c] for c in ids
                                               if vb[c] is not None})}}


def _paired_versions(native=NATIVE, openrouter=OPENROUTER):
    """(ids, va, vb) de los éxitos PAREADOS con el literal `model` servido
    por lado — observado, no acreditado: la separación alias/snapshot se
    hace en `_version_pairs` (un alias sin fecha NO acredita el snapshot
    de OpenRouter; versión ausente = desconocida, nunca suplida)."""
    ids, va, vb = [], {}, {}
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        recs = [{cid: r for cid, r in ((store.load(run, ph) or {})
                     .get("cases") or {}).items()
                 if cid in cur and error_kind(r) is None}
                for run in (native, openrouter)]
        for cid in sorted(set(recs[0]) & set(recs[1])):
            key = f"{ph}/{cid}"
            ids.append(key)
            va[key], vb[key] = (recs[0][cid].get("model"),
                                recs[1][cid].get("model"))
    return ids, va, vb


def mcnemar_holm(run=NATIVE, ref=JEV):
    """Familia completa de McNemar del run frente a la referencia
    (acierto estricto por pregunta×fase, convención JEV-81) con Holm.
    Una pregunta rechazada puntúa 0 -> su acierto es False; los casos
    con error del run o de la referencia quedan False en su celda."""
    rows = []
    for ph in score.ADJ_PHASES:
        s, r = score.score_run(run, ph), score.score_run(ref, ph)
        if s is None or r is None:
            continue
        for q in sorted(s["hits"]):
            b_, c_, p = M.mcnemar(r["hits"][q], s["hits"][q])
            rows.append({"phase": ph, "q": q, "b": b_, "c": c_, "p": p})
    for row, pa in zip(rows, holm([r["p"] for r in rows])):
        row["p_holm"] = pa
    return rows


def _dp_paired(native=NATIVE, openrouter=OPENROUTER):
    """Δp medio/máx sobre componentes escalares comunes de los éxitos
    pareados (alineados por etiqueta). Una pregunta rechazada no tiene
    componente escalar: no entra ni al numerador ni al denominador."""
    diffs = []
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        per = []
        for run in (native, openrouter):
            doc = store.load(run, ph) or {}
            per.append({cid: jev81._prob_entries(r)
                        for cid, r in (doc.get("cases") or {}).items()
                        if cid in cur and error_kind(r) is None})
        for cid in sorted(set(per[0]) & set(per[1])):
            for qid in sorted(set(per[0][cid]) & set(per[1][cid])):
                for opt in sorted(set(per[0][cid][qid])
                                  & set(per[1][cid][qid])):
                    diffs.append(abs(per[0][cid][qid][opt]
                                     - per[1][cid][qid][opt]))
    return {"mean": sum(diffs) / len(diffs) if diffs else None,
            "max": max(diffs) if diffs else None, "n": len(diffs)}


def _latency(run):
    """Mediana de `ms` por fase sobre los registros del universo vigente."""
    out = {}
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        ms = sorted(r["ms"] for cid, r in ((store.load(run, ph) or {})
                        .get("cases") or {}).items()
                    if cid in cur
                    and isinstance(r.get("ms"), (int, float)))
        if ms:
            out[ph] = ms[len(ms) // 2]
    return out


def _coverage(run):
    """{phase: (n_ok, n)} del universo vigente con el scorer oficial."""
    out = {}
    for ph in score.ADJ_PHASES:
        s = score.score_run(run, ph)
        if s:
            out[ph] = {"n_ok": s["n_ok"], "n": s["n"], "pct": s["pct"],
                       "errors": s["errors"]}
    return out


def report(native=NATIVE, openrouter=OPENROUTER, jev=JEV, printer=print):
    """Informe del contraste nativo vs OpenRouter (pre-registro §3). Todo
    lo calculado aquí usa `error_kind` de ESTE módulo (prefijos del
    contrato nativo + delegación en jev81) — nunca el clasificador de
    jev81 directamente sobre registros del run nativo."""
    qhash = jev81._sources_compatible(native, openrouter, printer=printer)
    jev82._cost_guard_declared(native, printer)
    _check_paired(native, openrouter, printer)

    rej = rejections_paired(native, openrouter)
    qref = question_refusals(native)
    ids, va, vb = _paired_versions(native, openrouter)
    versions = _version_pairs(ids, va, vb)
    ag = agreement_paired(native, openrouter)
    pa, pb = jev81._adjusted_phases(native), jev81._adjusted_phases(openrouter)
    delta = qs_.paired_delta(openrouter, native)   # nativo − OpenRouter
    return {"runs": {"native": native, "openrouter": openrouter,
                     "jev": jev},
            "coverage": {native: _coverage(native),
                         openrouter: _coverage(openrouter)},
            "rejections": rej,
            "question_refusals": {ph: v for ph, v in qref.items() if v},
            "versions": versions,
            "agreement": {**ag, "reference": AGREEMENT_REF,
                          "reference_on": "estimación puntual",
                          "meets": (ag["p"] >= AGREEMENT_REF
                                    if ag["n"] else None)},
            "adjusted": {"delta": delta,
                         "phases_native": pa[0], "phases_openrouter": pb[0],
                         "same_phases": pa[0] == pb[0],
                         "adj_native": (100 * sum(pa[1].values()) / len(pa[1])
                                        if pa[1] else None),
                         "adj_openrouter": (100 * sum(pb[1].values()) / len(pb[1])
                                            if pb[1] else None)},
            "mcnemar_holm_vs_jev": mcnemar_holm(native, jev),
            "dp": _dp_paired(native, openrouter),
            "cost": {"native": jev82._costs(native),
                     "openrouter": jev82._costs(openrouter)},
            "latency_ms_median": {"native": _latency(native),
                                  "openrouter": _latency(openrouter)},
            "descriptive_adjusted": {
                r: {"adjusted": score.adjusted(r),
                    "ci95": score.adjusted_ci(r)}
                for r in (native, openrouter, LLM_PROB, jev)
                if any(score.score_run(r, ph) for ph in score.ADJ_PHASES)},
            "provenance": {"questions_hash": qhash,
                           "source_sha": jev81._source_sha(native, openrouter),
                           "gt_scoring_sha": jev81._gt_scoring_sha()}}


def _print_report(rep, printer=print):
    printer(f"JEV-78 — {rep['runs']['native']} (nativo) vs "
            f"{rep['runs']['openrouter']} (OpenRouter)")
    rj = rep["rejections"]
    printer(f"rechazos/errores: en ambos {rj['both'] or 'ninguno'}; solo "
            f"OpenRouter {rj['only_openrouter'] or '—'}; solo nativo "
            f"{rj['only_native'] or '—'}; por tipo {rj['error_kinds']}")
    printer("  lectura acotada: un éxito nativo sobre un rechazo de "
            "OpenRouter muestra que el caso pudo responderse por esa "
            "ruta — no prueba qué capa produjo la negativa histórica")
    qr = rep["question_refusals"]
    n_qr = sum(len(qids) for per_case in qr.values()
               for qids in per_case.values())
    printer(f"negativas por pregunta (casos conservados, puntúan 0): "
            f"{n_qr} pregunta(s) rechazada(s)"
            + (f" — {qr}" if qr else ""))
    ag = rep["agreement"]
    printer(f"acuerdo pareado: {ag['k']}/{ag['n']} = "
            f"{score.fmt(100 * ag['p'])}% IC95 "
            f"{score.fmt(100 * ag['ci95'][0])}–{score.fmt(100 * ag['ci95'][1])} "
            f"(referencia >= {100 * ag['reference']:.0f} % sobre la "
            f"estimación: {'SÍ' if ag['meets'] else 'NO'}; sin par: "
            f"{len(ag['no_pair'])})")
    v = rep["versions"]
    printer(f"versión servida: same_model={v['same_model']} "
            f"({v['known_pairs']} pares conocidos, "
            f"{len(v['mismatch'])} discrepantes, "
            f"{len(v['unknown'])} sin snapshot acreditado; "
            f"observado nativo={v['observed']['native']} "
            f"OpenRouter={v['observed']['openrouter']})")
    if not v["same_model"]:
        printer("  AVISO: versión desconocida o distinta — el contraste "
                "no acredita mismo snapshot; el alias nativo sin fecha "
                "no discrimina")
    d = rep["adjusted"]["delta"]
    if d:
        printer(f"ajustado nativo−OpenRouter: {score.fmt(d['delta'], 2)} "
                f"IC95 {score.fmt(d['lo'], 2)}–{score.fmt(d['hi'], 2)} "
                f"({d['reps']} réplicas; fases comunes completas: "
                f"{', '.join(d['phases'])})")
    else:
        printer("ajustado nativo−OpenRouter: sin fases comunes completas")
    if not rep["adjusted"]["same_phases"]:
        printer(f"  AVISO: fases completas distintas (nativo: "
                f"{rep['adjusted']['phases_native']} vs OpenRouter: "
                f"{rep['adjusted']['phases_openrouter']}) — el Δ usa la "
                "intersección")
    sig = [r for r in rep["mcnemar_holm_vs_jev"] if r["p_holm"] < 0.05]
    printer(f"McNemar–Holm vs {rep['runs']['jev']}: "
            f"{len(rep['mcnemar_holm_vs_jev'])} pruebas, "
            f"{len(sig)} significativas tras Holm"
            + (f" ({[r['phase'] + '.' + r['q'] for r in sig[:6]]})"
               if sig else ""))
    dp = rep["dp"]
    printer(f"Δp: media {score.fmt(dp['mean'], 4)} máx "
            f"{score.fmt(dp['max'], 4)} ({dp['n']} componentes)")
    for tag, c in (("nativo", rep["cost"]["native"]),
                   ("OpenRouter", rep["cost"]["openrouter"])):
        flag = (f" — SOBRE LA GUARDA: {c['over_cap']}"
                if c["over_cap"] else "")
        printer(f"coste {tag}: ${c['total']:.4f} registrado en "
                f"{c['n_priced']} casos (máx ${c['max_case'] or 0:.5f}; "
                f"desconocidos {len(c['unknown'])}){flag}")
    for tag, lat in rep["latency_ms_median"].items():
        printer(f"ms mediano {tag}: "
                + ", ".join(f"{ph}={score.fmt(v, 0)}"
                            for ph, v in lat.items()))
    printer("ajustados descriptivos (IC95): "
            + "; ".join(f"{r}: {score.fmt(a['adjusted'][0], 1)} "
                        f"[{score.fmt(a['ci95'][1], 0)}–"
                        f"{score.fmt(a['ci95'][2], 0)}]"
                        for r, a in rep["descriptive_adjusted"].items()))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jevbench.jev78",
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze",
                        help="contraste nativo vs OpenRouter (offline)")
    an.add_argument("native", nargs="?", default=NATIVE)
    an.add_argument("openrouter", nargs="?", default=OPENROUTER)
    an.add_argument("--jev", default=JEV)
    an.add_argument("--json", help="vuelca el informe completo a un fichero")
    args = ap.parse_args(argv)
    rep = report(args.native, args.openrouter, args.jev)
    _print_report(rep)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1, default=str)
        print(f"informe escrito en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
