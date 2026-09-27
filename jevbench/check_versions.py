"""Check which Jev version each provider serves and log it (docs/versiones_jev.md).

  python -m jevbench.check_versions            # one 1-question probe per alias (~$0.00001 each)
  python -m jevbench.check_versions --log      # also append a row to docs/versiones_jev.md

If any alias resolves to something other than KNOWN, the battery must be re-run
(jev_v3 + cascade) before comparing numbers: see AGENTS.md, rule 4.
"""
import argparse
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

from .adapters.jev import Jev
from .env import load_env

KNOWN = {"typesafe/jev-1.13-20260917", "jev-1.13.0"}
PROBES = [("openrouter", "~typesafe/jev-latest"), ("typesafe", "jev-latest"), ("typesafe", "jev-preview")]
LOG = Path(__file__).resolve().parent.parent / "docs" / "versiones_jev.md"
QUESTION = {"q": {"type": "noul", "instructions": "Is this text about cooking?"}}


def listed_models():
    load_env()
    out = {}
    req = urllib.request.Request("https://api.typesafe.ai/v1/models",
                                 headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out["typesafe"] = [f"{m['name']} ({m.get('release_date', '')[:10]})" for m in json.loads(r.read())["models"]]
    req = urllib.request.Request("https://openrouter.ai/api/v1/models",
                                 headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out["openrouter"] = [m["id"] for m in json.loads(r.read())["data"]
                             if "typesafe" in m["id"] or "jev" in m["id"].lower()]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="store_true")
    args = ap.parse_args()
    resolved = {}
    for provider, model in PROBES:
        try:
            out = Jev(provider=provider, model=model).decide("Roast the chicken for 35 minutes.", QUESTION)
            resolved[f"{provider}:{model}"] = out["model"]
        except Exception as e:  # e.g. alias not offered by that provider
            resolved[f"{provider}:{model}"] = f"ERROR {str(e)[:60]}"
    listed = listed_models()
    new = sorted({v for v in resolved.values() if not v.startswith("ERROR") and v not in KNOWN})
    for k, v in resolved.items():
        print(f"{k:34} -> {v}")
    print("listados:", json.dumps(listed, ensure_ascii=False))
    print("NUEVA VERSIÓN: " + ", ".join(new) if new else f"sin cambios (conocidas: {sorted(KNOWN)})")
    if args.log:
        row = (f"| {dt.date.today().isoformat()} | " + " · ".join(f"`{k}` → `{v}`" for k, v in resolved.items())
               + f" | {'**nueva: ' + ', '.join(new) + '**' if new else 'sin cambios'} |")
        LOG.write_text(LOG.read_text().rstrip("\n") + "\n" + row + "\n")
        print(f"registrado en {LOG}")


if __name__ == "__main__":
    main()
