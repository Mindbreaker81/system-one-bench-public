"""Rebuild the abstracts of data/papers32.json from PubMed.

  python3 -m jevbench.fetch_abstracts            # fetch + report (no writes)
  python3 -m jevbench.fetch_abstracts --write    # also save the downloaded abstracts

The public mirror ships papers32.json without abstracts (PubMed text is not ours to
redistribute): each paper keeps `pmid`, `title`, `journal`, `pubtypes` and `abstract_sha256`.
This tool fetches each PMID with efetch (rettype=abstract, retmode=text) and the same
normalisation the original fetcher used, fills `abstract` back in and warns when PubMed's
text no longer matches the stored hash (the record may have changed since sep-2026).
"""
import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "papers32.json"
EFETCH = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
          "?db=pubmed&id={pmid}&rettype=abstract&retmode=text")


def fetch(pmid):
    with urllib.request.urlopen(EFETCH.format(pmid=pmid), timeout=60) as r:
        return re.sub(r"\s*\n\s*", " ", r.read().decode().strip())


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="guardar los abstracts descargados en data/papers32.json")
    ap.add_argument("--sleep", type=float, default=0.4, help="pausa entre peticiones a NCBI")
    args = ap.parse_args(argv)

    papers = json.loads(DATA.read_text())
    same, drifted, failed, filled = [], [], [], []
    for i, p in enumerate(papers):
        if i:
            time.sleep(args.sleep)
        try:
            text = fetch(p["pmid"])
        except Exception as e:
            failed.append((p["pid"], f"{type(e).__name__}: {e}"))
            continue
        ref = p.get("abstract_sha256") or (sha(p["abstract"]) if p.get("abstract") else None)
        if ref:
            (same if ref == sha(text) else drifted).append(p["pid"])
        if not p.get("abstract"):
            p["abstract"] = text
            filled.append(p["pid"])
    print(f"{len(papers)} papers: {len(same)} con hash idéntico, {len(drifted)} cambiados en PubMed, "
          f"{len(failed)} fallos de descarga; {len(filled)} abstracts rellenados")
    if drifted:
        print(f"texto distinto al hash registrado (PubMed pudo cambiarlo): {', '.join(drifted)}")
    for pid, err in failed:
        print(f"{pid}: {err}")
    if args.write and filled:
        DATA.write_text(json.dumps(papers, ensure_ascii=False, indent=1) + "\n")
        print(f"{DATA} actualizado")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
