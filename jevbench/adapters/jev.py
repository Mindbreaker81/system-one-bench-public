"""Jev through OpenRouter (legacy rerun_jev.py call) or TypeSafe's own API.

  provider=openrouter  POST openrouter.ai/api/alpha/decisions, model ~typesafe/jev-latest,
                       OPENROUTER_API_KEY; cost comes back in usage.cost
  provider=typesafe    POST api.typesafe.ai/v1/systemone, model jev-latest,
                       TYPESAFE_API_KEY; cost = input tokens x $0.042/Mtok (output is free)
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import Adapter
from ..env import load_env

PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/alpha/decisions", "OPENROUTER_API_KEY", "~typesafe/jev-latest"),
    "typesafe": ("https://api.typesafe.ai/v1/systemone", "TYPESAFE_API_KEY", "jev-latest"),
}
TYPESAFE_USD_PER_INPUT_TOKEN = 0.042 / 1e6


class Jev(Adapter):
    def __init__(self, provider="openrouter", model=None, retries=3, pause=0.3, **opts):
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
        return {"provider": self.provider, "model": self.model, "resolved": self.resolved, "endpoint": self.url}

    def decide(self, state, questions):
        body = json.dumps({"model": self.model, "state": state, "questions": questions}).encode()
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(self.url, data=body, headers={
                    "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    out = json.loads(r.read())
                break
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries - 1:
                    detail = e.read().decode()[:300] if isinstance(e, urllib.error.HTTPError) else ""
                    raise RuntimeError(f"{e} {detail}") from e
                time.sleep(2 * (attempt + 1))
        time.sleep(self.pause)
        self.resolved = out.get("model") or self.resolved
        usage = out.get("usage") or {}
        cost = usage.get("cost")
        if cost is None and self.provider == "typesafe" and "input_tokens" in usage:
            cost = usage["input_tokens"] * TYPESAFE_USD_PER_INPUT_TOKEN
        return {"answers": out["answers"], "cost": cost, "model": out.get("model"), "usage": usage}
