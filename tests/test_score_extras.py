"""JEV-71 §3–4: IC bootstrap del ajustado agregado (`adjusted_ci`) y la
sensibilidad `--null-as-error` (vectores crudos nulos cuentan como error)."""
import json
import tempfile
import unittest
from pathlib import Path

from jevbench import score, store
from jevbench.battery import load_phase


def _raw_archived(run, phase="adv2"):
    """El espejo público sustituye `raw` por `raw_sha256`: sin raw, --null-as-error
    no puede interpretar nada y estos tests no aplican."""
    f = store.path(run, phase)
    return f.exists() and any("raw" in c for c in json.loads(f.read_text())["cases"].values())


def _attempt(answers):
    """Intento llm mínimo: la respuesta del proveedor como JSON de answers."""
    return {"llm_response": {"choices": [{"message": {"content": json.dumps(
        {"answers": answers})}, "finish_reason": "stop"}]}}


def _rec(qs, null_qids=(), raw=True):
    """Record sintético: answers ya normalizadas a uniforme (lo que haría el
    adaptador) y raw con el vector crudo."""
    answers, raw_answers = {}, {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            opts = list(q["criteria"])
            answers[qid] = {"choice": opts[0],
                            "probabilities": {o: 1 / len(opts) for o in opts}}
            raw_answers[qid] = ({o: 0.0 for o in opts} if qid in null_qids
                                else {o: (0.9 if o == opts[0] else 0.1 / (len(opts) - 1))
                                      for o in opts})
        elif q["type"] == "score":
            n = len(q["criteria"])
            answers[qid] = {"score": 0.0, "probabilities": {str(i): 1 / n for i in range(n)}}
            raw_answers[qid] = ({str(i): 0.0 for i in range(n)} if qid in null_qids
                                else {str(i): (0.9 if i == 0 else 0.1 / (n - 1)) for i in range(n)})
        else:
            answers[qid] = {"noul": 0.5}
            raw_answers[qid] = True
    rec = {"answers": answers, "ms": 10}
    if raw:
        rec["raw"] = [_attempt(raw_answers)]
    return rec


class NullAsError(unittest.TestCase):
    """Sensibilidad: choice/score con vector crudo nulo → error, no uniforme."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="score_null_"))
        self.qs, self.cases = load_phase("adv1")  # set pequeño (10 casos)
        self.choice_qid = next(q for q, qq in self.qs.items() if qq["type"] == "choice")
        self.score_qid = next(q for q, qq in self.qs.items() if qq["type"] == "score")

    def _write(self, cases_map, name="syn"):
        run = self.tmp / name
        run.mkdir(parents=True)
        doc = {"meta": {"adapter": "llm"}, "cases": cases_map}
        (run / "adv1.json").write_text(json.dumps(doc))
        return str(run)

    def test_nulo_choice_cuenta_como_error(self):
        cases = {self.cases[0].id: _rec(self.qs, null_qids={self.choice_qid}),
                 self.cases[1].id: _rec(self.qs)}
        run = self._write(cases)
        normal = score.score_run(run, "adv1")
        self.assertEqual(normal["n_ok"], 2)
        self.assertEqual(normal["null_as_error"], 0)
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["n_ok"], 1)
        self.assertEqual(strict["null_as_error"], 1)
        self.assertIn(self.cases[0].id, strict["errors"])

    def test_nulo_score_tambien(self):
        cases = {self.cases[0].id: _rec(self.qs, null_qids={self.score_qid})}
        run = self._write(cases)
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 1)

    def test_sin_raw_no_cambia(self):
        cases = {self.cases[0].id: _rec(self.qs, raw=False)}
        run = self._write(cases)
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["n_ok"], 1)
        self.assertEqual(strict["null_as_error"], 0)
        # raw ausente ≠ «sin nulos»: cuenta como desconocido
        self.assertEqual(strict["null_unknown"], 1)

    def test_content_none_no_rompe(self):
        """Un intento con content=None seguido de uno válido no rompe la
        sensibilidad: el último intento parseado manda (C9/R14)."""
        rec = _rec(self.qs)
        none_att = {"llm_response": {"choices": [{"message": {"content": None}}]}}
        rec["raw"] = [none_att, rec["raw"][0]]
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["n_ok"], 1)
        self.assertEqual(strict["null_as_error"], 0)
        self.assertEqual(strict["null_unknown"], 0)

    def test_cercas_sin_salto(self):
        """Cercas ``` sin etiqueta y sin salto de línea se aceptan igual que el
        _extract_json del adaptador (C9/R14)."""
        nulo = {self.choice_qid: {o: 0.0 for o in self.qs[self.choice_qid]["criteria"]}}
        for i, fence in enumerate(("```json %s```", "```%s```", "```json\n%s\n```")):
            rec = _rec(self.qs)
            payload = json.dumps({"answers": nulo})
            rec["raw"] = [{"llm_response": {"choices": [{"message": {"content": fence % payload}}]}}]
            run = self._write({self.cases[0].id: rec}, name=f"syn_fence{i}")
            strict = score.score_run(run, "adv1", null_as_error=True)
            self.assertEqual(strict["null_as_error"], 1, fence)

    def test_reintento_valido_a_nulo_cuenta(self):
        """Si el último intento parseado es nulo aunque uno anterior era
        válido, el caso sí cuenta como nulo."""
        rec = _rec(self.qs)
        null_att = _attempt({self.choice_qid: {o: 0.0 for o in self.qs[self.choice_qid]["criteria"]}})
        rec["raw"] = [rec["raw"][0], null_att]
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 1)

    def test_diag_raw_respaldo(self):
        """El fallback rec.diag.raw se usa igual que rec.raw."""
        rec = _rec(self.qs, null_qids={self.choice_qid})
        rec["diag"] = {"raw": rec.pop("raw")}
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 1)

    def test_raw_no_interpretable_es_desconocido(self):
        """Intentos que no son formato OpenAI chat cuentan como desconocido,
        no como ausencia de nulos."""
        rec = _rec(self.qs)
        rec["raw"] = [{"llm_response": {"choices": [{"message": {"content": "no json"}}]}},
                      {"unexpected": "shape"}]
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 0)
        self.assertEqual(strict["null_unknown"], 1)

    def test_null_vector_qids_none_en_desconocido(self):
        """La función distingue explícitamente «desconocido» (None) de
        «sin nulos» (set vacío)."""
        self.assertIsNone(score.null_vector_qids({"answers": {}}, self.qs))
        self.assertEqual(score.null_vector_qids(_rec(self.qs), self.qs), set())

    def test_vector_parcial_no_es_nulo(self):
        """Un dict que no cubre las opciones esperadas (p. ej. solo
        {bronchoscopia: 0}) es `invalid`, no `zero` — equivalencia con
        diag65._validate_raw_value."""
        q = self.qs[self.choice_qid]
        first = next(iter(q["criteria"]))
        rec = _rec(self.qs)
        rec["raw"] = [_attempt({self.choice_qid: {first: 0.0}})]
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 0)
        self.assertEqual(strict["null_unknown"], 0)

    def test_no_nulo_no_cambia(self):
        cases = {self.cases[0].id: _rec(self.qs)}
        run = self._write(cases)
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["n_ok"], 1)
        self.assertEqual(strict["null_as_error"], 0)

    def test_intento_anterior_nulo_no_cuenta(self):
        """Un nulo en un intento anterior que fue reintentado no convierte a error:
        solo manda el último intento con respuesta parseada."""
        rec = _rec(self.qs)
        ok_answers = json.loads(rec["raw"][0]["llm_response"]["choices"][0]
                                ["message"]["content"])["answers"]
        bad = {k: ({o: 0.0 for o in v} if isinstance(v, dict) else v)
               for k, v in ok_answers.items()}
        rec["raw"] = [_attempt(bad), rec["raw"][0]]
        run = self._write({self.cases[0].id: rec})
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertEqual(strict["null_as_error"], 0)

    def test_run_real_con_nulos(self):
        """El diag JEV-66 estructurado sin inyección tenía vectores nulos:
        el marcador oficial los puntúa; con el flag pasan a error."""
        run = "diag_qwen38_jev66_fp8_typesafe_struct_r1"
        if not store.runs_in(run):
            self.skipTest(f"{run} no está en results/")
        normal = score.score_run(run, "adv1")
        strict = score.score_run(run, "adv1", null_as_error=True)
        self.assertGreaterEqual(normal["n_ok"], strict["n_ok"])
        self.assertEqual(strict["n_ok"] + strict["null_as_error"], normal["n_ok"])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)


class AdjustedCI(unittest.TestCase):
    """IC bootstrap estratificado del ajustado agregado (JEV-71 §4)."""

    def test_reproducible_centro_y_cobertura(self):
        v1 = score.adjusted_ci("jev_v3")
        v2 = score.adjusted_ci("jev_v3")
        self.assertEqual(v1, v2)  # semilla fija → idéntico
        adj, _ = score.adjusted("jev_v3")
        self.assertAlmostEqual(v1[0], adj, places=9)
        self.assertLessEqual(v1[1], v1[0])
        self.assertLessEqual(v1[0], v1[2])
        self.assertLess(v1[1], v1[2])  # IC no degenerado

    def test_otra_semilla_cambia_replicas_no_centro(self):
        a = score.adjusted_ci("jev_v3", seed=0)
        b = score.adjusted_ci("jev_v3", seed=1)
        self.assertEqual(a[0], b[0])
        self.assertNotEqual((a[1], a[2]), (b[1], b[2]))

    def test_sin_fases_devuelve_none(self):
        self.assertEqual(score.adjusted_ci("run_que_no_existe"), (None, None, None))

    def test_summary_adj_ci_columna_opcional(self):
        plain = score.summary(["jev_v3"])
        self.assertNotIn("IC95 ajust", plain)
        con = score.summary(["jev_v3"], adj_ci=True)
        self.assertIn("IC95 ajust", con)
        adj, _ = score.adjusted("jev_v3")
        self.assertIn(f"{adj:.0f} |", con)

    def test_summary_null_as_error_pie(self):
        txt = score.summary(["jev_v3"], null_as_error=True)
        self.assertIn("--null-as-error", txt)

    def test_ic_misma_politica_null_as_error(self):
        """C9/R14 §1: el IC usa la misma política (y las mismas fases) que el
        ajustado mostrado — run real con un nulo que cambia la cobertura."""
        run = "llm_qwen38_27b_fp8_inject_prob"
        if not store.runs_in(run):
            self.skipTest(f"{run} no está en results/")
        if not _raw_archived(run):
            self.skipTest("raw no archivado (export público)")
        adj0, n0 = score.adjusted(run)
        adj1, n1 = score.adjusted(run, null_as_error=True)
        self.assertEqual(n0, len(score.ADJ_PHASES))
        self.assertLess(n1, n0)  # el nulo de adv2/B07 saca la fase del agregado
        v, lo, hi = score.adjusted_ci(run, null_as_error=True)
        self.assertAlmostEqual(v, adj1, places=9)
        self.assertNotAlmostEqual(v, adj0, places=3)
        self.assertLessEqual(lo, v)
        self.assertLessEqual(v, hi)
        # y en --summary el IC impreso corresponde al ajustado impreso
        txt = score.summary([run], adj_ci=True, null_as_error=True)
        self.assertIn(f"{adj1:.0f}*", txt)
        self.assertIn(f"{lo:.0f}–{hi:.0f}", txt)

    def test_summary_lista_fases_fuera_y_avisa(self):
        """C9/R14 §3: la salida lista las fases que salen del agregado y
        advierte de que coberturas distintas no son comparables."""
        run = "llm_qwen38_27b_fp8_inject_prob"
        if not store.runs_in(run):
            self.skipTest(f"{run} no está en results/")
        if not _raw_archived(run):
            self.skipTest("raw no archivado (export público)")
        txt = score.summary([run], null_as_error=True)
        self.assertIn("adv2", txt)
        self.assertIn("cobertura", txt)
        self.assertIn("no son", txt)

    def test_ponderacion_por_fase_no_por_caso(self):
        """C9/R14 §4: cada fase pesa lo mismo con independencia de su nº de
        casos — adv1 (10) perfecta + adv3 (20) respondiendo la mayoría dan
        margen medio (1 + 0) / 2 = 50, no un promedio ponderado por casos."""
        import shutil
        from collections import Counter
        tmp = Path(tempfile.mkdtemp(prefix="score_w_"))
        self.addCleanup(shutil.rmtree, tmp)

        def wire(q, val):
            if q["type"] == "choice":
                return {"choice": val}
            if q["type"] == "score":
                return {"score": float(val)}
            return {"noul": float(val)}

        def doc_for(phase, val_of):
            qs, cases = load_phase(phase)
            return {"meta": {}, "cases": {
                c.id: {"answers": {qid: wire(q, val_of(qid, q, c))
                                   for qid, q in qs.items()}, "ms": 1}
                    for c in cases}}

        qs1, cases1 = load_phase("adv1")
        qs3, cases3 = load_phase("adv3")
        self.assertNotEqual(len(cases1), len(cases3))
        (tmp / "adv1.json").write_text(json.dumps(
            doc_for("adv1", lambda qid, q, c: c.gt[qid])))
        maj = {qid: Counter(c.gt[qid] for c in cases3).most_common(1)[0][0]
               for qid in qs3}
        (tmp / "adv3.json").write_text(json.dumps(
            doc_for("adv3", lambda qid, q, c: maj[qid])))
        adj, n = score.adjusted(str(tmp))
        self.assertEqual(n, 2)
        self.assertAlmostEqual(adj, 50.0, places=9)
        v, lo, hi = score.adjusted_ci(str(tmp), iters=100)
        self.assertAlmostEqual(v, 50.0, places=9)


if __name__ == "__main__":
    unittest.main()
