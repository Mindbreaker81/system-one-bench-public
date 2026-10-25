"""Tests del set opt-in bscribe_verif (JEV-111): coherencia del GT, estado por
transcripción y puntuación con resultados falsos (offline).

  python3 -m unittest tests.test_bscribe_verif -v
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import bscribe_verif as bv
from jevbench import store


class TestGT(unittest.TestCase):
    """GT promovido a data/ (validado en JEV-112); el borrador ya no existe."""
    @classmethod
    def setUpClass(cls):
        cls.facts = bv.load("facts")
        cls.states = bv.load("states")

    def test_gt_coherent(self):
        self.assertEqual(bv.check(self.facts, self.states), [])

    def test_every_case_has_both_labels(self):
        for case, fs in self.facts["cases"].items():
            self.assertEqual({f["label"] for f in fs}, {0, 1}, case)

    def test_reference_states_untouched_by_normalization(self):
        for st in self.states["states"].values():
            if st["source"] == "reference":
                self.assertNotIn("raw_text", st)
            else:
                self.assertEqual(bv.bscribe_normalize(st["raw_text"]), st["text"])

    def test_questions_stable_and_wire_format(self):
        qs = bv.questions_for(self.facts["cases"]["B1"])
        self.assertEqual(len(qs), len(self.facts["cases"]["B1"]))
        for q in qs.values():
            self.assertEqual(q["type"], "noul")
            self.assertIn("«", q["instructions"])
            self.assertEqual(q["criteria"], bv.CRITERIA)
        self.assertEqual(bv.questions_hash(self.facts), bv.questions_hash(self.facts))


class TestStatus(unittest.TestCase):
    def test_evidence_lost_and_trap(self):
        true_fact = {"evidence": [r"(siete|7) pases"], "trap": []}
        false_fact = {"evidence": [], "trap": [r"(seis|6) pases"]}
        self.assertEqual(bv.status(true_fact, "Siete pases con aguja"), "included")
        self.assertEqual(bv.status(true_fact, "fases con aguja"), "evidence_lost")
        self.assertEqual(bv.status(false_fact, "se hicieron 6 pases"), "trap_present")
        self.assertEqual(bv.status(false_fact, "se hicieron 7 pases"), "included")

    def test_bscribe_normalization(self):
        self.assertEqual(bv.bscribe_normalize("22 gauches, Rouse negativo"), "22 gauge, ROSE negativo")
        self.assertEqual(bv.bscribe_normalize("tres fases"), "tres fases")  # sin contexto de punción
        self.assertEqual(bv.bscribe_normalize("aguja, tres fases"), "aguja, tres pases")

    def test_normalize_strips_accents(self):
        self.assertEqual(bv.normalize("Estación  Siete"), "estacion siete")


class TestScore(unittest.TestCase):
    FACTS = {"cases": {"X1": [
        {"id": "X1-01", "claim": "a", "label": 1, "family": "pases", "evidence": [r"siete"], "trap": []},
        {"id": "X1-02", "claim": "b", "label": 0, "family": "pases", "evidence": [], "trap": [r"seis"]},
    ]}}
    STATES = {"states": {
        "X1__reference": {"case": "X1", "source": "reference", "text": "siete pases"},
        "X1__asr": {"case": "X1", "source": "asr", "text": "seis pases"},
    }}

    def test_rates_and_exclusion(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "ROOT", Path(d)):
            store.save("fake", bv.PHASE, {"meta": {}, "cases": {
                "X1__reference": {"answers": {"f_X1_01": {"noul": 0.95}, "f_X1_02": {"noul": 0.2}}},
                "X1__asr": {"answers": {"f_X1_01": {"noul": 0.4}, "f_X1_02": {"noul": 0.9}}},
            }})
            ds = bv.decisions("fake", self.FACTS, self.STATES)
        # en X1__asr: X1-01 pierde la evidencia y X1-02 tiene la trampa → ambos excluidos
        self.assertEqual({(d["state"], d["fact"]) for d in ds},
                         {("X1__reference", "X1-01"), ("X1__reference", "X1-02")})
        r = bv._rates(ds)
        self.assertEqual((r["accuracy"], r["sensitivity"], r["fp_rate"]), (1.0, 1.0, 0.0))
        self.assertEqual(bv.verdict(r), "CUMPLE")

    def test_run_refuses_unpromoted_gt(self):
        with mock.patch.object(bv, "DATA", Path(tempfile.mkdtemp())):
            with self.assertRaises(SystemExit):
                bv.load("facts")


if __name__ == "__main__":
    unittest.main()
