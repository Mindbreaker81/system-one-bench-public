"""JEV-66: confirmación causal del mecanismo identificado en la revisión externa
(4-oct): con structured=true el adaptador solo envía el system prompt fijo y el
documento — las preguntas van únicamente en el response_format, que SGLang no
inyecta en el prompt — y el modelo local responde a ciegas (vectores nulos).

Predicción pre-registrada (issue JEV-66): la celda `typesafe_struct` con el
esquema además serializado en el system prompt (mismo apéndice que la librería
usa en structured=false; gramática intacta) produce **0 vectores nulos** en los
12 casos JEV-63, mientras el control `typesafe_struct` sin inyección, en la
misma sesión, reproduce los nulos (~9/14 por rep en NVFP4/FP8).

  python3 -m jevbench.diag66 nvfp4 --opt base_url=http://127.0.0.1:18000/v1 \
      --opt model=qwen3.8-27b-sglang --opt 'extra_body={"temperature":0,...}'

Run por celda × rep: `diag_qwen38_jev66_<bloque>_<celda>_r<rep>` con un fichero
por fase, mismo formato que jevbench.run más `raw` por caso. Reanudable con la
misma protección de configuración que diag65: si la configuración efectiva
guardada no coincide con la pedida, la reanudación se rechaza.
"""
import argparse
import datetime as dt
import json
import platform
import sys
import time
import traceback

from . import adapters, store
from .battery import load_phase, questions_hash
from .diag63 import DIAG_CASES, SEEDS
from .diag65 import (CASES_SHA256, POST_CALL_KEYS, _case_list, _check_resume,
                     _merge_meta, _meta_with_expected)
from .diag65 import CONFIG_KEYS as _CONFIG_KEYS_65
from .redact import redact_options
from .run import git_rev

# Celdas del pre-registro JEV-66: celda -> inject_schema_in_prompt del adaptador
# llm. Ambas usan prompt=typesafe, mode=probabilities y structured=true; la
# experimental añade el esquema serializado al system prompt sin tocar la
# gramática. El control reproduce la celda degenerada de JEV-63/65.
CELLS = {
    "typesafe_struct": False,
    "typesafe_struct_schema_in_prompt": True,
}

# Orden alternado por rep (control primero en reps impares) para no confundir
# deriva temporal con la celda.
CELL_ORDER = {
    1: ["typesafe_struct", "typesafe_struct_schema_in_prompt"],
    2: ["typesafe_struct_schema_in_prompt", "typesafe_struct"],
    3: ["typesafe_struct", "typesafe_struct_schema_in_prompt"],
}

# CONFIG_KEYS de diag65 ya incluyen inject_schema_in_prompt y rotate_choice
# (JEV-67); se mantiene el alias por compatibilidad con tests y run scripts.
CONFIG_KEYS = _CONFIG_KEYS_65


def _run_cell(name, cell, rep, opts, limit=None, retry_errors=False,
              prefix="diag_qwen38_jev66"):
    """One cell x one repetition = one diag run directory (6 phase files)."""
    run = f"{prefix}_{name}_{cell}_r{rep}"
    cell_opts = dict(opts)
    cell_opts["structured"] = "true"
    cell_opts["prompt"] = "typesafe"
    cell_opts["mode"] = "probabilities"
    cell_opts["capture_raw"] = "true"
    cell_opts["inject_schema_in_prompt"] = "true" if CELLS[cell] else "false"
    eb = json.loads(cell_opts.get("extra_body") or "{}")
    if rep in SEEDS:
        eb["seed"] = SEEDS[rep]
    if eb:
        cell_opts["extra_body"] = json.dumps(eb)
    model = adapters.get("llm")(**cell_opts)
    print(f"[{run}] {model.meta()}", flush=True)
    done_cases = 0
    for phase, ids in DIAG_CASES.items():
        qs, _ = load_phase(phase)
        targets = _case_list(phase, ids)
        doc = store.load(run, phase) or {"meta": {}, "cases": {}}
        diag = {"issue": "JEV-66", "block": name, "cell": cell,
                "mode": "probabilities", "route": "struct",
                "inject_schema_in_prompt": CELLS[cell],
                "rep": rep, "seed": SEEDS.get(rep), "cases": ids,
                "cases_sha256": CASES_SHA256["diag"]}
        exp_sha = model.expected_system_prompt_sha256(qs)
        cfg = {"opts": redact_options(cell_opts), "meta": model.meta(),
               "expected": {"questions_hash": questions_hash(qs),
                            "system_prompt_sha256": exp_sha}}
        _check_resume(run, phase, doc, diag, cfg, config_keys=CONFIG_KEYS)
        meta_now = _meta_with_expected(model.meta(), exp_sha)
        doc["meta"].update({
            "adapter": "llm", "opts": redact_options(cell_opts),
            "phase": phase, "questions_hash": questions_hash(qs),
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0], "git": git_rev(),
            "diag": diag,
            "updated": dt.datetime.now().isoformat(timespec="seconds")})
        _merge_meta(doc["meta"], meta_now)
        if retry_errors:
            todo = [c for c in targets if c.id not in doc["cases"]
                    or "error" in doc["cases"][c.id]]
        else:
            todo = [c for c in targets if c.id not in doc["cases"]]
            kept = [c.id for c in targets
                    if "error" in (doc["cases"].get(c.id) or {})]
            if kept:
                print(f"{run} {phase}: {len(kept)} casos con error se conservan "
                      f"({', '.join(kept)}); --retry-errors para repetirlos",
                      flush=True)
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
                diag_e = getattr(e, "diag", None)
                if isinstance(diag_e, dict) and diag_e:
                    rec["diag"] = diag_e
                print(f"{run} {phase} {c.id}: ERROR {rec['error'][:120]}", flush=True)
            doc["cases"][c.id] = rec
            _merge_meta(doc["meta"], _meta_with_expected(model.meta(), exp_sha))
            store.save(run, phase, doc)
            done_cases += 1
    return done_cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="slug del bloque (nvfp4, fp8)")
    ap.add_argument("--cells", default=None,
                    help="celdas a ejecutar (defecto: las 2 en el orden del rep)")
    ap.add_argument("--opt", action="append", default=[],
                    help="opcion del adaptador llm k=v (repetible)")
    ap.add_argument("--reps", default="1,2,3", help="repeticiones a ejecutar")
    ap.add_argument("--limit", type=int, help="max casos por fase (smoke)")
    ap.add_argument("--prefix", default="diag_qwen38_jev66",
                    help="prefijo de los directorios de run (JEV-67 usa "
                         "diag_qwen38_jev67 para P+live y las sondas D-*)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="repite también los casos guardados con error "
                         "(por defecto se conservan y se avisa)")
    args = ap.parse_args()

    opts = dict(o.split("=", 1) for o in args.opt)
    reps = [int(r) for r in args.reps.split(",")]
    total = 0
    for rep in reps:
        order = CELL_ORDER.get(rep)
        if order is None:
            raise SystemExit(f"rep {rep}: no hay orden de celdas fijado para esa rep")
        cells = args.cells.split(",") if args.cells else order
        for cell in cells:
            if cell not in CELLS:
                raise SystemExit(f"celda {cell!r} desconocida: {sorted(CELLS)}")
            if cell not in order:
                print(f"aviso: {cell} fuera del calendario del rep {rep}: {order}",
                      flush=True)
            total += _run_cell(args.name, cell, rep, opts, args.limit,
                               args.retry_errors, prefix=args.prefix)
    print(f"diag66 done: {total} evaluaciones nuevas", flush=True)


if __name__ == "__main__":
    main()
