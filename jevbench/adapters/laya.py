"""convaiinnovations/laya (pip install laya). variant: router | en | multilingual | typed-decisions.
Legacy runs used `multilingual` for ES and the English root for EN."""
import os

from . import Adapter

os.environ.setdefault("USE_TF", "0")

SUBFOLDER = {"en": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}


class Laya(Adapter):
    def __init__(self, variant="router", repo="convaiinnovations/laya", **opts):
        super().__init__(**opts)
        import laya
        self.variant, self.repo = variant, repo
        if variant == "router":
            self.agent = laya.Router()
        else:
            sub = SUBFOLDER[variant]
            self.agent = laya.load(repo, subfolder=sub) if sub else laya.load(repo)

    def meta(self):
        import laya
        return {"model": self.repo, "variant": self.variant, "laya_version": getattr(laya, "__version__", None)}

    def decide(self, state, questions):
        out = self.agent.predict(state, questions)
        return {"answers": out["answers"], "cost": None, "model": f"{self.repo}:{self.variant}",
                "routing": out.get("routing")}
