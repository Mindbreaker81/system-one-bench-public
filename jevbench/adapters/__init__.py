"""Model adapters. Each one takes TypeSafe wire-format questions and returns
wire-format answers, so the battery and the scorer never see model specifics.

Interface:
    class X(Adapter):
        def __init__(self, **opts)          # opts come from --opt k=v on the CLI
        def meta(self) -> dict              # model id, version, device, dtype...
        def decide(self, state, questions) -> dict
            # {"answers": {q: {"choice"|"score"|"noul": ..., "probabilities": {...}}},
            #  "cost": float|None, "model": str|None}
"""
import importlib

REGISTRY = {
    "jev": "jevbench.adapters.jev:Jev",
    "systemone_http": "jevbench.adapters.systemone_http:SystemOneHTTP",
    "decider": "jevbench.adapters.decider:DeciderLocal",
    "laya": "jevbench.adapters.laya:Laya",
    "anyjev": "jevbench.adapters.anyjev:AnyJev",
    "gliner": "jevbench.adapters.gliner:Gliner",
    "julia": "jevbench.adapters.julia:Julia",
}


class Adapter:
    def __init__(self, **opts):
        self.opts = opts

    def meta(self):
        return {}

    def decide(self, state, questions):
        raise NotImplementedError


def get(name):
    mod, cls = REGISTRY[name].split(":")
    return getattr(importlib.import_module(mod), cls)


def option_list(q):
    """(labels, texts) for a choice question; text = 'label - description' like anyjev_run.py."""
    crit = q["criteria"]
    labels = list(crit)
    texts = []
    for k in labels:
        d = crit[k]
        if isinstance(d, dict):
            d = d.get("what")
        texts.append(f"{k} - {d}" if d else k)
    return labels, texts
