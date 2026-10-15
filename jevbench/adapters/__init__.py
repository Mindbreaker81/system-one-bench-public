"""Model adapters. Each one takes TypeSafe wire-format questions and returns
wire-format answers, so the battery and the scorer never see model specifics.

Interface:
    class X(Adapter):
        def __init__(self, **opts)          # opts come from --opt k=v on the CLI
        def meta(self) -> dict              # model id, version, device, dtype...
        def decide(self, state, questions) -> dict
            # {"answers": {q: {"choice"|"score"|"noul": ..., "probabilities": {...}}},
            #  "cost": float|None, "model": str|None}

Common option (base class): choice_order=<qid>:<orden> (JEV-103; same
semantics as the `jev` adapter's JEV-82 option) reorders the criteria keys of
the named choice questions before the adapter builds prompt, schema or wire
payload — a frozen named order (d0..d3, jevbench.rotation.NAMED_ORDERS) or a
comma-separated label list. Labels, criteria texts and GT stay intact; with
the option unset, decide() receives `questions` untouched and meta() carries
no order fields.
"""
import importlib

from ..rotation import (order_manifest as _order_manifest,
                        reorder_choice as _reorder_choice,
                        resolve_choice_order as _resolve_choice_order)

REGISTRY = {
    "jev": "jevbench.adapters.jev:Jev",
    "systemone_http": "jevbench.adapters.systemone_http:SystemOneHTTP",
    "decider": "jevbench.adapters.decider:DeciderLocal",
    "laya": "jevbench.adapters.laya:Laya",
    "anyjev": "jevbench.adapters.anyjev:AnyJev",
    "gliner": "jevbench.adapters.gliner:Gliner",
    "julia": "jevbench.adapters.julia:Julia",
    "llm": "jevbench.adapters.llm:LLM",
    "respan": "jevbench.adapters.respan:Respan",
    "nimble": "jevbench.adapters.nimble:Nimble",
    "tev1": "jevbench.adapters.tev1:Tev1",
    "clef": "jevbench.adapters.clef:Clef",
    "openai_decisions": "jevbench.adapters.openai_decisions:OpenAIDecisions",
}


class Adapter:
    def __init__(self, choice_order=None, **opts):
        self.opts = opts
        self.choice_order = (_resolve_choice_order(choice_order)
                             if choice_order else None)
        self._perm_sha256 = None

    def meta(self):
        return {}

    def _apply_choice_order(self, questions):
        """`questions` with `choice_order` applied (a new dict), or the same
        object untouched when the option is not set. Records the manifest of
        the order actually sent so `_order_meta` can report it."""
        if not self.choice_order:
            return questions
        questions = _reorder_choice(questions, self.choice_order)
        self._perm_sha256 = _order_manifest(
            questions, self.choice_order)["perm_sha256"]
        return questions

    def _order_meta(self):
        """meta() fields for the order option — only when it is set, so a run
        without it keeps the meta byte-identical to before."""
        if not self.choice_order:
            return {}
        return {"choice_order": self.choice_order,
                "perm_sha256": self._perm_sha256}

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
