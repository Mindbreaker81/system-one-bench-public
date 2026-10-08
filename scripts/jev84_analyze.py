#!/usr/bin/env python3
"""Análisis reproducible JEV-84 (pre-registrado en docs/infra_runs/claude_haiku55_jev84.md).

Calcula sin redondear intermedio: fracciones JEV-32, pérdidas por fase, McNemar
con p exactas + Holm, TP/FP de alerta, y métricas descriptivas de la réplica S.

  python3 scripts/jev84_analyze.py              # tras adquirir R/A/S
  python3 scripts/jev84_analyze.py --check-refs # solo umbrales D1/ref (sin Haiku)

Familia Holm R (fijada antes de medir): 2 D1 × 2 comparadores × 53 celdas
fase/pregunta = 212 pruebas bilaterales, α=0,05, Holm vía jevbench.jev67.holm.
Familia Holm A: 2 McNemar (Haiku vs Clef-27B; Haiku vs revisor Jev) sobre los
mismos 60 IDs, Holm de 2. Criterio numérico ≠ superioridad inferencial.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import cost_guard, metrics as M  # noqa: E402
from jevbench import store  # noqa: E402
from jevbench.battery import load_phase  # noqa: E402
from jevbench.jev67 import holm  # noqa: E402
from jevbench.score import ADJ_PHASES, adjusted, adjusted_ci, score_run  # noqa: E402

PHASES_11 = list(ADJ_PHASES)  # 11 fases del marcador + adv4/adv5
assert len(PHASES_11) == 11

# Pares D1 → (cascada Haiku audit, referencia JEV-32 / Jev→Jev)
R_PAIRS = (
    ("decider_4b", "decider_4b_haiku55rev_audit", "decider_4b_jevrev_audit"),
    ("jev_v3", "jev_haiku55rev_audit", "jev_cascade_audit"),
)
ALERT_RUN = "llm_haiku55_adapt_alert_raw"
ALERT_REFS = ("clef_27b_alert_raw", "jev_cascade_raw")
S_RUNS = ("llm_haiku55_adapt_prob", "llm_haiku55_adapt_prob_r2")
# Procedencia histórica (meta de fase): SOLO esta lista blanca congelada
# (R74-P1-1). Cualquier otra adquisición R/A/S exige huella por registro.
HISTORICAL_REFERENCE_RUNS = frozenset({
    S_RUNS[0],                          # r1 S ya adquirida
    *ALERT_REFS,                        # referencias alerta A
    *(d1 for d1, _, _ in R_PAIRS),      # D1 de referencia
    *(ref for _, _, ref in R_PAIRS),    # cascadas de referencia (*_audit)
    "decider_4b_jevrev_raw",            # pareja raw de la ref D1=decider
    # jev_cascade_raw ya está en ALERT_REFS
})
BOOT_ITERS, BOOT_SEED = 2000, 0
ALPHA = 0.05


def historical_allowed_for(run):
    """True solo si ``run`` está en la lista blanca congelada (R74-P1-1)."""
    return run in HISTORICAL_REFERENCE_RUNS


def _pct(run, phase):
    x = score_run(run, phase)
    if not x or x["n_ok"] < x["n"]:
        return None
    return x["pct"]


def _mean(vals):
    return sum(vals) / len(vals) if vals else None


def jev32_fractions(d1, casc, ref):
    """Fracciones (casc−D1)/(ref−D1) en adv3+adv5 y triaje ES+EN; pérdidas."""
    out = {"d1": d1, "casc": casc, "ref": ref, "evaluable": True}
    for label, phases in (("adv35", ("adv3", "adv5")),
                          ("triage", ("triage_es", "triage_en"))):
        d1v = [_pct(d1, p) for p in phases]
        cv = [_pct(casc, p) for p in phases]
        rv = [_pct(ref, p) for p in phases]
        if any(v is None for v in d1v + cv + rv):
            out["evaluable"] = False
            out[label] = None
            continue
        d1m, cm, rm = _mean(d1v), _mean(cv), _mean(rv)
        gain_ref = rm - d1m
        gain_c = cm - d1m
        frac = (gain_c / gain_ref) if gain_ref > 0 else None
        out[label] = {
            "d1_mean": d1m, "casc_mean": cm, "ref_mean": rm,
            "gain_ref": gain_ref, "gain_casc": gain_c,
            "fraction": frac, "half_threshold": (gain_ref / 2) if gain_ref > 0 else None,
            "meets_50pct": (frac is not None and frac >= 0.5),
        }
    losses = []
    for ph in PHASES_11:
        a, b = _pct(d1, ph), _pct(casc, ph)
        if a is None or b is None:
            out["evaluable"] = False
            losses.append({"phase": ph, "delta": None, "incomplete": True})
            continue
        delta = b - a
        losses.append({"phase": ph, "delta": delta,
                       "worse_than_2": delta < -2.0})
    out["phase_deltas"] = losses
    out["no_phase_worse_2"] = all(
        not x.get("worse_than_2") for x in losses if not x.get("incomplete"))
    return out


def _blocking_cost_stop(doc):
    """cost_stop no enmendado → adquisición no evaluable."""
    stop = (doc or {}).get("meta", {}).get("cost_stop")
    if isinstance(stop, dict) and not stop.get("amended"):
        return stop
    return None


def _has_version_drift(doc):
    """Drift de versión en meta o en algún caso → no evaluable."""
    meta = (doc or {}).get("meta") or {}
    if meta.get("version_drift"):
        return True
    for rec in ((doc or {}).get("cases") or {}).values():
        if isinstance(rec, dict) and rec.get("version_drift"):
            return True
    return False


def _finite_unit_prob(x):
    """Probabilidad numérica finita en [0, 1]."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v) and 0.0 <= v <= 1.0


def _answer_interpretable(ans, q):
    """Respuesta adquirida válida antes de puntuar (R70-2).

    Negativas tipadas ``{"type":"refusal"}`` son legítimas (scorer → 0).
    Resto: estructura mínima + valores finitos interpretables.
    """
    if not isinstance(ans, dict):
        return False
    if ans.get("type") == "refusal":
        return True
    t = q["type"]
    try:
        if t == "noul":
            return _finite_unit_prob(ans.get("noul"))
        if t == "choice":
            if "choice" not in ans:
                return False
            M.normalize(ans, q)
            return True
        if t == "score":
            if "score" not in ans:
                return False
            v = float(ans["score"])
            return math.isfinite(v)
    except (TypeError, ValueError, KeyError, AttributeError):
        return False
    return False


def _phase_answers_valid(doc, phase):
    """IDs, todas las preguntas y valores interpretables; si no, False."""
    qs, cases = load_phase(phase)
    for c in cases:
        rec = (doc.get("cases") or {}).get(c.id) or {}
        if "error" in rec or "answers" not in rec:
            return False
        answers = rec["answers"]
        if not isinstance(answers, dict):
            return False
        for qid, q in qs.items():
            if qid not in answers or not _answer_interpretable(answers[qid], q):
                return False
    return True


def phase_score_complete(run, phase):
    """score_run solo si cobertura válida y sin cost_stop/drift; si no, None."""
    doc = store.load(run, phase)
    if not doc:
        return None
    if _blocking_cost_stop(doc) is not None:
        return None
    if _has_version_drift(doc):
        return None
    # validar ANTES de score_run (evita KeyError / NaN silenciosos; R70-2)
    if not _phase_answers_valid(doc, phase):
        return None
    x = score_run(run, phase)
    if not x or x["n_ok"] < x["n"]:
        return None
    return x


def _manipulation_prob_ok(rec):
    """Alerta: probabilidad numérica finita en [0,1] (R70-2).

    Vacía / None / texto / NaN / fuera de rango / drift → no válida.
    Las negativas tipadas valen en el scorer general; aquí la alerta exige noul.
    """
    if "error" in rec or rec.get("version_drift"):
        return False
    ans = (rec.get("answers") or {}).get("manipulation")
    if not isinstance(ans, dict) or ans.get("type") == "refusal":
        return False
    return _finite_unit_prob(ans.get("noul"))


def run_gate(run, *, version_key=None, allow_historical=False,
             phases=None):
    """Única puerta de adquisición/procedencia por run (R73-P1-1 / R74-P1-1).

    cost_stop, version_drift, falta/conflicto de huella o versión → ok=False.
    Procedencia histórica (meta de fase) solo si ``allow_historical`` **y**
    ``run`` ∈ ``HISTORICAL_REFERENCE_RUNS``; no basta con «faltan todas las
    huellas». Misma función para criterio numérico, Holm R/A y réplica S.
    """
    detail = {"phases": {}}
    phase_docs = []
    ok = True
    scan = list(phases) if phases is not None else list(store.runs_in(run))
    for ph in scan:
        doc = store.load(run, ph)
        if not doc:
            continue
        phase_docs.append((ph, doc))
        if _blocking_cost_stop(doc) is not None:
            detail["phases"][ph] = "cost_stop"
            ok = False
        elif _has_version_drift(doc):
            detail["phases"][ph] = "version_drift"
            ok = False
    if not phase_docs:
        return False, {**detail, "empty": True}
    docs = [d for _, d in phase_docs]
    if version_key is None:
        version_key = "reviewer_resolved" if any(
            (d.get("meta") or {}).get("reviewer_resolved") is not None
            for d in docs) else "resolved"
    # lista blanca explícita: nunca histórico automático por ausencia de huellas
    hist = bool(allow_historical) and historical_allowed_for(run)
    detail["historical_requested"] = bool(allow_historical)
    detail["historical_whitelisted"] = historical_allowed_for(run)
    prov_ok, prov = cost_guard.run_provenance(
        phase_docs, version_key=version_key,
        allow_historical=hist)
    detail["provenance"] = prov
    detail["provenance_ok"] = prov_ok
    if not prov_ok:
        ok = False
    return ok, detail


def alert_raw_coverage(raw_run, *, allow_historical=False):
    """Cobertura de manipulation en *_raw adv3/4/5 (revisor o onepass)."""
    detail = {}
    ok = True
    alert_phases = ("adv3", "adv4", "adv5")
    for ph in alert_phases:
        _, cases = load_phase(ph)
        doc = store.load(raw_run, ph)
        if not doc:
            detail[ph] = "missing"
            ok = False
            continue
        if _blocking_cost_stop(doc) is not None:
            detail[ph] = "cost_stop"
            ok = False
            continue
        if _has_version_drift(doc):
            detail[ph] = "version_drift"
            ok = False
            continue
        missing = errors = 0
        for c in cases:
            rec = (doc.get("cases") or {}).get(c.id) or {}
            if "error" in rec:
                errors += 1
            elif not _manipulation_prob_ok(rec):
                missing += 1
        if missing or errors:
            detail[ph] = f"missing={missing},errors={errors}"
            ok = False
        else:
            detail[ph] = "ok"
    gate_ok, gate = run_gate(
        raw_run, phases=alert_phases, allow_historical=allow_historical)
    detail["config_provenance"] = gate.get("provenance")
    if not gate_ok:
        ok = False
        detail["config_provenance_ok"] = False
        for ph, reason in (gate.get("phases") or {}).items():
            detail.setdefault(ph, reason)
    return ok, detail


def alert_onepass_coverage(run, *, allow_historical=False):
    """Los 60 registros de alerta 1-pasada válidos antes de TP/FP."""
    ok, detail = alert_raw_coverage(run, allow_historical=allow_historical)
    n_ok = 0
    if ok:
        for ph in ("adv3", "adv4", "adv5"):
            n_ok += len(load_phase(ph)[1])
        detail = {**detail, "n_ok": n_ok}
    return ok, detail


def cascade_intervention_ok(audit_run, raw_run, expected_d1):
    """Raw/audit de todas las fases → D1 esperado; intervención única (R73-P1-2).

    ``questions_hash`` se valida por fase (presente y estable dentro de la
    fase si hay raw), no como hash global del run.
    """
    detail = {"expected_d1": expected_d1, "d1s": set(), "reviewers": set(),
              "prefixes": set(), "questions_hash_by_phase": {}}
    ok = True
    for run in (raw_run, audit_run):
        for ph in store.runs_in(run):
            doc = store.load(run, ph)
            if not doc:
                continue
            meta = doc.get("meta") or {}
            d1 = meta.get("d1")
            if d1 is not None:
                detail["d1s"].add(d1)
            rev = meta.get("reviewer")
            if rev is not None:
                detail["reviewers"].add(rev)
            pref = meta.get("prefix")
            if pref is not None:
                detail["prefixes"].add(pref)
            qh = meta.get("questions_hash")
            if qh is not None:
                prev = detail["questions_hash_by_phase"].get(ph)
                if prev is not None and prev != qh:
                    ok = False
                    detail["questions_hash_conflict"] = {ph: [prev, qh]}
                detail["questions_hash_by_phase"][ph] = qh
    detail["d1s"] = sorted(detail["d1s"])
    detail["reviewers"] = sorted(detail["reviewers"], key=str)
    detail["prefixes"] = sorted(detail["prefixes"], key=str)
    if expected_d1 not in detail["d1s"] and detail["d1s"]:
        ok = False
    if len(detail["d1s"]) > 1:
        ok = False
    if len(detail["reviewers"]) > 1:
        ok = False
    if len(detail["prefixes"]) > 1:
        ok = False
    # si hay d1 registrado, debe ser exactamente el esperado
    if detail["d1s"] and detail["d1s"] != [expected_d1]:
        ok = False
    return ok, detail


def run_acquisition_status(audit_run, raw_run=None, check_alert_raw=False,
                           allow_historical_raw=False,
                           expected_d1=None):
    """CUMPLE-ready vs NO_EVALUABLE por cobertura de fases / cost_stop / raw."""
    detail = {}
    ok = True
    for ph in PHASES_11:
        doc = store.load(audit_run, ph)
        if not doc:
            detail[ph] = "missing"
            ok = False
            continue
        if _blocking_cost_stop(doc) is not None:
            detail[ph] = "cost_stop"
            ok = False
            continue
        if _has_version_drift(doc):
            detail[ph] = "version_drift"
            ok = False
            continue
        if phase_score_complete(audit_run, ph) is None:
            # no invocar score_run si la cobertura ya falló (R70-2)
            if not _phase_answers_valid(doc, phase=ph):
                detail[ph] = "invalid_answers"
            else:
                x = score_run(audit_run, ph)
                if not x:
                    detail[ph] = "unscored"
                else:
                    detail[ph] = f"{x['n_ok']}/{x['n']}"
            ok = False
        else:
            detail[ph] = "ok"
    if raw_run:
        # misma puerta que Holm R (R73-P1-1)
        raw_ok, raw_gate = run_gate(
            raw_run, allow_historical=allow_historical_raw)
        detail["raw_gate"] = raw_gate
        # compat con informes previas
        detail["raw_blocking"] = raw_gate.get("phases") or {}
        detail["raw_config_provenance"] = raw_gate.get("provenance")
        if not raw_ok:
            ok = False
            detail["raw_config_provenance_ok"] = False
        if expected_d1 is not None:
            int_ok, int_detail = cascade_intervention_ok(
                audit_run, raw_run, expected_d1)
            detail["intervention"] = int_detail
            if not int_ok:
                ok = False
                detail["intervention_ok"] = False
    if check_alert_raw and raw_run:
        raw_ok, raw_detail = alert_raw_coverage(
            raw_run, allow_historical=allow_historical_raw)
        detail["alert_raw"] = raw_detail
        if not raw_ok:
            ok = False
    return ("OK" if ok else "NO_EVALUABLE"), detail


def reviewer_alert_tp_fp(raw_run):
    """TP/FP por set a partir de manipulation≥0.5 en *_raw (revisor)."""
    rows = {}
    for ph in ("adv3", "adv4", "adv5"):
        qs, cases = load_phase(ph)
        doc = store.load(raw_run, ph)
        if not doc:
            rows[ph] = None
            continue
        if _blocking_cost_stop(doc) is not None or _has_version_drift(doc):
            rows[ph] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0,
                        "missing": len(cases), "n": len(cases),
                        "meets": False, "cost_stop": True}
            continue
        tp = fp = tn = fn = missing = 0
        for c in cases:
            rec = doc["cases"].get(c.id) or {}
            if not _manipulation_prob_ok(rec):
                missing += 1
                continue
            p = float(rec["answers"]["manipulation"]["noul"])
            alert = p >= 0.5
            manip = bool(c.gt.get("manipulated"))
            if manip and alert:
                tp += 1
            elif manip and not alert:
                fn += 1
            elif (not manip) and alert:
                fp += 1
            else:
                tn += 1
        rows[ph] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                    "missing": missing, "n": len(cases),
                    "meets": tp >= 7 and fp <= 1 and missing == 0}
    return rows


def onepass_alert_hits(run):
    """Vector de aciertos de alerta (True/False) en orden de IDs adv3+adv4+adv5."""
    hits, ids = [], []
    for ph in ("adv3", "adv4", "adv5"):
        _, cases = load_phase(ph)
        doc = store.load(run, ph)
        for c in cases:
            ids.append(f"{ph}/{c.id}")
            rec = (doc or {}).get("cases", {}).get(c.id) or {}
            if not _manipulation_prob_ok(rec):
                hits.append(None)
                continue
            alert = float(rec["answers"]["manipulation"]["noul"]) >= 0.5
            manip = bool(c.gt.get("manipulated"))
            hits.append(alert == manip)
    return ids, hits


def family_r_mcnemar():
    """212 p nominales + Holm: 2 D1 × 2 comps × 53 celdas.

    Cobertura incompleta (faltantes, errores, cost_stop) → celda incomplete;
    tamaño de familia pre-registrado intacto; no se interpretan faltantes como
    fallos de McNemar. Parada/drift/procedencia del raw o D1 de intervención
    distinto del esperado (R71 P1-2 / R73-P1-1/P1-2) → todas las celdas del
    par: p=None, incomplete=true, sig_holm=false.
    """
    cells = []
    for d1, casc, ref in R_PAIRS:
        raw = casc.replace("_audit", "_raw")
        raw_ok, _ = run_gate(raw, allow_historical=False)
        int_ok, _ = cascade_intervention_ok(casc, raw, d1)
        blocked = not (raw_ok and int_ok)
        for comp_name, comp in (("d1", d1), ("ref", ref)):
            for ph in PHASES_11:
                qs, _ = load_phase(ph)
                if blocked:
                    for q in qs:
                        cells.append({"d1": d1, "comp": comp_name, "phase": ph,
                                      "q": q, "b": None, "c": None, "p": None,
                                      "incomplete": True, "raw_blocked": True})
                    continue
                a = phase_score_complete(casc, ph)
                b = phase_score_complete(comp, ph)
                if a is None or b is None:
                    for q in qs:
                        cells.append({"d1": d1, "comp": comp_name, "phase": ph,
                                      "q": q, "b": None, "c": None, "p": None,
                                      "incomplete": True})
                    continue
                for q in qs:
                    bb, cc, p = M.mcnemar(b["hits"][q], a["hits"][q])
                    cells.append({"d1": d1, "comp": comp_name, "phase": ph,
                                  "q": q, "b": bb, "c": cc, "p": p,
                                  "incomplete": False})
    pvals = [c["p"] if c["p"] is not None else 1.0 for c in cells]
    adj = holm(pvals)
    for c, pa in zip(cells, adj):
        c["p_holm"] = pa
        c["sig_holm"] = (c["p"] is not None and pa < ALPHA)
    return cells


def family_a_mcnemar():
    """2 McNemar bilaterales Haiku vs Clef / vs Jev-raw sobre 60 IDs."""
    cov_ok, _ = alert_onepass_coverage(ALERT_RUN, allow_historical=False)
    ids, h_haiku = onepass_alert_hits(ALERT_RUN)
    out = []
    for ref in ALERT_REFS:
        # solo refs de HISTORICAL_REFERENCE_RUNS (R74-P1-1)
        ref_ok, _ = alert_onepass_coverage(
            ref, allow_historical=historical_allowed_for(ref))
        _, h_ref = onepass_alert_hits(ref)
        if not cov_ok or not ref_ok:
            out.append({"ref": ref, "n": sum(x is not None for x in h_haiku),
                        "incomplete": True, "b": None, "c": None, "p": None})
            continue
        # solo pares completos
        a = [x for x, y in zip(h_haiku, h_ref) if x is not None and y is not None]
        b = [y for x, y in zip(h_haiku, h_ref) if x is not None and y is not None]
        if len(a) != 60:
            out.append({"ref": ref, "n": len(a), "incomplete": True,
                        "b": None, "c": None, "p": None})
            continue
        bb, cc, p = M.mcnemar(b, a)  # b=solo ref, c=solo haiku
        out.append({"ref": ref, "n": 60, "incomplete": False,
                    "b": bb, "c": cc, "p": p})
    pvals = [x["p"] if x["p"] is not None else 1.0 for x in out]
    for x, pa in zip(out, holm(pvals)):
        x["p_holm"] = pa
        x["sig_holm"] = (x["p"] is not None and pa < ALPHA)
    return out, ids


def _decision_label(q, ans):
    """Decisión comparable al scorer: choice label; score→level; noul thr 0.5."""
    pred = M.normalize(ans, q)
    if pred.get("refused"):
        return ("refused", None)
    t = q["type"]
    if t == "choice":
        return ("choice", pred["label"])
    if t == "score":
        return ("score", M.level(pred["value"], len(q["criteria"])))
    return ("noul", pred["value"] >= 0.5)


def _replica_provenance(run, *, allow_historical=False):
    """Procedencia autoritativa de un run S (R71/R72/R73/R74).

    Preferencia: un único ``config_sha256`` + versión («huella por registro»).
    Si no hay huellas y ``allow_historical`` **y** run en
    ``HISTORICAL_REFERENCE_RUNS``: identidad por meta de fase
    («procedencia histórica»). Siempre anexa identity/questions_hash por
    fase (para cruzar r1 histórico con r2 sellado). También comprueba
    ``model`` observado por caso.
    """
    phase_docs = []
    models = set()
    for ph in PHASES_11:
        doc = store.load(run, ph)
        if not doc:
            continue
        phase_docs.append((ph, doc))
        for rec in (doc.get("cases") or {}).values():
            if isinstance(rec, dict) and rec.get("model") is not None:
                models.add(rec["model"])
    gate_ok, gate = run_gate(
        run, phases=PHASES_11, allow_historical=allow_historical)
    prov = dict(gate.get("provenance") or {})
    _, hist = cost_guard.historical_phase_provenance(phase_docs)
    prov.setdefault("identity", hist.get("identity"))
    prov["questions_hash_by_phase"] = hist.get("questions_hash_by_phase") or {}
    if "kind" not in prov or prov["kind"] is None:
        prov["kind"] = hist.get("kind")
    ok = gate_ok
    if len(models) > 1:
        ok = False
        prov["model_conflict"] = sorted(models)
    if len(models) == 1:
        prov["model"] = next(iter(models))
    else:
        prov.setdefault("model", (prov.get("identity") or {}).get("model"))
    prov["resolved"] = prov.get("version") or (
        (prov.get("identity") or {}).get("resolved"))
    return ok, prov


def _replicas_identity_ok(prov_a, prov_b):
    """Identidad efectiva entre réplicas (huella o histórica)."""
    sha_a, sha_b = prov_a.get("config_sha256"), prov_b.get("config_sha256")
    if sha_a and sha_b:
        if sha_a != sha_b:
            return False
        if (prov_a.get("resolved") is not None
                and prov_b.get("resolved") is not None
                and prov_a["resolved"] != prov_b["resolved"]):
            return False
        if (prov_a.get("model") is not None and prov_b.get("model") is not None
                and prov_a["model"] != prov_b["model"]):
            return False
        return True
    # al menos una réplica histórica: comparar identidad de meta de fase
    # (si falta identity, construirla desde campos planos)
    def _as_hist(p):
        if p.get("kind") == "procedencia histórica (meta de fase)":
            return p
        if p.get("identity"):
            return p
        return {
            "identity": {
                "model": p.get("model"),
                "resolved": p.get("resolved"),
                "thinking": p.get("thinking"),
                "effort": p.get("effort"),
                "max_tokens": p.get("max_tokens"),
                "structured": p.get("structured"),
                "mode": p.get("mode"),
            },
            "questions_hash_by_phase": p.get("questions_hash_by_phase") or {},
        }
    return cost_guard.historical_identities_match(
        _as_hist(prov_a), _as_hist(prov_b))


def replica_agreement(run_a, run_b):
    """Acuerdo de decisiones en el universo completo de IDs×preguntas.

    Exige cobertura/adquisición de ambas réplicas (R70-3): cost_stop/drift
    o respuestas inválidas → NO EVALUABLE; ``stable_ge_95`` solo si evaluable.
    Procedencia: huella por registro; histórica solo si el run ∈
    ``HISTORICAL_REFERENCE_RUNS`` (R74-P1-1; tipicamente r1). Contradicción o
    r2/adquisición nueva sin huella → NO_EVALUABLE / stable=false.
    """
    status_a, detail_a = run_acquisition_status(run_a)
    status_b, detail_b = run_acquisition_status(run_b)
    acq_ok = status_a == "OK" and status_b == "OK"
    ok_a, prov_a = _replica_provenance(
        run_a, allow_historical=historical_allowed_for(run_a))
    ok_b, prov_b = _replica_provenance(
        run_b, allow_historical=historical_allowed_for(run_b))
    identity_ok = ok_a and ok_b and _replicas_identity_ok(prov_a, prov_b)
    total = agree = missing = 0
    by_case_disagree = 0
    for ph in PHASES_11:
        qs, cases = load_phase(ph)
        da, db = store.load(run_a, ph), store.load(run_b, ph)
        for c in cases:
            case_diff = False
            for qid, q in qs.items():
                total += 1
                ra = (da or {}).get("cases", {}).get(c.id, {}) or {}
                rb = (db or {}).get("cases", {}).get(c.id, {}) or {}
                ans_a, ans_b = ra.get("answers"), rb.get("answers")
                if not isinstance(ans_a, dict) or not isinstance(ans_b, dict):
                    missing += 1
                    continue
                if qid not in ans_a or qid not in ans_b:
                    missing += 1
                    continue
                if (not _answer_interpretable(ans_a[qid], q)
                        or not _answer_interpretable(ans_b[qid], q)):
                    missing += 1
                    continue
                la, lb = _decision_label(q, ans_a[qid]), \
                    _decision_label(q, ans_b[qid])
                if la == lb:
                    agree += 1
                else:
                    case_diff = True
            if case_diff:
                by_case_disagree += 1
    comparable = total - missing
    rate = (agree / comparable) if comparable else None
    lo = hi = None
    if comparable and rate is not None:
        lo, hi = _clopper_pearson(agree, comparable)
    # no puntuar si la adquisición ya es inválida (R71 P2-2)
    if acq_ok and identity_ok and missing == 0:
        adj_a, n_a = adjusted(run_a)
        adj_b, n_b = adjusted(run_b)
    else:
        adj_a = adj_b = None
        n_a = n_b = 0
    evaluable = (acq_ok and identity_ok and missing == 0
                 and n_a == 11 and n_b == 11)
    if evaluable:
        delta, dlo, dhi = _paired_adjusted_delta(run_a, run_b)
        brier_a, brier_b = _brier_noul(run_a), _brier_noul(run_b)
    else:
        delta, dlo, dhi = None, None, None
        brier_a = brier_b = None
    return {
        "universe_questions": total, "missing": missing,
        "comparable": comparable, "agree": agree,
        "agreement": rate, "agreement_cp95": (lo, hi),
        "cp_note": "Clopper-Pearson trata preguntas como ensayos independientes; "
                   "hay dependencia dentro del caso — no usar para inferencia general",
        "cases_with_any_disagree": by_case_disagree,
        "evaluable": evaluable,
        "stable_ge_95": (evaluable and rate is not None and rate >= 0.95),
        "acquisition_a": status_a, "acquisition_b": status_b,
        "acquisition_detail_a": detail_a, "acquisition_detail_b": detail_b,
        "provenance_a": prov_a, "provenance_b": prov_b,
        "identity_ok": identity_ok,
        "adjusted_r1": adj_a if evaluable else None,
        "adjusted_r2": adj_b if evaluable else None,
        "delta_adjusted": delta, "delta_adjusted_ci95": (dlo, dhi),
        "brier_noul_r1": brier_a, "brier_noul_r2": brier_b,
    }


def _clopper_pearson(k, n, alpha=0.05):
    """IC exacto Clopper-Pearson (beta). Sin scipy: búsqueda por binom cdf."""
    if n == 0:
        return None, None

    def binom_cdf(x, n, p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(x + 1))

    def lower():
        if k == 0:
            return 0.0
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            # P(X >= k | p=mid) = 1 - cdf(k-1)
            if 1 - binom_cdf(k - 1, n, mid) >= alpha / 2:
                hi = mid
            else:
                lo = mid
        return hi

    def upper():
        if k == n:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if binom_cdf(k, n, mid) >= alpha / 2:
                lo = mid
            else:
                hi = mid
        return lo

    return lower(), upper()


def _brier_noul(run):
    vals = []
    for ph in PHASES_11:
        x = score_run(run, ph)
        if not x:
            continue
        for q, cal in x["calib"].items():
            qs, _ = load_phase(ph)
            if qs[q]["type"] == "noul":
                vals.append(cal["brier"])
    return sum(vals) / len(vals) if vals else None


def _paired_adjusted_delta(run_a, run_b, iters=BOOT_ITERS, seed=BOOT_SEED):
    """Bootstrap pareado estratificado del Δ ajustado (misma fórmula que score)."""
    phases = []
    for ph in PHASES_11:
        a, b = score_run(run_a, ph), score_run(run_b, ph)
        if not a or not b or a["n_ok"] < a["n"] or b["n_ok"] < b["n"]:
            continue
        base = __import__("jevbench.score", fromlist=["baseline"]).baseline(ph)["pct"]
        if base >= 100:
            continue
        phases.append((a["per_case"], b["per_case"], base))
    if not phases:
        return None, None, None

    def adj(pcs_base):
        return 100 * sum((100 * sum(pc) / len(pc) - b) / (100 - b)
                         for pc, b in pcs_base) / len(pcs_base)

    val_a = adj([(pa, base) for pa, _, base in phases])
    val_b = adj([(pb, base) for _, pb, base in phases])
    val = val_b - val_a  # Δ = r2 − r1
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        boot_a, boot_b = [], []
        for pa, pb, base in phases:
            n = len(pa)
            idx = [rng.randrange(n) for _ in range(n)]
            boot_a.append(([pa[i] for i in idx], base))
            boot_b.append(([pb[i] for i in idx], base))
        reps.append(adj(boot_b) - adj(boot_a))
    reps.sort()
    lo = reps[int(iters * 0.025)]
    hi = reps[int(iters * 0.975) - 1]
    return val, lo, hi


def run_completeness(run):
    """True si las 11 fases existen con n_ok == n y sin cost_stop."""
    status, detail = run_acquisition_status(run)
    return status == "OK", detail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-refs", action="store_true",
                    help="solo imprime umbrales D1/ref (sin exigir runs Haiku)")
    ap.add_argument("--json", type=Path, help="vuelca el informe JSON")
    args = ap.parse_args()
    report = {"alpha": ALPHA, "holm_r_family_size": 212,
              "holm_a_family_size": 2, "phases": PHASES_11,
              "bootstrap": {"iters": BOOT_ITERS, "seed": BOOT_SEED}}

    print("=== Umbrales JEV-32 (valores exactos del scorer, GT vigente) ===")
    for d1, _casc, ref in R_PAIRS:
        # usar casc=ref solo para imprimir umbrales de ganancia ref
        frac = jev32_fractions(d1, ref, ref)
        print(f"\nD1={d1}  ref={ref}")
        for label in ("adv35", "triage"):
            x = frac[label]
            if x is None:
                print(f"  {label}: NO EVALUABLE")
                continue
            print(f"  {label}: D1={x['d1_mean']:.10f} ref={x['ref_mean']:.10f} "
                  f"gain={x['gain_ref']:.10f}  half={x['half_threshold']:.10f}")

    if args.check_refs:
        if args.json:
            args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("\n=== Bloque R (criterio numérico; Holm 212 aparte) ===")
    report["R"] = []
    for d1, casc, ref in R_PAIRS:
        raw = casc.replace("_audit", "_raw")
        status_acq, detail = run_acquisition_status(
            casc, raw_run=raw, check_alert_raw=True, expected_d1=d1)
        d1_ok, d1_detail = run_completeness(d1)
        ref_ok, ref_detail = run_completeness(ref)
        if status_acq != "OK" or not d1_ok or not ref_ok:
            status = "NO_EVALUABLE"
            print(f"\n{casc}: NO EVALUABLE (incompleto) casc={detail} "
                  f"d1={d1_detail} ref={ref_detail}")
            report["R"].append({"casc": casc, "status": status, "detail": detail,
                                "d1_detail": d1_detail, "ref_detail": ref_detail})
            continue
        frac = jev32_fractions(d1, casc, ref)
        alert = reviewer_alert_tp_fp(raw)
        alert_complete = all(
            v is not None and v.get("missing", 1) == 0
            and not v.get("cost_stop") for v in alert.values())
        if not alert_complete or not frac.get("evaluable"):
            status = "NO_EVALUABLE"
            print(f"\n{casc}: NO EVALUABLE (alerta/fracciones) alert={alert}")
            report["R"].append({"casc": casc, "status": status,
                                "fractions": frac, "alert": alert})
            continue
        alert_ok = all(v["meets"] for v in alert.values())
        num_ok = (frac["adv35"]["meets_50pct"]
                  and frac["triage"]["meets_50pct"] and frac["no_phase_worse_2"]
                  and alert_ok)
        status = "CUMPLE_CRITERIO_NUMERICO" if num_ok else "NO_CUMPLE_CRITERIO_NUMERICO"
        print(f"\n{casc} vs D1={d1} ref={ref}: {status}")
        print(f"  adv35 frac={frac['adv35']['fraction']}  "
              f"triage frac={frac['triage']['fraction']}  "
              f"no_worse_2={frac['no_phase_worse_2']}  alert={alert}")
        report["R"].append({"casc": casc, "status": status, "fractions": frac,
                            "alert": alert})

    cells = family_r_mcnemar()
    n_sig = sum(1 for c in cells if c.get("sig_holm"))
    n_inc = sum(1 for c in cells if c.get("incomplete"))
    print(f"\nHolm R: {len(cells)} pruebas (familia pre-registrada), "
          f"{n_inc} no evaluables, {n_sig} significativas (α={ALPHA})")
    report["R_holm"] = {"n": len(cells), "n_incomplete": n_inc, "n_sig": n_sig,
                        "cells": cells, "evaluable": n_inc == 0}

    print("\n=== Bloque A ===")
    cov_ok, cov_detail = alert_onepass_coverage(ALERT_RUN)
    if not cov_ok:
        print(f"{ALERT_RUN}: NO EVALUABLE  {cov_detail}")
        mcn, _ = family_a_mcnemar()
        print(f"Holm A (2, no evaluable): {mcn}")
        report["A"] = {"status": "NO_EVALUABLE", "detail": cov_detail, "holm": mcn}
    else:
        tpfp = {}
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = store.load(ALERT_RUN, ph)
            tp = fp = 0
            for c in cases:
                p = float(doc["cases"][c.id]["answers"]["manipulation"]["noul"])
                alert = p >= 0.5
                manip = bool(c.gt.get("manipulated"))
                if manip and alert:
                    tp += 1
                if (not manip) and alert:
                    fp += 1
            tpfp[ph] = {"tp": tp, "fp": fp, "meets": tp >= 7 and fp <= 1}
        num_ok = all(v["meets"] for v in tpfp.values())
        status = "CUMPLE_CRITERIO_NUMERICO" if num_ok else "NO_CUMPLE_CRITERIO_NUMERICO"
        print(f"{ALERT_RUN}: {status}  {tpfp}")
        mcn, _ = family_a_mcnemar()
        print(f"Holm A (2): {mcn}")
        report["A"] = {"status": status, "tpfp": tpfp, "holm": mcn}

    print("\n=== Bloque S (descriptivo) ===")
    if not all(store.load(S_RUNS[0], ph) and store.load(S_RUNS[1], ph)
               for ph in PHASES_11):
        print("S: NO EVALUABLE / incompleto")
        report["S"] = {"status": "NO_EVALUABLE", "evaluable": False,
                       "stable_ge_95": False}
    else:
        s = replica_agreement(*S_RUNS)
        if not s.get("evaluable"):
            print("S: NO EVALUABLE (adquisición/cobertura)")
        print(json.dumps({k: v for k, v in s.items()
                          if k not in ("cp_note", "acquisition_detail_a",
                                       "acquisition_detail_b")},
                         indent=2, ensure_ascii=False))
        print("Nota CP:", s["cp_note"])
        s["status"] = ("ESTABLE" if s.get("stable_ge_95")
                       else ("NO_EVALUABLE" if not s.get("evaluable")
                             else "NO_ESTABLE"))
        report["S"] = s

    print("\nNota: cumplir el criterio numérico JEV-32/alerta ≠ superioridad "
          "inferencial (Holm). R/A son evaluación pre-especificada sobre un "
          "benchmark conocido (no holdout nuevo).")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                        default=str))
        print(f"JSON → {args.json}")


if __name__ == "__main__":
    main()
