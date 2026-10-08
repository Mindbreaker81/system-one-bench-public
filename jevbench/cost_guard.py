"""Guarda de coste opt-in compartida (JEV-82 / JEV-84).

Misma semántica base que `jevbench.run`: sin flags no cambia el comportamiento.
Con topes activos: ledger durable, presupuesto agotado con ``>=`` antes de
peticiones, y una parada ``case_cost`` persistida bloquea **toda** reanudación
(cualquier fase) hasta enmienda explícita (`amended=True` en el stop, sin
borrar la evidencia).

Las guardas se evalúan **después** de `decide`: el último caso puede
sobrepasar el tope; costes desconocidos (sin `cost`) no disparan ni suman.

Configuración efectiva canónica (JEV-84 R72): todos los campos de
petición/contabilidad con ``None``/ausente comparable; solo
``DYNAMIC_OBSERVED_KEYS`` admite «desconocido aún» = None en el lado nuevo.
Cada caso adquirido puede guardar ``config_sha256`` de esa canónica.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

# Campos de petición / contabilidad del adaptador (configuración canónica).
# d1/reviewer/prefix = identidad de la intervención (cascade; R73-P1-2).
# questions_hash NO entra aquí: varía legítimamente por fase (se valida aparte).
CONFIG_FINGERPRINT_KEYS = (
    "provider", "model", "mode", "structured", "normalize",
    "thinking", "effort", "timeout", "case_timeout", "max_tokens",
    "reasoning_effort", "retries_malformed", "prompt",
    # petición / contabilidad (R69 F2)
    "base_url", "extra_body", "usd_per_mtok", "usd_in", "usd_out",
    # identidad efectiva del prompt / orden (R70-6)
    "prompt_sha256", "system_prompt_sha256", "prompt_template_sha256",
    "inject_schema_in_prompt", "rotate_choice", "perm_sha256", "choice_order",
    # versión observada (también en DYNAMIC: None al iniciar)
    "resolved",
    # intervención cascade (estable entre fases)
    "d1", "reviewer", "prefix",
)

# Identidad histórica por meta de fase (sin fabricar huellas; R73 P2).
HISTORICAL_IDENTITY_KEYS = (
    "model", "resolved", "thinking", "effort", "max_tokens",
    "structured", "mode",
)

# Solo estos admiten None en el lado nuevo (= aún no observado tras decide).
DYNAMIC_OBSERVED_KEYS = frozenset({
    "system_prompt_sha256", "resolved", "perm_sha256",
})


def recorded_and_ledger(docs):
    """Suma de costes vigentes + máximo de cost_ledger entre docs de fase."""
    recorded, ledger = 0.0, 0.0
    for d in docs:
        recorded += sum(r.get("cost") or 0
                        for r in (d.get("cases") or {}).values())
        prev = (d.get("meta") or {}).get("cost_ledger")
        if isinstance(prev, (int, float)) and not isinstance(prev, bool):
            ledger = max(ledger, prev)
    return recorded, ledger


def prior_cost(docs):
    recorded, ledger = recorded_and_ledger(docs)
    return max(recorded, ledger)


def load_phase_docs(store_mod, run):
    """Docs de todas las fases persistidas de un run."""
    return [store_mod.load(run, ph) or {} for ph in store_mod.runs_in(run)]


def blocking_case_cost_stop(docs):
    """Primera parada ``case_cost`` no enmendada en cualquier fase del run.

    Bloquea reanudación global: no basta con cambiar ``--phases``.
    """
    for d in docs:
        stop = (d.get("meta") or {}).get("cost_stop")
        if not isinstance(stop, dict):
            continue
        if stop.get("reason") == "case_cost" and not stop.get("amended"):
            return dict(stop)
    return None


def apply_case_cost(meta, *, case_cost, case_id, phase, session_cost,
                    prior, max_case_cost, max_cost):
    """Actualiza meta de guarda/ledger y devuelve `stop` o None.

    `case_cost` puede ser None (desconocido: no dispara ni suma — el
    llamador no debe haberlo sumado a session_cost). Tras `decide`, un
    caso puede sobrepasar el tope acumulado; eso se registra y para.
    """
    stop = None
    if isinstance(case_cost, (int, float)) and not isinstance(case_cost, bool):
        if max_case_cost is not None and case_cost > max_case_cost:
            stop = {"reason": "case_cost", "phase": phase, "case": case_id,
                    "cost": case_cost, "cap": max_case_cost}
        if (stop is None and max_cost is not None
                and prior + session_cost >= max_cost):
            stop = {"reason": "accumulated_cost", "phase": phase,
                    "case": case_id, "accumulated": prior + session_cost,
                    "cap": max_cost}
    if max_case_cost is not None or max_cost is not None:
        meta["cost_guard"] = {"max_case_cost": max_case_cost,
                              "max_cost": max_cost}
    if max_cost is not None:
        meta["cost_ledger"] = prior + session_cost
    return stop


def stop_before_requests(meta, *, phase, prior, session_cost, max_cost,
                         docs=None):
    """Parada antes de abrir peticiones.

    1) Si hay ``case_cost`` no enmendada en **cualquier** fase del run → bloqueo.
    2) Si el acumulado durable ``>= max_cost`` → presupuesto agotado.
    """
    if docs is not None:
        blocked = blocking_case_cost_stop(docs)
        if blocked is not None:
            stop = {**blocked, "phase": phase, "before_requests": True,
                    "blocked_by": "case_cost_stop",
                    "origin_phase": blocked.get("phase")}
            meta["cost_stop"] = _stamp(stop)
            if max_cost is not None:
                meta["cost_ledger"] = prior + session_cost
            return stop
    if max_cost is not None and prior + session_cost >= max_cost:
        stop = {"reason": "accumulated_cost", "phase": phase,
                "accumulated": prior + session_cost, "cap": max_cost,
                "before_requests": True}
        meta["cost_ledger"] = prior + session_cost
        meta["cost_stop"] = _stamp(stop)
        return stop
    return None


# Alias histórico usado por cascade/alert T24
stop_before_phase = stop_before_requests


def mark_stop(meta, stop):
    meta["cost_stop"] = _stamp(stop)


def _stamp(stop):
    return {
        **stop, "when": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "progreso conservado; repetir el comando no elude "
                "el presupuesto — ampliarlo o enmendar case_cost exige "
                "aprobación explícita (--amend-case-cost-stop)"}


def amend_case_cost_stops(docs_by_phase, store_mod, run):
    """Marca ``amended=True`` en cada cost_stop case_cost sin borrar evidencia.

    Devuelve el número de fases enmendadas.
    """
    n = 0
    for ph in store_mod.runs_in(run):
        doc = store_mod.load(run, ph)
        if not doc:
            continue
        stop = (doc.get("meta") or {}).get("cost_stop")
        if isinstance(stop, dict) and stop.get("reason") == "case_cost" \
                and not stop.get("amended"):
            stop = dict(stop)
            stop["amended"] = True
            stop["amended_when"] = dt.datetime.now().isoformat(
                timespec="seconds")
            doc["meta"]["cost_stop"] = stop
            store_mod.save(run, ph, doc)
            n += 1
    return n


def canonical_config(meta, keys=CONFIG_FINGERPRINT_KEYS):
    """Configuración efectiva canónica: todas las claves, ausente → None."""
    meta = meta or {}
    return {k: meta.get(k) for k in keys}


def config_sha256(meta, keys=CONFIG_FINGERPRINT_KEYS):
    """Huella durable de la configuración canónica (JSON estable)."""
    cfg = canonical_config(meta, keys=keys)
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def config_mismatches(prev_meta, current_meta, keys=CONFIG_FINGERPRINT_KEYS,
                      dynamic_keys=DYNAMIC_OBSERVED_KEYS):
    """Diferencias de configuración canónica (R72 P1-1).

    Campos estáticos: ``None``/ausente es valor comparable (medium→None
    rechaza). Lista blanca dinámica: solo el lado *nuevo* puede ser None
    («desconocido aún» tras decide); si ambos son conocidos y difieren,
    también rechaza (R71 P2-1 conservado para hashes post-decide).
    Solo se exige que la clave existiera en el meta previo (runs antiguos).
    """
    out = []
    prev = prev_meta or {}
    cur = current_meta or {}
    dyn = frozenset(dynamic_keys)
    for k in keys:
        if k not in prev:
            continue
        pv, cv = prev[k], cur.get(k)
        if k in dyn and cv is None:
            continue
        if pv != cv:
            out.append((k, pv, cv))
    return out


def run_config_mismatches(store_mod, run, current_meta,
                          keys=CONFIG_FINGERPRINT_KEYS,
                          dynamic_keys=DYNAMIC_OBSERVED_KEYS):
    """Compara current_meta contra TODAS las fases persistidas del run.

    Devuelve (phase, mismatches) de la primera discrepancia, o (None, []).
    Incluye fases no seleccionadas en la invocación actual (R69 F2).
    También rechaza si los ``config_sha256`` por caso del run no son únicos.
    """
    for ph in store_mod.runs_in(run):
        doc = store_mod.load(run, ph)
        if not doc:
            continue
        mm = config_mismatches(doc.get("meta"), current_meta, keys=keys,
                               dynamic_keys=dynamic_keys)
        if mm:
            return ph, mm
    bad_ph, shas = cases_config_sha_conflict(store_mod, run)
    if bad_ph is not None:
        return bad_ph, [("config_sha256", shas[0], shas[1])]
    return None, []


def cases_config_sha_conflict(store_mod, run):
    """Si hay ≥2 huellas distintas entre casos, (fase, [sha_a, sha_b])."""
    seen = None
    for ph in store_mod.runs_in(run):
        doc = store_mod.load(run, ph)
        if not doc:
            continue
        for rec in (doc.get("cases") or {}).values():
            if not isinstance(rec, dict):
                continue
            sha = rec.get("config_sha256")
            if sha is None:
                continue
            if seen is None:
                seen = sha
            elif sha != seen:
                return ph, [seen, sha]
    return None, []


def run_config_provenance(docs, version_key="resolved"):
    """Única ``config_sha256`` + versión entre todos los registros de ``docs``.

    Devuelve ``(ok, detail)``. Falta de huella en cualquier caso presente,
    huellas distintas o versiones distintas → ``ok=False`` (R72 P1-2).
    """
    shas, versions = set(), set()
    missing_sha = 0
    n_cases = 0
    for d in docs:
        meta = d.get("meta") or {}
        ver = meta.get(version_key)
        if ver is not None:
            versions.add(ver)
        for rec in (d.get("cases") or {}).values():
            if not isinstance(rec, dict):
                continue
            n_cases += 1
            sha = rec.get("config_sha256")
            if sha is None:
                missing_sha += 1
            else:
                shas.add(sha)
            # versión por caso si el meta de fase no la trajo
            cv = rec.get("resolved") or rec.get("reviewer_version")
            if cv is not None:
                versions.add(cv)
    detail = {
        "kind": "huella por registro",
        "n_cases": n_cases,
        "missing_config_sha256": missing_sha,
        "config_sha256s": sorted(shas),
        "versions": sorted(versions, key=str),
    }
    # huella única en todos los registros + a lo sumo una versión;
    # sin versión observada aún (runs de prueba mínimos) basta la huella
    ok = (n_cases > 0 and missing_sha == 0 and len(shas) == 1
          and len(versions) <= 1)
    detail["config_sha256"] = next(iter(shas)) if len(shas) == 1 else None
    detail["version"] = next(iter(versions)) if len(versions) == 1 else None
    return ok, detail


def _freeze_meta_val(v):
    """Valor comparable de meta (bool/num/str/None)."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    return str(v)


def historical_phase_provenance(phase_docs, keys=HISTORICAL_IDENTITY_KEYS):
    """Procedencia histórica por meta de fase (R73 P2).

    No fabrica ``config_sha256``. Claves estables: los valores *conocidos*
    (no None) deben coincidir entre fases. ``questions_hash`` se registra
    por fase (varía legítimamente; no se exige un único hash global).
    Exige al menos un identificador estable conocido (p. ej. ``model``).
    """
    known = {k: set() for k in keys}
    qh_by_phase = {}
    n_phases = 0
    for item in phase_docs:
        if isinstance(item, tuple) and len(item) == 2:
            ph, d = item
        else:
            ph, d = None, item
        meta = (d or {}).get("meta") or {}
        n_phases += 1
        for k in keys:
            v = meta.get(k)
            if v is not None:
                known[k].add(_freeze_meta_val(v))
        if ph is not None:
            qh_by_phase[ph] = meta.get("questions_hash")
    conflicts = {k: sorted(vs, key=str) for k, vs in known.items()
                 if len(vs) > 1}
    identity = {k: (next(iter(vs)) if len(vs) == 1 else None)
                for k, vs in known.items()}
    has_id = any(identity[k] is not None for k in keys)
    ok = n_phases > 0 and has_id and not conflicts
    detail = {
        "kind": "procedencia histórica (meta de fase)",
        "n_phases": n_phases,
        "identity": identity,
        "conflicts": conflicts,
        "questions_hash_by_phase": qh_by_phase,
        "config_sha256": None,
        "version": identity.get("resolved"),
    }
    return ok, detail


def run_provenance(phase_docs, version_key="resolved", *,
                   allow_historical=False):
    """Puerta de procedencia: huella por registro, o histórica si se admite.

    ``phase_docs``: docs o pares ``(phase, doc)``. Si hay huellas en todos
    los casos → camino «huella por registro». Si faltan todas y
    ``allow_historical`` → «procedencia histórica (meta de fase)».
    Huellas parciales → fallo (nunca se inventa huella retrospectiva).
    """
    docs = []
    for item in phase_docs:
        if isinstance(item, tuple) and len(item) == 2:
            docs.append(item[1])
        else:
            docs.append(item)
    n_cases = missing = 0
    for d in docs:
        for rec in ((d or {}).get("cases") or {}).values():
            if not isinstance(rec, dict):
                continue
            n_cases += 1
            if rec.get("config_sha256") is None:
                missing += 1
    if n_cases == 0:
        return False, {"kind": None, "n_cases": 0,
                       "missing_config_sha256": 0}
    if missing == 0:
        return run_config_provenance(docs, version_key=version_key)
    if missing == n_cases and allow_historical:
        return historical_phase_provenance(phase_docs)
    # parcial o histórico no admitido
    ok, detail = run_config_provenance(docs, version_key=version_key)
    detail["historical_allowed"] = bool(allow_historical)
    return False, detail


def historical_identities_match(prov_a, prov_b):
    """Misma identidad histórica estable + questions_hash por fase común."""
    if not prov_a or not prov_b:
        return False
    id_a = prov_a.get("identity") or {}
    id_b = prov_b.get("identity") or {}
    keys = set(id_a) | set(id_b)
    for k in keys:
        va, vb = id_a.get(k), id_b.get(k)
        if va is not None and vb is not None and va != vb:
            return False
    qh_a = prov_a.get("questions_hash_by_phase") or {}
    qh_b = prov_b.get("questions_hash_by_phase") or {}
    for ph in set(qh_a) & set(qh_b):
        if qh_a[ph] != qh_b[ph]:
            return False
    # al menos un campo estable conocido en ambos
    shared = [k for k in keys
              if id_a.get(k) is not None and id_b.get(k) is not None]
    return bool(shared)


def stamp_case_config(rec, meta, keys=CONFIG_FINGERPRINT_KEYS):
    """Anota ``config_sha256`` canónica en el registro del caso."""
    rec["config_sha256"] = config_sha256(meta, keys=keys)
    return rec


def acquisition_registry(meta):
    """Registro de adquisición por bloque (reanudación vs único retry)."""
    reg = meta.get("acquisition")
    if not isinstance(reg, dict):
        reg = {"retry_errors_passes": 0, "retried_cases": []}
        meta["acquisition"] = reg
    reg.setdefault("retried_cases", [])
    return reg


def mark_retry_attempt(meta, phase, case_id):
    """Registra ANTES del intento que este caso consume su único retry."""
    reg = acquisition_registry(meta)
    reg["retry_pass_started"] = True
    key = f"{phase}/{case_id}"
    if key not in reg["retried_cases"]:
        reg["retried_cases"] = list(reg["retried_cases"]) + [key]
    return key


def case_already_retried(meta, phase, case_id):
    reg = acquisition_registry(meta)
    return f"{phase}/{case_id}" in (reg.get("retried_cases") or [])


def remaining_budget(*, ceiling, spent, margin_reserved, unknown_spent=0.0):
    """Cupo restante del encargo antes de un bloque (R69 F6 / R70-1).

    La cota desconocida se descuenta **además** del margen aún reservado:
    ``cupo = ceiling − spent − unknown − max(0, reserve − unknown)``
    (= ``ceiling − spent − max(reserve, unknown)``). Más desconocido nunca
    aumenta el cupo; no se registra la estimación como gasto medido.
    """
    unk = float(unknown_spent or 0)
    reserve = float(margin_reserved)
    margin_left = max(0.0, reserve - unk)
    cupo = float(ceiling) - float(spent) - unk - margin_left
    return cupo, margin_left


def frozen_resolved_from_docs(docs, key="reviewer_resolved"):
    """Única versión congelada del run a partir de todas las fases (R70-4).

    Devuelve la versión común, o None si ninguna fase la tiene.
    Si hay contradicción entre fases, lanza ``ValueError`` con el detalle.
    """
    frozen = None
    origin = None
    for i, d in enumerate(docs):
        v = (d.get("meta") or {}).get(key)
        if v is None:
            continue
        if frozen is None:
            frozen, origin = v, i
        elif v != frozen:
            raise ValueError(
                f"versiones contradictorias en el run: {frozen!r} "
                f"(doc[{origin}]) vs {v!r} (doc[{i}])")
    return frozen
