"""JEV-70 §7–§8 y revisión 3: auditoría y clasificación de las celdas de DiffusionGemma.

  python -m jevbench.dgemma_report [--json out.json]

- auditoría §7: cobertura por fase, errores de la 1.ª pasada (`<run>_pass1` si hubo
  reintento), `meta.opts` idéntico en todas las fases y `extra` del `raw` de cada caso
  igual al congelado;
- P.d2: auditoría numérica de las respuestas;
- §8.2: P.a–P.e, S1.a–S1.d, R.a–R.b y, de la revisión 3, X.a–X.b, Rot1.a–c, L.c–L.e;
- McNemar exacto (mismos conteos que `score --vs`) con Holm sobre la familia de celdas
  fase × pregunta de las 11 fases.
Las cifras se recalculan desde results/; nada se ajusta a mano."""
import argparse
import json
import math
import statistics

from . import metrics as M
from . import store
from .battery import ALERT_PHASES, EXTRA_PHASES, PHASES, RULES_PHASES, load_phase
from .jev67 import (_decisions_run, agreement, choice_changes, clopper_pearson, holm,
                    newcombe_paired, poisson_binomial_sf)
from .score import ADJ_PHASES, adjusted, score_run

RUNS = {
    "P": "dgemma_26b_a4b_nvfp4",
    "S1": "dgemma_26b_a4b_nvfp4_s1",
    "R": "dgemma_26b_a4b_nvfp4_rep",
    "X": "dgemma_26b_a4b_nvfp4_x80",
    "Rot1": "dgemma_26b_a4b_nvfp4_rot1",
    "Lp": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob",   # L de R3 (no ejecutable)
    "Ld": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc",
    "Lp2": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_dflt",   # L′ (rev. 4, no ejecutable)
    "Lr2": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_dflt_rep",
    "Ld2": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc_dflt",
    "Lp3": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp",     # L″ (revisión 5)
    "Lr3": "llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp_rep",
    "Ld3": "llm_dgemma_26b_a4b_nvfp4_nostruct_disc_rp",
}
REF = "jev_v3"
BASE9 = PHASES + EXTRA_PHASES
FROZEN_EXTRA = {
    "P": {"seed": 42, "samples": "auto", "auto_threshold": 0.1, "auto_max": 4, "steps": 1,
          "think": 0, "format": "lines"},
}
FROZEN_EXTRA["S1"] = dict(FROZEN_EXTRA["P"], samples=1)
for k in ("R", "X", "Rot1"):
    FROZEN_EXTRA[k] = FROZEN_EXTRA["P"]


def present(run):
    return bool(store.runs_in(run))


# ------------------------------------------------------------------ auditoría
def audit(cell):
    run = RUNS[cell]
    phases = store.runs_in(run)
    rep = {"run": run, "phases": {}, "n_ok": 0, "n": 0, "errors": [], "missing": [],
           "opts_variants": set(), "extra_mismatch": [], "no_raw": 0}
    want = FROZEN_EXTRA.get(cell)
    for ph in phases:
        doc = store.load(run, ph) or {}
        rep["opts_variants"].add(json.dumps((doc.get("meta") or {}).get("opts"), sort_keys=True))
        _, cases = load_phase(ph)
        recs = doc.get("cases") or {}
        ok = 0
        for c in cases:
            r = recs.get(c.id)
            if r is None:
                rep["missing"].append(f"{ph}/{c.id}")
            elif "error" in r:
                rep["errors"].append(f"{ph}/{c.id}: {r['error'][:80]}")
            else:
                ok += 1
                # el extra congelado solo existe en el formato raw de
                # systemone_http (dict {"request","response"}); el adaptador llm
                # guarda una lista de intentos
                if want is not None:
                    raw = r.get("raw")
                    req = raw.get("request") if isinstance(raw, dict) else None
                    if req is None:
                        rep["no_raw"] += 1
                    elif {k: req.get(k) for k in want} != want:
                        rep["extra_mismatch"].append(f"{ph}/{c.id}")
        rep["phases"][ph] = (ok, len(cases))
        rep["n_ok"] += ok
        rep["n"] += len(cases)
    rep["opts_variants"] = len(rep["opts_variants"])
    p1 = run + "_pass1"
    if present(p1):
        rep["errors_pass1"] = sum(1 for ph in store.runs_in(p1)
                                  for r in (store.load(p1, ph) or {}).get("cases", {}).values()
                                  if "error" in r)
    else:
        rep["errors_pass1"] = len(rep["errors"])
    rep["complete"] = (rep["n_ok"] == rep["n"] and set(phases) >= set(ADJ_PHASES))
    return rep


def numeric_audit(run):
    """P.d2: incidencias numéricas en las respuestas (11 fases). Valida tipo,
    finitud y etiquetas antes de operar: lo que no se pueda comprobar queda
    como incidencia y no aborta el informe."""
    inc = []
    for ph in store.runs_in(run):
        qs, _ = load_phase(ph)
        for cid, r in ((store.load(run, ph) or {}).get("cases") or {}).items():
            if "error" in r:
                continue
            for qid, q in qs.items():
                a = (r.get("answers") or {}).get(qid)
                where = f"{ph}/{cid}.{qid}"
                if a is None:
                    inc.append(f"{where}: sin respuesta")
                    continue
                if q["type"] == "noul":
                    v = a.get("noul")
                    if not (isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1):
                        inc.append(f"{where}: noul={v}")
                    continue
                p = a.get("probabilities")
                if not isinstance(p, dict) or not all(
                        isinstance(v, (int, float)) and math.isfinite(v) for v in p.values()):
                    inc.append(f"{where}: probabilities no numéricas o no finitas")
                    continue
                vals = list(p.values())
                if not all(0 <= v <= 1 for v in vals):
                    inc.append(f"{where}: probabilidad fuera de [0,1]")
                if not 0.99 <= sum(vals) <= 1.01:
                    inc.append(f"{where}: suma {sum(vals):.4f}")
                if q["type"] == "choice":
                    if set(p) != set(q["criteria"]):
                        inc.append(f"{where}: etiquetas {sorted(map(str, p))}")
                    continue
                names = [str(i) for i in range(len(q["criteria"]))]
                if set(p) != set(names):
                    inc.append(f"{where}: niveles {sorted(map(str, p))}")
                    continue
                s = a.get("score")
                if not (isinstance(s, (int, float)) and math.isfinite(s)):
                    inc.append(f"{where}: score={s} no finito")
                elif abs(s - sum(i * p[str(i)] for i in range(len(names)))) > 1e-6:
                    inc.append(f"{where}: score≠esperanza")
    return inc


# ------------------------------------------------------------------ métricas
def brier_noul(run, phases=BASE9):
    """Columna `Brier noul` del marcador (media de Brier de las preguntas noul, 9 fases)."""
    vals = []
    for ph in phases:
        x = score_run(run, ph)
        if x:
            qs, _ = load_phase(ph)
            vals += [v["brier"] for q, v in x["calib"].items() if qs[q]["type"] == "noul"]
    return sum(vals) / len(vals) if vals else None


def unif_choice(run):
    xs = [score_run(run, ph) for ph in BASE9]
    return (sum(x["n_near_uniform"] for x in xs if x), sum(x["n_choice"] for x in xs if x))


def latencies(run):
    out, by_reads, server = {}, {"1": [], ">1": []}, []
    allms = []
    for ph in store.runs_in(run):
        ms = []
        for r in ((store.load(run, ph) or {}).get("cases") or {}).values():
            if r.get("ms") is None or "error" in r:
                continue
            ms.append(r["ms"])
            # diagnostics del interposer solo en celdas systemone_http (raw dict);
            # con el adaptador llm (raw = lista de intentos) la latencia es solo ms
            raw = r.get("raw")
            d = ((raw.get("response") or {}).get("diagnostics") or {}) \
                if isinstance(raw, dict) else {}
            n = (d.get("samples") or {}).get("n")
            if isinstance(n, int):
                by_reads["1" if n == 1 else ">1"].append(r["ms"])
            t = (d.get("timing") or {}).get("total_ms")
            if t is not None:
                server.append(t)
        allms += ms
        if ms:
            out[ph] = (statistics.median(ms), _p95(ms), len(ms))
    return {"median": statistics.median(allms) if allms else None, "p95": _p95(allms),
            "per_phase": out,
            "by_reads": {k: (statistics.median(v), len(v)) for k, v in by_reads.items() if v},
            "server_median": statistics.median(server) if server else None}


def _p95(xs):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]


def max_abs_dp(run_a, run_b):
    """R.b/X.b: máx |Δp| entre distribuciones pareadas (choice, score y noul)."""
    worst, n, over = 0.0, 0, 0
    for ph in set(store.runs_in(run_a)) & set(store.runs_in(run_b)):
        da = (store.load(run_a, ph) or {}).get("cases") or {}
        db = (store.load(run_b, ph) or {}).get("cases") or {}
        for cid in set(da) & set(db):
            if "error" in da[cid] or "error" in db[cid]:
                continue
            for qid, a in da[cid]["answers"].items():
                b = db[cid]["answers"].get(qid) or {}
                pa = a.get("probabilities") or {"yes": a.get("noul")}
                pb = b.get("probabilities") or {"yes": b.get("noul")}
                for k in pa:
                    d = abs(float(pa[k]) - float(pb.get(k, float("nan"))))
                    n += 1
                    over += d > 1e-3
                    worst = max(worst, d) if not math.isnan(d) else float("inf")
    return (worst if n else None), over, n  # sin pares pareados → no evaluable


def _current_choice_keys():
    """{fase/caso: {qid choice}} del GT vigente: los casos retirados (p. ej. P02 en GT v4)
    no entran aunque sigan en los JSON históricos (JEV-86)."""
    out = {}
    for ph in PHASES + EXTRA_PHASES + RULES_PHASES + ALERT_PHASES:
        qs, cases = load_phase(ph)
        ch = {q for q, d in qs.items() if d["type"] == "choice"}
        for c in cases:
            out[f"{ph}/{c.id}"] = ch
    return out


def rotation(base, rot):
    valid = _current_choice_keys()
    changes, _ = choice_changes(base, rot)
    changes = [c for c in changes if c["pc"] in valid]
    da, db = _decisions_run(base), _decisions_run(rot)
    tot = sum(1 for pc in set(da) & set(db) if pc in valid
              for qid in valid[pc] if da[pc].get(qid) is not None and db[pc].get(qid) is not None)
    lo, hi = clopper_pearson(len(changes), tot)
    probs = [1.0 / (c["k"] - 1) for c in changes if c["k"] > 2]
    obs = sum(1 for c in changes if c["conserva"] and c["k"] > 2)
    p = poisson_binomial_sf(probs, obs) if changes else float("nan")
    a = b = cc = d = 0
    for pc in sorted(set(da) & set(db)):
        if pc not in valid:
            continue
        ph, cid = pc.split("/", 1)
        qs, cases = load_phase(ph)
        gt = {c.id: c.gt for c in cases}[cid]
        for qid, q in qs.items():
            if q["type"] != "choice" or da[pc].get(qid) is None or db[pc].get(qid) is None:
                continue
            h1, h3 = da[pc][qid] == gt[qid], db[pc][qid] == gt[qid]
            a += h1 and h3
            b += h3 and not h1
            cc += h1 and not h3
            d += not h1 and not h3
    return {"changes": len(changes), "paired": tot, "ci": (lo, hi), "conserved": obs,
            "poisson_p": p, "newcombe": newcombe_paired(a, b, cc, d), "table": (a, b, cc, d)}


def mcnemar_holm(run, ref=REF, phases=ADJ_PHASES):
    """Familia: celdas fase × pregunta que imprime `score --vs` (11 fases)."""
    rows = []
    for ph in phases:
        x, y = score_run(ref, ph), score_run(run, ph)
        if not x or not y:
            continue
        for q in load_phase(ph)[0]:
            b, c, p = M.mcnemar(x["hits"][q], y["hits"][q])
            rows.append({"phase": ph, "q": q, "b": b, "c": c, "p": p})
    for r, pa in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = pa
    return rows


def primacy(run):
    """§2bis: department con la 1.ª opción a p ≥ 0.7 y GT distinto."""
    out = []
    for ph in store.runs_in(run):
        qs, cases = load_phase(ph)
        if "department" not in qs:
            continue
        first = next(iter(qs["department"]["criteria"]))
        recs = (store.load(run, ph) or {}).get("cases") or {}
        for c in cases:
            r = recs.get(c.id)
            if not r or "error" in r:
                continue
            a = r["answers"]["department"]
            if a.get("choice") == first and (a.get("probabilities") or {}).get(first, 0) >= 0.7 \
                    and c.gt["department"] != first:
                out.append(f"{ph}/{c.id} (GT {c.gt['department']})")
    return out


# ------------------------------------------------------------------ clasificación
def band(x, conf, inc):
    """conf(x)/inc(x) → etiqueta; x None → no evaluable."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NO EVALUABLE"
    return "CONFIRMADA" if conf(x) else ("INCONCLUSA" if inc(x) else "REFUTADA")


def _try(f, default=None):
    """Una métrica que no se puede calcular queda no evaluable; no aborta el informe."""
    try:
        return f()
    except Exception as e:  # visible: un fallo de cálculo no debe parecer un resultado (JEV-86)
        import sys
        print(f"[dgemma_report] métrica no evaluable: {type(e).__name__}: {e}", file=sys.stderr)
        return default


def _finite(x):
    """Número real finito (None/NaN/inf → False)."""
    return isinstance(x, (int, float)) and math.isfinite(x)


LAT_EMPTY = {"median": None, "p95": None, "per_phase": {}, "by_reads": {},
             "server_median": None}


def build():
    res = {"cells": {}}
    for cell, run in RUNS.items():
        if not present(run):
            continue
        aud = audit(cell)
        numeric = _try(lambda: numeric_audit(run))  # antes del scoring
        adj, n_adj = _try(lambda: adjusted(run), (None, 0))
        res["cells"][cell] = {
            "audit": aud,
            # el ajustado del experimento exige cobertura completa de las 11
            # fases (§8.1) y un valor finito; la media sobre fases completas
            # queda como diagnóstico
            "adjusted": adj if aud["complete"] and _finite(adj) else None,
            "adjusted_partial": adj, "n_adj_phases": n_adj,
            "brier_noul": _try(lambda: brier_noul(run)),
            "unif_choice": _try(lambda: unif_choice(run), (None, 0)),
            "numeric": numeric, "latency": _try(lambda: latencies(run), LAT_EMPTY),
            "primacy": _try(lambda: primacy(run)) if cell in ("P", "Lp", "Ld", "Lp2", "Ld2", "Lp3", "Ld3") else None,
            "mcnemar": _try(lambda: mcnemar_holm(run)) if cell in ("P", "S1", "Rot1", "Lp", "Ld", "Lp2", "Ld2", "Lp3", "Ld3") else None,
        }
    C = res["cells"]
    cls = {}
    if "P" in C:
        p = C["P"]
        cls["P.a ajustado"] = band(p["adjusted"], lambda x: 22 <= x <= 48,
                                   lambda x: 15 <= x <= 55)
        cls["P.b Brier noul"] = band(p["brier_noul"], lambda x: x >= 0.085, lambda x: x > 0.071)
        cls["P.c errores 1.ª pasada"] = band(p["audit"]["errors_pass1"], lambda x: x <= 2,
                                             lambda x: x <= 9)
        cls["P.d1 unif choice"] = band(p["unif_choice"][0], lambda x: x <= 4, lambda x: x <= 20)
        cls["P.d2 auditoría numérica"] = band(
            len(p["numeric"]) if isinstance(p["numeric"], list) else None,
            lambda x: x == 0, lambda x: x <= 5)
        cls["P.e latencia mediana"] = band(p["latency"].get("median"), lambda x: x <= 1500,
                                           lambda x: x <= 3000)
    if "P" in C and "S1" in C:
        ag = _try(lambda: agreement(RUNS["P"], RUNS["S1"]))
        if ag is not None:
            res["S1_agreement"] = ag
        cls["S1.a acuerdo P↔S1"] = band(ag[2] if ag else None,
                                        lambda x: x >= 0.95, lambda x: x >= 0.90)
        both = C["P"]["audit"]["complete"] and C["S1"]["audit"]["complete"]
        ap, aq = C["P"]["adjusted"], C["S1"]["adjusted"]
        # cobertura completa no basta: el ajustado puede ser None si el scorer
        # falló (_try); S1.b y la recomendación exigen ambos finitos
        d = abs(ap - aq) if _finite(ap) and _finite(aq) else None
        cls["S1.b |Δ ajustado|"] = band(d, lambda x: x <= 3, lambda x: x <= 6)
        bp, bs = C["P"]["brier_noul"], C["S1"]["brier_noul"]
        cls["S1.c Brier P<S1"] = band(bs - bp if _finite(bp) and _finite(bs) else None,
                                      lambda x: x > 0.002, lambda x: abs(x) <= 0.002)
        mp, ms = C["P"]["latency"].get("median"), C["S1"]["latency"].get("median")
        cls["S1.d latencia S1"] = band(ms if _finite(ms) else None,
                                       lambda x: x <= 600, lambda x: x <= 1200)
        if both and all(_finite(v) for v in (ap, aq, bp, bs, mp, ms)):
            res["recomendacion"] = (
                "S1" if (C["P"]["adjusted"] - C["S1"]["adjusted"] <= 2
                         and bs <= bp + 0.01
                         and C["S1"]["latency"]["median"] <= 0.6 * C["P"]["latency"]["median"])
                else "P")
    for cell, tag in (("R", "R"), ("X", "X")):
        if "P" in C and cell in C:
            ag = _try(lambda: agreement(RUNS["P"], RUNS[cell]))
            worst, over, m = _try(lambda: max_abs_dp(RUNS["P"], RUNS[cell]), (None, 0, 0))
            if ag is not None:
                res[f"{tag}_agreement"] = ag
            res[f"{tag}_dp"] = (worst, over, m)
            cls[f"{tag}.a acuerdo P↔{tag}"] = band(ag[2] if ag else None,
                                                   lambda x: x == 1.0, lambda x: x >= 0.98)
            cls[f"{tag}.b distribuciones"] = band(worst, lambda x: x <= 1e-3, lambda x: x <= 0.02)
    if "P" in C and "Rot1" in C:
        rot = _try(lambda: rotation(RUNS["P"], RUNS["Rot1"]))
        if rot is None:
            cls["Rot1.a cambios de etiqueta"] = cls["Rot1.b conservan posición"] = \
                cls["Rot1.c Δ acierto choice"] = "NO EVALUABLE"
        else:
            res["rot1"] = rot
            lo, hi = rot["ci"]
            x_ok = cls.get("X.a acuerdo P↔X") == "CONFIRMADA"
            a = ("CONFIRMADA" if hi <= 0.10 else "REFUTADA" if lo > 0.10 else "INCONCLUSA")
            b = ("NO EVALUABLE (<10 cambios)" if rot["changes"] < 10
                 else "CONFIRMADA" if rot["poisson_p"] >= 0.05 else "REFUTADA")
            if not x_ok:
                a, b = f"INCONCLUSA POR HOST ({a})", f"INCONCLUSA POR HOST ({b})"
            cls["Rot1.a cambios de etiqueta"] = a
            cls["Rot1.b conservan posición"] = b
            _, nlo, nhi = rot["newcombe"]
            cls["Rot1.c Δ acierto choice"] = ("CONFIRMADA" if nlo >= -0.05 and nhi <= 0.05
                                              else "REFUTADA" if nlo > 0 or nhi < 0 else "INCONCLUSA")
    for cell in ("Lp", "Ld"):
        if cell in C:
            cls[f"L.c errores 1.ª pasada ({cell})"] = band(
                C[cell]["audit"]["errors_pass1"], lambda x: x <= 2, lambda x: x <= 9)
    if "Lp" in C and "Ld" in C:
        v = _try(lambda: mcnemar_holm(RUNS["Ld"], ref=RUNS["Lp"]))
        if v is not None:
            res["Ld_vs_Lp"] = v
    for cell in ("Lp", "Ld"):
        if "P" in C and cell in C:
            v = _try(lambda: mcnemar_holm(RUNS[cell], ref=RUNS["P"]))
            if v is not None:
                res[f"{cell}_vs_P"] = v
    # celdas L′ (revisión 4): errores, acuerdo Lp2↔Lr2, Ld2 vs Lp2 y P vs L′
    for cell in ("Lp2", "Lr2", "Ld2"):
        if cell in C:
            cls[f"L′.c errores 1.ª pasada ({cell})"] = band(
                C[cell]["audit"]["errors_pass1"], lambda x: x <= 2, lambda x: x <= 9)
    if "Lp2" in C and "Lr2" in C:
        ag = _try(lambda: agreement(RUNS["Lp2"], RUNS["Lr2"]))
        if ag is not None:
            res["Lp2_Lr2_agreement"] = ag
    if "Lp2" in C and "Ld2" in C:
        v = _try(lambda: mcnemar_holm(RUNS["Ld2"], ref=RUNS["Lp2"]))
        if v is not None:
            res["Ld2_vs_Lp2"] = v
    for cell in ("Lp2", "Ld2"):
        if "P" in C and cell in C:
            v = _try(lambda: mcnemar_holm(RUNS[cell], ref=RUNS["P"]))
            if v is not None:
                res[f"{cell}_vs_P"] = v
    # celdas L″ (revisión 5): errores, acuerdo Lp3↔Lr3, Ld3 vs Lp3 y P vs L″
    for cell in ("Lp3", "Lr3", "Ld3"):
        if cell in C:
            cls[f"L″.c errores 1.ª pasada ({cell})"] = band(
                C[cell]["audit"]["errors_pass1"], lambda x: x <= 2, lambda x: x <= 9)
    if "Lp3" in C and "Lr3" in C:
        ag = _try(lambda: agreement(RUNS["Lp3"], RUNS["Lr3"]))
        if ag is not None:
            res["Lp3_Lr3_agreement"] = ag
    if "Lp3" in C and "Ld3" in C:
        v = _try(lambda: mcnemar_holm(RUNS["Ld3"], ref=RUNS["Lp3"]))
        if v is not None:
            res["Ld3_vs_Lp3"] = v
    for cell in ("Lp3", "Ld3"):
        if "P" in C and cell in C:
            v = _try(lambda: mcnemar_holm(RUNS[cell], ref=RUNS["P"]))
            if v is not None:
                res[f"{cell}_vs_P"] = v
    res["classification"] = cls
    return res


def _sig(rows):
    return [f"{r['phase']}.{r['q']} b={r['b']} c={r['c']} p={r['p']:.3f} holm={r['p_holm']:.3f}"
            for r in rows if r["p"] < 0.05]


def report(res, printer=print):
    for cell, c in res["cells"].items():
        a = c["audit"]
        printer(f"\n## {cell} `{a['run']}`")
        printer(f"- cobertura {a['n_ok']}/{a['n']} · completa={a['complete']} · errores 1.ª pasada "
                f"{a['errors_pass1']} · faltan {len(a['missing'])} · variantes de opts "
                f"{a['opts_variants']} · extra≠congelado {len(a['extra_mismatch'])} · sin raw {a['no_raw']}")
        adj = c["adjusted"]
        if adj is not None:
            printer(f"- ajustado {adj:.1f} ({c['n_adj_phases']} fases completas)")
        else:
            part = c.get("adjusted_partial")
            printer("- ajustado no evaluable" + (
                f" (parcial {part:.1f} sobre {c['n_adj_phases']} fases completas; "
                "diagnóstico, no es el ajustado del experimento)"
                if part is not None else ""))
        if c["brier_noul"] is not None:
            unif = c["unif_choice"]
            num = len(c["numeric"]) if isinstance(c["numeric"], list) else "—"
            printer(f"- Brier noul {c['brier_noul']:.3f} · unif choice {unif[0]}/"
                    f"{unif[1]} · incidencias numéricas {num}")
        else:
            printer("- Brier noul no evaluable")
        lat = c["latency"]
        printer(f"- latencia cliente mediana {lat.get('median')} ms, p95 {lat.get('p95')} ms; "
                f"servidor mediana {lat.get('server_median')}; por lecturas {lat.get('by_reads')}")
        if c["primacy"]:
            printer(f"- primacía department (1.ª opción ≥0.7, GT otra): {len(c['primacy'])} → "
                    + ", ".join(c["primacy"]))
        if c["mcnemar"]:
            sig = _sig(c["mcnemar"])
            printer(f"- McNemar vs {REF}: {len(c['mcnemar'])} celdas; p<0.05 crudo: "
                    + ("; ".join(sig) if sig else "ninguna"))
    for k in ("S1_agreement", "R_agreement", "X_agreement", "Lp2_Lr2_agreement",
              "Lp3_Lr3_agreement"):
        if k in res:
            kk, n, f, lo, hi = res[k]
            printer(f"\n{k}: {kk}/{n} = {100 * f:.2f} % (IC95 {100 * lo:.1f}–{100 * hi:.1f})")
    for k in ("R_dp", "X_dp"):
        if k in res:
            w, over, m = res[k]
            printer(f"{k}: máx |Δp| {w:.2e}; >1e-3 en {over}/{m}" if w is not None
                    else f"{k}: sin pares pareados ({m}) — no evaluable")
    if "rot1" in res:
        r = res["rot1"]
        printer(f"\nRot1: {r['changes']}/{r['paired']} cambios (IC95 {100 * r['ci'][0]:.1f}–"
                f"{100 * r['ci'][1]:.1f} %), conservan posición {r['conserved']} "
                f"(p={r['poisson_p']:.3f}); Δ acierto choice Rot1−P {100 * r['newcombe'][0]:+.1f} pp "
                f"IC95 [{100 * r['newcombe'][1]:+.1f}, {100 * r['newcombe'][2]:+.1f}] tabla {r['table']}")
    for k in ("Ld_vs_Lp", "Lp_vs_P", "Ld_vs_P"):
        if k in res:
            sig = _sig(res[k])
            printer(f"{k}: p<0.05 crudo: " + ("; ".join(sig) if sig else "ninguna"))
    printer("\n## Clasificación")
    for k, v in res["classification"].items():
        printer(f"- {k}: {v}")
    if "recomendacion" in res:
        printer(f"- Recomendación S1 vs P (regla fijada): {res['recomendacion']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    res = build()
    report(res)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    from .attest import public_exit
    return public_exit()


if __name__ == "__main__":
    raise SystemExit(main())
