"""Tests del supervisor y la sonda de JEV-67 (offline, servidor falso).

  .venv-llm/bin/python -m unittest tests.test_jev67 -v
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import jevbench.jev67 as j67
import jevbench.probe_injection as probe
from jevbench import metrics, store
from jevbench.battery import TRIAGE_QS, load_phase, questions_hash
from jevbench.rotation import rotate_choice, rotation_manifest
from tests.test_llm_adapter import (ANSWERS, FakeOpenAIServer,
                                    _answers_payload, _chat_completion)

HAS_LIB = importlib.util.find_spec("system_one_adapter") is not None

STATE = "Factura duplicada, pido reembolso."


def _plan(payload=None):
    """Plan del servidor falso: responde la misma completion a todo."""
    text = _answers_payload("probabilities", payload or ANSWERS)
    return lambda n, body: {"json": _chat_completion(text)}


def _llm(server, **kw):
    from jevbench.adapters.llm import LLM
    return LLM(mode="probabilities", base_url=server.base_url,
               model="fake-model", api_key="none", capture_raw=True,
               timeout=5, case_timeout=20, **kw)


# ------------------------------------------------------------------ stats

class TestStats(unittest.TestCase):
    def test_clopper_pearson_known_values(self):
        lo, hi = j67.clopper_pearson(48, 100)
        self.assertAlmostEqual(lo, 0.3790, places=3)
        self.assertAlmostEqual(hi, 0.5822, places=3)
        lo, hi = j67.clopper_pearson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.3085, places=3)
        lo, hi = j67.clopper_pearson(10, 10)
        self.assertEqual(hi, 1.0)
        self.assertAlmostEqual(lo, 0.6915, places=3)

    def test_poisson_binomial_sf(self):
        # X ~ 3 Bernoulli(0.5): P(X>=2) = 0.5
        self.assertAlmostEqual(j67.poisson_binomial_sf([0.5] * 3, 2), 0.5)
        # P(X >= 0) = 1
        self.assertAlmostEqual(j67.poisson_binomial_sf([0.1, 0.9], 0), 1.0)
        # heterogéneas: P(X>=2) por enumeración exacta
        ps = [0.2, 0.5, 0.7]
        p_exact2 = 0.2 * 0.5 * 0.3 + 0.2 * 0.5 * 0.7 + 0.8 * 0.5 * 0.7
        p3 = 0.2 * 0.5 * 0.7
        self.assertAlmostEqual(j67.poisson_binomial_sf(ps, 2),
                               p_exact2 + p3)

    def test_newcombe_bounds(self):
        d, lo, hi = j67.newcombe_paired(40, 5, 15, 40)
        self.assertAlmostEqual(d, 0.45 - 0.55, places=6)
        self.assertLess(lo, -0.1)
        self.assertLess(hi, 0.05)
        # discordancias simétricas: el IC debe cubrir 0
        d, lo, hi = j67.newcombe_paired(40, 10, 10, 40)
        self.assertAlmostEqual(d, 0.0)
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)


# --------------------------------------------------------------- rotación

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestRotateChoiceAdapter(unittest.TestCase):
    def test_payload_rotated_schema_order(self):
        """El esquema enviado rota las propiedades igual que
        rotation.rotate_choice y el prompt inyectado lleva el mismo orden."""
        with FakeOpenAIServer(_plan()) as server:
            model = _llm(server, structured="true",
                         inject_schema_in_prompt="true", rotate_choice=1)
            model.decide(STATE, TRIAGE_QS)
        req = server.httpd.requests[0]["body"]
        sch = req["response_format"]["json_schema"]["schema"]
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        dept_ref = ans["properties"]["department"]["$ref"].split("/")[-1]
        props = list(sch["$defs"][dept_ref]["properties"])
        self.assertEqual(props,
                         list(rotate_choice(TRIAGE_QS, 1)["department"]
                              ["criteria"].keys()))
        # el esquema incrustado en el system prompt es idéntico al enviado
        embedded = j67._embedded_schema(req["messages"][0]["content"])
        self.assertEqual(embedded, sch)

    def test_questions_hash_invariant(self):
        self.assertEqual(questions_hash(rotate_choice(TRIAGE_QS, 1)),
                         questions_hash(TRIAGE_QS))

    def test_rot1_frozen_shas(self):
        """§7.3: los sha rot1 congelados se reproducen con rotate_choice=1."""
        from jevbench.adapters.llm import LLM
        for phase, want in (("triage_es", "64191fd2a4fb"),
                            ("papers32", "e8761e9f8246"),
                            ("ood", "a9c6380e1962")):
            qs, _ = load_phase(phase)
            m = LLM(mode="probabilities", structured="true",
                    inject_schema_in_prompt="true", rotate_choice=1,
                    base_url="http://127.0.0.1:9/v1", api_key="none")
            self.assertEqual(m.expected_system_prompt_sha256(qs), want, phase)

    def test_meta_records_rotation(self):
        with FakeOpenAIServer(_plan()) as server:
            model = _llm(server, structured="true",
                         inject_schema_in_prompt="true", rotate_choice=1)
            model.decide(STATE, TRIAGE_QS)
        meta = model.meta()
        self.assertEqual(meta["rotate_choice"], 1)
        self.assertEqual(meta["perm_sha256"],
                         rotation_manifest(rotate_choice(TRIAGE_QS, 1))
                         ["perm_sha256"])

    def test_pfix_null_vector_first_key(self):
        """P+fix: un vector nulo elige la PRIMERA clave del orden enviado,
        en base y rotada, leído por el scorer (el servidor falso emite el
        vector nulo en el orden del esquema recibido)."""

        def plan(n, body):
            sch = body["response_format"]["json_schema"]["schema"]
            ans = sch["properties"]["answers"]
            ans = sch["$defs"][ans["$ref"].split("/")[-1]]
            nulls = {}
            for qid, field in ans["properties"].items():
                ref = sch["$defs"][field["$ref"].split("/")[-1]] \
                    if "$ref" in field else field
                sub = ref.get("properties")
                nulls[qid] = ({k: 0.0 for k in sub} if sub else 0.0)
            return {"json": _chat_completion(json.dumps({"answers": nulls}))}

        for rot in (0, 1):
            with FakeOpenAIServer(plan) as server:
                model = _llm(server, structured="true",
                             inject_schema_in_prompt="true", rotate_choice=rot)
                out = model.decide(STATE, TRIAGE_QS)
            pred = metrics.normalize(out["answers"]["department"],
                                     TRIAGE_QS["department"])
            sent = list(rotate_choice(TRIAGE_QS, rot)["department"]
                        ["criteria"])
            self.assertEqual(pred["label"], sent[0],
                             f"rot={rot}: el nulo debe elegir la 1ª clave")


# ----------------------------------------------------- check_client (puerta)

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestCheckClient(unittest.TestCase):
    def _capture(self, **kw):
        with FakeOpenAIServer(_plan()) as server:
            model = _llm(server, **kw)
            model.decide(STATE, TRIAGE_QS)
        return server.httpd.requests[0]["body"]

    def test_inject_request_passes_all_checks(self):
        req = self._capture(structured="true", inject_schema_in_prompt="true")
        self.assertEqual(j67.check_client(req, TRIAGE_QS, "inject",
                                          "probabilities"), [])

    def test_rot1_request_passes_order_check(self):
        req = self._capture(structured="true", inject_schema_in_prompt="true",
                            rotate_choice=1)
        self.assertEqual(j67.check_client(req, rotate_choice(TRIAGE_QS, 1),
                                          "rot1", "probabilities"), [])

    def test_nostruct_request_passes(self):
        req = self._capture(structured="false")
        self.assertEqual(j67.check_client(req, TRIAGE_QS, "nostruct",
                                          "probabilities"), [])

    def test_blind_request_passes(self):
        req = self._capture(structured="true", inject_schema_in_prompt="false")
        self.assertEqual(j67.check_client(req, TRIAGE_QS, "blind",
                                          "probabilities"), [])

    def test_blind_flagged_when_injected(self):
        """Un request con apéndice no puede pasar por blind."""
        req = self._capture(structured="true", inject_schema_in_prompt="true")
        fails = j67.check_client(req, TRIAGE_QS, "blind", "probabilities")
        self.assertTrue(any("apéndice" in f for f in fails))

    def test_disc_inject_visibility_check(self):
        """En discrete, las instrucciones y 'label = criterio' van en la
        description del campo."""
        disc_answers = {"department": "admin", "urgency": 1, "clinical": False,
                        "hostile": False, "same_day": False}
        plan = lambda n, b: {"json": _chat_completion(
            json.dumps({"answers": disc_answers}))}
        with FakeOpenAIServer(plan) as server:
            from jevbench.adapters.llm import LLM
            model = LLM(mode="discrete", structured="true",
                        inject_schema_in_prompt="true",
                        base_url=server.base_url, model="fake-model",
                        api_key="none", capture_raw=True, timeout=5,
                        case_timeout=20)
            model.decide(STATE, TRIAGE_QS)
        req = server.httpd.requests[0]["body"]
        self.assertEqual(j67.check_client(req, TRIAGE_QS, "inject",
                                          "discrete"), [])


# --------------------------------------------------- supervisor run (falso)

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestRunSupervisor(unittest.TestCase):
    """run_cell contra el servidor falso; la referencia de tokens se
    parchea para coincidir con el usage del fake."""

    def _cell(self, run="t_cell", seed=101, budget=600):
        return {"run": run, "host": "fake", "mode": "probabilities",
                "structured": True, "inject": True, "rot": 0, "seed": seed,
                "phases": ["triage_es"], "budget_s": budget}

    def _patch(self, ref_tokens=10):
        ref = {"triage_es": {c.id: ref_tokens
                             for c in load_phase("triage_es")[1]}}
        patches = [
            mock.patch.object(j67, "CELLS",
                              {**j67.CELLS, "t": self._cell()}),
            mock.patch.object(j67, "load_token_ref", lambda: ref),
            mock.patch.object(j67, "HOSTS", {**j67.HOSTS, "fake": {
                "base_url": self.server.base_url, "model": "fake"}}),
            mock.patch.object(store, "ROOT", Path(self._tmp.name)),
            # puerta aprobada genérica: las celdas de test no tienen gate67_*
            mock.patch.object(j67, "_latest_gate",
                              lambda *a: ("gate_fake", {"ok": True,
                                                        "gate_id": "gf@t"})),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _serve(self, plan):
        self.server = FakeOpenAIServer(plan)
        self.server.__enter__()
        self.addCleanup(self.server.__exit__)

    def test_run_completes_and_writes_run_format(self):
        self._serve(_plan())
        self._patch(ref_tokens=10)
        status = j67.run_cell("t")
        self.assertEqual(status, "complete")
        doc = store.load("t_cell", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")
        self.assertIn("raw", doc["cases"]["T01_ebus_alergia"])

    def test_run_aborts_on_token_violation(self):
        """Si el primer intento incumple la regla de tokens, el run entero
        se aborta y queda marcado invalid_visibility."""
        self._serve(_plan())
        self._patch(ref_tokens=900)          # |10-900| >> 2 -> ciego
        status = j67.run_cell("t")
        self.assertEqual(status, "invalid_visibility")
        doc = store.load("t_cell", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["status"], "invalid_visibility")
        self.assertEqual(len(doc["cases"]), 1)   # abortó tras el 1er caso

    def test_resume_rejects_different_config_without_writing(self):
        self._serve(_plan())
        self._patch()
        j67.run_cell("t")
        before = store.load("t_cell", "triage_es")
        with mock.patch.object(j67, "CELLS", {**j67.CELLS, "t": self._cell(
                seed=202)}):
            with self.assertRaises(SystemExit):
                j67.run_cell("t")
        self.assertEqual(store.load("t_cell", "triage_es"), before)

    def test_no_usage_counts_and_applies_client_check(self):
        """Un intento sin usage no aborta: cuenta como «no verificable por
        tokens» y solo se aplica el criterio de cliente."""
        def plan(n, body):
            resp = _chat_completion(_answers_payload("probabilities", ANSWERS))
            del resp["usage"]
            return {"json": resp}
        self._serve(plan)
        self._patch()
        status = j67.run_cell("t")
        self.assertEqual(status, "complete")
        doc = store.load("t_cell", "triage_es")
        self.assertEqual(len(doc["meta"]["diag"]["no_usage_cases"]), 14)

    def test_phase_stops_after_three_errors(self):
        """3 errores en una fase -> los casos restantes de ESA fase quedan
        registrados como no ejecutados por regla de parada."""
        calls = {"n": 0}

        def plan(n, body):
            calls["n"] += 1
            if calls["n"] <= 3:
                # 400 no es retryable en el SDK: un error por caso
                return {"status": 400, "json": {"error": {"message": "boom"}}}
            return {"json": _chat_completion(
                _answers_payload("probabilities", ANSWERS))}
        self._serve(plan)
        self._patch()
        j67.run_cell("t")
        doc = store.load("t_cell", "triage_es")
        errors = sum(1 for r in doc["cases"].values() if "error" in r)
        self.assertEqual(errors, 3)
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 14 - 3)

    def test_gate_required_before_battery(self):
        """Sin puerta aprobada, run_cell rechaza antes de crear el adaptador."""
        self._serve(_plan())
        self._patch()
        with mock.patch.object(j67, "_latest_gate",
                               lambda *a: ("gate_fake", None)):
            with self.assertRaises(SystemExit):
                j67.run_cell("t")
        self.assertIsNone(store.load("t_cell", "triage_es"))

    def test_resume_after_complete_run_allowed(self):
        """Reanudar un run terminado (con status/stopped/no_usage en diag)
        no se rechaza a sí mismo: son claves operativas, no config."""
        self._serve(_plan())
        self._patch()
        j67.run_cell("t")
        doc = store.load("t_cell", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")
        status = j67.run_cell("t")          # segunda pasada, mismos opts
        self.assertEqual(status, "complete")

    def test_meta_records_gate_id(self):
        self._serve(_plan())
        self._patch()
        j67.run_cell("t")
        doc = store.load("t_cell", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["gate_id"], "gf@t")

    def test_missing_offset_is_violation(self):
        """En discrete, familia sin offset de puerta = visibilidad no
        verificable, no ok implícito."""
        rec = {"raw": [{"llm_response": {"choices": [{}],
                                         "usage": {"prompt_tokens": 100}}}]}
        # sin referencia del caso -> violación, no ok
        st, det = j67._token_rule_ok({"mode": "discrete", "rot": 0},
                                     "triage_es", rec,
                                     {"triage_es": {"x": 300}}, {})
        self.assertEqual((st, det), ("violacion", "sin ref"))
        rec["_cid"] = "x"
        st2, det2 = j67._token_rule_ok({"mode": "discrete", "rot": 0},
                                       "triage_es", rec,
                                       {"triage_es": {"x": 300}}, {})
        self.assertEqual((st2, det2), ("violacion", "sin offset de puerta"))

    def test_missing_reference_is_violation(self):
        """Referencia ausente (`sin ref`) = violación en los tres caminos:
        probabilities base, rot1 y discrete — nunca un ok implícito."""
        rec = {"raw": [{"llm_response": {"choices": [{}],
                                         "usage": {"prompt_tokens": 100}}}]}
        for cell in ({"mode": "probabilities", "rot": 0},
                     {"mode": "probabilities", "rot": 1},
                     {"mode": "discrete", "rot": 0}):
            for r in (rec, {**rec, "_cid": "desconocido"}):
                st, det = j67._token_rule_ok(cell, "triage_es", r,
                                             {"triage_es": {"x": 300}}, {})
                self.assertEqual((st, det), ("violacion", "sin ref"), cell)


class TestAuditYPlive(unittest.TestCase):
    """Regresiones del informe: ausentes no cuentan como ok, conserva
    posición usa la etiqueta nueva, P+ se verifica con evidencia."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.object(store, "ROOT", Path(self._tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_audit_missing_not_ok(self):
        """Un caso ausente del doc no cuenta como ok ni como caso."""
        rec = {"answers": {"q": {"choice": "a"}},
               "usage": {"input_tokens": 10}}
        doc = {"meta": {"opts": {}},
               "cases": {"T01_ebus_alergia": rec}}   # resto ausentes
        store.save("aud_test", "triage_es", doc)
        with mock.patch.object(j67, "load_token_ref",
                               lambda: {"triage_es": {}}):
            rep = j67.audit_run("aud_test", ["triage_es"])
        self.assertEqual(rep["phases"]["triage_es"]["ok"], 1)
        self.assertEqual(len(rep["phases"]["triage_es"]["missing"]),
                         len(load_phase("triage_es")[1]) - 1)

    def test_conserva_uses_new_label(self):
        """conserva posición = posición de la NUEVA etiqueta en el orden
        rotado vs la de la antigua en el original."""
        qs = {"q1": {"type": "choice",
                     "criteria": {"a": "A", "b": "B", "c": "C"}}}
        rqs = j67.rotate_choice(qs, 1)           # b,c,a
        for run, label in (("rot0t", "a"), ("rot1t", "b")):
            store.save(run, "triage_es",
                       {"meta": {}, "cases": {"T01_ebus_alergia": {
                           "answers": {"q1": {"choice": label}}}}})
        with mock.patch.object(j67, "load_phase",
                               lambda ph: (qs, [])):
            changes, tot = j67.choice_changes("rot0t", "rot1t")
        # 'a' (pos 0 base) -> 'b' (pos 0 rotado): la nueva etiqueta conserva
        self.assertEqual(changes[0]["conserva"], True)
        # 'a' -> 'c' (pos 1 rotado): no conserva
        store.save("rot1t", "triage_es",
                   {"meta": {}, "cases": {"T01_ebus_alergia": {
                       "answers": {"q1": {"choice": "c"}}}}})
        with mock.patch.object(j67, "load_phase",
                               lambda ph: (qs, [])):
            changes, _ = j67.choice_changes("rot0t", "rot1t")
        self.assertEqual(changes[0]["conserva"], False)

    def test_pfix_evidence(self):
        self.assertTrue(j67.pfix_check())

    def test_null_qids(self):
        qs = {"q": {"type": "choice",
                    "criteria": {"a": "A", "b": "B"}}}
        rec = {"raw": [{"llm_response": {"choices": [{
            "message": {"content": '{"answers": {"q": {"a": 0.0, "b": 0.0}}}'}}]}}]}
        self.assertEqual(j67._null_qids(rec, qs), {"q"})


# -------------------------------------------------------- probe_injection

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestProbe(unittest.TestCase):
    def test_pad_schema_descriptions(self):
        sch = {"properties": {"a": {"description": "x", "type": "number"}},
               "$defs": {"D": {"description": "y",
                               "properties": {"p": {"description": "z"}}}}}
        out = probe._pad_schema_descriptions(sch, "PAD")
        self.assertEqual(out["properties"]["a"]["description"], "x PAD")
        self.assertEqual(out["$defs"]["D"]["description"], "y PAD")
        self.assertEqual(out["$defs"]["D"]["properties"]["p"]["description"],
                         "z PAD")
        self.assertEqual(sch["properties"]["a"]["description"], "x")

    def test_token_probe_classification_no_inject(self):
        """Servidor que no inyecta: a≈b≈d -> 'no_inyecta'."""
        tokens = {"a": 300, "b": 300, "c": 900, "d": 302}

        class FakeCompletions:
            @staticmethod
            def create(**kw):
                has_rf = "response_format" in kw
                padded = has_rf and "Padding note" in json.dumps(
                    kw["response_format"])
                injected = "matches this schema exactly" in \
                    kw["messages"][0]["content"]
                t = (tokens["c"] if injected else tokens["d"] if padded
                     else tokens["a"] if has_rf else tokens["b"])
                u = SimpleNamespace(prompt_tokens=t,
                                    prompt_tokens_details=None,
                                    completion_tokens=1, total_tokens=t + 1)
                return SimpleNamespace(
                    usage=u,
                    choices=[SimpleNamespace(finish_reason="length")])

        class FakeClient:
            chat = SimpleNamespace(completions=FakeCompletions)

        with FakeOpenAIServer(_plan()) as server:
            model = _llm(server, structured="true",
                         inject_schema_in_prompt="false")
            model.target._client = FakeClient
        res = probe.token_probe(model, printer=lambda *a: None)
        for cid, v in res["interpretation"].items():
            self.assertEqual(v, "no_inyecta", cid)

    def test_token_probe_injects_with_descriptions(self):
        """a-b>=200 y d-a≈relleno -> 'inyecta_con_descripciones'."""
        tokens = {"a": 800, "b": 300, "c": 900, "d": 1100}

        class FakeCompletions:
            @staticmethod
            def create(**kw):
                has_rf = "response_format" in kw
                padded = has_rf and "Padding note" in json.dumps(
                    kw["response_format"])
                injected = "matches this schema exactly" in \
                    kw["messages"][0]["content"]
                t = (tokens["c"] if injected else tokens["d"] if padded
                     else tokens["a"] if has_rf else tokens["b"])
                u = SimpleNamespace(prompt_tokens=t,
                                    prompt_tokens_details=None,
                                    completion_tokens=1, total_tokens=t + 1)
                return SimpleNamespace(
                    usage=u,
                    choices=[SimpleNamespace(finish_reason="length")])

        class FakeClient:
            chat = SimpleNamespace(completions=FakeCompletions)

        with FakeOpenAIServer(_plan()) as server:
            model = _llm(server, structured="true",
                         inject_schema_in_prompt="false")
            model.target._client = FakeClient
        res = probe.token_probe(model, printer=lambda *a: None)
        for cid, v in res["interpretation"].items():
            self.assertEqual(v, "inyecta_con_descripciones", cid)

    def test_classify_table(self):
        """§6.2: combinaciones (T) x (C) -> clase."""
        def c(b, i="ve", t="ve"):
            return {"blind": {"verdict": b}, "inject": {"verdict": i},
                    "twin": {"verdict": t}}
        self.assertEqual(probe.classify({"A01": "no_inyecta"},
                                        c("no ve"))["clase"], "no_visibles")
        self.assertEqual(probe.classify({"A01": "inyecta_con_descripciones"},
                                        c("ve"))["clase"], "visibles")
        self.assertEqual(probe.classify({"A01": "no_inyecta"},
                                        c("parcial"))["clase"],
                         "visibilidad_parcial")
        self.assertEqual(probe.classify({"A01": "no_inyecta"},
                                        c("no ve", t="parcial"))["clase"],
                         "no_evaluable")
        self.assertEqual(probe.classify({"A01": "unstable"},
                                        c("no ve"))["clase"], "inconcluso")


# --------------------------------------------------------- diag66 --prefix

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestDiag66Prefix(unittest.TestCase):
    def test_prefix_in_run_names(self):
        """--prefix cambia el directorio de run sin tocar el de JEV-66."""
        from jevbench import diag66
        calls = []
        with mock.patch.object(diag66, "_run_cell",
                               lambda name, cell, rep, opts, limit=None,
                               retry_errors=False,
                               prefix="diag_qwen38_jev66":
                               calls.append((name, cell, rep, prefix)) or 0):
            argv = sys.argv
            sys.argv = ["diag66", "fp8_rot1", "--reps", "1",
                        "--cells", "typesafe_struct",
                        "--prefix", "diag_qwen38_jev67"]
            try:
                diag66.main()
            finally:
                sys.argv = argv
        self.assertEqual(calls, [("fp8_rot1", "typesafe_struct", 1,
                                  "diag_qwen38_jev67")])


if __name__ == "__main__":
    unittest.main()
