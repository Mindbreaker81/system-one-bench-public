"""JEV-90 — análisis opt-in de Microsoft-Decision-1 (pre-registro).

Pre-registro: docs/infra_runs/ms_decision1_jev90.md.

Este módulo **no** altera el comportamiento por defecto de `jev81`,
`jev82` ni `score`. Solo se usa cuando el comando o import lo invocan
explícitamente (puerta de snapshot, Holm confirmatorio sin IDs
expuestos, primacía confirmatoria, discordancias de `department`,
preflight, costes; cupo global por construcción).

Reglas fijadas antes de medir (R94 / T31b / R96 / T31c / R98 / T31d):
  1) IDs expuestos antes del pre-registro quedan fuera de *todos* los
     integrantes de las familias confirmatorias (Holm53 y primacía
     {todos, primacía}); la batería completa sigue para lo descriptivo.
  2) Negativa por pregunta (`answers[qid]={"type":"refusal"}`) = 0 en
     esa pregunta; el resto se conserva. jev81/jev82 exigen vectores
     ordinarios completos → si hay negativas parciales, esos análisis
     no aplican (NO EVALUABLE) y este módulo lista las marcas.
  3) Puerta de snapshot único: todas las versiones por caso =
     EXPECTED_SNAPSHOT y ≥1 par/éxito válido; si no → NO EVALUABLE.
  4) Familia Holm 53 con exclusión; celdas sin observaciones → p=1,
     n=0 (entran en Holm). Comando confirmatorio exige preflight
     (universo/hash) + puerta de snapshot antes de etiquetar.
  5) Réplica (`--r2`) ausente, con drift, negativas parciales, sin
     cobertura de control o sin vectores conformes → NO EVALUABLE
     (nunca REFUTADA). Sin `--r2` válido no hay veredicto causal
     (NO EVALUABLE; el conteo d0↔d1 es descriptivo).
  6) Contador «0 cambios»: D1 debe declarar rotación (choice_order /
     perm_sha256 por fase) + guarda; D0 procedencia canónica.
  7) Contrastes confirmatorios validan vectores pareados completos
     (`_check_paired_vectors`) antes de calcular.
  8) Cupo GLOBAL ≤ $0,15 POR CONSTRUCCIÓN: exactamente 3 runs (D0, R, D1)
     con guardas fijas `--max-case-cost 0.01 --max-cost 0.05` cada uno
     (un único retry dentro de la misma guarda). Sin cupo dinámico ni
     `effective_max_cost` en el procedimiento. Parada al tope del run
     sin reanudación salvo enmienda. Sobrepaso ≤1 caso post-guarda
     declarado por run.
  9) Desconocidos: `capture-unknowns` antes de cada retry distingue
     capturados (reemplazo no acreditado) de reemplazos comprobados.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys

from . import cost_guard, jev78, jev81, jev82, metrics as M, score, store
from . import qwen_session as qs_
from .battery import load_phase
from .diag65_report import _decisions
from .jev67 import holm

EXPECTED_SNAPSHOT = "microsoft/microsoft-decision-1-20261009"
D0 = "jev_ms_decision1"
R2 = "jev_ms_decision1_r2"
D1 = "jev_ms_decision1_d1"
REF = "jev_v3"
EXPERIMENT_CELLS = (D0, R2, D1)

# Casos del banco vistos en el humo T31 (10-oct-2026) antes de fijar
# hipótesis confirmatorias. Congelado: no se amplía tras medir.
EXPOSED_CASE_IDS = {
    "ood": frozenset({"receta", "contrato"}),
    "triage_es": frozenset({"T01_ebus_alergia", "T02_factura_duplicada"}),
}

# Sondas previas al endpoint (10-oct): estados sintéticos ajenos al banco.
# Inventario procedimental — no son ids de la batería.
EXPOSED_SYNTHETIC_PROBES = (
    {
        "id": "probe_roast_chicken_20261010",
        "state_prefix": "Roast the chicken",
        "note": ("sonda previa (10-oct): estado sintético, no caso del "
                 "banco; no entra en scorers ni en Holm"),
    },
)

CASE_COST_CAP = 0.01
RUN_COST_CAP = 0.05
GLOBAL_EXPERIMENT_BUDGET = 0.15   # cupo GLOBAL D0+R+D1 (operativo)
PHASES_11 = tuple(score.ADJ_PHASES)
PHASES_11_CSV = ",".join(PHASES_11)
PRIMACY_SUBSET_SHA = jev82.PRIMACY_SUBSET_SHA


def exposed_tags():
    """Lista estable `fase/id` de los casos del banco expuestos."""
    return sorted(f"{ph}/{cid}"
                  for ph, ids in sorted(EXPOSED_CASE_IDS.items())
                  for cid in sorted(ids))


def is_exposed(phase, case_id):
    return case_id in EXPOSED_CASE_IDS.get(phase, ())


def holm_cells_confirm(run_a, run_b, exclude=None):
    """Familia de 53 celdas McNemar–Holm excluyendo IDs expuestos.

    Misma geometría que `qwen_session.holm_cells` (53 filas), pero sin
    observaciones de `exclude` (por defecto EXPOSED_CASE_IDS). Celda sin
    pares válidos → n=0, p=1.0 (entra en Holm; no se omite).
    """
    skip = exclude if exclude is not None else EXPOSED_CASE_IDS
    rows = []
    for ph in qs_.PHASES_ALL:
        qs, cases = load_phase(ph)
        ban = set(skip.get(ph, ()))
        da = store.load(run_a, ph) or {}
        db = store.load(run_b, ph) or {}
        ra, rb = da.get("cases") or {}, db.get("cases") or {}
        for qid, q in qs.items():
            ha, hb = [], []
            for c in cases:
                if c.id in ban:
                    continue
                x, y = ra.get(c.id), rb.get(c.id)
                if (not isinstance(x, dict) or not isinstance(y, dict)
                        or "error" in x or "error" in y):
                    continue
                ax = (x.get("answers") or {}).get(qid)
                ay = (y.get("answers") or {}).get(qid)
                # refusal por pregunta: normalize → refused → exact=False
                pa = M.normalize(ax, q)
                pb = M.normalize(ay, q)
                ha.append(M.exact(q, pa, c.gt[qid]))
                hb.append(M.exact(q, pb, c.gt[qid]))
            if not ha:
                b_, c_, p = 0, 0, 1.0
            else:
                b_, c_, p = M.mcnemar(ha, hb)
            rows.append({"cell": f"{ph}.{qid}", "b": b_, "c": c_,
                         "p": p, "n": len(ha),
                         "excluded": sorted(ban)})
    for r, a in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = a
    return rows


def _dept_hits_confirm(run, exclude=None):
    """Acierto department por (fase, id), sin IDs expuestos ni refusals."""
    skip = exclude if exclude is not None else EXPOSED_CASE_IDS
    out = {}
    for ph in qs_.PHASES_ALL:
        qs, cases = load_phase(ph)
        if "department" not in qs:
            continue
        ban = set(skip.get(ph, ()))
        doc = store.load(run, ph) or {}
        recs = doc.get("cases") or {}
        for c in cases:
            if c.id in ban:
                continue
            rec = recs.get(c.id)
            if not isinstance(rec, dict) or "error" in rec:
                continue
            dec = _decisions(rec, qs).get("department")
            if dec is None:
                continue
            out[(ph, c.id)] = (dec == c.gt["department"])
    return out


def primacy_analysis_confirm(run_d0, run_d1, exclude=None,
                             iters=qs_.BOOT_ITERS, seed=qs_.BOOT_SEED,
                             level=0.95):
    """Primacía confirmatoria JEV-90: mismo criterio/subconjunto JEV-82,
    pero la familia Holm {todos, primacía} excluye IDs expuestos en
    *todos* sus integrantes. La salida de `jev82 analyze` /
    `qwen_session.primacy_analysis` sigue siendo descriptiva.
    """
    runs_by_order = {"d0": run_d0, "d1": run_d1}
    orders = sorted(runs_by_order)
    hits = {o: _dept_hits_confirm(runs_by_order[o], exclude=exclude)
            for o in orders}
    subset = qs_.primacy_subset()
    sha = qs_.primacy_sha(subset)
    pair = [pc for pc in subset
            if pc in hits["d0"] and pc in hits["d1"]]
    err = {o: [0 if hits[o][pc] else 1 for pc in pair] for o in orders}
    delta = (100 * (sum(err["d0"]) - sum(err["d1"])) / len(pair)
             if pair else None)
    units = {}
    for pc in pair:
        units.setdefault(pc[1], []).append(pc)
    units = list(units.values())
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        draw = rng.choices(units, k=len(units)) if units else []
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
        lo, hi = qs_._pct(reps, level)
    es = qs_._es_subset(pair)
    if es:
        b_, c_, p_prim = M.mcnemar([hits["d0"][pc] for pc in es],
                                  [hits["d1"][pc] for pc in es])
    else:
        b_, c_, p_prim = 0, 0, 1.0
    pvals, labels = [], []
    todos_ids = []
    for i, o1 in enumerate(orders):
        for o2 in orders[i + 1:]:
            common = qs_._es_subset(
                [pc for pc in hits[o1] if pc in hits[o2]])
            todos_ids = [f"{ph}/{cid}" for ph, cid in common]
            if common:
                _, _, p = M.mcnemar([hits[o1][pc] for pc in common],
                                    [hits[o2][pc] for pc in common])
            else:
                p = 1.0
            pvals.append(p)
            labels.append(f"{o1}vs{o2} todos")
    pvals.append(p_prim)
    labels.append("primacía")
    adj = holm(pvals)
    return {
        "subset": subset, "subset_sha": sha,
        "n_paired": len(pair), "delta_pp": delta, "lo": lo, "hi": hi,
        "errors": {o: sum(err[o]) for o in orders},
        "error_ids": {o: [f"{pc[0]}/{pc[1]}"
                          for pc, e in zip(pair, err[o]) if e]
                      for o in orders},
        "mcnemar_primacy": {"b": b_, "c": c_, "p": p_prim, "n": len(es)},
        "holm": sorted(zip(labels, pvals, adj), key=lambda x: x[2]),
        "p_holm_primacy": adj[-1],
        "exclude_exposed": True,
        "todos_ids": todos_ids,
        "exposed_excluded": exposed_tags(),
    }


def primacy_confirm_verdict(run_d0, run_d1, expected=EXPECTED_SNAPSHOT,
                            iters=qs_.BOOT_ITERS, seed=qs_.BOOT_SEED,
                            printer=lambda *a, **k: None):
    """Veredicto confirmatorio de primacía con puertas JEV-90."""
    gate = snapshot_gate_pair(run_d0, run_d1, expected=expected)
    if has_question_refusals(run_d0) or has_question_refusals(run_d1):
        return {"verdict": "NO EVALUABLE",
                "reason": "negativas parciales por pregunta",
                "snapshot": gate, "primacy": None}
    if not gate["evaluable"]:
        return {"verdict": "NO EVALUABLE",
                "reason": "snapshot drift/ausente o <1 par válido",
                "snapshot": gate, "primacy": None}
    try:
        jev81._sources_compatible(run_d0, run_d1, printer=printer)
        jev82._order_provenance(run_d0, "d0", printer=printer)
        jev82._order_provenance(run_d1, "d1", printer=printer)
        jev82._cost_guard_declared(run_d1, printer=printer)
        jev81._check_paired_vectors(run_d0, run_d1, printer=printer)
    except SystemExit as e:
        return {"verdict": "NO EVALUABLE",
                "reason": f"procedencia/vectores d0↔d1 ({e})",
                "snapshot": gate, "primacy": None}
    subset = qs_.primacy_subset()
    if qs_.primacy_sha(subset) != PRIMACY_SUBSET_SHA:
        return {"verdict": "NO EVALUABLE",
                "reason": "subconjunto de primacía distinto del congelado",
                "snapshot": gate, "primacy": None}
    prim = primacy_analysis_confirm(run_d0, run_d1, iters=iters, seed=seed)
    if (prim["delta_pp"] is not None and prim["delta_pp"] >= 5
            and prim["lo"] is not None and prim["lo"] > 0
            and prim["p_holm_primacy"] < 0.05):
        verdict = "CONFIRMADA"
    elif prim["hi"] is not None and prim["hi"] < 5:
        verdict = "REFUTADA"
    else:
        verdict = "INCONCLUSA"
    return {"verdict": verdict, "reason": None, "snapshot": gate,
            "primacy": prim}


def question_refusals(run):
    """Reutiliza el inventario de marcas por pregunta (convención JEV-78)."""
    return jev78.question_refusals(run)


def has_question_refusals(run):
    qr = question_refusals(run)
    return any(qr[ph] for ph in qr)


def analysis_formats():
    """Qué análisis admite cada formato de negativa (fijado ahora)."""
    return {
        "case_rejection_502": {
            "marker": "error_kind=rejection (HTTP 502 + «refused to answer»)",
            "scoring": ("registro de caso entero con error; fuera del "
                        "ajustado oficial sin imputación"),
            "score": "sí (fase incompleta si hay error)",
            "holm_confirm": "parejas con error omitidas (n baja)",
            "jev81_repeat": "sí (rechazos desglosados; no entran en acuerdo)",
            "jev82_rotation": "sí (rechazos desglosados; no entran en pares)",
        },
        "question_refusal": {
            "marker": 'answers[qid]={"type":"refusal"} (HTTP 200 parcial)',
            "scoring": ("esa pregunta = 0 (metrics.point); el resto del "
                        "caso se conserva"),
            "score": "sí (pregunta a 0)",
            "holm_confirm": "sí (exact=False en la pregunta rechazada)",
            "jev81_repeat": ("NO — `_check_paired_vectors` exige respuestas "
                             "ordinarias; contraste → NO EVALUABLE"),
            "jev82_rotation": ("NO — misma validación; contraste → "
                               "NO EVALUABLE"),
            "jev90": "lista marcas; veredictos confirmatorios con puerta",
        },
    }


def _success_versions(run):
    """{fase/id: model|None} de registros sin error de caso (universo)."""
    out = {}
    for ph in PHASES_11:
        cur = set(jev81._current_ids(ph))
        doc = store.load(run, ph) or {}
        for cid, r in (doc.get("cases") or {}).items():
            if cid not in cur or jev81.error_kind(r) is not None:
                continue
            out[f"{ph}/{cid}"] = r.get("model")
    return out


def snapshot_gate(runs, expected=EXPECTED_SNAPSHOT):
    """Puerta de snapshot único sobre uno o varios runs.

    exigencia: ≥1 éxito con versión conocida en el conjunto, y TODAS las
    versiones observadas (éxitos) iguales a `expected`. Ausencia o
    discrepancia → evaluable=False (NO EVALUABLE como propiedad del
    snapshot fijado). Los números entre versiones solo descriptivos.
    """
    if isinstance(runs, str):
        runs = [runs]
    observed = {}
    drift, unknown = [], []
    for run in runs:
        for tag, model in _success_versions(run).items():
            key = f"{run}:{tag}"
            observed[key] = model
            if model is None:
                unknown.append(key)
            elif model != expected:
                drift.append(key)
    n_known = sum(1 for m in observed.values()
                  if m is not None and m == expected)
    evaluable = bool(n_known >= 1 and not drift and not unknown
                     and len(observed) >= 1)
    return {
        "expected": expected,
        "runs": list(runs),
        "n_successes": len(observed),
        "n_expected": n_known,
        "drift": sorted(drift),
        "unknown": sorted(unknown),
        "evaluable": evaluable,
        "versions_seen": sorted({m for m in observed.values()
                                 if m is not None}),
    }


def snapshot_gate_pair(run_a, run_b, expected=EXPECTED_SNAPSHOT):
    """Puerta sobre un par (R o D1): snapshot único + ≥1 par válido."""
    gate = snapshot_gate([run_a, run_b], expected=expected)
    pairs = []
    for ph in PHASES_11:
        cur = set(jev81._current_ids(ph))
        ra = {cid for cid, r in ((store.load(run_a, ph) or {})
                                 .get("cases") or {}).items()
              if cid in cur and jev81.error_kind(r) is None}
        rb = {cid for cid, r in ((store.load(run_b, ph) or {})
                                 .get("cases") or {}).items()
              if cid in cur and jev81.error_kind(r) is None}
        pairs.extend(f"{ph}/{c}" for c in sorted(ra & rb))
    gate["n_valid_pairs"] = len(pairs)
    gate["evaluable"] = bool(gate["evaluable"] and len(pairs) >= 1)
    gate["pair_runs"] = [run_a, run_b]
    return gate


def department_discords(run_d0, run_d1, exclude_exposed=True):
    """Cambios de decisión en `department` entre d0 y d1 (éxitos pareados).

    Por defecto excluye IDs expuestos (lectura confirmatoria del
    fabricante). `exclude_exposed=False` → descriptivo sobre todos.
    """
    discords = []
    n_paired = 0
    paired_ids = []
    for ph in PHASES_11:
        qs, _ = load_phase(ph)
        if "department" not in qs:
            continue
        cur = set(jev81._current_ids(ph))
        da, db = {}, {}
        for run, acc in ((run_d0, da), (run_d1, db)):
            for cid, r in ((store.load(run, ph) or {})
                           .get("cases") or {}).items():
                if cid not in cur or jev81.error_kind(r) is not None:
                    continue
                if exclude_exposed and is_exposed(ph, cid):
                    continue
                acc[cid] = _decisions(r, qs)
        for cid in sorted(set(da) & set(db)):
            va = da[cid].get("department")
            vb = db[cid].get("department")
            if va is None or vb is None:
                continue
            n_paired += 1
            paired_ids.append(f"{ph}/{cid}")
            if va != vb:
                discords.append({"case": f"{ph}/{cid}",
                                 "d0": va, "d1": vb})
    return {"n_paired": n_paired, "n_changes": len(discords),
            "discords": discords, "paired_ids": paired_ids,
            "exclude_exposed": exclude_exposed}


def _replica_control_ok(run_d0, run_r2, dep_d0_d1, expected=EXPECTED_SNAPSHOT,
                        printer=lambda *a, **k: None):
    """Puertas de la réplica canónica cuando se pasa `--r2`.

    Exige: run presente, universo/hashes, snapshot, procedencia de orden
    canónico (d0), vectores pareados conformes, sin negativas parciales,
    ≥1 par department tras exclusión, y cobertura del control sobre los
    casos discordantes d0↔d1. Ante fallo → (False, reason, None|int).
    El conteo d0↔d1 se conserva como descriptivo en el llamador.
    """
    if not store.runs_in(run_r2):
        return False, "réplica ausente", None
    try:
        jev81._sources_compatible(run_d0, run_r2, printer=printer)
    except SystemExit as e:
        return False, f"réplica: universo/hash ({e})", None
    try:
        jev82._order_provenance(run_d0, "d0", printer=printer)
        jev82._order_provenance(run_r2, "d0", printer=printer)
    except SystemExit as e:
        return False, f"réplica: procedencia de orden canónico ({e})", None
    try:
        jev81._check_paired_vectors(run_d0, run_r2, printer=printer)
    except SystemExit as e:
        return False, f"réplica: vectores no conformes ({e})", None
    if has_question_refusals(run_r2):
        return False, "negativas parciales por pregunta en la réplica", None
    rg = snapshot_gate_pair(run_d0, run_r2, expected=expected)
    if not rg["evaluable"]:
        return False, "snapshot drift/ausente en la réplica o <1 par válido", None
    rdep = department_discords(run_d0, run_r2, exclude_exposed=True)
    if rdep["n_paired"] < 1:
        return False, "réplica sin pares department válidos tras exclusión", None
    control = set(rdep.get("paired_ids") or [])
    for d in (dep_d0_d1 or {}).get("discords") or []:
        if d["case"] not in control:
            return False, ("réplica sin cobertura de control sobre el caso "
                           f"contrastado {d['case']}"), None
    return True, None, rdep["n_changes"]


def manufacturer_zero_change_verdict(run_d0, run_d1, run_r2=None,
                                     expected=EXPECTED_SNAPSHOT,
                                     printer=lambda *a, **k: None):
    """Veredicto acotado de «0 cambios» del fabricante.

    - snapshot drift / sin pares / negativas parciales → NO EVALUABLE;
    - D1 debe acreditar rotación (choice_order/perm_sha256) + guarda;
      D0 procedencia canónica; vectores d0↔d1 conformes;
    - sin `--r2` → NO EVALUABLE (conteo descriptivo; sin atribución causal);
    - con `--r2`: réplica evaluable (universo, hash, snapshot, orden
      canónico, vectores, sin negativas, cobertura de control);
      si falla → NO EVALUABLE (nunca REFUTADA por omisión del control);
      si la réplica ya cambia department → NO EVALUABLE (no se atribuye
      al orden);
    - n_changes ≥ 1 (excl. expuestos) + R válida → REFUTADA;
    - n_changes = 0 + R válida → COMPATIBLE/INCONCLUSA.
    """
    gate = snapshot_gate_pair(run_d0, run_d1, expected=expected)
    if has_question_refusals(run_d0) or has_question_refusals(run_d1):
        return {"verdict": "NO EVALUABLE",
                "reason": "negativas parciales por pregunta",
                "snapshot": gate,
                "department": None}
    if not gate["evaluable"]:
        return {"verdict": "NO EVALUABLE",
                "reason": "snapshot drift/ausente o <1 par válido",
                "snapshot": gate,
                "department": None}
    try:
        jev81._sources_compatible(run_d0, run_d1, printer=printer)
        jev82._order_provenance(run_d0, "d0", printer=printer)
        jev82._order_provenance(run_d1, "d1", printer=printer)
        jev82._cost_guard_declared(run_d1, printer=printer)
        jev81._check_paired_vectors(run_d0, run_d1, printer=printer)
    except SystemExit as e:
        dep = department_discords(run_d0, run_d1, exclude_exposed=True)
        return {"verdict": "NO EVALUABLE",
                "reason": f"procedencia/rotación/vectores d0↔d1 ({e})",
                "snapshot": gate, "department": dep,
                "department_descriptive": True}
    dep = department_discords(run_d0, run_d1, exclude_exposed=True)
    if run_r2 is None:
        return {"verdict": "NO EVALUABLE",
                "reason": ("sin réplica canónica (--r2); conteo "
                           "descriptivo sin atribución causal al orden"),
                "snapshot": gate, "department": dep,
                "department_descriptive": True,
                "replica_department_changes": None}
    ok, reason, replica_changes = _replica_control_ok(
        run_d0, run_r2, dep, expected=expected, printer=printer)
    if not ok:
        return {"verdict": "NO EVALUABLE", "reason": reason,
                "snapshot": gate, "department": dep,
                "replica_department_changes": replica_changes,
                "department_descriptive": True}
    if replica_changes >= 1:
        return {"verdict": "NO EVALUABLE",
                "reason": ("la réplica canónica ya cambia "
                           "department; no se atribuye al orden"),
                "snapshot": gate,
                "department": dep,
                "replica_department_changes": replica_changes}
    if dep["n_changes"] >= 1:
        verdict = "REFUTADA"
    else:
        verdict = "COMPATIBLE/INCONCLUSA"
    return {"verdict": verdict, "reason": None, "snapshot": gate,
            "department": dep,
            "replica_department_changes": replica_changes}


def note_unknown_replacement(meta, phase, case_id, old_rec, *, when=None):
    """Append a pre-retry unknown-cost capture to ``meta.cost_unknown_history``.

    Contrato JEV-90 P3: la captura **no** acredita reemplazo. Guarda el
    intento vigente sin coste con ``replaced=False`` /
    ``status=captured_pre_retry``. El reemplazo solo se comprueba después
    (caso con ``error`` que el retry sustituyó). Flujo publicado:
    ``capture-unknowns`` **antes** de cada ``--retry-errors``.
    """
    if not (isinstance(old_rec, dict) and old_rec.get("cost") is None
            and ("answers" in old_rec or "error" in old_rec
                 or "usage" in old_rec)):
        return False
    hist = meta.setdefault("cost_unknown_history", [])
    if any(e.get("phase") == phase and e.get("case") == case_id
           for e in hist):
        return False
    hist.append({
        "phase": phase, "case": case_id, "replaced": False,
        "status": "captured_pre_retry",
        "had_error": "error" in old_rec,
        "when": when or dt.datetime.now().isoformat(timespec="seconds"),
    })
    return True


def _replacement_accredited(entry, cur):
    """True solo si el capturado tenía error y el vigente ya no es ese
    desconocido con error (tiene coste o dejó de ser error). Éxitos sin
    coste y retries bloqueados no acreditan reemplazo."""
    if not entry.get("had_error"):
        return False
    if not isinstance(cur, dict):
        return False
    if cur.get("cost") is not None:
        return True
    if "error" in cur and cur.get("cost") is None:
        return False
    return "answers" in cur or "usage" in cur


def capture_unknowns(run, *, when=None):
    """Persiste intentos sin coste vigentes en ``meta.cost_unknown_history``.

    Comando exacto a ejecutar **antes** de cada ``--retry-errors`` (opt-in;
    no modifica ``run.py``). La captura etiqueta «reemplazo no acreditado»;
    ``costs`` solo lista en ``unknown_replaced`` los reemplazos comprobados
    tras el retry. Vacío en ``unknown_replaced`` no acredita ausencia si
    este comando no se ejecutó antes del reemplazo.
    """
    n = 0
    tags = []
    for ph in store.runs_in(run):
        doc = store.load(run, ph) or {}
        meta = doc.setdefault("meta", {})
        changed = False
        for cid, r in list((doc.get("cases") or {}).items()):
            if note_unknown_replacement(meta, ph, cid, r, when=when):
                n += 1
                tags.append(f"{ph}/{cid}")
                changed = True
        if changed:
            store.save(run, ph, doc)
    return {"run": run, "captured": n, "tags": sorted(tags),
            "note": ("capturados antes del retry; reemplazo no acreditado "
                     "hasta que costs compruebe la sustitución")}


def costs_report(run):
    """Suma final de `cost` vigentes, máximo del ledger durable e
    inventario de desconocidos (vigentes / capturados / reemplazados)."""
    docs = cost_guard.load_phase_docs(store, run)
    recorded, ledger = cost_guard.recorded_and_ledger(docs)
    unknown_current = []
    unknown_captured = []
    unknown_replaced = []
    for ph in store.runs_in(run):
        doc = store.load(run, ph) or {}
        cases = doc.get("cases") or {}
        for cid, r in cases.items():
            if not isinstance(r, dict):
                continue
            if r.get("cost") is None and (
                    "answers" in r or "error" in r or "usage" in r):
                unknown_current.append(f"{ph}/{cid}")
        for entry in (doc.get("meta") or {}).get("cost_unknown_history") or []:
            eph = entry.get("phase", ph)
            ecid = entry.get("case")
            if not ecid:
                continue
            tag = f"{eph}/{ecid}"
            cur = cases.get(ecid) if eph == ph else (
                (store.load(run, eph) or {}).get("cases") or {}).get(ecid)
            if _replacement_accredited(entry, cur):
                unknown_replaced.append(tag)
            else:
                unknown_captured.append(tag)
    return {
        "run": run,
        "recorded_sum": recorded,
        "ledger_max": ledger,
        "unknown": sorted(unknown_current),
        "unknown_current": sorted(unknown_current),
        "unknown_captured": sorted(set(unknown_captured)),
        "unknown_replaced": sorted(set(unknown_replaced)),
        "note": ("recorded_sum = suma de cost vigentes; ledger_max = "
                 "máximo meta.cost_ledger (incluye retries reemplazados); "
                 "unknown_current = registros vigentes sin coste; "
                 "unknown_captured = capturados con `jev90 capture-unknowns` "
                 "antes del retry (reemplazo no acreditado: éxitos sin coste "
                 "o errores cuyo retry no sustituyó); "
                 "unknown_replaced = reemplazos comprobados (había error sin "
                 "coste y el vigente ya tiene coste o dejó de ser error); "
                 "lista vacía de replaced no acredita ausencia si no se "
                 "ejecutó capture-unknowns; intentos HTTP internos del "
                 "adaptador sin trazabilidad individual; no se estima "
                 "desconocido como gasto medido ni dispara guardas"),
    }


def experiment_spent(runs=None):
    """Gasto durable agregado del experimento (suma de prior_cost por celda)."""
    runs = tuple(runs) if runs is not None else EXPERIMENT_CELLS
    per = {}
    total = 0.0
    for run in runs:
        if not store.runs_in(run):
            per[run] = 0.0
            continue
        docs = cost_guard.load_phase_docs(store, run)
        spent = cost_guard.prior_cost(docs) if docs else 0.0
        per[run] = spent
        total += spent
    return total, per


def global_budget_status(ceiling=GLOBAL_EXPERIMENT_BUDGET,
                         margin_reserved=CASE_COST_CAP, runs=None):
    """Estado del cupo GLOBAL: spent durable, remaining tras margen."""
    spent, per = experiment_spent(runs)
    remaining, margin_left = cost_guard.remaining_budget(
        ceiling=ceiling, spent=spent, margin_reserved=margin_reserved)
    return {
        "ceiling": ceiling,
        "spent": spent,
        "per_run": per,
        "remaining": remaining,
        "margin_reserved": margin_reserved,
        "margin_left": margin_left,
        "allows_next_cell": remaining > 0,
        "run_cap": RUN_COST_CAP,
        "case_cap": CASE_COST_CAP,
    }


def check_global_budget_before(run, ceiling=GLOBAL_EXPERIMENT_BUDGET,
                               margin_reserved=CASE_COST_CAP,
                               run_cap=RUN_COST_CAP, runs=None):
    """Helper legado (R96/R98): cupo dinámico con ``effective_max_cost``.

    **No forma parte del procedimiento JEV-90 (T31e / R99).** El cupo
    global ≤ $0,15 queda garantizado por construcción (3 runs × guarda
    fija 0,05 + un retry dentro de la misma guarda; sin reanudación tras
    tope salvo enmienda). Se conserva por si hace falta diagnóstico
    offline; el borrador y los comandos publicados no lo invocan.
    """
    st = global_budget_status(ceiling=ceiling,
                              margin_reserved=margin_reserved, runs=runs)
    run_spent = float((st["per_run"] or {}).get(run) or 0.0)
    spent_other = float(st["spent"]) - run_spent
    room_for_cell = float(ceiling) - spent_other - float(margin_reserved)
    effective = min(float(run_cap), max(0.0, room_for_cell))
    st["spent_other"] = spent_other
    st["run_spent"] = run_spent
    st["effective_max_cost"] = effective
    st["procedure_note"] = (
        "T31e: el procedimiento publicado NO usa este helper; cupo "
        "global por construcción (3×$0,05)")
    st["overshoot_note"] = (
        "guarda post-caso: el último caso puede sobrepasar el tope "
        "en ≤ un caso; no garantiza techo estricto ≤ ceiling")
    if st["remaining"] <= 0 or effective <= 0:
        st["reason"] = "cupo global del experimento agotado o sin margen"
        st["allows_next_cell"] = False
        return False, st
    if run_spent <= 0 and st["remaining"] < run_cap:
        st["reason"] = (f"cupo global restante {st['remaining']:.4f} < "
                        f"tope/run {run_cap}; no se inicia {run}")
        st["allows_next_cell"] = False
        return False, st
    if run_spent > 0 and run_spent >= effective:
        st["reason"] = (f"reanudación de {run}: gasto durable {run_spent:.4f} "
                        f">= tope efectivo {effective:.4f} "
                        f"(otras celdas {spent_other:.4f})")
        st["allows_next_cell"] = False
        return False, st
    st["reason"] = None
    st["allows_next_cell"] = True
    return True, st


def preflight(run, ref=REF, printer=print):
    """Comando ejecutable: universo, hashes, IDs expuestos, puerta
    snapshot, inventory de negativas por pregunta. Abortar si el
    universo/hash falla; ref ausente o snapshot no evaluable → ok=False.
    """
    jev81._validate_universe(run, printer=printer)
    if not store.runs_in(ref):
        printer(f"ERROR entrada: referencia ausente: {ref}")
        raise SystemExit(f"preflight: referencia {ref} ausente — no se "
                         "continúa")
    jev81._sources_compatible(run, ref, printer=printer)
    gate = snapshot_gate(run)
    qr = question_refusals(run)
    n_ref = sum(len(v) for v in qr.values())
    out = {
        "run": run,
        "ref": ref,
        "phases": list(PHASES_11),
        "n_phases": len(PHASES_11),
        "exposed_bank": exposed_tags(),
        "exposed_synthetic": list(EXPOSED_SYNTHETIC_PROBES),
        "snapshot": gate,
        "question_refusals_cases": n_ref,
        "holm_family_cells": 53,
        "holm_empty_cell_policy": "n=0,p=1 (entra en Holm)",
        "ok": bool(gate["evaluable"]),
    }
    printer(f"preflight JEV-90 {run}: fases={out['n_phases']}; "
            f"expuestos banco={len(out['exposed_bank'])}; "
            f"sondas sintéticas={len(out['exposed_synthetic'])}; "
            f"snapshot_evaluable={gate['evaluable']}; "
            f"refusals_por_pregunta_casos={n_ref}")
    for tag in out["exposed_bank"]:
        printer(f"  expuesto: {tag}")
    for p in out["exposed_synthetic"]:
        printer(f"  sonda: {p['id']} («{p['state_prefix']}…»)")
    if not gate["evaluable"]:
        printer("NO EVALUABLE: puerta de snapshot "
                f"(drift={gate['drift'][:5]}, unknown={gate['unknown'][:5]}, "
                f"n_successes={gate['n_successes']})")
    return out


def holm53_confirm(run_a, run_b, *, descriptive=False, printer=print):
    """Holm53 con puertas: universo/hash + snapshot del lado Microsoft.

    Confirmatorio solo si las puertas pasan. Fallos de entrada → abort
    (SystemExit). Drift/ausencia → NO EVALUABLE (sin filas confirmatorias).
    `--descriptive` omite puertas y etiqueta la salida como descriptiva.
    """
    if descriptive:
        rows = holm_cells_confirm(run_a, run_b)
        return {"verdict": "DESCRIPTIVO", "rows": rows, "ok": True}

    if not store.runs_in(run_a) or not store.runs_in(run_b):
        printer("NO EVALUABLE: run(s) ausente(s) — no hay familia "
                "confirmatoria")
        return {"verdict": "NO EVALUABLE",
                "reason": "runs ausentes", "rows": None, "ok": False}

    jev81._sources_compatible(run_a, run_b, printer=printer)

    # Snapshot del lado Microsoft (run_a en el comando documentado D0 vs REF)
    gate = snapshot_gate(run_a)
    if not gate["evaluable"]:
        printer("NO EVALUABLE: puerta de snapshot en "
                f"{run_a} (drift={gate['drift'][:5]}, "
                f"n_successes={gate['n_successes']}) — Holm53 no "
                "confirmatorio")
        return {"verdict": "NO EVALUABLE", "reason": "snapshot",
                "snapshot": gate, "rows": None, "ok": False}

    rows = holm_cells_confirm(run_a, run_b)
    return {"verdict": "OK", "rows": rows, "snapshot": gate, "ok": True}


def _print_holm(rows, only_sig=False, printer=print, label="confirmatorio"):
    printer(f"Holm53 {label} n={len(rows)} "
            f"(excluye {exposed_tags()}; vacías p=1)")
    show = ([r for r in rows if r["p_holm"] < 0.05] if only_sig
            else rows)
    if only_sig:
        printer(f"p_holm<0.05 → {len(show)}")
    for r in sorted(show, key=lambda x: (x["p_holm"], x["cell"])):
        printer(f"  {r['cell']} b={r['b']} c={r['c']} p={r['p']:.4g} "
                f"p_holm={r['p_holm']:.4g} n={r['n']}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jevbench.jev90",
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("preflight", help="universo, expuestos, snapshot")
    pf.add_argument("run", nargs="?", default=D0)
    pf.add_argument("--ref", default=REF)

    hm = sub.add_parser("holm53", help="53 filas Holm confirmatorias")
    hm.add_argument("run_a", nargs="?", default=D0)
    hm.add_argument("run_b", nargs="?", default=REF)
    hm.add_argument("--sig-only", action="store_true",
                    help="solo p_holm<0.05 (por defecto: las 53)")
    hm.add_argument("--descriptive", action="store_true",
                    help="sin puertas: Holm descriptivo (no confirmatorio)")
    hm.add_argument("--json", help="vuelca las filas a fichero")

    pr = sub.add_parser("primacy",
                        help="primacía confirmatoria sin IDs expuestos")
    pr.add_argument("run_d0", nargs="?", default=D0)
    pr.add_argument("run_d1", nargs="?", default=D1)
    pr.add_argument("--iters", type=int, default=qs_.BOOT_ITERS)
    pr.add_argument("--json", help="vuelca el informe")

    dd = sub.add_parser("department-discords",
                        help="contador y lista de cambios department")
    dd.add_argument("run_d0", nargs="?", default=D0)
    dd.add_argument("run_d1", nargs="?", default=D1)
    dd.add_argument("--include-exposed", action="store_true")
    dd.add_argument("--r2", help="réplica canónica (atribución de orden)")
    dd.add_argument("--json", help="vuelca el informe")

    sg = sub.add_parser("snapshot", help="puerta de snapshot único")
    sg.add_argument("runs", nargs="+")
    sg.add_argument("--json", help="vuelca el informe")

    cs = sub.add_parser("costs", help="suma final / ledger / desconocidos")
    cs.add_argument("run", nargs="?", default=D0)

    cu = sub.add_parser(
        "capture-unknowns",
        help="persiste desconocidos vigentes ANTES de --retry-errors")
    cu.add_argument("run", nargs="?", default=D0)

    bg = sub.add_parser(
        "budget",
        help="diagnóstico del ledger agregado (no es el procedimiento T31e)")
    bg.add_argument("--before", metavar="RUN",
                    help="helper legado effective_max_cost (no publicado)")
    bg.add_argument("--json", help="vuelca el estado")

    fm = sub.add_parser("formats", help="qué análisis admite cada negativa")

    args = ap.parse_args(argv)

    if args.cmd == "preflight":
        try:
            out = preflight(args.run, ref=args.ref)
        except SystemExit as e:
            print(f"ABORT preflight: {e}")
            return 2
        return 0 if out.get("ok") else 2

    if args.cmd == "holm53":
        try:
            rep = holm53_confirm(args.run_a, args.run_b,
                                 descriptive=args.descriptive)
        except SystemExit as e:
            print(f"ABORT holm53: {e}")
            return 2
        if not rep.get("ok"):
            print(f"veredicto: {rep.get('verdict')} "
                  f"({rep.get('reason')})")
            return 2
        label = ("descriptivo" if args.descriptive else "confirmatorio")
        _print_holm(rep["rows"], only_sig=args.sig_only, label=label)
        if args.json:
            with open(args.json, "w") as f:
                json.dump(rep["rows"], f, indent=1)
            print(f"escrito {args.json}")
        return 0

    if args.cmd == "primacy":
        rep = primacy_confirm_verdict(args.run_d0, args.run_d1,
                                      iters=args.iters)
        prim = rep.get("primacy") or {}
        print(f"primacía confirmatoria (excluye {exposed_tags()}): "
              f"{rep['verdict']}"
              + (f" ({rep['reason']})" if rep.get("reason") else ""))
        if prim:
            print(f"  subset_sha={prim.get('subset_sha')} "
                  f"n_paired={prim.get('n_paired')} "
                  f"Δ={prim.get('delta_pp')} "
                  f"p_holm_primacy={prim.get('p_holm_primacy')}")
            for lab, p, ph in prim.get("holm") or []:
                print(f"  {lab}: p={p:.4g} p_holm={ph:.4g}")
        if args.json:
            with open(args.json, "w") as f:
                json.dump(rep, f, indent=1)
            print(f"escrito {args.json}")
        return 0 if rep["verdict"] != "NO EVALUABLE" else 2

    if args.cmd == "department-discords":
        try:
            rep = manufacturer_zero_change_verdict(
                args.run_d0, args.run_d1, run_r2=args.r2)
        except SystemExit as e:
            print(f"ABORT department-discords: {e}")
            return 2
        if args.include_exposed and args.r2 is None:
            dep_all = department_discords(
                args.run_d0, args.run_d1, exclude_exposed=False)
            rep = dict(rep)
            rep["department"] = dep_all
        dep = rep.get("department") or {}
        print(f"department discords: {dep.get('n_changes', '—')}/"
              f"{dep.get('n_paired', '—')} "
              f"(exclude_exposed={dep.get('exclude_exposed')})")
        for d in dep.get("discords") or []:
            print(f"  {d['case']}: {d['d0']} → {d['d1']}")
        label = ("veredicto fabricante «0 cambios»"
                 if args.r2 else
                 "veredicto fabricante «0 cambios» (sin --r2: no causal)")
        print(f"{label}: {rep['verdict']}"
              + (f" ({rep['reason']})" if rep.get("reason") else ""))
        if args.json:
            with open(args.json, "w") as f:
                json.dump(rep, f, indent=1)
            print(f"escrito {args.json}")
        return 0 if rep["verdict"] != "NO EVALUABLE" else 2

    if args.cmd == "snapshot":
        if len(args.runs) == 2:
            gate = snapshot_gate_pair(args.runs[0], args.runs[1])
        else:
            gate = snapshot_gate(args.runs)
        print(json.dumps(gate, indent=1))
        if args.json:
            with open(args.json, "w") as f:
                json.dump(gate, f, indent=1)
        return 0 if gate["evaluable"] else 2

    if args.cmd == "costs":
        print(json.dumps(costs_report(args.run), indent=1))
        return 0

    if args.cmd == "capture-unknowns":
        out = capture_unknowns(args.run)
        print(json.dumps(out, indent=1))
        return 0

    if args.cmd == "budget":
        if args.before:
            ok, st = check_global_budget_before(args.before)
            st["ok"] = ok
            print(json.dumps(st, indent=1))
            if args.json:
                with open(args.json, "w") as f:
                    json.dump(st, f, indent=1)
            return 0 if ok else 2
        st = global_budget_status()
        print(json.dumps(st, indent=1))
        if args.json:
            with open(args.json, "w") as f:
                json.dump(st, f, indent=1)
        return 0 if st["allows_next_cell"] else 2

    if args.cmd == "formats":
        print(json.dumps(analysis_formats(), indent=1, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
