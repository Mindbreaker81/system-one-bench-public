"""Tests offline del wrapper de la cascada JEV-77 (jevbench.jev77_cascade):
el cupo de 800 intentos de red es persistente (no se resetea entre
invocaciones), se reserva ANTES de abrir cada intento HTTP (reintentos
internos del revisor incluidos), el deadline wall de 3 h corta la pasada
y sin remanente la petición no se abre — lo pendiente queda no ejecutado.
"""
import json
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import jevbench.jev77_cascade as jc
from jevbench import qwen_session as qs_mod
from jevbench import store
from jevbench.battery import load_phase


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps({"answers": {}, "model": "m",
                           "usage": {}}).encode()


class _FakeReviewer:
    """Revisor sintético: hace `attempts` aperturas HTTP por decide()
    (vía urllib.request.urlopen, que el wrapper intercepta) y devuelve
    respuestas wire válidas para las preguntas de revisión."""

    def __init__(self, attempts=1):
        self.attempts = attempts
        self.calls = 0

    def meta(self):
        # el modelo efectivo de OpenRouter, como en adapters.jev
        # (PROVIDERS) — no el alias typesafe
        return {"provider": "openrouter", "model": "~typesafe/jev-latest",
                "resolved": "jev-test"}

    def decide(self, state, questions):
        self.calls += 1
        for _ in range(self.attempts):
            urllib.request.urlopen("http://fake.local/v1")
        out = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                out[qid] = {"noul": 0.9}
            elif q["type"] == "choice":
                crit = list(q["criteria"])
                out[qid] = {"choice": crit[0],
                            "probabilities": {k: (1.0 if k == crit[0]
                                                  else 0.0)
                                              for k in crit}}
            else:
                out[qid] = {"score": 0.0,
                            "probabilities": {"0": 1.0}}
        return {"answers": out, "cost": 0.001, "model": "fake"}


def _write_d1(run, phase):
    """Run de pasada 1 sintético con respuestas wire por tipo."""
    qs, cases = load_phase(phase)
    recs = {}
    for c in cases:
        a = {}
        for qid, q in qs.items():
            if q["type"] == "noul":
                a[qid] = {"noul": float(c.gt[qid])}
            elif q["type"] == "choice":
                a[qid] = {"choice": c.gt[qid],
                          "probabilities": {k: (1.0 if k == c.gt[qid]
                                                else 0.0)
                                            for k in q["criteria"]}}
            else:
                a[qid] = {"score": float(c.gt[qid]),
                          "probabilities":
                          {str(i): (1.0 if i == c.gt[qid] else 0.0)
                           for i in range(len(q["criteria"]))}}
        recs[c.id] = {"answers": a}
    store.save(run, phase, {"meta": {}, "cases": recs})
    return len(cases)


MD0_RUN = "llm_medgemma_27b_it_bf16_jev77_d0_disc"


def _write_encargo(root, caps=None, mutate=None, recompute=True):
    """Fixture de encargo válido (R39): estado A6 con sesión y wall_t0
    + el manifiesto COMPLETO del plan vigente (integridad verificable).
    `caps`/`mutate` alteran el contenido; `recompute=False` deja el sha
    declarado sin renovar (contenido alterado, R39 §1)."""
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / jc.JEV77_STATE_FILE).write_text(json.dumps(
        {"session": "s0", "wall_t0": time.time()}))
    qs_mod._set_profile("jev77")
    man = qs_mod._plan_manifest()
    if caps:
        man["policies"]["cascade"].update(caps)
    if mutate:
        mutate(man)
    if recompute:
        man["manifest_sha256"] = qs_mod._manifest_content_sha(man)
    (root / "logs" / jc.JEV77_MANIFEST_FILE).write_text(
        json.dumps(man))
    return man


def _freeze(budget, meta=None):
    """Congela el revisor en el presupuesto como hace el paso A4
    (`freeze_reviewer`) — los tests lo fijan directo para no depender
    de la petición de sondeo."""
    meta = meta or _FakeReviewer().meta()
    budget.st["reviewer"] = {**meta, "adapter": "jev"}
    budget._save()


class TestJEV77CascadeBudget(unittest.TestCase):
    """El cupo persistente del wrapper: contador de red y reloj wall."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root = store.ROOT
        store.ROOT = self.tmp
        self.path = self.tmp / "logs" / jc.STATE_FILE
        self.addCleanup(setattr, store, "ROOT", self._root)
        self.addCleanup(qs_mod._set_profile, "jev68")
        # el M-D0 sintético de las pruebas no tiene puertas ni raw: la
        # mayoría de pasadas mockean la evaluabilidad (la costosa se
        # prueba aparte, test_d1_no_evaluable_*)
        self._eval_patcher = mock.patch.object(
            jc, "_md0_evaluable", return_value=(True, None))
        self._eval_mock = self._eval_patcher.start()
        self.addCleanup(self._eval_patcher.stop)

    def test_reserva_antes_de_abrir_y_persiste(self):
        times = [1000.0]
        b = jc.Budget(now=lambda: times[0])
        b.charge()
        b.charge()
        # persistido en disco: una segunda pasada hereda el gasto
        b2 = jc.Budget(now=lambda: times[0])
        self.assertEqual(b2.st["requests"], 2)
        self.assertEqual(b2.st["started_wall"], 1000.0)

    def test_cupo_800_no_se_amplia(self):
        b = jc.Budget(now=lambda: 0.0)
        b.st["requests"] = jc.CAP_REQUESTS
        b.st["started_wall"] = 0.0
        with self.assertRaises(jc.QuotaExhausted):
            b.charge()
        self.assertEqual(b.st["requests"], jc.CAP_REQUESTS)

    def test_deadline_wall_3h(self):
        t = [0.0]
        b = jc.Budget(now=lambda: t[0])
        b.charge()                      # nace el reloj wall
        t[0] = jc.WALL_S + 1
        self.assertEqual(b.deadline_remaining(), 0.0)
        with self.assertRaises(jc.DeadlineExceeded):
            b.charge()

    def test_contador_cuenta_intentos_no_decides(self):
        """El proxy reserva por cada urlopen — los reintentos internos
        del adaptador cuentan como intentos de red separados."""
        b = jc.Budget(now=lambda: 0.0)
        inner = _FakeReviewer(attempts=3)
        proxy = jc.CountingAdapter(inner, b, urlopen=lambda *a, **k: None)
        orig = urllib.request.urlopen
        proxy.decide("state", {"q": {"type": "noul"}})
        self.assertEqual(b.st["requests"], 3)
        self.assertIs(urllib.request.urlopen, orig)  # restaurado

    def test_quota_exhausted_no_tragable_por_except_exception(self):
        """La parada de cupo atraviesa el `except Exception` por caso de
        la cascada: no se convierte en un error de caso ni sigue la
        pasada."""
        b = jc.Budget(now=lambda: 0.0)
        b.st["requests"] = jc.CAP_REQUESTS
        b.st["started_wall"] = 0.0
        proxy = jc.CountingAdapter(_FakeReviewer(), b,
                                   urlopen=lambda *a, **k: None)
        try:
            proxy.decide("state", {"q": {"type": "noul"}})
        except Exception:
            self.fail("QuotaExhausted no debe ser un Exception de caso")
        except jc.QuotaExhausted:
            pass

    def test_run_cascada_completa_offline(self):
        """Pasada real sobre una fase pequeña con el revisor sintético:
        cuenta intentos, escribe raw/audit/review/avg y termina."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        n_cases = len(load_phase("adv1")[1])
        opened = [0]

        def fake_open(*a, **kw):
            opened[0] += 1
            return _FakeResponse()

        budget = jc.Budget(now=lambda: 0.0)
        _freeze(budget)
        reviewer = jc.CountingAdapter(_FakeReviewer(), budget,
                                      urlopen=fake_open)
        rc = jc.run(prefix="synth_rev", control="",
                    phases=["adv1"], budget=budget,
                    reviewer=reviewer, printer=lambda *a: None)
        self.assertEqual(rc, 0)
        self.assertEqual(opened[0], n_cases)      # un intento por caso
        self.assertEqual(budget.st["requests"], n_cases)
        for suffix in ("raw", "audit", "review", "avg"):
            self.assertTrue(store.runs_in(f"synth_rev_{suffix}"), suffix)
        audit = store.load("synth_rev_audit", "adv1")
        self.assertEqual(len(audit["cases"]), n_cases)

    def test_run_para_en_deadline_sin_abrir_red(self):
        """Con las 3 h wall agotadas la pasada ni empieza: cero
        aperturas de red y código de parada."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        t = [0.0]
        budget = jc.Budget(now=lambda: t[0])
        _freeze(budget)
        budget.charge()
        t[0] = jc.WALL_S + 60
        opened = [0]

        def fake_open(*a, **kw):
            opened[0] += 1
            return _FakeResponse()

        reviewer = jc.CountingAdapter(_FakeReviewer(), budget,
                                      urlopen=fake_open)
        rc = jc.run(d1=MD0_RUN, prefix="synth2_rev", control="",
                    phases=["adv1"], budget=budget, reviewer=reviewer,
                    printer=lambda *a: None)
        self.assertEqual(rc, 2)
        self.assertEqual(opened[0], 0)
        # la parada queda persistida en el registro durable
        self.assertEqual(budget.st["stopped"]["phase"], "adv1")

    def test_request_en_vuelo_acotada_por_deadline(self):
        """Sonda R36: una petición que se abre a 1 s del deadline no
        puede pasarlo — el socket recibe el remanente como timeout
        (nunca los 120 s internos del adaptador)."""
        t = [jc.WALL_S - 1]
        budget = jc.Budget(now=lambda: t[0])
        budget.st["started_wall"] = 0.0     # empezó hace WALL_S-1
        calls = []

        def fake_open(*a, **kw):
            calls.append(dict(kw))
            t[0] += 120           # la apertura "dura" más que el remanente
            return _FakeResponse()

        proxy = jc.CountingAdapter(_FakeReviewer(attempts=1), budget,
                                   urlopen=fake_open)
        proxy.decide("state", {"q": {"type": "noul"}})
        self.assertAlmostEqual(calls[0]["timeout"], 1.0, places=1)
        # y la siguiente petición ya ni se abre: deadline agotado
        with self.assertRaises(jc.DeadlineExceeded):
            proxy.decide("state", {"q": {"type": "noul"}})
        self.assertEqual(len(calls), 1)

    def test_espera_interna_acotada_por_deadline(self):
        """Los backoff/pause internos del adaptador también quedan
        acotados: un sleep más largo que el remanente duerme solo el
        remanente y tras él lanza DeadlineExceeded."""
        t = [jc.WALL_S - 1]
        budget = jc.Budget(now=lambda: t[0])
        budget.st["started_wall"] = 0.0
        slept = []

        def fake_sleep(s):
            slept.append(s)
            t[0] += s

        class Slow:
            def meta(self):
                return {}
            def decide(self, state, questions):
                urllib.request.urlopen("http://x", timeout=120)
                time.sleep(120)
                return {"answers": {}}

        proxy = jc.CountingAdapter(Slow(), budget,
                                   urlopen=lambda *a, **k: _FakeResponse(),
                                   sleep=fake_sleep)
        with self.assertRaises(jc.DeadlineExceeded):
            proxy.decide("state", {})
        self.assertAlmostEqual(slept[0], 1.0, places=1)

    def test_reloj_global_del_encargo_acota_la_cascada(self):
        """Sonda R36: la cascada corre dentro del reloj global de 40 h —
        agotado el global no se abre nada aunque queden 3 h propias."""
        # el encargo A6 arrancó hace 41 h: global agotado
        (self.tmp / "logs").mkdir(exist_ok=True)
        (self.tmp / "logs" / jc.JEV77_STATE_FILE).write_text(
            json.dumps({"wall_t0": time.time() - 41 * 3600}))
        budget = jc.Budget(global_remaining=jc._global_remaining)
        opened = [0]

        def fake_open(*a, **kw):
            opened[0] += 1
            return _FakeResponse()

        proxy = jc.CountingAdapter(_FakeReviewer(), budget,
                                   urlopen=fake_open)
        with self.assertRaises(jc.DeadlineExceeded):
            proxy.decide("state", {"q": {"type": "noul"}})
        self.assertEqual(opened[0], 0)
        self.assertEqual(budget.st["requests"], 0)

    def test_version_del_revisor_congelada(self):
        """La primera resolución del revisor se congela en el estado
        durable; una deriva posterior detiene la cascada y conserva lo
        revisado."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        budget = jc.Budget(now=lambda: 0.0)
        versions = ["jev-a"]

        class VR(_FakeReviewer):
            def meta(self):
                return {"provider": "openrouter",
                        "model": "~typesafe/jev-latest",
                        "resolved": versions[0]}

        _freeze(budget, VR().meta())
        proxy = jc.CountingAdapter(VR(), budget,
                                   urlopen=lambda *a, **k: _FakeResponse())
        rc = jc.run(prefix="ver_rev", control="",
                    phases=["adv1"], budget=budget, reviewer=proxy,
                    printer=lambda *a: None)
        self.assertEqual(rc, 0)
        self.assertEqual(budget.st["reviewer"]["resolved"], "jev-a")
        # una segunda pasada con otra versión para y no reutiliza
        versions[0] = "jev-b"
        budget2 = jc.Budget(now=lambda: 0.0)   # mismo fichero de estado
        proxy2 = jc.CountingAdapter(VR(), budget2,
                                    urlopen=lambda *a, **k: _FakeResponse())
        rc = jc.run(prefix="ver2_rev", control="",
                    phases=["adv1"], budget=budget2, reviewer=proxy2,
                    printer=lambda *a: None)
        self.assertEqual(rc, 2)
        self.assertIn("versión", budget2.st["stopped"]["reason"])

    def _run_offline(self, d1_arg=None, freeze=True, phases_list=None):
        """Pasada sintética de una fase: devuelve (rc, aperturas,
        budget) sin red real."""
        opened = [0]

        def fake_open(*a, **kw):
            opened[0] += 1
            return _FakeResponse()

        budget = jc.Budget(now=lambda: 0.0)
        if freeze:
            _freeze(budget)
        reviewer = jc.CountingAdapter(_FakeReviewer(), budget,
                                      urlopen=fake_open)
        kw = {} if d1_arg is None else {"d1": d1_arg}
        rc = jc.run(prefix="noe_rev", control="",
                    phases=phases_list or ["adv1"],
                    budget=budget, reviewer=reviewer,
                    printer=lambda *a: None, **kw)
        return rc, opened[0], budget

    def test_sin_estado_a6_no_abre_red(self):
        """R38 §3: sin fichero de estado del encargo la cascada no
        ejecuta — parada de configuración persistida, 0 peticiones."""
        _write_d1(MD0_RUN, "adv1")
        rc, opened, budget = self._run_offline(MD0_RUN)
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)
        self.assertEqual(budget.st["requests"], 0)
        self.assertIn("encargo", budget.st["stopped"]["reason"])

    def test_estado_corrupto_o_sin_wall_no_abre_red(self):
        """R38 §3: estado ilegible o sin wall_t0 — igual: 0 red."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        stfile = self.tmp / "logs" / jc.JEV77_STATE_FILE
        for bad in ("{no-json", json.dumps({"session": "s0"})):
            stfile.write_text(bad)
            rc, opened, budget = self._run_offline(MD0_RUN)
            self.assertEqual(rc, 1)
            self.assertEqual(opened, 0)
            self.assertEqual(budget.st["requests"], 0)

    def test_manifiesto_sin_politicas_coincidentes_no_abre_red(self):
        """R38 §5: las políticas efectivas del wrapper deben ser las
        congeladas en el manifiesto — una divergencia (o su ausencia)
        detiene la ejecución sin red."""
        _write_encargo(self.tmp, caps={"requests": 999,
                                       "wall_s": 36000,
                                       "raw": f"{jc.PREFIX_77}_raw",
                                       "audit": f"{jc.PREFIX_77}_audit"})
        _write_d1(MD0_RUN, "adv1")
        rc, opened, _b = self._run_offline(MD0_RUN)
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)
        # y sin políticas de cascada en el manifiesto, también
        (self.tmp / "logs" / jc.JEV77_MANIFEST_FILE).write_text(
            json.dumps({"manifest_sha256": "m77",
                        "cells": {"MD0": {"run": MD0_RUN}}}))
        rc, opened, _b = self._run_offline(MD0_RUN)
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)

    def test_d1_default_es_el_run_md0_del_manifiesto(self):
        """R38 §8: sin --d1 la cascada audita el run de la celda M-D0
        del manifiesto congelado — el que realmente genera el
        supervisor."""
        _write_encargo(self.tmp)
        n = _write_d1(MD0_RUN, "adv1")
        rc, opened, _b = self._run_offline()   # sin d1: default
        self.assertEqual(rc, 0)
        self.assertEqual(opened, n)
        raw = store.load("noe_rev_raw", "adv1")
        self.assertEqual(raw["meta"]["d1"], MD0_RUN)

    def test_d1_ausente_o_incompleto_no_abre_red(self):
        """R38 §8: M-D0 ausente o sin cobertura completa es error de
        configuración ANTES de abrir red — nunca una pasada con todos
        los casos en error."""
        _write_encargo(self.tmp)
        rc, opened, _b = self._run_offline()        # sin M-D0
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)
        # M-D0 incompleto (un caso sin answers) — tampoco
        _write_d1(MD0_RUN, "adv1")
        d = store.load(MD0_RUN, "adv1")
        d["cases"][next(iter(d["cases"]))] = {"error": "x"}
        store.save(MD0_RUN, "adv1", d)
        rc, opened, _b = self._run_offline()
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)

    def test_version_cambia_dentro_de_fase_para(self):
        """R38 §6: la versión del revisor se congela en la PRIMERA
        respuesta; un cambio en el segundo caso detiene la pasada,
        conserva lo revisado y persiste la evidencia de deriva."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")

        class Flip(_FakeReviewer):
            def meta(self):
                return {"provider": "openrouter",
                        "model": "~typesafe/jev-latest",
                        "resolved": ("jev-a" if self.calls <= 1
                                     else "jev-b")}

        budget = jc.Budget(now=lambda: 0.0)
        _freeze(budget, {"provider": "openrouter",
                         "model": "~typesafe/jev-latest",
                         "resolved": "jev-a"})
        proxy = jc.CountingAdapter(Flip(), budget,
                                   urlopen=lambda *a, **k: _FakeResponse())
        rc = jc.run(prefix="flip", phases=["adv1"],
                    budget=budget, reviewer=proxy,
                    printer=lambda *a: None)
        self.assertEqual(rc, 2)
        raw = store.load("flip_raw", "adv1")
        self.assertEqual(raw["meta"]["version_drift"],
                         {"frozen": "jev-a", "observed": "jev-b",
                          "case": raw["meta"]["version_drift"]["case"]})
        self.assertEqual(len(raw["cases"]), 1)  # solo el primer caso
        versions = {c.get("reviewer_version")
                    for c in raw["cases"].values()}
        self.assertEqual(versions, {"jev-a"})
        self.assertIn("versión", budget.st["stopped"]["reason"])
        # no se abrió la red del caso divergente… solo se consumió su
        # intento (la respuesta ya venía con otra versión)
        self.assertEqual(budget.st["requests"], 2)

    def test_manifiesto_alterado_sin_enmienda_no_abre_red(self):
        """Sonda R39 §1 (tampered_manifest_d1): contenido cambiado con
        el sha viejo → integridad rota, parada sin red."""
        _write_encargo(self.tmp,
                       mutate=lambda m: m["cells"]["MD0"].update(
                           run="foreign_d1"),
                       recompute=False)
        _write_d1("foreign_d1", "adv1")
        rc, opened, _b = self._run_offline("foreign_d1")
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)

    def test_manifiesto_distinto_del_plan_no_abre_red(self):
        """R39 §1: un manifiesto con sha consistente pero distinto del
        plan vigente (sin enmienda autorizada) tampoco autoriza."""
        _write_encargo(self.tmp,
                       mutate=lambda m: m["cells"]["MD0"].update(
                           budget_s=m["cells"]["MD0"]["budget_s"] + 1))
        _write_d1(MD0_RUN, "adv1")
        rc, opened, _b = self._run_offline()
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)

    def test_reanudacion_no_reetiqueta_manifiesto(self):
        """Sonda R39 §1 (resume_relabels): un raw previo con otro
        manifest_sha256 conserva su origen — la reanudación para sin
        reescribirlo ni reutilizar sus casos."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        rc, opened, _b = self._run_offline()
        self.assertEqual(rc, 0)
        rawrun = "noe_rev_raw"
        raw = store.load(rawrun, "adv1")
        raw["meta"]["manifest_sha256"] = "otro_encargo"
        store.save(rawrun, "adv1", raw)
        rc, opened2, b2 = self._run_offline()
        self.assertEqual(rc, 2)
        self.assertEqual(opened2, 0)
        self.assertEqual(store.load(rawrun, "adv1")["meta"]
                         ["manifest_sha256"], "otro_encargo")
        self.assertIn("manifiesto", b2.st["stopped"]["reason"])

    def test_sin_resolucion_a4_no_abre_red(self):
        """Sonda R39 §2 (without_frozen_a4): sin la versión congelada
        por el paso A4 no se abre la red de evaluación."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        rc, opened, budget = self._run_offline(freeze=False)
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)
        self.assertIn("A4", budget.st["stopped"]["reason"])

    def test_identidad_revisor_incompatible_no_abre_red(self):
        """R39 §2: un revisor congelado que no coincide con el
        contrato del manifiesto (proveedor distinto) detiene sin red."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        budget = jc.Budget(now=lambda: 0.0)
        _freeze(budget, {"provider": "typesafe", "model": "jev-latest",
                         "resolved": "jev-a"})     # ajena al contrato
        proxy = jc.CountingAdapter(_FakeReviewer(), budget,
                                   urlopen=lambda *a, **k: _FakeResponse())
        rc = jc.run(prefix="id_rev", phases=["adv1"], budget=budget,
                    reviewer=proxy, printer=lambda *a: None)
        self.assertEqual(rc, 1)
        self.assertIn("revisor", budget.st["stopped"]["reason"])

    def test_d1_explicito_ajeno_no_abre_red(self):
        """Sonda R39 §4 (explicit_foreign_d1): un run completo que no
        es la celda M-D0 congelada se rechaza antes de abrir red."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        _write_d1("foreign_d1", "adv1")
        rc, opened, _b = self._run_offline("foreign_d1")
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)

    def test_d1_no_evaluable_no_abre_red(self):
        """R39 §4: tener `answers` no basta — la celda M-D0 debe ser
        evaluable según la auditoría del supervisor."""
        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")      # answers sin puertas ni raw
        self._eval_mock.return_value = (False, "sin puertas acreditadas")
        rc, opened, _b = self._run_offline()
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)
        # y la comprobación real sobre el sintético también dice no
        self._eval_patcher.stop()
        ok, note = jc._md0_evaluable(MD0_RUN, ["adv1"])
        self.assertFalse(ok)

    def test_freeze_persiste_identidad_del_revisor(self):
        """El paso A4 (`freeze_reviewer`) persiste proveedor/modelo/
        versión resuelta en el presupuesto durable."""
        budget = jc.Budget(now=lambda: 0.0)
        rc = jc.freeze_reviewer(reviewer=_FakeReviewer(), budget=budget,
                                printer=lambda *a: None)
        self.assertEqual(rc, 0)
        rv = jc.Budget(now=lambda: 0.0).st["reviewer"]
        self.assertEqual(rv["provider"], "openrouter")
        self.assertEqual(rv["model"], "~typesafe/jev-latest")
        self.assertEqual(rv["resolved"], "jev-test")
        self.assertEqual(rv["adapter"], "jev")

    def test_freeze_y_run_con_adaptador_jev_real(self):
        """Sonda R40 §1 (real_default_openrouter): freeze→run con el
        adaptador Jev REAL por defecto (OpenRouter, modelo efectivo
        ~typesafe/jev-latest) y TODO el transporte simulado — el
        contrato acepta la identidad real del proveedor."""
        from jevbench.adapters.jev import Jev
        from jevbench.cascade import review_questions

        _write_encargo(self.tmp)
        _write_d1(MD0_RUN, "adv1")
        calls = []
        # respuesta simulada: answers válidas para todas las preguntas
        # de revisión de adv1 (y la sonda A4)
        answers = {"a4_probe": {"noul": 0.9}}
        for qid, q in review_questions(load_phase("adv1")[0],
                                       "adv1").items():
            if q["type"] == "noul":
                answers[qid] = {"noul": 0.9}
            elif q["type"] == "choice":
                crit = list(q["criteria"])
                answers[qid] = {"choice": crit[0],
                                "probabilities": {
                                    k: (1.0 if k == crit[0] else 0.0)
                                    for k in crit}}
            else:
                answers[qid] = {"score": 1.0,
                                "probabilities": {"0": 1.0}}

        class R(_FakeResponse):
            def read(self):
                return json.dumps({"answers": answers, "usage": {},
                                   "model": "jev-1.14-sim"}).encode()

        # clave ficticia: el transporte está simulado y el test no debe
        # depender de .env (falla en un checkout limpio o en el espejo público)
        with mock.patch.object(urllib.request, "urlopen",
                               lambda *a, **k: (calls.append(k),
                                                R())[1]), \
                mock.patch.dict("os.environ",
                                {"OPENROUTER_API_KEY": "test-key-ficticia"}), \
                mock.patch("jevbench.adapters.jev.load_env", lambda: None):
            jev = Jev(provider="openrouter")   # constructor real
            self.assertEqual(jev.meta()["model"], "~typesafe/jev-latest")
            budget = jc.Budget(now=lambda: 0.0)
            rc = jc.freeze_reviewer(reviewer=jev, budget=budget,
                                    printer=lambda *a: None)
            self.assertEqual(rc, 0)
            rv = budget.st["reviewer"]
            self.assertEqual(rv["model"], "~typesafe/jev-latest")
            self.assertEqual(rv["resolved"], "jev-1.14-sim")
            proxy = jc.CountingAdapter(jev, budget,
                                       urlopen=lambda *a, **k:
                                       (calls.append(k), R())[1])
            n_cases = len(load_phase("adv1")[1])
            rc = jc.run(prefix="real_rev", phases=["adv1"],
                        budget=budget, reviewer=proxy,
                        printer=lambda *a: None)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1 + n_cases)   # sondeo + casos

    def test_md0_del_manifiesto_vigente_y_ajeno(self):
        """Sonda R40 §3 (d1_provenance): M-D0 evaluable ligado al
        manifiesto vigente pasa; el MISMO run internamente válido bajo
        otro manifiesto se rechaza (rc1, 0 aperturas)."""
        try:
            from test_qwen_session import TestJEV77Analysis
        except ImportError:
            from tests.test_qwen_session import TestJEV77Analysis
        man = _write_encargo(self.tmp)
        sha = man["manifest_sha256"]
        self._eval_patcher.stop()   # la comprobación real, sin mock
        # celda M-D0 con evidencia completa (refs + puerta + raw),
        # atribuida al manifiesto vigente
        cell = {**qs_mod.CELLS_77["MD0"], "phases": ["triage_es"]}
        TestJEV77Analysis._write_cell(
            TestJEV77Analysis.__new__(TestJEV77Analysis), cell, hit=True)
        doc = store.load(MD0_RUN, "triage_es")
        doc["meta"].setdefault("diag", {})["manifest_sha256"] = sha
        for rec in doc["cases"].values():
            rec["manifest_sha256"] = sha
        store.save(MD0_RUN, "triage_es", doc)
        ok, note = jc._md0_evaluable(MD0_RUN, ["triage_es"], man)
        self.assertTrue(ok, note)
        # mismo contenido evaluable pero ligado a OTRO manifiesto
        foreign = "a7c737af1667fead"
        doc["meta"]["diag"]["manifest_sha256"] = foreign
        for rec in doc["cases"].values():
            rec["manifest_sha256"] = foreign
        store.save(MD0_RUN, "triage_es", doc)
        ok, note = jc._md0_evaluable(MD0_RUN, ["triage_es"], man)
        self.assertFalse(ok)
        self.assertIn("procedencia", note)
        # y por la vía del wrapper
        rc, opened, _b = self._run_offline(phases_list=["triage_es"])
        self.assertEqual(rc, 1)
        self.assertEqual(opened, 0)


if __name__ == "__main__":
    unittest.main()


class A4ProbeWireFormat(unittest.TestCase):
    """El sondeo A4 usa el formato wire de las preguntas noul del banco
    (la API de Jev rechazó con 400 una pregunta sin `instructions`)."""

    def test_probe_como_noul_de_bateria(self):
        from jevbench.battery import TRIAGE_QS
        from jevbench.jev77_cascade import A4_PROBE_QS
        q = A4_PROBE_QS["a4_probe"]
        ref = TRIAGE_QS["clinical"]
        self.assertEqual(set(q), set(ref))
        self.assertEqual(q["type"], "noul")
        self.assertIsInstance(q["instructions"], str)
        self.assertTrue(q["instructions"])
