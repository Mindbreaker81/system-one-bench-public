"""JEV-65: ablación controlada del prompt y sesgo de posición (seguimiento de
JEV-63; pre-registro en docs/plan_ablacion_prompt_llm.md y en la issue).

  python3 -m jevbench.diag65 nvfp4 --section A --opt base_url=http://127.0.0.1:18000/v1 \
      --opt model=qwen3.8-27b-sglang --opt 'extra_body={"temperature":0,...}'

Secciones (matriz fijada):
  A  probabilities, struct: 5 variantes × 12 casos JEV-63 × 3 reps
  B  discrete, struct: v1/v2 × 12 casos × 3 reps
  C  discrete, struct, rot1: v1/v2 × 6 casos × 3 reps (rota una posición las
     claves de las preguntas choice, en prompt y esquema a la vez)

Run por celda × rep: `diag_qwen38_jev65_<bloque>_<variante>_<mode>_<route>[_rot1]_r<rep>`
con un fichero por fase, mismo formato que jevbench.run más `raw` por caso.
Reanudable: los casos ya respondidos se saltan y los casos con error se
conservan (`--retry-errors` los repite). Si el diag o la configuración
efectiva guardada (modelo, endpoint, límites, prompt enviado, preguntas)
no coincide con la pedida, la reanudación se rechaza.
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
from .diag63 import DIAG_CASES, SEEDS
from .redact import redact_options
# rotate_choice/rotation_manifest viven en jevbench.rotation desde JEV-67;
# se reexportan aquí para no romper diag65_report ni los tests
from .rotation import rotate_choice, rotation_manifest
from .run import git_rev

# Variantes del pre-registro JEV-65 (slug del run -> prompt= del adaptador llm).
VARIANTS = {
    "v1_typesafe": "typesafe",
    "v2_simple": "simple",
    "v3_sin_antinj": "sin_antinj",
    "v4_simple_antinj": "simple_antinj",
    "v5_antinj_alt": "antinj_alt",
}

# Calendario pre-registrado: controles v1/v2 primero; después el orden de las
# variantes se alterna por rep para no confundir deriva temporal con prompt.
ORDER_A = {
    1: ["v1_typesafe", "v2_simple", "v3_sin_antinj", "v4_simple_antinj", "v5_antinj_alt"],
    2: ["v5_antinj_alt", "v4_simple_antinj", "v1_typesafe", "v3_sin_antinj", "v2_simple"],
    3: ["v3_sin_antinj", "v1_typesafe", "v5_antinj_alt", "v2_simple", "v4_simple_antinj"],
}
ORDER_BC = {
    1: ["v1_typesafe", "v2_simple"],
    2: ["v2_simple", "v1_typesafe"],
    3: ["v1_typesafe", "v2_simple"],
}

# Sección C: control de posición en discrete sobre 6 casos fijados.
ROT_CASES = {
    "triage_es": ["T01_ebus_alergia", "T02_factura_duplicada"],
    "papers32": ["P01", "P02"],
    "adv1": ["A01_keyword_recipe"],
    "adv3": ["C01_downplay_hemoptysis"],
}

SECTIONS = {
    "A": {"mode": "prob", "rot": 0, "cases": DIAG_CASES, "order": ORDER_A},
    "B": {"mode": "disc", "rot": 0, "cases": DIAG_CASES, "order": ORDER_BC},
    "C": {"mode": "disc", "rot": 1, "cases": ROT_CASES, "order": ORDER_BC},
}

MODE = {"prob": "probabilities", "disc": "discrete"}
ROUTE = {"struct": "true", "nostruct": "false"}

CASES_SHA256 = {k: hashlib.sha256(
    json.dumps(v, sort_keys=True).encode()).hexdigest()[:12]
    for k, v in (("diag", DIAG_CASES), ("rot", ROT_CASES))}


def _case_list(phase, ids):
    """Cases of `phase` restricted to the fixed ids, in the manifest's order."""
    _, cases = load_phase(phase)
    by_id = {c.id: c for c in cases}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"{phase}: ids del manifiesto ausentes en battery.py: {missing}")
    return [by_id[i] for i in ids]


# Campos del meta del adaptador que definen la configuración efectiva de una
# celda: modelo y endpoint, modo, ruta estructurada, límites, muestreo y
# plantilla de prompt. Si alguno difiere al reanudar, la configuración pedida
# no es la del run guardado: se rechaza la mezcla. El sha del system prompt no
# va aquí — los prompts "simple" incrustan las preguntas de la fase y cambian
# por fase; se compara el esperado calculado para la fase concreta.
CONFIG_KEYS = ("provider", "model", "resolved", "base_url", "mode", "structured",
               "normalize", "retries_malformed", "timeout", "case_timeout",
               "min_interval", "max_tokens", "reasoning_effort", "prompt",
               "prompt_template_sha256", "extra_body", "usd_per_mtok",
               "inject_schema_in_prompt", "rotate_choice")

# Solo se rellenan tras la primera petición: un None fresco es "aún desconocido",
# no un valor efectivo. En el resto de CONFIG_KEYS, None sí es valor efectivo.
POST_CALL_KEYS = ("resolved",)


def _check_resume(run, phase, doc, diag, cfg, config_keys=CONFIG_KEYS):
    """Refuse to extend a run whose stored config differs from this one.
    Compares the frozen cell fields (diag), the adapter options recorded in
    meta.opts, every effective adapter field in config_keys in both
    directions, the phase's questions_hash and — when it can be reproduced
    without a request — the sha of the system prompt for this phase. A
    stored value that the new config no longer produces also aborts."""
    old = (doc.get("meta") or {}).get("diag") or {}
    for key, val in diag.items():
        if key in old and old[key] != val:
            raise SystemExit(
                f"{run} {phase}: diag incompatible al reanudar "
                f"({key}: guardado {old[key]!r} != pedido {val!r}); "
                "usa un run nuevo en vez de mezclar configuraciones")
    for key in old:
        if key not in diag:
            raise SystemExit(
                f"{run} {phase}: diag incompatible al reanudar "
                f"(el guardado tiene {key}={old[key]!r} y la config pedida no); "
                "usa un run nuevo en vez de mezclar configuraciones")
    # la comparación estricta solo aplica cuando hay respuestas guardadas:
    # sin casos no hay configuración efectiva previa que proteger
    if not doc.get("cases"):
        return
    meta = doc.get("meta") or {}
    diffs = []
    if "opts" in meta and meta["opts"] != cfg["opts"]:
        diffs.append(("opts", meta["opts"], cfg["opts"]))
    for key in config_keys:
        new = cfg["meta"].get(key)
        if new is None and key in POST_CALL_KEYS:
            continue
        if key in meta and meta.get(key) != new:
            diffs.append((key, meta.get(key), new))
        elif key not in meta and new is not None:
            diffs.append((key, "<ausente>", new))
    for key in ("questions_hash", "system_prompt_sha256"):
        new = (cfg.get("expected") or {}).get(key)
        if new is None:
            continue  # no reproducible sin petición (familia typesafe + nostruct)
        if meta.get(key) is not None and meta.get(key) != new:
            diffs.append((key, meta.get(key), new))
        elif meta.get(key) is None:
            diffs.append((key, "<ausente>", new))
    if diffs:
        det = "; ".join(f"{k}: guardado {a!r} != pedido {b!r}" for k, a, b in diffs)
        raise SystemExit(
            f"{run} {phase}: configuración incompatible al reanudar ({det}); "
            "usa un run nuevo en vez de mezclar configuraciones")


def _merge_meta(doc_meta, fields):
    """Update doc meta with fresh adapter fields without erasing confirmed
    values: fields that only exist after a successful call (resolved, prompt
    shas) keep the stored value while the fresh one is still None."""
    for key, val in fields.items():
        if val is not None or key not in doc_meta:
            doc_meta[key] = val


def _meta_with_expected(meta, exp_sha):
    """meta() with the prompt sha pinned to the one computed for this phase.
    The adapter's own value is authoritative after a successful decide in the
    same phase, but between phases it still carries the previous phase's sha —
    or None — so the reproducible expected sha wins whenever it exists."""
    m = dict(meta)
    if exp_sha is not None:
        m["system_prompt_sha256"] = exp_sha
        if m.get("prompt") != "typesafe":
            m["prompt_sha256"] = exp_sha
    return m


def _run_cell(name, section, variant, rep, opts, limit=None, retry_errors=False):
    """One variant x one repetition = one diag run directory."""
    mode, rot, cases_spec = section["mode"], section["rot"], section["cases"]
    run = (f"diag_qwen38_jev65_{name}_{variant}_{mode}_"
           f"{opts['route_slug']}{'_rot1' if rot else ''}_r{rep}")
    cell_opts = dict(opts)
    cell_opts.pop("route_slug")
    cell_opts["mode"] = MODE[mode]
    cell_opts["prompt"] = VARIANTS[variant]
    cell_opts["capture_raw"] = "true"
    eb = json.loads(cell_opts.get("extra_body") or "{}")
    if rep in SEEDS:
        eb["seed"] = SEEDS[rep]
    if eb:
        cell_opts["extra_body"] = json.dumps(eb)
    model = adapters.get("llm")(**cell_opts)
    print(f"[{run}] {model.meta()}", flush=True)
    done_cases = 0
    for phase, ids in cases_spec.items():
        qs, _ = load_phase(phase)
        if rot:
            qs = rotate_choice(qs, shift=rot)
        targets = _case_list(phase, ids)
        doc = store.load(run, phase) or {"meta": {}, "cases": {}}
        diag = {"issue": "JEV-65", "block": name, "variant": variant,
                "mode": MODE[mode], "route": opts["route_slug"], "rot": rot,
                "rep": rep, "seed": SEEDS.get(rep), "cases": ids,
                "cases_sha256": CASES_SHA256["rot" if rot else "diag"]}
        if rot:
            diag["rotation"] = rotation_manifest(qs)
        exp_sha = model.expected_system_prompt_sha256(qs)
        cfg = {"opts": redact_options(cell_opts), "meta": model.meta(),
               "expected": {"questions_hash": questions_hash(qs),
                            "system_prompt_sha256": exp_sha}}
        _check_resume(run, phase, doc, diag, cfg)
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
    ap.add_argument("--section", required=True, choices=sorted(SECTIONS),
                    help="A: probabilities 5 variantes; B: discrete v1/v2; "
                         "C: discrete rot1 v1/v2 sobre 6 casos")
    ap.add_argument("--route", default="struct", choices=sorted(ROUTE),
                    help="struct (matriz) | nostruct (extensión condicionada)")
    ap.add_argument("--variants", default=None,
                    help="variantes a ejecutar (defecto: el orden fijado del rep)")
    ap.add_argument("--opt", action="append", default=[],
                    help="opcion del adaptador llm k=v (repetible)")
    ap.add_argument("--reps", default="1,2,3", help="repeticiones a ejecutar")
    ap.add_argument("--limit", type=int, help="max casos por fase (smoke)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="repite también los casos guardados con error "
                         "(por defecto se conservan y se avisa)")
    args = ap.parse_args()

    opts = dict(o.split("=", 1) for o in args.opt)
    opts["structured"] = ROUTE[args.route]
    opts["route_slug"] = args.route
    section = SECTIONS[args.section]
    reps = [int(r) for r in args.reps.split(",")]
    total = 0
    for rep in reps:
        order = section["order"].get(rep)
        if order is None:
            raise SystemExit(f"rep {rep}: no hay orden de variantes fijado para esa rep")
        variants = args.variants.split(",") if args.variants else order
        for variant in variants:
            if variant not in VARIANTS:
                raise SystemExit(f"variante {variant!r} desconocida: {sorted(VARIANTS)}")
            if variant not in order:
                print(f"aviso: {variant} fuera del calendario del rep {rep}: {order}",
                      flush=True)
            total += _run_cell(args.name, section, variant, rep, opts,
                               args.limit, args.retry_errors)
    print(f"diag65 done: {total} evaluaciones nuevas", flush=True)


if __name__ == "__main__":
    main()
