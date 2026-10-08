"""Run a model on the battery. Resumable: cases already answered are skipped.

  python -m jevbench.run jev --run jev_v3
  python -m jevbench.run decider --run decider_2b --opt model=Mapika/decider-2b --opt device=cuda
  python -m jevbench.run anyjev --run anyjev_qwen3_8b --opt model=Qwen/Qwen3-8B --phases triage_es,triage_en
  python -m jevbench.run jev --run smoke --phases ood --limit 1
"""
import argparse
import datetime as dt
import platform
import subprocess
import sys
import time
import traceback

from . import adapters, cost_guard, store
from .battery import EXTRA_PHASES, PHASES, load_phase, missing_abstracts, questions_hash
from .redact import redact_options


def safe_opts(opts):
    """opts as stored in meta; the adapter still receives the original values."""
    return redact_options(opts)


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=store.ROOT.parent).stdout.strip() or None
    except OSError:
        return None


def git_dirty():
    """True si el árbol tiene cambios sin commitear: el meta.git de un run
    ejecutado con código pendiente identifica la base, no el código."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"],
                             capture_output=True, text=True,
                             cwd=store.ROOT.parent).stdout
        return bool(out.strip()) or None
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter", choices=sorted(adapters.REGISTRY))
    ap.add_argument("--run", required=True, help="results/<run>/ directory name")
    ap.add_argument("--phases", default="all")
    ap.add_argument("--opt", action="append", default=[], help="adapter option k=v (repeatable)")
    ap.add_argument("--limit", type=int, help="max cases per phase (smoke tests)")
    ap.add_argument("--retry-errors", action="store_true", help="re-run cases stored with an error")
    ap.add_argument("--max-case-cost", type=float,
                    help="JEV-82 guard: stop before the next case when a recorded case cost exceeds this")
    ap.add_argument("--max-cost", type=float,
                    help="JEV-82 guard: stop before the next case when the run's recorded accumulated cost exceeds this")
    ap.add_argument("--stamp-config", action="store_true",
                    help="JEV-84 opt-in (bloque S): huella config_sha256 por caso "
                         "+ preflight de configuración antes de llamadas/meta")
    args = ap.parse_args()

    phases = PHASES if args.phases == "all" else (PHASES + EXTRA_PHASES if args.phases == "all+new" else args.phases.split(","))
    missing = [f"{ph}:{pid}" for ph in phases for pid in missing_abstracts(ph)]
    if missing:
        sys.exit(f"{len(missing)} papers sin abstract ({', '.join(missing[:5])}…): "
                 f"ejecuta `python3 -m jevbench.fetch_abstracts`")
    opts = dict(o.split("=", 1) for o in args.opt)
    t0 = time.time()
    model = adapters.get(args.adapter)(**opts)
    print(f"[{args.adapter}] ready in {time.time() - t0:.0f}s {model.meta()}", flush=True)

    # Guarda de coste opt-in (JEV-82): prior_cost cubre TODOS los casos ya
    # registrados del run — también los de invocaciones anteriores, así que
    # el acumulado abarca los dos bloques y sus reintentos. Se comprueba
    # ANTES de abrir el primer caso de cada fase con trabajo pendiente (si
    # el acumulado durable ya supera el tope: 0 peticiones nuevas) y otra
    # vez tras registrar cada caso; los casos sin coste informado no
    # disparan la guarda ni suman (se cuentan). Los registros de error
    # también pueden llevar `cost` cuando el adaptador informa el gasto
    # del intento rechazado (JEV-78: ProviderRefusal.cost).
    #
    # Ledger durable (R58c §2): un --retry-errors REEMPLAZA los registros
    # (incluidos errores con coste informado), así que la suma de los
    # registros vigentes puede BAJAR tras un retry. Cada fase guarda en
    # meta.cost_ledger el acumulado total informado de todas las
    # invocaciones del run (monótono, nunca disminuye) y prior_cost es el
    # mayor entre lo registrado ahora y ese ledger — sin doble conteo: el
    # gasto de un registro reemplazado ya está en el ledger y el nuevo
    # decide solo suma lo suyo en session_cost.
    prior_cost = 0.0
    if args.max_cost is not None:
        recorded, ledger = 0.0, 0.0
        for ph in store.runs_in(args.run):
            d = store.load(args.run, ph) or {}
            recorded += sum(r.get("cost") or 0
                            for r in (d.get("cases") or {}).values())
            prev = (d.get("meta") or {}).get("cost_ledger")
            if isinstance(prev, (int, float)) and not isinstance(prev, bool):
                ledger = max(ledger, prev)
        prior_cost = max(recorded, ledger)
    session_cost, session_unknown, stop = 0.0, 0, None
    stamp = args.stamp_config

    for phase in phases:
        qs, cases = load_phase(phase)
        doc = store.load(args.run, phase) or {"meta": {}, "cases": {}}
        prev = dict(doc.get("meta") or {})
        base_meta = {
            "adapter": args.adapter, "opts": safe_opts(opts), **model.meta(),
            "phase": phase, "questions_hash": questions_hash(qs),
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0], "git": git_rev(),
            "updated": dt.datetime.now().isoformat(timespec="seconds")}
        # preflight de configuración ANTES de tocar meta / abrir llamadas (S)
        if stamp:
            probe = {**model.meta(), "adapter": args.adapter,
                     "questions_hash": questions_hash(qs)}
            bad_ph, mm = cost_guard.run_config_mismatches(
                store, args.run, probe)
            if not mm and prev:
                mm = cost_guard.config_mismatches(prev, base_meta)
                bad_ph = phase if mm else None
            if mm:
                detail = "; ".join(f"{k}: {a!r}→{b!r}" for k, a, b in mm)
                raise SystemExit(
                    f"{args.run}/{bad_ph}: configuración efectiva distinta "
                    f"({detail}) — 0 llamadas; meta intacta")
        doc["meta"].update(base_meta)
        todo = [c for c in cases if c.id not in doc["cases"]
                or (args.retry_errors and "error" in doc["cases"][c.id])]
        done = len(cases) - len(todo)
        if args.limit:
            todo = todo[:args.limit]
        print(f"--- {phase}: {len(todo)} to run ({done} already done) ---", flush=True)
        if (todo and args.max_cost is not None
                and prior_cost + session_cost > args.max_cost):
            stop = {"reason": "accumulated_cost", "phase": phase,
                    "accumulated": prior_cost + session_cost,
                    "cap": args.max_cost, "before_requests": True}
            doc["meta"]["cost_ledger"] = prior_cost + session_cost
            doc["meta"]["cost_stop"] = {
                **stop, "when": dt.datetime.now().isoformat(timespec="seconds"),
                "note": "progreso conservado; repetir el comando no elude "
                        "el presupuesto — ampliarlo exige nueva aprobación"}
            store.save(args.run, phase, doc)
            print(f"--- {phase}: PARADA por guarda de coste {stop} ---", flush=True)
            break
        for c in todo:
            t1 = time.time()
            try:
                out = model.decide(c.state, qs)
                rec = {"answers": out["answers"], "ms": round((time.time() - t1) * 1000),
                       "cost": out.get("cost"), "model": out.get("model")}
                if "usage" in out:  # compact telemetry only; never prompts or bodies
                    rec["usage"] = {k: v for k, v in out["usage"].items()
                                    if isinstance(v, (int, float, str, bool, type(None)))}
                if out.get("refusals"):
                    # negativa POR PREGUNTA (JEV-78, openai_decisions): la
                    # pregunta queda marcada {"type": "refusal"} en answers y
                    # se lista aquí; el caso se conserva y esa pregunta
                    # puntúa 0 como error en su pregunta
                    rec["refusals"] = out["refusals"]
                if "raw" in out:
                    # excepción deliberada (capture_raw): incluye cuerpos de
                    # petición y respuesta sin redactar — las claves van en
                    # cabeceras, nunca en el cuerpo; publish.py lo elimina del
                    # espejo público
                    rec["raw"] = out["raw"]
                short = " ".join(f"{k}={v.get('choice', v.get('score', v.get('noul', v.get('type'))))!s:.6}" for k, v in out["answers"].items())
                print(f"{phase} {c.id}: {short} | {rec['ms']}ms", flush=True)
            except Exception as e:  # keep going; the case is stored with its error
                traceback.print_exc()
                rec = {"error": f"{type(e).__name__}: {e}"[:300], "ms": round((time.time() - t1) * 1000)}
                diag = getattr(e, "diag", None)
                if isinstance(diag, dict) and diag:
                    rec["diag"] = diag
                err_cost = getattr(e, "cost", None)
                # coste informado del intento rechazado (p. ej. ProviderRefusal
                # del adaptador openai_decisions): se registra y cuenta para la
                # guarda — un rechazo no convierte en desconocido lo pagado
                if isinstance(err_cost, (int, float)) and not isinstance(err_cost, bool):
                    rec["cost"] = err_cost
                print(f"{phase} {c.id}: ERROR {rec['error'][:120]}", flush=True)
            doc["meta"].update(model.meta())
            if stamp:
                cost_guard.stamp_case_config(
                    rec, {**doc["meta"], **model.meta()})
            doc["cases"][c.id] = rec
            case_cost = rec.get("cost")
            if isinstance(case_cost, (int, float)):
                session_cost += case_cost
                if args.max_case_cost is not None and case_cost > args.max_case_cost:
                    stop = {"reason": "case_cost", "phase": phase, "case": c.id,
                            "cost": case_cost, "cap": args.max_case_cost}
            elif "error" not in rec:
                session_unknown += 1
            if (stop is None and args.max_cost is not None
                    and prior_cost + session_cost > args.max_cost):
                stop = {"reason": "accumulated_cost", "phase": phase, "case": c.id,
                        "accumulated": prior_cost + session_cost, "cap": args.max_cost}
            if args.max_case_cost is not None or args.max_cost is not None:
                doc["meta"]["cost_guard"] = {"max_case_cost": args.max_case_cost,
                                             "max_cost": args.max_cost}
            if args.max_cost is not None:
                doc["meta"]["cost_ledger"] = prior_cost + session_cost
            store.save(args.run, phase, doc)
            if stop is not None:
                doc["meta"]["cost_stop"] = {
                    **stop, "when": dt.datetime.now().isoformat(timespec="seconds"),
                    "note": "progreso conservado; repetir el comando no elude "
                            "el presupuesto — ampliarlo exige nueva aprobación"}
                store.save(args.run, phase, doc)
                print(f"--- {phase}: PARADA por guarda de coste {stop} ---", flush=True)
                break
        if stop is not None:
            break
    # con guarda activa se informa del acumulado DURABLE (incluye el gasto
    # de registros luego reemplazados por --retry-errors); sin ella, la
    # suma de los registros vigentes, como siempre
    cost = (prior_cost + session_cost if args.max_cost is not None else
            sum(r.get("cost") or 0 for p in phases
                for r in (store.load(args.run, p) or {"cases": {}})["cases"].values()))
    print(f"[{args.adapter}] done in {time.time() - t0:.0f}s, accumulated cost ${cost:.5f}"
          + (f" ({session_unknown} casos sin coste informado esta sesión)" if session_unknown else "")
          + (f" — PARADO por guarda de coste" if stop else ""), flush=True)


if __name__ == "__main__":
    main()
