#!/usr/bin/env python3
"""W1 (JEV-89): papers de entrenamiento desde PubMed para el decisor propio.

Descarga artículos con las E-utilities de NCBI (esearch + efetch XML) en cinco
cubos temáticos, les asigna las etiquetas débiles fijadas en
docs/plan_modelo_propio.md §8 y escribe el corpus en el formato común JSONL.

  python3 scripts/jev89/papers_pubmed.py                     # ejecución completa
  python3 scripts/jev89/papers_pubmed.py --only ip --target 20   # humo

Salida (no se versiona; v2 tras la enmienda E1 de R-JEV89):
  /var/tmp/jev89/build/papers_pubmed_v2.jsonl
  /var/tmp/jev89/build/papers_pubmed_v2_informe.md

Política NCBI sin clave de API: <= 3 peticiones/s (SLEEP antes de cada
petición), tool=system-one-bench, email vacío y reintentos con backoff ante
errores de red o respuestas inválidas.

Decisiones (documentadas en el informe W1):
- Filtro común: años 2015-2026 [dp], english[lang], hasabstract[text] y
  medline[sb] (solo registros indexados: garantiza que los MeSH de los que
  dependen las señales de `design` están presentes). Además se excluyen los
  tipos de publicación que no aportan (erratas, retracciones, comments,
  letters, news, preprints...). En cliente se exige además Language == ["eng"]
  y abstract y título no vacíos.
- Cubos por MeSH Major Topic [Majr] (enmienda E1): el dominio es el tema
  principal indexado, no una mención incidental en título/abstract. Sin
  términos [tiab] en la definición de cubo.
- Muestreo determinista: esearch ordena por fecha de publicación y, cuando un
  cubo supera el tope de 10.000 resultados, la ventana 2015-2026 se divide por
  la mitad en meses hasta que cada trozo cabe; la lista completa se recorre
  con paso equiespaciado → reparto temporal uniforme en los cinco cubos.
- Un PMID presente en dos cubos se descarta por completo (regla del encargo).
- design (mapa LITERAL de §8, enmienda E1; se consultan tipos de publicación
  Y MeSH):
    rct: "Randomized Controlled Trial".
    meta: "Meta-Analysis" / "Systematic Review".
    review: "Review", "Guideline", "Practice Guideline", "Editorial",
      "Consensus Development Conference"*.
    basic: MeSH Animals sin Humans, o "In Vitro Techniques" / "Cell Line".
    cohort: PT "Observational Study" / "Comparative Study" y MeSH
      "Cohort/Retrospective/Prospective Studies", "Registries",
      "Sensitivity and Specificity".
  Resolución de señales coexistentes: meta > rct > review > basic > cohort,
  salvo meta + rct simultáneos, que es un conflicto real -> sin `design`.
  Sin señal prevista (p. ej. "Journal Article" a secas, "Case Reports",
  ensayos no aleatorizados) -> sin `design` (regla "ambiguos, sin design").
- relevance por cubo (§8): ip y oncology -> 2; ai_radiology y pulm_general
  -> 1; other -> 0. depth y practice nunca se etiquetan.
- Procedencia (E1): cada registro lleva `sources` (nombre, pmid y licencia de
  la fuente), `publishable: false` (derechos editoriales sin verificar), y en
  `meta` los autores (apellidos + iniciales) y `copyright` (CopyrightInformation
  de PubMed, si existe).
- `state` se construye con jevbench.battery.paper_state (misma plantilla que
  papers32) sin tocar battery.py.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jevbench.battery import paper_state  # noqa: E402  (misma plantilla que el banco)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "system-one-bench"
LICENSE = ("PubMed/NLM: uso interno; algunos abstracts con copyright del editor")
SLEEP = 0.34          # <= 3 peticiones/s sin clave de API
TARGET = 400          # artículos por cubo
RETMAX = 10000        # tope duro de esearch
BATCH = 200           # PMIDs por efetch
RETRIES = 4
TIMEOUT = 60

# Filtros comunes a los cinco cubos (la ventana [dp] la genera _common()).
LANG_FILTER = "english[lang]"
ABSTRACT_FILTER = "hasabstract[text]"
INDEXED_FILTER = "medline[sb]"
EXCLUDED_PT = ("Retracted Publication", "Published Erratum",
               "Comment", "Letter", "News",
               "Newspaper Article", "Historical Article", "Interview",
               "Lecture", "Legal Case", "Patient Education Handout",
               "Duplicate Publication", "Preprint", "English Abstract",
               "Biography", "Portrait", "Video-Audio Media", "Webcast")
# PubMed no admite "AND NOT": el NOT va como operador propio, sin AND delante.
PT_EXCLUSION = "NOT (" + " OR ".join(f'"{pt}"[pt]' for pt in EXCLUDED_PT) + ")"


def _common(t0=(2015, 1), t1=(2026, 12)):
    """Filtros comunes para la ventana de publicación t0..t1 ((año, mes))."""
    d = f'("{t0[0]}/{t0[1]:02d}"[dp] : "{t1[0]}/{t1[1]:02d}"[dp])'
    return f"{d} AND {LANG_FILTER} AND {ABSTRACT_FILTER} AND {INDEXED_FILTER} {PT_EXCLUSION}"


COMMON = _common()

# Consultas por cubo (enmienda E1, W1b): solo descriptores MeSH Major Topic
# [Majr], sin términos [tiab] — así el dominio del cubo es el tema principal
# indexado del artículo, no una mención incidental (hallazgo P2-1 de R-JEV89).
BUCKET_QUERY = {
    # Neumología intervencionista: broncoscopia como tema principal, EBUS
    # (Endosonography[Majr] solo con contexto pulmonar: sin él es EUS
    # gastrointestinal), procedimientos y enfermedades pleurales.
    "ip": '("Bronchoscopy"[Majr] OR ("Endosonography"[Majr] AND '
          '("Mediastinum"[Mesh] OR "Mediastinal Diseases"[Mesh] '
          'OR "Lung Neoplasms"[Mesh] OR "Bronchoscopy"[Mesh] OR "Lung"[Mesh] '
          'OR "Respiratory Tract Diseases"[Mesh])) OR "Pleurodesis"[Majr] '
          'OR "Thoracoscopy"[Majr] OR "Pleural Diseases"[Majr] '
          'OR "Pleural Neoplasms"[Majr])',
    # Oncología de pulmón: Lung Neoplasms con subencabezado mayor de terapia /
    # estadificación (pathology), o Lung Neoplasms[Majr] junto a un descriptor
    # mayor de tratamiento/estadificación.
    "oncology": '("Lung Neoplasms/drug therapy"[Majr] OR '
                '"Lung Neoplasms/therapy"[Majr] OR '
                '"Lung Neoplasms/radiotherapy"[Majr] OR '
                '"Lung Neoplasms/surgery"[Majr] OR '
                '"Lung Neoplasms/pathology"[Majr] OR '
                '("Lung Neoplasms"[Majr] AND ("Neoplasm Staging"[Majr] '
                'OR "Antineoplastic Agents"[Majr] OR "Immunotherapy"[Majr] '
                'OR "Molecular Targeted Therapy"[Majr])))',
    # IA en pulmón: descriptor mayor de IA/imagen Y descriptor mayor pulmonar.
    "ai_radiology": '(("Deep Learning"[Majr] OR "Machine Learning"[Majr] '
                    'OR "Radiomics"[Majr] OR "Artificial Intelligence"[Majr] '
                    'OR "Neural Networks, Computer"[Majr]) AND '
                    '("Lung"[Majr] OR "Lung Diseases"[Majr] '
                    'OR "Lung Neoplasms"[Majr] '
                    'OR "Solitary Pulmonary Nodule"[Majr] '
                    'OR "Multiple Pulmonary Nodules"[Majr]))',
    # Neumología general (EPOC, asma, apnea, neumonía) sin oncología mayor.
    "pulm_general": '(("Pulmonary Disease, Chronic Obstructive"[Majr] '
                    'OR "Asthma"[Majr] OR "Sleep Apnea Syndromes"[Majr] '
                    'OR "Pneumonia"[Majr]) NOT "Lung Neoplasms"[Majr])',
    # Otros órganos: descriptor mayor no respiratorio y NADA respiratorio mayor.
    "other": '(("Breast Neoplasms"[Majr] OR "Colorectal Neoplasms"[Majr] '
             'OR "Prostatic Neoplasms"[Majr] OR "Heart Failure"[Majr] '
             'OR "Myocardial Infarction"[Majr] OR "Stroke"[Majr] '
             'OR "Diabetes Mellitus, Type 2"[Majr] OR "Alzheimer Disease"[Majr] '
             'OR "Parkinson Disease"[Majr] OR "Arthritis, Rheumatoid"[Majr] '
             'OR "Inflammatory Bowel Diseases"[Majr] '
             'OR "Kidney Failure, Chronic"[Majr] OR "Depressive Disorder"[Majr] '
             'OR "Atrial Fibrillation"[Majr] OR "Osteoporosis"[Majr]) '
             'NOT ("Respiratory Tract Diseases"[Majr] OR "Lung"[Majr] '
             'OR "Respiratory System"[Majr] OR "Bronchoscopy"[Majr] '
             'OR "Thoracoscopy"[Majr] OR "Pleurodesis"[Majr]))',
}
# relevance derivada del cubo (§8).
BUCKET_RELEVANCE = {"ip": 2, "oncology": 2, "ai_radiology": 1, "pulm_general": 1, "other": 0}

# --- Mapeo design (literal, docs/plan_modelo_propio.md §8; enmienda E1:
# sin Adaptive/Pragmatic Clinical Trial ni "Observational Studies as Topic";
# lo no previsto -> sin design) ---
PT_RCT = {"Randomized Controlled Trial"}
PT_META = {"Meta-Analysis", "Systematic Review"}
PT_REVIEW = {"Review", "Guideline", "Practice Guideline", "Editorial"}
PT_REVIEW_PREFIX = ("Consensus Development Conference",)
PT_COHORT = {"Observational Study", "Comparative Study"}
MESH_COHORT = {"Cohort Studies", "Retrospective Studies", "Prospective Studies",
               "Registries", "Sensitivity and Specificity"}
MESH_BASIC_ANY = {"In Vitro Techniques", "Cell Line"}


def design_label(pubtypes, mesh):
    """Etiqueta `design` débil a partir de tipos de publicación y MeSH (§8).

    Devuelve la etiqueta o None cuando no hay señal o hay conflicto real
    (meta + rct). Las señales se resuelven por precedencia
    meta > rct > review > basic > cohort porque en PubMed los tipos se solapan
    de forma asimétrica (p. ej. casi todo "Meta-Analysis" lleva también
    "Review"; un RCT comparativo lleva "Comparative Study").
    """
    pts, ms = set(pubtypes), set(mesh)
    meta = bool(pts & PT_META)
    rct = bool(pts & PT_RCT)
    review = bool(pts & PT_REVIEW) or any(
        p.startswith(PT_REVIEW_PREFIX) for p in pts)
    basic = ("Animals" in ms and "Humans" not in ms) or bool(ms & MESH_BASIC_ANY)
    cohort = bool(pts & PT_COHORT) or bool(ms & MESH_COHORT)
    if meta and rct:
        return None
    for hit, label in ((meta, "meta"), (rct, "rct"), (review, "review"),
                       (basic, "basic"), (cohort, "cohort")):
        if hit:
            return label
    return None


# --- PubMed ---
def _request(url, parse, retries=RETRIES):
    """GET con SLEEP previo (<=3 req/s) y reintentos con backoff."""
    last = None
    for i in range(retries):
        time.sleep(SLEEP)
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                return parse(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if 400 <= e.code < 500 and e.code != 429:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                ET.ParseError, ValueError, KeyError) as e:
            last = e
        time.sleep(min(20.0, 1.5 * 2 ** i))
    raise SystemExit(f"PubMed: {retries} intentos fallidos -> {url[:160]} ({last})")


def esearch(query, t0=(2015, 1), t1=(2026, 12), retmax=RETMAX):
    """PMIDs que cumplen la consulta, ordenados por fecha de publicación."""
    params = {
        "db": "pubmed", "tool": TOOL, "email": "", "retmode": "json",
        "retmax": retmax, "sort": "pub date",
        "term": f"({query}) AND {_common(t0, t1)}",
    }
    url = f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    res = _request(url, lambda b: json.loads(b)["esearchresult"])
    warn = res.get("warninglist") or {}
    bad = {k: v for k, v in warn.items()
           if k != "outputmessages" and v} or res.get("errorlist")
    if bad:
        print(f"AVISO esearch: {bad}", file=sys.stderr)
    return res


def _month_index(t):
    return t[0] * 12 + (t[1] - 1)


def collect_pmids(query, t0=(2015, 1), t1=(2026, 12), retmax=RETMAX):
    """(count, PMIDs) de la consulta en la ventana t0..t1.

    Cuando los resultados superan `retmax` (tope duro de esearch) la ventana
    se parte por la mitad en meses y se acumula: el muestreo posterior cubre
    todo el periodo 2015-2026 aunque el cubo tenga cientos de miles de hits.
    """
    res = esearch(query, t0, t1, retmax)
    count, ids = int(res.get("count", 0)), res.get("idlist", [])
    if count <= retmax:
        return count, ids
    if _month_index(t1) - _month_index(t0) < 1:
        print(f"AVISO: {count} hits en un solo mes > retmax; truncado a {len(ids)}",
              file=sys.stderr)
        return count, ids
    m = (_month_index(t0) + _month_index(t1)) // 2
    left_end, right_start = (m // 12, m % 12 + 1), ((m + 1) // 12, (m + 1) % 12 + 1)
    c1, i1 = collect_pmids(query, t0, left_end, retmax)
    c2, i2 = collect_pmids(query, right_start, t1, retmax)
    return c1 + c2, i1 + i2


def _text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_article(pa):
    """PubmedArticle -> dict con los campos que necesita el corpus (o None)."""
    mc = pa.find("MedlineCitation")
    art = mc.find("Article") if mc is not None else None
    if mc is None or art is None:
        return None
    title = _text(art.find("ArticleTitle"))
    journal = (_text(art.find("Journal/Title")) or _text(art.find("Journal/ISOAbbreviation"))
               or _text(mc.find("MedlineJournalInfo/MedlineTA")))
    abstract_el = art.find("Abstract")
    parts = []
    copyright = None
    if abstract_el is not None:
        for at in abstract_el.findall("AbstractText"):
            txt = _text(at)
            if not txt:
                continue
            label = at.get("Label")
            parts.append(f"{label}: {txt}" if label else txt)
        copyright = _text(abstract_el.find("CopyrightInformation")) or None
    authors = []
    for a in art.findall("AuthorList/Author"):
        last, init = _text(a.find("LastName")), _text(a.find("Initials"))
        if last:
            authors.append(f"{last} {init}".strip())
        else:
            collective = _text(a.find("CollectiveName"))
            if collective:
                authors.append(collective)
    pubtypes = [p.text for p in art.findall("PublicationTypeList/PublicationType") if p.text]
    mesh = [d.text for d in mc.findall("MeshHeadingList/MeshHeading/DescriptorName") if d.text]
    langs = [l.text for l in art.findall("Language")]
    year = None
    for path in ("Journal/JournalIssue/PubDate/Year",
                 "Journal/JournalIssue/PubDate/MedlineDate",
                 "ArticleDate/Year"):
        m = re.search(r"\d{4}", art.findtext(path) or "")
        if m:
            year = int(m.group())
            break
    return {"pmid": (mc.findtext("PMID") or "").strip(), "title": title,
            "journal": journal.strip(), "abstract": " ".join(parts),
            "pubtypes": pubtypes, "mesh": mesh, "langs": langs, "year": year,
            "authors": authors, "copyright": copyright}


def efetch(pmids):
    url = (f"{EUTILS}/efetch.fcgi?db=pubmed&tool={TOOL}&email="
           f"&retmode=xml&id={','.join(pmids)}")
    root = _request(url, ET.fromstring)
    return [a for a in (parse_article(pa) for pa in root.iter("PubmedArticle")) if a]


def usable(art):
    """Abstract en inglés con título (filtro estricto en cliente)."""
    return bool(art["title"] and art["abstract"] and art["langs"] == ["eng"])


# --- Muestreo ---
def spread_order(length, target):
    """Permutación determinista de range(length): primero índices
    equiespaciados (reparto temporal sobre la lista ordenada por fecha),
    después los intermedios si hace falta rellenar."""
    if target <= 0 or length <= target:
        return list(range(length))
    step = max(1, length // target)
    return [i for off in range(step) for i in range(off, length, step)]


def double_bucket_pmids(idlists):
    """PMIDs presentes en más de un cubo: se descartan por completo."""
    seen = Counter(pmid for ids in idlists.values() for pmid in set(ids))
    return {pmid for pmid, n in seen.items() if n > 1}


def build_record(art, bucket, query):
    gt = {"domain": bucket, "relevance": BUCKET_RELEVANCE[bucket]}
    design = design_label(art["pubtypes"], art["mesh"])
    if design:
        gt["design"] = design
    meta = {"pmid": art["pmid"], "bucket": bucket, "query": query,
            "pubtypes": art["pubtypes"], "mesh": art["mesh"],
            "year": art["year"], "authors": art["authors"]}
    if art["copyright"]:
        meta["copyright"] = art["copyright"]
    return {"id": f"pubmed-{art['pmid']}", "task": "papers", "lang": "en",
            "state": paper_state({"title": art["title"], "journal": art["journal"],
                                  "pubtypes": art["pubtypes"],
                                  "abstract": art["abstract"]}),
            "gt": gt, "source": "pubmed", "license": LICENSE, "nc": False,
            "split": "", "publishable": False,
            "sources": [{"name": "PubMed/MEDLINE", "pmid": art["pmid"],
                         "license": ("NLM: uso con atribución; copyright "
                                     "del editor si consta")}],
            "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=int, default=TARGET, help="artículos por cubo")
    ap.add_argument("--retmax", type=int, default=RETMAX, help="tope de esearch")
    ap.add_argument("--batch", type=int, default=BATCH, help="PMIDs por efetch")
    ap.add_argument("--only", help="cubos separados por comas (depuración)")
    ap.add_argument("--out", default="/var/tmp/jev89/build/papers_pubmed_v2.jsonl")
    ap.add_argument("--informe", default="/var/tmp/jev89/build/papers_pubmed_v2_informe.md")
    args = ap.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    buckets = [b for b in BUCKET_QUERY if not only or b in only]
    if not buckets:
        raise SystemExit(f"--only sin cubos válidos; hay {sorted(BUCKET_QUERY)}")

    # 1) esearch por cubo (necesario antes de muestrear para detectar dobles cubos).
    idlists, hits = {}, {}
    for b in buckets:
        hits[b], idlists[b] = collect_pmids(BUCKET_QUERY[b], retmax=args.retmax)
        print(f"{b}: {hits[b]} hits, {len(idlists[b])} PMIDs recuperados")
    dup = double_bucket_pmids(idlists)

    # 2) efetch + etiquetado por cubo, hasta `target` válidos.
    records, stats = [], {}
    for b in buckets:
        cands = [p for p in idlists[b] if p not in dup]
        order = spread_order(len(cands), args.target)
        kept, drops, pos, fetched = [], Counter(), 0, 0
        while len(kept) < args.target and pos < len(order):
            idx = order[pos:pos + args.batch]
            pos += len(idx)
            arts = efetch([cands[i] for i in idx])
            fetched += len(idx)
            drops["sin_registro"] += len(idx) - len(arts)
            for a in arts:
                if not usable(a):
                    drops["sin_abstract_en"] += 1
                    continue
                kept.append(build_record(a, b, BUCKET_QUERY[b]))
        # dedup defensiva dentro del cubo (efetch no debería repetir PMIDs)
        uniq, seen = [], set()
        for r in kept:
            if r["meta"]["pmid"] not in seen:
                seen.add(r["meta"]["pmid"])
                uniq.append(r)
        kept = uniq[:args.target]
        records.extend(kept)
        designs = Counter(r["gt"].get("design", "(sin design)") for r in kept)
        stats[b] = {"hits": hits[b], "idlist": len(idlists[b]), "cands": len(cands),
                    "fetched": fetched, "kept": len(kept), "drops": dict(drops),
                    "designs": dict(designs)}
        print(f"{b}: {len(kept)} registros "
              f"(examinados {fetched}; descartes {dict(drops)}); design={dict(designs)}")

    # 3) corpus + informe.
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(records)
    design_all = Counter(r["gt"].get("design", "(sin design)") for r in records)
    no_design = design_all.pop("(sin design)", 0)
    lines = ["# W1 — papers_pubmed: informe", ""]
    lines += [f"Objetivo por cubo: {args.target}; corpus total: **{total}** registros.", ""]
    lines += ["## Consultas", ""]
    for b in buckets:
        lines.append(f"- **{b}** (relevance {BUCKET_RELEVANCE[b]}): `{BUCKET_QUERY[b]}`")
    lines += ["", "Filtros comunes: `" + COMMON + "`", ""]
    lines += ["## Resultados por cubo", "",
              "| Cubo | hits esearch | PMIDs | tras doble cubo | examinados | corpus |",
              "|---|---|---|---|---|---|"]
    for b in buckets:
        s = stats[b]
        lines.append(f"| {b} | {s['hits']} | {s['idlist']} | {s['cands']} "
                     f"| {s['fetched']} | {s['kept']} |")
    lines += ["", "## Distribución de design", "",
              "| design | n |", "|---|---|"]
    for d, n in design_all.most_common():
        lines.append(f"| {d} | {n} |")
    lines += [f"| **(sin design)** | **{no_design}** |", ""]
    lines += ["## Descartados por doble cubo", "",
              f"PMIDs presentes en más de un cubo, retirados de todos: **{len(dup)}**.", ""]
    lines += ["## Otros descartes en cliente", "",
              "| Cubo | motivo -> n |", "|---|---|"]
    for b in buckets:
        lines.append(f"| {b} | {stats[b]['drops']} |")
    lines.append("")
    report = "\n".join(lines)
    Path(args.informe).write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\n{args.out} ({total} líneas) + {args.informe} escritos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
