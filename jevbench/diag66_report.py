"""Informe de la matriz JEV-66: lee results/diag_qwen38_jev66_<bloque>_*_r*
y resume por celda/repetición los vectores nulos crudos, errores, reintentos,
tokens de entrada (la inyección del esquema debe subirlos ~4x frente al
control), acuerdo de decisiones entre reps y acierto contra el GT real.

  python3 -m jevbench.diag66_report nvfp4
  python3 -m jevbench.diag66_report nvfp4 --json

Diagnóstico sobre 12 casos fijados: no es puntuación del marcador.
"""
import argparse
import json
import statistics
from collections import defaultdict

from . import store
from .battery import load_phase
from .diag63 import DIAG_CASES
from .diag66 import CELLS
from .diag65_report import (_accuracy, _decisions, _majority_baseline,
                            _med, analyze_case)


def _iter_cases():
    """phase -> {case_id: (questions, case)} for the 12 fixed JEV-63 cases."""
    out = {}
    for phase, ids in DIAG_CASES.items():
        qs, cases = load_phase(phase)
        by_id = {c.id: c for c in cases}
        out[phase] = {i: (qs, by_id[i]) for i in ids if i in by_id}
    return out


def _input_tokens(rec):
    u = rec.get("usage") or {}
    v = u.get("input_tokens")
    return v if isinstance(v, (int, float)) else None


def _row(pc):
    n = len(pc)
    costs = [r["cost"] for r in pc.values()]
    known = [c for c in costs if c is not None]
    ms_all = [r["ms"] for r in pc.values() if r["ms"] is not None]
    tin = [r["input_tokens"] for r in pc.values() if r["input_tokens"] is not None]
    return {
        "cases": n,
        "errors": sum(1 for r in pc.values() if r["error"]),
        "malformed_retries": sum(r["retries"] for r in pc.values()),
        "raw_zero": sum(r["raw_zero"] for r in pc.values()),
        "raw_uniform": sum(r["raw_uniform"] for r in pc.values()),
        "raw_invalid": sum(r["raw_invalid"] for r in pc.values()),
        "raw_unparsed": sum(r["raw_unparsed"] for r in pc.values()),
        # distingue «sin captura raw» de «captura sin nulos»: un caso sin
        # intentos registrados no es una evidencia de cero fallos
        "raw_absent": sum(1 for r in pc.values()
                          if r["attempts"] == 0 and not r["error"]),
        "finish_length": sum(r["finish_length"] for r in pc.values()),
        "norm_uniform": sum(r["norm_uniform"] for r in pc.values()),
        "input_tokens_med": _med(tin),
        "ms_med": _med(ms_all),
        "cost": round(sum(known), 5) if known else None,
    }


def _slug(run, config, prefix="diag_qwen38_jev66"):
    """run name -> (cell, rep)."""
    rest = run[len(f"{prefix}_{config}_"):]
    cell, rep = rest.rsplit("_r", 1)
    return cell, int(rep)


def collect(config, prefix="diag_qwen38_jev66"):
    """Scan every <prefix>_<config>_* run dir -> structured summary."""
    phase_case = _iter_cases()
    cells = {}
    decs = {}
    missing = {}
    for d in sorted(store.ROOT.glob(f"{prefix}_{config}_*_r*")):
        run = d.name
        cell, rep = _slug(run, config, prefix)
        if cell not in CELLS:
            continue
        cells[run] = {"meta": None, "cases": {}}
        decs[run] = {}
        expected = {f"{ph}/{cid}": None for ph, ids in DIAG_CASES.items()
                    for cid in ids}
        for ph in store.runs_in(d.name):
            doc = store.load(run, ph) or {}
            cells[run]["meta"] = doc.get("meta") or {}
            case_map = phase_case.get(ph) or {}
            for cid, rec in (doc.get("cases") or {}).items():
                pc = f"{ph}/{cid}"
                if cid not in case_map:
                    continue
                qs, _ = case_map[cid]
                r = analyze_case(rec, qs, discrete=False)
                r["input_tokens"] = _input_tokens(rec)
                cells[run]["cases"][pc] = r
                decs[run][pc] = _decisions(rec, qs)
        missing[run] = sorted(set(expected) - set(cells[run]["cases"]))
    return cells, decs, missing, phase_case


def summarize(config, cells, decs, missing, phase_case,
              prefix="diag_qwen38_jev66"):
    groups = defaultdict(dict)   # cell -> rep -> per-case
    for run, data in cells.items():
        cell, rep = _slug(run, config, prefix)
        groups[cell][rep] = data["cases"]
    out = {}
    for cell, reps in sorted(groups.items()):
        rows = [dict(rep=rep, **_row(reps.get(rep) or {})) for rep in (1, 2, 3)]
        acc = {}
        for rep, pc in reps.items():
            hits = tot = 0
            for pcc in (pc or {}):
                ph, cid = pcc.split("/", 1)
                if cid not in (phase_case.get(ph) or {}):
                    continue
                qs, case = phase_case[ph][cid]
                h, t = _accuracy((decs.get(
                    f"{prefix}_{config}_{cell}_r{rep}") or {}).get(pcc) or {},
                    case, qs)
                hits += h
                tot += t
            acc[rep] = (hits, tot)
        agree = tot_a = 0
        run_of = {rep: f"{prefix}_{config}_{cell}_r{rep}"
                  for rep in (1, 2, 3)}
        for pcc, d1 in (decs.get(run_of.get(1)) or {}).items():
            for rep in (2, 3):
                d2 = (decs.get(run_of.get(rep)) or {}).get(pcc) or {}
                for qid, v in d1.items():
                    if v is not None and qid in d2 and d2[qid] is not None:
                        tot_a += 1
                        agree += int(v == d2[qid])
        expected_all = sorted(f"{ph}/{cid}" for ph, ids in DIAG_CASES.items()
                              for cid in ids)
        out[cell] = {"reps": rows, "accuracy": acc,
                     "missing": {rep: (missing[run_of[rep]]
                                       if run_of[rep] in missing
                                       else expected_all)
                                 for rep in (1, 2, 3)},
                     "decision_agreement": (agree, tot_a)}
    baselines = {}
    for ph, m in phase_case.items():
        if m:
            qs = m[next(iter(m))][0]
            baselines[ph] = _majority_baseline(m, qs)
    return out, baselines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="slug del bloque (nvfp4, fp8)")
    ap.add_argument("--prefix", default="diag_qwen38_jev66")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cells, decs, missing, phase_case = collect(args.config, args.prefix)
    summary, baselines = summarize(args.config, cells, decs, missing,
                                   phase_case, args.prefix)

    if args.json:
        print(json.dumps({"config": args.config,
                          "summary": {k: v for k, v in summary.items()},
                          "majority_baseline": baselines}, indent=1))
        return

    print(f"# diag66 {args.config}")
    for ph, (h, t) in baselines.items():
        print(f"baseline mayoría {ph}: {h}/{t}")
    for cell, s in sorted(summary.items()):
        print(f"\n## {cell}")
        print("rep | casos | err | nulos | uniform | inv | unparsed | sin raw | "
              "length | reintentos | tok-in med | ms med | acierto | missing")
        for row in s["reps"]:
            rep = row["rep"]
            h, t = s["accuracy"].get(rep, (0, 0))
            miss = s["missing"].get(rep) or []
            print(f"{rep} | {row['cases']} | {row['errors']} | "
                  f"{row['raw_zero']} | {row['raw_uniform']} | "
                  f"{row['raw_invalid']} | {row['raw_unparsed']} | "
                  f"{row['raw_absent']} | "
                  f"{row['finish_length']} | {row['malformed_retries']} | "
                  f"{row['input_tokens_med']} | {row['ms_med']} | {h}/{t} | "
                  f"{len(miss)}")
        a, t = s["decision_agreement"]
        print(f"acuerdo de decisiones entre reps: {a}/{t}")


if __name__ == "__main__":
    main()
