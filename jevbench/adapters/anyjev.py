"""AnyJev (Nokia) over a local HF model: wire questions -> anyjev.Question -> wire answers.
Mirrors legacy anyjev_run.py (options rendered as 'label - description')."""
from . import Adapter, option_list


class AnyJev(Adapter):
    def __init__(self, model="Qwen/Qwen3-1.7B", level="L0", device="cuda", dtype="bfloat16", batch_size=8, **opts):
        super().__init__(**opts)
        from anyjev import Decider
        from anyjev.backends.hf import HFBackend
        self.model, self.level, self.device, self.dtype = model, level, device, dtype
        self.dec = Decider(HFBackend(model, device=device, dtype=dtype, batch_size=int(batch_size)), level=level)

    def meta(self):
        import anyjev
        return {"model": self.model, "level": self.level, "device": self.device, "dtype": self.dtype,
                "anyjev_version": getattr(anyjev, "__version__", None)}

    def _questions(self, questions):
        from anyjev import Question
        qs, spec = [], {}
        for name, q in questions.items():
            if q["type"] == "choice":
                labels, texts = option_list(q)
                qs.append(Question.choice(q["instructions"], texts, name=name))
                spec[name] = (labels, texts)
            elif q["type"] == "score":
                qs.append(Question.score(q["instructions"], levels=list(q["criteria"]), name=name))
                spec[name] = list(q["criteria"])
            else:
                qs.append(Question.noul(q["instructions"], name=name))
        return qs, spec

    def decide(self, state, questions):
        qs, spec = self._questions(questions)
        ds = self.dec.decide(state, qs)
        ans = {}
        for name, q in questions.items():
            d = ds[name]
            if q["type"] == "choice":
                labels, texts = spec[name]
                probs = {lab: float(d.distribution.get(t, 0.0)) for lab, t in zip(labels, texts)}
                ans[name] = {"choice": max(probs, key=probs.get), "probabilities": probs}
            elif q["type"] == "score":
                ans[name] = {"score": float(d.value),
                             "probabilities": {str(i): float(d.distribution[lv]) for i, lv in enumerate(spec[name])}}
            else:
                ans[name] = {"noul": float(d.p_true)}
        return {"answers": ans, "cost": None, "model": self.model}
