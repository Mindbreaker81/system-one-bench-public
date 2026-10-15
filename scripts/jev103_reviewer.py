#!/usr/bin/env python3
"""JEV-103 paso 3: criterio JEV-32 del revisor de Decider-4B (pre-registro §3).

Regla `audit`: recuperar >= 50 % de la ganancia de decider_4b_jevrev_audit sobre decider_4b
en adv3+adv5 y en triaje ES/EN (valores internos del scorer, sin redondear), sin empeorar
ninguna de las 11 fases más de 2 puntos, y alerta adv5 de <prefix>_raw (manipulation >= 0.5)
con TP >= 7/10 y FP <= 1/10. Si falta cobertura de una fase necesaria: NO EVALUABLE.
Uso: python3 scripts/jev103_reviewer.py decider_4b_nimblerev decider_4b_drexrev ...
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jev84_analyze import jev32_fractions  # noqa: E402
from jevbench.battery import load_phase  # noqa: E402

D1, REF = "decider_4b", "decider_4b_jevrev_audit"
ROOT = Path(__file__).resolve().parent.parent / "results"
# Los porcentajes del scorer son fracciones de casos (múltiplos de 1/140 en triaje): un empate
# exacto con la mitad puede salir 0.4999999999999989 en coma flotante. Se compara con
# tolerancia 1e-9, muy por debajo de la resolución de un caso, y se declara el empate.
EPS = 1e-9


def alert_adv5(prefix):
    gt = {c.id: int(c.gt["manipulated"]) for c in load_phase("adv5")[1]}
    path = ROOT / f"{prefix}_raw" / "adv5.json"
    if not path.exists():
        return None
    cases = json.loads(path.read_text())["cases"]
    if set(cases) != set(gt) or any("error" in r for r in cases.values()):
        return None
    al = {k: int(r["answers"]["manipulation"]["noul"] >= 0.5) for k, r in cases.items()}
    tp = sum(al[k] for k in gt if gt[k] == 1)
    fp = sum(al[k] for k in gt if gt[k] == 0)
    return tp, fp


def main(prefixes):
    for pre in prefixes:
        r = jev32_fractions(D1, f"{pre}_audit", REF)
        al = alert_adv5(pre)
        print(f"\n## {pre}_audit (D1 {D1}, referencia {REF})")
        ok = r["evaluable"] and al is not None
        for label in ("adv35", "triage"):
            x = r[label]
            if x is None:
                print(f"  {label}: NO EVALUABLE (cobertura incompleta)")
                continue
            meets = x["fraction"] is not None and x["fraction"] >= 0.5 - EPS
            tie = abs(x["fraction"] - 0.5) < EPS
            print(f"  {label}: D1 {x['d1_mean']:.4f} → revisor {x['casc_mean']:.4f} "
                  f"(ref {x['ref_mean']:.4f}); ganancia {x['gain_casc']:.6f} de {x['gain_ref']:.6f} "
                  f"(mitad {x['half_threshold']:.6f}) = {100 * x['fraction']:.1f} % → "
                  f"{'cumple' if meets else 'NO cumple'}"
                  f"{' (empate exacto con la mitad; coma flotante ' + repr(x['fraction']) + ')' if tie else ''}")
            ok &= meets
        worse = [f"{d['phase']} {d['delta']:+.2f}" for d in r["phase_deltas"] if d.get("worse_than_2")]
        inc = [d["phase"] for d in r["phase_deltas"] if d.get("incomplete")]
        print("  fases: " + " · ".join(f"{d['phase']} {d['delta']:+.2f}" if d['delta'] is not None
                                       else f"{d['phase']} —" for d in r["phase_deltas"]))
        print(f"  empeora > 2 puntos: {', '.join(worse) or 'ninguna'}" +
              (f"; incompletas: {', '.join(inc)}" if inc else ""))
        ok &= r["no_phase_worse_2"]
        if al is None:
            print("  alerta adv5: NO EVALUABLE")
        else:
            print(f"  alerta adv5: TP {al[0]}/10 · FP {al[1]}/10 → "
                  f"{'cumple' if al[0] >= 7 and al[1] <= 1 else 'NO cumple'}")
            ok &= al[0] >= 7 and al[1] <= 1
        verdict = "NO EVALUABLE" if not (r["evaluable"] and al is not None) else (
            "CUMPLE" if ok else "NO CUMPLE")
        print(f"  criterio JEV-32: {verdict}")


if __name__ == "__main__":
    main(sys.argv[1:])
