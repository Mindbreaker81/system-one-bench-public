"""Check which version each watched System One endpoint serves.

  python -m jevbench.check_versions            # one 1-question probe per alias (~$0.00002 total)
  python -m jevbench.check_versions --log      # also append rows to docs/versiones_jev.md

Families (each with its own known-set):
  - Jev (OpenRouter + TypeSafe aliases)
  - gpt-6-luna-decisions (OpenRouter decisions endpoint; JEV-80/81/82)

If a family resolves to something outside its known set, the warning names that family
and which runs / pre-registrations to repeat. Extension hook for OpenAI's native
Decisions API (JEV-78) is reserved below — not implemented yet.
"""
import argparse
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

from .adapters.jev import Jev
from .env import load_env

# Backward-compatible alias (historical Jev known-set).
KNOWN = {"typesafe/jev-1.13-20260917", "jev-1.13.0"}
KNOWN_LUNA_DECISIONS = {"openai/gpt-6-luna-decisions-20261006"}

LOG = Path(__file__).resolve().parent.parent / "docs" / "versiones_jev.md"
QUESTION = {"q": {"type": "noul", "instructions": "Is this text about cooking?"}}
PROBE_STATE = "Roast the chicken for 35 minutes."

# (id, label, known versions, probes [(provider, model)], on_new message)
FAMILIES = (
    {
        "id": "jev",
        "label": "Jev",
        "section": "## Jev",
        "known": KNOWN,
        "probes": [
            ("openrouter", "~typesafe/jev-latest"),
            ("typesafe", "jev-latest"),
            ("typesafe", "jev-preview"),
        ],
        "on_new": (
            "familia Jev: re-ejecutar `jev_v3` y la cascada Jev→Jev antes de comparar "
            "(AGENTS.md, regla 4; docs/procedimientos/evaluar-version-jev.md)."
        ),
    },
    {
        "id": "luna_decisions",
        "label": "gpt-6-luna-decisions",
        "section": "## gpt-6-luna-decisions (OpenRouter)",
        "known": KNOWN_LUNA_DECISIONS,
        "probes": [
            ("openrouter", "openai/gpt-6-luna-decisions"),
        ],
        "on_new": (
            "familia gpt-6-luna-decisions: re-ejecutar la batería JEV-80 "
            "(run `jev_luna_decisions`) y la rotación JEV-82 "
            "(run `jev_luna_decisions_d1`); comandos en "
            "`docs/infra_runs/luna_decisions_jev81.md` y "
            "`docs/infra_runs/luna_decisions_jev82.md`."
        ),
    },
)

# JEV-78 — OpenAI native Decisions API (`POST /v1/decisions`). Reserved: do not
# probe until an adapter and known version exist. Shape when enabled:
#   {"id": "openai_decisions", "label": "OpenAI Decisions", "known": {...},
#    "probes": [("openai", "<model>")], "on_new": "...", "section": "## OpenAI Decisions"}
OPENAI_DECISIONS_FAMILY = None


def active_families():
    """Families currently probed (excludes the JEV-78 stub until wired)."""
    out = list(FAMILIES)
    if OPENAI_DECISIONS_FAMILY is not None:
        out.append(OPENAI_DECISIONS_FAMILY)
    return out


def probe(provider, model):
    """One cheap noul call; returns the resolved model id string."""
    out = Jev(provider=provider, model=model).decide(PROBE_STATE, QUESTION)
    return out["model"]


def listed_models():
    load_env()
    out = {}
    req = urllib.request.Request(
        "https://api.typesafe.ai/v1/models",
        headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out["typesafe"] = [
            f"{m['name']} ({m.get('release_date', '')[:10]})"
            for m in json.loads(r.read())["models"]]
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ids = [m["id"] for m in json.loads(r.read())["data"]]
        out["openrouter"] = [
            mid for mid in ids
            if "typesafe" in mid or "jev" in mid.lower()
            or "luna-decisions" in mid or "gpt-6-luna-decisions" in mid]
    return out


def check_families(probe_fn=probe):
    """Run probes. Returns (resolved_by_family, new_by_family).

    resolved_by_family[id] = {provider:model → version or ERROR…}
    new_by_family[id] = sorted list of unknown versions (empty if none).
    """
    resolved_by, new_by = {}, {}
    for fam in active_families():
        resolved = {}
        for provider, model in fam["probes"]:
            key = f"{provider}:{model}"
            try:
                resolved[key] = probe_fn(provider, model)
            except Exception as e:  # e.g. alias not offered by that provider
                resolved[key] = f"ERROR {str(e)[:60]}"
        new = sorted({
            v for v in resolved.values()
            if not v.startswith("ERROR") and v not in fam["known"]})
        resolved_by[fam["id"]] = resolved
        new_by[fam["id"]] = new
    return resolved_by, new_by


def format_lines(resolved_by, new_by, listed=None):
    """Human-readable report lines (no I/O)."""
    lines = []
    fam_by_id = {f["id"]: f for f in active_families()}
    for fid, resolved in resolved_by.items():
        fam = fam_by_id[fid]
        lines.append(f"--- {fam['label']} ---")
        for k, v in resolved.items():
            lines.append(f"{k:42} -> {v}")
        if new_by.get(fid):
            lines.append("NUEVA VERSIÓN (" + fam["label"] + "): " + ", ".join(new_by[fid]))
            lines.append("→ " + fam["on_new"])
        else:
            lines.append(
                f"sin cambios ({fam['label']}; conocidas: {sorted(fam['known'])})")
    if listed is not None:
        lines.append("listados: " + json.dumps(listed, ensure_ascii=False))
    any_new = [fid for fid, n in new_by.items() if n]
    if any_new:
        labels = [fam_by_id[f]["label"] for f in any_new]
        lines.append("NUEVA VERSIÓN (familias): " + ", ".join(labels))
    else:
        lines.append("sin cambios (todas las familias)")
    return lines


def _append_under_section(text, section_heading, row):
    """Insert `row` after the last markdown table row of `section_heading`."""
    if section_heading not in text:
        return text.rstrip("\n") + f"\n\n{section_heading}\n\n" \
            "| fecha | alias → versión resuelta | resultado |\n|---|---|---|\n" \
            + row + "\n"
    start = text.index(section_heading)
    rest = text[start:]
    # Next ## after this section (if any)
    nxt = rest.find("\n## ", 1)
    block = rest if nxt < 0 else rest[:nxt]
    after = "" if nxt < 0 else rest[nxt:]
    # Last table row starting with |
    lines = block.rstrip("\n").split("\n")
    insert_at = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("|") and not lines[i].startswith("|---") \
                and not lines[i].startswith("| fecha"):
            insert_at = i + 1
            break
    lines.insert(insert_at, row)
    return text[:start] + "\n".join(lines) + ("\n" if after else "\n") + after.lstrip("\n")


def append_log(resolved_by, new_by):
    """Append one row per family under its section in docs/versiones_jev.md."""
    text = LOG.read_text()
    fam_by_id = {f["id"]: f for f in active_families()}
    today = dt.date.today().isoformat()
    for fid, resolved in resolved_by.items():
        fam = fam_by_id[fid]
        new = new_by.get(fid) or []
        aliases = " · ".join(f"`{k}` → `{v}`" for k, v in resolved.items())
        result = f"**nueva: {', '.join(new)}**" if new else "sin cambios"
        row = f"| {today} | {aliases} | {result} |"
        text = _append_under_section(text, fam["section"], row)
    LOG.write_text(text if text.endswith("\n") else text + "\n")
    return LOG


def main(argv=None, probe_fn=probe, list_fn=listed_models):
    ap = argparse.ArgumentParser(
        description="Probe Jev and gpt-6-luna-decisions versions on each provider.")
    ap.add_argument("--log", action="store_true",
                    help="append a row per family to docs/versiones_jev.md")
    args = ap.parse_args(argv)
    resolved_by, new_by = check_families(probe_fn=probe_fn)
    listed = list_fn()
    for line in format_lines(resolved_by, new_by, listed=listed):
        print(line)
    if args.log:
        path = append_log(resolved_by, new_by)
        print(f"registrado en {path}")
    return 0 if not any(new_by.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
