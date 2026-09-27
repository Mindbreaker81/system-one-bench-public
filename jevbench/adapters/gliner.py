"""fastino GLiNER2 / GLiNER2.5-Decide (pip install gliner2).

GLiNER classifies spans against label sets and has no free-text question, so
the wire question has to be packed into labels:
  labels=bare  -> legacy 24-sep behaviour: choice keys, score "0".."n", noul yes/no
  labels=desc  -> choice keys with their descriptions, score levels by their text,
                  noul yes/no with the question as the "yes" description
  score=ev     -> score = expected level from the renormalised confidences (default)
  score=argmax -> score = most likely level (legacy)
Probabilities: every label is scored (multi_label, threshold 0, confidences) and
renormalised; the argmax is the answer. Checked 26-sep on GLiNER2.5-Decide: the
argmax matches plain single-label classify_text in 190/190 answers.
"""
from . import Adapter


class Gliner(Adapter):
    def __init__(self, model="fastino/GLiNER2.5-Decide", labels="desc", device=None, score="ev", **opts):
        super().__init__(**opts)
        self.score = score  # ev = expected level (like Jev's score); argmax = legacy 24-sep behaviour
        from gliner2 import AutoExtractor
        self.model_id, self.labels = model, labels
        self.m = AutoExtractor.from_pretrained(model)
        if device:
            self.m.to(device)
        self.m.eval()
        self.device = device

    def meta(self):
        return {"model": self.model_id, "labels": self.labels, "device": self.device, "score": self.score}

    def _task(self, q):
        """-> (schema entry, [label strings], [wire keys])"""
        t = q["type"]
        if t == "choice":
            keys = list(q["criteria"])
            if self.labels == "desc":
                labs = {k: (v.get("what") if isinstance(v, dict) else v) or k for k, v in q["criteria"].items()}
                return {"labels": labs, "multi_label": True, "cls_threshold": 0.0}, keys, keys
            return {"labels": keys, "multi_label": True, "cls_threshold": 0.0}, keys, keys
        if t == "score":
            keys = [str(i) for i in range(len(q["criteria"]))]
            labs = list(q["criteria"]) if self.labels == "desc" else keys
            return {"labels": labs, "multi_label": True, "cls_threshold": 0.0}, labs, keys
        labs = ["yes", "no"]
        if self.labels == "desc":
            return ({"labels": {"yes": q["instructions"], "no": "no / not the case"},
                     "multi_label": True, "cls_threshold": 0.0}, labs, ["1", "0"])
        return {"labels": labs, "multi_label": True, "cls_threshold": 0.0}, labs, ["1", "0"]

    def decide(self, state, questions):
        schema, maps = {}, {}
        for name, q in questions.items():
            schema[name], labs, keys = self._task(q)
            maps[name] = dict(zip(labs, keys))
        raw = self.m.classify_text(state, schema, include_confidence=True)
        ans = {}
        for name, q in questions.items():
            items = raw[name]
            items = items if isinstance(items, list) else [items]
            conf = {maps[name][it["label"]]: float(it["confidence"]) for it in items if it["label"] in maps[name]}
            for k in maps[name].values():
                conf.setdefault(k, 0.0)
            s = sum(conf.values()) or 1.0
            probs = {k: v / s for k, v in conf.items()}
            top = max(probs, key=probs.get)
            if q["type"] == "choice":
                ans[name] = {"choice": top, "probabilities": probs}
            elif q["type"] == "score":
                val = float(top) if self.score == "argmax" else sum(int(k) * p for k, p in probs.items())
                ans[name] = {"score": val, "probabilities": probs}
            else:
                ans[name] = {"noul": probs["1"]}
        return {"answers": ans, "cost": None, "model": self.model_id, "raw": raw}
