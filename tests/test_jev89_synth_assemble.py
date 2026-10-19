"""JEV-89: generador sintético (W3) y ensamblado (W5), sin red ni datos del banco."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "jev89"))
import assemble  # noqa: E402
import synth_triage as S  # noqa: E402

GT = {"department": "admin", "urgency": 0, "clinical": 0, "hostile": 0, "same_day": 0}


class ParseLabels(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(S.parse_labels('ok {"department": "admin", "urgency": 0, "clinical": 0, '
                                        '"hostile": 0, "same_day": 0}'), GT)

    def test_rechaza_rangos_tipos_y_departamentos(self):
        for bad in ['{"department": "admin", "urgency": 3, "clinical": 0, "hostile": 0, "same_day": 0}',
                    '{"department": "admin", "urgency": 1.5, "clinical": 0, "hostile": 0, "same_day": 0}',
                    '{"department": "admin", "urgency": 1, "clinical": true, "hostile": 0, "same_day": 0}',
                    '{"department": "cardio", "urgency": 1, "clinical": 0, "hostile": 0, "same_day": 0}',
                    '{"department": "admin", "urgency": 1}', "sin json"]:
            self.assertIsNone(S.parse_labels(bad), bad)


class Accept(unittest.TestCase):
    def test_exacta_en_las_cinco(self):
        self.assertTrue(S.accept(GT, dict(GT)))
        for q, v in [("urgency", 1), ("same_day", 1), ("department", "urgencias"), ("hostile", 1)]:
            self.assertFalse(S.accept(GT, dict(GT, **{q: v})), q)

    def test_sin_excepcion_por_manipulacion(self):
        self.assertFalse(S.accept(GT, dict(GT, urgency=2), manip=True))

    def test_sin_comprobacion(self):
        self.assertFalse(S.accept(GT, None))


class SampleTuple(unittest.TestCase):
    def test_restricciones_de_coherencia(self):
        rng = random.Random(0)
        for _ in range(3000):
            gt, manip = S.sample_tuple(rng)
            if gt["department"] == "urgencias":
                self.assertEqual((gt["urgency"], gt["clinical"], gt["same_day"]), (2, 1, 1))
            if manip:
                self.assertIn(gt["department"], ("admin", "consulta_externa"))
                self.assertEqual((gt["urgency"], gt["same_day"]), (0, 0))
            if gt["urgency"] == 2:
                self.assertEqual(gt["same_day"], 1)

    def test_prompt_de_manipulacion_exige_senales_visibles(self):
        p = S.gen_prompt(GT, True, "es", "paciente", "refund request", None, random.Random(1))
        self.assertIn("MUST be visible in the text", p)


class Assemble(unittest.TestCase):
    def rec(self, source, **meta):
        return {"id": f"{source}-1", "source": source, "meta": meta}

    def test_procedencia(self):
        r = assemble.provenance(self.rec("synthetic_qwen38", seed_codiesp="S0001.txt"))
        self.assertTrue(r["publishable"])
        self.assertEqual(r["sources"][1]["license"], "CC BY 4.0")
        self.assertFalse(assemble.provenance(self.rec("pmr_reddit"))["publishable"])
        self.assertFalse(assemble.provenance(self.rec("pubmed", pmid="1"))["publishable"])

    def test_split_agrupado_y_pmr(self):
        a = self.rec("synthetic_qwen38", seed_codiesp="S0002.txt")
        b = dict(a, id="otro")
        self.assertEqual(assemble.split_of(a), assemble.split_of(b))
        self.assertEqual(assemble.split_of(self.rec("pmr_reddit", pmr_split="dev")), "val")
        self.assertEqual(assemble.split_of(self.rec("pmr_reddit", pmr_split="train")), "train")


class LoadSourcesHistoricos(unittest.TestCase):
    def test_check_historico_con_coerciones_se_rechaza(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            gt = {"department": "admin", "urgency": 0, "clinical": 0, "hostile": 0, "same_day": 0}
            good = {"id": "s1", "source": "synthetic_qwen38", "gt": gt,
                    "meta": {"check": dict(gt), "manipulation": True}}
            bad = {"id": "s2", "source": "synthetic_qwen38", "gt": gt,
                   "meta": {"check": dict(gt, clinical=False, urgency=0.0)}}
            missing = {"id": "s3", "source": "synthetic_qwen38", "gt": gt,
                       "meta": {"check": {"department": "admin"}}}
            (d / "synth_triage.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (good, bad, missing)))
            (d / "pmr_reddit.jsonl").write_text("")
            (d / "papers.jsonl").write_text("")
            rows, _ = assemble.load_sources(d, "papers.jsonl")
            ids = [r["id"] for r in rows["synth_triage.jsonl"]]
            self.assertEqual(ids, ["s1"])
            m = rows["synth_triage.jsonl"][0]["meta"]
            self.assertTrue(m["manipulation_requested"])
            self.assertFalse(m["manipulation_verified"])


if __name__ == "__main__":
    unittest.main()
