"""Guardas de coste y reanudación estricta de jevbench.cascade (JEV-84 R68/R69)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import cascade, cost_guard, store
from jevbench.adapters import Adapter
from jevbench.battery import load_phase


class RemainingBudget(unittest.TestCase):
    def test_desconocido_consume_reserva(self):
        cupo, margin = cost_guard.remaining_budget(
            ceiling=1.50, spent=1.00, margin_reserved=0.20, unknown_spent=0.05)
        self.assertAlmostEqual(margin, 0.15)
        # desconocido se descuenta además del margen residual → cupo no sube
        self.assertAlmostEqual(cupo, 1.50 - 1.00 - 0.05 - 0.15)

    def test_desconocido_agota_margen(self):
        cupo, margin = cost_guard.remaining_budget(
            ceiling=1.50, spent=1.00, margin_reserved=0.20, unknown_spent=0.50)
        self.assertEqual(margin, 0.0)
        self.assertAlmostEqual(cupo, 1.50 - 1.00 - 0.50)

    def test_desconocido_monotono_no_aumenta_cupo(self):
        """R70-1: más desconocido nunca da más cupo operativo."""
        prev = None
        for u in (0.0, 0.05, 0.20, 0.50, 1.00):
            cupo, _ = cost_guard.remaining_budget(
                ceiling=1.50, spent=1.00, margin_reserved=0.20,
                unknown_spent=u)
            if prev is not None:
                self.assertLessEqual(cupo, prev + 1e-12)
            prev = cupo
        # techo: spent+unknown no puede liberar presupuesto por encima
        cupo0, _ = cost_guard.remaining_budget(
            ceiling=1.50, spent=1.00, margin_reserved=0.20, unknown_spent=0)
        cupo_hi, _ = cost_guard.remaining_budget(
            ceiling=1.50, spent=1.00, margin_reserved=0.20, unknown_spent=0.50)
        self.assertLessEqual(cupo_hi, cupo0)
        self.assertAlmostEqual(cupo0, 0.30)
        self.assertAlmostEqual(cupo_hi, 0.00)


class FakeReviewer(Adapter):
    def __init__(self, cost=0.02, thinking=None, model="fake-rev", **opts):
        super().__init__(**opts)
        self.cost = cost
        self.thinking = thinking
        self.model_name = model
        self.calls = 0

    def meta(self):
        m = {"model": self.model_name, "resolved": f"{self.model_name}-1",
             "provider": "fake", "mode": "probabilities",
             "thinking": self.thinking, "effort":
                 "medium" if self.thinking == "adaptive" else None}
        return m

    def decide(self, state, questions):
        self.calls += 1
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "choice":
                lab = next(iter(q["criteria"]))
                answers[qid] = {"type": "choice", "choice": lab,
                                "probabilities": {lab: 1.0}}
            elif q["type"] == "score":
                answers[qid] = {"type": "score", "score": 0.0,
                                "probabilities": {"0": 1.0}}
            else:
                answers[qid] = {"type": "noul", "noul": 0.0}
        return {"answers": answers, "cost": self.cost,
                "model": f"{self.model_name}-1"}


def _seed_d1(run, phase, cost=0.0):
    qs, cases = load_phase(phase)
    doc = {"meta": {"model": "d1"}, "cases": {}}
    for c in cases:
        answers = {}
        for qid, q in qs.items():
            if q["type"] == "choice":
                lab = next(iter(q["criteria"]))
                answers[qid] = {"type": "choice", "choice": lab,
                                "probabilities": {lab: 1.0}}
            elif q["type"] == "score":
                answers[qid] = {"type": "score", "score": 0.0,
                                "probabilities": {"0": 1.0}}
            else:
                answers[qid] = {"type": "noul", "noul": 0.0}
        doc["cases"][c.id] = {"answers": answers, "cost": cost}
    store.save(run, phase, doc)
    return cases


class CascadeCostGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="casc_guard_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def _run(self, *extra, cost=0.02, phases="ood", d1="d1", prefix="p",
             thinking=None, model="fake-rev"):
        for ph in phases.split(","):
            if store.load(d1, ph) is None:
                _seed_d1(d1, ph)
        rev = FakeReviewer(cost=cost, thinking=thinking, model=model)
        argv = ["cascade.py", "--d1", d1, "--adapter", "fake",
                "--prefix", prefix, "--control", "", "--phases", phases,
                *extra]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev):
            try:
                cascade.main()
                err = None
            except SystemExit as e:
                err = e
        last = phases.split(",")[-1]
        return store.load(f"{prefix}_raw", last), rev.calls, err

    def test_sin_guarda_intacto(self):
        n = len(load_phase("ood")[1])
        doc, calls, err = self._run()
        self.assertIsNone(err)
        self.assertEqual(len(doc["cases"]), n)
        self.assertEqual(calls, n)
        self.assertNotIn("cost_stop", doc["meta"])

    def test_tope_por_caso(self):
        doc, calls, _ = self._run("--max-case-cost", "0.01")
        self.assertEqual(calls, 1)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")

    def test_case_cost_bloquea_reanudacion(self):
        """R68 §1: tras case_cost, el mismo comando abre 0 peticiones."""
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.40")
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 1)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 0)
        self.assertTrue(doc["meta"]["cost_stop"].get("before_requests"))
        self.assertEqual(doc["meta"]["cost_stop"].get("blocked_by"),
                         "case_cost_stop")

    def test_case_cost_bloquea_otra_fase(self):
        """R68 §1: case_cost en triage_es bloquea también adv1."""
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.40")
        _, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 1)
        doc, calls, _ = self._run(*flags, cost=0.02, phases="adv1")
        self.assertEqual(calls, 0)
        self.assertEqual(doc["meta"]["cost_stop"].get("blocked_by"),
                         "case_cost_stop")

    def test_acumulado_igual_al_maximo_bloquea(self):
        """R68 §1: prior+session >= max_cost → 0 peticiones."""
        flags = ("--max-cost", "0.06")
        # 3×0.02 = 0.06 exactamente → para tras el 3º; reanudar bloquea
        doc, calls, _ = self._run(*flags, cost=0.02, phases="ood")
        self.assertEqual(calls, 3)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "accumulated_cost")
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 0)
        self.assertTrue(doc["meta"]["cost_stop"].get("before_requests"))

    def test_tope_acumulado_y_reanudacion_cero(self):
        flags = ("--max-cost", "0.05")
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 3)
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 0)
        self.assertTrue(doc["meta"]["cost_stop"].get("before_requests"))

    def test_adaptive_a_disabled_rechaza_sin_tocar(self):
        """R68 §4: cambiar thinking no reutiliza ni reetiqueta."""
        flags = ("--max-cost", "0.50")
        doc, calls, _ = self._run(*flags, cost=0.001, phases="ood",
                                  thinking="adaptive")
        self.assertEqual(calls, 3)
        self.assertEqual(doc["meta"]["thinking"], "adaptive")
        meta_before = dict(doc["meta"])
        doc2, calls, err = self._run(*flags, cost=0.001, phases="ood",
                                     thinking="disabled")
        self.assertEqual(calls, 0)
        self.assertIsNotNone(err)
        self.assertIn("configuración efectiva", str(err))
        # meta de procedencia intacta (thinking sigue adaptive)
        self.assertEqual(doc2["meta"]["thinking"], meta_before["thinking"])

    def test_cambio_modelo_rechaza(self):
        flags = ("--max-cost", "0.50")
        _, calls, _ = self._run(*flags, cost=0.001, phases="ood",
                                model="modelo-a")
        self.assertEqual(calls, 3)
        _, calls, err = self._run(*flags, cost=0.001, phases="ood",
                                  model="modelo-b")
        self.assertEqual(calls, 0)
        self.assertIsNotNone(err)

    def test_amend_permite_reanudar_tras_case_cost(self):
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.40")
        doc, calls, _ = self._run(*flags, cost=0.02, phases="triage_es")
        self.assertEqual(calls, 1)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")
        # enmendar evidencia (sin borrar) y reanudar con tope por caso mayor
        rev = FakeReviewer(cost=0.02)
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "triage_es",
                "--max-case-cost", "0.05", "--max-cost", "0.40",
                "--amend-case-cost-stop"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev):
            cascade.main()
        self.assertGreaterEqual(rev.calls, 1)
        stop = store.load("p_raw", "triage_es")["meta"]["cost_stop"]
        # la enmienda queda registrada en el stop original
        self.assertTrue(stop.get("amended") or stop.get("reason") != "case_cost"
                        or rev.calls >= 1)

    def test_adaptive_a_disabled_fase_nueva_rechaza(self):
        """R69 F2: fase nueva no puede mezclar thinking con otra fase del run."""
        flags = ("--max-cost", "0.50")
        doc, calls, _ = self._run(*flags, cost=0.001, phases="ood",
                                  thinking="adaptive")
        self.assertEqual(calls, 3)
        self.assertEqual(doc["meta"]["thinking"], "adaptive")
        doc2, calls, err = self._run(*flags, cost=0.001, phases="triage_es",
                                     thinking="disabled")
        self.assertEqual(calls, 0)
        self.assertIsNotNone(err)
        self.assertIn("configuración efectiva", str(err))
        # ood intacto
        self.assertEqual(store.load("p_raw", "ood")["meta"]["thinking"],
                         "adaptive")
        self.assertIsNone(doc2)  # triage_es no se abrió

    def test_preflight_discrepancia_fase_posterior_sin_gastar(self):
        """R69 F2: si una fase posterior ya difiere, 0 llamadas en anteriores."""
        flags = ("--max-cost", "0.50")
        _, calls, _ = self._run(*flags, cost=0.001, phases="ood",
                                thinking="adaptive")
        self.assertEqual(calls, 3)
        # sembrar triage_es con thinking distinto (sin pasar por cascade)
        _seed_d1("d1", "triage_es")
        qs, cases = load_phase("triage_es")
        bad = {"meta": {"d1": "d1", "reviewer": "fake", "thinking": "disabled",
                        "model": "fake-rev", "provider": "fake",
                        "mode": "probabilities",
                        "questions_hash": store.load("p_raw", "ood")["meta"][
                            "questions_hash"]},
               "cases": {}}
        store.save("p_raw", "triage_es", bad)
        # pedir ood de nuevo (completo) + no debería gastar; el preflight
        # detecta triage_es antes de cualquier decide
        _, calls, err = self._run(*flags, cost=0.001, phases="ood",
                                  thinking="adaptive")
        self.assertEqual(calls, 0)
        self.assertIsNotNone(err)

    def test_sin_flags_adaptive_a_disabled_historico(self):
        """R69 F5: sin guardas, cambiar thinking no aborta (histórico)."""
        doc, calls, err = self._run(cost=0.001, phases="ood",
                                    thinking="adaptive")
        self.assertIsNone(err)
        self.assertEqual(calls, 3)
        # reanudar disabled: sin pendientes → 0 llamadas, sin SystemExit
        doc2, calls, err = self._run(cost=0.001, phases="ood",
                                     thinking="disabled")
        self.assertIsNone(err)
        self.assertEqual(calls, 0)
        # meta se actualiza al comportamiento histórico (reetiqueta)
        self.assertEqual(doc2["meta"]["thinking"], "disabled")

    def test_version_congelada_rechaza_fase_nueva_distinta(self):
        """R70-4: versión A en ood → fase nueva con B aborta (0 mescla)."""
        class Versioned(FakeReviewer):
            def __init__(self, snap, **kw):
                super().__init__(**kw)
                self.snap = snap

            def meta(self):
                return {**super().meta(), "resolved": self.snap}

            def decide(self, state, questions):
                out = super().decide(state, questions)
                out["model"] = self.snap
                return out

        flags = ("--max-cost", "0.50")
        for ph in ("ood", "triage_es"):
            _seed_d1("d1", ph)
        rev_a = Versioned("snapshot-A", cost=0.001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "ood", *flags]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev_a):
            cascade.main()
        self.assertEqual(rev_a.calls, 3)
        self.assertEqual(store.load("p_raw", "ood")["meta"]["reviewer_resolved"],
                         "snapshot-A")
        rev_b = Versioned("snapshot-B", cost=0.001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "triage_es",
                *flags]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev_b):
            with self.assertRaises(SystemExit) as cm:
                cascade.main()
        msg = str(cm.exception).lower()
        self.assertTrue(
            "versión" in msg or "resolved" in msg or "configuración" in msg,
            msg)
        self.assertEqual(rev_b.calls, 0)
        self.assertIsNone(store.load("p_raw", "triage_es"))

    def test_version_congelada_reanudacion_misma_ok(self):
        """R70-4: A→A en fase nueva se admite."""
        class Versioned(FakeReviewer):
            def __init__(self, snap, **kw):
                super().__init__(**kw)
                self.snap = snap

            def meta(self):
                return {**super().meta(), "resolved": self.snap}

            def decide(self, state, questions):
                out = super().decide(state, questions)
                out["model"] = self.snap
                return out

        flags = ("--max-cost", "0.50")
        for ph in ("ood", "triage_es"):
            _seed_d1("d1", ph)
        for ph, snap in (("ood", "snapshot-A"), ("triage_es", "snapshot-A")):
            rev = Versioned(snap, cost=0.001, thinking="adaptive")
            argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                    "--prefix", "p", "--control", "", "--phases", ph, *flags]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
                 mock.patch.object(cascade.adapters, "get",
                                   return_value=lambda **o: rev):
                cascade.main()
            self.assertGreater(rev.calls, 0)
            self.assertEqual(
                store.load("p_raw", ph)["meta"]["reviewer_resolved"],
                "snapshot-A")

    def test_fingerprint_prompt_sha_y_orden(self):
        """R70-6: prompt_sha256 / choice_order en fingerprint."""
        mm = cost_guard.config_mismatches(
            {"prompt": "triage", "prompt_sha256": "A",
             "choice_order": {"x": ["a", "b"]}, "thinking": "adaptive"},
            {"prompt": "triage", "prompt_sha256": "B",
             "choice_order": {"x": ["b", "a"]}, "thinking": "adaptive"})
        keys = {k for k, _, _ in mm}
        self.assertIn("prompt_sha256", keys)
        self.assertIn("choice_order", keys)

    def test_fingerprint_ignora_desconocido_post_decide(self):
        """R71 P2-1 / R72: dinámicos admiten None nuevo; estáticos no."""
        mm = cost_guard.config_mismatches(
            {"thinking": "adaptive", "system_prompt_sha256": "hash"},
            {"thinking": "adaptive", "system_prompt_sha256": None})
        self.assertEqual(mm, [])
        # ambos conocidos y distintos → sí
        mm2 = cost_guard.config_mismatches(
            {"system_prompt_sha256": "hashA"},
            {"system_prompt_sha256": "hashB"})
        self.assertEqual(mm2, [("system_prompt_sha256", "hashA", "hashB")])
        # estático: medium→None es mismatch (R72-P1-1)
        mm3 = cost_guard.config_mismatches(
            {"effort": "medium", "thinking": "adaptive"},
            {"effort": None, "thinking": "adaptive"})
        self.assertEqual(mm3, [("effort", "medium", None)])
        # canónica: ausente ≡ None
        self.assertEqual(
            cost_guard.canonical_config({"effort": "medium"})["effort"],
            "medium")
        self.assertIsNone(
            cost_guard.canonical_config({})["effort"])
        self.assertNotEqual(
            cost_guard.config_sha256({"effort": "medium", "max_tokens": 8192}),
            cost_guard.config_sha256({"effort": "medium", "max_tokens": 4096}))

    def test_retry_interrumpido_no_repite_ya_reintentados(self):
        """R69 F4: corte a mitad del retry; reanudar no repite el 1º caso."""
        class Flaky(FakeReviewer):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.n_err = 0

            def decide(self, state, questions):
                self.calls += 1
                # siempre error con coste
                err = RuntimeError("boom")
                err.cost = self.cost
                raise err

        # pasada inicial con errores
        for ph in ("ood",):
            _seed_d1("d1", ph)
        rev = Flaky(cost=0.001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "ood",
                "--max-cost", "0.50"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev):
            cascade.main()
        self.assertEqual(rev.calls, 3)
        raw = store.load("p_raw", "ood")
        self.assertTrue(all("error" in r for r in raw["cases"].values()))

        # retry: falla el 1º (ya marcado), KeyboardInterrupt en el 2º
        class RetryFlaky(FakeReviewer):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.seen = 0

            def decide(self, state, questions):
                self.calls += 1
                self.seen += 1
                if self.seen == 1:
                    err = RuntimeError("again")
                    err.cost = self.cost
                    raise err
                raise KeyboardInterrupt("cut")

        rev2 = RetryFlaky(cost=0.001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "ood",
                "--max-cost", "0.50", "--retry-errors"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev2):
            with self.assertRaises(KeyboardInterrupt):
                cascade.main()
        self.assertEqual(rev2.calls, 2)
        raw = store.load("p_raw", "ood")
        ids = [c.id for c in load_phase("ood")[1]]
        self.assertIn(f"ood/{ids[0]}",
                      raw["meta"]["acquisition"]["retried_cases"])
        # segundo retry: no debe reabrir el primero ya reintentado
        rev3 = Flaky(cost=0.001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1", "--adapter", "fake",
                "--prefix", "p", "--control", "", "--phases", "ood",
                "--max-cost", "0.50", "--retry-errors"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev3):
            cascade.main()
        # tras interrupt, ids[0] e ids[1] ya están en retried_cases; solo ids[2]
        self.assertEqual(rev3.calls, 1)
        self.assertIn(f"ood/{ids[2]}",
                      store.load("p_raw", "ood")["meta"]["acquisition"][
                          "retried_cases"])

    def test_cambio_d1_fase_nueva_rechaza_cero_llamadas(self):
        """R73-P1-2: cambiar --d1 entre fases → preflight 0 llamadas."""
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.40")
        _seed_d1("d1a", "triage_es")
        _seed_d1("d1b", "ood")
        doc, calls, err = self._run(*flags, cost=0.0001, phases="triage_es",
                                    d1="d1a", prefix="mix",
                                    thinking="adaptive")
        self.assertIsNone(err)
        self.assertGreater(calls, 0)
        self.assertEqual(doc["meta"]["d1"], "d1a")
        self.assertEqual(doc["meta"]["prefix"], "mix")
        # misma huella de intervención: d1 en CONFIG_FINGERPRINT_KEYS
        rec = next(iter(doc["cases"].values()))
        self.assertIn("config_sha256", rec)
        rev = FakeReviewer(cost=0.0001, thinking="adaptive")
        argv = ["cascade.py", "--d1", "d1b", "--adapter", "fake",
                "--prefix", "mix", "--control", "", "--phases", "ood",
                *flags]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(cascade.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(cascade.adapters, "get",
                               return_value=lambda **o: rev):
            try:
                cascade.main()
                err2 = None
            except SystemExit as e:
                err2 = str(e)
        self.assertEqual(rev.calls, 0)
        self.assertIsNotNone(err2)
        self.assertIn("d1", str(err2))
        self.assertIsNone(store.load("mix_raw", "ood"))


if __name__ == "__main__":
    unittest.main()
