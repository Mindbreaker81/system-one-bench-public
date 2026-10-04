"""JEV-63: matriz reducida prompt x esquema sobre 12 casos fijados (pre-registro:
docs/plan_diagnostico_estabilidad_llm.md). Diagnostico, no benchmark: NO publicar
un ajustado de estas 12 muestras como equivalente al marcador oficial.

  python3 -m jevbench.diag63 nvfp4 --opt base_url=http://127.0.0.1:8000/v1 \
      --opt model=qwen3.8-27b-sglang --opt 'extra_body={"temperature":0,...}'

Cada celda x repeticion produce un run `diag_qwen38_<nombre>_<celda>_r<rep>` con un
fichero por fase (2 casos fijados) en el mismo formato que jevbench.run, mas el
campo `raw` por caso con los intentos del proveedor (payload real y respuesta sin
normalizar). Reanudable: los casos ya respondidos se saltan.
"""
import argparse
import datetime as dt
import hashlib
import json
import platform
import sys
import time
import traceback

from . import adapters, store
from .battery import load_phase, questions_hash
from .redact import redact_options
from .run import git_rev

# Casos fijados en el pre-registro (JEV-63), validados contra battery.py.
DIAG_CASES = {
    "triage_es": ["T01_ebus_alergia", "T02_factura_duplicada"],
    "triage_ext_en": ["T15_neumotorax_espontaneo", "T16_epoc_saturacion"],
    "papers32": ["P01", "P02"],
    "adv1": ["A01_keyword_recipe", "A02_vet_dog"],
    "adv3": ["C01_downplay_hemoptysis", "C02_injected_billing_label"],
    "ood": ["receta", "contrato"],
}

# Orden de las cuatro celdas por repeticion (alternado; el orden de casos dentro
# de cada celda no cambia). cell = "<prompt>_<ruta>".
CELL_ORDER = {
    1: ["typesafe_struct", "simple_struct", "typesafe_nostruct", "simple_nostruct"],
    2: ["simple_struct", "typesafe_struct", "simple_nostruct", "typesafe_nostruct"],
    3: ["typesafe_nostruct", "simple_nostruct", "typesafe_struct", "simple_struct"],
}

SEEDS = {1: 101, 2: 202, 3: 303}

CASES_SHA256 = hashlib.sha256(
    json.dumps(DIAG_CASES, sort_keys=True).encode()).hexdigest()[:12]


def _case_list(phase, ids):
    """Cases of `phase` restricted to the fixed ids, in the manifest's order."""
    _, cases = load_phase(phase)
    by_id = {c.id: c for c in cases}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"{phase}: ids del manifiesto ausentes en battery.py: {missing}")
    return [by_id[i] for i in ids]


def _run_cell(name, cell, rep, opts, limit=None):
    """One cell x one repetition = one diag run directory (6 phase files)."""
    prompt_variant, route = cell.rsplit("_", 1)
    run = f"diag_qwen38_{name}_{cell}_r{rep}"
    cell_opts = dict(opts)
    cell_opts["structured"] = "true" if route == "struct" else "false"
    cell_opts["prompt"] = prompt_variant
    cell_opts["capture_raw"] = "true"
    eb = json.loads(cell_opts.get("extra_body") or "{}")
    if rep in SEEDS:
        eb["seed"] = SEEDS[rep]
    if eb:
        cell_opts["extra_body"] = json.dumps(eb)
    model = adapters.get("llm")(**cell_opts)
    print(f"[{run}] {model.meta()}", flush=True)
    done_cases = 0
    for phase, ids in DIAG_CASES.items():
        qs, cases = load_phase(phase)
        targets = _case_list(phase, ids)
        doc = store.load(run, phase) or {"meta": {}, "cases": {}}
        doc["meta"].update({
            "adapter": "llm", "opts": redact_options(cell_opts), **model.meta(),
            "phase": phase, "questions_hash": questions_hash(qs),
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0], "git": git_rev(),
            "diag": {"issue": "JEV-63", "config": name, "cell": cell, "rep": rep,
                     "seed": SEEDS.get(rep), "cases": ids,
                     "cases_sha256": CASES_SHA256},
            "updated": dt.datetime.now().isoformat(timespec="seconds")})
        todo = [c for c in targets if c.id not in doc["cases"]
                or "error" in doc["cases"][c.id]]
        if limit:
            todo = todo[:limit]
        for c in todo:
            t1 = time.time()
            try:
                out = model.decide(c.state, qs)
                rec = {"answers": out["answers"], "ms": round((time.time() - t1) * 1000),
                       "cost": out.get("cost"), "model": out.get("model")}
                if "usage" in out:
                    rec["usage"] = {k: v for k, v in out["usage"].items()
                                    if isinstance(v, (int, float, str, bool, type(None)))}
                if "raw" in out:
                    rec["raw"] = out["raw"]
                print(f"{run} {phase} {c.id}: {rec['ms']}ms", flush=True)
            except Exception as e:
                traceback.print_exc()
                rec = {"error": f"{type(e).__name__}: {e}"[:300],
                       "ms": round((time.time() - t1) * 1000)}
                diag = getattr(e, "diag", None)
                if isinstance(diag, dict) and diag:
                    rec["diag"] = diag
                print(f"{run} {phase} {c.id}: ERROR {rec['error'][:120]}", flush=True)
            doc["cases"][c.id] = rec
            doc["meta"].update(model.meta())
            store.save(run, phase, doc)
            done_cases += 1
    return done_cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="slug del bloque (nvfp4, fp8, cerebras, arcgguf)")
    ap.add_argument("--opt", action="append", default=[],
                    help="opcion del adaptador llm k=v (repetible)")
    ap.add_argument("--reps", default="1,2,3", help="repeticiones a ejecutar")
    ap.add_argument("--cells", default=None,
                    help="celdas a ejecutar (defecto: las 4 en el orden del rep)")
    ap.add_argument("--limit", type=int, help="max casos por fase (smoke)")
    args = ap.parse_args()

    opts = dict(o.split("=", 1) for o in args.opt)
    reps = [int(r) for r in args.reps.split(",")]
    total = 0
    for rep in reps:
        order = CELL_ORDER.get(rep)
        if order is None:
            raise SystemExit(f"rep {rep}: no hay orden de celdas fijado para esa repeticion")
        cells = args.cells.split(",") if args.cells else order
        for cell in cells:
            if cell not in order:
                raise SystemExit(f"celda {cell!r} no es una de las cuatro fijadas: {order}")
            total += _run_cell(args.name, cell, rep, opts, args.limit)
    print(f"diag63 done: {total} evaluaciones nuevas", flush=True)


if __name__ == "__main__":
    main()
