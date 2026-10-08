"""JEV-82 — rotación d1 del orden de `department` en gpt-6-luna-decisions
(sensibilidad al orden): contraste del run nuevo `jev_luna_decisions_d1`
frente a `jev_luna_decisions` (JEV-80, orden canónico d0).

Pre-registro: docs/infra_runs/luna_decisions_jev82.md. Solo stdlib; lee
results/ y no escribe en los runs existentes.

Reglas fijadas en el pre-registro (nada fuera de ellas es oficial):
  1) universo: ambos runs cubren las 11 fases con todos los ids vigentes y
     questions_hash igual al actual (el hash es invariante al orden de las
     claves — la procedencia del orden la acreditan meta.choice_order y
     perm_sha256, verificados contra la rotación declarada);
  2) contraste ajustado (d1−d0) SOLO sobre las fases completas en ambos
     runs (intersección; listas explícitas), bootstrap pareado por
     clusters ES/EN+PMID, 10 000 réplicas, semilla 271828, IC95 —
     descriptivo;
  3) acuerdo de decisiones pareado (convención del scorer) con IC95 de
     Clopper-Pearson; referencia descriptiva >= 97 % (misma convención
     que la repetibilidad de JEV-81);
  4) primacía: subconjunto CONGELADO de JEV-72 (sha 4e7e2877f27d; si no
     coincide, se aborta), Δpp de errores de department (d0−d1) sobre
     casos respondidos por ambos, IC95 bootstrap por clusters + McNemar
     con convención ES; veredicto con la regla de JEV-72: CONFIRMADA si
     Δ>=5 pp, L95>0 y el contraste es significativo tras Holm de la
     familia {d0vsd1 en todos los casos, primacía}; REFUTADA si U95<5;
     si no, INCONCLUSA;
  5) rechazos/errores por run (both/only_d0/only_d1) y versión servida
     por caso sobre los éxitos PAREADOS (ausentes conservadas y listadas):
     same_model solo si hay >=1 par conocido y ninguna ausencia ni
     discrepancia; si difiere o falta en algún éxito pareado, el contraste
     es entre versiones o de versión desconocida, no sensibilidad del
     mismo modelo;
  6) coste: guarda EFECTIVA durante la adquisición (--max-case-cost 0,01 /
     --max-cost 0,05 de jevbench.run, acreditada por meta.cost_guard en
     cada fase del run d1); en el informe, solo lo registrado: cualquier
     caso con coste > $0,01 se marca y los desconocidos se listan aparte.
"""
import argparse
import json
import sys

from . import jev81, score, store
from . import qwen_session as qs_
from .battery import load_phase
from .jev67 import clopper_pearson
from .rotation import (NAMED_ORDERS, order_manifest, reorder_choice,
                       resolve_choice_order)

D0 = "jev_luna_decisions"        # JEV-80: orden canónico
D1 = "jev_luna_decisions_d1"     # orden department:d1
PRIMACY_SUBSET_SHA = "4e7e2877f27d"   # subconjunto congelado JEV-72 (R13 §5)
AGREEMENT_REF = 0.97                  # referencia descriptiva (convención JEV-81)
CASE_COST_CAP = 0.01                  # guarda: ningún caso debe costar > $0,01
RUN_COST_CAP = 0.05                   # guarda: acumulado registrado del run > $0,05
COST_GUARD_SPEC = {"max_case_cost": CASE_COST_CAP, "max_cost": RUN_COST_CAP}


def _expected_perm(phase, spec):
    """perm_sha256 que DEBE declarar el run en `phase` con la especificación
    de orden `spec` ('d0'|'d1'), calculado sobre las preguntas vigentes."""
    qs, _ = load_phase(phase)
    orders = resolve_choice_order(f"department:{spec}")
    return order_manifest(reorder_choice(qs, orders), orders)["perm_sha256"]


def _order_provenance(run, spec, printer=print):
    """El run declara el orden esperado: opts.choice_order='department:<spec>',
    meta.choice_order resuelto igual a NAMED_ORDERS y perm_sha256 igual al de
    la rotación aplicada sobre las preguntas vigentes, en TODAS las fases.
    En d0 también se admite la ausencia de la opción (comportamiento
    histórico, pre-JEV-82)."""
    want = resolve_choice_order(f"department:{spec}")
    problems = []
    for ph in score.ADJ_PHASES:
        doc = store.load(run, ph)
        if doc is None:
            problems.append(f"{ph}: fase ausente en {run}")
            continue
        meta = doc.get("meta") or {}
        opt = (meta.get("opts") or {}).get("choice_order")
        if opt is None and spec == "d0":
            opt_ok = True                     # histórico: sin la opción
        else:
            opt_ok = opt == f"department:{spec}"
        if not opt_ok:
            problems.append(f"{ph}: opts.choice_order={opt!r} != "
                            f"'department:{spec}' en {run}")
        declared = meta.get("choice_order")
        if declared is None:
            if spec != "d0":
                problems.append(f"{ph}: meta.choice_order ausente en {run}")
        elif declared != want:
            problems.append(f"{ph}: meta.choice_order={declared!r} != "
                            f"{want!r} en {run}")
        perm = meta.get("perm_sha256")
        expect = _expected_perm(ph, spec)
        if perm is not None and perm != expect:
            problems.append(f"{ph}: perm_sha256 {perm!r} != esperado "
                            f"{expect!r} en {run}")
        if spec != "d0" and perm is None:
            problems.append(f"{ph}: perm_sha256 ausente en {run}")
    if problems:
        for p in problems:
            printer(f"ERROR entrada: {p}")
        raise SystemExit(f"{run}: orden declarado incompatible con "
                         f"department:{spec} — no se calcula nada")
    return True


def _rejections(run):
    """{phase: {cid: kind}} de los registros con error (universo vigente)."""
    out = {}
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        doc = store.load(run, ph) or {}
        out[ph] = {cid: jev81.error_kind(r)
                   for cid, r in (doc.get("cases") or {}).items()
                   if cid in cur and jev81.error_kind(r) is not None}
    return out


def _rejections_paired(ra, rb):
    both, only_a, only_b, kinds = [], [], [], {}
    for ph in score.ADJ_PHASES:
        for cid, k in ra.get(ph, {}).items():
            kinds[k] = kinds.get(k, 0) + 1
            (both if cid in rb.get(ph, {}) else only_a).append(f"{ph}/{cid}")
        for cid, k in rb.get(ph, {}).items():
            if cid not in ra.get(ph, {}):
                kinds[k] = kinds.get(k, 0) + 1
                only_b.append(f"{ph}/{cid}")
    return {"both": sorted(both), "only_d0": sorted(only_a),
            "only_d1": sorted(only_b), "error_kinds": kinds}


def _paired_versions(run_a, run_b):
    """(ids, va, vb) de los éxitos PAREADOS (universo vigente, sin error en
    ninguno de los dos runs) con la versión servida por lado — ausencias
    conservadas como None y listadas, no omitidas (R56.1: intersectar los
    mapas de _versions pierde los éxitos sin `model` y declara falsamente
    same_model)."""
    ids, va, vb = [], {}, {}
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        recs = [{cid: r for cid, r in ((store.load(run, ph) or {})
                     .get("cases") or {}).items()
                 if cid in cur and jev81.error_kind(r) is None}
                for run in (run_a, run_b)]
        for cid in sorted(set(recs[0]) & set(recs[1])):
            key = f"{ph}/{cid}"
            ids.append(key)
            va[key], vb[key] = recs[0][cid].get("model"), recs[1][cid].get("model")
    return ids, va, vb


def _cost_guard_declared(run, printer=print):
    """Toda fase del run declara en meta.cost_guard los topes congelados —
    la guarda de la adquisición (§2) es efectiva, no solo post hoc."""
    problems = []
    for ph in score.ADJ_PHASES:
        doc = store.load(run, ph)
        if doc is None:
            continue          # la ausencia la detecta la validación de universo
        g = (doc.get("meta") or {}).get("cost_guard")
        if g != COST_GUARD_SPEC:
            problems.append(f"{ph}: meta.cost_guard={g!r} != "
                            f"{COST_GUARD_SPEC} en {run}")
    if problems:
        for p in problems:
            printer(f"ERROR entrada: {p}")
        raise SystemExit(f"{run}: guarda de coste no declarada como la "
                         "congelada — no se calcula nada")
    return True


def _dp_paired(run_a, run_b):
    """Δp medio/máx sobre componentes escalares comunes de los éxitos
    pareados (las probabilities llevan etiqueta, no posición: alinear por
    etiqueta es invariante al orden)."""
    diffs = []
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        per = []
        for run in (run_a, run_b):
            doc = store.load(run, ph) or {}
            per.append({cid: jev81._prob_entries(r)
                        for cid, r in (doc.get("cases") or {}).items()
                        if cid in cur and jev81.error_kind(r) is None})
        for cid in sorted(set(per[0]) & set(per[1])):
            for qid in sorted(set(per[0][cid]) & set(per[1][cid])):
                for opt in sorted(set(per[0][cid][qid])
                                  & set(per[1][cid][qid])):
                    diffs.append(abs(per[0][cid][qid][opt]
                                     - per[1][cid][qid][opt]))
    return {"mean": sum(diffs) / len(diffs) if diffs else None,
            "max": max(diffs) if diffs else None, "n": len(diffs),
            "weighting": "media sobre componentes escalares comunes "
                         "(alineados por etiqueta; cada opción una observación)"}


def _costs(run):
    """Coste registrado total, máximo por caso y casos por encima de la
    guarda $0,01 (los desconocidos se listan aparte, no son cero)."""
    total, mx, over, unknown, n = 0.0, None, [], [], 0
    for ph in score.ADJ_PHASES:
        cur = set(jev81._current_ids(ph))
        for cid, r in ((store.load(run, ph) or {})
                       .get("cases") or {}).items():
            if cid not in cur:
                continue
            c = r.get("cost")
            if c is None:
                unknown.append(f"{ph}/{cid}")
                continue
            total += c
            n += 1
            mx = c if mx is None else max(mx, c)
            if c > CASE_COST_CAP:
                over.append(f"{ph}/{cid}")
    return {"total": total, "n_priced": n, "max_case": mx,
            "over_cap": sorted(over), "cap": CASE_COST_CAP,
            "unknown": sorted(unknown)}


def rotation_report(run_a=D0, run_b=D1, printer=print):
    """Informe completo del contraste d1 vs d0 (reglas fijadas arriba)."""
    jev81._sources_compatible(run_a, run_b, printer=printer)
    _order_provenance(run_a, "d0", printer)
    _order_provenance(run_b, "d1", printer)
    _cost_guard_declared(run_b, printer)   # el run d1 debió adquirirse con la guarda
    jev81._check_paired_vectors(run_a, run_b, printer=printer)

    # primacía: el subconjunto congelado debe coincidir antes de calcular
    subset = qs_.primacy_subset()
    sha = qs_.primacy_sha(subset)
    if sha != PRIMACY_SUBSET_SHA:
        raise SystemExit(f"subconjunto de primacía sha {sha} != congelado "
                         f"{PRIMACY_SUBSET_SHA} — GT/casos cambiaron; no se "
                         "recalcula tras inferir")
    prim = qs_.primacy_analysis({"d0": run_a, "d1": run_b})
    verdict = ("CONFIRMADA" if (prim["delta_pp"] is not None
                                and prim["delta_pp"] >= 5
                                and prim["lo"] is not None
                                and prim["lo"] > 0
                                and prim["p_holm_primacy"] < 0.05)
               else "REFUTADA" if (prim["hi"] is not None and prim["hi"] < 5)
               else "INCONCLUSA")

    k, n, p, lo, hi = jev81._agreement_current(run_a, run_b)
    pa, vsa = jev81._adjusted_phases(run_a)
    pb, vsb = jev81._adjusted_phases(run_b)
    delta = qs_.paired_delta(run_a, run_b, level=0.95)

    pairs, va, vb = _paired_versions(run_a, run_b)
    v_mismatch = sorted(c for c in pairs
                        if va[c] is not None and vb[c] is not None
                        and va[c] != vb[c])
    v_unknown = sorted(c for c in pairs
                       if va[c] is None or vb[c] is None)
    n_known = sum(1 for c in pairs
                  if va[c] is not None and vb[c] is not None)

    return {"run_d0": run_a, "run_d1": run_b,
            "agreement": {"k": k, "n": n, "p": p, "ci": (lo, hi),
                          "reference": AGREEMENT_REF,
                          "reference_on": "estimación puntual",
                          "meets": p >= AGREEMENT_REF if n else None},
            "dp": _dp_paired(run_a, run_b),
            "adjusted": {"delta": delta,
                         "phases_a": pa, "phases_b": pb,
                         "same_phases": pa == pb,
                         "adj_a": (100 * sum(vsa[x] for x in pa) / len(pa)
                                   if pa else None),
                         "adj_b": (100 * sum(vsb[x] for x in pb) / len(pb)
                                   if pb else None)},
            "primacy": {**prim, "verdict": verdict,
                        "rule": "CONFIRMADA si Δ>=5 pp, L95>0 y significativa "
                                "tras Holm (familia: d0vsd1 todos + primacía); "
                                "REFUTADA si U95<5; si no, INCONCLUSA"},
            "rejections": _rejections_paired(_rejections(run_a),
                                           _rejections(run_b)),
            "versions": {"paired_successes": len(pairs),
                         "known_pairs": n_known,
                         "mismatch": v_mismatch, "unknown": v_unknown,
                         "same_model": (n_known >= 1 and not v_mismatch
                                        and not v_unknown)},
            "cost": {"d0": _costs(run_a), "d1": _costs(run_b)},
            "provenance": {"questions_hash_a": jev81._qhash_map(run_a),
                           "questions_hash_b": jev81._qhash_map(run_b),
                           "source_sha": jev81._source_sha(run_a, run_b),
                           "gt_scoring_sha": jev81._gt_scoring_sha(),
                           "primacy_subset_sha": sha,
                           "primacy_subset_n": len(subset)}}


def _print_report(rep, printer=print):
    ag = rep["agreement"]
    printer(f"rotación d1 de department — {rep['run_d0']} (d0) vs "
            f"{rep['run_d1']} (d1)")
    printer(f"acuerdo pareado: {ag['k']}/{ag['n']} = "
            f"{score.fmt(100 * ag['p'])}% IC95 "
            f"{score.fmt(100 * ag['ci'][0])}–{score.fmt(100 * ag['ci'][1])} "
            f"(referencia >= {100 * ag['reference']:.0f} % sobre la "
            f"estimación: {'SÍ' if ag['meets'] else 'NO'})")
    d = rep["adjusted"]["delta"]
    if d:
        printer(f"ajustado d1−d0: {score.fmt(d['delta'], 2)} IC95 "
                f"{score.fmt(d['lo'], 2)}–{score.fmt(d['hi'], 2)} "
                f"({d['reps']} réplicas; fases comunes completas: "
                f"{', '.join(d['phases'])})")
    else:
        printer("ajustado d1−d0: sin fases comunes completas")
    if not rep["adjusted"]["same_phases"]:
        printer(f"AVISO: fases completas distintas (d0: "
                f"{rep['adjusted']['phases_a']} vs d1: "
                f"{rep['adjusted']['phases_b']}) — el Δ usa la intersección")
    pr = rep["primacy"]
    printer(f"primacía (subconjunto congelado {rep['provenance']['primacy_subset_sha']}, "
            f"n={pr['n_paired']} pareados): Δ errores department "
            f"{score.fmt(pr['delta_pp'], 2)} pp IC95 "
            f"{score.fmt(pr['lo'], 2)}–{score.fmt(pr['hi'], 2)}; "
            f"McNemar b={pr['mcnemar_primacy']['b']} "
            f"c={pr['mcnemar_primacy']['c']} "
            f"p_holm={score.fmt(pr['p_holm_primacy'], 4)} -> {pr['verdict']}")
    printer(f"  errores: d0={pr['errors']['d0']} d1={pr['errors']['d1']}")
    rj = rep["rejections"]
    printer(f"rechazos/errores: en ambos {rj['both'] or 'ninguno'}; "
            f"solo d0 {rj['only_d0'] or '—'}; solo d1 "
            f"{rj['only_d1'] or '—'}; por tipo {rj['error_kinds']}")
    v = rep["versions"]
    if not v["same_model"]:
        printer(f"AVISO: versión servida distinta/ausente en éxitos "
                f"pareados ({len(v['mismatch'])} distintos "
                f"{v['mismatch'][:5]}, {len(v['unknown'])} desconocidos "
                f"{v['unknown'][:5]}, de {v['paired_successes']} pares) — "
                f"el contraste no es del mismo modelo")
    dp = rep["dp"]
    printer(f"Δp: media {score.fmt(dp['mean'], 4)} máx "
            f"{score.fmt(dp['max'], 4)} ({dp['n']} componentes)")
    for tag, c in (("d0", rep["cost"]["d0"]), ("d1", rep["cost"]["d1"])):
        flag = f" — SOBRE LA GUARDA: {c['over_cap']}" if c["over_cap"] else ""
        printer(f"coste {tag}: ${c['total']:.4f} registrado en "
                f"{c['n_priced']} casos (máx "
                f"${c['max_case'] or 0:.5f}; desconocidos "
                f"{len(c['unknown'])}){flag}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jevbench.jev82",
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="contraste d1 vs d0 (offline)")
    an.add_argument("run_a", nargs="?", default=D0)
    an.add_argument("run_b", nargs="?", default=D1)
    an.add_argument("--json", help="vuelca el informe completo a un fichero")
    args = ap.parse_args(argv)
    rep = rotation_report(args.run_a, args.run_b)
    _print_report(rep)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1, default=str)
        print(f"informe escrito en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
