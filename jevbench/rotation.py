"""Choice-key rotation helpers shared by the diagnostics and the `llm`
adapter's `rotate_choice` option (JEV-65 introduced them; JEV-67 moved them
here so the adapter can rotate prompt and schema identically)."""
import hashlib
import json


def rotate_choice(questions, shift=1):
    """Return a copy of `questions` with every choice question's criteria keys
    rotated `shift` positions. Score levels and noul are untouched: rotating
    keys changes the label order in prompt AND schema while keeping labels,
    criteria texts and GT identical."""
    out = {}
    for qid, q in questions.items():
        q = dict(q)
        if q.get("type") == "choice":
            items = list(q["criteria"].items())
            offset = shift % len(items)
            q["criteria"] = dict(items[offset:] + items[:offset])
        out[qid] = q
    return out


def rotation_manifest(questions):
    """Explicit permutation record for rot runs: ordered labels per choice
    question plus its hash."""
    order = {qid: list(q["criteria"]) for qid, q in questions.items()
             if q.get("type") == "choice"}
    return {"shift": 1, "order": order,
            "perm_sha256": hashlib.sha256(
                json.dumps(order, sort_keys=True).encode()).hexdigest()[:12]}


# ---------------------------------------------------------------------------
# Órdenes explícitos por pregunta (JEV-68/72 §2 de R13): a diferencia de
# rotate_choice —que rota TODAS las choice— aquí solo se reordenan las
# preguntas nombradas, en prompt y esquema a la vez. Las etiquetas, los
# criterios y el GT no cambian: el literal del modelo sigue mapeando a la
# etiqueta original.

# Órdenes con nombre congelados por protocolo. d0 es el orden canónico de la
# batería (el de battery.py); d1–d3 son sus rotaciones cíclicas. Nombres
# nuevos se añaden aquí, nunca inline en las celdas.
NAMED_ORDERS = {
    "department": {
        "d0": ["bronchoscopia", "consulta_externa", "urgencias", "admin"],
        "d1": ["consulta_externa", "urgencias", "admin", "bronchoscopia"],
        "d2": ["urgencias", "admin", "bronchoscopia", "consulta_externa"],
        "d3": ["admin", "bronchoscopia", "consulta_externa", "urgencias"],
    }
}


def resolve_choice_order(spec):
    """Parse a 'qid:order' spec where order is a NAMED_ORDERS name (d0..d3)
    or an explicit comma-separated label list. Returns {qid: [labels]}."""
    qid, sep, tail = str(spec or "").partition(":")
    if not sep or not qid or not tail:
        raise ValueError(
            f"choice_order debe tener la forma <qid>:<orden> (p. ej. "
            f"department:d1 o department:a,b,c), no {spec!r}")
    order = NAMED_ORDERS.get(qid, {}).get(tail)
    if order is None:
        order = [x for x in tail.split(",") if x]
        if len(order) < 2:
            raise ValueError(
                f"choice_order: {tail!r} no es un orden con nombre de {qid} "
                f"({sorted(NAMED_ORDERS.get(qid, {}))}) ni una lista de "
                "etiquetas separadas por comas")
    return {qid: list(order)}


def reorder_choice(questions, orders):
    """Return a copy of `questions` where each question named in `orders`
    (a {qid: [labels]} map) gets its criteria keys reordered to exactly that
    label list. The order must be a permutation of the original keys;
    everything else — labels, criteria texts, the other questions — is left
    untouched. Questions named in `orders` but absent from this set are a
    no-op: the same spec applies to every battery phase and not all of them
    share question sets (e.g. department no existe en papers32 ni ood); the
    caller verifies the order where the question does exist."""
    out = {}
    for qid, q in questions.items():
        if qid not in orders:
            out[qid] = q
            continue
        q = dict(q)
        if q.get("type") != "choice":
            raise ValueError(f"{qid}: choice_order solo aplica a preguntas choice")
        want = list(orders[qid])
        if sorted(want) != sorted(q["criteria"]):
            raise ValueError(
                f"{qid}: {want} no es una permutación de {sorted(q['criteria'])}")
        q["criteria"] = {k: q["criteria"][k] for k in want}
        out[qid] = q
    return out


def order_manifest(questions, orders=None):
    """Permutation record for explicit-order runs: the requested orders and
    the resulting criteria order of EVERY choice question (the real order
    sent), plus the hash of that applied order. `shift` no aplica aquí: el
    orden se declara completo, no como desplazamiento."""
    order = {qid: list(q["criteria"]) for qid, q in questions.items()
             if q.get("type") == "choice"}
    return {"orders": {qid: list(o) for qid, o in (orders or {}).items()},
            "order": order,
            "perm_sha256": hashlib.sha256(
                json.dumps(order, sort_keys=True).encode()).hexdigest()[:12]}
