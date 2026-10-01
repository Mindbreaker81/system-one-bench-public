"""Span-01 / Span-01 Lite (Respan). Dos caminos:

  provider=respan      POST api.respan.ai/api/v1/scores, RESPAN_API_KEY.
                       API nativa: puntúa definiciones de comportamiento en
                       lenguaje natural sobre un "span" en una sola pasada,
                       devolviendo p_present / p_absent / p_not_observable.
                       Modelos: span-01-pro (necesita créditos Respan,
                       $0.02/M input) y span-01-free (Lite).
  provider=openrouter  POST openrouter.ai/api/alpha/decisions, OPENROUTER_API_KEY.
                       Mismo endpoint que el adaptador jev; Respan solo acepta
                       preguntas noul, así que choice/score se expanden a una
                       noul por opción ("... Correct: \"X\"") y se renormalizan.

  Mapeo en ambos caminos: noul -> una definición, choice/score -> una por
  opción. En nativo, p = p_present / (p_present + p_absent): "not observable"
  cuenta como falta de evidencia (->0.5), no como "no". El `state` va a
  span.input[0] y span.output es un turno de asistente vacío, así que las
  definiciones se enmarcan como "In the input text: ...".
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import Adapter
from ..env import load_env

PROVIDERS = {
    "respan": ("https://api.respan.ai", "RESPAN_API_KEY", "span-01-pro"),
    "openrouter": ("https://openrouter.ai", "OPENROUTER_API_KEY", "respan/span-01"),
}
USD_PER_INPUT_TOKEN = {"span-01-pro": 0.02 / 1e6}


def _present(r):
    den = r["p_present"] + r["p_absent"]
    return r["p_present"] / den if den > 0 else 0.5


class Respan(Adapter):
    def __init__(self, provider="respan", model=None, retries=4, pause=0.3, **opts):
        super().__init__(**opts)
        load_env()
        self.url, key_var, default_model = PROVIDERS[provider]
        self.key = os.environ.get(key_var)
        if not self.key:
            raise SystemExit(f"{key_var} not set (put it in .env)")
        self.provider, self.model = provider, model or default_model
        self.retries, self.pause = int(retries), float(pause)
        self.resolved = None

    def meta(self):
        return {"provider": self.provider, "model": self.model, "resolved": self.resolved,
                "endpoint": self.url + ("/api/alpha/decisions" if self.provider == "openrouter"
                                        else "/api/v1/scores")}

    @staticmethod
    def _defs(name, q):
        """Typed question -> {behavior_id: definition} (noul keeps its own id)."""
        instr = q["instructions"]
        if q["type"] == "noul":
            return {name: instr}
        items = q["criteria"].items() if q["type"] == "choice" else enumerate(q["criteria"])
        defs = {}
        for k, crit in items:
            desc = crit.get("what", "") if isinstance(crit, dict) else crit
            label = k if q["type"] == "choice" else str(desc).split(":", 1)[0].strip()
            det = f" ({desc})" if desc else ""
            defs[f"{name}__{k}"] = f'{instr} Correct: "{label}"{det}.'
        return defs

    def _post(self, path, body):
        data = json.dumps(body).encode()
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(
                    self.url + path, data=data,
                    headers={"Authorization": f"Bearer {self.key}",
                             "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.loads(r.read())
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries - 1:
                    detail = e.read().decode()[:300] if isinstance(e, urllib.error.HTTPError) else ""
                    raise RuntimeError(f"{e} {detail}") from e
                retry_after = getattr(e, "headers", None) and e.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2 * (attempt + 1))

    @staticmethod
    def _multi(name, q, s, raw):
        keys = list(q["criteria"]) if q["type"] == "choice" else range(len(q["criteria"]))
        tot = sum(s) or 1.0
        probs = {str(k): v / tot for k, v in zip(keys, s)}
        best = max(probs, key=probs.get)
        if q["type"] == "choice":
            return {"choice": best, "probabilities": probs, "respan_raw": raw}
        return {"score": float(best), "probabilities": probs, "respan_raw": raw}

    def _decide_respan(self, state, questions):
        defs = {}
        for name, q in questions.items():
            for bid, d in self._defs(name, q).items():
                defs[bid] = f"In the input text: {d}"
        out = self._post("/api/v1/scores", {
            "model": self.model,
            "span": {"input": [{"role": "user", "content": state}],
                     "output": {"role": "assistant", "content": ""}},
            "behaviors": [{"id": i, "definition": d} for i, d in defs.items()]})
        res = {r["id"]: r for r in out["results"]}
        answers = {}
        for name, q in questions.items():
            if q["type"] == "noul":
                answers[name] = {"noul": _present(res[name]), "respan_raw": res[name]}
            else:
                keys = list(q["criteria"]) if q["type"] == "choice" else range(len(q["criteria"]))
                answers[name] = self._multi(
                    name, q, [_present(res[f"{name}__{k}"]) for k in keys],
                    {str(k): res[f"{name}__{k}"] for k in keys})
        usage = out.get("usage") or {}
        in_tok = usage.get("input_tokens")
        cost = in_tok * USD_PER_INPUT_TOKEN[self.model] if in_tok and self.model in USD_PER_INPUT_TOKEN else 0.0
        return answers, usage.get("cost", cost), out.get("model"), usage

    def _decide_openrouter(self, state, questions):
        defs = {name: d for name, q in questions.items() for name, d in self._defs(name, q).items()}
        wire = {bid: {"type": "noul", "instructions": d} for bid, d in defs.items()}
        out = self._post("/api/alpha/decisions",
                         {"model": self.model, "state": state, "questions": wire})
        got = out["answers"]
        answers = {}
        for name, q in questions.items():
            if q["type"] == "noul":
                answers[name] = {"noul": float(got[name]["noul"])}
            else:
                keys = list(q["criteria"]) if q["type"] == "choice" else range(len(q["criteria"]))
                answers[name] = self._multi(
                    name, q, [float(got[f"{name}__{k}"]["noul"]) for k in keys], None)
        usage = out.get("usage") or {}
        return answers, usage.get("cost"), out.get("model"), usage

    def decide(self, state, questions):
        fn = self._decide_openrouter if self.provider == "openrouter" else self._decide_respan
        answers, cost, model, usage = fn(state, questions)
        self.resolved = model or self.resolved
        time.sleep(self.pause)
        return {"answers": answers, "cost": cost, "model": model, "usage": usage}
