"""Any server that speaks TypeSafe's wire format over HTTP, e.g. Decider's
`scripts/serve.sh <model> 8000` or `decider.serve_vllm:app` (POST /v1/systemone).

  url=… path=/v1/systemone model=…
  extra=<json>         merged into the request body (e.g. the DiffusionGemma
                       structured_server's {"seed":42,"samples":"auto",…}); it may
                       not override `state`, `questions` or `model` (JEV-70)
  timeout=<s>          per-request timeout (default 600)
  capture_raw=<bool>   store the request body and the full response (usage,
                       diagnostics) in each case's `raw`; publish.py drops `raw`
                       from the public mirror
  rotate_choice=<int>  JEV-70: rotate the criteria keys of every choice question
                       N positions before sending (jevbench.rotation.rotate_choice);
                       labels, criteria and GT stay intact — only the order changes

HTTP errors keep the status and the (truncated) response body in `diag`, which
jevbench.run stores with the case.
"""
import json
import time
import urllib.error
import urllib.request

from . import Adapter
from ..rotation import rotate_choice as _rotate_choice
from ..rotation import rotation_manifest as _rotation_manifest

RESERVED = ("state", "questions", "model")
DIAG_BODY_MAX = 2048  # bytes del cuerpo guardado en diag, antes de decodificar


def _bool(v):
    return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")


class SystemOneHTTP(Adapter):
    def __init__(self, url="http://127.0.0.1:8000", path="/v1/systemone", model=None, extra=None,
                 timeout=600, capture_raw=False, rotate_choice=0, **opts):
        super().__init__(**opts)
        self.url, self.path, self.model = url.rstrip("/"), path, model
        self.extra = json.loads(extra) if isinstance(extra, str) else dict(extra or {})
        clash = [k for k in RESERVED if k in self.extra]
        if clash:
            raise ValueError(f"extra no puede pisar {clash}")
        self.timeout = float(timeout)
        if self.timeout <= 0:
            raise ValueError("timeout debe ser > 0")
        self.capture_raw = _bool(capture_raw)
        self.rotate_choice = int(rotate_choice or 0)
        self._perm_sha256 = None

    def meta(self):
        m = {"url": self.url + self.path, "model": self.model}
        if self.rotate_choice:
            m.update(rotate_choice=self.rotate_choice, perm_sha256=self._perm_sha256)
        return m

    def decide(self, state, questions):
        if self.rotate_choice:
            questions = _rotate_choice(questions, self.rotate_choice)
            self._perm_sha256 = _rotation_manifest(questions)["perm_sha256"]
        body = {**self.extra, "state": state, "questions": questions}
        if self.model:
            body["model"] = self.model
        req = urllib.request.Request(self.url + self.path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()
            text = body.decode("utf-8", "replace")
            err = RuntimeError(f"HTTP {e.code}: {text[:200]}")
            # 2048 bytes antes de decodificar; ignore no corta un multibyte a medias
            err.diag = {"http_status": e.code,
                        "body": body[:DIAG_BODY_MAX].decode("utf-8", "ignore")}
            raise err from e
        rec = {"answers": out["answers"], "cost": None, "model": out.get("model") or self.model,
               "server_ms": (time.time() - t0) * 1000}
        usage = out.get("usage")
        if isinstance(usage, dict):
            rec["usage"] = usage
        if self.capture_raw:
            rec["raw"] = {"request": body, "response": out}
        return rec
