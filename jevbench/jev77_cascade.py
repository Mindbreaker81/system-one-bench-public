"""JEV-77 hybrid cascade runner: M-D0 (MedGemma-27B local) -> Jev audit
(medgemma_jev77 §5.3). Wraps jevbench.cascade.run_phase with the
pre-registered network quota (≤800 API intentos de red) y el deadline
efectivo (≤3 h wall de la cascada ∩ el reloj global de 40 h del encargo
— la cascada corre DENTRO de A6, R36 §4), ambos durables en el fichero
de estado.

Cada intento HTTP que abre el adaptador de Jev consume cupo (urllib
interceptado en el proxy): se acuerda ANTES de abrir la petición y el
socket lleva el remanente como timeout, para que ni un timeout interno
de la librería ni un retry puedan pasar del tope; las esperas internas
(backoff de retry/pause) también quedan acotadas por el deadline. Con
el cupo o el deadline agotados no se abre nada: se registra la parada
durable y lo pendiente queda NO EVALUABLE (nunca un «completado»
silencioso). El revisor congelado (proveedor + versión resuelta) se
persiste en el estado; si una reanudación resuelve otra versión la
cascada para y conserva lo revisado.

  python -m jevbench.jev77_cascade --provider typesafe

Offline en los tests (adaptador falso); en producción lee TYPESAFE_API_KEY
u OPENROUTER_API_KEY de .env como el resto del harness.
"""
import argparse
import datetime as dt
import json
import platform
import time
import urllib.request

from . import adapters, cascade, store
from .battery import load_phase

CAP_REQUESTS = 800
WALL_S = 3 * 3600
STATE_FILE = "jev77_cascade.json"
PHASES_77 = ["triage_es", "triage_en", "adv1", "adv2", "adv3", "adv4",
             "adv5", "papers32", "triage_ext_es", "triage_ext_en", "ood"]
PREFIX_77 = "medgemma_27b_jev77_jevrev"
JEV77_STATE_FILE = "qwen_session_jev77.json"
JEV77_GLOBAL_S = 40 * 3600
JEV77_MANIFEST_FILE = "qwen_manifest_jev77.json"


class QuotaExhausted(BaseException):
    """Cupo de red agotado: corta la fase igual que un apagón — no se
    confunde con un fallo transitorio del caso (que sí se reintenta)."""


class DeadlineExceeded(BaseException):
    """Deadline efectivo de la cascada agotado (3 h propias ∩ 40 h del
    encargo). Idem."""


def _state_path():
    return store.ROOT / "logs" / STATE_FILE


def _global_remaining(now=time.time):
    """Remanente del reloj global de evaluación JEV-77 (§8.2: 40 h wall
    desde el inicio A6 registrado en el estado durable del encargo):
    la cascada corre dentro del encargo — agotado el global no se abre
    nada (R36 §4). None si el reloj del encargo aún no arrancó."""
    try:
        st = json.loads((store.ROOT / "logs" / JEV77_STATE_FILE)
                        .read_text())
    except (OSError, ValueError):
        return None
    wt0 = st.get("wall_t0")
    if not isinstance(wt0, (int, float)):
        return None
    return max(0.0, JEV77_GLOBAL_S - (now() - wt0))


def _encargo_files():
    """Estado A6 + manifiesto congelado del encargo JEV-77, leídos y
    verificados ANTES de construir/abrir el revisor (R38 §3, §5):
    ausencia, JSON corrupto, falta de wall_t0/sesión, manifiesto sin
    sha o políticas de cascada divergentes de las efectivas son
    SystemExit — nunca se ejecuta sin encargo acreditado."""
    try:
        st = json.loads((store.ROOT / "logs" / JEV77_STATE_FILE)
                        .read_text())
    except (OSError, ValueError) as e:
        raise SystemExit(f"estado del encargo ausente o ilegible ({e})")
    if not isinstance(st.get("wall_t0"), (int, float)) \
            or not st.get("session"):
        raise SystemExit("estado del encargo sin inicio A6 válido "
                         "(sesión y wall_t0 obligatorios)")
    try:
        man = json.loads((store.ROOT / "logs" / JEV77_MANIFEST_FILE)
                         .read_text())
    except (OSError, ValueError) as e:
        raise SystemExit(f"manifiesto jev77 ausente o ilegible ({e})")
    if not man.get("manifest_sha256"):
        raise SystemExit("manifiesto jev77 sin manifest_sha256")
    # integridad: el sha declarado debe reproducirse del contenido —
    # un cuerpo alterado con el sha viejo es un manifiesto distinto sin
    # enmienda verificable (R39 §1)
    from . import qwen_session as _qs
    _qs._set_profile("jev77")
    if man["manifest_sha256"] != _qs._manifest_content_sha(man):
        raise SystemExit("manifiesto jev77 alterado: manifest_sha256 "
                         "declarado no cuadra con el contenido")
    # compatibilidad con el plan vigente: el fichero debe ser el
    # manifiesto que produce el ejecutable actual — cualquier otro
    # (incluso con sha consistente) exige recongelar el encargo
    if man["manifest_sha256"] != _qs._plan_manifest()["manifest_sha256"]:
        raise SystemExit("manifiesto jev77 != el del plan vigente: sin "
                         "enmienda autorizada y verificable no se "
                         "ejecuta ni se reanuda la cascada")
    # los límites EFECTIVOS del wrapper deben ser los congelados en el
    # manifiesto — una divergencia invalida la ejecución (R38 §5)
    caps = (man.get("policies") or {}).get("cascade") or {}
    for k, v in {"requests": CAP_REQUESTS, "wall_s": WALL_S,
                 "raw": f"{PREFIX_77}_raw",
                 "audit": f"{PREFIX_77}_audit",
                 "reviewer": _qs.JEV77_CASCADE_REVIEWER}.items():
        if caps.get(k) != v:
            raise SystemExit(
                f"política de cascada del manifiesto diverge de la "
                f"vigente: {k} {caps.get(k)!r} != {v!r}")
    return st, man


def _default_d1(man):
    """El D1 de la cascada es el run que el supervisor generó para la
    celda M-D0 del manifiesto congelado (R38 §8) — nunca un literal
    aparte que pueda divergir del perfil."""
    run = ((man.get("cells") or {}).get("MD0") or {}).get("run")
    if not run:
        raise SystemExit("manifiesto jev77 sin run de la celda M-D0")
    return run


def _md0_evaluable(d1, phases, man=None):
    """¿Es M-D0 EVALUABLE según la auditoría de celdas del supervisor
    (puertas, raw, procedencia, regla de tokens — R39 §4) Y ligado al
    manifiesto vigente? La evaluabilidad no basta: el doc y cada caso
    deben registrar el sha del manifiesto actual o el de un eslabón
    autorizado de su cadena de enmiendas — un M-D0 internamente válido
    de OTRO encargo no autoriza la cascada (R40 §3)."""
    from . import qwen_session as _qs
    _qs._set_profile("jev77")
    cell = {**_qs.CELLS_77["MD0"], "phases": list(phases)}
    try:
        rep = _qs._audit_cell("MD0", cell)
    except SystemExit as e:
        return False, f"auditoría no concluye: {e}"
    if not rep.get("evaluable"):
        return False, rep.get("note")
    if man is None:
        try:
            man = json.loads((store.ROOT / "logs" / JEV77_MANIFEST_FILE)
                             .read_text())
        except (OSError, ValueError) as e:
            return False, f"manifiesto ilegible para procedencia ({e})"
    cur = man.get("manifest_sha256")
    if not cur:
        return False, "manifiesto sin sha: imposible acreditar M-D0"
    for ph in phases:
        doc = store.load(d1, ph)
        diag = (doc.get("meta") or {}).get("diag") or {}
        allowed, origin, merr = _qs._manifest_allowed(diag)
        if merr or not allowed or cur not in allowed:
            return False, (f"{ph}: procedencia de manifiesto ajena o "
                           "ausente en M-D0")
        _, cases = load_phase(ph)
        for c in cases:
            rec = (doc.get("cases") or {}).get(c.id) or {}
            if rec.get("manifest_sha256", origin) not in allowed:
                return False, (f"{ph}/{c.id}: manifest_sha256 ajeno al "
                               "encargo vigente")
    return True, None


def _check_d1(d1, man, phases):
    """D1 válido = EXACTAMENTE la celda M-D0 del manifiesto congelado,
    presente, completa en su ámbito y evaluable según su auditoría —
    todo ANTES de abrir red (R38 §8, R39 §4)."""
    frozen = _default_d1(man)
    if d1 != frozen:
        raise SystemExit(f"D1 {d1!r} != la celda M-D0 congelada "
                         f"{frozen!r} — la cascada solo audita el run "
                         "del encargo")
    for ph in phases:
        _, cases = load_phase(ph)
        doc = store.load(d1, ph)
        if doc is None:
            raise SystemExit(f"{d1}: fase {ph} ausente — la cascada "
                             "audita el run M-D0 del encargo")
        recs = doc.get("cases") or {}
        missing = [c.id for c in cases
                   if "answers" not in (recs.get(c.id) or {})]
        if missing:
            raise SystemExit(f"{d1}: {ph} sin respuestas en "
                             f"{len(missing)}/{len(cases)} casos "
                             f"({missing[0]}…) — M-D0 incompleto")
    ok, note = _md0_evaluable(d1, phases, man)
    if not ok:
        raise SystemExit(f"M-D0 {d1} no evaluable según la auditoría "
                         f"del encargo ({note})")


# Sondeo A4: mismo formato wire que las preguntas noul de la batería
# (`instructions` obligatorio; noul no lleva `criteria`).
A4_PROBE_QS = {"a4_probe": {"type": "noul",
                            "instructions": "Is this text a version probe?"}}


def freeze_reviewer(budget=None, reviewer=None, adapter="jev",
                    provider="openrouter", opts=None, printer=print):
    """Paso A4 explícito (§5.3): resuelve y congela la identidad del
    revisor — adaptador/proveedor/modelo y versión resuelta — en el
    presupuesto durable ANTES de A6. Si el meta no informa aún versión,
    hace UNA petición de sondeo para resolverla; sin este registro
    `run` no abre la red de evaluación (R39 §2)."""
    budget = budget or Budget()
    if reviewer is None:
        o = dict(opts or {})
        if adapter == "jev":
            o.setdefault("provider", provider)
        reviewer = adapters.get(adapter)(**o)
    meta = reviewer.meta()
    if meta.get("resolved") is None:
        reviewer.decide("a4-version-probe", A4_PROBE_QS)
        meta = reviewer.meta()
    if meta.get("resolved") is None:
        printer("ERROR: el revisor no informó versión resuelta")
        return 1
    rv = {**meta, "adapter": adapter,
          "frozen_wall": budget._now()}
    budget.st["reviewer"] = rv
    budget._save()
    printer(f"revisor congelado (A4): adapter={rv['adapter']} "
            f"provider={rv.get('provider')} model={rv.get('model')} "
            f"resolved={rv['resolved']}")
    return 0


def _encargo_meta():
    """Procedencia del encargo a persistir en raw/fusión de la cascada:
    host, sesión vigente, sha del manifiesto congelado y los cupos."""
    meta = {"host": platform.node(),
            "cascade_caps": {"requests": CAP_REQUESTS, "wall_s": WALL_S}}
    try:
        st = json.loads((store.ROOT / "logs" / JEV77_STATE_FILE)
                        .read_text())
        meta["session"] = st.get("session")
    except (OSError, ValueError):
        pass
    try:
        man = json.loads((store.ROOT / "logs" / JEV77_MANIFEST_FILE)
                         .read_text())
        meta["manifest_sha256"] = man.get("manifest_sha256")
    except (OSError, ValueError):
        pass
    return meta


class Budget:
    """Cupo durable de intentos de red + deadline efectivo (3 h propias
    ∩ global del encargo). El gasto se persiste ANTES de abrir cada
    intento: un apagón no regala peticiones, como en qwen_session."""

    def __init__(self, now=time.time, path=None, global_remaining=None):
        self._now, self._path = now, path or _state_path()
        self._global = global_remaining
        self.st = (json.loads(self._path.read_text())
                   if self._path.exists()
                   else {"requests": 0, "started_wall": None})

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self.st, ensure_ascii=False, indent=1))

    def start(self):
        """Marca operativa del arranque de la cascada: el reloj de las
        3 h nace aquí (no en la primera petición, R36 §4)."""
        if self.st["started_wall"] is None:
            self.st["started_wall"] = self._now()
            self._save()

    def deadline_remaining(self):
        rem = (float(WALL_S) if self.st["started_wall"] is None
               else WALL_S - (self._now() - self.st["started_wall"]))
        g = self._global() if self._global is not None else None
        return max(0.0, min(rem, g) if g is not None else rem)

    def charge(self):
        """Reserva un intento de red (persistido); lanza QuotaExhausted
        o DeadlineExceeded sin abrir nada si el tope ya llegó."""
        self.start()
        if self.deadline_remaining() <= 0:
            raise DeadlineExceeded(
                "deadline de la cascada agotado (3 h propias o reloj "
                "global del encargo)")
        if self.st["requests"] + 1 > CAP_REQUESTS:
            raise QuotaExhausted(
                f"cupo de {CAP_REQUESTS} intentos agotado")
        self.st["requests"] += 1
        self._save()

    def stop(self, reason, phase=None):
        """Parada persistida: queda en el registro durable del encargo
        para que el análisis la publique como tal (R36 §7)."""
        self.st["stopped"] = {"reason": reason, "phase": phase,
                              "wall_ts": self._now(),
                              "ts": dt.datetime.now().isoformat(
                                  timespec="seconds")}
        self._save()


class CountingAdapter:
    """Proxy del adaptador real: cuenta/persiste cada intento HTTP
    (`urllib.request.urlopen`) que abra el interior, acota el timeout
    del socket al remanente del deadline efectivo (3 h ∩ global) y
    acota sus esperas internas (backoff de retry/pause): ninguna
    petición puede pasar del tope, ni abierta ni durmiendo (R36 §4)."""

    def __init__(self, inner, budget, urlopen=None, sleep=None):
        self._inner, self._budget = inner, budget
        self._open_real = urlopen or urllib.request.urlopen
        self._sleep_real = sleep or time.sleep

    def meta(self):
        return self._inner.meta()

    def decide(self, state, questions):
        real_open, real_sleep, budget = (self._open_real,
                                         self._sleep_real, self._budget)

        def _counted(*a, **kw):
            rem = budget.deadline_remaining()
            if rem <= 0:
                raise DeadlineExceeded(
                    "deadline agotado antes de abrir la petición")
            budget.charge()
            t = kw.get("timeout")
            kw["timeout"] = rem if t is None else min(t, rem)
            return real_open(*a, **kw)

        def _bounded_sleep(s):
            rem = budget.deadline_remaining()
            if rem <= 0:
                raise DeadlineExceeded(
                    "deadline agotado durante la espera interna")
            real_sleep(min(float(s), rem))
            if budget.deadline_remaining() <= 0:
                raise DeadlineExceeded(
                    "deadline agotado tras la espera interna")

        old_open, old_sleep = urllib.request.urlopen, time.sleep
        urllib.request.urlopen = _counted
        time.sleep = _bounded_sleep
        try:
            return self._inner.decide(state, questions)
        finally:
            urllib.request.urlopen = old_open
            time.sleep = old_sleep


def run(d1=None, prefix=PREFIX_77, control="", adapter="jev",
        provider="openrouter", opts=None, phases=PHASES_77,
        reviewer=None, budget=None, urlopen=None, now=time.time,
        global_remaining=_global_remaining, printer=print):
    """Ejecuta la cascada jev77 con el cupo durable. Las paradas por
    cupo/deadline quedan registradas en el fichero de estado y el
    trabajo pendiente es NO EVALUABLE — nunca se trata como completado.
    Antes de abrir red exige el encargo acreditado (estado A6 con
    sesión+wall_t0, manifiesto congelado cuyas políticas de cascada son
    las efectivas, y M-D0 completo); sin él es parada de configuración.
    Devuelve 0 completada, 2 parada registrada, 1 error de
    configuración."""
    budget = budget or Budget(now=now)
    if budget._global is None and global_remaining is not None:
        budget._global = global_remaining
    # el reloj de la cascada nace en el arranque del encargo, no en la
    # primera petición (R36 §4)
    budget.start()
    try:
        _encargo_st, man = _encargo_files()
        d1 = d1 or _default_d1(man)
        _check_d1(d1, man, phases)
    except SystemExit as e:
        budget.stop(f"configuración: {e}")
        printer(f"PARADA cascada: {e} — no se abre red")
        return 1
    extra = _encargo_meta()
    if reviewer is None:
        o = dict(opts or {})
        if adapter == "jev":
            o.setdefault("provider", provider)
        reviewer = CountingAdapter(adapters.get(adapter)(**o), budget,
                                   urlopen=urlopen)
    # la versión del revisor debe estar resuelta y congelada ANTES de
    # A6 (paso `freeze`, §5.3): sin registro previo no se abre la red
    # de evaluación — la primera respuesta no fija la versión (R39 §2)
    rv = budget.st.get("reviewer") or {}
    if not rv.get("resolved"):
        budget.stop("configuración: revisor sin resolución A4 congelada "
                    "— ejecuta `jev77_cascade freeze` antes de A6")
        printer("PARADA cascada: revisor sin resolución A4 congelada "
                "— no se abre red de evaluación")
        return 1
    cur_meta = {**reviewer.meta(), "adapter": adapter}
    mrev = ((man.get("policies") or {}).get("cascade") or {}) \
        .get("reviewer") or {}
    for k in ("provider", "model", "adapter"):
        if mrev.get(k) != rv.get(k) or cur_meta.get(k) != rv.get(k):
            budget.stop(f"revisor divergente del contrato: {k} "
                        f"manifiesto {mrev.get(k)!r}, congelado "
                        f"{rv.get(k)!r}, vigente {cur_meta.get(k)!r}")
            printer(f"PARADA cascada: revisor {k} divergente del "
                    "contrato congelado — no se abre red")
            return 1
    # la sesión del encargo queda ligada al presupuesto — el auditor la
    # exige compatible en raw/fusión (R39 §3)
    if budget.st.get("session") != _encargo_st.get("session"):
        if budget.st.get("session") is not None:
            budget.stop(f"sesión del presupuesto "
                        f"{budget.st.get('session')!r} != encargo "
                        f"{_encargo_st.get('session')!r}")
            printer("PARADA cascada: la sesión del presupuesto no es "
                    "la del encargo — no se abre red")
            return 1
        budget.st["session"] = _encargo_st.get("session")
        budget._save()
    for ph in phases:
        if budget.deadline_remaining() <= 0:
            budget.stop("deadline agotado antes de la fase", ph)
            printer(f"PARADA cascada: deadline efectivo agotado — {ph} y "
                    "lo pendiente quedan NO EVALUABLE")
            return 2
        try:
            cascade.run_phase(d1, prefix, reviewer, ph,
                              reviewer=adapter, control=control or None,
                              extra_meta=extra,
                              expected_version=rv.get("resolved"))
        except (QuotaExhausted, DeadlineExceeded) as e:
            budget.stop(f"{type(e).__name__}: {e}", ph)
            printer(f"PARADA cascada: {e} — se conserva lo revisado; "
                    "lo pendiente queda NO EVALUABLE")
            return 2
        except SystemExit as e:
            # integridad de procedencia (meta/versión): parada
            # registrada — lo revisado se conserva
            budget.stop(f"SystemExit: {e}", ph)
            printer(f"PARADA cascada: {e} — lo pendiente queda NO "
                    "EVALUABLE")
            return 2
        res = reviewer.meta().get("resolved")
        if res is not None:
            if rv.get("resolved") is None:
                rv["resolved"] = res
                budget._save()
            elif rv["resolved"] != res:
                budget.stop(f"versión del revisor {rv['resolved']} != "
                            f"{res}", ph)
                printer(f"PARADA cascada: la versión del revisor cambió "
                        f"({rv['resolved']} → {res}) — se conserva lo "
                        "revisado; lo pendiente queda NO EVALUABLE")
                return 2
    printer(f"cascada jev77: {budget.st['requests']}/{CAP_REQUESTS} "
            f"intentos de red — completada")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--d1", default=None,
                    help="run de pasada 1 (defecto: la celda M-D0 del "
                         "manifiesto congelado)")
    ap.add_argument("--freeze", action="store_true",
                    help="paso A4: resuelve y congela la identidad del "
                         "revisor en el presupuesto (antes de A6)")
    ap.add_argument("--prefix", default=PREFIX_77)
    ap.add_argument("--provider", default="openrouter")
    ap.add_argument("--adapter", default="jev")
    ap.add_argument("--control", default="")
    ap.add_argument("--opt", action="append", default=[])
    args = ap.parse_args()
    opts = dict(o.split("=", 1) for o in args.opt)
    if args.freeze:
        return freeze_reviewer(adapter=args.adapter,
                               provider=args.provider, opts=opts)
    return run(d1=args.d1, prefix=args.prefix, control=args.control,
               adapter=args.adapter, provider=args.provider, opts=opts)


if __name__ == "__main__":
    raise SystemExit(main())
