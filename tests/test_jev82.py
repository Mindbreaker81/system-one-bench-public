"""Tests offline de jevbench.jev82 (JEV-82: contraste de la rotación
department:d1 de gpt-6-luna-decisions) — runs sintéticos en un store.ROOT
temporal; sin API ni llamadas externas."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import jev82, score, store
from jevbench.battery import load_phase, questions_hash
from jevbench.rotation import order_manifest, reorder_choice, resolve_choice_order


class TmpStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="j82_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)


def _answers(qs, gt, bad):
    """Respuestas sintéticas completas (contrato de la batería); `bad`
    desplaza la choice a una etiqueta distinta del GT."""
    out = {}
    for qid, q in qs.items():
        v = gt.get(qid)
        if q["type"] == "choice":
            labels = list(q["criteria"])
            pick = (v if not bad else
                    next(l for l in labels if l != v))
            out[qid] = {"type": "choice", "choice": pick,
                        "probabilities": {o: (0.9 if o == pick else 0.0)
                                          for o in labels}}
        elif q["type"] == "score":
            out[qid] = {"type": "score", "score": float(v or 0),
                        "probabilities": {str(i): 0.5
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"type": "noul", "noul": float(bool(v))}
    return out


def _primacy_ids():
    """Ids de los casos del subconjunto de primacía congelado (por fase)."""
    from jevbench.qwen_session import primacy_subset
    out = {}
    for ph, cid in primacy_subset():
        out.setdefault(ph, set()).add(cid)
    return out


def _write_run(run, phase, spec="d0", reject_ids=(), wrong_ids=(),
               correct=True, cost=0.0001, model="m-1"):
    """Doc sintético de `run`/`phase` con la procedencia de orden que el
    adaptador jev declara en meta (opts.choice_order + meta.choice_order +
    perm_sha256 del orden aplicado)."""
    qs, cases = load_phase(phase)
    orders = resolve_choice_order(f"department:{spec}")
    perm = order_manifest(reorder_choice(qs, orders), orders)["perm_sha256"]
    meta = {"adapter": "jev", "phase": phase,
            "questions_hash": questions_hash(qs),
            "opts": {"provider": "openrouter", "model": "m",
                     "choice_order": f"department:{spec}"},
            "choice_order": orders, "perm_sha256": perm}
    if spec != "d0":
        meta["cost_guard"] = dict(jev82.COST_GUARD_SPEC)
    doc = {"meta": meta, "cases": {}}
    reject = {c.id for c in cases
              if any(c.id.startswith(r) for r in reject_ids)}
    wrong = {c.id for c in cases
             if any(c.id.startswith(w) for w in wrong_ids)}
    for c in cases:
        if c.id in reject:
            doc["cases"][c.id] = {
                "error": "HTTP Error 502: refused to answer question",
                "ms": 7000}
        else:
            doc["cases"][c.id] = {
                "answers": _answers(qs, c.gt, (not correct) or c.id in wrong),
                "ms": 100, "cost": cost, "model": model}
    store.save(run, phase, doc)
    return doc


def _write_all(run, spec="d0", reject_ids=None, **kw):
    for ph in score.ADJ_PHASES:
        _write_run(run, ph, spec=spec,
                   reject_ids=(reject_ids or {}).get(ph, ()), **kw)


class TestProvenance(TmpStore):
    def test_informe_ok_con_runs_bien_declarados(self):
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertEqual(rep["run_d0"], jev82.D0)
        self.assertEqual(rep["provenance"]["primacy_subset_sha"],
                         jev82.PRIMACY_SUBSET_SHA)

    def test_d1_sin_declarar_aborta(self):
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d0")   # meta dice d0 en el run d1
        with self.assertRaises(SystemExit):
            jev82.rotation_report(printer=lambda *a: None)

    def test_perm_sha256_falso_aborta(self):
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        doc = store.load(jev82.D1, "adv3")
        doc["meta"]["perm_sha256"] = "000000000000"
        store.save(jev82.D1, "adv3", doc)
        with self.assertRaises(SystemExit):
            jev82.rotation_report(printer=lambda *a: None)

    def test_d1_sin_guarda_de_coste_aborta(self):
        """El run d1 debe declarar en meta.cost_guard los topes congelados
        (la guarda de adquisición es parte del protocolo fijado)."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        doc = store.load(jev82.D1, "triage_es")
        del doc["meta"]["cost_guard"]
        store.save(jev82.D1, "triage_es", doc)
        with self.assertRaises(SystemExit):
            jev82.rotation_report(printer=lambda *a: None)

    def test_d0_historico_sin_opcion_admitido(self):
        """El run d0 histórico no declara la opción (meta.opts sin
        choice_order, meta.choice_order/perm_sha256 ausentes): válido."""
        _write_all(jev82.D1, spec="d1")
        for ph in score.ADJ_PHASES:
            qs, _ = load_phase(ph)
            doc = {"meta": {"adapter": "jev", "phase": ph,
                            "questions_hash": questions_hash(qs),
                            "opts": {"provider": "openrouter", "model": "m"}},
                   "cases": {}}
            _, cases = load_phase(ph)
            for c in cases:
                doc["cases"][c.id] = {"answers": _answers(qs, c.gt, False),
                                      "ms": 1, "cost": 0.0001, "model": "m-1"}
            store.save(jev82.D0, ph, doc)
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertTrue(rep["versions"]["same_model"])


class TestContrastes(TmpStore):
    def test_runs_identicos(self):
        """Réplicas idénticas: acuerdo 100 %, Δ ajustado 0, primacía
        refutada (U95 < 5 con errores 0-0)."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertEqual(rep["agreement"]["n"], rep["agreement"]["k"])
        self.assertAlmostEqual(rep["agreement"]["p"], 1.0)
        self.assertAlmostEqual(rep["adjusted"]["delta"]["delta"], 0.0)
        self.assertEqual(rep["primacy"]["errors"], {"d0": 0, "d1": 0})
        self.assertEqual(rep["primacy"]["verdict"], "REFUTADA")
        self.assertTrue(rep["adjusted"]["same_phases"])
        self.assertTrue(rep["versions"]["same_model"])

    def test_d1_mejor_en_primacia_confirma(self):
        """d0 falla el subconjunto y d1 acierta: Δpp grande positivo,
        Holm significativo -> CONFIRMADA (regla JEV-72)."""
        prim = _primacy_ids()
        _write_all(jev82.D0, spec="d0",
                   wrong_ids={cid for ids in prim.values() for cid in ids})
        _write_all(jev82.D1, spec="d1")
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertEqual(rep["primacy"]["verdict"], "CONFIRMADA")
        self.assertGreater(rep["primacy"]["delta_pp"], 5)
        self.assertLess(rep["primacy"]["p_holm_primacy"], 0.05)

    def test_acuerdo_y_dp_capturan_cambios(self):
        """Respuestas distintas en d1 bajan el acuerdo; Δp > 0 solo si
        las probabilities difieren."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1", wrong_ids={_cid("triage_es", "T01")})
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertLess(rep["agreement"]["p"], 1.0)
        self.assertEqual(rep["dp"]["n"] > 0, True)

    def test_fases_completas_distintas_interseccion(self):
        """Un rechazo extra en d1 saca su fase del pareado; el Δ usa la
        intersección y la diferencia se declara (same_phases=False)."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1",
                   reject_ids={"adv3": {_cid("adv3", "C01")}})
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertFalse(rep["adjusted"]["same_phases"])
        self.assertNotIn("adv3", rep["adjusted"]["delta"]["phases"])
        self.assertIn("adv3", rep["adjusted"]["phases_a"])
        self.assertIn(f"adv3/{_cid('adv3', 'C01')}",
                      rep["rejections"]["only_d1"])

    def test_rechazos_en_ambos(self):
        _write_all(jev82.D0, spec="d0", reject_ids={"adv5": {"E01"}})
        _write_all(jev82.D1, spec="d1",
                   reject_ids={"adv5": {"E01", "E02"}})
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertEqual(rep["rejections"]["both"],
                         [f"adv5/{_cid('adv5', 'E01')}"])
        self.assertEqual(rep["rejections"]["only_d1"],
                         [f"adv5/{_cid('adv5', 'E02')}"])
        self.assertEqual(rep["rejections"]["only_d0"], [])

    def test_version_distinta_no_es_mismo_modelo(self):
        _write_all(jev82.D0, spec="d0", model="m-1")
        _write_all(jev82.D1, spec="d1", model="m-2")
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertFalse(rep["versions"]["same_model"])
        self.assertTrue(rep["versions"]["mismatch"])

    def test_version_ausente_unilateral(self):
        """Un éxito de d1 sin `model` queda listado como desconocido y
        same_model pasa a falso (R56.1: antes se perdía al intersectar)."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        _strip_model(jev82.D1, phases=["adv2"])
        rep = jev82.rotation_report(printer=lambda *a: None)
        v = rep["versions"]
        self.assertFalse(v["same_model"])
        _, cases = load_phase("adv2")
        self.assertEqual(v["unknown"],
                         sorted(f"adv2/{c.id}" for c in cases))
        self.assertFalse(v["mismatch"])

    def test_version_ausente_bilateral(self):
        """Ausencia en ambos lados: el par es desconocido igualmente."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        cid = _cid("adv1", "A")
        _strip_model(jev82.D0, phases=["adv1"], only=cid[:4])
        _strip_model(jev82.D1, phases=["adv1"], only=cid[:4])
        rep = jev82.rotation_report(printer=lambda *a: None)
        self.assertIn(f"adv1/{cid}", rep["versions"]["unknown"])
        self.assertFalse(rep["versions"]["same_model"])

    def test_version_ausente_en_todos(self):
        """Sin un solo par conocido no hay base para same_model."""
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1")
        _strip_model(jev82.D0)
        _strip_model(jev82.D1)
        rep = jev82.rotation_report(printer=lambda *a: None)
        v = rep["versions"]
        self.assertEqual(v["known_pairs"], 0)
        self.assertEqual(len(v["unknown"]), v["paired_successes"])
        self.assertGreater(v["paired_successes"], 0)
        self.assertFalse(v["same_model"])

    def test_guarda_coste_por_caso(self):
        _write_all(jev82.D0, spec="d0")
        _write_all(jev82.D1, spec="d1", cost=0.02)
        rep = jev82.rotation_report(printer=lambda *a: None)
        c1 = rep["cost"]["d1"]
        self.assertEqual(c1["max_case"], 0.02)
        self.assertTrue(c1["over_cap"])
        self.assertFalse(rep["cost"]["d0"]["over_cap"])


def _cid(phase, prefix):
    _, cases = load_phase(phase)
    return next(c.id for c in cases if c.id.startswith(prefix))


def _strip_model(run, phases=None, only=None):
    """Quita `model` de los registros de éxito (todos, o solo los ids que
    empiezan por `only`) — simula un proveedor que no declara versión."""
    for ph in phases or score.ADJ_PHASES:
        doc = store.load(run, ph)
        for cid, r in (doc.get("cases") or {}).items():
            if "error" not in r and (only is None or cid.startswith(only)):
                r.pop("model", None)
        store.save(run, ph, doc)


if __name__ == "__main__":
    unittest.main()
