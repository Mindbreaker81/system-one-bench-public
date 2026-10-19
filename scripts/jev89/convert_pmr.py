#!/usr/bin/env python3
"""W2 (JEV-89): PMR-Reddit Train/Dev → JSONL formato común (nc: true).

Lee solo PortalPal-AI/PMR-Reddit-Train-Dev-Pool (no Test-Pairs ni sintéticos).
Requiere pyarrow (venv en /var/tmp/jev89/venv si no está en el sistema).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

DEFAULT_SRC = Path(
    "/var/tmp/jev89/datasets/hf/PortalPal-AI/PMR-Reddit-Train-Dev-Pool"
)
DEFAULT_OUT = Path("/var/tmp/jev89/build/pmr_reddit.jsonl")

# §8 plan_modelo_propio: PMR level 1 (más urgente) … 6 → etiquetas del banco.
# urgency del banco: 0=bajo, 1=medio, 2=crítico (índices de TRIAGE_QS).
LEVEL_TO_GT = {
    1: {"department": "urgencias", "urgency": 2, "same_day": 1, "clinical": 1},
    2: {"department": "consulta_externa", "urgency": 2, "same_day": 1, "clinical": 1},
    3: {"department": "consulta_externa", "urgency": 1, "same_day": 1, "clinical": 1},
    4: {"department": "consulta_externa", "urgency": 1, "same_day": 0, "clinical": 1},
    5: {"department": "consulta_externa", "urgency": 0, "same_day": 0, "clinical": 1},
    6: {"department": "consulta_externa", "urgency": 0, "same_day": 0, "clinical": 1},
}


def round_level(level) -> int:
    """Redondeo half-up a entero en [1, 6].

    Los niveles PMR a veces son medias de anotadores (p. ej. 3.5, 4.666…).
    Se documenta en el informe W24; no se descartan para conservar los 859.
    """
    x = float(level)
    if not math.isfinite(x):
        raise ValueError(f"level no finito: {level!r}")
    n = int(math.floor(x + 0.5))  # half-up para x >= 0
    if n < 1 or n > 6:
        raise ValueError(f"level fuera de 1–6 tras redondeo: {level!r} → {n}")
    return n


def map_level(level) -> tuple[int, dict]:
    """Devuelve (level_entero, gt parcial sin hostile)."""
    n = round_level(level)
    return n, dict(LEVEL_TO_GT[n])


def _read_parquet(path: Path) -> list[dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError as e:
        raise SystemExit(
            "hace falta pyarrow; usa /var/tmp/jev89/venv/bin/python "
            f"scripts/jev89/convert_pmr.py ({e})"
        ) from e
    table = pq.read_table(path)
    cols = {name: table.column(name).to_pylist() for name in table.column_names}
    n = len(next(iter(cols.values())))
    rows = []
    for i in range(n):
        rows.append({k: cols[k][i] for k in cols})
    return rows


def convert_pool(src: Path) -> list[dict]:
    """Convierte train+dev del pool a registros formato común."""
    data_dir = src / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"no hay data/ en {src}")

    records: list[dict] = []
    for split_name, pattern in (("train", "train-*.parquet"), ("dev", "dev-*.parquet")):
        files = sorted(data_dir.glob(pattern))
        if not files:
            raise FileNotFoundError(f"sin parquet {pattern} en {data_dir}")
        idx = 0
        for path in files:
            for row in _read_parquet(path):
                text = row.get("text")
                if text is None or not str(text).strip():
                    continue
                level_raw = row["level"]
                level_int, gt = map_level(level_raw)
                rec = {
                    "id": f"pmr-reddit-{split_name}-{idx:06d}",
                    "task": "triage",
                    "lang": "en",
                    "state": str(text),
                    "gt": gt,
                    "source": "pmr_reddit",
                    "license": "CC BY-NC 4.0",
                    "nc": True,
                    "split": "",
                    "meta": {
                        "pmr_split": split_name,
                        "level": level_raw if isinstance(level_raw, (int, float)) else float(level_raw),
                        "level_rounded": level_int,
                    },
                }
                if row.get("expert_comments") is not None:
                    rec["meta"]["expert_comments"] = row["expert_comments"]
                records.append(rec)
                idx += 1
    return records


def write_jsonl(records: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", type=Path, default=DEFAULT_SRC,
                   help="directorio del dataset HF Train-Dev-Pool")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help="JSONL de salida")
    args = p.parse_args(argv)
    records = convert_pool(args.src)
    write_jsonl(records, args.out)
    print(f"wrote {len(records)} → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
