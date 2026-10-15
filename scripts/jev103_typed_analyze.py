#!/usr/bin/env python3
"""JEV-103, enmienda E1: jev82 analyze / jev81 repeat sobre runs cuyo adaptador no guarda
`type` en las respuestas (nimble, tev1). Los analizadores se ejecutan sin cambios; solo se
envuelve store.load para añadir el `type` de cada pregunta según jevbench/battery.py.
Uso: python3 scripts/jev103_typed_analyze.py d1|r2 <base>
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import store  # noqa: E402
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

if __name__ == "__main__":
    mode, base = sys.argv[1], sys.argv[2]
    if mode == "d1":
        from jevbench import jev82
        jev82.main(["analyze", base, f"{base}_d1"])
    else:
        from jevbench import jev81
        jev81.main(["repeat", base, f"{base}_r2"])
