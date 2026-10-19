"""Tests unitarios de scripts/jev89/papers_pubmed.py (JEV-89, flujo W1).

Sin red: cubren los mapeos de `design` (tipos de publicación/MeSH), el mapeo
cubo -> relevance, el formato de `state` (misma plantilla que
jevbench.battery.paper_state), el formato del registro JSONL, el descarte por
doble cubo y el muestreo equiespaciado.
"""
import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "jev89" / "papers_pubmed.py"
_spec = importlib.util.spec_from_file_location("papers_pubmed", _SCRIPT)
pp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pp)


def D(pubtypes, mesh=()):
    return pp.design_label(list(pubtypes), list(mesh))


class TestDesign(unittest.TestCase):
    def test_rct(self):
        self.assertEqual(D(["Journal Article", "Randomized Controlled Trial"]), "rct")

    def test_variantes_ensayo_no_literales_sin_design(self):
        """E1: Adaptive/Pragmatic Clinical Trial no están en el mapa §8 -> sin design."""
        for pt in ("Adaptive Clinical Trial", "Pragmatic Clinical Trial",
                   "Controlled Clinical Trial"):
            self.assertIsNone(D([pt]), pt)

    def test_meta(self):
        self.assertEqual(D(["Meta-Analysis"]), "meta")
        self.assertEqual(D(["Systematic Review"]), "meta")
        # combinación frecuente en PubMed: las tres a la vez
        self.assertEqual(D(["Systematic Review", "Meta-Analysis", "Review"]), "meta")

    def test_meta_absorbe_review_y_cohort(self):
        self.assertEqual(D(["Meta-Analysis", "Review", "Comparative Study"]), "meta")
        self.assertEqual(D(["Systematic Review"], ["Cohort Studies"]), "meta")

    def test_review(self):
        for pt in ("Review", "Guideline", "Practice Guideline", "Editorial",
                   "Consensus Development Conference",
                   "Consensus Development Conference, NIH"):
            self.assertEqual(D([pt]), "review", pt)

    def test_basic_animals_sin_humans(self):
        self.assertEqual(D(["Journal Article"], ["Animals", "Mice"]), "basic")
        # Animals + Humans no es basic por esa señal
        self.assertIsNone(D(["Journal Article"], ["Animals", "Humans"]))

    def test_basic_in_vitro_y_cell_line(self):
        self.assertEqual(D(["Journal Article"], ["In Vitro Techniques"]), "basic")
        self.assertEqual(D(["Journal Article"], ["Cell Line"]), "basic")

    def test_cohort_pubtypes(self):
        self.assertEqual(D(["Observational Study"]), "cohort")
        self.assertEqual(D(["Comparative Study"]), "cohort")

    def test_cohort_mesh(self):
        for m in ("Cohort Studies", "Retrospective Studies", "Prospective Studies",
                  "Registries", "Sensitivity and Specificity"):
            self.assertEqual(D(["Journal Article"], [m]), "cohort", m)

    def test_observational_studies_as_topic_no_es_cohort(self):
        """E1: un MeSH «as Topic» no establece el diseño -> sin design."""
        self.assertIsNone(D(["Journal Article"], ["Observational Studies as Topic"]))

    def test_conflicto_meta_rct_sin_design(self):
        self.assertIsNone(D(["Meta-Analysis", "Randomized Controlled Trial"]))

    def test_rct_absorbe_comparative(self):
        self.assertEqual(D(["Randomized Controlled Trial", "Comparative Study",
                            "Multicenter Study"]), "rct")

    def test_precedencia_review_sobre_basic_y_cohort(self):
        self.assertEqual(D(["Review"], ["Animals"]), "review")
        self.assertEqual(D(["Review"], ["Cohort Studies"]), "review")

    def test_precedencia_basic_sobre_cohort(self):
        self.assertEqual(D(["Comparative Study"], ["Animals"]), "basic")
        self.assertEqual(D(["Journal Article"],
                           ["Animals", "Cohort Studies"]), "basic")

    def test_sin_senal_sin_design(self):
        self.assertIsNone(D(["Journal Article"]))
        self.assertIsNone(D(["Case Reports"]))
        self.assertIsNone(D(["Clinical Trial"]))          # no aleatorizado -> ambiguo
        self.assertIsNone(D(["Clinical Trial, Phase III"]))
        self.assertIsNone(D(["Journal Article"], ["Humans"]))
        self.assertIsNone(D([], []))


class TestRelevance(unittest.TestCase):
    def test_cubo_a_relevance(self):
        self.assertEqual(pp.BUCKET_RELEVANCE,
                         {"ip": 2, "oncology": 2, "ai_radiology": 1,
                          "pulm_general": 1, "other": 0})

    def test_los_cinco_cubos_tienen_consulta(self):
        self.assertEqual(set(pp.BUCKET_QUERY), set(pp.BUCKET_RELEVANCE))
        for b in pp.BUCKET_QUERY.values():
            self.assertTrue(b.strip())

    def test_cubos_solo_major_topic(self):
        """E1: los cubos se definen con [Majr]; nada de términos [tiab]."""
        for name, q in pp.BUCKET_QUERY.items():
            self.assertNotIn("[tiab]", q, name)
            self.assertIn("[Majr]", q, name)


_ART = {"pmid": "12345678", "title": "Radial EBUS biopsy of nodules",
        "journal": "Respiration", "abstract": "BACKGROUND: We did X.",
        "pubtypes": ["Journal Article", "Randomized Controlled Trial"],
        "mesh": ["Humans", "Bronchoscopy"], "langs": ["eng"], "year": 2021,
        "authors": ["Garcia M", "Rosell R"], "copyright": "(c) 2021 Elsevier"}


class TestStateYRegistro(unittest.TestCase):
    def test_state_misma_plantilla_que_el_banco(self):
        rec = pp.build_record(dict(_ART), "ip", "Q")
        esperado = ("Title: Radial EBUS biopsy of nodules\n"
                    "Journal: Respiration\n"
                    "Publication types: Journal Article, Randomized Controlled Trial\n"
                    "\nAbstract: BACKGROUND: We did X.")
        self.assertEqual(rec["state"], esperado)
        # y es literalmente la salida de battery.paper_state
        from jevbench.battery import paper_state
        self.assertEqual(rec["state"], paper_state(
            {"title": _ART["title"], "journal": _ART["journal"],
             "pubtypes": _ART["pubtypes"], "abstract": _ART["abstract"]}))

    def test_formato_registro(self):
        rec = pp.build_record(dict(_ART), "oncology", "SELECT")
        self.assertEqual(rec["id"], "pubmed-12345678")
        self.assertEqual(rec["task"], "papers")
        self.assertEqual(rec["lang"], "en")
        self.assertEqual(rec["source"], "pubmed")
        self.assertTrue(rec["license"].startswith("PubMed/NLM"))
        self.assertFalse(rec["nc"])
        self.assertEqual(rec["split"], "")
        self.assertEqual(rec["gt"], {"domain": "oncology", "relevance": 2,
                                     "design": "rct"})
        self.assertEqual({"pmid", "bucket", "query", "pubtypes", "mesh", "year",
                          "authors", "copyright"}, set(rec["meta"]))
        self.assertEqual(rec["meta"]["pmid"], "12345678")
        self.assertEqual(rec["meta"]["bucket"], "oncology")
        self.assertEqual(rec["meta"]["query"], "SELECT")

    def test_procedencia_e1(self):
        """E1: sources con licencia/atribución, publishable False, autores y
        copyright en meta."""
        rec = pp.build_record(dict(_ART), "ip", "Q")
        self.assertEqual(rec["publishable"], False)
        self.assertEqual(rec["sources"],
                         [{"name": "PubMed/MEDLINE", "pmid": "12345678",
                           "license": "NLM: uso con atribución; copyright "
                                      "del editor si consta"}])
        self.assertEqual(rec["meta"]["authors"], ["Garcia M", "Rosell R"])
        self.assertEqual(rec["meta"]["copyright"], "(c) 2021 Elsevier")
        # sin copyright declarado -> la clave no aparece en meta
        rec2 = pp.build_record(dict(_ART, copyright=None), "ip", "Q")
        self.assertNotIn("copyright", rec2["meta"])

    def test_gt_parcial_sin_design(self):
        art = dict(_ART, pubtypes=["Journal Article"], mesh=["Humans"])
        rec = pp.build_record(art, "other", "Q")
        self.assertEqual(rec["gt"], {"domain": "other", "relevance": 0})
        self.assertNotIn("depth", rec["gt"])
        self.assertNotIn("practice", rec["gt"])


XML = """<PubmedArticleSet><PubmedArticle>
<MedlineCitation Status="MEDLINE"><PMID>999</PMID>
<Article>
<Journal><Title>J Thorac <i>Dis</i></Title><ISOAbbreviation>JTD</ISOAbbreviation>
<JournalIssue><PubDate><Year>2020</Year><Month>Mar</Month></PubDate></JournalIssue></Journal>
<ArticleTitle>Cryobiopsy in <sub>ILD</sub> diagnosis</ArticleTitle>
<AuthorList>
<Author><LastName>García</LastName><ForeName>María</ForeName><Initials>M</Initials></Author>
<Author><LastName>Ross</LastName><Initials>J K</Initials></Author>
<Author><CollectiveName>ILD Group</CollectiveName></Author>
</AuthorList>
<Abstract><AbstractText Label="BACKGROUND">First part.</AbstractText>
<AbstractText Label="RESULTS">Second <i>part</i>.</AbstractText>
<CopyrightInformation>(c) 2020 Elsevier</CopyrightInformation></Abstract>
<Language>eng</Language>
<PublicationTypeList>
<PublicationType UI="D016428">Journal Article</PublicationType>
<PublicationType UI="D016430">Observational Study</PublicationType>
</PublicationTypeList></Article>
<MeshHeadingList>
<MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading>
<MeshHeading><DescriptorName>Retrospective Studies</DescriptorName></MeshHeading>
</MeshHeadingList>
</MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation Status="PubMed-not-MEDLINE"><PMID>1</PMID>
</MedlineCitation></PubmedArticle></PubmedArticleSet>"""


class TestParseYFiltros(unittest.TestCase):
    def test_parse_article(self):
        arts = [pp.parse_article(pa) for pa in ET.fromstring(XML).iter("PubmedArticle")]
        a = arts[0]
        self.assertEqual(a["pmid"], "999")
        self.assertEqual(a["title"], "Cryobiopsy in ILD diagnosis")
        self.assertEqual(a["journal"], "J Thorac Dis")
        self.assertEqual(a["abstract"], "BACKGROUND: First part. RESULTS: Second part.")
        self.assertEqual(a["pubtypes"], ["Journal Article", "Observational Study"])
        self.assertEqual(a["mesh"], ["Humans", "Retrospective Studies"])
        self.assertEqual(a["langs"], ["eng"])
        self.assertEqual(a["year"], 2020)
        self.assertEqual(a["authors"], ["García M", "Ross J K", "ILD Group"])
        self.assertEqual(a["copyright"], "(c) 2020 Elsevier")
        self.assertIsNone(arts[1])  # sin Article -> None

    def test_usable_exige_eng_y_abstract(self):
        self.assertTrue(pp.usable(dict(_ART)))
        self.assertFalse(pp.usable(dict(_ART, abstract="")))
        self.assertFalse(pp.usable(dict(_ART, title="")))
        self.assertFalse(pp.usable(dict(_ART, langs=["spa"])))
        self.assertFalse(pp.usable(dict(_ART, langs=["eng", "spa"])))

    def test_doble_cubo(self):
        dup = pp.double_bucket_pmids({"a": ["1", "2", "3"], "b": ["3", "4"],
                                      "c": ["5"]})
        self.assertEqual(dup, {"3"})

    def test_spread_order_cubre_todo_y_se_reparte(self):
        o = pp.spread_order(10000, 400)
        self.assertEqual(sorted(o), list(range(10000)))
        self.assertEqual(o[:400], list(range(0, 10000, 25)))
        self.assertEqual(pp.spread_order(100, 400), list(range(100)))
        self.assertEqual(pp.spread_order(50, 0), list(range(50)))


if __name__ == "__main__":
    unittest.main()
