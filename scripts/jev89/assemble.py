"""JEV-89 W5: ensambla el conjunto de entrenamiento (docs/plan_modelo_propio.md §8 y §8.1).

Une las fuentes esperadas, recalcula la aceptación de los sintéticos con la regla vigente
(synth_triage.accept, enmienda E1), añade la procedencia por registro, pasa el filtro de
contaminación, asigna train/val (10 % val, agrupando por la unidad que podría filtrarse: semilla
CodiEsp en los sintéticos, PMID en papers, split original en PMR), separa lo no comercial (nc) y
escribe un manifiesto con hashes de scripts, fuentes, índice de exclusión y salidas.

    python3 scripts/jev89/assemble.py --build /var/tmp/jev89/build --papers papers_pubmed_v2.jsonl
"""
import argparse
import collections
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_triage  # noqa: E402

GENERATOR = {"repo": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a",
             "dtype": "fp8", "server": "SGLang lmsysorg/sglang:qwen38-27b", "thinking": False,
             "gen": {"temperature": 0.9, "top_p": 0.8, "presence_penalty": 1.5},
             "check": {"temperature": 0.0}}
CODIESP = {"name": "CodiEsp (BSC, eHealth CLEF 2020)", "license": "CC BY 4.0",
           "url": "https://zenodo.org/records/3693570", "doi": "10.5281/zenodo.3693570",
           "role": "semilla clínica reescrita (no se copian frases)"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(r):
    """Añade `sources` y `publishable` (§8.1) si el productor no los trae."""
    if r["source"] == "synthetic_qwen38":
        src = [{"name": "texto generado", "generator": GENERATOR["repo"],
                "generator_license": "Apache-2.0 (licencia del modelo, no de los datos)"}]
        if r["meta"].get("seed_codiesp"):
            src.append(dict(CODIESP, file=r["meta"]["seed_codiesp"]))
        r["sources"], r["publishable"] = src, True
    elif r["source"] == "pmr_reddit":
        r.setdefault("sources", [{"name": "PMR-Bench / PMR-Reddit (PortalPal-AI)", "license": "CC BY-NC 4.0",
                                  "url": "https://huggingface.co/datasets/PortalPal-AI/PMR-Reddit-Train-Dev-Pool"}])
        r["publishable"] = False
    else:  # pubmed: derechos del editor sin verificar
        r.setdefault("sources", [{"name": "PubMed/MEDLINE", "pmid": r["meta"].get("pmid"),
                                  "license": "NLM: uso con atribución; copyright del editor si consta"}])
        r["publishable"] = False
    return r


def group_key(r):
    m = r.get("meta", {})
    if r["source"] == "synthetic_qwen38":
        return "codiesp:" + m["seed_codiesp"] if m.get("seed_codiesp") else r["id"]
    if r["source"] == "pubmed":
        return "pmid:" + str(m.get("pmid"))
    return r["id"]


def split_of(r):
    if r["source"] == "pmr_reddit":
        return "val" if r["meta"].get("pmr_split") == "dev" else "train"
    h = int(hashlib.sha256(group_key(r).encode()).hexdigest(), 16)
    return "val" if h % 10 == 0 else "train"


def load_sources(b, papers):
    """Fuentes esperadas; falta una → error (no se ensambla un conjunto parcial)."""
    srcs = {"synth_triage.jsonl": b / "synth_triage.jsonl", "pmr_reddit.jsonl": b / "pmr_reddit.jsonl",
            "papers_pubmed.jsonl": b / papers}
    for p in srcs.values():
        if not p.exists():
            sys.exit(f"falta la fuente esperada {p}")
    out, stats = {}, {}
    for name, p in srcs.items():
        rows = [json.loads(line) for line in p.open()]
        n_in = len(rows)
        if name == "synth_triage.jsonl":
            for r in rows:
                # validación estricta (sin coerciones bool/float) antes de comparar, también en históricos
                chk = r["meta"].get("check")
                chk = synth_triage.parse_labels(json.dumps(chk)) if isinstance(chk, dict) else None
                gt_ok = synth_triage.parse_labels(json.dumps(r["gt"])) == r["gt"]
                r["accepted"] = gt_ok and synth_triage.accept(r["gt"], chk)
                # la manipulación se pidió al generador, pero nadie comprueba que el engaño sea visible
                m = r["meta"]
                if "manipulation" in m:
                    m["manipulation_requested"] = m.pop("manipulation")
                m["manipulation_verified"] = False
            rows = [r for r in rows if r["accepted"]]
        out[name] = [provenance(r) for r in rows]
        stats[name] = {"path": str(p), "sha256": sha(p), "n_in": n_in, "n_aceptados": len(rows)}
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="/var/tmp/jev89/build")
    ap.add_argument("--papers", default="papers_pubmed_v2.jsonl")
    a = ap.parse_args()
    b = Path(a.build)
    run = b / ("run-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    staged, clean, out = run / "staged", run / "limpio", run / "final"
    for d in (staged, clean, out):
        d.mkdir(parents=True)
    sources, src_stats = load_sources(b, a.papers)
    inputs = []
    for name, rows in sources.items():
        dst = staged / name
        dst.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        inputs.append(str(dst))
    subprocess.run([sys.executable, str(ROOT / "scripts/jev89/contamination.py"), *inputs,
                    "--out-dir", str(clean)], check=True)
    buckets = collections.defaultdict(list)
    for name in sources:
        for line in (clean / name).open():
            r = json.loads(line)
            r["split"] = split_of(r)
            buckets[(r["split"], r.get("nc", False))].append(r)
    report = {"ficheros": {}, "distribucion": {}, "mayoria": {}}
    for (split, nc), rows in sorted(buckets.items()):
        name = f"{split}{'_nc' if nc else ''}.jsonl"
        (out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        report["ficheros"][name] = len(rows)
        dist = collections.defaultdict(collections.Counter)
        for r in rows:
            dist["task/lang"][f"{r['task']}/{r['lang']}"] += 1
            dist["source"][r["source"]] += 1
            dist["publishable"][str(r["publishable"])] += 1
            for q, v in r["gt"].items():
                dist[q][str(v)] += 1
        report["distribucion"][name] = {k: dict(v) for k, v in dist.items()}
        # línea base de mayoría por pregunta (regla del banco: toda tabla lleva la mayoría)
        report["mayoria"][name] = {q: round(max(c.values()) / sum(c.values()), 3) for q, c in dist.items()
                                   if q not in ("task/lang", "source", "publishable")}
    (out / "informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    scripts = {p.name: sha(p) for p in sorted((ROOT / "scripts/jev89").glob("*.py"))}
    manifest = {
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "spec": "docs/plan_modelo_propio.md §8 + enmienda E1 (§8.1)",
        "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                   text=True).stdout.strip(),
        "scripts_sha256": scripts,
        "fuentes": src_stats,
        "contaminacion_informe_sha256": sha(clean / "contaminacion_informe.json"),
        "indice_exclusion": {k: json.loads((clean / "contaminacion_informe.json").read_text())[k]
                             for k in ("bank_index_version", "bank_index_sha256", "bank_ngrams", "bank_pmids",
                                       "coverage")},
        "generador": GENERATOR,
        "aceptacion_sinteticos": "synth_triage.accept: coincidencia exacta en las 5 preguntas (E1)",
        "salidas_sha256": {n: sha(out / n) for n in sorted(report["ficheros"])},
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    (out / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in manifest["salidas_sha256"].items()))
    print(run)
    print(json.dumps(report["ficheros"], indent=1))


if __name__ == "__main__":
    main()
