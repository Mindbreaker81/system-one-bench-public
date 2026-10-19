"""Errores con mucha confianza (docs/experimentos/errores_seguros.md).

Descriptivo y de solo lectura: recorre las configuraciones de una pasada de la web
sobre las 11 fases del ajustado y cuenta las decisiones erróneas emitidas con
confianza >= 0,9 / 0,99. No modifica el scorer ni los resultados.

    python3 scripts/errores_seguros.py [--json SALIDA.json] [--md SALIDA.md]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jevbench import metrics as M, store, web  # noqa: E402
from jevbench.battery import load_phase  # noqa: E402
from jevbench.score import ADJ_PHASES  # noqa: E402

THRESHOLDS = (0.9, 0.99)


def confidence(q, pred):
    """Probabilidad que el modelo asigna a la decisión que emite (None si no hay)."""
    if pred.get("refused"):
        return None
    if q["type"] == "noul":
        v = min(1.0, max(0.0, pred["value"]))
        return max(v, 1 - v)
    probs = pred.get("probs")
    if not probs:
        return None
    s = sum(probs.values()) or 1.0
    if q["type"] == "choice":
        return probs.get(pred["label"], 0.0) / s
    return probs.get(str(M.level(pred["value"], len(q["criteria"]))), 0.0) / s


def decisions(run):
    """[(fase, caso, pregunta, tipo, acierto, confianza)] o None si falta una fase."""
    out = []
    for ph in ADJ_PHASES:
        doc = store.load(run, ph)
        if doc is None:
            return None
        qs, cases = load_phase(ph)
        for c in cases:
            r = doc["cases"].get(c.id)
            if r is None or "error" in r:
                continue
            for name, q in qs.items():
                pred = M.normalize(r["answers"][name], q)
                hit = M.point(q, pred, c.gt[name]) == 1.0
                out.append((ph, c.id, name, q["type"], hit, confidence(q, pred)))
    return out


def stats(rows):
    rows = [r for r in rows if r[5] is not None]
    n = len(rows)
    errors = sum(1 for r in rows if not r[4])
    d = {"n": n, "errors": errors}
    for t in THRESHOLDS:
        sure = [r for r in rows if r[5] >= t]
        bad = sum(1 for r in sure if not r[4])
        d[f"sure_{t}"] = len(sure)
        d[f"sure_err_{t}"] = bad
        d[f"sure_err_per100_{t}"] = 100 * bad / n if n else None
        d[f"precision_sure_{t}"] = 100 * (len(sure) - bad) / len(sure) if sure else None
        d[f"err_share_sure_{t}"] = 100 * bad / errors if errors else None
    return d


def majority_noul_error():
    n = bad = 0
    for ph in ADJ_PHASES:
        qs, cases = load_phase(ph)
        base = M.majority_baseline(qs, cases)
        for name, q in qs.items():
            if q["type"] != "noul":
                continue
            n += len(cases)
            bad += len(cases) - base[name]["points"]
    return 100 * bad / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args()
    res, incomplete = {}, []
    for rid, (label, family, kind) in web.RUNS.items():
        if kind != "single":
            continue
        rows = decisions(rid)
        if rows is None:
            incomplete.append(rid)
            continue
        noul = [r for r in rows if r[3] == "noul"]
        discrete = rid.endswith("_disc") or all(r[5] == 1.0 for r in noul)
        res[rid] = {"label": label, "family": family, "discrete": discrete,
                    "noul": stats(noul), "all": stats(rows)}
    maj = majority_noul_error()
    out = {"phases": ADJ_PHASES, "thresholds": THRESHOLDS, "majority_noul_error_pct": maj,
           "incomplete": incomplete, "runs": res}
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))

    def f(x, nd=1):
        return "—" if x is None else f"{x:.{nd}f}"

    lines = [f"Mayoría oráculo: {maj:.1f} % de error en binarias (sin confianza).", "",
             "| run | n binarias | error % | seguros ≥0,9 % | errores seguros /100 (≥0,9) | "
             "precisión si ≥0,9 | % errores seguros (≥0,9) | errores /100 (≥0,99) | "
             "errores seguros /100 todas (≥0,9) |",
             "|---|---|---|---|---|---|---|---|---|"]
    order = sorted(res, key=lambda k: (res[k]["discrete"], -res[k]["noul"]["sure_err_per100_0.9"]))
    for rid in order:
        r = res[rid]
        nb, al = r["noul"], r["all"]
        tag = " (discreta)" if r["discrete"] else ""
        lines.append(
            f"| `{rid}`{tag} | {nb['n']} | {f(100 * nb['errors'] / nb['n'])} | "
            f"{f(100 * nb['sure_0.9'] / nb['n'])} | {f(nb['sure_err_per100_0.9'])} | "
            f"{f(nb['precision_sure_0.9'])} | {f(nb['err_share_sure_0.9'])} | "
            f"{f(nb['sure_err_per100_0.99'])} | {f(al['sure_err_per100_0.9'])} |")
    if incomplete:
        lines += ["", "Sin las 11 fases (fuera): " + ", ".join(f"`{x}`" for x in incomplete)]
    text = "\n".join(lines)
    if a.md:
        Path(a.md).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
