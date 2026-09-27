"""Result files: results/<run>/<phase>.json = {"meta": {...}, "cases": {id: record}}.
A record is {"answers": <wire answers>, "ms", "cost", "model"} or {"error": str}."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"


def path(run, phase):
    run = Path(run)
    base = run if run.is_absolute() or run.parts[:1] == ("results",) else ROOT / run
    return base / f"{phase}.json"


def load(run, phase):
    p = path(run, phase)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save(run, phase, doc):
    p = path(run, phase)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    os.replace(tmp, p)
    return p


def runs_in(run):
    """Phases present for a run directory."""
    base = path(run, "x").parent
    return sorted(p.stem for p in base.glob("*.json"))
