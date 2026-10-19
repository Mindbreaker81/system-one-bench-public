#!/usr/bin/env python3
"""W4 (JEV-89): filtro de contaminación frente a data/ del banco.

Único punto del flujo que lee data/. Normaliza textos, descarta candidatos
que compartan un 8-grama con el banco, cuyo meta.pmid esté en el banco, o
que sean duplicados exactos (texto normalizado) de otro candidato.

Enmienda E1 / W4c: sin exención por frecuencia; índice incluye
battery.OOD_CASES; fallo cerrado si data/ es ilegible, el índice queda vacío
o falta alguna fase; deduplicación global entre ficheros de la llamada.
En papers compara solo Title+Abstract (exclusión estructural).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jevbench.battery import (  # noqa: E402
    ALERT_PHASES,
    EXTRA_PHASES,
    OOD_CASES,
    PHASES,
    RULES_PHASES,
)

DEFAULT_DATA = REPO_ROOT / "data"
DEFAULT_OUT_DIR = Path("/var/tmp/jev89/build/limpio")

REQUIRED_PHASES = list(PHASES) + list(EXTRA_PHASES) + list(RULES_PHASES) + list(ALERT_PHASES)

# stem base (sin .vN) → fases de la batería que cubre ese fichero
_STEM_TO_PHASES: dict[str, list[str]] = {
    "bench_cases": ["triage_es", "triage_en"],
    "triage_ext_cases": ["triage_ext_es", "triage_ext_en"],
    "papers32": ["papers32"],
    "adversarial_cases": ["adv1"],
    "adversarial2_cases": ["adv2"],
    "adversarial3_cases": ["adv3"],
    "adversarial4_cases": ["adv4"],
    "adversarial5_cases": ["adv5"],
}

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")
_TITLE_LINE_RE = re.compile(r"^Title:\s*(.+)$", re.MULTILINE)
_ABSTRACT_RE = re.compile(r"^Abstract:\s*(.*)\Z", re.MULTILINE | re.DOTALL)
_VERSION_STEM_RE = re.compile(r"^(.+)\.v\d+$")


class BankError(Exception):
    """Índice de evaluación incompleto, ilegible o vacío."""


def normalize(text: str) -> str:
    """Minúsculas, sin acentos, solo alfanuméricos, tokens separados por espacio."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFD", str(text).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _NON_ALNUM_RE.sub(" ", s)
    return " ".join(s.split())


def tokens(text: str) -> list[str]:
    norm = normalize(text)
    return norm.split() if norm else []


def ngrams(toks: list[str], n: int = 8) -> set[tuple[str, ...]]:
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def _paper_text(item: dict) -> str:
    """Solo Title + Abstract (sin Journal ni Publication types)."""
    title = item.get("title") or ""
    abstract = item.get("abstract") or ""
    return f"{title}\n{abstract}".strip()


def extract_title_abstract(state: str) -> str:
    """Del state plantilla de papers, solo Title + Abstract."""
    if not state:
        return ""
    title_m = _TITLE_LINE_RE.search(state)
    abs_m = _ABSTRACT_RE.search(state)
    title = title_m.group(1).strip() if title_m else ""
    abstract = abs_m.group(1).strip() if abs_m else ""
    if title or abstract:
        return f"{title}\n{abstract}".strip()
    return state


def comparable_text(rec: dict) -> str:
    """Texto usado para 8-gramas: en papers solo Title+Abstract."""
    state = rec.get("state") or ""
    if rec.get("task") == "papers":
        return extract_title_abstract(state)
    return state


def _stem_base(path: Path) -> str:
    stem = path.stem
    m = _VERSION_STEM_RE.match(stem)
    return m.group(1) if m else stem


def _phases_for_path(path: Path) -> list[str]:
    return list(_STEM_TO_PHASES.get(_stem_base(path), []))


INDEX_VERSION = "8gram-nfd-alnum-v1"


def index_digest(gram_to_case, bank_pmids) -> str:
    """SHA-256 determinista del índice de exclusión (8-gramas ordenados + PMIDs ordenados)."""
    payload = {"version": INDEX_VERSION,
               "grams": sorted(" ".join(g) for g in gram_to_case),
               "pmids": sorted(bank_pmids)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_bank(
    data_dir: Path,
    *,
    ood_cases: dict[str, str] | None = None,
    require_phases: bool = True,
) -> tuple[dict[tuple[str, ...], str], set[str], dict]:
    """Índice 8-grama → id de caso del banco, PMIDs y cobertura.

    No expone textos: solo ids y n-gramas internos.
    Abortan con BankError: JSON ilegible, índice vacío, fase requerida ausente.
    """
    gram_to_case: dict[tuple[str, ...], str] = {}
    pmids: set[str] = set()
    by_file: dict[str, int] = {}
    by_phase: dict[str, int] = {p: 0 for p in REQUIRED_PHASES}
    ood = OOD_CASES if ood_cases is None else ood_cases

    def add_text(case_id: str, text: str) -> None:
        for g in ngrams(tokens(text), 8):
            gram_to_case.setdefault(g, case_id)

    def bump_file(label: str, n: int = 1) -> None:
        if n > 0:
            by_file[label] = by_file.get(label, 0) + n

    def bump_phases(phases: list[str], n: int = 1) -> None:
        if n <= 0:
            return
        for ph in phases:
            if ph in by_phase:
                by_phase[ph] += n

    if not data_dir.is_dir():
        raise BankError(f"data_dir inexistente o no es directorio: {data_dir}")

    for path in sorted(data_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BankError(f"no se pudo parsear {path}: {exc}") from exc

        phases = _phases_for_path(path)
        n_file = 0

        if isinstance(data, list):
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                if item.get("pmid") is not None and str(item["pmid"]).strip():
                    pmids.add(str(item["pmid"]).strip())
                if "es" in item or "en" in item:
                    name = str(item.get("name") or f"{path.stem}:{i}")
                    used = False
                    for lang in ("es", "en"):
                        if item.get(lang):
                            add_text(f"{name}#{lang}", item[lang])
                            used = True
                            lang_phases = [p for p in phases if p.endswith(f"_{lang}")]
                            bump_phases(lang_phases, 1)
                    if used:
                        n_file += 1
                elif "title" in item or "abstract" in item:
                    pid = str(item.get("pid") or item.get("pmid") or f"{path.stem}:{i}")
                    add_text(pid, _paper_text(item))
                    n_file += 1
                    bump_phases(phases, 1)
                elif item.get("state"):
                    cid = str(item.get("id") or item.get("name") or f"{path.stem}:{i}")
                    add_text(cid, item["state"])
                    n_file += 1
                    bump_phases(phases, 1)
        elif isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict) and val.get("state"):
                    add_text(str(key), val["state"])
                    n_file += 1
                    bump_phases(phases, 1)
                if isinstance(val, dict) and val.get("pmid") is not None:
                    pmids.add(str(val["pmid"]).strip())

        bump_file(path.name, n_file)

    # OOD: estados de la batería (no viven en data/)
    for oid, text in ood.items():
        add_text(f"ood:{oid}", text)
    bump_file("battery.OOD_CASES", len(ood))
    bump_phases(["ood"], len(ood))

    coverage = {
        "by_file": dict(sorted(by_file.items())),
        "by_phase": dict(by_phase),
        "ood_cases": sorted(ood.keys()),
    }

    if not gram_to_case:
        raise BankError("índice de 8-gramas vacío tras cargar el banco")

    if require_phases:
        missing = [p for p in REQUIRED_PHASES if by_phase.get(p, 0) <= 0]
        if missing:
            raise BankError(
                "fases sin cobertura en el índice: " + ", ".join(missing)
            )

    return gram_to_case, pmids, coverage


def _candidate_pmid(rec: dict) -> str | None:
    meta = rec.get("meta") or {}
    if not isinstance(meta, dict):
        return None
    pmid = meta.get("pmid")
    if pmid is None or str(pmid).strip() == "":
        return None
    return str(pmid).strip()


def filter_candidates(
    records: list[dict],
    gram_to_case: dict[tuple[str, ...], str],
    bank_pmids: set[str],
    sources: list[str] | None = None,
) -> tuple[list[dict], list[str], dict]:
    """Filtra candidatos con deduplicación global.

    ``sources[i]`` es el fichero de origen de ``records[i]`` (misma longitud).
    Devuelve (kept, kept_sources, stats).
    """
    if sources is None:
        sources = [""] * len(records)
    if len(sources) != len(records):
        raise ValueError("sources debe tener la misma longitud que records")

    kept: list[dict] = []
    kept_sources: list[str] = []
    seen_norm: dict[str, tuple[str, str]] = {}  # norm → (id, file)
    discarded_ngram: list[dict] = []
    discarded_dups: list[dict] = []
    n_pmid = 0
    n_dup = 0
    n_ngram = 0

    for rec, src in zip(records, sources):
        cid = str(rec.get("id") or "")
        state = rec.get("state") or ""
        norm = normalize(state)

        pmid = _candidate_pmid(rec)
        if pmid is not None and pmid in bank_pmids:
            n_pmid += 1
            continue

        if norm in seen_norm:
            first_id, first_file = seen_norm[norm]
            n_dup += 1
            discarded_dups.append({
                "candidate_id": cid,
                "source_file": src,
                "first_id": first_id,
                "first_file": first_file,
            })
            continue

        hit_bank = None
        for g in ngrams(tokens(comparable_text(rec)), 8):
            if g in gram_to_case:
                hit_bank = gram_to_case[g]
                break
        if hit_bank is not None:
            n_ngram += 1
            discarded_ngram.append({
                "candidate_id": cid,
                "bank_case_id": hit_bank,
                "source_file": src,
            })
            continue

        seen_norm[norm] = (cid, src)
        kept.append(rec)
        kept_sources.append(src)

    stats = {
        "n_in": len(records),
        "n_out": len(kept),
        "discarded_ngram": n_ngram,
        "discarded_pmid": n_pmid,
        "discarded_duplicate": n_dup,
        "ngram_hits": discarded_ngram,
        "duplicate_hits": discarded_dups,
    }
    return kept, kept_sources, stats


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(
    inputs: list[Path],
    out_dir: Path,
    data_dir: Path,
    *,
    ood_cases: dict[str, str] | None = None,
    require_phases: bool = True,
) -> dict:
    gram_to_case, bank_pmids, coverage = load_bank(
        data_dir, ood_cases=ood_cases, require_phases=require_phases
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    all_sources: list[str] = []
    input_names: list[str] = []
    for inp in inputs:
        records = read_jsonl(inp)
        input_names.append(inp.name)
        for rec in records:
            all_records.append(rec)
            all_sources.append(inp.name)

    kept, kept_sources, stats = filter_candidates(
        all_records, gram_to_case, bank_pmids, sources=all_sources
    )

    by_out: dict[str, list[dict]] = {name: [] for name in input_names}
    for rec, src in zip(kept, kept_sources):
        by_out.setdefault(src, []).append(rec)

    # Contadores por fichero de entrada
    n_in_by: dict[str, int] = {name: 0 for name in input_names}
    for src in all_sources:
        n_in_by[src] = n_in_by.get(src, 0) + 1

    ngram_by: dict[str, list[dict]] = {name: [] for name in input_names}
    for hit in stats["ngram_hits"]:
        ngram_by.setdefault(hit["source_file"], []).append(hit)

    dup_by: dict[str, list[dict]] = {name: [] for name in input_names}
    for hit in stats["duplicate_hits"]:
        dup_by.setdefault(hit["source_file"], []).append(hit)

    pmid_by: dict[str, int] = {name: 0 for name in input_names}
    # recount pmid discards per source
    for rec, src in zip(all_records, all_sources):
        pmid = _candidate_pmid(rec)
        if pmid is not None and pmid in bank_pmids:
            pmid_by[src] = pmid_by.get(src, 0) + 1

    report: dict = {
        "bank_ngrams": len(gram_to_case),
        "bank_pmids": len(bank_pmids),
        "bank_index_version": INDEX_VERSION,
        "bank_index_sha256": index_digest(gram_to_case, bank_pmids),
        "coverage": coverage,
        "files": {},
        "duplicates": stats["duplicate_hits"],
    }
    for name in input_names:
        out_path = out_dir / name
        rows = by_out.get(name, [])
        write_jsonl(rows, out_path)
        report["files"][name] = {
            "n_in": n_in_by.get(name, 0),
            "n_out": len(rows),
            "discarded_ngram": len(ngram_by.get(name, [])),
            "discarded_pmid": pmid_by.get(name, 0),
            "discarded_duplicate": len(dup_by.get(name, [])),
            "ngram_hits": ngram_by.get(name, []),
            "duplicate_hits": dup_by.get(name, []),
            "out": str(out_path),
        }
    informe = out_dir / "contaminacion_informe.json"
    informe.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["informe"] = str(informe)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="+", type=Path, help="JSONL candidatos")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA,
                   help="raíz data/ del banco (solo este script la lee)")
    args = p.parse_args(argv)
    try:
        report = run(args.inputs, args.out_dir, args.data_dir)
    except BankError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for name, st in report["files"].items():
        print(
            f"{name}: in={st['n_in']} out={st['n_out']} "
            f"ngram={st['discarded_ngram']} pmid={st['discarded_pmid']} "
            f"dup={st['discarded_duplicate']}",
            file=sys.stderr,
        )
    cov = report["coverage"]
    print("cobertura por fichero/fase:", file=sys.stderr)
    for fname, n in cov["by_file"].items():
        print(f"  file {fname}: {n}", file=sys.stderr)
    for phase, n in cov["by_phase"].items():
        print(f"  phase {phase}: {n}", file=sys.stderr)
    print(f"informe → {report['informe']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
