"""Atestaciones congeladas de los análisis confirmatorios (JEV-87).

El espejo público sustituye los `raw` de cada respuesta por su `raw_sha256` (publish.transform):
las puertas de visibilidad que leen esos raw (cliente, thinking, motor) no se pueden repetir allí.
En vez de relajar las puertas, el repo privado ejecuta cada analizador, registra **todos los
ficheros que lee** (resultados, GT, runs de puertas, logs, código importado; con un audit hook de
Python) y congela su salida junto con el hash de la versión pública de cada uno.

  python3 -m jevbench.attest freeze            # privado: regenera docs/auditorias/*.json
  python3 -m jevbench.attest verify            # privado o espejo: exit 0 solo si todo cuadra

Niveles que imprime `verify`, por experimento:
  - «reproducido»: el analizador no lee raw; se re-ejecuta (en privado y en el espejo) y su
    salida y código de retorno coinciden literalmente con los congelados;
  - «atestado»: el analizador lee raw. En privado se re-ejecuta y se compara igual; en el espejo
    se comprueba que cada dependencia exportada tiene el hash congelado (los raw quedan ligados por
    su `raw_sha256`) y la clasificación mostrada es la congelada. Es una declaración del editor
    sobre evidencia privada ligada por hashes, no una prueba criptográfica de ejecución.
Los veredictos que se imprimen se extraen siempre de la salida comprobada.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "auditorias"
PUBLIC_EXIT = 3

# nombre → (comando, ¿lee raw?)
EXPERIMENTS = {
    "jev67": (["-m", "jevbench.jev67", "report"], True),
    "jev68": (["-m", "jevbench.qwen_session", "analyze", "--profile", "jev68"], True),
    "jev70": (["-m", "jevbench.dgemma_report"], True),
    "jev76": (["-m", "jevbench.qwen_session", "analyze", "--profile", "jev76"], True),
    "jev77": (["-m", "jevbench.qwen_session", "analyze", "--profile", "jev77"], True),
    "jev78": (["-m", "jevbench.jev78", "analyze"], False),
    "jev81": (["-m", "jevbench.jev81", "repeat"], False),
    "jev82": (["-m", "jevbench.jev82", "analyze"], False),
    "jev84": (["scripts/jev84_analyze.py"], False),
    # JEV-90: confirmatorios Microsoft-Decision-1 (lean scores/decisiones; no lean raw)
    "jev90_holm53": (["-m", "jevbench.jev90", "holm53"], False),
    "jev90_primacy": (["-m", "jevbench.jev90", "primacy"], False),
    "jev90_department_discords": (
        ["-m", "jevbench.jev90", "department-discords", "--r2", "jev_ms_decision1_r2"],
        False),
}

VERDICT = re.compile(r"CONFIRMAD|REFUTAD|INCONCLUS|NO EVALUABLE|CUMPLE|ESTABLE|significativ", re.I)
DEP_PREFIXES = ("results/", "data/", "docs/", "jevbench/", "scripts/")

# Envoltorio: ejecuta el analizador y anota cada fichero del repo que abre (audit hook) y cada
# módulo importado desde el repo. Se escribe en un fichero temporal al salir (también con SystemExit).
_TRACER = r"""
import atexit, json, os, runpy, sys
root, out, argv = os.getcwd(), sys.argv[1], sys.argv[2:]
seen = set()
def hook(ev, args):
    if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.path.abspath(os.fsdecode(args[0]))
        if p.startswith(root + os.sep):
            seen.add(os.path.relpath(p, root))
sys.addaudithook(hook)
def dump():
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f and os.path.abspath(f).startswith(root + os.sep):
            seen.add(os.path.relpath(os.path.abspath(f), root))
    with open(out, "w") as fh:
        json.dump(sorted(seen), fh)
atexit.register(dump)
if argv[0] == "-m":
    sys.argv = [argv[1]] + argv[2:]
    runpy.run_module(argv[1], run_name="__main__", alter_sys=True)
else:
    sys.argv = argv
    runpy.run_path(argv[0], run_name="__main__")
"""


def in_public_export():
    """True en el espejo público: publish.py no se exporta y los raw están sustituidos por hashes."""
    import importlib.util
    return importlib.util.find_spec("jevbench.publish") is None


def public_exit(printer=print):
    """Para los analizadores que leen raw: en el espejo avisan y salen con código ≠ 0, en vez de
    dar por buenas clasificaciones «NO EVALUABLE» que solo reflejan la ausencia de raw (JEV-87)."""
    if not in_public_export():
        return 0
    printer("\nAVISO (espejo público): este análisis lee los raw de cada respuesta, que el espejo "
            "sustituye por raw_sha256; sus puertas no se pueden repetir aquí. Las clasificaciones "
            "congeladas en privado y su ligadura por hash se comprueban con "
            "`python3 -m jevbench.attest verify`.")
    return PUBLIC_EXIT


def _run(cmd, trace=False):
    """(rc, stdout, deps). deps = ficheros del repo leídos (solo si trace)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if not trace:
        p = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True, env=env)
        return p.returncode, p.stdout, None
    with tempfile.NamedTemporaryFile("r", suffix=".json") as tf:
        p = subprocess.run([sys.executable, "-c", _TRACER, tf.name, *cmd], cwd=ROOT,
                           capture_output=True, text=True, env=env)
        try:
            deps = json.load(open(tf.name))
        except (OSError, ValueError):
            deps = []
    deps = set(deps) | ({_entry_file(cmd)} - {None})  # runpy restaura __main__: el hook no lo ve
    deps = sorted(d for d in deps
                  if d.startswith(DEP_PREFIXES) and "__pycache__" not in d
                  and not d.startswith("docs/auditorias/") and (ROOT / d).is_file())
    return p.returncode, p.stdout, deps


def _entry_file(cmd):
    """Fichero fuente del analizador que se ejecuta (módulo con -m o script), relativo al repo;
    None para código en línea (-c, solo en tests)."""
    if cmd[0] == "-c":
        return None
    if cmd[0] == "-m":
        rel = cmd[1].replace(".", "/") + ".py"
        if not (ROOT / rel).is_file():
            rel = cmd[1].replace(".", "/") + "/__main__.py"
        return rel
    return cmd[0]


def _dep_hash(rel):
    """(sha256 de la versión pública, ¿se exporta?). En el espejo los ficheros ya están transformados."""
    data = (ROOT / rel).read_bytes()
    try:
        from . import publish  # privado
    except ImportError:
        return hashlib.sha256(data).hexdigest(), True
    if not publish.in_manifest(rel):
        return hashlib.sha256(data).hexdigest(), False
    return hashlib.sha256(publish.transform(rel, data)).hexdigest(), True


def verdicts(output):
    return [l.strip() for l in output.splitlines() if VERDICT.search(l)]


def freeze(names=None):
    unknown = set(names or ()) - set(EXPERIMENTS)
    if unknown:
        raise SystemExit(f"experimentos desconocidos: {sorted(unknown)}")
    if in_public_export():
        raise SystemExit("freeze solo se ejecuta en el repo privado (necesita los raw)")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cmd, needs_raw) in EXPERIMENTS.items():
        if names and name not in names:
            continue
        rc, text, deps = _run(cmd, trace=True)
        runs = sorted({d.split("/")[1] for d in deps if d.startswith("results/") and d.count("/") >= 2})
        if rc != 0 or not text.strip() or not runs:
            raise SystemExit(f"{name}: el analizador falló o no leyó resultados "
                             f"(rc={rc}, {len(runs)} runs); no se congela")
        files = {}
        for d in deps:
            h, exported = _dep_hash(d)
            files[d] = {"sha256": h, "exported": exported}
        doc = {"experiment": name, "command": "python3 " + " ".join(cmd), "needs_raw": needs_raw,
               "returncode": rc, "output": text, "runs": runs, "files": files}
        (OUT / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        priv = sum(not f["exported"] for f in files.values())
        print(f"{name}: {len(runs)} runs, {len(files)} ficheros leídos ({priv} privados), "
              f"{len(verdicts(text))} líneas de veredicto")


def _check(name, doc, public):
    """Lista de problemas de una atestación (vacía = cuadra)."""
    cmd, needs_raw = EXPERIMENTS[name]
    problems = []
    if doc.get("experiment") != name or doc.get("command") != "python3 " + " ".join(cmd) \
            or doc.get("needs_raw") != needs_raw:
        problems.append("la atestación no corresponde al registro EXPERIMENTS")
    if doc.get("returncode") != 0 or not doc.get("output", "").strip() or not doc.get("runs") \
            or not doc.get("files"):
        problems.append("atestación de un análisis fallido o vacío")
    entry = _entry_file(cmd)
    if entry is not None and entry not in (doc.get("files") or {}):
        problems.append(f"{entry}: el analizador no está ligado en la atestación")
    for rel, ref in (doc.get("files") or {}).items():
        if public and not ref["exported"]:
            continue  # evidencia privada: ligada en privado, no verificable en el espejo
        if not (ROOT / rel).is_file():
            problems.append(f"{rel}: falta")
            continue
        h, exported = _dep_hash(rel)
        if not public and exported != ref["exported"]:
            problems.append(f"{rel}: cambió su pertenencia al espejo")
        if h != ref["sha256"]:
            problems.append(f"{rel}: hash distinto del congelado")
    if not needs_raw or not public:
        rc, text, _ = _run(cmd)
        if rc != 0:
            problems.append(f"código de retorno {rc} al re-ejecutar")
        if text != doc.get("output"):
            problems.append("la salida re-ejecutada no coincide con la congelada")
    return problems


def verify(names=None, printer=print):
    """Devuelve el número de discrepancias (0 = todo cuadra). Sin nombres exige todos los de EXPERIMENTS."""
    wanted = list(names) if names else list(EXPERIMENTS)
    unknown = [n for n in wanted if n not in EXPERIMENTS]
    if unknown:
        printer(f"experimentos desconocidos: {unknown}")
        return len(unknown)
    public = in_public_export()
    bad = 0
    for name in wanted:
        f = OUT / f"{name}.json"
        if not f.is_file():
            printer(f"✗ {name}: falta docs/auditorias/{name}.json")
            bad += 1
            continue
        doc = json.loads(f.read_text())
        problems = _check(name, doc, public)
        if problems:
            bad += len(problems)
            printer(f"✗ {name}: {len(problems)} discrepancias")
            for p in problems[:20]:
                printer(f"    {p}")
            continue
        files = doc["files"]
        priv = sum(not v["exported"] for v in files.values())
        if not doc["needs_raw"]:
            level = "reproducido (salida re-ejecutada idéntica)"
        elif public:
            level = (f"atestado (clasificación congelada en privado; {len(files) - priv} ficheros "
                     f"ligados por hash, {priv} privados no verificables aquí)")
        else:
            level = "re-ejecutado en privado sobre raw (salida idéntica)"
        printer(f"✓ {name}: {level}; {len(doc['runs'])} runs")
        for v in verdicts(doc["output"])[:40]:
            printer(f"    {v}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["freeze", "verify"])
    ap.add_argument("names", nargs="*", help="experimentos (por defecto, todos)")
    a = ap.parse_args(argv)
    if a.cmd == "freeze":
        freeze(a.names)
        return 0
    return 1 if verify(a.names) else 0


if __name__ == "__main__":
    raise SystemExit(main())
