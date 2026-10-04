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
            shift %= len(items)
            q["criteria"] = dict(items[shift:] + items[:shift])
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
