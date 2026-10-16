#!/usr/bin/env python3
"""JEV-104, enmienda E1: jev82 analyze sobre jev_v114_typesafe_preview_d1, adquirido con
--max-cost 0.20 en vez de la guarda congelada de jev82 (0.05). El analizador se ejecuta sin
cambios; solo se envuelve store.load para presentar meta.cost_guard = 0.05 en el run d1, y
SOLO tras comprobar que la guarda congelada no habría disparado nunca (coste acumulado del
run < 0.05 y ningún caso > 0.01): la adquisición habría sido idéntica.
Uso: python3 scripts/jev104_d1_analyze.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import store  # noqa: E402

BASE, D1 = "jev_v114_typesafe_preview", "jev_v114_typesafe_preview_d1"
ACQ = {"max_case_cost": 0.01, "max_cost": 0.2}
FROZEN = {"max_case_cost": 0.01, "max_cost": 0.05}

_orig = store.load


def check():
    total, worst = 0.0, 0.0
    for ph in store.runs_in(D1):
        doc = _orig(D1, ph)
        if doc["meta"].get("cost_guard") != ACQ:
            raise SystemExit(f"{D1}/{ph}: cost_guard inesperado {doc['meta'].get('cost_guard')}")
        for rec in doc["cases"].values():
            c = rec.get("cost") or 0.0
            total += c
            worst = max(worst, c)
    if total >= FROZEN["max_cost"] or worst > FROZEN["max_case_cost"]:
        raise SystemExit(f"la guarda congelada habría disparado (total {total}, caso máx {worst})")
    print(f"E1: coste acumulado {total:.5f} < {FROZEN['max_cost']} y caso máx {worst:.5f} "
          f"<= {FROZEN['max_case_cost']}: guarda congelada nunca habría disparado")


def _load(run, phase, *a, **kw):
    doc = _orig(run, phase, *a, **kw)
    if doc and run == D1:
        doc = copy.deepcopy(doc)
        doc["meta"]["cost_guard"] = dict(FROZEN)
    return doc


if __name__ == "__main__":
    check()
    store.load = _load
    from jevbench import jev82
    jev82.main(["analyze", BASE, D1])
