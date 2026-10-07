"""JEV-70 §6.4: puerta de montaje del interposer de DiffusionGemma (bloqueante).

  python3 -m jevbench.dgemma_gate --preflight preflight.json --engine-log vllm.log \
      --results results/<run> --server structured_server.py \
      [--since "MM-DD HH:MM:SS"] [--until "MM-DD HH:MM:SS"] \
      [--log-from N --log-to M] [--require-families all|h1,h2] \
      [--expected-tokens tokens.json] [--json salida.json]

El log del motor (vLLM 1b3b88ec, --enable-log-requests) enlaza dos líneas por
petición con el id `chatcmpl-…`:

  DEBUG … Request <id> details: prompt: '<repr>', prompt_token_ids: […],
          prompt_embeds shape: …
  INFO  … Received request <id>: params: SamplingParams(…,
          extra_args={'diffusion_canvas_length': N, …}), lora_request: …

La puerta parsea registros por id (el prompt se decodifica con ast.literal_eval
del repr — si no decodifica, evidencia insuficiente; el prompt solo se registra
a nivel DEBUG) y atribuye las peticiones a cada caso revisado: las del log cuyo
prompt decodificado contiene el `state` exacto del request y el `system_text`
congelado de su familia. Por caso se exige:

  (a) ≥1 petición atribuida y ninguna con el mismo state y otro sistema;
  (b) diagnostics.prompt_tokens del motor (null = respaldo del interposer →
      fallo), |Δ| ≤ 2 frente al preflight o a --expected-tokens (casos ajenos al
      banco, p. ej. el canario) y |len(prompt_token_ids) − prompt_tokens| ≤ 2;
  (c) una etapa, un grupo, sin skipped en diagnostics y ancho
      diffusion_canvas_length == width del preflight en cada petición
      (si no viene registrado → «no verificable», sin fallo);
  (d) el raw.request reproduce el system_text congelado, reconstruido con el
      structured_server.py congelado (--server, importado sin transformers con
      módulos sustitutos y sha256 verificado contra el preflight). Sin --server
      la puerta no certifica: la comparación degradada de `questions` queda
      como diagnóstico. meta.rotate_choice ≠ preflight.rotate → fallo.

Además (e): ≥1 caso verificado y cada familia requerida (por defecto las del
preflight presentes en --results; `all` = las tres) con ≥1 caso verificado.
Exit 0 solo si todas las comprobaciones pasan.

Ventana de ejecución: --since/--until acotan por timestamp del log y
--log-from/--log-to por números de línea FÍSICA (1-based, inclusivos, tal como
los cuentan `wc -l` y `sed -n A,Bp`: separador único `\n`; los `\r` de barras de
progreso permanecen dentro de su línea y no numeran). Un registro solo entra si
TODAS sus líneas físicas caen dentro. El operador recortará el log por run con
offsets anotados antes y después de cada celda: --since por sí solo NO delimita
una ejecución cuando en el mismo log hay ejecuciones posteriores que reutilizan
los mismos estados (smoke base + Rot1 + L en .80). Los límites usados quedan en
la evidencia JSON bajo `ventana`.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

from . import dgemma_canary, store
from .battery import load_phase
from .dgemma_preflight import sha
from .rotation import rotate_choice

TOL_TOKENS = 2  # §6.4(b): |prompt_tokens del motor − esperado| tolerado
REQ_DETAILS_RE = re.compile(
    r"Request (\S+) details: prompt: (.*), prompt_token_ids: (\[[^\]]*\])")
RECEIVED_RE = re.compile(r"Received request (\S+):")
TS_RE = re.compile(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
WIDTH_RE = re.compile(r"'diffusion_canvas_length': (\d+)")


# ------------------------------------------------------------------ parseo
def result_files(arg):
    """--results admite un directorio, un fichero JSON o un nombre de run."""
    p = Path(arg)
    if p.is_file():
        return [p]
    base = p if p.is_dir() else store.ROOT / arg
    if not base.is_dir():
        raise SystemExit(f"--results: {arg} no es un directorio, un JSON ni un run de {store.ROOT}")
    files = sorted(base.glob("*.json"))
    if not files:
        raise SystemExit(f"--results: {base} no contiene ficheros JSON")
    return files


def parse_log(log_text):
    """Registros por id de petición: prompt decodificado (repr exacto), nº de
    prompt_token_ids, diffusion_canvas_length, timestamp y números de línea
    (1-based) del log de los que procede cada registro.

    Numeración física por LF, coherente con `wc -l` y `sed -n A,Bp`: se divide
    SOLO por `\\n` y los `\\r` (barras de progreso) se conservan dentro de la
    línea. Una línea física puede contener varios registros separados por `\\r`:
    cada segmento se examina por separado."""
    recs = {}
    for ln, line in enumerate(log_text.split("\n"), 1):
        for seg in line.split("\r"):
            m = REQ_DETAILS_RE.search(seg)
            if m:
                r = recs.setdefault(m.group(1), {"id": m.group(1)})
                r.setdefault("lines", []).append(ln)
                ts = TS_RE.search(seg)
                r.setdefault("ts", ts.group(1) if ts else None)
                try:
                    r["prompt"] = ast.literal_eval(m.group(2))
                except (ValueError, SyntaxError, MemoryError):
                    r["undecodable"] = True
                try:
                    r["n_ids"] = len(ast.literal_eval(m.group(3)))
                except (ValueError, SyntaxError, MemoryError):
                    r["n_ids"] = None
                continue
            m = RECEIVED_RE.search(seg)
            if m:
                r = recs.setdefault(m.group(1), {"id": m.group(1)})
                r.setdefault("lines", []).append(ln)
                ts = TS_RE.search(seg)
                r.setdefault("ts", ts.group(1) if ts else None)
                w = WIDTH_RE.search(seg)
                if w:
                    r["width"] = int(w.group(1))
    return list(recs.values())


def same_ordered(a, b):
    """Igualdad profunda respetando el orden de las claves (preguntas y opciones)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return list(a) == list(b) and all(same_ordered(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_ordered(x, y) for x, y in zip(a, b))
    return a == b


def load_frozen_server(path, want_sha256=None):
    """Importa el structured_server.py congelado con stubs de transformers y
    pybase64 (system_text/jev_schema no los usan). Devuelve (módulo, error,
    fatal): fatal=True si el fichero no es el congelado (sha256 distinto)."""
    p = Path(path)
    if not p.is_file():
        return None, f"--server {path} no existe", False
    if want_sha256:
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want_sha256:
            return None, (f"--server no es el congelado del preflight "
                          f"(sha256 {got[:12]} ≠ {want_sha256[:12]})"), True
    for name in ("pybase64", "transformers"):
        if name not in sys.modules:
            try:
                __import__(name)
            except ImportError:
                sys.modules[name] = types.ModuleType(name)
    if not hasattr(sys.modules["transformers"], "AutoTokenizer"):
        sys.modules["transformers"].AutoTokenizer = None
    try:
        spec = importlib.util.spec_from_file_location("structured_server_frozen", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, None, False
    except Exception as e:
        return None, f"--server no importable ({type(e).__name__}: {e})", False


def _family_of(phase, meta, families):
    h = meta.get("questions_hash")
    if h in families:
        return h
    hits = [h for h, f in families.items() if phase in f.get("phases", [])]
    return hits[0] if hits else None


def _rotate_of(meta):
    v = meta.get("rotate_choice") or (meta.get("opts") or {}).get("rotate_choice") or 0
    return int(v)


def _collect(files, families):
    """Un item por caso: fase, meta del JSON, raw.request y diagnostics."""
    items = []
    for p in files:
        doc = json.loads(p.read_text())
        meta = doc.get("meta") or {}
        phase = p.stem
        canary = phase == "canary" or "canary_sha256" in meta
        fam = None if canary else _family_of(phase, meta, families)
        for cid, rec in (doc.get("cases") or {}).items():
            raw = rec.get("raw") or {}
            req = raw.get("request") if isinstance(raw, dict) else None
            resp = raw.get("response") if isinstance(raw, dict) else None
            diag = (resp or {}).get("diagnostics") if isinstance(resp, dict) else None
            items.append({"fase": phase, "cid": cid, "rec": rec, "meta": meta,
                          "canary": canary, "familia": fam,
                          "request": req, "diagnostics": diag})
    return items


def _reads_of(it):
    """Lecturas del caso según diagnostics: samples.n o timing.reads (None si
    no hay)."""
    d = it["diagnostics"] or {}
    reads = (d.get("samples") or {}).get("n")
    if not isinstance(reads, int):
        reads = (d.get("timing") or {}).get("reads")
    return reads if isinstance(reads, int) else None


# ------------------------------------------------------------------ puerta
def _in_window(r, since, until, log_from, log_to):
    """El registro pertenece a la ventana: por timestamp (--since/--until) y/o
    por números de línea del log (--log-from/--log-to, inclusivos; un registro
    entra solo si TODAS sus líneas están dentro)."""
    if log_from is not None or log_to is not None:
        lines = r.get("lines") or []
        if not lines or (log_from is not None and min(lines) < log_from) \
                or (log_to is not None and max(lines) > log_to):
            return False
    if since and (not r.get("ts") or r["ts"] < since):
        return False
    if until and (not r.get("ts") or r["ts"] > until):
        return False
    return True


def evaluate(files, preflight, log_text, ss=None, ss_error=None, ss_fatal=False,
             expected_extra=None, since=None, until=None, log_from=None,
             log_to=None, require_families=None):
    """Ejecuta las comprobaciones (a)–(e) y devuelve el dict del informe."""
    canvas = str(preflight.get("canvas"))
    fams = preflight.get("families") or {}
    expected_extra = expected_extra or {}
    items = _collect(files, fams)
    fam_entry = {h: ((f.get("by_canvas") or {}).get(canvas) or {})
                 for h, f in fams.items()}
    all_records = parse_log(log_text)
    records = [r for r in all_records
               if _in_window(r, since, until, log_from, log_to)]
    fuera = len(all_records) - len(records)
    ventana = {"since": since, "until": until,
               "log_from": log_from, "log_to": log_to,
               "registros": len(records), "excluidos": fuera}
    n_decoded = sum(1 for r in records if r.get("prompt"))
    n_undecodable = sum(1 for r in records if r.get("undecodable"))
    fallo_case = set()

    # system_texts esperados por item (familias del banco + variantes del canario)
    canary_reqs = {}
    for it in items:
        if it["canary"] and it["request"] is not None:
            canary_reqs.setdefault(it["cid"].split(":")[0], it["request"])
    canary_texts = {}
    for var, req in sorted(canary_reqs.items()):
        try:
            canary_texts[var] = ss.system_text(ss.jev_schema(req)) if ss else None
        except Exception:
            canary_texts[var] = None
    for it in items:
        if it["canary"]:
            it["sys_text"] = canary_texts.get(it["cid"].split(":")[0])
            it["sys_allowed"] = {t for t in canary_texts.values() if t}
        else:
            ent = fam_entry.get(it["familia"]) or {}
            it["sys_text"] = ent.get("system_text") if ent.get("fits") else None
            it["sys_allowed"] = {it["sys_text"]} if it["sys_text"] else set()
        it["same"] = it["attributed"] = it["conflict"] = []
        state = (it["request"] or {}).get("state")
        if isinstance(state, str) and state:
            same = [r for r in records if r.get("prompt") and state in r["prompt"]]
            it["same"] = same
            st = it["sys_text"]
            it["attributed"] = [r for r in same if st and st in r["prompt"]]
            it["conflict"] = [r for r in same
                              if not any(t in r["prompt"] for t in it["sys_allowed"])]

    # casos con (state, system_text) idénticos comparten las peticiones
    # atribuidas: el recuento se exige en conjunto (p. ej. paper duplicado P02/P03)
    grupos = {}
    for it in items:
        state = (it["request"] or {}).get("state")
        key = (state, it["sys_text"])
        if state and it["sys_text"]:
            grupos.setdefault(key, []).append(it)
    for key, grp in grupos.items():
        if len(grp) > 1:
            for it in grp:
                it["grupo"] = grp
                it["grupo_key"] = key

    # (a) texto de sistema en el log, atribuido por petición
    det = []
    if any(v is not None for v in (since, until, log_from, log_to)):
        det.append(f"ventana {ventana}: {fuera} registros fuera ignorados")
    if not n_decoded:
        det.append("evidencia insuficiente: prompt no registrado "
                   "(el motor solo lo escribe a nivel DEBUG)")
    if n_undecodable:
        det.append(f"{n_undecodable} registro(s) con repr no decodificable "
                   "(evidencia insuficiente)")
    hechos = set()
    for it in items:
        tag = f"{it['fase']}:{it['cid']}"
        if it["sys_text"] is None:
            det.append(f"FALLO: {tag}: sin system_text de referencia")
            fallo_case.add(tag)
            continue
        grp = it.get("grupo")
        if grp and it["grupo_key"] in hechos:
            continue  # el grupo ya se informó con el primer miembro
        if grp:
            hechos.add(it["grupo_key"])
        tags = ", ".join(f"{g['fase']}:{g['cid']}" for g in grp) if grp else tag
        def _marca():
            if grp:
                for g in grp:
                    fallo_case.add(f"{g['fase']}:{g['cid']}")
            else:
                fallo_case.add(tag)
        if not it["attributed"]:
            extra = (f"; {len(it['same'])} petición(es) con el state y otro sistema"
                     if it["same"] else "")
            det.append(f"FALLO: {tags}: ninguna petición atribuida{extra}")
            _marca()
            continue
        r0 = it["attributed"][0]
        i = r0["prompt"].find(it["sys_text"])
        frag = r0["prompt"][i:i + len(it["sys_text"])]
        if grp:
            det.append(f"casos con estado idéntico: {tags} — atribución "
                       f"conjunta ({len(it['attributed'])} petición(es), "
                       f"sha256 del texto del log={sha(frag)[:12]})")
        else:
            det.append(f"{tag}: {len(it['attributed'])} petición(es) atribuidas, "
                       f"sha256 del texto del log={sha(frag)[:12]}")
        if it["conflict"]:
            det.append(f"FALLO: {tags}: {len(it['conflict'])} petición(es) con el "
                       "mismo state y otro sistema")
            _marca()
        # nº de peticiones == lecturas del interposer (samples=auto → 1–4);
        # en un grupo, la suma de lecturas de sus casos
        if grp:
            reads = [_reads_of(g) for g in grp]
            if all(r is not None for r in reads):
                if len(it["attributed"]) != sum(reads):
                    det.append(f"FALLO: {tags}: {len(it['attributed'])} "
                               f"petición(es) atribuidas ≠ {sum(reads)} "
                               "lecturas en conjunto")
                    _marca()
            else:
                det.append(f"{tags}: lecturas no registradas en todos los casos "
                           "(nº de peticiones no verificable)")
        else:
            reads = _reads_of(it)
            if reads is not None and len(it["attributed"]) != reads:
                det.append(f"FALLO: {tag}: {len(it['attributed'])} petición(es) "
                           f"atribuidas ≠ {reads} lecturas")
                fallo_case.add(tag)
            elif reads is None:
                det.append(f"{tag}: lecturas no registradas (nº de peticiones "
                           "no verificable)")
    a = {"id": "a", "titulo": "texto de sistema en el log, atribuido por petición",
         "detalles": det}

    # (b) prompt_tokens del motor y recuento del log
    det = []
    pref_pt = preflight.get("prompt_tokens") or {}
    for it in items:
        tag = f"{it['fase']}:{it['cid']}"
        if "error" in it["rec"]:
            det.append(f"FALLO: {tag}: caso con error ({it['rec']['error'][:60]})")
            fallo_case.add(tag)
            continue
        d = it["diagnostics"]
        if d is None:
            det.append(f"FALLO: {tag}: sin raw.response.diagnostics (¿capture_raw?)")
            fallo_case.add(tag)
            continue
        pt = d.get("prompt_tokens")
        if pt is None:
            det.append(f"FALLO: {tag}: prompt_tokens null (respaldo del interposer)")
            fallo_case.add(tag)
            continue
        exp = pref_pt.get(tag) or expected_extra.get(tag) or expected_extra.get(it["cid"])
        if exp is None:
            det.append(f"FALLO: {tag}: sin valor esperado (preflight/--expected-tokens)")
            fallo_case.add(tag)
        elif abs(pt - exp) > TOL_TOKENS:
            det.append(f"FALLO: {tag}: prompt_tokens {pt} ≠ esperado {exp} (|Δ| > {TOL_TOKENS})")
            fallo_case.add(tag)
        else:
            det.append(f"{tag}: {pt} tokens del motor (Δ={pt - exp:+})")
        for r in it["attributed"]:
            if r.get("n_ids") is not None and abs(r["n_ids"] - pt) > TOL_TOKENS:
                det.append(f"FALLO: {tag}: petición {r['id']} con {r['n_ids']} "
                           f"token ids ≠ prompt_tokens {pt}")
                fallo_case.add(tag)
    b = {"id": "b", "titulo": "prompt_tokens del motor (±2 del preflight y del log)",
         "detalles": det}

    # (c) una etapa, un grupo, sin skipped; ancho por petición
    det = []
    for it in items:
        tag = f"{it['fase']}:{it['cid']}"
        d = it["diagnostics"]
        if "error" in it["rec"] or d is None:
            det.append(f"FALLO: {tag}: sin diagnostics")
            fallo_case.add(tag)
            continue
        mal = []
        if len(d.get("stages") or []) != 1:
            mal.append(f"{len(d.get('stages') or [])} etapas")
        if len(d.get("chunks") or []) != 1:
            mal.append(f"{len(d.get('chunks') or [])} grupos")
        if d.get("skipped"):
            mal.append(f"skipped={sorted(d['skipped'])}")
        if mal:
            det.append(f"FALLO: {tag}: " + ", ".join(mal))
            fallo_case.add(tag)
        else:
            det.append(f"{tag}: 1 etapa, 1 grupo")
        want_w = None if it["canary"] else (fam_entry.get(it["familia"]) or {}).get("width")
        for r in it["attributed"]:
            if r.get("width") is None:
                det.append(f"{tag}: petición {r['id']} sin ancho registrado (no verificable)")
            elif want_w is None:
                det.append(f"{tag}: petición {r['id']} con ancho {r['width']} "
                           "(sin referencia en el preflight)")
            elif r["width"] != want_w:
                det.append(f"FALLO: {tag}: petición {r['id']} con ancho {r['width']} "
                           f"≠ {want_w} del preflight")
                fallo_case.add(tag)
    c = {"id": "c", "titulo": "1 etapa, 1 grupo, sin skipped y ancho por petición",
         "detalles": det}

    # (d) raw.request ↔ system_text congelado (reconstrucción con --server)
    det = []
    if ss_fatal:
        det.append(f"FALLO: {ss_error}")
    elif ss is None:
        det.append("FALLO: sin --server la puerta no certifica el montaje "
                   "(modo degradado solo diagnóstico)" + (f": {ss_error}" if ss_error else ""))
    try:
        spec_can, sha_can = dgemma_canary.load()
    except Exception as e:
        spec_can, sha_can = None, None
        det.append(f"aviso: spec del canario ilegible ({e})")
    pre_rot = int(preflight.get("rotate") or 0)
    for it in items:
        tag = f"{it['fase']}:{it['cid']}"
        rot = _rotate_of(it["meta"])
        if rot != pre_rot:
            det.append(f"FALLO: {it['fase']}: meta.rotate_choice={rot} pero el "
                       f"preflight es rotate={pre_rot}")
            fallo_case.add(tag)
            continue
        req = it["request"]
        if req is None:
            det.append(f"FALLO: {tag}: sin raw.request")
            fallo_case.add(tag)
            continue
        if it["canary"]:
            variant = it["cid"].split(":")[0]
            want_qs = (dgemma_canary.questions(spec_can, variant)
                       if spec_can and variant in spec_can["variants"] else None)
            if sha_can and it["meta"].get("canary_sha256") not in (None, sha_can):
                det.append(f"FALLO: {tag}: canary_sha256 del run ≠ spec congelada")
                fallo_case.add(tag)
                continue
            if want_qs is None:
                det.append(f"FALLO: {tag}: variante de canario desconocida")
                fallo_case.add(tag)
                continue
            if ss is not None:
                try:
                    ss.jev_schema(req)
                except Exception as e:
                    det.append(f"FALLO: {tag}: el servidor congelado rechaza el request: {e}")
                    fallo_case.add(tag)
                    continue
            ok = same_ordered(req.get("questions"), want_qs)
            det.append(f"{tag}: questions del canario ok" if ok
                       else f"FALLO: {tag}: questions distintas de la spec del canario")
            if not ok:
                fallo_case.add(tag)
            continue
        ent = fam_entry.get(it["familia"]) or {}
        if ss is not None:
            try:
                rebuilt = ss.system_text(ss.jev_schema(req))
            except Exception as e:
                det.append(f"FALLO: {tag}: el servidor congelado rechaza el request: {e}")
                fallo_case.add(tag)
                continue
            if not ent.get("system_text"):
                det.append(f"FALLO: {tag}: familia sin system_text en el preflight")
                fallo_case.add(tag)
            elif rebuilt == ent["system_text"]:
                det.append(f"{tag}: system_text reproducido (sha256={sha(rebuilt)[:12]})")
            else:
                det.append(f"FALLO: {tag}: system_text reconstruido ≠ congelado")
                fallo_case.add(tag)
            continue
        # modo degradado (diagnóstico): solo questions en orden, no certifica
        try:
            qs, _ = load_phase(it["fase"])
        except (ValueError, SystemExit) as e:
            det.append(f"FALLO: {tag}: fase no verificable ({e})")
            fallo_case.add(tag)
            continue
        want = rotate_choice(qs, rot) if rot else qs
        ok = same_ordered(req.get("questions"), want)
        det.append(f"diagnóstico {tag}: questions " +
                   ("coinciden en orden" if ok else "≠ fase"))
        if not ok:
            det.append(f"FALLO: {tag}: questions del request distintas de la fase")
            fallo_case.add(tag)
    d = {"id": "d", "titulo": "raw.request ↔ system_text congelado", "detalles": det}

    # (e) cobertura: ≥1 caso verificado y cada familia requerida con ≥1
    det = []
    valid = [it for it in items
             if f"{it['fase']}:{it['cid']}" not in fallo_case]
    det.append(f"{len(valid)}/{len(items)} casos verificados")
    if not valid:
        det.append("FALLO: ningún caso pudo verificarse")
    if require_families == "all":
        want_fams = set(fams)
    elif require_families:
        want_fams = set(require_families)
    else:
        want_fams = {it["familia"] for it in items if not it["canary"] and it["familia"]}
        if any(it["canary"] for it in items):
            want_fams.add("canario")
    for fam in sorted(want_fams, key=str):
        n = sum(1 for it in valid if (it["canary"] and fam == "canario")
                or (not it["canary"] and it["familia"] == fam))
        det.append(f"familia {str(fam)[:12]}: {n} caso(s) verificados" if n
                   else f"FALLO: familia {str(fam)[:12]} sin ningún caso verificado")
    e = {"id": "e", "titulo": "cobertura de casos y familias", "detalles": det}

    checks = [a, b, c, d, e]
    for chk in checks:
        chk["ok"] = not any(x.startswith("FALLO:") for x in chk["detalles"])
    return {"ok": all(chk["ok"] for chk in checks), "checks": checks,
            "casos": len(items), "verificados": len(valid),
            "ventana": ventana, "canvas": preflight.get("canvas")}


def print_report(res, printer=print):
    for chk in res["checks"]:
        printer(f"({chk['id']}) {chk['titulo']}: {'OK' if chk['ok'] else 'FALLO'}")
        for d in chk["detalles"]:
            printer(f"    {d}")
    printer(f"\n{res['verificados']}/{res['casos']} casos verificados; "
            f"puerta de montaje: {'ABIERTA' if res['ok'] else 'CERRADA'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", required=True, help="salida de jevbench.dgemma_preflight --out")
    ap.add_argument("--engine-log", required=True, help="log de vLLM con --enable-log-requests (DEBUG)")
    ap.add_argument("--results", required=True, help="results/<run>, un directorio o un JSON")
    ap.add_argument("--server", help="structured_server.py congelado (obligatorio para certificar)")
    ap.add_argument("--expected-tokens", help="JSON {<fase:id|id>: n} para casos ajenos al banco")
    ap.add_argument("--since", help="ignora registros anteriores a este timestamp del log (MM-DD HH:MM:SS)")
    ap.add_argument("--until", help="ignora registros posteriores a este timestamp del log")
    ap.add_argument("--log-from", type=int,
                    help="primera línea física del log (1-based, como `wc -l`/`sed -n`) "
                         "de la ventana del run")
    ap.add_argument("--log-to", type=int,
                    help="última línea física del log (1-based, inclusiva, como "
                         "`wc -l`/`sed -n A,Bp`) de la ventana")
    ap.add_argument("--require-families", nargs="?", const="all",
                    help="familias exigidas: all (defecto al usar la opción) o lista "
                         "separada por comas; sin la opción, las presentes en --results")
    ap.add_argument("--json", help="volcar el informe a un fichero")
    args = ap.parse_args()

    preflight = json.loads(Path(args.preflight).read_text())
    # lectura binaria + decodificación con reemplazo: la numeración física por
    # \n coincide con `wc -l`/`sed -n`; los \r de progreso no cuentan como línea
    log_text = Path(args.engine_log).read_bytes().decode("utf-8", errors="replace")
    files = result_files(args.results)
    ss = ss_error = None
    ss_fatal = False
    if args.server:
        ss, ss_error, ss_fatal = load_frozen_server(args.server, preflight.get("server_sha256"))
    expected_extra = json.loads(Path(args.expected_tokens).read_text()) if args.expected_tokens else {}
    req_fams = (None if args.require_families in (None, "all") else
                args.require_families.split(","))
    res = evaluate(files, preflight, log_text, ss=ss, ss_error=ss_error,
                   ss_fatal=ss_fatal, expected_extra=expected_extra,
                   since=args.since, until=args.until,
                   log_from=args.log_from, log_to=args.log_to,
                   require_families="all" if args.require_families == "all" else req_fams)
    print_report(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
