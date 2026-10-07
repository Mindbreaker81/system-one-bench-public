"""JEV-70 §7 y revisiones 3–4: ejecución por fases de las celdas de DiffusionGemma.

  python3 -m jevbench.dgemma_f1 <celda> --session <id> [--resume] [--retry-pass] \
      [--dry-run] [--python EXE]

Celdas congeladas: P, S1 y R en el .81; X, Rot1 y L″ (Lp3, Lr3, Ld3) en el .80
(los puertos 127.0.0.1:1801x/1802x son túneles SSH locales). Lp/Ld (L) y
Lp2/Lr2/Ld2 (L′) quedan no ejecutables por las revisiones 4 y 5; L″ exige una
sesión nueva del motor de .80 arrancada con --reasoning-parser gemma4.
Cada fase es una invocación de `jevbench.run`;
su salida se anexa a results/logs/<run>.log y el resumen va por stdout.

La primera pasada es CASO A CASO: cada invocación es
`jevbench.run … --phases <fase> --limit 1` (el harness ejecuta el primer caso
no escrito; un caso con error cuenta como escrito). Antes de cada invocación se
evalúan las reglas de parada pre-registradas, así la cota es exacta: cero casos
extra tras alcanzar un límite:
  - 3 errores en una fase o 10 en el run → parar (los casos pendientes quedan
    sin ejecutar);
  - error cuyo texto contiene «timeout» → hacer GET a los dos /health
    (reintentos cada 10 s hasta 2 min); si responden se continúa con el
    siguiente caso (el del timeout queda con su error para el reintento), si no
    → parar;
  - tope global de la celda: minutos de la tabla acumulados de forma persistente
    en el estado entre primera pasada, resume y retry (no por invocación);
  - rc ≠ 0 del hijo o invocación que no escribe ningún caso → parar.
Al parar se imprime motivo y estado y se sale con exit ≠ 0.

Estado persistente por run en results/logs/<run>.f1_state.json (sesión, adapter,
opts, questions_hash por fase, tiempo consumido e intervalos) y lock exclusivo
results/logs/<run>.f1.lock que cubre comprobación, copia y ejecución (publish.py
no exporta results/logs/: línea 58 del MANIFEST). --session es obligatorio y lo
da el operador (id de la sesión de servidor del manifiesto); --resume y
--retry-pass exigen la misma sesión: un run no mezcla sesiones.

--retry-pass es una pasada standalone sobre un run ya ejecutado: exige el
marcador de primera pasada completa (todas las fases con todos los casos
intentados, respuesta o error — si faltan, un --retry-errors los ejecutaría por
primera vez), copia una vez results/<run>/ a results/<run>_pass1/ y ejecuta UNA
invocación --retry-errors por cada fase con errores, sin --limit. Los errores
del reintento no provocan relanzamiento: ante un timeout se comprueba health y,
si no responde, se para; los casos que sigan con error se quedan así. El estado
registra `retry_scheduled` (selección previa) y `retry_attempted` (solo los
cids cuyo registro cambió tras la invocación — respuesta, error distinto u otro
ms); los restantes quedan en `retry_not_attempted`.

Ciclo de vida del hijo: ante excepción o KeyboardInterrupt del supervisor,
run_phase_command termina al hijo y espera su fin (terminate → wait 10 s →
kill → wait) antes de liberar el lock y guardar el estado.

--dry-run imprime los comandos exactos del modo pedido (primera pasada, o solo
reintento con sus precondiciones) sin ejecutarlos.
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import store
from .battery import EXTRA_PHASES, PHASES, load_phase, questions_hash
from .redact import redact_options

FASES11 = PHASES + EXTRA_PHASES + ["adv4", "adv5"]
FASES_RX = ["papers32", "adv3"]
# pares motor+interposer de cada Spark, vistos por túnel desde esta máquina
H81 = ("http://127.0.0.1:18010/health", "http://127.0.0.1:18011/health")
H80 = ("http://127.0.0.1:18020/health", "http://127.0.0.1:18021/health")
VENV_LLM = ".venv-llm/bin/python"

MAX_ERR_FASE = 3
MAX_ERR_RUN = 10
HEALTH_ESPERA_S = 120
HEALTH_PASO_S = 10
POLL_S = 1.0


def _extra(samples="auto"):
    """extra congelado de P/S1/R/X/Rot1 (el servidor ignora `format`: lo deriva)."""
    return json.dumps({"seed": 42, "samples": samples, "auto_threshold": 0.1,
                       "auto_max": 4, "steps": 1, "think": 0, "format": "lines"},
                      separators=(",", ":"))


def _opts_p(url="http://127.0.0.1:18011", samples="auto", rotate=0):
    opts = {"url": url, "path": "/v1/systemone", "model": "dgemma", "timeout": "120",
            "capture_raw": "true", "extra": _extra(samples)}
    if rotate:
        opts["rotate_choice"] = str(rotate)
    return opts


def _opts_l(mode):
    # L′ (revisión 4): sin extra_body — decodificación por defecto del servidor
    return {"provider": "openai", "base_url": "http://127.0.0.1:18020/v1",
            "api_key": "none", "model": "dgemma", "structured": "false",
            "mode": mode, "max_tokens": "2048", "timeout": "120",
            "case_timeout": "300", "capture_raw": "true"}


def _opts_l_viejo(mode):
    # L de R3 (no ejecutable): llevaba extra_body={"temperature":0,"seed":101}
    return {**_opts_l(mode),
            "extra_body": json.dumps({"temperature": 0, "seed": 101}, separators=(",", ":"))}


_MOTIVO_L = "revisión 4: celdas L sustituidas por L′ (sin extra_body)"
_MOTIVO_L1 = ("revisión 5: celdas L′ sustituidas por L″ (el motor saca prefijo "
              "'thought\\n' sin --reasoning-parser gemma4)")

CELLS = {
    "P": {"run": "dgemma_26b_a4b_nvfp4", "adapter": "systemone_http",
          "opts": _opts_p(), "phases": FASES11, "health": H81, "cap_min": 60},
    "S1": {"run": "dgemma_26b_a4b_nvfp4_s1", "adapter": "systemone_http",
           "opts": _opts_p(samples=1), "phases": FASES11, "health": H81, "cap_min": 45},
    "R": {"run": "dgemma_26b_a4b_nvfp4_rep", "adapter": "systemone_http",
          "opts": _opts_p(), "phases": FASES_RX, "health": H81, "cap_min": 20},
    "X": {"run": "dgemma_26b_a4b_nvfp4_x80", "adapter": "systemone_http",
          "opts": _opts_p(url="http://127.0.0.1:18021"), "phases": FASES_RX,
          "health": H80, "cap_min": 20},
    "Rot1": {"run": "dgemma_26b_a4b_nvfp4_rot1", "adapter": "systemone_http",
             "opts": _opts_p(url="http://127.0.0.1:18021", rotate=1),
             "phases": FASES11, "health": H80, "cap_min": 60},
    "Lp": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob", "adapter": "llm",
           "opts": _opts_l_viejo("probabilities"), "phases": FASES11,
           "health": H80, "cap_min": 90, "python": VENV_LLM,
           "executable": False, "motivo": _MOTIVO_L},
    "Ld": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc", "adapter": "llm",
           "opts": _opts_l_viejo("discrete"), "phases": FASES11,
           "health": H80, "cap_min": 60, "python": VENV_LLM,
           "executable": False, "motivo": _MOTIVO_L},
    "Lp2": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_dflt", "adapter": "llm",
            "opts": _opts_l("probabilities"), "phases": FASES11,
            "health": H80, "cap_min": 90, "python": VENV_LLM,
            "executable": False, "motivo": _MOTIVO_L1},
    "Lr2": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_dflt_rep", "adapter": "llm",
            "opts": _opts_l("probabilities"), "phases": FASES_RX,
            "health": H80, "cap_min": 30, "python": VENV_LLM,
            "executable": False, "motivo": _MOTIVO_L1},
    "Ld2": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc_dflt", "adapter": "llm",
            "opts": _opts_l("discrete"), "phases": FASES11,
            "health": H80, "cap_min": 60, "python": VENV_LLM,
            "executable": False, "motivo": _MOTIVO_L1},
    "Lp3": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp", "adapter": "llm",
            "opts": _opts_l("probabilities"), "phases": FASES11,
            "health": H80, "cap_min": 90, "python": VENV_LLM},
    "Lr3": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp_rep", "adapter": "llm",
            "opts": _opts_l("probabilities"), "phases": FASES_RX,
            "health": H80, "cap_min": 30, "python": VENV_LLM},
    "Ld3": {"run": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc_rp", "adapter": "llm",
            "opts": _opts_l("discrete"), "phases": FASES11,
            "health": H80, "cap_min": 60, "python": VENV_LLM},
}


def command(cell, phase, python=None, retry=False):
    """La invocación exacta de jevbench.run para una fase de la celda."""
    py = python or cell.get("python") or sys.executable
    cmd = [py, "-m", "jevbench.run", cell["adapter"], "--run", cell["run"],
           "--phases", phase]
    if retry:
        cmd.append("--retry-errors")
    for k, v in cell["opts"].items():
        cmd += ["--opt", f"{k}={v}"]
    return cmd


# ------------------------------------------------------------------ estado
def state_path(run):
    return store.ROOT / "logs" / f"{run}.f1_state.json"


def lock_path(run):
    return store.ROOT / "logs" / f"{run}.f1.lock"


def load_state(run):
    p = state_path(run)
    return json.loads(p.read_text()) if p.exists() else None


def save_state(run, st):
    state_path(run).write_text(json.dumps(st, ensure_ascii=False, indent=1))


def acquire_lock(run):
    """Lock exclusivo results/logs/<run>.f1.lock; devuelve el fd o lanza."""
    p = lock_path(run)
    p.parent.mkdir(parents=True, exist_ok=True)
    return os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)


def release_lock(run, fd):
    os.close(fd)
    lock_path(run).unlink(missing_ok=True)


def expected_ids(phase):
    _, cases = load_phase(phase)
    return {c.id for c in cases}


def phase_complete(path, phase):
    """La fase está terminada si todos sus casos fueron intentados
    (respuesta o error, sin ausentes)."""
    if not path.exists():
        return False
    doc = json.loads(path.read_text())
    return expected_ids(phase) <= set(doc.get("cases") or {})


def phase_errors(path):
    """[(cid, mensaje)] de los casos con error de un JSON de fase."""
    if not path.exists():
        return []
    doc = json.loads(path.read_text())
    return [(cid, r.get("error", "")) for cid, r in (doc.get("cases") or {}).items()
            if "error" in r]


def run_errors(run_dir):
    return sum(len(phase_errors(p)) for p in sorted(run_dir.glob("*.json")))


def check_frozen(cell, run_dir):
    """Problemas de coherencia de un run ya escrito: adapter y questions_hash de
    cada fase contra la batería, meta.opts idénticas a las congeladas (ya
    redactadas como hace run.py) y, en systemone_http, el extra congelado en el
    raw.request de cada caso respondido."""
    want = redact_options(dict(cell["opts"]))
    extra = json.loads(cell["opts"]["extra"]) if cell["adapter"] == "systemone_http" else None
    probs = []
    for p in sorted(run_dir.glob("*.json")):
        if p.stem not in cell["phases"]:
            probs.append(f"{p.stem}: fase ajena a la celda")
            continue
        doc = json.loads(p.read_text())
        meta = doc.get("meta") or {}
        if meta.get("opts") != want:
            probs.append(f"{p.stem}: meta.opts distintas de las congeladas")
        if meta.get("adapter") != cell["adapter"]:
            probs.append(f"{p.stem}: adapter {meta.get('adapter')!r} ≠ {cell['adapter']!r}")
        try:
            qs, _ = load_phase(p.stem)
            if meta.get("questions_hash") != questions_hash(qs):
                probs.append(f"{p.stem}: questions_hash distinto de la batería")
        except (ValueError, SystemExit) as e:
            probs.append(f"{p.stem}: {e}")
        if extra is None:
            continue
        for cid, rec in (doc.get("cases") or {}).items():
            if "error" in rec:
                continue
            req = (rec.get("raw") or {}).get("request") or {}
            if {k: req.get(k) for k in extra} != extra:
                probs.append(f"{p.stem}/{cid}: raw.request sin el extra congelado")
    return probs


# ------------------------------------------------------------------ salud/hijo
def health_ok(url, timeout=5):
    """El endpoint responde HTTP (cualquier estado <500 vale: está vivo)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def wait_health(urls, deadline, now=time.monotonic, sleep=time.sleep):
    """Los dos /health deben responder dentro de HEALTH_ESPERA_S (reintentos cada
    HEALTH_PASO_S) y antes del tope de la celda. Devuelve (todo_ok, estados)."""
    end = min(deadline, now() + HEALTH_ESPERA_S)
    while True:
        states = {u: health_ok(u) for u in urls}
        if all(states.values()):
            return True, states
        if now() >= end:
            return False, states
        sleep(HEALTH_PASO_S)


def _wait_or_kill(proc):
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_phase_command(cmd, log_path, deadline):
    """Lanza la invocación volcando al log y espera a que termine, cortándola en
    el tope de la celda. En cualquier salida (incluida excepción o
    KeyboardInterrupt del supervisor) termina al hijo y espera su fin antes de
    propagar. Devuelve (rc, 'tope'|None)."""
    with open(log_path, "a") as lf:
        lf.write(f"\n$ {shlex.join(cmd)}\n")
        lf.flush()
        proc = subprocess.Popen(cmd, cwd=store.ROOT.parent, stdout=lf,
                                stderr=subprocess.STDOUT)
        try:
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    proc.terminate()
                    _wait_or_kill(proc)
                    return proc.returncode, "tope"
                time.sleep(POLL_S)
            return proc.returncode, None
        finally:
            if proc.poll() is None:
                proc.terminate()
                _wait_or_kill(proc)


def run_cell(cell, session=None, python=None, resume=False, retry_pass=False,
             dry_run=False, printer=print):
    """Ejecuta la celda y devuelve el código de salida (0 = sin paradas)."""
    run = cell["run"]
    run_dir = store.ROOT / run
    if not cell.get("executable", True):
        printer(f"ERROR: celda {run} no ejecutable ({cell.get('motivo', '')})")
        return 1
    if dry_run:
        if retry_pass:
            printer("# solo pasada de reintento: exige primera pasada completa,")
            printer("# la misma --session y que no exista <run>_pass1")
            printer(f"# cp -a {run_dir} {str(run_dir) + '_pass1'}")
            for ph in cell["phases"]:
                printer(shlex.join(command(cell, ph, python, retry=True))
                        + "   # solo si la fase tiene errores")
        else:
            for ph in cell["phases"]:
                printer(shlex.join(command(cell, ph, python))
                        + " --limit 1   # una vez por caso no escrito")
        return 0
    if not session:
        printer("ERROR: --session <id> es obligatorio (id de la sesión del manifiesto)")
        return 1
    try:
        fd = acquire_lock(run)
    except FileExistsError:
        printer(f"ERROR: {lock_path(run)} existe: otro proceso tiene el run")
        return 1
    try:
        return _run_locked(cell, session, python, resume, retry_pass, printer)
    finally:
        release_lock(run, fd)


def _run_locked(cell, session, python, resume, retry_pass, printer):
    run = cell["run"]
    run_dir = store.ROOT / run
    log_path = store.ROOT / "logs" / f"{run}.log"
    st = load_state(run)

    if retry_pass:
        probs = []
        if not run_dir.is_dir():
            probs.append("run inexistente")
        if st is None:
            probs.append("sin estado f1: no consta primera pasada")
        elif st.get("session") != session:
            probs.append(f"sesión distinta ({st.get('session')} ≠ {session})")
        elif not st.get("pass1_complete"):
            probs.append("primera pasada incompleta (falta el marcador)")
        if run_dir.is_dir():
            probs += check_frozen(cell, run_dir)
            for ph in cell["phases"]:
                if not phase_complete(run_dir / f"{ph}.json", ph):
                    probs.append(f"{ph}: casos sin intentar (no sería reintento)")
        dst = store.ROOT / (run + "_pass1")
        if dst.exists():
            probs.append(f"{dst} ya existe: la pasada de reintento es única")
        if probs:
            printer("ERROR: --retry-pass no puede continuar:")
            printer("\n".join("  " + p for p in probs))
            return 1
    elif run_dir.exists() or st is not None:
        if not resume:
            printer(f"ERROR: {run_dir} o su estado ya existen; usa --resume para "
                    f"continuarlo o --retry-pass para la pasada de reintento")
            return 1
        if st is None:
            printer("ERROR: falta results/logs/" + run + ".f1_state.json: "
                    "no se puede reanudar sin sesión registrada")
            return 1
        if st.get("session") != session:
            printer(f"ERROR: sesión distinta ({st.get('session')} ≠ {session}): "
                    "un run no mezcla sesiones")
            return 1
        probs = check_frozen(cell, run_dir)
        if probs:
            printer("ERROR: el run existente no coincide con la configuración congelada:")
            printer("\n".join("  " + p for p in probs))
            return 1
    else:
        st = {"session": session, "adapter": cell["adapter"],
              "opts": dict(cell["opts"]), "phases": {}, "elapsed_s": 0.0,
              "intervals": [], "pass1_complete": False}

    # tope global persistente: el tiempo consumido se acumula entre invocaciones
    remaining = cell["cap_min"] * 60 - (st.get("elapsed_s") or 0.0)
    deadline = time.monotonic() + max(0.0, remaining)
    t0m, t0e = time.monotonic(), time.time()
    stop = None

    def estado():
        n_files = len(list(run_dir.glob("*.json"))) if run_dir.is_dir() else 0
        return f"{run_errors(run_dir)} errores acumulados en el run; fases escritas: {n_files}"

    def ejecutar(ph, retry):
        """Una fase: caso a caso en la primera pasada (--limit 1 por invocación;
        las reglas se evalúan antes de cada caso → cero casos extra), una única
        invocación --retry-errors en el reintento (sin relanzamiento)."""
        nonlocal stop
        p = run_dir / f"{ph}.json"
        t0 = time.time()
        if retry:
            # retry_scheduled: selección previa; retry_attempted: solo cids
            # cuyo registro en el JSON cambió tras la invocación (respuesta,
            # error distinto u otro ms); los restantes quedan no intentados
            pend = sorted(cid for cid, _ in phase_errors(p))
            antes = {}
            if p.exists():
                casos = (json.loads(p.read_text()).get("cases") or {})
                antes = {cid: casos.get(cid) for cid in pend}
            st.setdefault("retry_scheduled", {})[ph] = pend
            printer(f"--- {ph} (reintento único de {len(pend)} caso(s)) ---")
            rc, sig = run_phase_command(command(cell, ph, python, retry=True),
                                        log_path, deadline)
            despues = {}
            if p.exists():
                casos = (json.loads(p.read_text()).get("cases") or {})
                despues = {cid: casos.get(cid) for cid in pend}
            att = [cid for cid in pend if antes.get(cid) != despues.get(cid)]
            st.setdefault("retry_attempted", {})[ph] = att
            rest = [cid for cid in pend if cid not in set(att)]
            if rest:
                st.setdefault("retry_not_attempted", {})[ph] = rest
                printer(f"{ph}: reintentados {len(att)}/{len(pend)}; "
                        f"sin intento acreditado: {rest}")
            if sig == "tope":
                stop = f"tope global de la celda ({cell['cap_min']} min acumulados)"
            elif rc != 0:
                stop = f"{ph}: jevbench.run terminó con rc={rc}"
            else:
                timeouts = [e for e in phase_errors(p) if "timeout" in e[1].lower()]
                if timeouts:
                    printer(f"{ph}: timeout en el reintento; probando /health…")
                    ok, states = wait_health(cell["health"], deadline)
                    if not ok:
                        stop = (f"health no responde tras {HEALTH_ESPERA_S} s: "
                                f"{json.dumps(states)}")
        else:
            vistos_timeout = set()
            n_ant = -1
            while not stop:
                errs = phase_errors(p)
                if len(errs) >= MAX_ERR_FASE:
                    stop = f"{ph}: {MAX_ERR_FASE} errores en una fase"
                    break
                if run_errors(run_dir) >= MAX_ERR_RUN:
                    stop = f"{MAX_ERR_RUN} errores acumulados en el run"
                    break
                if phase_complete(p, ph):
                    break
                if time.monotonic() >= deadline:
                    stop = (f"tope global de la celda "
                            f"({cell['cap_min']} min acumulados)")
                    break
                n = len((json.loads(p.read_text()).get("cases") or {})
                        if p.exists() else {})
                if n == n_ant:
                    stop = f"{ph}: la última invocación no escribió ningún caso"
                    break
                n_ant = n
                printer(f"--- {ph} caso {n + 1} ---")
                rc, sig = run_phase_command(
                    command(cell, ph, python) + ["--limit", "1"],
                    log_path, deadline)
                if sig == "tope":
                    stop = (f"tope global de la celda "
                            f"({cell['cap_min']} min acumulados)")
                    break
                if rc != 0:
                    stop = f"{ph}: jevbench.run terminó con rc={rc}"
                    break
                nuevos_to = [e for e in phase_errors(p)
                             if "timeout" in e[1].lower() and e[0] not in vistos_timeout]
                if nuevos_to:
                    vistos_timeout.update(cid for cid, _ in nuevos_to)
                    printer(f"{ph}: error de timeout; probando /health…")
                    ok, states = wait_health(cell["health"], deadline)
                    if not ok:
                        stop = (f"health no responde tras {HEALTH_ESPERA_S} s: "
                                f"{json.dumps(states)}")
                    else:
                        printer(f"{ph}: health ok; continúo con el siguiente caso "
                                "(el del timeout queda para el reintento)")
        meta = {}
        if p.exists():
            meta = (json.loads(p.read_text()).get("meta") or {})
        pst = st["phases"].setdefault(ph, {"intervals": []})
        pst["intervals"].append([t0, time.time()])
        if meta.get("questions_hash"):
            pst["questions_hash"] = meta["questions_hash"]
        printer(f"{ph}: {len(phase_errors(p))} errores en la fase, "
                f"{run_errors(run_dir)} en el run")

    try:
        if remaining <= 0:
            stop = f"tope global de la celda ({cell['cap_min']} min) ya consumido"
        elif retry_pass:
            dst = store.ROOT / (run + "_pass1")
            shutil.copytree(run_dir, dst)
            printer(f"copia de la 1.ª pasada → {dst}")
            for ph in cell["phases"]:
                if phase_errors(run_dir / f"{ph}.json"):
                    ejecutar(ph, retry=True)
                    if stop:
                        break
        else:
            for ph in cell["phases"]:
                ejecutar(ph, retry=False)
                if stop:
                    break
            if not stop:
                pendientes = [ph for ph in cell["phases"]
                              if not phase_complete(run_dir / f"{ph}.json", ph)]
                if pendientes:
                    stop = f"fases sin cubrir todos los casos: {pendientes}"
                else:
                    st["pass1_complete"] = True
                    printer("primera pasada completa: todos los casos intentados")
    finally:
        st["elapsed_s"] = (st.get("elapsed_s") or 0.0) + (time.monotonic() - t0m)
        st.setdefault("intervals", []).append([t0e, time.time()])
        save_state(run, st)

    if stop:
        printer(f"PARADA: {stop}")
        printer(f"estado: {estado()}")
        return 2
    printer(f"celda terminada: {estado()}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("celda", choices=sorted(CELLS))
    ap.add_argument("--session", help="id de la sesión de servidor del manifiesto "
                    "(obligatorio para ejecutar)")
    ap.add_argument("--retry-pass", action="store_true",
                    help="pasada única de reintento sobre una primera pasada completa")
    ap.add_argument("--resume", action="store_true",
                    help="reanudar un run existente (misma --session y opts congeladas)")
    ap.add_argument("--dry-run", action="store_true",
                    help="imprimir los comandos exactos del modo pedido, sin ejecutar")
    ap.add_argument("--python",
                    help="intérprete para jevbench.run (por defecto el de la celda: "
                         ".venv-llm en L′, sys.executable en el resto)")
    args = ap.parse_args()
    return run_cell(CELLS[args.celda], session=args.session, python=args.python,
                    resume=args.resume, retry_pass=args.retry_pass,
                    dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
