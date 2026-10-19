"""JEV-89 paso 3: regla de parada pre-registrada. Acierto por pregunta en val + val_nc del modelo
fusionado frente a la clase mayoritaria de esa pregunta en el mismo conjunto. Mismas muestras y misma
lectura (softmax restringida a las letras) que train_lora.py.

    python3 scripts/jev89/val_por_pregunta.py --model ~/modelos/jev89_qwen35_9b_merged \
        --data ~/jev89/data --out val_por_pregunta.json
"""
import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_lora import build_samples, load  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--seed", type=int, default=89)
a = ap.parse_args()

import torch  # noqa: E402
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration  # noqa: E402

data = Path(a.data).expanduser()
recs = load(data / "val.jsonl") + load(data / "val_nc.jsonl")
val = build_samples(recs, random.Random(a.seed + 1))
model_path = str(Path(a.model).expanduser())
tok = AutoTokenizer.from_pretrained(model_path)
tok.padding_side = "left"
model = Qwen3_5ForConditionalGeneration.from_pretrained(model_path, dtype=torch.bfloat16).cuda().eval()

majority = collections.defaultdict(collections.Counter)
for r in recs:
    for name, value in r["gt"].items():
        majority[name][json.dumps(value)] += 1

hits, n, nll = collections.Counter(), collections.Counter(), collections.Counter()
with torch.inference_mode():
    for s in val:
        prompt = tok.apply_chat_template(s["messages"], tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
        ids = tok.encode(prompt, add_special_tokens=False)
        cand = [tok.encode(prompt + letter, add_special_tokens=False)[-1] for letter in s["letters"]]
        lg = model(input_ids=torch.tensor([ids]).cuda(), logits_to_keep=1).logits[0, -1].float()
        p = lg[torch.tensor(cand, device=lg.device)].log_softmax(-1)
        gi = s["letters"].index(s["gold"])
        hits[s["q"]] += int(p.argmax().item() == gi)
        nll[s["q"]] -= p[gi].item()
        n[s["q"]] += 1

res = {}
for q in sorted(n):
    maj = majority[q].most_common(1)[0][1] / sum(majority[q].values())
    res[q] = {"n": n[q], "acc": hits[q] / n[q], "mayoria": maj, "logloss": nll[q] / n[q],
              "supera_mayoria": hits[q] / n[q] > maj}
    print(f"{q:12s} n={n[q]:5d} acc {hits[q]/n[q]:.3f} mayoría {maj:.3f} logloss {nll[q]/n[q]:.4f}", flush=True)
total = sum(hits.values()) / sum(n.values())
res["_total"] = {"n": sum(n.values()), "acc": total, "logloss": sum(nll.values()) / sum(n.values())}
res["_parada"] = not (res["department"]["supera_mayoria"] and res["domain"]["supera_mayoria"])
print(f"total acc {total:.4f}; parada: {res['_parada']}", flush=True)
Path(a.out).expanduser().write_text(json.dumps(res, indent=1))
