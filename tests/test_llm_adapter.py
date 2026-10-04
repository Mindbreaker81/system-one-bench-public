"""Offline checks of the `llm` adapter (system-one-adapter): a fake provider drives the
wire logic and a short-lived local HTTP server stands in for the OpenAI-compatible
endpoint. No external network, credentials or GPU. Skipped if the library is absent
(it lives in .venv-llm: `.venv-llm/bin/python -m unittest tests.test_llm_adapter`)."""
import http.server
import importlib.util
import json
import socket
import threading
import time
import unittest

from jevbench import metrics
from jevbench.battery import TRIAGE_QS

HAS_LIB = importlib.util.find_spec("system_one_adapter") is not None

ANSWERS = {"department": {"admin": 0.9, "bronchoscopia": 0.05, "urgencias": 0.03,
                          "consulta_externa": 0.02},
           "urgency": {"0": 0.8, "1": 0.15, "2": 0.05},
           "clinical": 0.1, "hostile": 0.0, "same_day": 0.2}


class FakeProvider:
    model_name = "fake"

    def __init__(self, texts):
        self.texts = texts if isinstance(texts, list) else [texts]
        self.calls = 0

    def request(self, messages, *, schema, structured):
        from system_one_adapter.providers.base import ProviderResult
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return ProviderResult(text=text, input_tokens=1000, output_tokens=100)


def _answers_payload(mode, answers=ANSWERS):
    return json.dumps({"answers": answers})


def _chat_completion(text, model="fake-served"):
    return {"id": "x", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}


def _responses_payload(text, model="fake-served"):
    return {"id": "r", "object": "response", "status": "completed", "model": model,
            "created_at": 0, "error": None, "incomplete_details": None,
            "output": [{"type": "message", "id": "m", "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": text,
                                     "annotations": [], "logprobs": []}]}],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}


class _Handler(http.server.BaseHTTPRequestHandler):
    """Each POST is recorded in server.requests and answered per server.plan(n, body),
    a callable returning one of:
      {"status": int, "json": obj}           normal JSON response
      {"sleep": s, "json": obj}              slow response
      {"close": True}                        drop the connection
      {"truncate": True, "json": obj}        announce a full body, send half, close"""

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        self.server.requests.append({"path": self.path, "body": body})
        action = self.server.plan(len(self.server.requests), body)
        if action.get("sleep"):
            time.sleep(action["sleep"])
        if action.get("close"):
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
            except OSError:
                pass
            return
        payload = json.dumps(action.get("json", {})).encode()
        self.send_response(action.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload) * (2 if action.get("truncate") else 1)))
        self.end_headers()
        try:
            if action.get("truncate"):
                self.wfile.write(payload[:len(payload) // 2])
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                except OSError:
                    pass
                return
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client may legitimately cut the connection (timeout tests)


class FakeOpenAIServer:
    """Context manager: local HTTP server answering like an OpenAI endpoint."""

    def __init__(self, plan):
        self.plan = plan

    def __enter__(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.plan = self.plan
        self.httpd.requests = []
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


@unittest.skipUnless(HAS_LIB, "system_one_adapter no instalado")
class TestLLMAdapter(unittest.TestCase):
    def _run(self, mode, answers, **opts):
        from jevbench.adapters.llm import LLM
        a = LLM(mode=mode, **opts)
        if "base_url" not in opts:
            a.target = FakeProvider(_answers_payload(mode, answers))
        return a, a.decide("Factura duplicada, pido reembolso.", TRIAGE_QS)

    def test_probabilities(self):
        _, out = self._run("probabilities", ANSWERS)
        ans = out["answers"]
        self.assertEqual(ans["department"]["choice"], "admin")
        self.assertAlmostEqual(ans["urgency"]["score"], 0.25)
        self.assertAlmostEqual(out["cost"], (1000 * 0.10 + 100 * 0.50) / 1e6)
        for q, spec in TRIAGE_QS.items():
            metrics.normalize(ans[q], spec)

    def test_discrete(self):
        _, out = self._run("discrete", {"department": "admin", "urgency": 0, "clinical": False,
                                        "hostile": False, "same_day": True})
        ans = out["answers"]
        self.assertEqual(ans["department"]["probabilities"]["admin"], 1.0)
        self.assertEqual(ans["same_day"]["noul"], 1.0)
        self.assertEqual(ans["urgency"]["score"], 0.0)

    def test_malformed_then_valid(self):
        """Una respuesta mal formada provoca una corrección: 2 intentos exactos."""
        from jevbench.adapters.llm import LLM
        a = LLM(mode="probabilities")
        a.target = FakeProvider(["no es json", _answers_payload("probabilities")])
        out = a.decide("Factura duplicada, pido reembolso.", TRIAGE_QS)
        self.assertEqual(a.target.calls, 2)
        self.assertEqual(out["usage"]["attempts"], 2)
        self.assertEqual(out["usage"]["n_retries_malformed"], 1)
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_private_api_compat(self):
        """La API privada de system-one-adapter que se parchea sigue ahí; si falta,
        el error debe ser claro."""
        import system_one_adapter.providers.openai as oai
        from jevbench.adapters.llm import COMPAT_VERSION, _openai_internals
        internals = _openai_internals()
        for name in ("OpenAIProvider", "_OpenAIErrors", "_response_format", "_result",
                     "_responses_request_kwargs", "_responses_result"):
            self.assertIn(name, internals)
        saved = oai._result
        try:
            del oai._result
            with self.assertRaises(RuntimeError) as cm:
                _openai_internals()
            self.assertIn(COMPAT_VERSION, str(cm.exception))
        finally:
            oai._result = saved

    def test_extra_body_rejected_on_other_provider(self):
        from jevbench.adapters.llm import LLM
        with self.assertRaises(ValueError):
            LLM(provider="anthropic", model="claude-x", api_key="x", timeout=10)
        with self.assertRaises(ValueError):
            LLM(provider="gemini", model="gemini-x", case_timeout=10)

    def test_timeout_ignored_bug_fixed(self):
        """Con OpenAI directo (sin base_url), timeout ya construye un proveedor
        en vez de perderse en el cliente por defecto."""
        from jevbench.adapters.llm import LLM
        a = LLM(model="gpt-6-luna", api_key="none", timeout=5)
        self.assertNotIsInstance(a.target, str)
        self.assertEqual(a.meta()["timeout"], 5.0)
        b = LLM(model="gpt-6-luna", api_key="none", case_timeout=30, max_tokens=256)
        self.assertNotIsInstance(b.target, str)
        self.assertEqual(b.meta()["case_timeout"], 30.0)
        self.assertEqual(b.meta()["max_tokens"], 256)

    def test_reasoning_effort_validation_and_meta(self):
        from jevbench.adapters.llm import LLM
        a = LLM(model="gpt-6.1-sol", api_key="none", reasoning_effort="low")
        self.assertNotIsInstance(a.target, str)
        self.assertEqual(a.meta()["reasoning_effort"], "low")
        b = LLM(model="gpt-6-luna")
        self.assertIsNone(b.meta()["reasoning_effort"])
        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            LLM(model="m", reasoning_effort="turbo")
        for provider in ("anthropic", "gemini"):
            with self.subTest(provider=provider), self.assertRaises(ValueError):
                LLM(provider=provider, model="m", api_key="x", reasoning_effort="low")

    def test_nested_secrets_redacted_from_meta(self):
        from jevbench.adapters.llm import LLM
        sentinel = "sk-CENTINELA-EXTRA-BODY"
        body = json.dumps({"headers": {"Authorization": f"Bearer {sentinel}"},
                           "access_token": sentinel, "temperature": 0.7})
        a = LLM(model="m", base_url="http://127.0.0.1:9/v1", api_key="none",
                extra_body=body)
        self.assertIn(sentinel, json.dumps(a.extra_body))
        self.assertNotIn(sentinel, json.dumps(a.meta()))

    def test_limits_must_be_positive(self):
        from jevbench.adapters.llm import LLM
        for name, value in (("timeout", 0), ("case_timeout", -1), ("min_interval", 0),
                            ("max_tokens", 0)):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, name):
                LLM(model="m", **{name: value})

    def test_chat_max_tokens_kwarg(self):
        from jevbench.adapters.llm import _chat_max_tokens_kwarg
        self.assertEqual(_chat_max_tokens_kwarg("api.openai.com", 7), {"max_completion_tokens": 7})
        self.assertEqual(_chat_max_tokens_kwarg("127.0.0.1", 7), {"max_tokens": 7})


@unittest.skipUnless(HAS_LIB, "system_one_adapter no instalado")
class TestOpenAIContract(unittest.TestCase):
    """Contrato HTTP contra un servidor OpenAI-compatible falso (sin red externa)."""

    def _adapter(self, base_url, **opts):
        from jevbench.adapters.llm import LLM
        return LLM(mode="probabilities", base_url=base_url, api_key="none", **opts)

    def test_base_url_schema_and_extra_body(self):
        body_text = _answers_payload("probabilities")

        def plan(n, body):
            return {"json": _chat_completion(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m",
                              extra_body='{"chat_template_kwargs": {"enable_thinking": false}}')
            out = a.decide("estado", TRIAGE_QS)
        req = srv.httpd.requests[0]
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["body"]["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(req["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_max_tokens_with_and_without_extra_body(self):
        body_text = _answers_payload("probabilities")

        def plan(n, body):
            return {"json": _chat_completion(body_text)}

        for extra in (None, '{"penalty": 0}'):
            with FakeOpenAIServer(plan) as srv:
                a = self._adapter(srv.base_url, model="m", max_tokens=64,
                                  **({"extra_body": extra} if extra else {}))
                a.decide("estado", TRIAGE_QS)
            body = srv.httpd.requests[0]["body"]
            self.assertEqual(body.get("max_tokens"), 64)
            self.assertNotIn("max_completion_tokens", body)
            if extra:
                self.assertEqual(body.get("penalty"), 0)

    def test_responses_api_uses_max_output_tokens(self):
        body_text = _answers_payload("probabilities")
        seen = {}

        def plan(n, body):
            seen.update(body)
            return {"json": _responses_payload(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", max_tokens=64)
            a.target.api = "responses"  # fuerza la rama Responses contra el servidor falso
            out = a.decide("estado", TRIAGE_QS)
        self.assertEqual(srv.httpd.requests[0]["path"], "/v1/responses")
        self.assertEqual(seen.get("max_output_tokens"), 64)
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_reasoning_effort(self):
        """Responses recibe reasoning={"effort": …} y Chat Completions
        reasoning_effort=…; sin la opción ninguna de las dos claves aparece."""
        body_text = _answers_payload("probabilities")

        for api, key, expected in (("responses", "reasoning", {"effort": "low"}),
                                   ("chat_completions", "reasoning_effort", "low")):
            for effort in (None, "low"):
                seen = {}

                def plan(n, body, seen=seen):
                    seen.update(body)
                    payload = (_responses_payload if api == "responses"
                               else _chat_completion)(body_text)
                    return {"json": payload}

                with FakeOpenAIServer(plan) as srv:
                    a = self._adapter(srv.base_url, model="m",
                                      **({"reasoning_effort": effort} if effort else {}))
                    a.target.api = api  # fuerza la rama contra el servidor falso
                    out = a.decide("estado", TRIAGE_QS)
                if effort:
                    self.assertEqual(seen.get(key), expected)
                else:
                    self.assertNotIn("reasoning", seen)
                    self.assertNotIn("reasoning_effort", seen)
                self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_structured_false_prompted_json(self):
        body_text = _answers_payload("probabilities")
        seen = {}

        def plan(n, body):
            seen.update(body)
            return {"json": _chat_completion(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", structured="false")
            out = a.decide("estado", TRIAGE_QS)
        self.assertIsNone(seen.get("response_format"))
        self.assertIn("schema", srv.httpd.requests[0]["body"]["messages"][0]["content"])
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_case_timeout_blocks_corrective(self):
        """Un JSON mal formado consume la misma bolsa: agotado case_timeout no debe
        abrir una segunda petición."""
        def plan(n, body):
            return {"json": _chat_completion("no es json")}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", case_timeout=600, retries_malformed=2)
            clock = [1000.0]
            a.target._clock = lambda: clock[0]
            # la primera petición entra a t=1000 con deadline=1600; la corrección vería
            # el reloj ya pasado y debe fallar antes de abrir otra petición
            orig_request = a.target.request.__func__

            def request_and_expire(self, messages, *, schema, structured):
                try:
                    return orig_request(self, messages, schema=schema, structured=structured)
                finally:
                    clock[0] = 2000.0

            import types
            a.target.request = types.MethodType(request_and_expire, a.target)
            with self.assertRaises(Exception) as cm:
                a.decide("estado", TRIAGE_QS)
        self.assertEqual(len(srv.httpd.requests), 1)
        self.assertIn("case_timeout", str(cm.exception))
        diag = getattr(cm.exception, "diag", {})
        self.assertEqual(diag.get("attempts"), 1)

    def test_request_timeout(self):
        def plan(n, body):
            return {"sleep": 2.0, "json": _chat_completion(_answers_payload("probabilities"))}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", timeout=0.4)
            t0 = time.monotonic()
            with self.assertRaises(Exception) as cm:
                a.decide("estado", TRIAGE_QS)
            elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 2.0, "el timeout por petición no se aplicó")
        self.assertTrue("timeout" in str(cm.exception).lower()
                        or "timeout" in type(cm.exception).__name__.lower(),
                        str(cm.exception))

    def test_min_interval_spaces_requests(self):
        def plan(n, body):
            return {"json": _chat_completion(_answers_payload("probabilities"))}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", min_interval=0.4)
            self.assertEqual(a.meta()["min_interval"], 0.4)
            t0 = time.monotonic()
            a.decide("estado", TRIAGE_QS)
            a.decide("estado", TRIAGE_QS)
            elapsed = time.monotonic() - t0
        self.assertEqual(len(srv.httpd.requests), 2)
        self.assertGreaterEqual(elapsed, 0.35, "min_interval no espació las peticiones")

    def test_http_error_statuses(self):
        for status in (429, 500):
            def plan(n, body, status=status):
                return {"status": status,
                        "json": {"error": {"message": f"boom {status}", "type": "x"}}}
            with FakeOpenAIServer(plan) as srv:
                a = self._adapter(srv.base_url, model="m", timeout=5)
                with self.assertRaises(Exception) as cm:
                    a.decide("estado", TRIAGE_QS)
            self.assertIn(f"boom {status}", str(cm.exception))
            self.assertEqual(getattr(cm.exception, "diag", {}).get("attempts"), 1)

    def test_connection_closed(self):
        def plan(n, body):
            return {"close": True}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", timeout=5)
            with self.assertRaises(Exception):
                a.decide("estado", TRIAGE_QS)

    def test_prompt_simple_swaps_system_message(self):
        """prompt=simple sustituye el system prompt de TypeSafe por la plantilla
        pre-registrada; el esquema enviado es idéntico al de la variante typesafe."""
        body_text = _answers_payload("probabilities")
        seen = {}

        def plan(n, body):
            seen.setdefault("requests", []).append(body)
            return {"json": _chat_completion(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", prompt="simple")
            out = a.decide("estado", TRIAGE_QS)
            self.assertIsNotNone(a.meta()["prompt_sha256"])
            self.assertIsNotNone(a.meta()["prompt_template_sha256"])
            b = self._adapter(srv.base_url, model="m")
            b.decide("estado", TRIAGE_QS)
            self.assertIsNone(b.meta()["prompt_sha256"])
            self.assertIsNone(b.meta()["prompt_template_sha256"])

        simple_req, typesafe_req = seen["requests"]
        simple_sys = simple_req["messages"][0]["content"]
        self.assertIn("Read the document provided by the user", simple_sys)
        self.assertIn('"department"', simple_sys)
        self.assertNotIn("untrusted", simple_sys)
        self.assertIn("untrusted", typesafe_req["messages"][0]["content"])
        self.assertEqual(simple_req["response_format"], typesafe_req["response_format"])
        self.assertEqual(simple_req["messages"][1], typesafe_req["messages"][1])
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_inject_schema_in_prompt(self):
        """JEV-66: inject_schema_in_prompt=true añade al system prompt el mismo
        apéndice de esquema que la ruta structured=false, conservando
        response_format (gramática intacta). El sha esperado se puede calcular
        sin petición."""
        body_text = _answers_payload("probabilities")
        seen = {}

        def plan(n, body):
            seen.setdefault("requests", []).append(body)
            return {"json": _chat_completion(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", inject_schema_in_prompt="true")
            exp_sha = a.expected_system_prompt_sha256(TRIAGE_QS)
            out = a.decide("estado", TRIAGE_QS)
            b = self._adapter(srv.base_url, model="m", structured="false")
            b.decide("estado", TRIAGE_QS)

        injected_req, nostruct_req = seen["requests"]
        injected_sys = injected_req["messages"][0]["content"]
        # mismo texto de system prompt que la ruta nostruct, pero con gramática
        self.assertEqual(injected_sys, nostruct_req["messages"][0]["content"])
        self.assertIn("schema", injected_sys)
        self.assertIn('"department"', injected_sys)
        self.assertEqual(injected_req["response_format"]["type"], "json_schema")
        self.assertIsNone(nostruct_req.get("response_format"))
        # el sha esperado (calculado sin petición) coincide con el enviado
        import hashlib
        self.assertEqual(exp_sha,
                         hashlib.sha256(injected_sys.encode()).hexdigest()[:12])
        self.assertEqual(a.meta()["system_prompt_sha256"], exp_sha)
        self.assertTrue(a.meta()["inject_schema_in_prompt"])
        self.assertFalse(b.meta()["inject_schema_in_prompt"])
        self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_inject_schema_in_prompt_validation(self):
        from jevbench.adapters.llm import LLM
        with self.assertRaisesRegex(ValueError, "inject_schema_in_prompt"):
            LLM(model="m", structured="false", inject_schema_in_prompt="true",
                base_url="http://127.0.0.1:9/v1", api_key="none")
        for provider in ("anthropic", "gemini"):
            with self.subTest(provider=provider), self.assertRaises(ValueError):
                LLM(provider=provider, model="m", api_key="x",
                    inject_schema_in_prompt="true")

    def test_prompt_simple_validation(self):
        from jevbench.adapters.llm import LLM
        with self.assertRaisesRegex(ValueError, "prompt"):
            LLM(model="m", base_url="http://127.0.0.1:9/v1", api_key="none",
                prompt="otro")
        # sin proveedor propio no hay donde colgar el override: falla en decide()
        a = LLM(model="m", prompt="simple")
        with self.assertRaisesRegex(ValueError, "prompt=simple"):
            a.decide("estado", TRIAGE_QS)

    def test_capture_raw_attempts(self):
        body_text = _answers_payload("probabilities")

        def plan(n, body):
            return {"json": _chat_completion(body_text)}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", capture_raw="true")
            out = a.decide("estado", TRIAGE_QS)
            b = self._adapter(srv.base_url, model="m")
            out_b = b.decide("estado", TRIAGE_QS)
        self.assertNotIn("raw", out_b)
        attempts = out["raw"]
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["request"]["model"], "m")
        content = attempts[0]["llm_response"]["choices"][0]["message"]["content"]
        self.assertEqual(json.loads(content), json.loads(body_text))
        self.assertEqual(attempts[0]["debug_info"]["finish_reason"], "stop")

    def test_truncated_response(self):
        def plan(n, body):
            return {"truncate": True, "json": _chat_completion(_answers_payload("probabilities"))}

        with FakeOpenAIServer(plan) as srv:
            a = self._adapter(srv.base_url, model="m", timeout=5)
            with self.assertRaises(Exception):
                a.decide("estado", TRIAGE_QS)


if __name__ == "__main__":
    unittest.main()
