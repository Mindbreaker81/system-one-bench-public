#!/usr/bin/env python3
"""JEV-106: `jev81 repeat` añadiendo en memoria el campo `type` (desde battery)
a respuestas que no lo traen (p. ej. el run local `tev1_4b` del 30-sep).

No modifica `results/`, `jevbench/attest.py` ni el validador de contrato de
`jev81`. Solo envuelve `store.load` para la sesión del proceso.

Uso:
  python3 scripts/jev106_repeat_typed.py tev1_4b tev1_4b_or
  python3 scripts/jev106_repeat_typed.py clef_27b clef_27b_or
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import jev81, store  # noqa: E402
from jevbench.battery import load_phase  # noqa: E402

_orig = store.load


def _typed_load(run, phase, *a, **kw):
    doc = _orig(run, phase, *a, **kw)
    if not doc:
        return doc
    try:
        qs, _ = load_phase(phase)
    except Exception:
        return doc
    doc = copy.deepcopy(doc)
    for rec in (doc.get("cases") or {}).values():
        for qid, ans in ((rec or {}).get("answers") or {}).items():
            if isinstance(ans, dict) and "type" not in ans and qid in qs:
                ans["type"] = qs[qid]["type"]
    return doc


store.load = _typed_load
jev81.store.load = _typed_load

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("uso: python3 scripts/jev106_repeat_typed.py <run_a> <run_b>")
    jev81._print_repeat(jev81.repeatability_report(sys.argv[1], sys.argv[2]))
