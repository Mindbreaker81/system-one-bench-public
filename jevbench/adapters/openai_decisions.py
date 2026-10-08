"""OpenAI's native Decisions API (public beta) through the official SDK
(openai==3.26.0, in .venv-oai — kept separate from .venv-llm, which pins
openai 3.16.2 for system-one-adapter): client.decisions.create(model,
input, questions), model gpt-6-luna, OPENAI_API_KEY.

Same "System One" contract the battery uses elsewhere (JEV-78): each typed
question maps to the API's predicate/choice/score and the answers normalize
back to the wire format (noul, choice per label, score level by index). The
battery has no global instructions, so `input` carries the state verbatim
and each question's `instructions` carries its text.

Refusal is PER QUESTION here («the host may decline one question»), unlike
the OpenRouter route where the refusal was a case-level 502. An answers[]
entry with type "refusal" is kept as a marker ({"type": "refusal"}) and the
case is stored with `refusals` — the refused question scores 0 as an error
on its question and the case is preserved (pre-registry
docs/infra_runs/openai_decisions_jev78.md). A response where EVERY question
is refused is the whole-case refusal — ProviderRefusal, classified
`rejection` by the JEV-78 classifier (jevbench/jev78.py) from the
`ProviderRefusal:` prefix. Answers that break the contract (duplicate
names, partial vectors, alien labels, out-of-range scalars) raise
ContractError — a local error, never a partial success.

  retries=3                  requests per decide; SDK errors with a
                             retriable status (429, 5xx), SDK
                             connection/timeout errors and responses
                             carrying refusals share the budget — same
                             acquisition policy as the OpenRouter cell
                             (one decide = 1-3 requests). Non-retriable
                             4xx fail fast. The SDK's own retries are
                             disabled (max_retries=0) so every attempt
                             and its cost stay visible.
  pause=0.3                  pause after each decide
  timeout=120                per-request socket timeout (seconds)
  choice_order=<qid>:<orden> like the jev adapter (JEV-82 semantics): reorders
                             the criteria keys of the named choice question —
                             the API `choices` array follows that order;
                             d0 = byte-identical to no option

Cost: the API bills input tokens only ($0.10/Mtok); usage.cost is honoured
when present, otherwise cost = input_tokens x rate — accumulated across
the attempts of each decide, refusals included, so a rejected decide still
reports what it spent. EVERY terminal outcome of decide carries the
informed spend in `e.cost` (ProviderRefusal, the wrapped RuntimeError of a
terminal SDK failure, ContractError and non-SDK errors alike — R58c §1):
`e.cost` reaches the stored record and the run's cost guard; what the
provider did not report stays unknown (None). Provenance (rule 4):
`model` in the response resolves the version and any model/version
response headers land in meta()["api_headers"].
"""
import math
import os
import time

from . import Adapter
from ..env import load_env
from ..rotation import (order_manifest as _order_manifest,
                        reorder_choice as _reorder_choice,
                        resolve_choice_order as _resolve_choice_order)

BASE_URL = "https://api.openai.com/v1"
KEY_VAR = "OPENAI_API_KEY"
USD_PER_INPUT_TOKEN = 0.10 / 1e6


class ProviderRefusal(RuntimeError):
    """Whole-case refusal: every question came back as an `answers[]` entry
    with type "refusal" — the native equivalent of the OpenRouter 502
    «refused to answer». The stored error starts with this class name,
    which is what classifies the record as a rejection. `cost` carries the
    informed spend of the attempts of the decide that raised it (None when
    the API reported none), so the rejection does not lose known
    telemetry."""

    def __init__(self, names):
        names = list(names)
        self.diag = {"refusal": names}
        self.cost = None
        word = "question" if len(names) == 1 else "questions"
        super().__init__(f"OpenAI refused to answer {word} "
                         + ", ".join(f'"{n}"' for n in names))


class ContractError(ValueError):
    """Local contract violation: the response cannot be normalized to the
    battery wire format (missing/duplicate names, changed types, partial
    probability vectors, alien labels or indices, out-of-range scalars).
    Messages start with «contract(local):» so the record classifies as
    `local` — never `rejection`, never a silent partial vector."""


def api_questions(questions):
    """Battery wire questions -> Decisions API `questions[]` (order kept)."""
    out = []
    for name, q in questions.items():
        t = q["type"]
        if t == "noul":
            out.append({"type": "predicate", "name": name,
                        "instructions": q["instructions"]})
        elif t == "choice":
            choices = []
            for label, crit in q["criteria"].items():
                if isinstance(crit, dict):
                    crit = crit.get("what")
                choices.append({"value": label, "description": crit or label})
            out.append({"type": "choice", "name": name,
                        "instructions": q["instructions"], "choices": choices})
        elif t == "score":
            levels = []
            for crit in q["criteria"]:
                text = crit if isinstance(crit, str) else str(crit)
                label, sep, desc = text.partition(":")
                levels.append({"label": label.strip(),
                               "description": (desc if sep else label).strip()})
            out.append({"type": "score", "name": name,
                        "instructions": q["instructions"], "levels": levels})
        else:
            raise ContractError(
                f"contract(local): tipo de pregunta desconocido {t!r}")
    return out


def _num(x, lo, hi, what):
    """Finite real scalar in [lo, hi] — bool is not a number here."""
    if (isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or not lo <= x <= hi):
        raise ContractError(f"contract(local): {what} fuera de rango "
                            f"[{lo}, {hi}]: {x!r}")
    return float(x)


def _probs(a, expected, qname):
    """[{value, probability}] -> {str(value): p}, checked against the
    contract: the key set must be exactly `expected` — a partial vector,
    an alien label/index or a duplicated key is a local contract error,
    never a silently dropped component."""
    raw = a.get("probabilities")
    if not isinstance(raw, list):
        raise ContractError(
            f"contract(local): {qname} probabilities no es una lista")
    probs = {}
    for p in raw:
        if not isinstance(p, dict) or "value" not in p:
            raise ContractError(
                f"contract(local): {qname} probabilities con entrada "
                f"sin value: {p!r}")
        k = str(p["value"])
        if k in probs:
            raise ContractError(
                f"contract(local): {qname} probabilities duplica {k!r}")
        probs[k] = _num(p.get("probability"), 0.0, 1.0,
                        f"{qname} probabilities[{k!r}]")
    if set(probs) != set(expected):
        raise ContractError(
            f"contract(local): {qname} probabilities con etiquetas "
            f"{sorted(probs)} — esperadas {sorted(map(str, expected))}")
    return probs


def wire_answers(answers, questions):
    """Decisions API answers[] -> (wire_answers, refused_names), keyed by
    the `name` each question was sent with. An entry with type "refusal"
    becomes the marker {"type": "refusal"} — the refusal is per question,
    the rest of the case is preserved; whether a full refusals set is the
    whole-case rejection (ProviderRefusal) is `decide`'s call. Names must
    be unambiguous (a repeated `name` is a contract error) and every
    non-refused answer must match its question's contract — complete
    probability vectors over exactly the criteria labels (choice) or level
    indices (score), a `choice` inside the criteria and finite scalars in
    range. Any violation raises ContractError — a "local" error, never a
    silent partial vector."""
    if not isinstance(answers, list):
        raise ContractError("contract(local): answers no es una lista")
    by_name = {}
    for a in answers:
        if not isinstance(a, dict) or not isinstance(a.get("name"), str):
            raise ContractError(
                f"contract(local): answers con entrada sin name: {a!r}")
        if a["name"] in by_name:
            raise ContractError(
                f"contract(local): answers duplica el name {a['name']!r}")
        by_name[a["name"]] = a
    missing = [name for name in questions if name not in by_name]
    if missing:
        raise ContractError(f"contract(local): answers sin {missing}")
    out, refused = {}, []
    for name, q in questions.items():
        a, t = by_name[name], q["type"]
        if a.get("type") == "refusal":
            out[name] = {"type": "refusal"}
            refused.append(name)
            continue
        want = {"noul": "predicate", "choice": "choice", "score": "score"}[t]
        if a.get("type") != want:
            raise ContractError(
                f"contract(local): {name} llegó {a.get('type')!r}, "
                f"esperado {want!r}")
        if t == "noul":
            out[name] = {"type": "noul",
                         "noul": _num(a.get("probability"), 0.0, 1.0,
                                      f"{name} probability")}
        elif t == "choice":
            choice = a.get("choice")
            if choice not in q["criteria"]:
                raise ContractError(
                    f"contract(local): {name} choice {choice!r} ajeno a "
                    f"los criterios")
            out[name] = {"type": "choice", "choice": choice,
                         "probabilities": _probs(a, q["criteria"], name)}
        else:
            idx = [str(i) for i in range(len(q["criteria"]))]
            out[name] = {"type": "score",
                         "score": _num(a.get("score"), 0.0, len(idx) - 1.0,
                                       f"{name} score"),
                         "legend": {str(i): c for i, c in
                                    enumerate(q["criteria"])},
                         "probabilities": _probs(a, idx, name)}
        if "confidence" in a:
            out[name]["confidence"] = _num(a["confidence"], 0.0, 1.0,
                                           f"{name} confidence")
    return out, refused


def _usage_cost(usage):
    """Informed cost of ONE response: usage.cost honoured when present,
    otherwise input_tokens x the input rate; None when nothing usable is
    reported."""
    usage = usage or {}
    cost = usage.get("cost")
    if cost is None and isinstance(usage.get("input_tokens"), (int, float)) \
            and not isinstance(usage["input_tokens"], bool):
        cost = usage["input_tokens"] * USD_PER_INPUT_TOKEN
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) \
            or not math.isfinite(cost):
        return None
    return float(cost)


def _status_of(e):
    """HTTP status of an SDK APIStatusError, else None."""
    s = getattr(e, "status_code", None)
    return s if isinstance(s, int) and not isinstance(s, bool) else None


def _retryable(e):
    """Fixed retry policy (pre-registry §2): retriable = HTTP 429 or 5xx
    (the SDK's APIStatusError carries .status_code) and the SDK
    connection/timeout errors (recognized by class name so no SDK import is
    needed here). Non-retriable 4xx and non-SDK errors propagate."""
    status = _status_of(e)
    if status is not None:
        return status == 429 or status >= 500
    return type(e).__name__ in ("APIConnectionError", "APITimeoutError")


def _sdk(e):
    """True si la excepción viene del SDK openai (status o nombre de clase
    reconocible) — los errores ajenos al SDK (pydantic, bugs) propagan sin
    envolver."""
    return _status_of(e) is not None or type(e).__name__.startswith(
        ("API", "RateLimit", "BadRequest", "Authentication", "PermissionDenied",
         "NotFound", "Unprocessable", "InternalServer", "Conflict"))


class OpenAIDecisions(Adapter):
    def __init__(self, model="gpt-6-luna", retries=3, pause=0.3, timeout=120,
                 choice_order=None, _client=None, **opts):
        super().__init__(**opts)
        load_env()
        self.key = os.environ.get(KEY_VAR)
        if not self.key:
            raise SystemExit(f"{KEY_VAR} not set (put it in .env)")
        self.model = model
        self.retries = int(retries)
        self.pause = float(pause)
        self.timeout = float(timeout)
        self.choice_order = (_resolve_choice_order(choice_order)
                             if choice_order else None)
        self.resolved = None
        self._perm_sha256 = None
        self._api_headers = {}
        self._client = _client

    def _sdk_client(self):
        """Lazy import (JEV-78): the official SDK lives in .venv-oai
        (openai==3.26.0). The SDK's own retry layer stays off — every
        attempt must keep its usage visible for the cost guard."""
        try:
            from openai import OpenAI
        except ImportError:
            raise SystemExit(
                "openai SDK no instalado — usa .venv-oai "
                "(python3 -m venv .venv-oai && "
                ".venv-oai/bin/pip install openai==3.26.0)")
        return OpenAI(api_key=self.key, base_url=BASE_URL,
                      timeout=self.timeout, max_retries=0)

    def meta(self):
        return {"provider": "openai", "model": self.model,
                "resolved": self.resolved, "endpoint": BASE_URL,
                "sdk": "openai-python",
                "choice_order": self.choice_order,
                "perm_sha256": self._perm_sha256,
                "api_headers": dict(self._api_headers)}

    def decide(self, state, questions):
        if self.choice_order:
            questions = _reorder_choice(questions, self.choice_order)
            self._perm_sha256 = _order_manifest(
                questions, self.choice_order)["perm_sha256"]
        if self._client is None:
            self._client = self._sdk_client()
        api_qs = api_questions(questions)
        spent, informed, out, answers, refused = 0.0, False, {}, None, None
        for attempt in range(self.retries):
            try:
                raw = self._client.decisions.with_raw_response.create(
                    model=self.model, input=state, questions=api_qs)
                resp = raw.parse()
                for k, v in raw.headers.items():
                    if "model" in k.lower() or "version" in k.lower():
                        self._api_headers[k] = v
                out = resp.model_dump()
                cost = _usage_cost(out.get("usage"))
                if cost is not None:
                    spent, informed = spent + cost, True
                answers, refused = wire_answers(out.get("answers") or [],
                                                questions)
                if refused and attempt < self.retries - 1:
                    # refusal shares the attempts budget — same policy as
                    # the OpenRouter cell retrying its 502s inside decide
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except ContractError as e:
                # respuesta pagada que fracasa en la validación local: lo
                # informado no se pierde (R58c §1)
                e.cost = spent if informed else None
                raise
            except Exception as e:
                if not _sdk(e):
                    e.cost = spent if informed else None
                    raise
                if _retryable(e) and attempt < self.retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                status = _status_of(e)
                err = (RuntimeError(f"HTTP Error {status}: {str(e)[:250]}")
                       if status is not None
                       else RuntimeError(f"{type(e).__name__}: {e}"))
                # desenlace terminal con la misma clase/mensaje de siempre
                # (la clasificación no cambia), pero llevando el gasto
                # informado ya acumulado del decide — una negativa pagada
                # seguida de timeout o 4xx no borra lo ya gastado
                err.cost = spent if informed else None
                raise err from e
        if refused is not None and len(refused) == len(questions):
            e = ProviderRefusal(refused)
            e.cost = spent if informed else None
            raise e
        time.sleep(self.pause)
        self.resolved = out.get("model") or self.resolved
        rec = {"answers": answers,
               "cost": spent if informed else None,
               "model": out.get("model"), "usage": out.get("usage") or {}}
        if refused:
            rec["refusals"] = refused
        return rec
