"""JEV-70 §6.5: canario de seguimiento de criterios y calentamiento con documentos
ajenos al banco (docs/experimentos/dgemma_canary.json).

  python -m jevbench.dgemma_canary canary --run canary_dgemma_26b_a4b_nvfp4 --opt url=… …
  python -m jevbench.dgemma_canary warmup --tag P --opt url=… …   # 3 peticiones C0

El canario guarda results/<run>/canary.json (respuestas completas, raw si
capture_raw) y clasifica según la tabla pre-registrada; el calentamiento se anexa a
results/logs/dgemma_warmup.jsonl (no entra en ningún run)."""
import argparse
import datetime as dt
import hashlib
import json
import platform
import time
from pathlib import Path

from . import adapters, store

CANARY = Path(__file__).resolve().parent.parent / "docs" / "experimentos" / "dgemma_canary.json"
QID = "calib_choice"


def load():
    data = CANARY.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def questions(spec, variant):
    return {QID: {"type": "choice", "instructions": spec["instructions"],
                  "criteria": spec["variants"][variant]}}


def classify(hits_b, hits_c, n=5):
    """Tabla §6.5 (5 documentos por variante)."""
    if hits_b >= 4 and hits_c >= 4:
        return "sigue los criterios"
    if (hits_b >= 4 and hits_c <= 2) or (hits_c >= 4 and hits_b <= 2):
        return "sigue la posición o el nombre, no el criterio"
    if hits_b <= 2 and hits_c <= 2:
        return "no sigue los criterios"
    return "inconcluso"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["canary", "warmup"])
    ap.add_argument("--adapter", default="systemone_http")
    ap.add_argument("--opt", action="append", default=[])
    ap.add_argument("--run", help="canary: results/<run>/canary.json")
    ap.add_argument("--tag", default="", help="warmup: etiqueta en el log")
    args = ap.parse_args()
    spec, digest = load()
    opts = dict(o.split("=", 1) for o in args.opt)
    model = adapters.get(args.adapter)(**opts)

    if args.mode == "warmup":
        log = store.ROOT / "logs" / "dgemma_warmup.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        for doc_id in list(spec["documents"])[:3]:
            t0 = time.time()
            out = model.decide(spec["documents"][doc_id], questions(spec, "C0"))
            rec = {"tag": args.tag, "doc": doc_id, "ms": round((time.time() - t0) * 1000),
                   "choice": out["answers"][QID]["choice"], "host": platform.node(),
                   "at": dt.datetime.now().isoformat(timespec="seconds")}
            print(json.dumps(rec), flush=True)
            with log.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        return

    if not args.run:
        ap.error("canary necesita --run")
    if store.load(args.run, "canary"):
        raise SystemExit(f"results/{args.run}/canary.json ya existe: no se sobrescribe")
    doc = {"meta": {"adapter": args.adapter, **model.meta(), "canary_sha256": digest,
                    "host": platform.node(),
                    "updated": dt.datetime.now().isoformat(timespec="seconds")}, "cases": {}}
    for variant in spec["variants"]:
        for doc_id, text in spec["documents"].items():
            t0 = time.time()
            rec = {"variant": variant, "doc": doc_id}
            try:
                out = model.decide(text, questions(spec, variant))
                rec.update(answers=out["answers"], ms=round((time.time() - t0) * 1000))
                if "raw" in out:
                    rec["raw"] = out["raw"]
            except Exception as e:  # el canario no es bloqueante: se registra
                rec.update(error=f"{type(e).__name__}: {e}"[:300], diag=getattr(e, "diag", None))
            doc["cases"][f"{variant}:{doc_id}"] = rec
            print(variant, doc_id, rec.get("answers", {}).get(QID, {}).get("choice", rec.get("error")),
                  flush=True)
    hits = {}
    for variant, want in spec["expected"].items():
        got = [r["answers"][QID]["choice"] for r in doc["cases"].values()
               if r["variant"] == variant and "answers" in r]
        hits[variant] = {c: got.count(c) for c in sorted(set(got))}
        if want:
            hits[variant]["expected_hits"] = got.count(want)
    doc["summary"] = {"hits": hits, "verdict": classify(hits["C+b"].get("expected_hits", 0),
                                                       hits["C+c"].get("expected_hits", 0))}
    store.save(args.run, "canary", doc)
    print(json.dumps(doc["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
