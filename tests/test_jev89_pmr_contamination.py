"""JEV-89 W2/W4/W4c: mapeo PMR, normalización y filtro de contaminación.

Los datos del banco se inventan en el propio test; no se lee data/.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "jev89"))

import contamination as cont  # noqa: E402
import convert_pmr as pmr  # noqa: E402


class TestPmrLevelMap(unittest.TestCase):
    def test_enteros_1_a_6(self):
        expected = {
            1: ("urgencias", 2, 1),
            2: ("consulta_externa", 2, 1),
            3: ("consulta_externa", 1, 1),
            4: ("consulta_externa", 1, 0),
            5: ("consulta_externa", 0, 0),
            6: ("consulta_externa", 0, 0),
        }
        for level, (dept, urg, same) in expected.items():
            n, gt = pmr.map_level(level)
            self.assertEqual(n, level)
            self.assertEqual(gt["department"], dept)
            self.assertEqual(gt["urgency"], urg)
            self.assertEqual(gt["same_day"], same)
            self.assertEqual(gt["clinical"], 1)
            self.assertNotIn("hostile", gt)

    def test_float_redondeo_half_up(self):
        self.assertEqual(pmr.round_level(3.5), 4)
        self.assertEqual(pmr.round_level(4.4), 4)
        self.assertEqual(pmr.round_level(4.5), 5)
        self.assertEqual(pmr.round_level(1.3333333333333333), 1)
        n, gt = pmr.map_level(1.5)
        self.assertEqual(n, 2)
        self.assertEqual(gt["department"], "consulta_externa")
        self.assertEqual(gt["urgency"], 2)

    def test_fuera_de_rango(self):
        with self.assertRaises(ValueError):
            pmr.round_level(0.2)
        with self.assertRaises(ValueError):
            pmr.round_level(7.1)


class TestNormalize(unittest.TestCase):
    def test_minusculas_acentos_alfanum(self):
        self.assertEqual(
            cont.normalize("  ¡Hólá, Mundo! 123  "),
            "hola mundo 123",
        )

    def test_tokens_y_8gramas(self):
        toks = cont.tokens("uno dos tres cuatro cinco seis siete ocho nueve")
        self.assertEqual(len(toks), 9)
        grams = cont.ngrams(toks, 8)
        self.assertEqual(len(grams), 2)
        self.assertIn(tuple(toks[:8]), grams)
        self.assertEqual(cont.ngrams(toks[:7], 8), set())


class TestContaminationFilter(unittest.TestCase):
    def _bank_dir(self, tmp: Path) -> Path:
        data = tmp / "data"
        data.mkdir()
        # caso adversarial inventado
        (data / "adv_fake.json").write_text(
            json.dumps({
                "FAKE_BANK_01": {
                    "state": (
                        "alpha bravo charlie delta echo foxtrot golf hotel "
                        "india juliet bankmarker"
                    ),
                    "department": "admin",
                    "urgency": 0,
                    "clinical": 0,
                    "hostile": 0,
                    "same_day": 0,
                }
            }),
            encoding="utf-8",
        )
        # paper inventado con PMID
        (data / "papers_fake.json").write_text(
            json.dumps([{
                "pid": "PX",
                "pmid": "99999999",
                "title": "Invented Paper About Nothing Useful Here",
                "journal": "Fake J",
                "pubtypes": ["Journal Article"],
                "abstract": (
                    "word0 word1 word2 word3 word4 word5 word6 word7 "
                    "word8 uniqueabstracttoken"
                ),
            }]),
            encoding="utf-8",
        )
        # triaje bilingüe inventado
        (data / "bench_fake.json").write_text(
            json.dumps([{
                "name": "T99_fake",
                "expected": {"department": "admin", "urgency": 0,
                             "clinical": 0, "hostile": 0, "same_day": 0},
                "es": "mensaje corto sin ocho tokens utiles aqui ya",
                "en": (
                    "yankee zulu quebec romeo sierra tango umbrella victor "
                    "whiskey xray benchonly"
                ),
            }]),
            encoding="utf-8",
        )
        return data

    def test_descarta_8grama_pmid_y_duplicado(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data_dir = self._bank_dir(tmp)
            gram_to_case, bank_pmids, _cov = cont.load_bank(
                data_dir, require_phases=False
            )
            self.assertIn("99999999", bank_pmids)

            # 8-grama compartido con FAKE_BANK_01 (alpha…hotel)
            dirty_ngram = {
                "id": "cand-ngram",
                "state": (
                    "prefix alpha bravo charlie delta echo foxtrot golf hotel "
                    "suffix extra"
                ),
                "meta": {},
            }
            # PMID del banco
            dirty_pmid = {
                "id": "cand-pmid",
                "state": "texto limpio sin ngramas del banco porque son pocos",
                "meta": {"pmid": "99999999"},
            }
            # limpio
            clean = {
                "id": "cand-clean",
                "state": (
                    "kappa lambda mu nu xi omicron pi rho sigma tau "
                    "upsilon phi chi"
                ),
                "meta": {"pmid": "11111111"},
            }
            # duplicado exacto (normalizado) del limpio
            dup = {
                "id": "cand-dup",
                "state": (
                    "Kappa Lambda MU nu xi omicron pi rho sigma tau "
                    "upsilon phi chi!!!"
                ),
                "meta": {},
            }

            kept, _srcs, stats = cont.filter_candidates(
                [dirty_ngram, dirty_pmid, clean, dup],
                gram_to_case,
                bank_pmids,
            )
            self.assertEqual([r["id"] for r in kept], ["cand-clean"])
            self.assertEqual(stats["discarded_ngram"], 1)
            self.assertEqual(stats["discarded_pmid"], 1)
            self.assertEqual(stats["discarded_duplicate"], 1)
            self.assertEqual(stats["ngram_hits"][0]["candidate_id"], "cand-ngram")
            self.assertEqual(stats["ngram_hits"][0]["bank_case_id"], "FAKE_BANK_01")

    def test_cli_escribe_limpio_e_informe(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data_dir = self._bank_dir(tmp)
            out_dir = tmp / "limpio"
            inp = tmp / "cands.jsonl"
            rows = [
                {
                    "id": "ok-1",
                    "state": "aaa bbb ccc ddd eee fff ggg hhh iii jjj kkk",
                    "meta": {},
                },
                {
                    "id": "bad-pmid",
                    "state": "zzz yyy xxx www vvv uuu ttt sss rrr qqq ppp",
                    "meta": {"pmid": "99999999"},
                },
            ]
            inp.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                encoding="utf-8",
            )
            report = cont.run(
                [inp], out_dir, data_dir, require_phases=False
            )
            clean_path = out_dir / "cands.jsonl"
            self.assertTrue(clean_path.exists())
            cleaned = [json.loads(l) for l in clean_path.read_text().splitlines() if l]
            self.assertEqual([r["id"] for r in cleaned], ["ok-1"])
            informe = json.loads((out_dir / "contaminacion_informe.json").read_text())
            self.assertEqual(informe["files"]["cands.jsonl"]["discarded_pmid"], 1)
            self.assertEqual(informe["files"]["cands.jsonl"]["n_out"], 1)
            self.assertIn("informe", report)
            self.assertIn("coverage", informe)
            self.assertNotIn("common_ngrams_ignored", informe)
            self.assertNotIn("common_frac", informe)

    def test_papers_solo_title_abstract(self):
        """Solape solo en Journal/Publication types no contamina; Title+Abstract sí."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data = tmp / "data"
            data.mkdir()
            (data / "papers_fake.json").write_text(
                json.dumps([{
                    "pid": "PX",
                    "pmid": "88888888",
                    "title": "Unique Bank Title About Zebras And Quokkas Only",
                    "journal": "Shared Journal Of Template Phrases",
                    "pubtypes": [
                        "Journal Article",
                        "Research Support, Non-U.S. Gov't",
                    ],
                    "abstract": (
                        "bankabs0 bankabs1 bankabs2 bankabs3 bankabs4 "
                        "bankabs5 bankabs6 bankabs7 bankabs8"
                    ),
                }]),
                encoding="utf-8",
            )
            gram_to_case, _, _ = cont.load_bank(data, require_phases=False)

            # Solo comparte Journal + Publication types con el banco → limpio
            only_meta = {
                "id": "cand-meta-only",
                "task": "papers",
                "state": (
                    "Title: Totally Different Candidate Title Without Overlap\n"
                    "Journal: Shared Journal Of Template Phrases\n"
                    "Publication types: Journal Article, Research Support, "
                    "Non-U.S. Gov't\n\n"
                    "Abstract: cand0 cand1 cand2 cand3 cand4 cand5 cand6 "
                    "cand7 cand8 cand9"
                ),
                "meta": {"pmid": "111"},
            }
            # Comparte 8-grama del abstract del banco → contaminado
            dirty_abs = {
                "id": "cand-abs-hit",
                "task": "papers",
                "state": (
                    "Title: Another Distinct Title Here For Safety\n"
                    "Journal: Other Journal\n"
                    "Publication types: Journal Article\n\n"
                    "Abstract: prefix bankabs0 bankabs1 bankabs2 bankabs3 "
                    "bankabs4 bankabs5 bankabs6 bankabs7 suffix"
                ),
                "meta": {"pmid": "222"},
            }
            kept, _, stats = cont.filter_candidates(
                [only_meta, dirty_abs], gram_to_case, set()
            )
            self.assertEqual([r["id"] for r in kept], ["cand-meta-only"])
            self.assertEqual(stats["discarded_ngram"], 1)
            self.assertEqual(stats["ngram_hits"][0]["candidate_id"], "cand-abs-hit")

    def test_control_positivo_codex_sin_exencion_frecuencia(self):
        """Frase contaminada se descarta siempre: 1/1 y 31/6000 (regresión P1-1)."""
        secret = (
            "secretphrase alpha bravo charlie delta echo foxtrot "
            "golf hotel india"
        )
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data = tmp / "data"
            data.mkdir()
            (data / "adv_fake.json").write_text(
                json.dumps({
                    "FAKE_BANK_SECRET": {
                        "state": f"prefix {secret} suffix end marker here",
                        "department": "admin",
                        "urgency": 0,
                        "clinical": 0,
                        "hostile": 0,
                        "same_day": 0,
                    }
                }),
                encoding="utf-8",
            )

            # Caso A: 1 de 1 contaminado → 0 aceptados
            out_a = tmp / "limpio_a"
            inp_a = tmp / "single.jsonl"
            inp_a.write_text(
                json.dumps({
                    "id": "single-dirty",
                    "state": f"stolen {secret} and trailing tokens now",
                    "meta": {},
                }) + "\n",
                encoding="utf-8",
            )
            report_a = cont.run(
                [inp_a], out_a, data, require_phases=False
            )
            self.assertEqual(report_a["files"]["single.jsonl"]["n_out"], 0)
            self.assertEqual(
                report_a["files"]["single.jsonl"]["discarded_ngram"], 1
            )

            # Caso B: 31 contaminados + 5969 limpios = 6000
            out_b = tmp / "limpio_b"
            inp_b = tmp / "batch.jsonl"
            rows = []
            for i in range(31):
                rows.append({
                    "id": f"dirty-{i}",
                    "state": (
                        f"stolen {secret} variant suffix number {i} "
                        f"extra tokens pad"
                    ),
                    "meta": {},
                })
            for i in range(5969):
                rows.append({
                    "id": f"clean-{i}",
                    "state": (
                        f"clean body number {i} kappa lambda mu nu xi "
                        f"omicron pi rho sigma"
                    ),
                    "meta": {},
                })
            inp_b.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n",
                encoding="utf-8",
            )
            report_b = cont.run(
                [inp_b], out_b, data, require_phases=False
            )
            st = report_b["files"]["batch.jsonl"]
            self.assertEqual(st["n_in"], 6000)
            self.assertEqual(st["discarded_ngram"], 31)
            self.assertEqual(st["n_out"], 5969)
            cleaned = [
                json.loads(l)
                for l in (out_b / "batch.jsonl").read_text().splitlines()
                if l
            ]
            self.assertTrue(all(r["id"].startswith("clean-") for r in cleaned))
            self.assertNotIn("common_ngrams_ignored", report_b)

    def test_ood_indexado_con_banco_inventado(self):
        """OOD simulado entra en el índice y contamina candidatos (P1-2)."""
        ood_sim = {
            "receta_sim": (
                "preheat oven to two hundred season the chicken thighs "
                "with smoked paprika garlic and salt roast"
            ),
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data = tmp / "data"
            data.mkdir()
            (data / "adv_fake.json").write_text(
                json.dumps({
                    "OTHER": {
                        "state": (
                            "unrelated zeta eta theta iota kappa lambda "
                            "mu nu xi bankonly"
                        ),
                        "department": "admin",
                        "urgency": 0,
                        "clinical": 0,
                        "hostile": 0,
                        "same_day": 0,
                    }
                }),
                encoding="utf-8",
            )
            gram_to_case, _, coverage = cont.load_bank(
                data, ood_cases=ood_sim, require_phases=False
            )
            self.assertEqual(coverage["by_phase"]["ood"], 1)
            self.assertEqual(coverage["by_file"]["battery.OOD_CASES"], 1)
            self.assertEqual(coverage["ood_cases"], ["receta_sim"])
            self.assertIn(
                ("preheat", "oven", "to", "two", "hundred", "season",
                 "the", "chicken"),
                gram_to_case,
            )
            self.assertEqual(
                gram_to_case[
                    ("preheat", "oven", "to", "two", "hundred", "season",
                     "the", "chicken")
                ],
                "ood:receta_sim",
            )

            dirty = {
                "id": "cand-ood",
                "state": (
                    "please note preheat oven to two hundred season the "
                    "chicken thighs with smoked paprika garlic"
                ),
                "meta": {},
            }
            clean = {
                "id": "cand-ok",
                "state": (
                    "totally different wording here about appointments "
                    "and billing questions only"
                ),
                "meta": {},
            }
            kept, _, stats = cont.filter_candidates(
                [dirty, clean], gram_to_case, set()
            )
            self.assertEqual([r["id"] for r in kept], ["cand-ok"])
            self.assertEqual(stats["discarded_ngram"], 1)
            self.assertEqual(
                stats["ngram_hits"][0]["bank_case_id"], "ood:receta_sim"
            )

    def test_json_roto_aborta(self):
        """JSON ilegible en data/ → BankError / exit ≠ 0 (P2-5)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data = tmp / "data"
            data.mkdir()
            (data / "ok.json").write_text(
                json.dumps({
                    "OK": {
                        "state": (
                            "alpha bravo charlie delta echo foxtrot golf "
                            "hotel india"
                        ),
                    }
                }),
                encoding="utf-8",
            )
            (data / "roto.json").write_text("{esto no es json", encoding="utf-8")
            with self.assertRaises(cont.BankError) as ctx:
                cont.load_bank(data, require_phases=False)
            self.assertIn("roto.json", str(ctx.exception))

            out_dir = tmp / "limpio"
            inp = tmp / "cands.jsonl"
            inp.write_text(
                json.dumps({
                    "id": "x",
                    "state": "aaa bbb ccc ddd eee fff ggg hhh iii",
                    "meta": {},
                }) + "\n",
                encoding="utf-8",
            )
            rc = cont.main([
                str(inp), "--out-dir", str(out_dir), "--data-dir", str(data),
            ])
            self.assertNotEqual(rc, 0)

    def test_indice_vacio_aborta(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "data"
            data.mkdir()
            (data / "vacio.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(cont.BankError) as ctx:
                cont.load_bank(data, ood_cases={}, require_phases=False)
            self.assertIn("vacío", str(ctx.exception).lower())

    def test_dedup_global_entre_ficheros(self):
        """Mismo texto en dos JSONL: el segundo se descarta e informa origen."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            data_dir = self._bank_dir(tmp)
            out_dir = tmp / "limpio"
            shared = (
                "unique shared body kappa lambda mu nu xi omicron pi rho "
                "sigma tau"
            )
            a = tmp / "fuente_a.jsonl"
            b = tmp / "fuente_b.jsonl"
            a.write_text(
                json.dumps({"id": "from-a", "state": shared, "meta": {}}) + "\n",
                encoding="utf-8",
            )
            b.write_text(
                json.dumps({
                    "id": "from-b",
                    "state": shared.upper() + "!!!",
                    "meta": {},
                }) + "\n",
                encoding="utf-8",
            )
            report = cont.run(
                [a, b], out_dir, data_dir, require_phases=False
            )
            self.assertEqual(report["files"]["fuente_a.jsonl"]["n_out"], 1)
            self.assertEqual(report["files"]["fuente_b.jsonl"]["n_out"], 0)
            self.assertEqual(
                report["files"]["fuente_b.jsonl"]["discarded_duplicate"], 1
            )
            dups = report["duplicates"]
            self.assertEqual(len(dups), 1)
            self.assertEqual(dups[0]["candidate_id"], "from-b")
            self.assertEqual(dups[0]["source_file"], "fuente_b.jsonl")
            self.assertEqual(dups[0]["first_id"], "from-a")
            self.assertEqual(dups[0]["first_file"], "fuente_a.jsonl")


if __name__ == "__main__":
    unittest.main()
