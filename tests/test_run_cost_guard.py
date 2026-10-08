"""Tests de la guarda de coste opt-in de jevbench.run (R56.2 / JEV-82) —
adaptador simulado, sin red: $0,02/caso para que el tope de $0,01/caso pare
tras el primer exceso y el acumulado de $0,05 lo haga al tercer caso."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import run, store
from jevbench.adapters import Adapter
from jevbench.battery import load_phase


class FakeAdapter(Adapter):
    """Responde el contrato de la batería con un coste fijo por caso.
    `calls` cuenta los decide() emitidos — la guarda debe impedir abrir
    peticiones cuando el presupuesto ya está superado."""

    def __init__(self, cost=0.02, fail=False, **opts):
        super().__init__(**opts)
        self.cost = cost
        self.fail = fail
        self.calls = 0

    def meta(self):
        return {"model": "fake"}

    def decide(self, state, questions):
        self.calls += 1
        if self.fail:
            # error pagado: el adaptador informa el gasto en e.cost
            # (contrato JEV-78 — ProviderRefusal y desenlaces terminales)
            e = RuntimeError("boom pagado")
            e.cost = self.cost
            raise e
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
        return {"answers": answers, "cost": self.cost, "model": "fake-1"}


class CostGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="guard_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()
        self.n_cases = len(load_phase("triage_es")[1])

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def _run(self, *extra, cost=0.02, phases="triage_es", run_name="r1",
             fail=False):
        """Ejecuta jevbench.run con el adaptador simulado; devuelve el doc
        de la última fase y el nº de decide() emitidos en la invocación."""
        a = FakeAdapter(cost=cost, fail=fail)
        last = phases.split(",")[-1]
        argv = ["run.py", "fake", "--run", run_name, "--phases", phases,
                *extra]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(run.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(run.adapters, "get", return_value=lambda **o: a):
            run.main()
        return store.load(run_name, last), a.calls

    def test_sin_guarda_comportamiento_intacto(self):
        """Sin los flags el ejecutor corre todos los casos, como siempre."""
        doc, calls = self._run()
        self.assertEqual(len(doc["cases"]), self.n_cases)
        self.assertEqual(calls, self.n_cases)
        self.assertNotIn("cost_stop", doc["meta"])
        self.assertNotIn("cost_guard", doc["meta"])
        self.assertNotIn("cost_ledger", doc["meta"])

    def test_tope_por_caso_para_tras_el_primer_exceso(self):
        """$0,02/caso con tope $0,01: se registra el caso, se anota la
        causa y no se abre el siguiente."""
        doc, calls = self._run("--max-case-cost", "0.01")
        self.assertEqual(len(doc["cases"]), 1)
        self.assertEqual(calls, 1)
        stop = doc["meta"]["cost_stop"]
        self.assertEqual(stop["reason"], "case_cost")
        self.assertEqual(stop["cost"], 0.02)
        self.assertEqual(stop["cap"], 0.01)
        self.assertEqual(doc["meta"]["cost_guard"],
                         {"max_case_cost": 0.01, "max_cost": None})

    def test_tope_acumulado(self):
        """$0,02/caso con tope $0,05: la tercera respuesta cruza el
        acumulado y se para antes de la cuarta."""
        doc, calls = self._run("--max-cost", "0.05")
        self.assertEqual(len(doc["cases"]), 3)
        self.assertEqual(calls, 3)
        stop = doc["meta"]["cost_stop"]
        self.assertEqual(stop["reason"], "accumulated_cost")
        self.assertAlmostEqual(stop["accumulated"], 0.06)

    def test_acumulado_cubre_invocaciones_anteriores(self):
        """El acumulado incluye lo registrado por invocaciones previas del
        mismo run (los dos bloques y sus reintentos comparten tope)."""
        doc, _ = self._run("--max-cost", "0.05", "--limit", "2")
        self.assertEqual(len(doc["cases"]), 2)          # $0,04 previos
        self.assertNotIn("cost_stop", doc["meta"])
        doc, _ = self._run("--max-cost", "0.05")         # reanudación
        self.assertEqual(len(doc["cases"]), 3)           # +1 caso = $0,06
        self.assertEqual(doc["meta"]["cost_stop"]["reason"],
                         "accumulated_cost")

    def test_reanudacion_sobre_el_tope_cero_peticiones(self):
        """Reproducción R56b: $0,006/caso para a 9 casos ($0,054) en la
        primera invocación; repetir el mismo comando NO abre ni una
        petición más — el acumulado durable ya supera el tope."""
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.05")
        doc, calls = self._run(*flags, cost=0.006)
        self.assertEqual(len(doc["cases"]), 9)           # $0,054 > $0,05
        self.assertEqual(calls, 9)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"],
                         "accumulated_cost")
        doc, calls = self._run(*flags, cost=0.006)       # mismo comando
        self.assertEqual(calls, 0)
        self.assertEqual(len(doc["cases"]), 9)
        stop = doc["meta"]["cost_stop"]
        self.assertEqual(stop["reason"], "accumulated_cost")
        self.assertTrue(stop["before_requests"])
        self.assertAlmostEqual(stop["accumulated"], 0.054)

    def test_segundo_bloque_con_run_sobre_el_tope(self):
        """Entrar en otro bloque/fase con el run ya sobre el tope también
        abre 0 peticiones y anota la parada en esa fase."""
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.05")
        doc, _ = self._run(*flags, cost=0.006)           # triage_es para
        self.assertEqual(len(doc["cases"]), 9)
        doc, calls = self._run(*flags, cost=0.006, phases="adv1")
        self.assertEqual(calls, 0)
        self.assertEqual(len(doc["cases"]), 0)
        stop = doc["meta"]["cost_stop"]
        self.assertEqual(stop["reason"], "accumulated_cost")
        self.assertTrue(stop["before_requests"])
        self.assertEqual(stop["phase"], "adv1")

    def test_coste_desconocido_no_dispara(self):
        """Política fijada: coste no informado no dispara la guarda ni suma
        al acumulado (se cuentan aparte)."""
        doc, calls = self._run("--max-case-cost", "0.01", "--max-cost",
                               "0.05", cost=None)
        self.assertEqual(len(doc["cases"]), self.n_cases)
        self.assertEqual(calls, self.n_cases)
        self.assertNotIn("cost_stop", doc["meta"])

    def test_ledger_durable_tras_retry_errors(self):
        """R58c §2: --retry-errors REEMPLAZA los registros de error y la
        suma de registros vigentes baja; meta.cost_ledger conserva el
        gasto de adquisición de todas las invocaciones y la guarda lo usa
        en el bloque siguiente. Réplica de R58c_retry_ledger.py: pasada
        $0,027 + retry $0,009 -> durable $0,036 (no $0,009)."""
        flags = ("--max-cost", "0.05")
        # pasada: 3 casos OOD fallan pagados ($0,009 cada uno)
        doc, calls = self._run(*flags, cost=0.009, phases="ood", fail=True)
        self.assertEqual((calls, len(doc["cases"])), (3, 3))
        self.assertAlmostEqual(doc["meta"]["cost_ledger"], 0.027)
        # único retry: los registros se reemplazan ($0,003 vigente cada
        # uno) pero el ledger acumula ambas pasadas — sin doble conteo
        doc, calls = self._run(*flags, "--retry-errors", cost=0.003,
                               phases="ood", fail=True)
        self.assertEqual((calls, len(doc["cases"])), (3, 3))
        self.assertAlmostEqual(
            sum(r["cost"] for r in doc["cases"].values()), 0.009)
        self.assertAlmostEqual(doc["meta"]["cost_ledger"], 0.036)
        # siguiente bloque bajo la guarda: el durable es $0,036 — un tope
        # de $0,035 para antes de abrir peticiones (con los registros
        # vigentes solos, $0,009, habría seguido)
        doc, calls = self._run("--max-cost", "0.035", cost=0.003,
                               phases="triage_es")
        self.assertEqual(calls, 0)
        stop = doc["meta"]["cost_stop"]
        self.assertEqual(stop["reason"], "accumulated_cost")
        self.assertTrue(stop["before_requests"])
        self.assertAlmostEqual(stop["accumulated"], 0.036)

    def test_sin_stamp_config_no_huella(self):
        """Sin --stamp-config el runner no escribe config_sha256 (previo)."""
        doc, _ = self._run(cost=0.001)
        self.assertTrue(doc["cases"])
        self.assertTrue(all("config_sha256" not in r
                            for r in doc["cases"].values()))

    def test_stamp_config_huella_y_rechaza_effort(self):
        """R72-P1-2b: con --stamp-config, high→medium aborta 0 llamadas."""
        from jevbench import cost_guard

        class Effort(FakeAdapter):
            def __init__(self, effort, interrupt=False, **k):
                super().__init__(cost=0.0001, **k)
                self.effort = effort
                self.interrupt = interrupt

            def meta(self):
                return {"model": "same-alias", "resolved": "snapshot-A",
                        "thinking": "adaptive", "effort": self.effort,
                        "max_tokens": 8192}

            def decide(self, state, qs):
                if self.interrupt and self.calls == 1:
                    raise KeyboardInterrupt()
                r = super().decide(state, qs)
                r["model"] = "snapshot-A"
                return r

        def invoke(name, a):
            argv = ["run", "fake", "--run", name, "--phases", "ood",
                    "--stamp-config",
                    "--max-case-cost", ".01", "--max-cost", ".15"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.dict(run.adapters.REGISTRY, {"fake": "x:y"}), \
                 mock.patch.object(run.adapters, "get",
                                   return_value=lambda **o: a):
                try:
                    run.main()
                    return None
                except (KeyboardInterrupt, SystemExit) as e:
                    return type(e).__name__

        first = Effort("high", interrupt=True)
        self.assertEqual(invoke("s_mixed", first), "KeyboardInterrupt")
        self.assertEqual(first.calls, 1)
        prior = store.load("s_mixed", "ood")
        self.assertEqual(prior["meta"]["effort"], "high")
        self.assertIn("config_sha256", next(iter(prior["cases"].values())))
        resume = Effort("medium")
        self.assertEqual(invoke("s_mixed", resume), "SystemExit")
        self.assertEqual(resume.calls, 0)
        self.assertEqual(store.load("s_mixed", "ood")["meta"]["effort"], "high")
        # huella canónica distinta entre efforts
        self.assertNotEqual(
            cost_guard.config_sha256({"effort": "high", "max_tokens": 8192}),
            cost_guard.config_sha256({"effort": "medium", "max_tokens": 8192}))


if __name__ == "__main__":
    unittest.main()
