"""Score one or more runs on the battery.

  python -m jevbench.score jev_v2 anyjev_qwen3_1.7b            # tables to stdout
  python -m jevbench.score --summary jev_v3 decider_4b ...      # one headline row per run
  python -m jevbench.score jev_v2 laya_v2 --vs jev_v2           # + paired McNemar vs a reference
  python -m jevbench.score jev_v2 --phases adv1,adv2 --json out.json
"""
import argparse
import json
import math
import random

from . import metrics as M
from . import store
from .battery import EXTRA_PHASES, PHASES, gt_problems, load_phase


def _strip_fence(text):
    """Réplica de `_extract_json` de system-one-adapter 0.2.1, sin importarla:
    quita la cerca ``` opcional, con o sin etiqueta `json` y con o sin saltos."""
    text = text.strip()
    if text.startswith("```"):
        text = text[3:]
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def _attempt_answers(rec):
    """`answers` parseadas de cada intento guardado en `raw` por el adaptador
    llm (lista de {llm_response, ...}); `rec["diag"]["raw"]` como respaldo.

    Solo entiende el formato OpenAI Chat Completions del adaptador llm
    (`llm_response.choices[0].message.content`); otros formatos de raw
    (Anthropic/Gemini nativos, dicts de systemone_http/gliner/tev1) o
    intentos incompletos (`content` None, JSON roto) devuelven None en su
    posición — un intento no interpretable no es evidencia de ausencia."""
    out = []
    attempts = rec.get("raw") or (rec.get("diag") or {}).get("raw") or []
    for att in attempts:
        if not isinstance(att, dict):
            out.append(None)
            continue
        resp = att.get("llm_response") or {}
        try:
            content = resp["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                out.append(None)
                continue
            data = json.loads(_strip_fence(content))
            answers = data.get("answers") if isinstance(data, dict) else None
            out.append(answers if isinstance(answers, dict) and answers else None)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            out.append(None)
    return out


def _null_expected_keys(q):
    """Claves que debe cubrir un vector para contarlo como nulo (misma
    equivalencia que diag65_report._validate_raw_value: fuera de eso es
    `invalid`, no `zero`)."""
    t = q.get("type")
    if t == "choice":
        return set(q.get("criteria") or {})
    if t == "score":
        return {str(i) for i in range(len(q.get("criteria") or []))}
    return None


def _is_null_vector(q, v):
    """True si `v` cubre exactamente las claves esperadas de la pregunta y
    todos sus valores numéricos son 0."""
    keys = _null_expected_keys(q)
    if keys is None or not isinstance(v, dict):
        return False
    nums = {k: x for k, x in v.items()
            if isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x)}
    return bool(nums) and set(nums) == keys and all(x == 0 for x in nums.values())


def null_vector_qids(rec, qs):
    """QIDs choice/score cuyo vector crudo es nulo (todas las opciones 0.0) en el
    último intento con respuesta parseada del `raw` guardado. Devuelve None si
    el raw está ausente o no se puede interpretar: «desconocido» no es «sin
    nulos». Misma detección que jev67._null_qids /
    diag65_report._validate_raw_value ("zero"), extendida a score y al formato
    OpenAI chat del adaptador llm únicamente."""
    answers = next((a for a in reversed(_attempt_answers(rec)) if a), None)
    if answers is None:
        return None
    return {qid for qid, q in qs.items() if _is_null_vector(q, answers.get(qid))}


def score_run(run, phase, null_as_error=False):
    doc = store.load(run, phase)
    if doc is None:
        return None
    qs, cases = load_phase(phase)
    recs = doc["cases"]
    preds, errors = {}, []
    n_null = n_unknown = 0
    for c in cases:
        r = recs.get(c.id)
        if r is None or "error" in r:
            errors.append(c.id)
            continue
        # sensibilidad (JEV-71 §3): un vector crudo nulo que el adaptador
        # normalizó a uniforme cuenta como error, no como respuesta. Raw
        # ausente o no interpretable cuenta aparte: no es «sin nulos».
        if null_as_error:
            qids = null_vector_qids(r, qs)
            if qids is None:
                n_unknown += 1
            elif qids:
                errors.append(c.id)
                n_null += 1
                continue
        preds[c.id] = {q: M.normalize(r["answers"][q], qs[q]) for q in qs}
    ok = [c for c in cases if c.id in preds]
    per_q = {q: sum(M.point(qs[q], preds[c.id][q], c.gt[q]) for c in ok) for q in qs}
    per_case = [sum(M.point(qs[q], preds[c.id][q], c.gt[q]) for q in qs) / len(qs) for c in ok]
    hits = {q: [M.exact(qs[q], preds[c.id][q], c.gt[q]) if c.id in preds else False for c in cases] for q in qs}
    border = sum(1 for c in ok for q in qs
                 if qs[q]["type"] == "noul" and M.BORDER[0] <= preds[c.id][q]["value"] <= M.BORDER[1])
    calib, ece = M.calibration(qs, preds, ok)
    out = {
        "run": run, "phase": phase, "meta": doc.get("meta", {}),
        "n": len(cases), "n_ok": len(ok), "errors": errors,
        "pct": 100 * sum(per_case) / len(ok) if ok else float("nan"),
        "ci": tuple(100 * x for x in M.bootstrap_ci(per_case)),
        "per_q": per_q, "hits": hits, "border": border, "calib": calib, "ece": ece,
        "missed": {q: [c.id for c in ok if M.point(qs[q], preds[c.id][q], c.gt[q]) < 1] for q in qs},
        "per_case": per_case, "null_as_error": n_null, "null_unknown": n_unknown,
    }
    if phase == "papers32" and ok:
        ids = [c.id for c in ok]
        gts = {c.id: c.gt for c in ok}
        out["spearman"] = M.spearman([preds[i]["relevance"]["value"] for i in ids], [gts[i]["relevance"] for i in ids])
        out["cascade"] = M.cascade(ids, preds, gts)
    ms = [r["ms"] for r in recs.values() if r.get("ms") is not None]
    out["ms"] = sum(ms) / len(ms) if ms else None
    out["ms_all"] = ms
    out["cost"] = sum(r.get("cost") or 0 for r in recs.values())
    # Calidad de salida: decisiones `choice` casi uniformes (máx−mín < 0.05). La
    # normalización del adaptador convierte vectores de ceros en uniformes, así
    # que la tasa detecta la emisión degenerada de JEV-57 aunque el raw no esté.
    cps = [a["probabilities"] for r in recs.values() if "error" not in r
           for a in (r.get("answers") or {}).values()
           if a.get("type") == "choice" and a.get("probabilities")]
    out["n_choice"] = len(cps)
    out["n_near_uniform"] = sum(1 for p in cps if max(p.values()) - min(p.values()) < 0.05)
    return out


def baseline(phase):
    qs, cases = load_phase(phase)
    b = M.majority_baseline(qs, cases)
    return {"per_q": {q: v["points"] for q, v in b.items()}, "answers": {q: v["answer"] for q, v in b.items()},
            "pct": 100 * sum(v["points"] for v in b.values()) / (len(cases) * len(qs)), "n": len(cases)}


def fmt(x, nd=1):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def print_phase(phase, results, ref=None):
    qs, cases = load_phase(phase)
    n = len(cases)
    names = list(qs)
    print(f"\n### {phase} (n={n})\n")
    for cid, q, v in gt_problems(phase):
        print(f"> AVISO GT: {cid}.{q} = {v!r} no es una opción válida (nadie puede acertarlo)\n")
    head = ["run", "total %", "IC95"] + names + ["Brier noul", "ECE", "0.45–0.55", "ms"]
    if phase == "papers32":
        head[3 + len(names):3 + len(names)] = ["Spearman", "casc cv2", "casc LOO", "skip cv2/LOO"]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for r in results:
        if r is None:
            continue
        brier = [v["brier"] for q, v in r["calib"].items() if qs[q]["type"] == "noul"]
        row = [r["run"] + (f" ({r['n_ok']}/{n})" if r["n_ok"] < n else ""),
               fmt(r["pct"]), f"{fmt(r['ci'][0], 0)}–{fmt(r['ci'][1], 0)}"]
        row += [f"{r['per_q'][q]:g}/{r['n_ok']}" for q in names]
        if phase == "papers32":
            cz = r.get("cascade", {})
            row += [fmt(r.get("spearman"), 3), f"{cz.get('cv2')}/{cz.get('n')}", f"{cz.get('loo')}/{cz.get('n')}",
                    f"{cz.get('skip_recall_cv2')}/{cz.get('skip_recall_loo')} de {cz.get('n_skip')}"]
        row += [fmt(sum(brier) / len(brier), 3) if brier else "—", fmt(r["ece"], 3), str(r["border"]), fmt(r["ms"], 0)]
        print("| " + " | ".join(row) + " |")
    b = baseline(phase)
    row = ["*mayoría (oráculo)*", fmt(b["pct"]), ""] + [f"{b['per_q'][q]:g}/{n}" for q in names]
    row += [""] * (len(head) - len(row))
    print("| " + " | ".join(row) + " |")
    if ref is not None:
        print(f"\nMcNemar exacto vs `{ref['run']}` (aciertos estrictos; b = solo ref acierta, c = solo el otro):\n")
        for r in results:
            if r is None or r["run"] == ref["run"]:
                continue
            parts = []
            for q in names:
                b_, c_, p = M.mcnemar(ref["hits"][q], r["hits"][q])
                parts.append(f"{q} b={b_} c={c_} p={p:.2f}")
            print(f"- {r['run']}: " + "; ".join(parts))
    for r in results:
        if r and r.get("null_as_error"):
            print(f"> --null-as-error: {r['run']}: {r['null_as_error']} caso(s) con vector "
                  "crudo nulo contados como error (fuera del % de la fase y del "
                  "agregado si la deja incompleta)")
        if r and r.get("null_unknown"):
            print(f"> --null-as-error: {r['run']}: {r['null_unknown']} caso(s) sin raw "
                  "interpretable (desconocido: ni nulo ni limpio demostrado)")


ADJ_PHASES = PHASES + EXTRA_PHASES + ["adv4", "adv5"]


def adjusted(run, null_as_error=False):
    """Margen sobre la línea base trivial: media por fase de (acierto - mayoría)/(100 - mayoría)
    x100. 100 = perfecto, 0 = responder siempre lo más frecuente, <0 = peor que el trivial.
    Returns (valor, n_fases completas)."""
    vals, n = [], 0
    for ph in ADJ_PHASES:
        x = score_run(run, ph, null_as_error=null_as_error)
        if not x or x["n_ok"] < x["n"]:
            continue
        n += 1
        b = baseline(ph)["pct"]
        if b < 100:  # ood está saturado (mayoría=100 %): se excluye de la media
            vals.append((x["pct"] - b) / (100 - b))
    return (100 * sum(vals) / len(vals), n) if vals else (None, n)


def adjusted_ci(run, iters=2000, seed=0, null_as_error=False):
    """IC bootstrap del ajustado agregado (JEV-71 §4): remuestreo estratificado de
    CASOS dentro de cada fase (misma fórmula que `adjusted` y mismas fases —
    con `null_as_error` salen las mismas que del centro, ood excluida) con
    semilla fija. Devuelve (valor, lo, hi) — lo/hi por percentil 2.5/97.5.

    Supuestos: los registros se remuestrean como independientes — no agrupa
    las traducciones ES/EN del mismo caso ni los duplicados conocidos
    (p. ej. papers con el mismo PMID), y mide variación de muestreo del set,
    no la variación entre ejecuciones del modelo."""
    phases = []
    for ph in ADJ_PHASES:
        x = score_run(run, ph, null_as_error=null_as_error)
        if not x or x["n_ok"] < x["n"]:
            continue
        b = baseline(ph)["pct"]
        if b < 100:
            phases.append((x["per_case"], b))
    if not phases:
        return (None, None, None)
    value = 100 * sum((100 * sum(pc) / len(pc) - b) / (100 - b) for pc, b in phases) / len(phases)
    rng = random.Random(seed)
    reps = []
    for _ in range(iters):
        vals = []
        for pc, b in phases:
            n = len(pc)
            m = 100 * sum(pc[rng.randrange(n)] for _ in range(n)) / n
            vals.append((m - b) / (100 - b))
        reps.append(100 * sum(vals) / len(vals))
    reps.sort()
    return value, reps[int(iters * 0.025)], reps[int(iters * 0.975) - 1]


def null_report(run):
    """Diagnóstico de la sensibilidad --null-as-error sobre ADJ_PHASES:
    (casos convertidos a error, fases completas que salen del agregado,
    casos sin raw interpretable)."""
    conv = unknown = 0
    dropped = []
    for ph in ADJ_PHASES:
        x1 = score_run(run, ph, null_as_error=True)
        if not x1:
            continue
        conv += x1["null_as_error"]
        unknown += x1["null_unknown"]
        x0 = score_run(run, ph)
        if (x0 and x0["n_ok"] == x0["n"] and baseline(ph)["pct"] < 100
                and x1["n_ok"] < x1["n"]):
            dropped.append(ph)
    return conv, dropped, unknown


def summary(runs, adj_ci=False, null_as_error=False):
    """One row per run with the headline numbers of every phase; returns the markdown table.
    adj_ci (JEV-71 §4) añade el IC95 bootstrap del ajustado; null_as_error (§3)
    cuenta como error las respuestas con vector crudo nulo en `raw`."""
    lines = []
    head = "| run | ajustado |" + (" IC95 ajust. |" if adj_ci else "") + \
        " triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total " \
        "| triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |"
    lines.append(head)
    lines.append("|" + "---|" * (16 + adj_ci))
    base = {ph: baseline(ph) for ph in PHASES + EXTRA_PHASES}
    null_reports = {}
    for run in runs:
        r = {ph: score_run(run, ph, null_as_error=null_as_error) for ph in PHASES + EXTRA_PHASES}
        if not any(r.values()):
            continue
        adj, n_adj = adjusted(run, null_as_error=null_as_error)
        if null_as_error:
            null_reports[run] = null_report(run)
        adj_s = f"{adj:.0f}" + ("*" if n_adj < len(ADJ_PHASES) else "") if adj is not None else "—"
        if adj_ci:
            v, lo, hi = adjusted_ci(run, null_as_error=null_as_error)
            adj_s += f" | {f'{lo:.0f}–{hi:.0f}' if lo is not None else '—'}"

        def g(ph, f, d="—"):
            return f(r[ph]) if r[ph] else d
        adv = [r[p] for p in ("adv1", "adv2") if r[p]]
        briers = [v["brier"] for x in r.values() if x for q, v in x["calib"].items()
                  if load_phase(x["phase"])[0][q]["type"] == "noul"]
        ms = sorted(m for x in r.values() if x for m in x["ms_all"])
        lines.append("| " + " | ".join([
            run, adj_s, g("triage_es", lambda x: fmt(x["pct"])), g("triage_en", lambda x: fmt(x["pct"])),
            f"{sum(r[p]['per_q']['department'] for p in ('triage_es', 'triage_en') if r[p]):g}/28",
            g("papers32", lambda x: fmt(x["pct"])), g("papers32", lambda x: fmt(x.get("spearman"), 2)),
            g("papers32", lambda x: f"{x['cascade']['skip_recall_loo']}/{x['cascade']['n_skip']}"),
            f"{sum(x['per_q']['department'] for x in adv):g}/{sum(x['n_ok'] for x in adv)}" if adv else "—",
            fmt(sum(x["pct"] for x in adv) / len(adv)) if adv else "—",
            f"{g('triage_ext_es', lambda x: fmt(x['pct']))} / {g('triage_ext_en', lambda x: fmt(x['pct']))}",
            g("adv3", lambda x: f"{x['per_q']['department']:g}/{x['n_ok']}"), g("adv3", lambda x: fmt(x["pct"])),
            fmt(sum(briers) / len(briers), 3) if briers else "—",
            fmt(ms[len(ms) // 2], 0) if ms else "—",
            f"{sum(x['n_near_uniform'] for x in r.values() if x)}/{sum(x['n_choice'] for x in r.values() if x)}"]) + " |")
    b = base
    lines.append("| " + " | ".join([
        "*mayoría (oráculo)*", "0"] + (["—"] if adj_ci else []) + [
        fmt(b["triage_es"]["pct"]), fmt(b["triage_en"]["pct"]),
        f"{b['triage_es']['per_q']['department'] + b['triage_en']['per_q']['department']:g}/28",
        fmt(b["papers32"]["pct"]), "—", "0/10",
        f"{b['adv1']['per_q']['department'] + b['adv2']['per_q']['department']:g}/20",
        fmt((b["adv1"]["pct"] + b["adv2"]["pct"]) / 2),
        f"{fmt(b['triage_ext_es']['pct'])} / {fmt(b['triage_ext_en']['pct'])}",
        f"{b['adv3']['per_q']['department']:g}/{b['adv3']['n']}", fmt(b["adv3"]["pct"]), "—", "—", "—"]) + " |")
    lines.append("\n*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 "
                 "(ood queda excluida: la mayoría ya acierta todo). "
                 "0 = responder siempre lo más frecuente, <0 = peor que el trivial; "
                 f"`*` = no tiene las {len(ADJ_PHASES)} fases.*")
    if adj_ci:
        lines.append("\n*IC95 ajust.: bootstrap estratificado de casos dentro de cada fase "
                     "(2000 réplicas, semilla fija, percentil 2.5/97.5; supone registros "
                     "independientes — no agrupa traducciones ES/EN ni duplicados, ni mide "
                     "variación entre ejecuciones del modelo).*")
    if null_as_error:
        parts = []
        for r, (conv, dropped, unk) in null_reports.items():
            s = f"{r}: {conv} caso(s) convertidos"
            if dropped:
                s += f" — fases que salen del agregado: {', '.join(dropped)}"
            if unk:
                s += f" ({unk} sin raw interpretable)"
            parts.append(s)
        lines.append("\n*--null-as-error (sensibilidad, formato OpenAI chat del adaptador llm): "
                     + "; ".join(parts) +
                     ". Un caso convertido sale del % de su fase y, si la deja incompleta, "
                     "también del agregado — los valores con distinta cobertura no son "
                     "comparables entre runs ni con el ajustado oficial.*")
    lines.append("\n*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--phases", default=",".join(PHASES))
    ap.add_argument("--vs", help="reference run for paired tests")
    ap.add_argument("--json", help="write full summaries to this file")
    ap.add_argument("--misses", action="store_true", help="list missed cases per question")
    ap.add_argument("--summary", action="store_true", help="one headline row per run, then exit")
    ap.add_argument("--adj-ci", action="store_true",
                    help="con --summary: añade el IC95 bootstrap del ajustado agregado "
                         "(2000 réplicas estratificadas por fase, semilla fija; supone "
                         "registros independientes: no agrupa traducciones ES/EN ni "
                         "duplicados, ni mide variación entre ejecuciones)")
    ap.add_argument("--null-as-error", action="store_true",
                    help="sensibilidad: respuestas choice/score con vector crudo nulo "
                         "en el raw guardado cuentan como error, no como uniforme. "
                         "Solo lee el formato OpenAI chat del adaptador llm "
                         "(llm_response.choices[0].message.content); raw ausente o no "
                         "interpretable se cuenta aparte como «desconocido». Los casos "
                         "convertidos salen del %% de su fase y pueden sacarla del "
                         "agregado: coberturas distintas no son comparables")
    args = ap.parse_args()
    if args.summary:
        print(summary(args.runs, adj_ci=args.adj_ci, null_as_error=args.null_as_error))
        return
    runs = list(dict.fromkeys(args.runs + ([args.vs] if args.vs else [])))
    dump = {}
    for phase in args.phases.split(","):
        res = [score_run(r, phase, null_as_error=args.null_as_error) for r in runs]
        if not any(res):
            continue
        ref = next((x for x in res if x and x["run"] == args.vs), None)
        print_phase(phase, res, ref)
        if args.misses:
            for r in res:
                if r:
                    print(f"\n{r['run']} fallos: " + "; ".join(f"{q}: {', '.join(v)}" for q, v in r["missed"].items() if v))
        dump[phase] = [{k: v for k, v in x.items() if k not in ("hits", "ms_all", "per_case")} for x in res if x]
    if args.json:
        with open(args.json, "w") as f:
            json.dump(dump, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
