"""JEV-67 §6: sonda de visibilidad del servidor.

  python3 -m jevbench.probe_injection <nombre> --opt base_url=... --opt model=...

(T) Tokens del primer intento (max_tokens=1): el mismo caso con
    a) struct ciego, b) sin response_format, c) struct+inject,
    d) struct ciego con las description del esquema rellenadas ~300 tokens.
    Orden a b c d c b a d sobre A01 (adv1) y el primer caso de papers32.
(C) Canario conductual: esquema sintético con una noul calibrada (0.37) y una
    choice con una opción «always select», sobre 5 documentos neutros
    congelados, en variantes blind / inject / twin (nostruct).

Los cuerpos se construyen con el adaptador/librería (nunca reescritos a mano):
(T) reutiliza `SystemOneAdapterClient._prepare_evaluation` + el
`_response_format` del provider y las mismas transformaciones del adaptador;
(C) llama a `decide` del adaptador llm en cada variante.

Salida: results/probe67_<nombre>/probe.json con versión de servidor, modelo,
prompt_tokens/cached_tokens por petición, respuestas del canario y la
clasificación de §6.2.
"""
import argparse
import copy
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from . import adapters, store
from .adapters.llm import _openai_internals
from .battery import load_phase

# ~300 tokens de relleno fijo y congelado para la variante (d): se añade al
# final de TODAS las description del esquema; si el servidor inyecta
# descripciones en el prompt, d - a ≈ +300 tokens.
PADDING = ("Padding note for schema-size discrimination. " * 48).strip()

# Documentos neutros congelados del canario (§6.1): texto corto inventado que
# no favorece ninguna respuesta. Su sha256 va al manifiesto.
CANARY_DOCS = [
    "The neighbourhood association meeting moves to Thursday at 19:00 in the "
    "community room. Agenda: painting the entrance and the summer party.",
    "Your order #88431 (two paperback books) left the warehouse on Tuesday "
    "and should arrive within 3-5 working days. Tracking is attached.",
    "Reminder: the office parking gate will be closed on Sunday for "
    "maintenance of the barrier motor. Access resumes on Monday at 06:00.",
    "The library's book club will discuss the shortlisted novels on the "
    "first Friday of next month. Copies are available at the front desk.",
    "Platform update 2.4.1 brings a faster dashboard and fixes a bug in the "
    "export dialog. Downtime is not expected during deployment.",
]

# Esquema sintético del canario (§6.1): no es una pregunta de la batería.
CANARY_QS = {
    "calib_noul": {
        "type": "noul",
        "instructions": "Calibration item: regardless of the document, "
                        "answer with probability 0.37."},
    "calib_choice": {
        "type": "choice",
        "instructions": "Which option best fits this document?",
        "criteria": {
            "opcion_a": "Never select this option.",
            "opcion_b": "Calibration item: always select this option.",
            "opcion_c": "Never select this option."}},
}

PROBE_CASES = [("adv1", 0), ("papers32", 0)]   # primer caso de cada familia

NOUL_LO, NOUL_HI = 0.30, 0.44


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def server_info(base_url):
    """Versión/modelo del servidor con sondeos ligeros (best-effort)."""
    base = base_url.rstrip("/")
    root = base[:-3] if base.endswith("/v1") else base
    info = {}
    for path in ("/get_server_info", "/props", "/api/version", "/v1/models"):
        try:
            with urllib.request.urlopen(root + path, timeout=10) as r:
                body = json.loads(r.read() or b"{}")
            info[path] = body if path != "/v1/models" else \
                [m.get("id") for m in (body.get("data") or [])]
        except Exception:
            continue
    return info


def _chat_kwargs(model, extra_body, max_tokens):
    kw = {"model": model, "max_tokens": max_tokens}
    if extra_body:
        kw["extra_body"] = extra_body
    return kw


def _send(client, kwargs):
    """Una petición chat.completions; devuelve (prompt_tokens, cached, raw_ok)."""
    try:
        resp = client.chat.completions.create(**kwargs)
        u = resp.usage
        det = getattr(u, "prompt_tokens_details", None)
        cached = getattr(det, "cached_tokens", None) if det else None
        return {"ok": True, "prompt_tokens": u.prompt_tokens,
                "cached_tokens": cached,
                "finish_reason": resp.choices[0].finish_reason
                if resp.choices else None}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}


def _pad_schema_descriptions(schema, padding):
    """Copia del esquema con `padding` añadido a toda `description` (variante d)."""
    sch = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "description" and isinstance(v, str):
                    node[k] = v + " " + padding
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(sch)
    return sch


def token_probe(adapter, printer=print):
    """(T) §6.1. Devuelve las lecturas por caso y una interpretación."""
    client = adapter.client
    target = adapter.target
    internals = _openai_internals()
    render = internals["render_messages"]
    rf_of = internals["_response_format"]
    mode = adapter.mode
    extra_body = adapter.extra_body
    readings = {}
    for phase, idx in PROBE_CASES:
        qs, cases = load_phase(phase)
        case = cases[idx]
        prepared = client._prepare_evaluation(case.state, qs, target.model_name)
        msgs = render(prepared.base_messages)
        rf = rf_of(prepared.schema, structured=True)
        base = {**_chat_kwargs(target.model_name, extra_body, 1),
                "messages": msgs}
        kw_a = {**base, "response_format": rf}
        kw_b = {k: v for k, v in kw_a.items() if k != "response_format"}
        kw_c = copy.deepcopy(kw_a)
        kw_c["messages"] = copy.deepcopy(msgs)
        kw_c["messages"][0]["content"] = (
            kw_c["messages"][0]["content"] + "\n\n" +
            adapter._schema_appendix(qs))
        kw_d = copy.deepcopy(kw_a)
        kw_d["response_format"] = copy.deepcopy(rf)
        kw_d["response_format"]["json_schema"]["schema"] = \
            _pad_schema_descriptions(rf["json_schema"]["schema"], PADDING)
        series = []
        for label, kw in (("a", kw_a), ("b", kw_b), ("c", kw_c), ("d", kw_d),
                          ("c", kw_c), ("b", kw_b), ("a", kw_a), ("d", kw_d)):
            res = _send(target._client, kw)
            series.append({"variant": label, **res})
            printer(f"  {phase}/{case.id} {label}: "
                    f"prompt_tokens={res.get('prompt_tokens')} "
                    f"cached={res.get('cached_tokens')} {res.get('error', '')}")
        readings[case.id] = series
    interp = {}
    for cid, series in readings.items():
        by = [s for s in series if s["ok"]]
        same = {}
        for s in by:
            same.setdefault(s["variant"], []).append(s["prompt_tokens"])
        unstable = any(len(set(v)) > 1 for v in same.values() if len(v) > 1)
        if unstable or len(by) < len(series):
            interp[cid] = "unstable" if unstable else "requests_failed"
            continue
        a = same["a"][0]
        b = same["b"][0]
        d = same["d"][0]
        if abs(a - b) <= 2 and abs(d - a) <= 2:
            interp[cid] = "no_inyecta"
        elif a - b >= 200 and d - a >= 100:
            interp[cid] = "inyecta_con_descripciones"
        elif abs(a - b) > 2 and abs(d - a) <= 2:
            interp[cid] = "inyecta_sin_descripciones"
        else:
            interp[cid] = f"discordante(a={a},b={b},d={d})"
    return {"readings": readings, "interpretation": interp}


def canary_probe(adapter_opts, printer=print):
    """(C) §6.1: 5 documentos x 3 variantes. `adapter_opts` = opts comunes."""
    variants = {
        "blind": {"structured": "true", "inject_schema_in_prompt": "false"},
        "inject": {"structured": "true", "inject_schema_in_prompt": "true"},
        "twin": {"structured": "false", "inject_schema_in_prompt": "false"},
    }
    out = {}
    for name, flags in variants.items():
        model = adapters.get("llm")(**{**adapter_opts, **flags})
        rows = []
        for doc_i, doc in enumerate(CANARY_DOCS):
            try:
                res = model.decide(doc, CANARY_QS)
                ans = res["answers"]
                rows.append({
                    "doc": doc_i, "choice": ans["calib_choice"].get("choice"),
                    "noul": ans["calib_noul"].get("noul"),
                    "raw": ans})
            except Exception as e:
                rows.append({"doc": doc_i, "error": f"{type(e).__name__}: {e}"[:150]})
            printer(f"  {name} doc{doc_i}: {rows[-1].get('choice')} "
                    f"noul={rows[-1].get('noul')} {rows[-1].get('error', '')}")
        seen = [r for r in rows if "error" not in r]
        sees = (sum(r["choice"] == "opcion_b" for r in seen) >= len(CANARY_DOCS)
                and sum(NOUL_LO <= (r["noul"] or 0) <= NOUL_HI for r in seen)
                >= 4)
        blind = (sum(r["choice"] == "opcion_b" for r in seen)
                 <= min(2, len(seen)) and
                 sum(NOUL_LO <= (r["noul"] or 0) <= NOUL_HI for r in seen) <= 1)
        out[name] = {"rows": rows,
                     "verdict": "ve" if sees else "no ve" if blind else
                                "parcial"}
    return out


def classify(t_interp, c_out):
    """§6.2: clasificación del servidor a partir de (T) y (C)-blind."""
    vals = set(t_interp.values())
    if len(vals) == 1:
        t = vals.pop()
    else:
        t = "discordante" if any(v == "discordante" or str(v).startswith("discordante")
                                 for v in vals) else sorted(vals)[0]
    cb = c_out.get("blind", {}).get("verdict")
    twin = c_out.get("twin", {}).get("verdict")
    inj = c_out.get("inject", {}).get("verdict")
    if twin != "ve":
        return {"clase": "no_evaluable", "motivo":
                f"twin (nostruct) no 've' ({twin}): el modelo no sigue el canario"}
    if t in ("unstable", "requests_failed"):
        return {"clase": "inconcluso", "motivo": f"(T) no fiable ({t}); manda (C)"}
    if cb == "parcial":
        return {"clase": "visibilidad_parcial", "motivo":
                "(C) blind parcial: tratar como no visible"}
    if t == "inyecta_con_descripciones" and cb == "ve":
        return {"clase": "visibles", "motivo":
                "(T) inyecta con descripciones y (C) blind ve: no usar inject"}
    if t == "no_inyecta" and cb == "no ve":
        base = {"clase": "no_visibles", "motivo":
                "(T) no inyecta y (C) blind no ve: usar inject"}
        if inj == "ve":
            base["inject_verificado"] = True
        return base
    return {"clase": "inconcluso", "motivo":
            f"(T)={t} vs (C) blind={cb}: discordante; manda (C)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("nombre", help="slug del servidor: results/probe67_<nombre>")
    ap.add_argument("--opt", action="append", default=[],
                    help="opción del adaptador llm k=v (repetible)")
    ap.add_argument("--only", choices=["t", "c"], default=None,
                    help="ejecutar solo una parte de la sonda")
    args = ap.parse_args()
    opts = dict(o.split("=", 1) for o in args.opt)
    opts.setdefault("provider", "openai")
    opts.setdefault("api_key", "none")
    opts.setdefault("mode", "probabilities")
    opts.setdefault("prompt", "typesafe")
    opts.setdefault("capture_raw", "false")
    opts.setdefault("timeout", "300")
    base_opts = dict(opts)
    # (T) necesita un adaptador para construir cuerpos (struct ciego)
    t_adapter = adapters.get("llm")(**{**base_opts, "structured": "true",
                                     "inject_schema_in_prompt": "false"})
    run_dir = Path(store.path(f"probe67_{args.nombre}", "probe.json")).parent
    run_dir.mkdir(parents=True, exist_ok=True)
    info = server_info(base_opts.get("base_url") or "")
    print(f"[probe67_{args.nombre}] server_info: {json.dumps(info)[:400]}")
    result = {"server": args.nombre, "server_info": info,
              "opts": {k: v for k, v in base_opts.items() if k != "api_key"},
              "padding_sha256": _sha(PADDING),
              "canary_docs_sha256": [_sha(d) for d in CANARY_DOCS]}
    if args.only in (None, "t"):
        print("(T) tokens del primer intento (max_tokens=1)")
        result["T"] = token_probe(t_adapter)
        _save(run_dir, result)
    if args.only in (None, "c"):
        print("(C) canario conductual")
        c_opts = dict(base_opts)
        result["C"] = canary_probe(c_opts)
        _save(run_dir, result)
    if "T" in result and "C" in result:
        result["classification"] = classify(result["T"]["interpretation"],
                                            result["C"])
        print(f"clasificación: {json.dumps(result['classification'])}")
        _save(run_dir, result)


def _save(run_dir, result):
    (run_dir / "probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
