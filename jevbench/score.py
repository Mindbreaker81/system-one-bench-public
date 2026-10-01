"""Score one or more runs on the battery.

  python -m jevbench.score jev_v2 anyjev_qwen3_1.7b            # tables to stdout
  python -m jevbench.score --summary jev_v3 decider_4b ...      # one headline row per run
  python -m jevbench.score jev_v2 laya_v2 --vs jev_v2           # + paired McNemar vs a reference
  python -m jevbench.score jev_v2 --phases adv1,adv2 --json out.json
"""
import argparse
import json
import math

from . import metrics as M
from . import store
from .battery import EXTRA_PHASES, PHASES, gt_problems, load_phase


def score_run(run, phase):
    doc = store.load(run, phase)
    if doc is None:
        return None
    qs, cases = load_phase(phase)
    recs = doc["cases"]
    preds, errors = {}, []
    for c in cases:
        r = recs.get(c.id)
        if r is None or "error" in r:
            errors.append(c.id)
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


ADJ_PHASES = PHASES + EXTRA_PHASES + ["adv4", "adv5"]


def adjusted(run):
    """Margen sobre la línea base trivial: media por fase de (acierto - mayoría)/(100 - mayoría)
    x100. 100 = perfecto, 0 = responder siempre lo más frecuente, <0 = peor que el trivial.
    Returns (valor, n_fases completas)."""
    vals, n = [], 0
    for ph in ADJ_PHASES:
        x = score_run(run, ph)
        if not x or x["n_ok"] < x["n"]:
            continue
        n += 1
        b = baseline(ph)["pct"]
        if b < 100:  # ood está saturado (mayoría=100 %): se excluye de la media
            vals.append((x["pct"] - b) / (100 - b))
    return (100 * sum(vals) / len(vals), n) if vals else (None, n)


def summary(runs):
    """One row per run with the headline numbers of every phase; returns the markdown table."""
    lines = []
    lines.append("| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total "
          "| triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana |")
    lines.append("|" + "---|" * 15)
    base = {ph: baseline(ph) for ph in PHASES + EXTRA_PHASES}
    for run in runs:
        r = {ph: score_run(run, ph) for ph in PHASES + EXTRA_PHASES}
        if not any(r.values()):
            continue
        adj, n_adj = adjusted(run)
        adj_s = f"{adj:.0f}" + ("*" if n_adj < len(ADJ_PHASES) else "") if adj is not None else "—"

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
            fmt(ms[len(ms) // 2], 0) if ms else "—"]) + " |")
    b = base
    lines.append("| " + " | ".join([
        "*mayoría (oráculo)*", "0", fmt(b["triage_es"]["pct"]), fmt(b["triage_en"]["pct"]),
        f"{b['triage_es']['per_q']['department'] + b['triage_en']['per_q']['department']:g}/28",
        fmt(b["papers32"]["pct"]), "—", "0/10",
        f"{b['adv1']['per_q']['department'] + b['adv2']['per_q']['department']:g}/20",
        fmt((b["adv1"]["pct"] + b["adv2"]["pct"]) / 2),
        f"{fmt(b['triage_ext_es']['pct'])} / {fmt(b['triage_ext_en']['pct'])}",
        f"{b['adv3']['per_q']['department']:g}/{b['adv3']['n']}", fmt(b["adv3"]["pct"]), "—", "—"]) + " |")
    lines.append("\n*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 "
                 "(ood queda excluida: la mayoría ya acierta todo). "
                 "0 = responder siempre lo más frecuente, <0 = peor que el trivial; "
                 f"`*` = no tiene las {len(ADJ_PHASES)} fases.*")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--phases", default=",".join(PHASES))
    ap.add_argument("--vs", help="reference run for paired tests")
    ap.add_argument("--json", help="write full summaries to this file")
    ap.add_argument("--misses", action="store_true", help="list missed cases per question")
    ap.add_argument("--summary", action="store_true", help="one headline row per run, then exit")
    args = ap.parse_args()
    if args.summary:
        print(summary(args.runs))
        return
    runs = list(dict.fromkeys(args.runs + ([args.vs] if args.vs else [])))
    dump = {}
    for phase in args.phases.split(","):
        res = [score_run(r, phase) for r in runs]
        if not any(res):
            continue
        ref = next((x for x in res if x and x["run"] == args.vs), None)
        print_phase(phase, res, ref)
        if args.misses:
            for r in res:
                if r:
                    print(f"\n{r['run']} fallos: " + "; ".join(f"{q}: {', '.join(v)}" for q, v in r["missed"].items() if v))
        dump[phase] = [{k: v for k, v in x.items() if k not in ("hits", "ms_all")} for x in res if x]
    if args.json:
        with open(args.json, "w") as f:
            json.dump(dump, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
