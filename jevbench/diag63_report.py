"""Informe de la matriz JEV-63: lee results/diag_qwen38_<config>_<celda>_r<rep>/
y resume por celda/repeticion validez, vectores nulos crudos, elecciones casi
uniformes normalizadas, decisiones, tiempos y dispersion entre repeticiones.

  python3 -m jevbench.diag63_report nvfp4
  python3 -m jevbench.diag63_report nvfp4 --json

No puntua: es diagnostico sobre 12 casos fijados, no una bateria comparable con
el marcador. Un vector casi uniforme NO implica error: distinguir "todos 0.0"
(raw nulo, invalido) de "repartido parejo" (posible incertidumbre legitima).
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from . import store
from .diag63 import DIAG_CASES, CELL_ORDER

PHASES = list(DIAG_CASES)
CELLS = ["typesafe_struct", "simple_struct", "typesafe_nostruct", "simple_nostruct"]


def _iter_choice_probs(answers):
    """Yield (qid, {label: p}) for choice/score answers in wire format."""
    for qid, a in (answers or {}).items():
        probs = a.get("probabilities") if isinstance(a, dict) else None
        if probs:
            yield qid, probs


def _extract_json(text):
    """Same tolerance as the adapter's decode: strip Markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl != -1 else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text


def _raw_choice_vectors(case):
    """Choice/score probability vectors from the raw LLM response (pre-normalize).
    Returns list of (qid, {label: float}) or None if unparseable."""
    out = []
    attempts = case.get("raw") or (case.get("diag") or {}).get("raw") or []
    for att in attempts:
        resp = att.get("llm_response") or {}
        try:
            content = resp["choices"][0]["message"]["content"]
            data = json.loads(_extract_json(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            out.append(("?", None))
            continue
        for qid, val in (data.get("answers") or {}).items():
            if isinstance(val, dict):
                out.append((qid, {k: v for k, v in val.items()
                                  if isinstance(v, (int, float))}))
    return out


def analyze_case(rec):
    """One case record -> compact flags."""
    r = {"error": bool(rec.get("error")), "ms": rec.get("ms"),
         "cost": rec.get("cost"), "retries": 0,
         "raw_zero": 0, "raw_uniform": 0, "raw_total": 0, "raw_bad": 0,
         "norm_uniform": 0}
    u = rec.get("usage") or {}
    r["retries"] = (u.get("n_retries_malformed") or 0)
    for qid, vec in _raw_choice_vectors(rec):
        if vec is None:
            r["raw_bad"] += 1
            continue
        r["raw_total"] += 1
        vals = list(vec.values())
        if vals and all(v == 0 for v in vals):
            r["raw_zero"] += 1
        elif vals and (max(vals) - min(vals)) < 0.05:
            r["raw_uniform"] += 1
    for _, probs in _iter_choice_probs(rec.get("answers")):
        vals = list(probs.values())
        if vals and (max(vals) - min(vals)) < 0.05:
            r["norm_uniform"] += 1
    return r


def decisions(rec):
    """Per-question argmax/noul decisions of a case record."""
    d = {}
    for qid, a in (rec.get("answers") or {}).items():
        if not isinstance(a, dict):
            continue
        if a.get("choice") is not None:
            d[qid] = a["choice"]
        elif a.get("score") is not None:
            # continuous score -> rounded level for agreement checks
            d[qid] = round(a["score"], 2)
        elif a.get("noul") is not None:
            d[qid] = round(a["noul"], 2)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="slug del bloque (nvfp4, fp8, cerebras, arcgguf)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cells = defaultdict(dict)   # cell -> rep -> per-case analysis
    decs = defaultdict(dict)    # cell -> rep -> {case: {qid: decision}}
    missing = []
    for cell in CELLS:
        for rep in (1, 2, 3):
            run = f"diag_qwen38_{args.config}_{cell}_r{rep}"
            per_case = {}
            for ph in PHASES:
                doc = store.load(run, ph) or {}
                for cid, rec in (doc.get("cases") or {}).items():
                    per_case[f"{ph}/{cid}"] = analyze_case(rec)
                    decs[cell].setdefault(rep, {})[f"{ph}/{cid}"] = decisions(rec)
            if not per_case:
                missing.append(run)
            cells[cell][rep] = per_case

    summary = {}
    for cell in CELLS:
        rows = []
        for rep in (1, 2, 3):
            pc = cells[cell][rep]
            n = len(pc)
            rows.append({
                "rep": rep, "cases": n,
                "errors": sum(1 for r in pc.values() if r["error"]),
                "malformed_retries": sum(r["retries"] for r in pc.values()),
                "raw_zero": sum(r["raw_zero"] for r in pc.values()),
                "raw_uniform": sum(r["raw_uniform"] for r in pc.values()),
                "raw_total": sum(r["raw_total"] for r in pc.values()),
                "norm_uniform": sum(r["norm_uniform"] for r in pc.values()),
                "ms_med": sorted(r["ms"] for r in pc.values() if r["ms"])[n // 2] if n else None,
                "cost": round(sum(r["cost"] or 0 for r in pc.values()), 5),
            })
        # decision agreement across reps (same case, same cell)
        agree = tot = 0
        for case_id, d1 in (decs[cell].get(1) or {}).items():
            for rep in (2, 3):
                d2 = (decs[cell].get(rep) or {}).get(case_id) or {}
                for qid, v in d1.items():
                    if qid in d2:
                        tot += 1
                        agree += int(v == d2[qid])
        summary[cell] = {"reps": rows,
                         "decision_agreement": f"{agree}/{tot}" if tot else "n/a"}

    if args.json:
        print(json.dumps({"config": args.config, "summary": summary,
                          "missing_runs": missing}, indent=1))
        return

    print(f"# diag63 {args.config} — {args.config} cells x 3 reps")
    if missing:
        print(f"runs ausentes: {', '.join(missing)}")
    for cell in CELLS:
        s = summary[cell]
        print(f"\n## {cell}  (acuerdo de decisiones entre reps: {s['decision_agreement']})")
        print("rep casos err reint raw_zero raw_unif raw_tot norm_unif ms_med coste")
        for r in s["reps"]:
            print(f"r{r['rep']} {r['cases']:>4} {r['errors']:>3} {r['malformed_retries']:>5} "
                  f"{r['raw_zero']:>8} {r['raw_uniform']:>8} {r['raw_total']:>7} "
                  f"{r['norm_uniform']:>10} {r['ms_med']} {r['cost']}")


if __name__ == "__main__":
    main()
