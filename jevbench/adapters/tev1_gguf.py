"""Contrato de Tev1 (una letra por decisión; ver `tev1.py`) sobre un modelo GGUF servido por
`llama-server` (llama.cpp), para equipos pequeños (Jetson Orin Nano) con pesos cuantizados.

El prompt se renderiza aquí con el tokenizador de Hugging Face del modelo base (misma plantilla
de chat y `enable_thinking=false` que `tev1.py`) y se envía en crudo a `/completion` con
`n_predict=1` y `n_probs`; las probabilidades del primer token se leen por id de token y se
renormalizan solo sobre las letras permitidas (como el softmax restringido de `tev1.py`). Una letra
fuera del top-`n_probs` recibe la probabilidad mínima devuelta (se cuenta en `raw.missing`).

Opciones: base (ruta o repo HF del tokenizador), url (llama-server), model (etiqueta del GGUF),
quant, n_probs, timeout, choice_order (base Adapter)."""
import json
import time
import urllib.request

from . import Adapter
from .tev1 import LETTERS, SYSTEM, _options


class Tev1GGUF(Adapter):
    def __init__(self, base, url="http://127.0.0.1:8080", model=None, quant=None,
                 n_probs=100, timeout=600, **opts):
        super().__init__(**opts)
        from transformers import AutoTokenizer
        self.base, self.url, self.model_id, self.quant = base, url.rstrip("/"), model, quant
        self.n_probs, self.timeout = int(n_probs), float(timeout)
        self.tok = AutoTokenizer.from_pretrained(base)
        self.server = self._get("/props")
        self.missing = 0

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.url + path, timeout=30) as r:
                d = json.loads(r.read())
            return {"build": d.get("build_info"), "n_ctx": (d.get("default_generation_settings") or {}).get("n_ctx"),
                    "model_path": d.get("model_path")}
        except Exception as e:  # meta informativa; no bloquea
            return {"error": str(e)[:200]}

    def meta(self):
        import transformers
        return {"model": self.model_id, "quant": self.quant, "base_tokenizer": self.base,
                "server": self.server, "n_probs": self.n_probs,
                "generations_per_state": "1 por pregunta (autoregresivo)",
                "sampling": "n_predict=1, temperature=0, enable_thinking=false",
                "transformers": transformers.__version__, **self._order_meta()}

    def _post(self, body):
        req = urllib.request.Request(self.url + "/completion", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def _letter_probs(self, state, q):
        options, keys = _options(None, q)
        decision = {"state": state, "question": q["instructions"], "options": options}
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps(decision, ensure_ascii=False)}]
        prompt = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                              enable_thinking=False)
        letters = LETTERS[:len(options)]
        ids = self.tok.encode(prompt, add_special_tokens=False)
        cand = []
        for letter in letters:
            combined = self.tok.encode(prompt + letter, add_special_tokens=False)
            suffix = combined[len(ids):]
            if combined[:len(ids)] != ids or len(suffix) != 1:
                raise ValueError(f"La letra {letter} no es un token único tras el prompt")
            cand.append(suffix[0])
        out = self._post({"prompt": ids, "n_predict": 1, "n_probs": self.n_probs, "temperature": 0,
                          "cache_prompt": True, "post_sampling_probs": False})
        top = out["completion_probabilities"][0]["top_logprobs"]
        lp = {t["id"]: t["logprob"] for t in top}
        floor = min(lp.values())
        vals = []
        for c in cand:
            if c not in lp:
                self.missing += 1
            vals.append(lp.get(c, floor))
        m = max(vals)
        ex = [pow(2.718281828459045, v - m) for v in vals]
        s = sum(ex)
        return keys, [e / s for e in ex]

    def decide(self, state, questions):
        questions = self._apply_choice_order(questions)
        ans = {}
        for name, q in questions.items():
            keys, probs = self._letter_probs(state, q)
            best = max(range(len(keys)), key=lambda i: probs[i])
            dist = {k: float(p) for k, p in zip(keys, probs)}
            if q["type"] == "noul":
                ans[name] = {"noul": float(probs[keys.index("yes")])}
            elif q["type"] == "choice":
                ans[name] = {"choice": keys[best], "probabilities": dist}
            else:
                ans[name] = {"score": sum(i * p for i, p in enumerate(probs)), "probabilities": dist}
        return {"answers": ans, "cost": None, "model": self.model_id,
                "raw": {"generations": len(questions), "missing_letters_total": self.missing}}
