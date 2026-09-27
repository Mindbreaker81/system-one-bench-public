"""SupersonicLabs/Julia-1 (mmBERT-small + decision head, 144M). Same wire format as Jev.
Install: snapshot_download('SupersonicLabs/Julia-1', local_dir='models/Julia-1'); pip install -e models/Julia-1
Options: path (local snapshot dir), device (cpu|cuda), max_length, head_length."""
from . import Adapter


class Julia(Adapter):
    def __init__(self, path="models/Julia-1", device="cpu", max_length=8192, head_length=512, **opts):
        super().__init__(**opts)
        from julia import load_model
        self.path, self.device = path, device
        self.max_length, self.head_length = int(max_length), int(head_length)
        self.engine = load_model(path, device=device, strict_encoding=True,
                                 max_length=self.max_length, head_length=self.head_length)

    def meta(self):
        import julia
        return {"model": "SupersonicLabs/Julia-1", "path": self.path, "device": self.device,
                "max_length": self.max_length, "head_length": self.head_length,
                "julia_version": getattr(julia, "__version__", None)}

    def decide(self, state, questions):
        out = self.engine.predict(state=state, questions=questions)
        return {"answers": out["answers"], "cost": None, "model": "SupersonicLabs/Julia-1"}
