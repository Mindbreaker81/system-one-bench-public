"""Re-liga en las auditorías congeladas el hash de un fichero que cambió sin cambiar el cálculo.

Caso típico: subir la versión cambia `jevbench/__init__.py`, que los 12 analizadores
confirmatorios importan, y `attest verify` deja de cuadrar. No se re-congela todo
(`attest freeze` regeneraría salidas y dependencias): se sustituye solo el `sha256` de ese
fichero en las auditorías que lo ligan, se comprueba que ningún otro campo cambia y se
documenta en `docs/experimentos/enmienda_atestaciones_r109.md`.

  python3 scripts/attest_rebind.py --check jevbench/__init__.py   # exit 1 si hay que re-ligar
  python3 scripts/attest_rebind.py jevbench/__init__.py           # re-liga y lo imprime
  python3 -m jevbench.attest verify                               # después, siempre
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import attest  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", help="ficheros del repo (p. ej. jevbench/__init__.py)")
    ap.add_argument("--check", action="store_true", help="no escribe; exit 1 si algo está desligado")
    args = ap.parse_args(argv)
    if attest.in_public_export():
        raise SystemExit("solo en el repo privado")
    stale = 0
    for rel in args.paths:
        new, _ = attest._dep_hash(rel)
        bound = 0
        for f in sorted(attest.OUT.glob("*.json")):
            doc = json.loads(f.read_text())
            entry = doc.get("files", {}).get(rel)
            if entry is None:
                continue
            bound += 1
            old = entry["sha256"]
            if old == new:
                continue
            stale += 1
            print(f"{f.name}: {rel} {old[:12]}… → {new}")
            if args.check:
                continue
            before = copy.deepcopy(doc)
            entry["sha256"] = new
            before["files"][rel]["sha256"] = new
            assert before == doc  # solo cambia ese campo
            f.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        if not bound:
            print(f"{rel}: ninguna auditoría lo liga")
    if not stale:
        print("auditorías al día")
    elif args.check:
        print(f"{stale} ligaduras desfasadas; ejecuta sin --check y documenta la enmienda")
    return 1 if (stale and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
