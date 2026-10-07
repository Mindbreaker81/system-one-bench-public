"""JEV-70: reglas pre-registradas del preflight, canario e informe de DiffusionGemma."""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import dgemma_canary, dgemma_preflight, dgemma_report, score, store
from jevbench import metrics as M
from jevbench.battery import EXTRA_PHASES, PHASES, load_phase
from jevbench.rotation import rotate_choice, rotation_manifest
from jevbench.score import ADJ_PHASES, score_run


class Rules(unittest.TestCase):
    def test_maxlen_rule(self):
        self.assertEqual(dgemma_preflight.maxlen_rule(1000), 16384)
        self.assertEqual(dgemma_preflight.maxlen_rule(15360), 16384)
        self.assertEqual(dgemma_preflight.maxlen_rule(15361), 17408)

    def test_families_cover_194_cases(self):
        # GT v4 (JEV-73): families() carga la batería actual, no el run histórico.
        with mock.patch.dict('os.environ', {'JEVBENCH_GT': 'current'}):
            fams = dgemma_preflight.families()
        self.assertEqual(sum(len(f["cases"]) for f in fams.values()), 194)
        self.assertEqual(len(fams), 3)  # triaje/adv, papers32, ood

    def test_canary_table(self):
        c = dgemma_canary.classify
        self.assertEqual(c(5, 4), "sigue los criterios")
        self.assertEqual(c(5, 1), "sigue la posición o el nombre, no el criterio")
        self.assertEqual(c(0, 2), "no sigue los criterios")
        self.assertEqual(c(3, 5), "inconcluso")

    def test_band(self):
        b = dgemma_report.band
        self.assertEqual(b(30, lambda x: 22 <= x <= 48, lambda x: 15 <= x <= 55), "CONFIRMADA")
        self.assertEqual(b(50, lambda x: 22 <= x <= 48, lambda x: 15 <= x <= 55), "INCONCLUSA")
        self.assertEqual(b(60, lambda x: 22 <= x <= 48, lambda x: 15 <= x <= 55), "REFUTADA")
        self.assertEqual(b(None, lambda x: True, lambda x: True), "NO EVALUABLE")


def _rotate_vieja(questions, shift=1):
    """La implementación anterior (JEV-67), que mutaba `shift`: el residuo de la
    primera pregunta choice se aplicaba a todas las demás."""
    out = {}
    for qid, q in questions.items():
        q = dict(q)
        if q.get("type") == "choice":
            items = list(q["criteria"].items())
            shift %= len(items)
            q["criteria"] = dict(items[shift:] + items[:shift])
        out[qid] = q
    return out


class RotateChoiceOffset(unittest.TestCase):
    """R1 hallazgo 5: el residuo es local a cada pregunta; para shift=1 (lo único
    usado hasta ahora) el resultado no cambia."""

    def test_shift1_igual_que_la_version_anterior(self):
        # assertEqual sobre dicts ignora el orden de claves (R3 hallazgo 2):
        # comparamos la serialización sin sort_keys, el orden por pregunta y
        # los perm_sha256 del manifiesto en las 11 fases
        for ph in PHASES + EXTRA_PHASES + ["adv4", "adv5"]:
            qs, _ = load_phase(ph)
            nuevo, viejo = rotate_choice(qs, 1), _rotate_vieja(qs, 1)
            self.assertEqual(json.dumps(nuevo), json.dumps(viejo), ph)
            for qid in nuevo:
                if nuevo[qid].get("type") == "choice":
                    self.assertEqual(list(nuevo[qid]["criteria"]),
                                     list(viejo[qid]["criteria"]), f"{ph}/{qid}")
            self.assertEqual(rotation_manifest(nuevo), rotation_manifest(viejo), ph)
            self.assertEqual(rotation_manifest(nuevo)["perm_sha256"],
                             rotation_manifest(viejo)["perm_sha256"], ph)

    def test_residuo_por_pregunta(self):
        qs = {"a": {"type": "choice", "criteria": {"x": None, "y": None}},
              "b": {"type": "choice", "criteria": {"p": None, "q": None, "r": None}}}
        out = rotate_choice(qs, 3)
        self.assertEqual(list(out["a"]["criteria"]), ["y", "x"])      # 3 % 2 = 1
        self.assertEqual(list(out["b"]["criteria"]), ["p", "q", "r"])  # 3 % 3 = 0
        # la versión anterior rotaba b con el residuo de a (1): mismo dict,
        # distinto orden de claves
        self.assertEqual(out["b"]["criteria"], _rotate_vieja(qs, 3)["b"]["criteria"])
        self.assertNotEqual(list(out["b"]["criteria"]),
                            list(_rotate_vieja(qs, 3)["b"]["criteria"]))


class ReportFixes(unittest.TestCase):
    """R1 hallazgos 1–4 sobre datos sintéticos en un store.ROOT temporal:
    raw por adaptador, ajustado solo con cobertura completa, pares vacíos no
    evaluables y auditoría numérica que registra sin abortar."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dgemma_rep_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def _answers(self, phase, bad=None):
        qs, _ = load_phase(phase)
        out = {}
        for qid, q in qs.items():
            if q["type"] == "choice":
                k = next(iter(q["criteria"]))
                out[qid] = {"choice": k,
                            "probabilities": {kk: 1.0 if kk == k else 0.0 for kk in q["criteria"]}}
            elif q["type"] == "score":
                n = len(q["criteria"])
                out[qid] = {"score": 0.0,
                            "probabilities": {str(i): 1.0 if i == 0 else 0.0 for i in range(n)}}
            else:
                out[qid] = {"noul": 0.1}
        if bad:
            out.update(bad)
        return out

    def _write(self, run, phase, raw_style=None, answers=None, extra=None):
        qs, cases = load_phase(phase)
        recs = {}
        for c in cases:
            rec = {"answers": answers if answers is not None else self._answers(phase),
                   "ms": 100}
            if raw_style == "dict":   # systemone_http: {"request","response"}
                rec["raw"] = {"request": {"state": c.state, "questions": qs,
                                          **(extra or dgemma_report.FROZEN_EXTRA["P"])},
                              "response": {"diagnostics": {"samples": {"n": 1},
                                           "timing": {"total_ms": 50},
                                           "prompt_tokens": 100}}}
            elif raw_style == "list":  # adaptador llm: lista de intentos
                rec["raw"] = [{"request": {"model": "dgemma"},
                               "llm_response": {"choices": []}}]
            recs[c.id] = rec
        d = self.tmp / run
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{phase}.json").write_text(json.dumps({"meta": {"opts": {}}, "cases": recs}))

    def test_build_con_raw_lista_en_celda_llm(self):
        self._write("dgemma_26b_a4b_nvfp4", "ood", raw_style="dict")
        self._write("llm_dgemma_26b_a4b_nvfp4_nostruct_prob", "ood", raw_style="list")
        res = dgemma_report.build()  # no debe abortar con raw en lista
        lp = res["cells"]["Lp"]
        self.assertEqual(lp["audit"]["n_ok"], 3)
        self.assertEqual(lp["audit"]["no_raw"], 0)  # sin comprobación de extra en L
        self.assertEqual(lp["latency"]["median"], 100)  # latencia solo desde ms
        self.assertIn("L.c errores 1.ª pasada (Lp)", res["classification"])
        p = res["cells"]["P"]
        self.assertEqual(p["audit"]["extra_mismatch"], [])
        self.assertEqual(p["latency"]["server_median"], 50)  # diagnostics sí leídos

    def test_ajustado_parcial_no_se_publica(self):
        # una fase completa y diez ausentes → ajustado no evaluable (§8.1)
        self._write("dgemma_26b_a4b_nvfp4", "triage_es", raw_style="dict")
        res = dgemma_report.build()
        p = res["cells"]["P"]
        self.assertIsNone(p["adjusted"])
        self.assertIsNotNone(p["adjusted_partial"])  # diagnóstico rotulado aparte
        self.assertEqual(res["classification"]["P.a ajustado"], "NO EVALUABLE")
        buf = []
        dgemma_report.report(res, printer=buf.append)
        self.assertIn("no evaluable", " ".join(buf))

    def test_x_sin_ajustado_por_diseno(self):
        for ph in ("papers32", "adv3"):
            self._write("dgemma_26b_a4b_nvfp4_x80", ph)
        res = dgemma_report.build()
        self.assertIsNone(res["cells"]["X"]["adjusted"])
        self.assertIsNotNone(res["cells"]["X"]["adjusted_partial"])

    def test_max_abs_dp_sin_pares(self):
        # todos los casos en error → no hay probabilidades pareadas
        for run in ("rA", "rB"):
            d = self.tmp / run
            d.mkdir()
            (d / "ood.json").write_text(json.dumps(
                {"meta": {}, "cases": {"c1": {"error": "boom"}}}))
        self.assertEqual(dgemma_report.max_abs_dp("rA", "rB"), (None, 0, 0))
        # intersección de casos vacía → idem
        d = self.tmp / "rC"
        d.mkdir()
        (d / "ood.json").write_text(json.dumps({"meta": {}, "cases": {
            "otro": {"answers": {"clinical": {"noul": 0.2}}}}}))
        self.assertEqual(dgemma_report.max_abs_dp("rA", "rC"), (None, 0, 0))

    def test_numeric_audit_no_aborta(self):
        bad = {
            "relevance": {"score": float("nan"),  # score no finito
                          "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0}},
        }
        self._write("dgemma_26b_a4b_nvfp4", "ood", answers=self._answers("ood", bad))
        inc = dgemma_report.numeric_audit("dgemma_26b_a4b_nvfp4")
        self.assertTrue(any("score=nan no finito" in i for i in inc), inc)

        bad = {"relevance": {"score": 0.0,
                             "probabilities": {"baja": 1.0}}}  # etiqueta no numérica
        self._write("dgemma_26b_a4b_nvfp4", "ood", answers=self._answers("ood", bad))
        inc = dgemma_report.numeric_audit("dgemma_26b_a4b_nvfp4")
        self.assertTrue(any("niveles" in i for i in inc), inc)

        bad = {"relevance": {"score": 0.0,
                             "probabilities": {"0": "alta", "1": 0.0, "2": 0.0}}}
        self._write("dgemma_26b_a4b_nvfp4", "ood", answers=self._answers("ood", bad))
        inc = dgemma_report.numeric_audit("dgemma_26b_a4b_nvfp4")
        self.assertTrue(any("no numéricas" in i for i in inc), inc)
        # y el informe completo no aborta aunque el scorer falle con estos datos
        res = dgemma_report.build()
        self.assertIn("P", res["cells"])
        self.assertIsNone(res["cells"]["P"]["adjusted"])

    def test_s1b_y_recomendacion_exigen_ambos_ajustados(self):
        # R3 hallazgo 1: cobertura completa en ambos, pero score=NaN en P → su
        # ajustado queda None; S1.b es NO EVALUABLE y no hay recomendación
        bad = {"relevance": {"score": float("nan"),
                             "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0}}}
        for ph in ADJ_PHASES:
            ans = self._answers(ph, bad) if ph == "ood" else None
            self._write("dgemma_26b_a4b_nvfp4", ph, raw_style="dict", answers=ans)
            self._write("dgemma_26b_a4b_nvfp4_s1", ph, raw_style="dict",
                        extra=dgemma_report.FROZEN_EXTRA["S1"])
        res = dgemma_report.build()
        p, s1 = res["cells"]["P"], res["cells"]["S1"]
        self.assertTrue(p["audit"]["complete"])
        self.assertTrue(s1["audit"]["complete"])
        self.assertIsNone(p["adjusted"])           # el scorer no pudo con P
        self.assertIsNotNone(s1["adjusted"])       # S1 sí tiene ajustado
        self.assertEqual(res["classification"]["S1.b |Δ ajustado|"], "NO EVALUABLE")
        self.assertNotIn("recomendacion", res)
        buf = []
        dgemma_report.report(res, printer=buf.append)  # tampoco aborta al imprimir
        self.assertTrue(buf)

    def test_s1b_recomendacion_ajustados_no_finitos(self):
        # R5 hallazgo 3: NaN/inf del productor no son ajustados válidos para
        # S1.b ni para la recomendación, aunque la cobertura sea completa
        for ph in ADJ_PHASES:
            self._write("dgemma_26b_a4b_nvfp4", ph, raw_style="dict")
            self._write("dgemma_26b_a4b_nvfp4_s1", ph, raw_style="dict",
                        extra=dgemma_report.FROZEN_EXTRA["S1"])
        for mal in (float("nan"), float("inf")):
            def fake_adj(run, _mal=mal):
                return (_mal, 11) if run.endswith("_s1") else (30.0, 11)
            with mock.patch.object(dgemma_report, "adjusted", fake_adj):
                res = dgemma_report.build()
            self.assertEqual(res["classification"]["S1.b |Δ ajustado|"],
                             "NO EVALUABLE", mal)
            self.assertNotIn("recomendacion", res)
            self.assertIsNone(res["cells"]["S1"]["adjusted"])
            self.assertEqual(res["cells"]["P"]["adjusted"], 30.0)
            buf = []
            dgemma_report.report(res, printer=buf.append)
            self.assertTrue(buf)


@unittest.skipUnless(store.runs_in("jev_v3") and store.runs_in("decider_4b"), "faltan runs")
class McNemarMatchesScore(unittest.TestCase):
    def test_raw_p_equal_to_score_vs(self):
        out = io.StringIO()
        argv = ["jevbench.score", "decider_4b", "--vs", "jev_v3",
                "--phases", ",".join(ADJ_PHASES)]
        with contextlib.redirect_stdout(out):
            old, sys.argv = sys.argv, argv
            try:
                score.main()
            finally:
                sys.argv = old
        printed = re.findall(r"(\w+) b=(\d+) c=(\d+) p=([\d.]+)", out.getvalue())
        rows = dgemma_report.mcnemar_holm("decider_4b", phases=ADJ_PHASES)
        self.assertEqual(len(printed), len(rows))
        for (q, b, c, p), r in zip(printed, rows):
            self.assertEqual((q, int(b), int(c)), (r["q"], r["b"], r["c"]))
            self.assertEqual(p, f"{r['p']:.2f}")
            self.assertGreaterEqual(r["p_holm"], r["p"])
            # referencia independiente sin redondear: score_run + metrics.mcnemar
            x, y = score_run("jev_v3", r["phase"]), score_run("decider_4b", r["phase"])
            b2, c2, p2 = M.mcnemar(x["hits"][r["q"]], y["hits"][r["q"]])
            self.assertEqual((r["b"], r["c"]), (b2, c2))
            self.assertAlmostEqual(r["p"], p2, places=12)


if __name__ == "__main__":
    unittest.main()
