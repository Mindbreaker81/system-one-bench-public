"""Base Labs decision models (elephant-1 / mammoth-1) in-process on OneJev's qev runtime.
The release pins OneJev @81ce62f + its `serve.patch` (applied by `setup.sh`); this adapter calls
`qev.engine.DecisionEngine` exactly like the release's `engine.py`: one shared-prefix prefill per
request, the checkpoint's `readout.json` read at load, requests over the trained length refused.
Options: model (HF repo or local path), revision (recorded only), device, choice_order
(base Adapter)."""
from . import Adapter


class BaseLabs(Adapter):
    def __init__(self, model="baselabs/elephant-1", revision=None, device="cuda:0", **opts):
        super().__init__(**opts)
        from qev.engine import DecisionEngine
        from qev.schema import SystemOneRequest
        self._request = SystemOneRequest
        self.model_name, self.revision, self.device = model, revision, device
        self.engine = DecisionEngine(model, device=device)
        info = self.engine.info
        self.info = {"fork_mode": info.fork_mode, "attention": info.extra.get("attention"),
                     "readout": info.extra.get("readout"), "calibration": info.extra.get("calibration")}

    def meta(self):
        return {"model": self.model_name, "revision": self.revision, "device": self.device,
                "runtime": "OneJev qev @81ce62f + serve.patch", **self.info, **self._order_meta()}

    def decide(self, state, questions):
        questions = self._apply_choice_order(questions)
        request = self._request(state=state, questions=questions)
        try:
            resp, _ = self.engine.decide(request)
        except RuntimeError as e:
            # Same fallback as the release engine.py: the batched prefix fork overflows 32-bit
            # indexing on the largest multi-question requests; sequential branches are exact.
            if "32BitIndexMath" not in str(e):
                raise
            mode, self.engine.info.fork_mode = self.engine.info.fork_mode, "sequential"
            try:
                resp, _ = self.engine.decide(request)
            finally:
                self.engine.info.fork_mode = mode
        answers = {k: a.model_dump(exclude_none=True) for k, a in resp.answers.items()}
        return {"answers": answers, "cost": None, "model": self.model_name}
