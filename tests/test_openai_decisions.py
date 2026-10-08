"""Tests offline del adaptador `openai_decisions` (JEV-78) — el SDK oficial
(openai==3.26.0) se sustituye por un cliente falso que reproduce la superficie
`client.decisions.with_raw_response.create(...) -> raw{headers, parse()}` con
`parse().model_dump()` devolviendo payloads del formato nativo (/v1/decisions):
respuestas válidas, refusal parcial y total, errores SDK y formas inválidas.
Sin red externa ni claves reales (OPENAI_API_KEY se fija a un valor de
prueba) y sin el SDK instalado — el adaptador lo importa perezoso solo al
crear el cliente real."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench.battery import OOD_QS, TRIAGE_QS
from jevbench.rotation import NAMED_ORDERS

os.environ.setdefault("OPENAI_API_KEY", "test-key")

CANNED = {"model": "gpt-6-luna-20261006",
          "answers": [
              {"type": "choice", "name": "department", "choice": "admin",
               "probabilities": [
                   {"value": "bronchoscopia", "probability": 0.05},
                   {"value": "consulta_externa", "probability": 0.03},
                   {"value": "urgencias", "probability": 0.02},
                   {"value": "admin", "probability": 0.9}],
               "confidence": 0.9},
              {"type": "score", "name": "urgency", "score": 1.2,
               "probabilities": [
                   {"value": 0, "label": "bajo", "probability": 0.2},
                   {"value": 1, "label": "medio", "probability": 0.6},
                   {"value": 2, "label": "critico", "probability": 0.2}],
               "confidence": 0.6},
              {"type": "predicate", "name": "clinical", "probability": 0.8},
              {"type": "predicate", "name": "hostile", "probability": 0.0},
              {"type": "predicate", "name": "same_day", "probability": 0.1}],
          "usage": {"input_tokens": 900, "output_tokens": 0}}

CANNED_OOD = {"model": "gpt-6-luna",
              "answers": [
                  {"type": "score", "name": "relevance", "score": 0.1,
                   "probabilities": [
                       {"value": 0, "label": "low", "probability": 0.9},
                       {"value": 1, "label": "medium", "probability": 0.08},
                       {"value": 2, "label": "high", "probability": 0.02}],
                   "confidence": 0.9},
                  {"type": "choice", "name": "domain", "choice": "other",
                   "probabilities": [
                       {"value": "ip", "probability": 0.01},
                       {"value": "oncology", "probability": 0.01},
                       {"value": "pulm_general", "probability": 0.03},
                       {"value": "other", "probability": 0.95}],
                   "confidence": 0.95},
                  {"type": "predicate", "name": "clinical",
                   "probability": 0.05}],
              "usage": {"input_tokens": 520, "output_tokens": 0}}


class _FakeResp:
    """Decision parseada: superficie pydantic mínima (model_dump)."""

    def __init__(self, payload):
        self._p = payload

    def model_dump(self):
        return self._p


class _FakeRaw:
    """Respuesta cruda del SDK (with_raw_response): headers + parse()."""

    def __init__(self, payload, headers=None):
        self._p = payload
        self.headers = {"openai-model": "gpt-6-luna-20261006",
                        **(headers or {})}

    def parse(self):
        return _FakeResp(self._p)


class _FakeDecisions:
    """client.decisions: cada llamada a create() consume la cola de
    payloads; el último se repite si la cola se agota. Una excepción en la
    cola se lanza tal cual (error SDK simulado)."""

    def __init__(self, payloads):
        self.with_raw_response = self
        self.calls = []
        self._queue = list(payloads)

    def create(self, **kw):
        self.calls.append(kw)
        item = (self._queue.pop(0) if len(self._queue) > 1
                else self._queue[0])
        if isinstance(item, Exception):
            raise item
        return _FakeRaw(item)


class FakeClient:
    """Sustituto de openai.OpenAI: solo la superficie decisions."""

    def __init__(self, payloads):
        if not isinstance(payloads, list):
            payloads = [payloads]
        self.decisions = _FakeDecisions(payloads)


def _sdk_error(name, status=None, msg="boom"):
    """Excepción con la superficie duck-typed que el adaptador reconoce:
    nombre de clase del SDK y .status_code para APIStatusError."""
    e = type(name, (Exception,), {})(msg)
    if status is not None:
        e.status_code = status
    return e


def _adapter(client, **opts):
    from jevbench.adapters.openai_decisions import OpenAIDecisions
    opts.setdefault("retries", 1)
    return OpenAIDecisions(model="gpt-6-luna", pause=0,
                           _client=client, **opts)


def _wire(answers, questions=None):
    from jevbench.adapters.openai_decisions import wire_answers
    return wire_answers(answers, OOD_QS if questions is None else questions)


def _rec_of(exc):
    """El registro que jevbench.run guardaría para esta excepción."""
    rec = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    diag = getattr(exc, "diag", None)
    if isinstance(diag, dict) and diag:
        rec["diag"] = diag
    cost = getattr(exc, "cost", None)
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        rec["cost"] = cost
    return rec


def _run_main(client, *argv_extra):
    """jevbench.run real sobre un run efímero con el cliente falso —
    reproduce la cadena excepción -> registro guardado -> clasificador."""
    from jevbench import run, store
    from jevbench.adapters import openai_decisions as oa

    tmp = Path(tempfile.mkdtemp(prefix="jev78test_"))
    argv = ["run", "openai_decisions", "--run", "t78", *argv_extra]
    factory = lambda **o: oa.OpenAIDecisions(pause=0, _client=client, **o)
    patches = [
        mock.patch.object(store, "ROOT", tmp),
        mock.patch.object(oa, "load_env"),
        mock.patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}),
        mock.patch.object(oa.time, "sleep"),
        mock.patch.object(run, "git_rev", return_value="offline"),
        mock.patch.object(run, "git_dirty", return_value=None),
        mock.patch.object(sys, "argv", argv),
        mock.patch.object(run.adapters, "get",
                          return_value=factory),
    ]
    import contextlib, io
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        run.main()
        # store.ROOT sigue parcheado: cargar el doc ANTES de salir del
        # contexto o se leería el results/ real
        doc = store.load("t78", argv_extra[argv_extra.index("--phases") + 1]
                         .split(",")[-1] if "--phases" in argv_extra else "ood")
    return doc, tmp


class TestMapping(unittest.TestCase):
    """Cuerpo enviado: state -> input, preguntas -> predicate/choice/score."""

    def test_mapeo_preguntas(self):
        from jevbench.adapters.openai_decisions import api_questions
        api = {q["name"]: q for q in api_questions(TRIAGE_QS)}
        dept = api["department"]
        self.assertEqual(dept["type"], "choice")
        self.assertEqual(dept["instructions"],
                         TRIAGE_QS["department"]["instructions"])
        self.assertEqual([c["value"] for c in dept["choices"]],
                         list(TRIAGE_QS["department"]["criteria"]))
        for c in dept["choices"]:
            self.assertEqual(c["description"],
                             TRIAGE_QS["department"]["criteria"][c["value"]])
        urg = api["urgency"]
        self.assertEqual(urg["type"], "score")
        self.assertEqual([(l["label"], l["description"]) for l in urg["levels"]],
                         [("bajo", "routine, no deadline"),
                          ("medio", "should be handled soon"),
                          ("critico", "deadline, blocking, or safety issue")])
        for qid in ("clinical", "hostile", "same_day"):
            self.assertEqual(api[qid]["type"], "predicate")
            self.assertEqual(api[qid]["instructions"],
                             TRIAGE_QS[qid]["instructions"])

    def test_input_es_el_state(self):
        client = FakeClient(CANNED)
        _adapter(client).decide("Factura duplicada.", TRIAGE_QS)
        sent = client.decisions.calls[0]
        self.assertEqual(sent["input"], "Factura duplicada.")
        self.assertEqual(sent["model"], "gpt-6-luna")
        self.assertEqual(len(sent["questions"]), len(TRIAGE_QS))


class TestNormalization(unittest.TestCase):
    def test_respuesta_a_formato_wire(self):
        client = FakeClient(CANNED)
        out = _adapter(client).decide("Factura duplicada.", TRIAGE_QS)
        ans = out["answers"]
        dept = ans["department"]
        self.assertEqual(dept["type"], "choice")
        self.assertEqual(dept["choice"], "admin")
        self.assertEqual(dept["probabilities"]["admin"], 0.9)
        self.assertEqual(set(dept["probabilities"]),
                         set(TRIAGE_QS["department"]["criteria"]))
        self.assertEqual(dept["confidence"], 0.9)
        urg = ans["urgency"]
        self.assertEqual(urg["type"], "score")
        self.assertEqual(urg["score"], 1.2)
        self.assertEqual(urg["probabilities"], {"0": 0.2, "1": 0.6, "2": 0.2})
        self.assertEqual(urg["legend"],
                         {str(i): c for i, c in
                          enumerate(TRIAGE_QS["urgency"]["criteria"])})
        self.assertEqual(ans["clinical"], {"type": "noul", "noul": 0.8})
        self.assertEqual(ans["hostile"], {"type": "noul", "noul": 0.0})

    def test_modelo_y_cabeceras_registrados(self):
        client = FakeClient(CANNED)
        a = _adapter(client)
        out = a.decide("Factura duplicada.", TRIAGE_QS)
        self.assertEqual(out["model"], "gpt-6-luna-20261006")
        self.assertEqual(a.meta()["resolved"], "gpt-6-luna-20261006")
        self.assertEqual(a.meta()["api_headers"].get("openai-model"),
                         "gpt-6-luna-20261006")

    def test_coste_por_tokens_de_entrada(self):
        client = FakeClient(CANNED)
        out = _adapter(client).decide("Factura duplicada.", TRIAGE_QS)
        self.assertAlmostEqual(out["cost"], 900 * 0.10 / 1e6)

    def test_coste_directo_del_usage(self):
        payload = dict(CANNED)
        payload["usage"] = {"input_tokens": 900, "cost": 0.000123}
        out = _adapter(FakeClient(payload)).decide("x", TRIAGE_QS)
        self.assertEqual(out["cost"], 0.000123)


class TestRefusal(unittest.TestCase):
    """Refusal POR PREGUNTA (semántica nativa): parcial se conserva marcado,
    total es ProviderRefusal (rejection)."""

    def _partial(self, qid="department"):
        payload = json.loads(json.dumps(CANNED))
        payload["answers"] = [
            {"type": "refusal", "name": qid},
            *[a for a in payload["answers"] if a["name"] != qid]]
        return payload

    def test_refusal_parcial_marca_la_pregunta(self):
        """Una sola pregunta rechazada: el caso se conserva, la pregunta
        queda {"type": "refusal"} y el registro la lista en `refusals`."""
        client = FakeClient(self._partial())
        out = _adapter(client).decide("x", TRIAGE_QS)
        self.assertEqual(out["answers"]["department"], {"type": "refusal"})
        self.assertEqual(out["refusals"], ["department"])
        self.assertEqual(out["answers"]["clinical"]["noul"], 0.8)
        self.assertNotIn("error", out)

    def test_refusal_parcial_reintenta_y_puede_limpiarse(self):
        """La negativa comparte el presupuesto de reintentos (JEV-80):
        un 2º intento limpio da el caso completo; el coste se acumula."""
        client = FakeClient([self._partial(), dict(CANNED)])
        out = _adapter(client, retries=3).decide("x", TRIAGE_QS)
        self.assertNotIn("refusals", out)
        self.assertEqual(out["answers"]["department"]["choice"], "admin")
        self.assertEqual(len(client.decisions.calls), 2)
        self.assertAlmostEqual(out["cost"], 2 * 900 * 0.10 / 1e6)

    def test_refusal_parcial_persistente_se_conserva(self):
        """Si agota los reintentos con negativas parciales, el último
        intento se conserva marcado (no hay excepción)."""
        client = FakeClient(self._partial())
        out = _adapter(client, retries=3).decide("x", TRIAGE_QS)
        self.assertEqual(out["refusals"], ["department"])
        self.assertEqual(len(client.decisions.calls), 3)

    def test_refusal_total_es_rejection(self):
        """Todas las preguntas rechazadas = negativa del caso entero:
        ProviderRefusal con el patrón «refused to answer», diag con los
        nombres y coste informado acumulado de los intentos."""
        from jevbench.adapters.openai_decisions import ProviderRefusal
        payload = {"model": "gpt-6-luna",
                   "answers": [{"type": "refusal", "name": n}
                               for n in OOD_QS],
                   "usage": {"input_tokens": 200000, "cost": 0.02}}
        client = FakeClient(payload)
        with self.assertRaises(ProviderRefusal) as cm:
            _adapter(client, retries=3).decide("x", OOD_QS)
        e = cm.exception
        err = f"{type(e).__name__}: {e}"
        self.assertIn("refused to answer", err)
        self.assertIn('"clinical"', err)
        self.assertEqual(e.diag, {"refusal": list(OOD_QS)})
        self.assertAlmostEqual(e.cost, 3 * 0.02)   # 3 intentos, coste de cada uno
        self.assertEqual(len(client.decisions.calls), 3)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(e)), "rejection")

    def test_cadena_excepcion_registro_clasificador(self):
        """Excepción -> registro guardado por jevbench.run -> clasificador
        JEV-78: el rechazo total persiste como error `rejection` y la
        negativa parcial como registro sin error con `refusals`."""
        from jevbench import jev78, store
        total = {"model": "gpt-6-luna",
                 "answers": [{"type": "refusal", "name": n} for n in OOD_QS],
                 "usage": {"input_tokens": 200000, "cost": 0.02}}
        doc, tmp = _run_main(FakeClient(total), "--phases", "ood",
                             "--opt", "retries=3")
        try:
            recs = doc["cases"]
            self.assertEqual(len(recs), 3)          # los 3 casos OOD
            for rec in recs.values():
                self.assertTrue(rec["error"].startswith("ProviderRefusal:"))
                self.assertEqual(jev78.error_kind(rec), "rejection")
                self.assertAlmostEqual(rec["cost"], 3 * 0.02)
        finally:
            shutil.rmtree(tmp)

    def test_registro_parcial_guardado_no_es_error(self):
        doc, tmp = _run_main(FakeClient(
            {"model": "gpt-6-luna",
             "answers": [{"type": "refusal", "name": "clinical"},
                         *[{"type": a["type"],
                            "name": a["name"],
                            **({"probability": 0.5} if a["type"] == "predicate"
                               else {"score": 0.0, "probabilities": [
                                     {"value": 0, "probability": 1.0},
                                     {"value": 1, "probability": 0.0},
                                     {"value": 2, "probability": 0.0}]}
                               if a["type"] == "score" else
                               {"choice": "other", "probabilities": [
                                   {"value": v, "probability": 1.0 if v == "other" else 0.0}
                                   for v in ("ip", "oncology", "pulm_general", "other")]})
                            } for a in CANNED_OOD["answers"] if a["name"] != "clinical"]],
             "usage": {"input_tokens": 100}}), "--phases", "ood")
        try:
            rec = next(iter(doc["cases"].values()))
            self.assertNotIn("error", rec)
            self.assertEqual(rec["refusals"], ["clinical"])
            self.assertEqual(rec["answers"]["clinical"], {"type": "refusal"})
            from jevbench import jev78
            self.assertIsNone(jev78.error_kind(rec))
            self.assertEqual(jev78.answer_states(rec, OOD_QS)["clinical"],
                             "refused")
        finally:
            shutil.rmtree(tmp)


class TestContractValidation(unittest.TestCase):
    """R58 §3: las formas inválidas son error local de contrato
    (ContractError -> `local`), nunca un vector parcial ni un éxito fuera
    de contrato."""

    def _bad(self, answers, questions=None):
        with self.assertRaises(ValueError) as cm:
            _wire(answers, questions)
        self.assertIn("contract", str(cm.exception).lower())
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(cm.exception)), "local")

    def test_choice_vector_incompleto(self):
        """probabilities vacías o con una sola etiqueta: vector parcial."""
        for probs in ([], [{"value": "admin", "probability": 1.0}]):
            self._bad([{"type": "choice", "name": "domain",
                        "choice": "other", "probabilities": probs},
                       {"type": "score", "name": "relevance", "score": 0.0,
                        "probabilities": [{"value": i, "probability": 1.0 if i == 0 else 0.0}
                                          for i in range(3)]},
                       {"type": "predicate", "name": "clinical",
                        "probability": 0.5}])

    def test_choice_ajeno_a_criterios(self):
        self._bad([{"type": "choice", "name": "domain",
                    "choice": "alien_label",
                    "probabilities": [{"value": v, "probability": 0.25}
                                      for v in ("ip", "oncology",
                                                "pulm_general", "other")]},
                   {"type": "score", "name": "relevance", "score": 0.0,
                    "probabilities": [{"value": i, "probability": 1.0 if i == 0 else 0.0}
                                      for i in range(3)]},
                   {"type": "predicate", "name": "clinical",
                    "probability": 0.5}])

    def test_score_nivel_extra(self):
        self._bad([{"type": "score", "name": "relevance", "score": 0.0,
                    "probabilities": [{"value": i, "probability": 0.25}
                                      for i in range(4)]},   # ¡nivel 9/3!
                   {"type": "choice", "name": "domain", "choice": "other",
                    "probabilities": [{"value": v, "probability": 0.25}
                                      for v in ("ip", "oncology",
                                                "pulm_general", "other")]},
                   {"type": "predicate", "name": "clinical",
                    "probability": 0.5}])

    def test_predicate_fuera_de_rango(self):
        self._bad([{"type": "predicate", "name": "clinical",
                    "probability": 1.5},
                   {"type": "score", "name": "relevance", "score": 0.0,
                    "probabilities": [{"value": i, "probability": 1.0 if i == 0 else 0.0}
                                      for i in range(3)]},
                   {"type": "choice", "name": "domain", "choice": "other",
                    "probabilities": [{"value": v, "probability": 0.25}
                                      for v in ("ip", "oncology",
                                                "pulm_general", "other")]}])

    def test_nombre_duplicado(self):
        dup = {"type": "predicate", "name": "clinical", "probability": 0.5}
        self._bad([dup, dict(dup),
                   {"type": "score", "name": "relevance", "score": 0.0,
                    "probabilities": [{"value": i, "probability": 1.0 if i == 0 else 0.0}
                                      for i in range(3)]},
                   {"type": "choice", "name": "domain", "choice": "other",
                    "probabilities": [{"value": v, "probability": 0.25}
                                      for v in ("ip", "oncology",
                                                "pulm_general", "other")]}])

    def test_pregunta_ausente_y_tipo_cambiado(self):
        with self.assertRaises(ValueError) as cm:
            _wire([{"type": "predicate", "name": "clinical",
                    "probability": 0.8}])
        self.assertIn("contract", str(cm.exception).lower())
        with self.assertRaises(ValueError):
            _wire([{"type": "choice", "name": "clinical", "choice": "x",
                    "probabilities": [{"value": "x", "probability": 1.0}]}],
                  {"clinical": OOD_QS["clinical"]})


class TestSDKErrors(unittest.TestCase):
    """Política fija de reintentos: 429/5xx y conexión/timeout se
    reintentan dentro del presupuesto; 4xx no reintentable falla rápido."""

    def test_5xx_reintenta_y_acaba_transport(self):
        client = FakeClient(_sdk_error("InternalServerError", 500))
        a = _adapter(client, retries=3)
        with self.assertRaises(RuntimeError) as cm:
            a.decide("x", OOD_QS)
        self.assertIn("HTTP Error 500", str(cm.exception))
        self.assertEqual(len(client.decisions.calls), 3)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(cm.exception)),
                         "transport")

    def test_429_reintenta(self):
        client = FakeClient([_sdk_error("RateLimitError", 429), dict(CANNED_OOD)])
        out = _adapter(client, retries=3).decide("x", OOD_QS)
        self.assertEqual(out["answers"]["clinical"]["noul"], 0.05)
        self.assertEqual(len(client.decisions.calls), 2)

    def test_4xx_no_reintenta(self):
        client = FakeClient(_sdk_error("BadRequestError", 400))
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client, retries=3).decide("x", OOD_QS)
        self.assertIn("HTTP Error 400", str(cm.exception))
        self.assertEqual(len(client.decisions.calls), 1)

    def test_conexion_reintenta(self):
        client = FakeClient(_sdk_error("APIConnectionError",
                                       msg="connection reset"))
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client, retries=2).decide("x", OOD_QS)
        self.assertIn("APIConnectionError", str(cm.exception))
        self.assertEqual(len(client.decisions.calls), 2)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(cm.exception)),
                         "transport")

    def test_timeout_clasifica_timeout(self):
        client = FakeClient(_sdk_error("APITimeoutError", msg="timed out"))
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client).decide("x", OOD_QS)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(cm.exception)), "timeout")


class TestCostGuardRefusal(unittest.TestCase):
    """R58 §4: el coste informado de intentos rechazados se registra y
    alimenta el acumulado durable de la guarda — también entre
    invocaciones. Réplica de R58_refusal_cost.py."""

    TOTAL_REFUSAL = {"model": "gpt-6-luna",
                     "answers": [{"type": "refusal", "name": n}
                                 for n in OOD_QS],
                     "usage": {"input_tokens": 200000, "cost": 0.02}}

    def test_repro_r58_refusal_cost_para(self):
        """3 casos OOD, retries=3, refusal con usage.cost=$0,02 por intento:
        cada decide gasta $0,06 -> el primero ya supera ambos topes y la
        guarda para (antes: 9 respuestas pagadas y ningún coste registrado)."""
        doc, tmp = _run_main(FakeClient(self.TOTAL_REFUSAL),
                             "--phases", "ood", "--opt", "retries=3",
                             "--max-case-cost", "0.01", "--max-cost", "0.05")
        try:
            self.assertEqual(len(doc["cases"]), 1)
            rec = next(iter(doc["cases"].values()))
            self.assertAlmostEqual(rec["cost"], 0.06)
            self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")
        finally:
            shutil.rmtree(tmp)

    def test_presupuesto_entre_invocaciones(self):
        """El acumulado durable incluye el coste de registros con error de
        invocaciones anteriores: una segunda invocación para antes de abrir
        peticiones si el tope ya está superado."""
        cheap = dict(self.TOTAL_REFUSAL)
        cheap["usage"] = {"input_tokens": 1, "cost": 0.03}
        doc, tmp = _run_main(FakeClient(cheap), "--phases", "ood",
                             "--opt", "retries=2", "--limit", "1",
                             "--max-cost", "0.05")
        self.assertEqual(len(doc["cases"]), 1)      # $0,06 registrados
        # segunda invocación sobre el MISMO run en el mismo tmp
        from jevbench import run, store
        from jevbench.adapters import openai_decisions as oa
        import contextlib, io
        client = FakeClient(self.TOTAL_REFUSAL)
        factory = lambda **o: oa.OpenAIDecisions(pause=0, _client=client, **o)
        with mock.patch.object(store, "ROOT", tmp), \
             mock.patch.object(oa, "load_env"), \
             mock.patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}), \
             mock.patch.object(oa.time, "sleep"), \
             mock.patch.object(run, "git_rev", return_value="offline"), \
             mock.patch.object(run, "git_dirty", return_value=None), \
             mock.patch.object(sys, "argv",
                               ["run", "openai_decisions", "--run", "t78",
                                "--phases", "ood", "--max-cost", "0.05"]), \
             mock.patch.object(run.adapters, "get", return_value=factory), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            run.main()
            # dentro del parche de store.ROOT: fuera se leería results/ real
            doc = store.load("t78", "ood")
        try:
            self.assertEqual(len(client.decisions.calls), 0)   # 0 peticiones
            stop = doc["meta"]["cost_stop"]
            self.assertEqual(stop["reason"], "accumulated_cost")
            self.assertTrue(stop["before_requests"])
            self.assertAlmostEqual(stop["accumulated"], 0.06)
        finally:
            shutil.rmtree(tmp)


class TestTerminalCost(unittest.TestCase):
    """R58c §1: el gasto informado acumulado del decide viaja en `e.cost`
    con CUALQUIER desenlace terminal (timeout, HTTP 4xx, ContractError) —
    la clase/clasificación del error no cambia y lo no informado sigue
    desconocido. Réplica de R58c_refusal_cost.py."""

    PAID_REFUSAL = {"model": "gpt-6-luna",
                    "answers": [{"type": "refusal", "name": n}
                                for n in OOD_QS],
                    "usage": {"input_tokens": 200000, "cost": 0.02}}

    def test_negativa_pagada_luego_timeout(self):
        """Negativa total pagada ($0,02, reintenta) → timeout terminal:
        la excepción sigue clasificando `timeout` y conserva el gasto."""
        client = FakeClient([dict(self.PAID_REFUSAL),
                             _sdk_error("APITimeoutError", msg="timed out")])
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client, retries=3).decide("x", OOD_QS)
        e = cm.exception
        self.assertEqual(len(client.decisions.calls), 3)  # refusal+2 timeouts
        self.assertIn("APITimeoutError", str(e))
        self.assertAlmostEqual(e.cost, 0.02)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(e)), "timeout")

    def test_negativa_pagada_luego_400(self):
        """Negativa total pagada → HTTP 400 (no reintentable, terminal):
        RuntimeError con el gasto informado de la negativa."""
        client = FakeClient([dict(self.PAID_REFUSAL),
                             _sdk_error("BadRequestError", 400)])
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client, retries=3).decide("x", OOD_QS)
        e = cm.exception
        self.assertEqual(len(client.decisions.calls), 2)
        self.assertIn("HTTP Error 400", str(e))
        self.assertAlmostEqual(e.cost, 0.02)
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(_rec_of(e)), "transport")

    def test_respuesta_pagada_luego_contract_error(self):
        """Respuesta pagada que fracasa en la validación local:
        ContractError con `cost` — un error `local` no pierde lo gastado."""
        from jevbench import jev78
        from jevbench.adapters.openai_decisions import ContractError
        bad = json.loads(json.dumps(CANNED_OOD))
        bad["answers"][0]["score"] = 9          # fuera de rango [0, 2]
        bad["usage"] = {"input_tokens": 200000, "cost": 0.02}
        with self.assertRaises(ContractError) as cm:
            _adapter(FakeClient(bad)).decide("x", OOD_QS)
        e = cm.exception
        self.assertAlmostEqual(e.cost, 0.02)
        self.assertEqual(jev78.error_kind(_rec_of(e)), "local")

    def test_error_terminal_sin_informar_desconocido(self):
        """Sin usage informado el coste sigue desconocido (None), aunque
        el desenlace sea terminal."""
        p = json.loads(json.dumps(self.PAID_REFUSAL))
        p["usage"] = {}
        client = FakeClient([p, _sdk_error("APITimeoutError",
                                           msg="timed out")])
        with self.assertRaises(RuntimeError) as cm:
            _adapter(client, retries=2).decide("x", OOD_QS)
        self.assertIsNone(cm.exception.cost)

    def test_cadena_terminal_registro_para_la_guarda(self):
        """Excepción terminal -> registro con coste -> parada de guarda:
        negativa pagada + timeouts = $0,02 por caso > tope $0,01 -> 1
        registro y 0 peticiones extra (antes: 3 registros sin coste)."""
        client = FakeClient([dict(self.PAID_REFUSAL),
                             _sdk_error("APITimeoutError", msg="timed out")])
        doc, tmp = _run_main(client, "--phases", "ood", "--opt", "retries=3",
                             "--max-case-cost", "0.01", "--max-cost", "0.05")
        try:
            self.assertEqual(len(client.decisions.calls), 3)
            self.assertEqual(len(doc["cases"]), 1)
            rec = next(iter(doc["cases"].values()))
            self.assertAlmostEqual(rec["cost"], 0.02)
            self.assertIn("APITimeoutError", rec["error"])
            from jevbench import jev78
            self.assertEqual(jev78.error_kind(rec), "timeout")
            self.assertEqual(doc["meta"]["cost_stop"]["reason"], "case_cost")
        finally:
            shutil.rmtree(tmp)


class TestVersionAcreditada(unittest.TestCase):
    """R58c §3: el literal `model` se conserva observado (procedencia) pero
    la versión ACREDITADA exige snapshot fechado — un alias sin fecha
    (`gpt-6-luna`) es snapshot desconocido y `same_model` solo vale con
    versiones conocidas."""

    def test_dos_alias_iguales_no_acreditan(self):
        from jevbench.jev78 import _version_pairs
        v = _version_pairs(["ood/x"], {"ood/x": "gpt-6-luna"},
                           {"ood/x": "gpt-6-luna"})
        self.assertEqual(v["known_pairs"], 0)
        self.assertEqual(v["unknown"], ["ood/x"])
        self.assertFalse(v["same_model"])
        self.assertEqual(v["observed"]["native"], ["gpt-6-luna"])
        self.assertEqual(v["observed"]["openrouter"], ["gpt-6-luna"])

    def test_alias_vs_id_fechado(self):
        from jevbench.jev78 import _version_pairs
        v = _version_pairs(["ood/x"], {"ood/x": "gpt-6-luna"},
                           {"ood/x": "openai/gpt-6-luna-decisions-20261006"})
        self.assertEqual(v["known_pairs"], 0)
        self.assertEqual(v["unknown"], ["ood/x"])
        self.assertFalse(v["mismatch"])
        self.assertFalse(v["same_model"])

    def test_fechados_iguales_mismo_snapshot(self):
        from jevbench.jev78 import _version_pairs
        v = _version_pairs(["ood/x"], {"ood/x": "gpt-6-luna-20261006"},
                           {"ood/x": "gpt-6-luna-20261006"})
        self.assertEqual(v["known_pairs"], 1)
        self.assertFalse(v["unknown"])
        self.assertFalse(v["mismatch"])
        self.assertTrue(v["same_model"])

    def test_fechados_distintos_discrepan(self):
        from jevbench.jev78 import _version_pairs
        v = _version_pairs(["ood/x"], {"ood/x": "gpt-6-luna-20261006"},
                           {"ood/x": "gpt-6-luna-20261001"})
        self.assertEqual(v["known_pairs"], 1)
        self.assertTrue(v["mismatch"])
        self.assertFalse(v["same_model"])


class TestScorerRefusal(unittest.TestCase):
    """La pregunta rechazada puntúa 0 (error en su pregunta) conservando el
    caso: score_run no rompe y lista los refusals."""

    def test_score_run_con_refusal_parcial(self):
        from jevbench import score, store
        qs, cases = __import__("jevbench.battery", fromlist=["x"]).load_phase("ood")
        answers_ok = {qid: ({"type": "noul", "noul": 0.0} if q["type"] == "noul"
                            else {"type": "choice", "choice": next(iter(q["criteria"])),
                                  "probabilities": {k: 1.0 for k in q["criteria"]}}
                            if q["type"] == "choice"
                            else {"type": "score", "score": 0.0,
                                  "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0},
                                  "legend": {str(i): c for i, c in enumerate(q["criteria"])}})
                      for qid, q in qs.items()}
        recs = {c.id: {"answers": dict(answers_ok), "ms": 1}
                for c in cases}
        # un caso con `clinical` rechazado (marcado) — caso conservado
        recs[cases[0].id]["answers"]["clinical"] = {"type": "refusal"}
        recs[cases[0].id]["refusals"] = ["clinical"]
        tmp = Path(tempfile.mkdtemp(prefix="jev78score_"))
        try:
            with mock.patch.object(store, "ROOT", tmp):
                store.save("r78", "ood", {"meta": {}, "cases": recs})
                out = score.score_run("r78", "ood")
        finally:
            shutil.rmtree(tmp)
        self.assertEqual(out["n_ok"], len(cases))     # el caso no se pierde
        self.assertEqual(out["refusals"], [f"{cases[0].id}.clinical"])
        # la pregunta rechazada puntúa 0 en ese caso (error en su pregunta)
        from jevbench import metrics as M
        gt = cases[0].gt["clinical"]
        esperado_sin_refusal = sum(float(gt == 0) for _ in [0])  # noul=0.0
        # per_q clinical: los demás casos aportan su punto; el rechazado, 0
        otros = sum(M.point(qs["clinical"], M.normalize(answers_ok["clinical"],
                                                        qs["clinical"]),
                            c.gt["clinical"]) for c in cases[1:])
        self.assertEqual(out["per_q"]["clinical"], otros)


class TestChoiceOrder(unittest.TestCase):
    """Misma semántica que el adaptador jev (JEV-82): d0 byte a byte."""

    def test_d0_cuerpo_byte_a_byte(self):
        c1, c2 = FakeClient(CANNED), FakeClient(CANNED)
        _adapter(c1).decide("Factura duplicada.", TRIAGE_QS)
        _adapter(c2, choice_order="department:d0").decide(
            "Factura duplicada.", TRIAGE_QS)
        self.assertEqual(json.dumps(c1.decisions.calls[0], sort_keys=False),
                         json.dumps(c2.decisions.calls[0], sort_keys=False))

    def test_d1_rota_el_array_choices(self):
        client = FakeClient(CANNED)
        _adapter(client, choice_order="department:d1").decide(
            "Factura duplicada.", TRIAGE_QS)
        dept = next(q for q in client.decisions.calls[0]["questions"]
                    if q["name"] == "department")
        self.assertEqual([c["value"] for c in dept["choices"]],
                         NAMED_ORDERS["department"]["d1"])

    def test_perm_sha256_en_meta(self):
        client = FakeClient(CANNED)
        a = _adapter(client, choice_order="department:d1")
        a.decide("Factura duplicada.", TRIAGE_QS)
        self.assertEqual(a.meta()["perm_sha256"], "15f6174736a0")
        self.assertEqual(a.meta()["choice_order"],
                         {"department": NAMED_ORDERS["department"]["d1"]})


class TestClassifier(unittest.TestCase):
    """jev78.error_kind: prefijos del contrato nativo + delegación intacta
    en jev81 para el resto de clases."""

    def test_prefijos_nativos(self):
        from jevbench import jev78
        self.assertEqual(jev78.error_kind(
            {"error": 'ProviderRefusal: OpenAI refused to answer question '
                      '"department"'}), "rejection")
        self.assertEqual(jev78.error_kind(
            {"error": "ContractError: contract(local): x"}), "local")
        # delegación intacta: 502 + «refused to answer» sigue siendo rejection
        rej = ('RuntimeError: HTTP Error 502: Bad Gateway '
               '{"error":{"message":"OpenAI refused to answer question"}}')
        self.assertEqual(jev78.error_kind({"error": rej}), "rejection")
        self.assertEqual(jev78.error_kind(
            {"error": "ConnectionRefusedError: connection refused"}),
            "transport")
        self.assertIsNone(jev78.error_kind({"answers": {}}))
        self.assertEqual(jev78.error_kind({"error": "x", "n": 1}), "other")


if __name__ == "__main__":
    unittest.main()
