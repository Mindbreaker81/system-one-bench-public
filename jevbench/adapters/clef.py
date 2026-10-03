"""Cloudflare/clef in-process: Qwen3.8-27B backbone + joint schema head.
The release ships `joint_schema_model.py` with `load_release_model` and `systemone`
(the wire-compatible Jev/SystemOne API), imported from the HF snapshot.
Options: model, revision, device (cuda|cpu), dtype, max_length."""
import sys
from pathlib import Path

from . import Adapter


class Clef(Adapter):
    def __init__(self, model="Cloudflare/clef", revision=None, device="cuda",
                 dtype="bfloat16", max_length=16384, **opts):
        super().__init__(**opts)
        from huggingface_hub import snapshot_download
        path = snapshot_download(model, revision=revision)
        if path not in sys.path:
            sys.path.insert(0, path)
        from joint_schema_model import load_release_model, systemone
        import torch
        self.systemone = systemone
        self.model_name, self.revision = model, revision
        self.snapshot = Path(path).name
        self.max_length = int(max_length)
        self.device, self.dtype = device, dtype
        self.model, self.processor = load_release_model(
            path, device=device, dtype=getattr(torch, dtype))

    def meta(self):
        return {"model": self.model_name, "revision": self.revision or self.snapshot,
                "device": self.device, "dtype": self.dtype, "max_length": self.max_length}

    def decide(self, state, questions):
        out = self.systemone(self.model, self.processor,
                             {"model": self.model_name, "state": state, "questions": questions},
                             max_length=self.max_length)
        return {"answers": out["answers"], "cost": None, "model": out.get("model") or self.model_name,
                "usage": out.get("usage")}
