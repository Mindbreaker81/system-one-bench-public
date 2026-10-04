"""Informe de la matriz JEV-65: lee results/diag_qwen38_jev65_<bloque>_*/
y resume por variante/repetición validez, vectores nulos crudos, decisiones,
acierto contra el GT real, tiempos y — en la sección C — el efecto de rotar
una posición las claves choice en discrete.

  python3 -m jevbench.diag65_report nvfp4
  python3 -m jevbench.diag65_report nvfp4 --json

Correcciones respecto a diag63_report: missing parcial por ID de caso, parseo
y validación del raw por tipo de pregunta (choice/score/noul), mediana con
fallos además de la de éxitos, coste desconocido distinto de 0 y acuerdo por
decisiones (argmax/umbral), no por igualdad de floats redondeados.

Diagnóstico sobre 12/6 casos fijados: no es puntuación del marcador.
"""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from . import store
from .battery import load_phase
from .diag63 import DIAG_CASES
from .diag65 import ROT_CASES, SECTIONS, VARIANTS, rotate_choice


def _iter_cases():
    """phase -> {case_id: (questions, case)} for every case of sections A/B/C."""
    wanted = {}
    for ids in (DIAG_CASES, ROT_CASES):
        for phase, case_ids in ids.items():
            wanted.setdefault(phase, []).extend(
                i for i in case_ids if i not in wanted.get(phase, []))
    out = {}
    for phase, ids in wanted.items():
        qs, cases = load_phase(phase)
        by_id = {c.id: c for c in cases}
        out[phase] = {i: (qs, by_id[i]) for i in ids if i in by_id}
    return out


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl != -1 else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text


def _qtype(qs, qid):
    return (qs.get(qid) or {}).get("type")


def _validate_raw_value(qs, qid, val):
    """Classify one raw answer for question `qid` (probabilities contract).
    Returns (kind, detail): kind in ok|zero|uniform|scalar|invalid."""
    q = qs.get(qid) or {}
    qtype = q.get("type")
    if qtype == "noul":
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return "ok" if 0 <= val <= 1 else "invalid", val
        return "invalid", val
    if not isinstance(val, dict):
        return "invalid", val
    nums = {k: v for k, v in val.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v)}
    if qtype == "choice" and set(nums) != set(q.get("criteria") or {}):
        return "invalid", val
    if qtype == "score" and set(nums) != {str(i) for i in range(len(q.get("criteria") or []))}:
        return "invalid", val
    if not nums:
        return "invalid", val
    vals = list(nums.values())
    if any(v < 0 or v > 1 for v in vals):
        return "invalid", val
    if all(v == 0 for v in vals):
        return "zero", nums
    if (max(vals) - min(vals)) < 0.05:
        return "uniform", nums
    return "ok", nums


def _validate_raw_discrete(qs, qid, val):
    """Discrete contract: choice = one allowed label, score = int in range,
    noul = bool. Returns (kind, detail)."""
    q = qs.get(qid) or {}
    qtype = q.get("type")
    if qtype == "choice":
        ok = isinstance(val, str) and val in (q.get("criteria") or {})
        return ("ok" if ok else "invalid"), val
    if qtype == "score":
        ok = isinstance(val, int) and not isinstance(val, bool) \
            and 0 <= val < len(q.get("criteria") or [])
        return ("ok" if ok else "invalid"), val
    if qtype == "noul":
        return ("ok" if isinstance(val, bool) else "invalid"), val
    return "invalid", val


def _raw_answers(rec):
    """Parsed raw answers of every provider attempt: [(finish_reason, {qid: val}|None)]."""
    out = []
    attempts = rec.get("raw") or (rec.get("diag") or {}).get("raw") or []
    for att in attempts:
        resp = att.get("llm_response") or {}
        finish = ((att.get("debug_info") or {}).get("finish_reason")
                  or (resp.get("choices") or [{}])[0].get("finish_reason"))
        try:
            content = resp["choices"][0]["message"]["content"]
            data = json.loads(_extract_json(content))
            answers = data.get("answers") if isinstance(data, dict) else None
            if not isinstance(answers, dict) or not answers:
                answers = None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            answers = None
        out.append((finish, answers))
    return out


def _decisions(rec, qs):
    """Per-question decisions of a record, by official scorer criteria:
    choice label / score ordinal level / noul by 0.5 threshold."""
    d = {}
    for qid, a in (rec.get("answers") or {}).items():
        if not isinstance(a, dict) or qid not in qs:
            continue
        qtype = qs[qid]["type"]
        if qtype == "noul":
            v = a.get("noul")
            d[qid] = None if v is None else int(v >= 0.5)
        elif qtype == "score":
            if a.get("score") is not None:
                d[qid] = int(round(a["score"]))
            elif a.get("probabilities"):
                d[qid] = int(max(a["probabilities"], key=a["probabilities"].get))
        elif a.get("choice") is not None:
            d[qid] = a["choice"]
        elif a.get("probabilities"):
            d[qid] = max(a["probabilities"], key=a["probabilities"].get)
    return d


def analyze_case(rec, qs, discrete):
    """One case record -> compact flags (denominators kept apart)."""
    r = {"error": bool(rec.get("error")), "ms": rec.get("ms"),
         "cost": rec.get("cost"), "retries": 0, "attempts": 0,
         "raw_vectors": 0, "raw_zero": 0, "raw_uniform": 0,
         "raw_scalar": 0, "raw_invalid": 0, "raw_unparsed": 0,
         "raw_sum_min": None, "raw_sum_max": None, "raw_sum_off": 0,
         "finish_length": 0, "norm_uniform": 0, "first_option": 0,
         "choice_answered": 0}
    u = rec.get("usage") or {}
    r["retries"] = (u.get("n_retries_malformed") or 0)
    validate = _validate_raw_discrete if discrete else _validate_raw_value
    for finish, answers in _raw_answers(rec):
        r["attempts"] += 1
        if finish == "length":
            r["finish_length"] += 1
        if answers is None:
            r["raw_unparsed"] += 1
            continue
        for qid, val in answers.items():
            kind, det = validate(qs, qid, val)
            if (isinstance(det, dict) and det and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in det.values())):
                s = sum(det.values())
                r["raw_sum_min"] = s if r["raw_sum_min"] is None else min(r["raw_sum_min"], s)
                r["raw_sum_max"] = s if r["raw_sum_max"] is None else max(r["raw_sum_max"], s)
                if s < 0.95 or s > 1.05:
                    r["raw_sum_off"] += 1
            if kind == "zero":
                r["raw_vectors"] += 1
                r["raw_zero"] += 1
            elif kind == "uniform":
                r["raw_vectors"] += 1
                r["raw_uniform"] += 1
            elif kind == "ok":
                if isinstance(val, dict):
                    r["raw_vectors"] += 1
                else:
                    r["raw_scalar"] += 1
            else:
                r["raw_invalid"] += 1
    # normalized answers: uniform vectors and first-option discrete choices
    for qid, a in (rec.get("answers") or {}).items():
        if not isinstance(a, dict) or qid not in qs:
            continue
        probs = a.get("probabilities")
        if probs and not discrete:
            vals = list(probs.values())
            if vals and (max(vals) - min(vals)) < 0.05:
                r["norm_uniform"] += 1
        if qs[qid]["type"] == "choice" and a.get("choice") is not None:
            r["choice_answered"] += 1
            if a["choice"] == list(qs[qid]["criteria"])[0]:
                r["first_option"] += 1
    return r


def _accuracy(dec, case, qs):
    """(hits, total) of a decision map against the case GT."""
    hits = tot = 0
    for qid, gt in case.gt.items():
        if qid not in qs or dec.get(qid) is None:
            continue
        tot += 1
        hits += int(dec[qid] == gt or str(dec[qid]) == str(gt))
    return hits, tot


def _majority_baseline(phase_case, qs):
    """Accuracy of always answering each question's majority GT label."""
    hits = tot = 0
    for qid, q in qs.items():
        votes = defaultdict(int)
        for _, case in phase_case.values():
            if qid in case.gt:
                votes[str(case.gt[qid])] += 1
        if not votes:
            continue
        best = max(votes, key=votes.get)
        for _, case in phase_case.values():
            if qid in case.gt:
                tot += 1
                hits += int(str(case.gt[qid]) == best)
    return hits, tot


def _med(values):
    return round(statistics.median(values)) if values else None


def collect(config):
    """Scan every diag_qwen38_jev65_<config>_* run dir -> structured summary."""
    phase_case = _iter_cases()
    cells = {}          # run_name -> {"meta": ..., "cases": {pc: analysis}}
    decs = {}           # run_name -> {pc: {qid: decision}}
    missing = {}
    root = store.ROOT
    for d in sorted(root.glob(f"diag_qwen38_jev65_{config}_*_r*")):
        run = d.name
        cells[run] = {"meta": None, "cases": {}}
        decs[run] = {}
        # casos esperados: la especificación fijada de la sección (diag.cases
        # grabado coincide); una fase entera ausente cuenta como missing
        _, _, _, rot, _ = _slug(run, config)
        spec = ROT_CASES if rot else DIAG_CASES
        expected = {f"{ph}/{cid}": None for ph, ids in spec.items()
                    for cid in ids}
        for ph in store.runs_in(d.name):
            doc = store.load(run, ph) or {}
            cells[run]["meta"] = (doc.get("meta") or {})
            diag = cells[run]["meta"].get("diag") or {}
            discrete = diag.get("mode") == "discrete"
            case_map = phase_case.get(ph) or {}
            for cid in (diag.get("cases") or []):
                expected[f"{ph}/{cid}"] = None
            for cid, rec in (doc.get("cases") or {}).items():
                pc = f"{ph}/{cid}"
                if cid not in case_map:
                    continue
                qs, case = case_map[cid]
                if rot:
                    # en los runs rotados la "primera opción" es la del orden
                    # rotado: el contador tiene que ver el mismo orden que el
                    # modelo
                    qs = rotate_choice(qs, 1)
                cells[run]["cases"][pc] = analyze_case(rec, qs, discrete)
                decs[run][pc] = _decisions(rec, qs)
        missing[run] = sorted(set(expected) - set(cells[run]["cases"]))
    return cells, decs, missing, phase_case


def _row(pc):
    n = len(pc)
    costs = [r["cost"] for r in pc.values()]
    known = [c for c in costs if c is not None]
    ms_all = [r["ms"] for r in pc.values() if r["ms"] is not None]
    ms_ok = [r["ms"] for r in pc.values() if r["ms"] is not None and not r["error"]]
    return {
        "cases": n,
        "errors": sum(1 for r in pc.values() if r["error"]),
        "malformed_retries": sum(r["retries"] for r in pc.values()),
        "raw_zero": sum(r["raw_zero"] for r in pc.values()),
        "raw_uniform": sum(r["raw_uniform"] for r in pc.values()),
        "raw_vectors": sum(r["raw_vectors"] for r in pc.values()),
        "raw_scalar": sum(r["raw_scalar"] for r in pc.values()),
        "raw_invalid": sum(r["raw_invalid"] for r in pc.values()),
        "raw_unparsed": sum(r["raw_unparsed"] for r in pc.values()),
        "raw_absent": sum(1 for r in pc.values()
                          if r["attempts"] == 0 and not r["error"]),
        "raw_sum_min": (min(r["raw_sum_min"] for r in pc.values()
                           if r["raw_sum_min"] is not None)
                        if any(r["raw_sum_min"] is not None for r in pc.values())
                        else None),
        "raw_sum_max": (max(r["raw_sum_max"] for r in pc.values()
                           if r["raw_sum_max"] is not None)
                        if any(r["raw_sum_max"] is not None for r in pc.values())
                        else None),
        "raw_sum_off": sum(r["raw_sum_off"] for r in pc.values()),
        "finish_length": sum(r["finish_length"] for r in pc.values()),
        "norm_uniform": sum(r["norm_uniform"] for r in pc.values()),
        "first_option": sum(r["first_option"] for r in pc.values()),
        "choice_answered": sum(r["choice_answered"] for r in pc.values()),
        "ms_med": _med(ms_all),
        "ms_med_ok": _med(ms_ok),
        "cost": round(sum(known), 5) if known else None,
        "cost_unknown": n - len(known),
    }


def _slug(run, config):
    """run name -> (variant, mode, route, rot, rep) parsed from the name."""
    rest = run[len(f"diag_qwen38_jev65_{config}_"):]
    rot = "_rot1_" in rest
    rep = int(rest.rsplit("_r", 1)[1])
    body = rest.rsplit("_r", 1)[0].replace("_rot1", "")
    variant, mode, route = body.rsplit("_", 2)
    return variant, mode, route, rot, rep


def summarize(config, cells, decs, missing, phase_case):
    groups = defaultdict(dict)   # (variant, mode, route, rot) -> rep -> per-case
    for run, data in cells.items():
        variant, mode, route, rot, rep = _slug(run, config)
        groups[(variant, mode, route, rot)][rep] = data["cases"]
    out = {}
    for key, reps in sorted(groups.items()):
        rows = [dict(rep=rep, **_row(reps.get(rep) or {})) for rep in (1, 2, 3)]
        # accuracy vs real GT, and majority baseline over the same cases
        acc = {}
        for rep, pc in reps.items():
            hits = tot = 0
            for pcc in (pc or {}):
                ph, cid = pcc.split("/", 1)
                if cid not in (phase_case.get(ph) or {}):
                    continue
                qs, case = phase_case[ph][cid]
                h, t = _accuracy((decs_of(cells, decs, config, key, rep) or {}).get(pcc) or {},
                                 case, qs)
                hits += h
                tot += t
            acc[rep] = (hits, tot)
        # decision agreement across reps (same case, same cell)
        variant, mode, route, rot = key
        agree = tot_a = 0
        run_of = {rep: f"diag_qwen38_jev65_{config}_{variant}_{mode}_{route}"
                       f"{'_rot1' if rot else ''}_r{rep}" for rep in (1, 2, 3)}
        for pcc, d1 in (decs.get(run_of.get(1)) or {}).items():
            for rep in (2, 3):
                d2 = (decs.get(run_of.get(rep)) or {}).get(pcc) or {}
                for qid, v in d1.items():
                    if v is not None and qid in d2 and d2[qid] is not None:
                        tot_a += 1
                        agree += int(v == d2[qid])
        spec = ROT_CASES if rot else DIAG_CASES
        expected_all = sorted(f"{ph}/{cid}" for ph, ids in spec.items()
                              for cid in ids)
        out[key] = {"reps": rows, "accuracy": acc,
                    "missing": {rep: (missing[run_of[rep]] if run_of[rep] in missing
                                     else expected_all)
                                for rep in (1, 2, 3)},
                    "decision_agreement": (agree, tot_a)}
    # majority baseline per phase subset (diag 12 / rot 6)
    baselines = {}
    for ph, m in phase_case.items():
        if m:
            qs = m[next(iter(m))][0]
            baselines[ph] = _majority_baseline(m, qs)
    return out, baselines


def decs_of(cells, decs, config, key, rep):
    variant, mode, route, rot = key
    run = (f"diag_qwen38_jev65_{config}_{variant}_{mode}_{route}"
           f"{'_rot1' if rot else ''}_r{rep}")
    return decs.get(run) or {}


def compare_rotation(cells, decs, config, phase_case):
    """Section C check: rot1 vs same-variant non-rot decisions on the shared
    cases — how often the chosen label changes after rotating (position-bias
    signal) and whether accuracy on those cases degrades."""
    rows = []
    for variant in ("v1_typesafe", "v2_simple"):
        for rep in (1, 2, 3):
            base = f"diag_qwen38_jev65_{config}_{variant}_disc_struct_r{rep}"
            rot = f"diag_qwen38_jev65_{config}_{variant}_disc_struct_rot1_r{rep}"
            d_base, d_rot = decs.get(base) or {}, decs.get(rot) or {}
            same = diff = tot = 0
            acc_base = acc_rot = acc_tot = 0
            only_base = only_rot = unpaired = 0
            rot_ids = {f"{ph}/{cid}" for ph, ids in ROT_CASES.items()
                       for cid in ids}
            for pcc in sorted(rot_ids):
                d1, d2 = d_base.get(pcc) or {}, d_rot.get(pcc) or {}
                ph, cid = pcc.split("/", 1)
                if cid not in (phase_case.get(ph) or {}):
                    continue
                qs, case = phase_case[ph][cid]
                shared = {qid for qid, v in d1.items()
                          if v is not None and d2.get(qid) is not None}
                if not shared:
                    # el caso solo respondió en un lado (o en ninguno):
                    # no entra en ninguna comparación pareada
                    unpaired += int(bool(d1) != bool(d2))
                    continue
                for qid in sorted(shared):
                    if (qs.get(qid) or {}).get("type") != "choice":
                        continue
                    tot += 1
                    same += int(d1[qid] == d2[qid])
                    diff += int(d1[qid] != d2[qid])
                # acierto pareado: ambos numeradores sobre las mismas
                # preguntas (respondidas por los dos lados y con GT)
                hb = ht = hr = 0
                for qid in sorted(shared):
                    if qid not in case.gt:
                        continue
                    ht += 1
                    hb += int(d1[qid] == case.gt[qid]
                              or str(d1[qid]) == str(case.gt[qid]))
                    hr += int(d2[qid] == case.gt[qid]
                              or str(d2[qid]) == str(case.gt[qid]))
                acc_base += hb
                acc_rot += hr
                acc_tot += ht
                # preguntas con GT respondidas solo por un lado, aparte
                only_base += sum(
                    1 for qid, v in d1.items()
                    if v is not None and d2.get(qid) is None
                    and qid in case.gt)
                only_rot += sum(
                    1 for qid, v in d2.items()
                    if v is not None and d1.get(qid) is None
                    and qid in case.gt)
            rows.append({"variant": variant, "rep": rep,
                         "choice_same": same, "choice_diff": diff,
                         "choice_total": tot,
                         "acc_base": acc_base, "acc_rot": acc_rot,
                         "acc_total": acc_tot,
                         "acc_base_only": only_base,
                         "acc_rot_only": only_rot,
                         "unpaired_cases": unpaired})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="slug del bloque (nvfp4, fp8)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cells, decs, missing, phase_case = collect(args.config)
    summary, baselines = summarize(args.config, cells, decs, missing, phase_case)
    rot_cmp = compare_rotation(cells, decs, args.config, phase_case)

    if args.json:
        print(json.dumps({"config": args.config, "summary": {
            "|".join(map(str, k)): v for k, v in summary.items()},
            "rotation_compare": rot_cmp,
            "majority_baseline": baselines}, indent=1))
        return

    print(f"# diag65 {args.config}")
    for ph, (h, t) in baselines.items():
        print(f"baseline mayoría {ph}: {h}/{t}")
    for key, s in sorted(summary.items()):
        variant, mode, route, rot = key
        agree, tot = s["decision_agreement"]
        print(f"\n## {variant} {mode} {route}{' rot1' if rot else ''}"
              f"  (acuerdo decisiones entre reps: {agree}/{tot})")
        print("rep casos err reint zero unif vec inv unp soff noraw len 1st/ch ms_med ms_ok acierto miss")
        for r in s["reps"]:
            rep = r["rep"]
            hits, tot_q = s["accuracy"].get(rep, (0, 0))
            fo = f"{r['first_option']}/{r['choice_answered']}" if r["choice_answered"] else "-"
            print(f"r{rep} {r['cases']:>4} {r['errors']:>3} {r['malformed_retries']:>5} "
                  f"{r['raw_zero']:>4} {r['raw_uniform']:>4} {r['raw_vectors']:>3} "
                  f"{r['raw_invalid']:>3} {r['raw_unparsed']:>3} {r['raw_sum_off']:>4} "
                  f"{r['raw_absent']:>3} "
                  f"{r['finish_length']:>3} "
                  f"{fo:>5} {r['ms_med']} {r['ms_med_ok']} {hits}/{tot_q} "
                  f"{len(s['missing'].get(rep) or [])}")
    if rot_cmp:
        print("\n## rotación choice (discrete): misma etiqueta tras rotar")
        for r in rot_cmp:
            extra = ""
            if r["acc_base_only"] or r["acc_rot_only"]:
                extra = (f"  (preguntas solo respondidas: base {r['acc_base_only']},"
                         f" rot {r['acc_rot_only']})")
            if r["unpaired_cases"]:
                extra += f"  (casos sin pareja: {r['unpaired_cases']})"
            print(f"{r['variant']} r{r['rep']}: {r['choice_same']}/{r['choice_total']}"
                  f" ({r['choice_diff']} cambian)  acierto pareado base {r['acc_base']}/"
                  f"{r['acc_total']} rot {r['acc_rot']}/{r['acc_total']}{extra}")


if __name__ == "__main__":
    main()
