"""General-purpose LLM through TypeSafe's own `system-one-adapter` (drop-in `system_one`
backed by OpenAI / Anthropic / Gemini or any OpenAI-compatible endpoint). The prompt and
schema are TypeSafe's, so this is the LLM baseline they consider fair.
https://github.com/typesafe-ai/system-one-adapter-python

  provider=openai|anthropic|gemini   model=gpt-6-luna
  mode=probabilities|discrete        structured=true (native JSON Schema) | false (prompted)
  base_url=…                         OpenAI-compatible endpoint (vLLM, SGLang, OpenRouter…)
  extra_body=<json>                  merged into each chat.completions request, e.g.
                                     '{"chat_template_kwargs": {"enable_thinking": false}}'
  api_key=…                          credential for the endpoint (local servers: any string)
  timeout=<s>                        per-request timeout (slow thinking models need more)
  case_timeout=<s>                   wall-clock budget for the whole case, corrective
                                     retries included (never reset by a malformed answer)
  max_tokens=<n>                     output cap: max_output_tokens (Responses),
                                     max_completion_tokens (OpenAI Chat Completions) or
                                     max_tokens (compatible endpoints: vLLM, SGLang…)
  usd_in / usd_out                   $/Mtok for the cost column (providers don't return it)

timeout/case_timeout/max_tokens/extra_body are implemented for provider=openai only; with
Anthropic or Gemini the adapter fails loudly instead of silently ignoring them.
"""
import json
import time

from . import Adapter
from ..env import load_env
from ..redact import redact_value

# $/Mtok (input, output); public list prices, override with --opt usd_in=… usd_out=…
PRICES = {"gpt-6-luna": (0.10, 0.50)}

# system-one-adapter version whose private members this adapter relies on
COMPAT_VERSION = "0.2.1"


def _bool(v):
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")


def _openai_internals():
    """Private members of system-one-adapter that the bounded provider reuses
    (`_OpenAIErrors`, `_response_format`, `_result`, `_responses_request_kwargs`,
    `_responses_result` and the base helpers). Everything private goes through this
    function so an incompatible library update fails here with a clear message."""
    try:
        import system_one_adapter
    except ImportError as e:
        raise RuntimeError(
            f"system-one-adapter no está instalado (se requiere {COMPAT_VERSION})") from e
    try:
        from system_one_adapter.providers.base import (
            ProviderResult, record_request, record_response, render_messages, translating)
        from system_one_adapter.providers.openai import (
            OpenAIProvider, _OpenAIErrors, _response_format, _responses_request_kwargs,
            _responses_result, _result)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(
            f"system-one-adapter {system_one_adapter.__version__} no expone la API interna "
            f"que espera este adaptador (probado con {COMPAT_VERSION}): {e}") from e
    if system_one_adapter.__version__ != COMPAT_VERSION:
        raise RuntimeError(
            f"system-one-adapter {system_one_adapter.__version__} no es la versión fijada "
            f"para este parche de API privada ({COMPAT_VERSION})")
    return {"ProviderResult": ProviderResult, "record_request": record_request,
            "record_response": record_response, "render_messages": render_messages,
            "translating": translating, "OpenAIProvider": OpenAIProvider,
            "_OpenAIErrors": _OpenAIErrors, "_response_format": _response_format,
            "_responses_request_kwargs": _responses_request_kwargs,
            "_responses_result": _responses_result, "_result": _result}


def _chat_max_tokens_kwarg(host, max_tokens):
    """Output-cap kwarg for Chat Completions: official OpenAI uses
    `max_completion_tokens`, compatible servers (vLLM, SGLang…) `max_tokens`."""
    return {"max_completion_tokens" if host == "api.openai.com" else "max_tokens": max_tokens}


def _positive(value, name, cast):
    if value is None:
        return None
    result = cast(value)
    if result <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return result


def _openai_provider(model, base_url, extra_body, api_key=None, timeout=None, max_tokens=None):
    """OpenAIProvider with per-request timeout, a per-case wall-clock budget and
    bounded output. The SDK client keeps max_retries=0 and every call is blocking, so
    an expired budget aborts the request in place and never leaves work running."""
    internals = _openai_internals()
    from typesafe_sdk import TypeSafeError

    OpenAIProvider = internals["OpenAIProvider"]
    _OpenAIErrors = internals["_OpenAIErrors"]
    _response_format = internals["_response_format"]
    _responses_request_kwargs = internals["_responses_request_kwargs"]
    _responses_result = internals["_responses_result"]
    _result = internals["_result"]
    record_request = internals["record_request"]
    render_messages = internals["render_messages"]
    translating = internals["translating"]

    class BoundedProvider(OpenAIProvider):
        def __init__(self):
            super().__init__(model, base_url=base_url, api_key=api_key)
            self._clock = time.monotonic
            self._case_deadline = None
            self.case_attempts = 0
            self.case_last_error = None

        def start_case(self, case_timeout):
            """Arm the per-case budget; the adapter calls this once per decide()."""
            self._case_deadline = self._clock() + case_timeout if case_timeout else None
            self.case_attempts = 0
            self.case_last_error = None

        def _request_timeout(self):
            """min(timeout, remaining case budget); fails before opening a request
            when the case budget is already spent."""
            remaining = None
            if self._case_deadline is not None:
                remaining = self._case_deadline - self._clock()
                if remaining <= 0:
                    raise TypeSafeError(
                        f"case_timeout agotado tras {self.case_attempts} peticion(es)")
            limits = [t for t in (timeout, remaining) if t is not None]
            return min(limits) if limits else None

        def _chat_limit_kwarg(self):
            if max_tokens is None:
                return {}
            return _chat_max_tokens_kwarg(self._client.base_url.host, max_tokens)

        def request(self, messages, *, schema, structured):
            req_timeout = self._request_timeout()
            self.case_attempts += 1
            call_kwargs = {} if req_timeout is None else {"timeout": req_timeout}
            try:
                with translating(_OpenAIErrors.translate_error):
                    if self.api == "responses":
                        if extra_body:
                            raise TypeSafeError(
                                "extra_body solo tiene contrato en Chat Completions; "
                                "este endpoint resuelve a la API Responses")
                        kwargs = _responses_request_kwargs(
                            self.model_name, messages, schema, structured=structured)
                        if max_tokens is not None:
                            kwargs["max_output_tokens"] = max_tokens
                        record_request(kwargs, api=self.api)
                        return _responses_result(
                            self._client.responses.create(**kwargs, **call_kwargs))
                    kwargs = {"model": self.model_name, "messages": render_messages(messages),
                              "response_format": _response_format(schema, structured=structured),
                              **self._chat_limit_kwarg()}
                    if extra_body:
                        kwargs["extra_body"] = extra_body
                    record_request(kwargs, api=self.api)
                    response = self._client.chat.completions.create(**kwargs, **call_kwargs)
                return _result(response)
            except Exception as e:
                self.case_last_error = type(e).__name__
                raise

    return BoundedProvider()


class LLM(Adapter):
    def __init__(self, provider="openai", model="gpt-6-luna", mode="probabilities", structured=True,
                 normalize=True, retries_malformed=2, base_url=None, extra_body=None,
                 api_key=None, usd_in=None, usd_out=None, timeout=None, case_timeout=None,
                 max_tokens=None, **opts):
        super().__init__(**opts)
        load_env()
        import system_one_adapter
        import typesafe_sdk
        from system_one_adapter import SystemOneAdapterClient
        self.extra_body = json.loads(extra_body) if extra_body else {}
        self.provider, self.model, self.mode, self.base_url = provider, model, mode, base_url
        self.structured, self.normalize, self.retries_malformed = _bool(structured), _bool(normalize), int(retries_malformed)
        self.timeout = _positive(timeout, "timeout", float)
        self.case_timeout = _positive(case_timeout, "case_timeout", float)
        self.max_tokens = _positive(max_tokens, "max_tokens", int)
        price = PRICES.get(model, (None, None))
        self.usd_in = float(usd_in) if usd_in is not None else price[0]
        self.usd_out = float(usd_out) if usd_out is not None else price[1]
        self.versions = {"system_one_adapter": system_one_adapter.__version__,
                         "typesafe_sdk": getattr(typesafe_sdk, "__version__", None)}
        limits = any(v is not None for v in (self.timeout, self.case_timeout, self.max_tokens))
        if base_url or self.extra_body or limits:
            if provider != "openai":
                raise ValueError(
                    "base_url/extra_body/timeout/case_timeout/max_tokens solo están "
                    f"implementados para provider=openai, no {provider!r}")
            target = _openai_provider(model, base_url, self.extra_body, api_key,
                                      timeout=self.timeout, max_tokens=self.max_tokens)
            if self.extra_body and target.api != "chat_completions":
                raise ValueError(
                    "extra_body solo tiene contrato en Chat Completions; este endpoint "
                    "resuelve a la API Responses")
        else:
            target = model
        self.target = target
        self.client = SystemOneAdapterClient(structured_outputs=self.structured, llm_answer_mode=mode,
                                             normalize_probabilities=self.normalize,
                                             n_retry_malformed_structure=self.retries_malformed,
                                             provider=None if not isinstance(target, str) else provider)
        self.resolved = None

    def meta(self):
        return {"provider": self.provider, "model": self.model, "resolved": self.resolved, "mode": self.mode,
                "structured": self.structured, "normalize": self.normalize,
                "retries_malformed": self.retries_malformed, "base_url": self.base_url,
                "extra_body": redact_value(self.extra_body), "timeout": self.timeout,
                "case_timeout": self.case_timeout, "max_tokens": self.max_tokens,
                "usd_per_mtok": [self.usd_in, self.usd_out], **self.versions}

    def decide(self, state, questions):
        if hasattr(self.target, "start_case"):
            self.target.start_case(self.case_timeout)
        try:
            r = self.client.system_one(state=state, questions=questions, model=self.target)
        except Exception as e:
            diag = {"attempts": getattr(self.target, "case_attempts", None),
                    "provider_error": getattr(self.target, "case_last_error", None)}
            debug = getattr(e, "debug", None)
            if isinstance(debug, dict):
                cats = [c for c, _ in debug.get("retry_reasons", [])]
                if cats:
                    diag["retry_reasons"] = cats
            e.diag = {k: v for k, v in diag.items() if v} or None
            raise
        d = r.model_dump(mode="json")
        u = d["usage"]
        attempts = d["debug"].get("llm_attempts") or []
        resp = (attempts[-1].get("llm_response") or {}) if attempts else {}
        self.resolved = (resp.get("model") if isinstance(resp, dict) else None) or self.resolved
        tin, tout = u.get("input_tokens_total"), u.get("output_tokens_total")
        cost = (tin * self.usd_in + tout * self.usd_out) / 1e6 if None not in (tin, tout, self.usd_in, self.usd_out) else None
        return {"answers": d["answers"], "cost": cost, "model": self.resolved or self.model,
                "usage": {"input_tokens": tin, "output_tokens": tout, "n_retries": u.get("n_retries"),
                          "n_retries_malformed": u.get("n_retries_malformed_structure"),
                          "latency": u.get("latency"), "attempts": len(attempts)}}
