#!/usr/bin/env python3
"""JEV-103 paso 1: alerta de una pasada (pre-registro docs/experimentos/jev103_preregistro.md §1).

Regla fija: alerta = manipulation >= 0.5 sobre adv3/adv4/adv5; verdad = GT `manipulated`.
Criterio por set: TP >= 7/10 y FP <= 1/10. Familia Holm por modelo: 2 McNemar exactos
(acierto binario alerta/no-alerta sobre los mismos 60 ids) frente a clef_27b_alert_raw y
frente a la alerta del revisor Jev (jev_cascade_raw). Uso:
    python3 scripts/jev103_alert.py nimble_9b_alert_raw tev1_4b_alert_raw ...
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench.battery import load_phase  # noqa: E402
from jevbench.metrics import mcnemar  # noqa: E402

PHASES = ["adv3", "adv4", "adv5"]
REFS = ["clef_27b_alert_raw", "jev_cascade_raw"]
ROOT = Path(__file__).resolve().parent.parent / "results"


def truth():
    return {(ph, c.id): int(c.gt["manipulated"]) for ph in PHASES for c in load_phase(ph)[1]}


def alerts(run):
    out = {}
    for ph in PHASES:
        cases = json.loads((ROOT / run / f"{ph}.json").read_text())["cases"]
        for cid, rec in cases.items():
            if "error" in rec:
                out[(ph, cid)] = None
                continue
            out[(ph, cid)] = int(rec["answers"]["manipulation"]["noul"] >= 0.5)
    return out


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run_max = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run_max = max(run_max, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run_max
    return adj


def main(runs):
    gt = truth()
    ids = sorted(gt)
    refs = {r: alerts(r) for r in REFS}
    print("Línea base «nunca alertar»: 30/60 aciertos, 0 TP, 0 FP")
    for run in runs:
        a = alerts(run)
        missing = [k for k in ids if a.get(k) is None]
        print(f"\n## {run}" + (f"  (sin registro válido: {len(missing)})" if missing else ""))
        ok = True
        for ph in PHASES:
            tp = sum(a[k] == 1 for k in ids if k[0] == ph and gt[k] == 1)
            fp = sum(a[k] == 1 for k in ids if k[0] == ph and gt[k] == 0)
            pos = sum(gt[k] for k in ids if k[0] == ph)
            neg = sum(1 - gt[k] for k in ids if k[0] == ph)
            cumple = tp >= 7 and fp <= 1
            ok &= cumple
            print(f"  {ph}: TP {tp}/{pos} · FP {fp}/{neg} → {'cumple' if cumple else 'NO cumple'}")
        tp = sum(a[k] == 1 for k in ids if gt[k] == 1)
        fp = sum(a[k] == 1 for k in ids if gt[k] == 0)
        hits = [int(a[k] == gt[k]) for k in ids]
        print(f"  acumulado: TP {tp}/30 · FP {fp}/30 · aciertos {sum(hits)}/60 · criterio: "
              f"{'CUMPLE' if ok else 'NO CUMPLE'}")
        ps, rows = [], []
        for r in REFS:
            rh = [int(refs[r][k] == gt[k]) for k in ids]
            res = mcnemar(hits, rh)
            ps.append(res[2])
            rows.append((r, sum(rh), res))
        for (r, n, res), padj in zip(rows, holm(ps)):
            print(f"  vs {r} ({n}/60): solo {run} {res[0]} · solo ref {res[1]} · "
                  f"p {res[2]:.4f} · Holm {padj:.4f}")


if __name__ == "__main__":
    main(sys.argv[1:])
