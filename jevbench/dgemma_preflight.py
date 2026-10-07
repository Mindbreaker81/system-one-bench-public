"""JEV-70 §6.2–6.3: preflight offline del interposer de DiffusionGemma.

Importa el `structured_server.py` congelado (mismo commit que el motor) y, con el
tokenizer fijado y sin GPU ni red:

- por familia de esquema de la batería (fases agrupadas por `questions_hash`, en orden
  base y, con --rotate N, rotadas como en `systemone_http rotate_choice=N`): mapeo
  original → etiqueta → token id, posición de cada hueco, tamaño de la plantilla, ancho
  efectivo, nº de etapas y de grupos para cada canvas candidato, y sha256 del texto de
  sistema y del mapeo de etiquetas;
- regla pre-registrada: CANVAS = el menor de {64, 128} con el que todas las familias
  caben en una etapa y un grupo;
- ventana: prompt de chat completo (plantilla del tokenizer) + CANVAS para los 194
  estados; máximo, 5 mayores y MAXLEN = máximo + 1024 redondeado al múltiplo de 1024
  superior, mínimo 16384.

  python -m jevbench.dgemma_preflight --server ~/dgemma/vllm/examples/features/\
structured_diffusion/structured_server.py --tokenizer ~/modelos/diffusiongemma-26B-A4B-it-NVFP4 \
      [--rotate 1] [--out preflight.json]

Solo usa el intérprete del venv del motor (transformers, pybase64)."""
import argparse
import hashlib
import importlib.util
import json
import math
import sys

from .battery import EXTRA_PHASES, PHASES, load_phase, questions_hash
from .rotation import rotate_choice

ALL_PHASES = PHASES + EXTRA_PHASES + ["adv4", "adv5"]
CANDIDATES = (64, 128)
# extensiones que P envía y que el servidor consume (format no es extensión: lo
# deriva el servidor, "lines" con ≤ 10 preguntas)
P_EXTRA = {"samples": "auto", "auto_threshold": 0.1, "auto_max": 4, "steps": 1, "think": 0}


def sha(obj):
    data = obj if isinstance(obj, (bytes, str)) else json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def load_server(path):
    spec = importlib.util.spec_from_file_location("structured_server", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def maxlen_rule(longest):
    return max(16384, math.ceil((longest + 1024) / 1024) * 1024)


def families(rotate=0):
    """Fases agrupadas por esquema (questions_hash del orden base)."""
    fams = {}
    for ph in ALL_PHASES:
        qs, cases = load_phase(ph)
        h = questions_hash(qs)
        f = fams.setdefault(h, {"questions": rotate_choice(qs, rotate) if rotate else qs,
                                "phases": [], "cases": []})
        f["phases"].append(ph)
        f["cases"] += [(ph, c.id, c.state) for c in cases]
    return fams


def analyse_family(ss, qs, canvas):
    ss.CANVAS_LEN = canvas
    ss._template_cache.clear()
    schema = ss.jev_schema({"questions": qs, **P_EXTRA})
    stages = ss.schedule(schema["questions"])
    groups = ss.chunk_groups(schema, schema["questions"])
    out = {"canvas": canvas, "stages": len(stages), "groups": len(groups)}
    if len(stages) != 1 or len(groups) != 1:
        out["fits"] = False
        return out, schema
    try:
        template, slots = ss.template_for(schema, ss.SCAFFOLD, "")
    except ss.SchemaError as e:
        out.update(fits=False, error=str(e))
        return out, schema
    labels = {}
    for q, s in zip(schema["questions"], slots):
        labels[q["id"]] = {"pos": s["pos"], "map": [
            {"original": name, "label": lab, "token_id": tid}
            for (name, _), lab, tid in zip(q["choices"], q["labels"], s["label_ids"])]}
    sys_text = ss.system_text(schema)
    out.update(fits=True, template_tokens=len(template), width=ss.canvas_width(template),
               labels=labels, labels_sha256=sha(labels), system_text=sys_text,
               system_sha256=sha(sys_text))
    return out, schema


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="structured_server.py congelado")
    ap.add_argument("--tokenizer", required=True, help="carpeta local del checkpoint")
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--out")
    args = ap.parse_args()

    from transformers import AutoTokenizer
    ss = load_server(args.server)
    ss.init_tokenizer(AutoTokenizer.from_pretrained(args.tokenizer))
    server_sha = hashlib.sha256(open(args.server, "rb").read()).hexdigest()

    fams = families(args.rotate)
    report = {"server_sha256": server_sha, "rotate": args.rotate, "p_extra": P_EXTRA,
              "families": {}, "canvas": None}
    for canvas in CANDIDATES:
        ok = True
        for h, f in fams.items():
            res, _ = analyse_family(ss, f["questions"], canvas)
            report["families"].setdefault(h, {"phases": f["phases"], "by_canvas": {}})
            report["families"][h]["by_canvas"][str(canvas)] = res
            ok &= res["fits"]
        if ok:
            report["canvas"] = canvas
            break
    if report["canvas"] is None:
        report["verdict"] = "no ejecutable sin fragmentar"
    else:
        canvas = report["canvas"]
        sizes = []
        for h, f in fams.items():
            sys_text = report["families"][h]["by_canvas"][str(canvas)]["system_text"]
            for ph, cid, state in f["cases"]:
                n = len(ss.chat_prompt_ids(sys_text, state))
                sizes.append({"phase": ph, "id": cid, "prompt_tokens": n, "total": n + canvas})
        sizes.sort(key=lambda r: -r["total"])
        report.update(cases=len(sizes), longest=sizes[:5], maxlen=maxlen_rule(sizes[0]["total"]),
                      prompt_tokens={f"{r['phase']}:{r['id']}": r["prompt_tokens"] for r in sizes},
                      verdict="ok")
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.out:
        open(args.out, "w").write(text)
    summary = {k: report[k] for k in ("server_sha256", "rotate", "canvas", "verdict")}
    summary.update({h[:12]: {"phases": f["phases"], **{
        c: {k: v for k, v in r.items() if k in ("fits", "stages", "groups", "template_tokens",
                                                   "width", "system_sha256", "labels_sha256", "error")}
        for c, r in f["by_canvas"].items()}} for h, f in report["families"].items()})
    if report.get("longest"):
        summary.update(longest=report["longest"], maxlen=report["maxlen"])
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if report["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
