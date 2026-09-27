"""Regenerate the generated sections of docs/resultados.md from results/ (JEV-9).

  python -m jevbench.report            # rewrite the AUTO sections in place
  python -m jevbench.report --check    # exit 1 if docs/resultados.md is out of date

Only text between `<!-- AUTO:<name> -->` and `<!-- /AUTO:<name> -->` is replaced;
everything written by hand stays untouched. The runs in the scoreboard, in order,
come from docs/resultados_runs.txt (one per line, `#` comments allowed).
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "resultados.md"
RUNS = ROOT / "docs" / "resultados_runs.txt"


def read_runs(path=RUNS):
    runs = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            runs.append(line)
    return runs


def sections(runs):
    from .score import summary
    cmd = "python3 -m jevbench.score --summary " + " \\\n    ".join(
        " ".join(runs[i:i + 5]) for i in range(0, len(runs), 5))
    return {
        "comando": "```bash\npython3 -m jevbench.report   # regenera este documento (runs en docs/resultados_runs.txt)\n"
                   + cmd + "\n```",
        "marcador": summary(runs),
    }


def render(text, generated):
    """Replace every AUTO section present in `text`; unknown or missing ones are left alone."""
    for name, body in generated.items():
        pattern = re.compile(rf"(<!-- AUTO:{name} -->\n).*?(\n<!-- /AUTO:{name} -->)", re.DOTALL)
        text = pattern.sub(lambda m: m.group(1) + body + m.group(2), text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the document is out of date")
    ap.add_argument("--doc", default=str(DOC))
    ap.add_argument("--runs", default=str(RUNS))
    args = ap.parse_args(argv)
    doc = Path(args.doc)
    old = doc.read_text()
    missing = [n for n in ("comando", "marcador") if f"<!-- AUTO:{n} -->" not in old]
    if missing:
        sys.exit(f"{doc}: faltan los marcadores AUTO {missing}")
    new = render(old, sections(read_runs(args.runs)))
    if args.check:
        if new != old:
            print(f"{doc} está desactualizado: ejecuta python3 -m jevbench.report")
            return 1
        print(f"{doc} al día")
        return 0
    if new != old:
        doc.write_text(new)
        print(f"{doc} regenerado")
    else:
        print(f"{doc} ya estaba al día")
    return 0


if __name__ == "__main__":
    sys.exit(main())
