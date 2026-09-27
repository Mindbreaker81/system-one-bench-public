"""Segunda anotación clínica del GT (JEV-27).

  python3 -m jevbench.annotation2 packet
      -> docs/segunda_anotacion/packet.md            formulario a ciegas para el anotador
      -> docs/segunda_anotacion/respuestas.json      plantilla a rellenar (null = sin responder)
      -> docs/segunda_anotacion/seleccion.json       por qué se eligió cada caso (NO dar al anotador)

  python3 -m jevbench.annotation2 concordance docs/segunda_anotacion/respuestas.json \
      [--sources docs/segunda_anotacion/procedencia.json]   # separa usuario / codex
      -> % acuerdo y kappa por pregunta contra el GT actual (ponderado lineal solo en
         preguntas score; sin ponderar en choice/noul),
         más la lista de desacuerdos para adjudicar (cambios -> data/GT_CHANGELOG.md)

Criterio de selección de casos límite (pre-registrado): para cada pregunta se toman
los votos de todos los runs no-legacy sobre las variantes de idioma del caso; un campo
entra si el voto modal contradice el GT o si los modelos están divididos (<60% en el
modal). Solo se piden los campos disputados; el anotador no ve ni el GT ni los votos.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from . import metrics as M
from . import store
from .battery import DATA, load_phase

# (grupo, fases que aportan votos, fase de la que sale el texto)
SETS = [
    ("triage", ("triage_es", "triage_en"), "triage_es"),
    ("triage_ext", ("triage_ext_es", "triage_ext_en"), "triage_ext_es"),
    ("adv1", ("adv1",), "adv1"),
    ("adv2", ("adv2",), "adv2"),
    ("adv3", ("adv3",), "adv3"),
    ("papers32", ("papers32",), "papers32"),
]

OUT_DIR = Path("docs/segunda_anotacion")
SPLIT_SHARE = 0.60  # debajo de esto los modelos están "divididos"

SÍNO = {"0": "no", "1": "sí"}


def _runs(phase):
    return [p.parent.name for p in Path("results").glob(f"*/{phase}.json")
            if not p.parent.name.startswith("legacy")]


def _pred_key(ans, q):
    p = M.normalize(ans, q)
    if q["type"] == "choice":
        return p["label"]
    if q["type"] == "score":
        return str(M.level(p["value"], len(q["criteria"])))
    return "1" if p["value"] >= 0.5 else "0"


def select_cases():
    """{group: [(case, {q: info})]} con los campos disputados por caso."""
    selected = {}
    for group, vote_phases, text_phase in SETS:
        qs, cases = load_phase(text_phase)
        docs = [store.load(r, ph) for ph in dict.fromkeys(vote_phases) for r in _runs(ph)]
        docs = [d for d in docs if d]
        group_sel = []
        for c in cases:
            disputed = {}
            for name, q in qs.items():
                votes = Counter()
                for d in docs:
                    r = d["cases"].get(c.id)
                    if r and "error" not in r and name in r.get("answers", {}):
                        try:
                            votes[_pred_key(r["answers"][name], q)] += 1
                        except Exception:
                            pass
                if not votes:
                    continue
                modal, n_modal = votes.most_common(1)[0]
                share = n_modal / sum(votes.values())
                gt = str(c.gt[name])
                if modal != gt or share < SPLIT_SHARE:
                    disputed[name] = {"modal": modal, "share": round(share, 2), "gt": gt,
                                      "votes": dict(votes),
                                      "reason": "modal!=gt" if modal != gt else "dividido"}
            if disputed:
                group_sel.append((c, disputed))
        selected[group] = group_sel
    return selected


def _fmt_options(name, q):
    if q["type"] == "choice":
        return " · ".join(f"☐ `{k}` — {v}" for k, v in q["criteria"].items())
    if q["type"] == "score":
        return " · ".join(f"☐ `{i}` — {c}" for i, c in enumerate(q["criteria"]))
    return "☐ `0` (no)  ☐ `1` (sí)"


def packet(selected):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = ["# Segunda anotación del GT — formulario (a ciegas)\n",
          "Instrucciones: valora cada caso con tu propio criterio clínico. **No mires el GT "
          "actual ni los resultados de modelos** (en `data/` y `results/`); la concordancia "
          "solo es válida si la anotación es independiente.",
          "",
          "Por cada campo se pide una única respuesta. Después, traslada tus respuestas a "
          "`respuestas.json` (o devuélveme este archivo marcado y las paso yo).",
          "",
          "Criterios de las preguntas (mismos que usó el anotador original):",
          "",
          "- **department**: a qué departamento debería ir el mensaje",
          "- **urgency**: 0 bajo (rutina, sin deadline) · 1 medio (convendría pronto) · "
          "2 crítico (deadline, bloqueo o seguridad)",
          "- **clinical**: ¿contenido clínico que requiere juicio médico? (0 no / 1 sí)",
          "- **hostile**: ¿remitente hostil, insultante o amenazante? (0/1)",
          "- **same_day**: ¿requiere respuesta o acción HOY? (0/1)",
          "- **relevance / domain / design / depth / practice** (papers): ver opciones en cada caso",
          "",
          "Los casos de triaje se muestran en español; tu respuesta se aplica también a la "
          "variante inglesa del mismo caso.\n"]
    respuestas, seleccion = {}, {}
    n_fields = 0
    for group, _, _ in SETS:
        sel = selected.get(group, [])
        if not sel:
            continue
        md.append(f"\n## {group} ({len(sel)} casos)\n")
        for c, disputed in sel:
            md.append(f"### `{c.id}`\n")
            md.append("> " + c.state.replace("\n", "\n> ") + "\n")
            respuestas[c.id] = {}
            seleccion[c.id] = {"group": group, "fields": disputed}
            qs, _ = load_phase({g: tp for g, _, tp in SETS}[group])
            for name, info in disputed.items():
                n_fields += 1
                md.append(f"- **{name}**: {_fmt_options(name, qs[name])}")
            md.append("")
            for name in disputed:
                respuestas[c.id][name] = None
    (OUT_DIR / "packet.md").write_text("\n".join(md))
    (OUT_DIR / "respuestas.json").write_text(
        json.dumps(respuestas, ensure_ascii=False, indent=1) + "\n")
    (OUT_DIR / "seleccion.json").write_text(
        json.dumps(seleccion, ensure_ascii=False, indent=1) + "\n")
    print(f"packet.md: {len(respuestas)} casos, {n_fields} campos a anotar")
    print(f"respuestas.json + seleccion.json en {OUT_DIR}/")


def _index_gt():
    idx = {}
    for group, _, text_phase in SETS:
        qs, cases = load_phase(text_phase)
        for c in cases:
            idx[c.id] = (group, qs, c.gt)
    return idx


def cohen_kappa(pairs, weighted=False):
    """Cohen's kappa; pairs = [(gt, annotator)] label strings. weighted=True uses linear
    weights and is only meaningful for ordinal (score) questions; nominal questions
    (choice, noul) must use the unweighted form, otherwise the weight depends on the
    alphabetical order of the labels."""
    n = len(pairs)
    if n == 0:
        return float("nan")
    try:
        cats = sorted({v for ab in pairs for v in ab}, key=float)
    except ValueError:
        cats = sorted({v for ab in pairs for v in ab}, key=str)
    k = len(cats)
    if k < 2:
        return float("nan")
    rank = {v: i for i, v in enumerate(cats)}
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    o = e = 0.0
    for a in cats:
        for b in cats:
            w = abs(rank[a] - rank[b]) / (k - 1) if weighted else float(a != b)
            o += w * sum(1 for x, y in pairs if x == a and y == b) / n
            e += w * (ca[a] / n) * (cb[b] / n)
    return 1.0 if e == 0 else 1.0 - o / e


def concordance(path, sources=None, only=None):
    """sources: {case: {field: label}} (e.g. procedencia.json); only: keep that label."""
    answers = json.loads(Path(path).read_text())
    if sources and only:
        answers = {cid: {q: v for q, v in f.items() if sources.get(cid, {}).get(q) == only}
                   for cid, f in answers.items()}
        answers = {cid: f for cid, f in answers.items() if f}
    idx = _index_gt()
    per_q, disagreements, missing = {}, [], []
    for cid, fields in answers.items():
        if cid not in idx:
            missing.append(f"{cid}: caso desconocido")
            continue
        group, qs, gt = idx[cid]
        for name, val in fields.items():
            if val is None:
                missing.append(f"{cid}.{name}: sin responder")
                continue
            val = str(val)
            q = qs[name]
            valid = (list(q["criteria"]) if q["type"] == "choice" else
                     [str(i) for i in range(len(q["criteria"]))] if q["type"] == "score" else ["0", "1"])
            if val not in valid:
                missing.append(f"{cid}.{name}: valor {val!r} no válido {valid}")
                continue
            g = str(gt[name])
            per_q.setdefault(name, []).append((g, val))
            if g != val:
                disagreements.append((cid, group, name, g, val))
    qtype = {name: q["type"] for _, qs, _ in idx.values() for name, q in qs.items()}
    print("Casos elegidos por estar en disputa: el kappa mide acuerdo en casos límite, no la")
    print("fiabilidad global del GT (en una muestra aleatoria sería más alto).\n")
    print("| pregunta | n | % acuerdo | kappa | tipo |")
    print("|---|---|---|---|---|")
    for name, pairs in per_q.items():
        agree = sum(a == b for a, b in pairs) / len(pairs)
        ordinal = qtype[name] == "score"
        print(f"| {name} | {len(pairs)} | {agree:.0%} | {cohen_kappa(pairs, weighted=ordinal):.2f} | "
              f"{'ponderado lineal' if ordinal else 'sin ponderar'} |")
    if disagreements:
        print("\nDesacuerdos a adjudicar (gt → anotador2):")
        for cid, group, name, g, val in disagreements:
            print(f"- {cid} [{group}] {name}: {g} → {val}")
    if missing:
        print("\nAvisos:")
        for m in missing:
            print(f"- {m}")
    n_ok = sum(len(v) for v in per_q.values())
    print(f"\n{n_ok} respuestas contrastadas, {len(disagreements)} desacuerdos.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("packet")
    cp = sub.add_parser("concordance")
    cp.add_argument("answers")
    cp.add_argument("--sources", help="JSON {case: {field: source}}, e.g. docs/segunda_anotacion/procedencia.json")
    args = ap.parse_args()
    if args.cmd == "packet":
        packet(select_cases())
    elif args.sources:
        sources = json.loads(Path(args.sources).read_text())
        for label in sorted({v for f in sources.values() for v in f.values()}):
            print(f"\n## Procedencia: {label}\n")
            concordance(args.answers, sources, label)
    else:
        concordance(args.answers)


if __name__ == "__main__":
    main()
