"""Mapika/decider in-process (pip install decider-ai). Same wire format as Jev.
Options: model, device (cuda|cpu), dtype, layout (state_first|schema_first), temperature,
use_graphs (true|false; CUDA graphs are on by default and break with the 35B-A3B MoE:
"Cannot copy between CPU and CUDA tensors during CUDA graph capture")."""
from . import Adapter


class DeciderLocal(Adapter):
    def __init__(self, model="Mapika/decider-2b", device="cuda", dtype="bfloat16", layout=None,
                 temperature=None, use_graphs=None, **opts):
        super().__init__(**opts)
        from decider.infer import Decider
        self.model, self.device, self.dtype, self.layout = model, device, dtype, layout
        kw = {"device": device, "dtype": dtype}
        if temperature is not None:
            kw["temperature"] = float(temperature)
        if use_graphs is not None:
            kw["use_graphs"] = str(use_graphs).lower() in ("1", "true", "yes")
        self.use_graphs = kw.get("use_graphs")
        self.d = Decider(model, **kw)

    def meta(self):
        import decider
        return {"model": self.model, "device": self.device, "dtype": self.dtype, "layout": self.layout,
                "use_graphs": self.use_graphs,
                "temperature": getattr(self.d, "temperature", None),
                "decider_version": getattr(decider, "__version__", None)}

    def decide(self, state, questions):
        kw = {"layout": self.layout} if self.layout else {}
        out = self.d.system_one(state, questions, **kw)
        return {"answers": out["answers"], "cost": None, "model": self.model}
