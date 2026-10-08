"""Guardas de coste y fingerprint de scripts/alert_onepass.py (JEV-84 R68)."""
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import store
from jevbench.adapters import Adapter
from jevbench.battery import load_phase

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "alert_onepass.py"
_spec = importlib.util.spec_from_file_location("alert_onepass", _SCRIPT)
alert = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alert)


class FakeAlert(Adapter):
    def __init__(self, cost=0.02, thinking=None, model="fake-alert", **opts):
        super().__init__(**opts)
        self.cost = cost
        self.thinking = thinking
        self.model_name = model
        self.calls = 0

    def meta(self):
        return {"model": self.model_name, "resolved": f"{self.model_name}-1",
                "provider": "fake", "mode": "probabilities",
                "thinking": self.thinking,
                "effort": "medium" if self.thinking == "adaptive" else None}

    def decide(self, state, questions):
        self.calls += 1
        return {"answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                "cost": self.cost, "model": f"{self.model_name}-1"}


class AlertCostGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="alert_guard_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def _run(self, *extra, cost=0.02, run="a1", thinking=None, model="fake-alert"):
        a = FakeAlert(cost=cost, thinking=thinking, model=model)
        argv = ["alert_onepass.py", "fake", run, *extra]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            try:
                alert.main()
                err = None
            except SystemExit as e:
                err = e
        return store.load(f"{run}_alert_raw", "adv3"), a.calls, err

    def test_sin_guarda_intacto(self):
        n = len(load_phase("adv3")[1])
        doc, calls, _ = self._run()
        self.assertEqual(calls, 60)
        self.assertEqual(len(doc["cases"]), n)
        self.assertNotIn("cost_stop", doc["meta"])

    def test_tope_acumulado(self):
        flags = ("--max-cost", "0.05")
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 3)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "accumulated_cost")
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 0)
        self.assertTrue(doc["meta"]["cost_stop"].get("before_requests"))

    def test_case_cost_bloquea_reanudacion(self):
        flags = ("--max-case-cost", "0.01", "--max-cost", "0.40")
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 1)
        self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 0)
        self.assertEqual(doc["meta"]["cost_stop"].get("blocked_by"),
                         "case_cost_stop")

    def test_acumulado_igual_al_maximo(self):
        flags = ("--max-cost", "0.06")
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 3)
        doc, calls, _ = self._run(*flags, cost=0.02)
        self.assertEqual(calls, 0)

    def test_adaptive_a_disabled_rechaza(self):
        flags = ("--max-cost", "0.50")
        doc, calls, _ = self._run(*flags, cost=0.001, thinking="adaptive")
        # solo adv3 empieza; con cost bajo completa las 3 fases (60)
        self.assertEqual(calls, 60)
        self.assertEqual(doc["meta"]["thinking"], "adaptive")
        doc2, calls, err = self._run(*flags, cost=0.001, thinking="disabled")
        self.assertEqual(calls, 0)
        self.assertIsNotNone(err)
        self.assertEqual(doc2["meta"]["thinking"], "adaptive")

    def test_sin_flags_adaptive_a_disabled_historico(self):
        """R69 F5: sin guardas, cambiar thinking no aborta."""
        doc, calls, err = self._run(cost=0.001, thinking="adaptive")
        self.assertIsNone(err)
        self.assertEqual(calls, 60)
        doc2, calls, err = self._run(cost=0.001, thinking="disabled")
        self.assertIsNone(err)
        self.assertEqual(calls, 0)
        self.assertEqual(doc2["meta"]["thinking"], "disabled")

    def test_resolved_none_preserva_y_detecta_drift(self):
        """R69 F3: reanudación con meta.resolved=None no borra la versión."""
        class UnresolvedThenB(FakeAlert):
            def __init__(self, *a, snap="A", **k):
                super().__init__(*a, **k)
                self.snap = snap

            def meta(self):
                m = super().meta()
                m["resolved"] = None  # adaptador aún no resolvió
                return m

            def decide(self, state, questions):
                self.calls += 1
                return {"answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                        "cost": self.cost, "model": f"snap-{self.snap}"}

        # primera adquisición: resolved se fija desde response.model
        a = UnresolvedThenB(cost=0.001, thinking="adaptive", snap="A")
        argv = ["alert_onepass.py", "fake", "a1",
                "--max-cost", "0.50"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            alert.main()
        doc = store.load("a1_alert_raw", "adv3")
        self.assertEqual(doc["meta"]["resolved"], "snap-A")
        self.assertEqual(a.calls, 60)

        # borrar un caso para forzar reanudación; adaptador unresolved + snap-B
        first_id = next(iter(doc["cases"]))
        del doc["cases"][first_id]
        # simular adaptador nuevo: resolved=None en meta persistido se
        # preservaría; aquí el meta sigue con snap-A
        store.save("a1_alert_raw", "adv3", doc)

        b = UnresolvedThenB(cost=0.001, thinking="adaptive", snap="B")
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: b):
            err = None
            try:
                alert.main()
            except SystemExit as e:
                err = e
        self.assertIsNotNone(err)
        self.assertIn("resolved cambió", str(err))
        doc2 = store.load("a1_alert_raw", "adv3")
        # evidencia del drift persistida con gasto
        self.assertIn(first_id, doc2["cases"])
        self.assertTrue(doc2["cases"][first_id].get("version_drift")
                        or doc2["meta"].get("version_drift"))
        self.assertEqual(doc2["cases"][first_id].get("cost"), 0.001)
        self.assertEqual(doc2["meta"]["resolved"], "snap-A")
        self.assertEqual(b.calls, 1)

    def test_version_congelada_fase_nueva_rechaza(self):
        """R70-4: adv3=A → adv4=B aborta sin mezclar versiones."""
        class VersionAlert(FakeAlert):
            def __init__(self, snap, **kw):
                super().__init__(**kw)
                self.snap = snap

            def meta(self):
                m = super().meta()
                m["resolved"] = None
                return m

            def decide(self, state, questions):
                self.calls += 1
                return {"answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                        "cost": self.cost, "model": self.snap}

        a = VersionAlert("snap-A", cost=0.001, thinking="adaptive")
        argv = ["alert_onepass.py", "fake", "ver", "--max-cost", "0.50"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(alert, "PHASES", ["adv3"]), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            alert.main()
        self.assertEqual(a.calls, 20)
        self.assertEqual(store.load("ver_alert_raw", "adv3")["meta"]["resolved"],
                         "snap-A")
        b = VersionAlert("snap-B", cost=0.001, thinking="adaptive")
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(alert, "PHASES", ["adv4"]), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: b):
            with self.assertRaises(SystemExit) as cm:
                alert.main()
        msg = str(cm.exception).lower()
        self.assertTrue("versión" in msg or "resolved" in msg or "cambió" in msg,
                        msg)
        # aborta en el 1º decide (evidencia) o en preflight
        self.assertLessEqual(b.calls, 1)
        # adv3 intacto; no se acepta snap-B como resolved del run
        self.assertEqual(store.load("ver_alert_raw", "adv3")["meta"]["resolved"],
                         "snap-A")
        adv4 = store.load("ver_alert_raw", "adv4")
        if adv4 is not None:
            self.assertNotEqual(adv4["meta"].get("resolved"), "snap-B")
            self.assertTrue(adv4["meta"].get("version_drift")
                            or any(r.get("version_drift")
                                   for r in adv4["cases"].values()))

    def test_reanudacion_hash_dinamico_no_aborta(self):
        """R71 P2-1: system_prompt_sha256 solo tras decide; repetir config OK."""
        class HashAlert(FakeAlert):
            def meta(self):
                m = super().meta()
                m["system_prompt_sha256"] = "hash" if self.calls else None
                return m

        a = HashAlert(cost=0.001, thinking="adaptive")
        argv = ["alert_onepass.py", "fake", "hash", "--max-cost", "0.50"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            alert.main()
        self.assertEqual(a.calls, 60)
        # reanudar con adaptador fresco (hash aún None) no debe abortar
        b = HashAlert(cost=0.001, thinking="adaptive")
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: b):
            err = None
            try:
                alert.main()
            except SystemExit as e:
                err = e
        self.assertIsNone(err)
        self.assertEqual(b.calls, 0)
        # huella por caso presente y única
        shas = {r["config_sha256"]
                for ph in alert.PHASES
                for r in store.load("hash_alert_raw", ph)["cases"].values()}
        self.assertEqual(len(shas), 1)

    def test_effort_medium_a_none_rechaza_cero_llamadas(self):
        """R72-P1-1: effort medium→None aborta antes de llamadas/meta."""
        class EffortAlert(FakeAlert):
            def __init__(self, effort, interrupt=False, **k):
                super().__init__(cost=0.0001, thinking="adaptive", **k)
                self.effort = effort
                self.interrupt = interrupt

            def meta(self):
                return {**super().meta(), "effort": self.effort,
                        "max_tokens": 8192}

            def decide(self, state, questions):
                if self.interrupt and self.calls == 1:
                    raise KeyboardInterrupt()
                return super().decide(state, questions)

        argv = ["alert_onepass.py", "fake", "effort",
                "--max-case-cost", ".01", "--max-cost", ".10"]
        a = EffortAlert("medium", interrupt=True)
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            with self.assertRaises(KeyboardInterrupt):
                alert.main()
        prior = store.load("effort_alert_raw", "adv3")
        self.assertEqual(prior["meta"]["effort"], "medium")
        b = EffortAlert(None)
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: b):
            with self.assertRaises(SystemExit) as cm:
                alert.main()
        self.assertEqual(b.calls, 0)
        self.assertIn("effort", str(cm.exception))
        self.assertEqual(store.load("effort_alert_raw", "adv3")["meta"]["effort"],
                         "medium")

    def test_retry_interrumpido_no_repite(self):
        """R69 F4: retry interrumpido no reabre casos ya reintentados."""
        class AlwaysErr(FakeAlert):
            def decide(self, state, questions):
                self.calls += 1
                err = RuntimeError("boom")
                err.cost = self.cost
                raise err

        a = AlwaysErr(cost=0.001, thinking="adaptive")
        argv = ["alert_onepass.py", "fake", "r1", "--max-cost", "1.00"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: a):
            alert.main()
        self.assertEqual(a.calls, 60)

        class RetryCut(FakeAlert):
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

        b = RetryCut(cost=0.001, thinking="adaptive")
        argv2 = ["alert_onepass.py", "fake", "r1",
                 "--max-cost", "1.00", "--retry-errors"]
        with mock.patch.object(sys, "argv", argv2), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: b):
            with self.assertRaises(KeyboardInterrupt):
                alert.main()
        self.assertEqual(b.calls, 2)

        c = AlwaysErr(cost=0.001, thinking="adaptive")
        with mock.patch.object(sys, "argv", argv2), \
             mock.patch.dict(alert.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(alert.adapters, "get",
                               return_value=lambda **o: c):
            alert.main()
        # 60-2 ya marcados = 58 restantes (adv3 tiene 20; corte en 2º de adv3)
        self.assertEqual(c.calls, 58)


if __name__ == "__main__":
    unittest.main()
