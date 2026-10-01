"""Bespoke-Nimble-9B (bespokelabs/Bespoke-Nimble-9B): LoRA PEFT sobre Qwen3.5-9B
que puntúa tokens candidato directamente, sin generación libre.

Usa el ParallelScorer oficial (inference.py del repo HF, con la validación de
hashes del prompt de entrenamiento intacta). El scorer construye UN prompt por
campo — cada prompt lleva el contexto + el esquema completo con todas las
preguntas + "Requested field: X" — y hace una pasada forward por campo; no hay
una única pasada que devuelva todas las preguntas a la vez.

Mapeo del formato wire:
  choice -> enum con choices=etiquetas y choice_descriptions
  score  -> enum de enteros "0".."N-1" + score_fields (score = expected_score)
  noul   -> boolean (noul = P(true))

Opciones:
  model      repo HF del adaptador (por defecto bespokelabs/Bespoke-Nimble-9B)
  revision   revisión fijada del repo HF
  model_dir  alternativa: directorio local con el snapshot (no va al meta)
"""
from . import Adapter


class Nimble(Adapter):
    def __init__(self, model="bespokelabs/Bespoke-Nimble-9B", revision=None,
                 model_dir=None, temperature=None, **opts):
        super().__init__(**opts)
        import sys
        from pathlib import Path
        self.model_id, self.revision = model, revision
        if model_dir:
            d = str(Path(model_dir).expanduser())
        else:
            from huggingface_hub import snapshot_download
            d = snapshot_download(model, revision=revision)
        if d not in sys.path:
            sys.path.insert(0, d)
        from inference import ParallelScorer
        kw = {}
        if temperature is not None:
            kw["temperature"] = float(temperature)
        self.scorer = ParallelScorer(d, **kw)

    def meta(self):
        import peft
        import torch
        import transformers
        contract = self.scorer.contract
        return {"model": self.model_id, "revision": self.revision,
                "base": f"{contract['model']}@{contract['revision']}",
                "device": "cuda", "dtype": "bfloat16",
                "temperature": self.scorer.temperature,
                "torch": torch.__version__, "transformers": transformers.__version__,
                "peft": peft.__version__}

    @staticmethod
    def _schema(questions):
        """Wire questions -> nimble schema + lista de score_fields."""
        schema, score_fields = {}, []
        for name, q in questions.items():
            instr = q["instructions"]
            if q["type"] == "noul":
                schema[name] = {"type": "boolean", "description": instr}
            elif q["type"] == "choice":
                descs = {}
                for label, crit in q["criteria"].items():
                    d = crit.get("what") if isinstance(crit, dict) else crit
                    if d:
                        descs[label] = str(d)
                schema[name] = {"type": "enum", "description": instr,
                                "choices": list(q["criteria"]),
                                "choice_descriptions": descs}
            else:  # score: niveles ordinales -> enum entero "0".."N-1"
                levels = list(q["criteria"])
                codes = [str(i) for i in range(len(levels))]
                schema[name] = {"type": "enum", "description": instr, "choices": codes,
                                "choice_descriptions": dict(zip(codes, levels))}
                score_fields.append(name)
        return schema, score_fields

    def decide(self, state, questions):
        schema, score_fields = self._schema(questions)
        out = self.scorer.score(state, schema, score_fields=score_fields)
        ans = {}
        for name, q in questions.items():
            f = out["fields"][name]
            if q["type"] == "noul":
                ans[name] = {"noul": float(f["probability_true"])}
            elif q["type"] == "choice":
                ans[name] = {"choice": f["prediction"],
                             "probabilities": {k: float(v) for k, v in f["probabilities"].items()}}
            else:
                ans[name] = {"score": float(f["expected_score"]),
                             "probabilities": {k: float(v) for k, v in f["probabilities"].items()}}
        return {"answers": ans, "cost": None, "model": self.model_id}
