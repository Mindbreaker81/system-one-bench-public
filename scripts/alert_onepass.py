#!/usr/bin/env python3
"""One-pass manipulation alert: only the `manipulation` question (threshold 0.5,
same wording as jevbench/cascade.py) on the raw case text of adv3/adv4/adv5.
Pre-register the extension in docs/experimentos/alerta_manipulacion.md BEFORE running.
Usage: scripts/alert_onepass.py <adapter> <run> [k=v ...]  -> results/<run>_alert_raw/

Opt-in cost guards (JEV-84): --max-case-cost / --max-cost with durable ledger,
case_cost blocking resume, config fingerprint, --retry-errors (one pass).
Without cost-guard flags there is no fingerprint/drift abort nor durable
retry; adapter/questions_hash are always checked (added in this JEV-84
pre-register — not claimed as pre-HEAD historical behaviour).
"""
import argparse
import datetime as dt
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import adapters, cost_guard, store  # noqa: E402
from jevbench.battery import load_phase, questions_hash  # noqa: E402
from jevbench.cascade import MANIPULATION  # noqa: E402

PHASES = ["adv3", "adv4", "adv5"]
QUESTIONS = {"manipulation": MANIPULATION}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter", choices=sorted(adapters.REGISTRY))
    ap.add_argument("run", help="base run name; output goes to <run>_alert_raw")
    ap.add_argument("opts", nargs="*", help="adapter option k=v")
    ap.add_argument("--max-case-cost", type=float,
                    help="opt-in: stop before next case when a recorded case cost exceeds this")
    ap.add_argument("--max-cost", type=float,
                    help="opt-in: stop before next case when the run's durable cost exceeds this")
    ap.add_argument("--retry-errors", action="store_true",
                    help="with cost guards: one allowed retry pass for error cases")
    ap.add_argument("--amend-case-cost-stop", action="store_true",
                    help="mark persisted case_cost stops as amended (keeps evidence)")
    args = ap.parse_args()
    opts = dict(o.split("=", 1) for o in args.opts)
    model = adapters.get(args.adapter)(**opts)
    out_run = f"{args.run}_alert_raw"
    guarded = args.max_cost is not None or args.max_case_cost is not None
    if args.amend_case_cost_stop:
        n = cost_guard.amend_case_cost_stops(None, store, out_run)
        print(f"[alert] case_cost stops enmendados en {n} fase(s)", flush=True)
    docs = cost_guard.load_phase_docs(store, out_run)
    prior = cost_guard.prior_cost(docs) if args.max_cost is not None else 0.0
    qhash = questions_hash(QUESTIONS)
    # versión congelada del run (todas las fases) — R70-4
    try:
        run_frozen = cost_guard.frozen_resolved_from_docs(docs, key="resolved")
    except ValueError as e:
        raise SystemExit(f"{out_run}: {e}") from e
    # fingerprint opt-in contra TODAS las fases (R69 F2/F5)
    if guarded:
        probe = {"adapter": args.adapter, "questions_hash": qhash, **model.meta()}
        bad_ph, mm = cost_guard.run_config_mismatches(store, out_run, probe)
        if mm:
            detail = "; ".join(f"{k}: {a!r}→{b!r}" for k, a, b in mm)
            raise SystemExit(
                f"{out_run}/{bad_ph}: configuración efectiva distinta "
                f"({detail}) — 0 llamadas; meta intacta")
        cur_ver = model.meta().get("resolved")
        if (run_frozen is not None and cur_ver is not None
                and cur_ver != run_frozen):
            raise SystemExit(
                f"{out_run}: versión congelada del run es {run_frozen!r} "
                f"y el adaptador resuelve {cur_ver!r} — 0 llamadas; "
                "meta intacta")
    if guarded and args.retry_errors:
        for d in docs:
            reg = cost_guard.acquisition_registry(d.setdefault("meta", {}))
            if reg.get("retry_errors_passes", 0) >= 1:
                raise SystemExit(
                    f"{out_run}: ya se usó el único --retry-errors del "
                    "bloque; no se abren más reintentos")
    session_cost, stop = 0.0, None
    for phase in PHASES:
        _, cases = load_phase(phase)
        doc = store.load(out_run, phase) or {"meta": {}, "cases": {}}
        prev = dict(doc.get("meta") or {})
        # frozen_ver: fase previa o la del run completo (R69 F3 / R70-4)
        frozen_ver = prev.get("resolved") or run_frozen
        base_meta = {
            "adapter": args.adapter, "opts": opts, **model.meta(),
            "phase": phase, "questions_hash": qhash,
            "note": "alerta de una pasada: solo pregunta manipulation, sin prompt de revisor",
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0],
            "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True,
                                  cwd=store.ROOT.parent).stdout.strip() or None,
            "updated": dt.datetime.now().isoformat(timespec="seconds")}
        # procedencia de este pre-registro (siempre; JEV-84)
        if prev.get("questions_hash") is not None \
                and prev["questions_hash"] != qhash:
            raise SystemExit(
                f"{out_run}/{phase}: questions_hash previo "
                f"{prev['questions_hash']!r} != vigente {qhash!r} — "
                "0 llamadas; meta intacta")
        if prev.get("adapter") is not None and prev["adapter"] != args.adapter:
            raise SystemExit(
                f"{out_run}/{phase}: adapter previo {prev['adapter']!r} != "
                f"{args.adapter!r} — 0 llamadas; meta intacta")
        # fingerprint extendido solo con guardas (R69 F5)
        if guarded:
            mismatches = cost_guard.config_mismatches(prev, base_meta)
            if mismatches:
                detail = "; ".join(f"{k}: {a!r}→{b!r}" for k, a, b in mismatches)
                raise SystemExit(
                    f"{out_run}/{phase}: configuración efectiva distinta "
                    f"({detail}) — 0 llamadas; meta intacta")
        doc["meta"].update(base_meta)
        # preservar resolved si el adaptador aún no resolvió
        if frozen_ver is not None and doc["meta"].get("resolved") is None:
            doc["meta"]["resolved"] = frozen_ver
        if guarded:
            todo = []
            for c in cases:
                rec = doc["cases"].get(c.id)
                if rec is None:
                    todo.append(c)
                elif ("error" in rec and args.retry_errors
                      and not cost_guard.case_already_retried(
                          doc["meta"], phase, c.id)):
                    todo.append(c)
        else:
            todo = [c for c in cases
                    if c.id not in doc["cases"]
                    or "error" in doc["cases"].get(c.id, {})]
        if todo and guarded:
            docs = cost_guard.load_phase_docs(store, out_run)
            stop = cost_guard.stop_before_requests(
                doc["meta"], phase=phase, prior=prior,
                session_cost=session_cost, max_cost=args.max_cost, docs=docs)
            if stop is not None:
                store.save(out_run, phase, doc)
                print(f"--- {phase}: PARADA por guarda de coste {stop} ---",
                      flush=True)
                break
        for c in cases:
            if c.id in doc["cases"] and "error" not in doc["cases"][c.id]:
                continue
            if (guarded and c.id in doc["cases"]
                    and "error" in doc["cases"][c.id]
                    and not args.retry_errors):
                continue
            if (guarded and c.id in doc["cases"]
                    and "error" in doc["cases"][c.id]
                    and args.retry_errors
                    and cost_guard.case_already_retried(
                        doc["meta"], phase, c.id)):
                continue
            if stop is not None:
                break
            # marcar retry ANTES del intento (R69 F4)
            rec0 = doc["cases"].get(c.id)
            if (guarded and args.retry_errors and rec0 is not None
                    and "error" in rec0):
                cost_guard.mark_retry_attempt(doc["meta"], phase, c.id)
                doc["cases"][c.id] = {**rec0, "retry_attempted": True}
                store.save(out_run, phase, doc)
            t0 = time.time()
            try:
                out = model.decide(c.state, QUESTIONS)
                ver = out.get("model") or model.meta().get("resolved")
                if frozen_ver is None and ver is not None:
                    frozen_ver = ver
                    doc["meta"]["resolved"] = ver
                elif (guarded and ver is not None and frozen_ver is not None
                      and ver != frozen_ver):
                    # drift: persistir gasto + evidencia antes de abortar
                    case_cost = out.get("cost")
                    doc["cases"][c.id] = {
                        "answers": out["answers"],
                        "ms": round((time.time() - t0) * 1000),
                        "cost": case_cost, "model": out.get("model"),
                        "resolved": ver, "version_drift": True}
                    cost_guard.stamp_case_config(
                        doc["cases"][c.id],
                        {**doc["meta"], **model.meta(), "resolved": ver})
                    if isinstance(case_cost, (int, float)) \
                            and not isinstance(case_cost, bool):
                        session_cost += case_cost
                    doc["meta"]["version_drift"] = {
                        "frozen": frozen_ver, "observed": ver, "case": c.id}
                    cost_guard.apply_case_cost(
                        doc["meta"], case_cost=case_cost, case_id=c.id,
                        phase=phase, session_cost=session_cost, prior=prior,
                        max_case_cost=args.max_case_cost,
                        max_cost=args.max_cost)
                    store.save(out_run, phase, doc)
                    raise SystemExit(
                        f"{phase}/{c.id}: resolved cambió "
                        f"{frozen_ver} → {ver} — meta de procedencia "
                        "conservada; pendiente NO EVALUABLE")
                doc["cases"][c.id] = {
                    "answers": out["answers"],
                    "ms": round((time.time() - t0) * 1000),
                    "cost": out.get("cost"), "model": out.get("model"),
                    "resolved": ver}
                cost_guard.stamp_case_config(
                    doc["cases"][c.id],
                    {**doc["meta"], **model.meta(), "resolved": ver})
                if "usage" in out:
                    doc["cases"][c.id]["usage"] = {
                        k: v for k, v in out["usage"].items()
                        if isinstance(v, (int, float, str, bool, type(None)))}
            except SystemExit:
                raise
            except Exception as e:  # keep going; the case is stored with its error
                rec = {"error": f"{type(e).__name__}: {e}"[:300],
                       "ms": round((time.time() - t0) * 1000)}
                if guarded and args.retry_errors:
                    rec["retry_attempted"] = True
                err_cost = getattr(e, "cost", None)
                if isinstance(err_cost, (int, float)) and not isinstance(err_cost, bool):
                    rec["cost"] = err_cost
                cost_guard.stamp_case_config(
                    rec, {**doc["meta"], **model.meta()})
                doc["cases"][c.id] = rec
                print(f"{phase} {c.id}: ERROR {e}", flush=True)
            case_cost = doc["cases"][c.id].get("cost")
            if isinstance(case_cost, (int, float)) and not isinstance(case_cost, bool):
                session_cost += case_cost
            stop = cost_guard.apply_case_cost(
                doc["meta"], case_cost=case_cost, case_id=c.id, phase=phase,
                session_cost=session_cost, prior=prior,
                max_case_cost=args.max_case_cost, max_cost=args.max_cost)
            store.save(out_run, phase, doc)
            p = doc["cases"][c.id].get("answers", {}).get("manipulation", {}).get("noul")
            print(f"{phase} {c.id}: manipulation={p}", flush=True)
            if stop is not None:
                cost_guard.mark_stop(doc["meta"], stop)
                store.save(out_run, phase, doc)
                print(f"--- {phase}: PARADA por guarda de coste {stop} ---",
                      flush=True)
                break
        if frozen_ver is not None:
            doc["meta"]["resolved"] = frozen_ver
            store.save(out_run, phase, doc)
            run_frozen = frozen_ver
        n = sum("answers" in x for x in doc["cases"].values())
        print(f"--- {phase}: {n}/{len(cases)} done ---", flush=True)
        if stop is not None:
            break
    if guarded and args.retry_errors:
        still = False
        for ph in store.runs_in(out_run):
            doc = store.load(out_run, ph)
            if not doc:
                continue
            _, cases = load_phase(ph)
            meta = doc.setdefault("meta", {})
            for c in cases:
                rec = doc["cases"].get(c.id) or {}
                if "error" in rec and not cost_guard.case_already_retried(
                        meta, ph, c.id):
                    still = True
                    break
            if still:
                break
        if not still:
            for ph in store.runs_in(out_run):
                doc = store.load(out_run, ph)
                if not doc:
                    continue
                reg = cost_guard.acquisition_registry(
                    doc.setdefault("meta", {}))
                reg["retry_errors_passes"] = max(
                    int(reg.get("retry_errors_passes") or 0), 1)
                store.save(out_run, ph, doc)


if __name__ == "__main__":
    main()
