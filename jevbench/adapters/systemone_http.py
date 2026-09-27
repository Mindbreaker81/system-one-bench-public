"""Any server that speaks TypeSafe's wire format over HTTP, e.g. Decider's
`scripts/serve.sh <model> 8000` or `decider.serve_vllm:app` (POST /v1/systemone)."""
import json
import time
import urllib.request

from . import Adapter


class SystemOneHTTP(Adapter):
    def __init__(self, url="http://127.0.0.1:8000", path="/v1/systemone", model=None, **opts):
        super().__init__(**opts)
        self.url, self.path, self.model = url.rstrip("/"), path, model

    def meta(self):
        return {"url": self.url + self.path, "model": self.model}

    def decide(self, state, questions):
        body = {"state": state, "questions": questions}
        if self.model:
            body["model"] = self.model
        req = urllib.request.Request(self.url + self.path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.loads(r.read())
        return {"answers": out["answers"], "cost": None, "model": out.get("model") or self.model,
                "server_ms": (time.time() - t0) * 1000}
