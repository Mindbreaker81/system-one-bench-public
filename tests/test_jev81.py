"""Tests offline de jevbench.jev81 (JEV-81: fallback por rechazo,
rechazo como alerta, repetibilidad) — datos sintéticos, sin API."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import score, store
from jevbench import jev81
from jevbench.battery import load_phase, questions_hash


class TmpStore(unittest.TestCase):
    """store.ROOT temporal por test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="j81_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)


def _answers(qs, correct):
    """Respuestas válidas sintéticas: `correct` dict {qid: valor GT} —
    choice=etiqueta, score=float del nivel, noul=float."""
    out = {}
    for qid, q in qs.items():
        v = correct.get(qid)
        if q["type"] == "choice":
            v = v if v is not None else list(q["criteria"])[0]
            out[qid] = {"type": "choice", "choice": v,
                        "probabilities": {o: (0.9 if o == v else 0.0)
                                          for o in q["criteria"]}}
        elif q["type"] == "score":
            v = float(v) if v is not None else 0.0
            out[qid] = {"type": "score", "score": v,
                        "legend": q.get("criteria") or {},
                        "probabilities": {str(i): 0.5
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"type": "noul", "noul": 0.8 if v else 0.2}
    return out


def _cid(phase, prefix):
    """Id real del caso cuyo nombre empieza por `prefix` (T01->T01_…)."""
    _, cases = load_phase(phase)
    return next(c.id for c in cases if c.id.startswith(prefix))


def _write_run(run, phase, reject_ids=(), correct=True, cost=0.001,
               err="HTTP Error 502: refused to answer question"):
    """Doc sintético de `run`/`phase`: respuestas GT (correct) salvo los
    ids en reject_ids (prefijos aceptados), que quedan con `error`."""
    qs, cases = load_phase(phase)
    reject_ids = {_cid(phase, r) for r in reject_ids}
    doc = {"meta": {"adapter": "jev", "phase": phase,
                    "questions_hash": questions_hash(qs)},
           "cases": {}}
    for c in cases:
        if c.id in reject_ids:
            doc["cases"][c.id] = {"error": err, "ms": 7000}
        else:
            gt = {q: c.gt[q] for q in qs} if correct else {
                q: (list(qs[q]["criteria"])[-1]
                    if qs[q]["type"] == "choice"
                    else (len(qs[q]["criteria"]) - 1)
                    if qs[q]["type"] == "score"
                    else 0) for q in qs}
            doc["cases"][c.id] = {"answers": _answers(qs, gt),
                                  "ms": 100, "cost": cost,
                                  "model": "m-1"}
    store.save(run, phase, doc)
    return doc


def _write_all(run, reject_ids=None, **kw):
    """Escribe el run en TODAS las fases del agregado."""
    for ph in score.ADJ_PHASES:
        _write_run(run, ph, reject_ids=(reject_ids or {}).get(ph, ()),
                   **kw)


class TestFallback(TmpStore):
    def test_fusiona_rechazos_con_jev(self):
        """La regla fijada sustituye solo los casos con error por la
        respuesta de jev_v3 y marca la procedencia por caso."""
        _write_all(jev81.LUNA, reject_ids={"triage_es": {"T01", "T05"}})
        _write_all(jev81.JEV)
        docs, per = jev81.merged_docs()
        doc = docs["triage_es"]
        t01, t05, t02 = (_cid("triage_es", p) for p in ("T01", "T05", "T02"))
        self.assertEqual(len(doc["cases"]), 14)
        self.assertEqual(per["triage_es"]["n_fallback"], 2)
        self.assertEqual(doc["cases"][t01]["fallback_from"], jev81.JEV)
        self.assertEqual(doc["cases"][t05]["fallback_from"], jev81.JEV)
        self.assertNotIn("fallback_from", doc["cases"][t02])
        self.assertNotIn("error", doc["cases"][t01])
        self.assertEqual(doc["meta"]["sources"]["fallback"], jev81.JEV)
        # desglose por tipo de error en la meta del fusionado
        self.assertEqual(doc["meta"]["error_kinds"], {"rejection": 2})

    def test_rechazo_sin_respaldo_conserva_error(self):
        """Si jev_v3 tampoco tiene el caso, el error se conserva."""
        _write_all(jev81.LUNA, reject_ids={"triage_es": {"T01"}})
        _write_all(jev81.JEV)
        d = store.load(jev81.JEV, "triage_es")
        del d["cases"][_cid("triage_es", "T01")]
        store.save(jev81.JEV, "triage_es", d)
        # sin el caso el respaldo ya no cubre el universo -> error
        with self.assertRaises(SystemExit):
            jev81.merged_docs()
        # en modo sin validación el error se conserva marcado
        docs, _ = jev81.merged_docs(validate=False)
        self.assertIn("error",
                      docs["triage_es"]["cases"][_cid("triage_es", "T01")])
        self.assertIsNone(docs["triage_es"]["cases"]
                          [_cid("triage_es", "T01")]["fallback_from"])

    def test_fallback_report_ajustado_y_coste(self):
        """Ajustado oficial, familia McNemar-Holm completa y coste
        registrado: primario íntegro + respaldo solo en sustituidos."""
        _write_all(jev81.LUNA, reject_ids={"triage_es": {"T01"}})
        _write_all(jev81.JEV)
        rep = jev81.fallback_report()
        self.assertIsNotNone(rep["adjusted"])
        n_cases = sum(len(load_phase(ph)[1]) for ph in score.ADJ_PHASES)
        # coste registrado: el primario íntegro (incluye el rechazo,
        # que tiene cost 0.001 escrito... aquí los errores no llevan
        # cost -> desconocido contabilizado) + respaldo en el sustituido
        self.assertAlmostEqual(rep["cost"]["fallback"], 0.001)
        self.assertEqual(rep["cost"]["unknown_primary"],
                         [f"triage_es/{_cid('triage_es', 'T01')}"])
        # familia McNemar completa por referencia (una por fase×pregunta)
        expected = sum(len(load_phase(ph)[0]) for ph in score.ADJ_PHASES)
        self.assertEqual(len(rep["mcnemar_vs_jev"]), expected)
        self.assertEqual(len(rep["mcnemar_vs_luna"]), expected)

    def test_coste_primario_incluye_rechazos_registrados(self):
        """R48 §5: el coste registrado del primario se suma en su fuente
        íntegra — un rechazo CON coste registrado no se pierde."""
        _write_all(jev81.LUNA, reject_ids={"triage_es": {"T01"}})
        _write_all(jev81.JEV)
        t01 = _cid("triage_es", "T01")
        d = store.load(jev81.LUNA, "triage_es")
        d["cases"][t01]["cost"] = 0.007   # coste observado del error
        store.save(jev81.LUNA, "triage_es", d)
        docs, _ = jev81.merged_docs()
        rep = jev81.fallback_report(docs=docs)
        n_ok = sum(len(load_phase(ph)[1]) for ph in score.ADJ_PHASES) - 1
        self.assertAlmostEqual(rep["cost"]["primary"],
                               n_ok * 0.001 + 0.007)
        self.assertAlmostEqual(rep["cost"]["total"],
                               n_ok * 0.001 + 0.007 + 0.001)
        self.assertEqual(rep["cost"]["unknown_primary"], [])

    def test_hashes_distintos_rechazados(self):
        """R48 §2: fuentes con questions_hash distintos no se fusionan."""
        _write_all(jev81.LUNA)
        _write_all(jev81.JEV)
        d = store.load(jev81.JEV, "triage_es")
        d["meta"]["questions_hash"] = "synthetic-b"
        store.save(jev81.JEV, "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.merged_docs()

    def test_fase_o_caso_ausente_es_error(self):
        """R48 §2: ausencias = error explícito, no «no evaluado»."""
        _write_all(jev81.LUNA)
        _write_all(jev81.JEV)
        d = store.load(jev81.LUNA, "triage_es")
        del d["cases"][_cid("triage_es", "T03")]
        store.save(jev81.LUNA, "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.merged_docs()

    def test_write_no_sobrescribe(self):
        """R48 §3: --write aborta si el destino existe, sin tocar nada."""
        _write_all(jev81.LUNA)
        _write_all(jev81.JEV)
        marker = {"meta": {"marker": "existing"}, "cases": {}}
        store.save(jev81.FB_RUN, "triage_es", marker)
        before = store.path(jev81.FB_RUN, "triage_es").read_bytes()
        with self.assertRaises(SystemExit):
            jev81.write_fallback(printer=lambda *a: None)
        self.assertEqual(store.path(jev81.FB_RUN, "triage_es")
                         .read_bytes(), before)
        self.assertEqual(store.runs_in(jev81.FB_RUN), ["triage_es"])

    def test_write_solo_con_flag(self):
        """`merged_docs` no escribe; `write_fallback` crea el run
        fusionado legible por el scorer."""
        _write_all(jev81.LUNA, reject_ids={"triage_es": {"T01"}})
        _write_all(jev81.JEV)
        self.assertIsNone(store.load(jev81.FB_RUN, "triage_es"))
        jev81.write_fallback(printer=lambda *a: None)
        doc = store.load(jev81.FB_RUN, "triage_es")
        self.assertEqual(doc["cases"][_cid("triage_es", "T01")]
                         ["fallback_from"], jev81.JEV)
        s = score.score_run(jev81.FB_RUN, "triage_es")
        self.assertEqual(s["n_ok"], 14)


class TestAlerta(TmpStore):
    def _alert_luna(self, reject_ids=None, err=None):
        for ph in jev81.ALERT_PHASES:
            _write_run(jev81.LUNA, ph,
                       reject_ids=(reject_ids or {}).get(ph, ()),
                       **({"err": err} if err else {}))

    def test_tp_fp_por_campo_manipulated(self):
        """Verdad = `manipulated==1` del GT (adv3/4/5): negativas del
        proveedor en manipulados cuentan TP; en honestos, FP."""
        self._alert_luna({"adv4": {"D05", "D12"}})
        rep = jev81.alert_report()
        self.assertEqual(rep["n"], 60)
        self.assertEqual(rep["tp"], 1)      # D05 está manipulado (GT)
        self.assertEqual(rep["fp"], 1)      # D12 honesto
        self.assertEqual(rep["fn"], 29)
        self.assertEqual(rep["tn"], 29)
        self.assertEqual(len(rep["precision_ci"]), 2)
        self.assertIn("gt_fingerprint", rep)

    def test_adv2_descriptivo_sin_conteo(self):
        """adv2 no lleva `manipulated` en el GT -> sus negativas se
        reportan descriptivamente, fuera de TP/FP/FN/TN."""
        self._alert_luna({"adv2": {"B05"}})
        rep = jev81.alert_report()
        self.assertEqual(rep["n"], 60)
        self.assertEqual(rep["adv2_rejected_descriptive"],
                         ["B05_trial_data_exfil"])
        self.assertEqual(rep["tp"], 0)

    def test_timeout_no_es_rechazo(self):
        """R48 §4: timeout/transporte/fallo local no son positivos de
        la alerta — se desglosan aparte; solo «refused» HTTP lo es."""
        self._alert_luna({"adv4": {"D05"}},
                         err="TimeoutError: client timeout")
        rep = jev81.alert_report()
        self.assertEqual(rep["tp"], 0)          # D05 manipulado, timeout
        self.assertEqual(rep["fn"], 30)
        self.assertEqual(rep["other_error_kinds"], {"timeout": 1})

    def test_fase_ausente_es_error_de_entrada(self):
        """R48 §2: fase que falta reduce el universo -> error explícito,
        no conteo reducido silencioso."""
        _write_run(jev81.LUNA, "adv4")
        with self.assertRaises(SystemExit):
            jev81.alert_report()

    def test_clasificador_negativa_estricto(self):
        """R48b §2: solo HTTP 502 + «refused to answer» es negativa del
        proveedor; «connection refused» -> transporte; fallo local con
        «refused» -> local."""
        rej = 'RuntimeError: HTTP Error 502: Bad Gateway '               '{"error":{"message":"OpenAI refused to answer question"}}'
        self.assertEqual(jev81.error_kind({"error": rej}), "rejection")
        self.assertEqual(jev81.error_kind(
            {"error": "ConnectionRefusedError: connection refused"}),
            "transport")
        self.assertEqual(jev81.error_kind(
            {"error": "RuntimeError: local parser refused payload"}),
            "local")
        self.assertEqual(jev81.error_kind(
            {"error": "HTTP Error 503: service unavailable"}),
            "transport")

    def test_gt_manipulated_ausente_es_error(self):
        """R48 §2: GT `manipulated` ausente no se interpreta como
        honesto — es error de entrada."""
        self._alert_luna()
        qs, cases = load_phase("adv4")
        from types import SimpleNamespace
        bad = [SimpleNamespace(id=c.id,
                               gt={k: v for k, v in c.gt.items()
                                   if k != "manipulated"})
               for c in cases]
        real = jev81.load_phase

        def fake(ph):
            return (qs, bad) if ph == "adv4" else real(ph)

        with mock.patch.object(jev81, "load_phase", fake):
            with self.assertRaises(SystemExit):
                jev81.alert_report()


class TestRepetibilidad(TmpStore):
    def test_replicas_identicas(self):
        for run in ("r1", "r2"):
            _write_all(run)
        rep = jev81.repeatability_report("r1", "r2")
        self.assertEqual(rep["agreement"]["k"], rep["agreement"]["n"])
        self.assertTrue(rep["agreement"]["meets"])
        self.assertEqual(rep["dp"]["mean"], 0.0)
        self.assertEqual(rep["rejections"]["both"], [])
        self.assertTrue(rep["adjusted"]["same_phases"])
        self.assertAlmostEqual(rep["adjusted"]["delta"], 0.0)

    def test_rechazos_repetidos_y_desglose(self):
        _write_all("r1")
        _write_all("r2", reject_ids={"triage_es": {"T01", "T02"}})
        rep = jev81.repeatability_report("r1", "r2")
        t01, t02 = _cid("triage_es", "T01"), _cid("triage_es", "T02")
        self.assertEqual(rep["rejections"]["only_b"],
                         [f"triage_es/{t01}", f"triage_es/{t02}"])
        self.assertEqual(rep["rejections"]["both"], [])
        # r2 sin triage_es completa -> conjuntos distintos -> Δ null
        self.assertFalse(rep["adjusted"]["same_phases"])
        self.assertIsNone(rep["adjusted"]["delta"])

    def test_delta_solo_mismas_fases_completas(self):
        """R48 §1: Δ ajustado existe solo si las fases completas son las
        mismas en ambas réplicas — conjuntos disjuntos -> null, con las
        listas explícitas."""
        _write_all("r1", reject_ids={"triage_en": {"T01"}})
        _write_all("r2", reject_ids={"triage_es": {"T01"}})
        rep = jev81.repeatability_report("r1", "r2")
        self.assertNotIn("triage_en", rep["adjusted"]["phases_a"])
        self.assertNotIn("triage_es", rep["adjusted"]["phases_b"])
        self.assertFalse(rep["adjusted"]["same_phases"])
        self.assertIsNone(rep["adjusted"]["delta"])

    def test_version_distinta_no_es_repetibilidad(self):
        """R48 §4: si cambia la versión servida se informa y deja de ser
        repetibilidad del mismo modelo."""
        _write_all("r1")
        _write_all("r2")
        d = store.load("r2", "triage_es")
        for r in d["cases"].values():
            r["model"] = "m-2"
        store.save("r2", "triage_es", d)
        rep = jev81.repeatability_report("r1", "r2")
        self.assertFalse(rep["versions"]["repeatable_model"])
        self.assertEqual(len(rep["versions"]["mismatch"]), 14)

    # ---------- R48b ----------

    def test_repeat_valida_fase_ausente(self):
        """R48b §1: fase que falta en r2 -> error de entrada antes de
        calcular, no acuerdo sobre subconjunto."""
        _write_all("r1")
        _write_all("r2")
        store.path("r2", "adv5").unlink()
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_repeat_valida_hash(self):
        """R48b §1: questions_hash distinto en r2 -> SystemExit."""
        _write_all("r1")
        _write_all("r2")
        d = store.load("r2", "triage_es")
        d["meta"]["questions_hash"] = "synthetic-b"
        store.save("r2", "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_repeat_componente_ausente_es_error(self):
        """R48b §1: una opción del vector pareado ausente -> error de
        entrada, no intersección silenciosa."""
        _write_all("r1")
        _write_all("r2")
        d = store.load("r2", "triage_es")
        rec = d["cases"][_cid("triage_es", "T01")]
        rec["answers"]["department"]["probabilities"].pop("admin")
        store.save("r2", "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_repeat_version_desconocida_no_acredita(self):
        """R48b §1: sin `model` en r2 la versión es desconocida — no se
        declara repeatable_model."""
        _write_all("r1")
        _write_all("r2")
        for ph in score.ADJ_PHASES:
            d = store.load("r2", ph)
            for r in d["cases"].values():
                r.pop("model", None)
            store.save("r2", ph, d)
        rep = jev81.repeatability_report("r1", "r2")
        self.assertFalse(rep["versions"]["repeatable_model"])
        self.assertEqual(len(rep["versions"]["mismatch"]), 0)
        self.assertTrue(rep["versions"]["unknown"])

    def test_p02_retirado_permitido_extra_desconocido_no(self):
        """R48b §3: P02 histórico de jev_v3 (retirado en GT v4) no
        bloquea ni se evalúa; un id ajeno inesperado sí aborta."""
        _write_all(jev81.LUNA)
        _write_all(jev81.JEV)
        d = store.load(jev81.JEV, "papers32")
        d["cases"]["P02"] = {"answers": _answers(
            load_phase("papers32")[0], {}), "ms": 1, "cost": 0.001}
        store.save(jev81.JEV, "papers32", d)
        docs, _ = jev81.merged_docs()
        self.assertNotIn("P02", docs["papers32"]["cases"])
        rep = jev81.fallback_report(docs=docs)
        self.assertEqual(rep["phases"]["papers32"]["n"], 31)
        # y un extra que no es el retirado documentado -> error
        d["cases"]["P99_fake"] = d["cases"]["P02"]
        store.save(jev81.JEV, "papers32", d)
        with self.assertRaises(SystemExit):
            jev81.merged_docs()

    # ---------- R48c ----------

    def test_componente_ausente_en_ambas_es_error(self):
        """R48c §1: opción ausente en AMBAS réplicas — la igualdad de
        vectores incompletos no acredita cobertura."""
        _write_all("r1")
        _write_all("r2")
        for run in ("r1", "r2"):
            d = store.load(run, "triage_es")
            rec = d["cases"][_cid("triage_es", "T01")]
            rec["answers"]["department"]["probabilities"].pop("admin")
            store.save(run, "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_vector_ausente_en_ambas_es_error(self):
        """R48c §1: vector `probabilities` ausente en ambas réplicas.""" 
        _write_all("r1")
        _write_all("r2")
        for run in ("r1", "r2"):
            d = store.load(run, "triage_es")
            rec = d["cases"][_cid("triage_es", "T01")]
            rec["answers"]["department"].pop("probabilities")
            store.save(run, "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_tipo_cambiado_es_error(self):
        """R48c §1: tipo de una respuesta cambiado (choice→score) en una
        réplica -> error de entrada."""
        _write_all("r1")
        _write_all("r2")
        d = store.load("r2", "triage_es")
        rec = d["cases"][_cid("triage_es", "T01")]
        rec["answers"]["department"]["type"] = "score"
        store.save("r2", "triage_es", d)
        with self.assertRaises(SystemExit):
            jev81.repeatability_report("r1", "r2")

    def test_p02_retirado_no_evaluado_en_repeat(self):
        """R48c §2: P02 con respuestas válidas en ambas réplicas NO se
        evalúa — agreement y Δp sobre el universo vigente."""
        _write_all("r1")
        _write_all("r2")
        base = jev81.repeatability_report("r1", "r2")
        for run in ("r1", "r2"):
            d = store.load(run, "papers32")
            d["cases"]["P02"] = {"answers": _answers(
                load_phase("papers32")[0], {}), "ms": 1,
                "model": "m-1"}
            store.save(run, "papers32", d)
        rep = jev81.repeatability_report("r1", "r2")
        self.assertEqual(rep["agreement"]["n"], base["agreement"]["n"])
        self.assertEqual(rep["dp"]["n"], base["dp"]["n"])
        # y procedencia completa en repeat
        self.assertIn("source_sha", rep["provenance"])
        self.assertIn("gt_scoring_sha", rep["provenance"])

    def test_desacuerdo_baja_acuerdo(self):
        _write_all("r1")
        _write_all("r2", correct=False)
        rep = jev81.repeatability_report("r1", "r2")
        self.assertLess(rep["agreement"]["p"], 1.0)
        self.assertGreater(rep["dp"]["max"], 0.0)


if __name__ == "__main__":
    unittest.main()
