"""JEV-89: fusiona el checkpoint LoRA elegido con la base y copia tokenizer/procesador para el adaptador tev1.

    python3 scripts/jev89/merge_lora.py --base /mnt/ai-models/hf/Qwen/Qwen3.5-9B \
        --adapter ~/modelos/jev89_qwen35_9b/epoch2 --out ~/modelos/jev89_qwen35_9b_merged
"""
import argparse
import shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

import torch  # noqa: E402
from peft import PeftModel  # noqa: E402
from transformers import Qwen3_5ForConditionalGeneration  # noqa: E402

base = Qwen3_5ForConditionalGeneration.from_pretrained(a.base, dtype=torch.bfloat16)
model = PeftModel.from_pretrained(base, str(Path(a.adapter).expanduser())).merge_and_unload()
out = Path(a.out).expanduser()
model.save_pretrained(out, safe_serialization=True)
for f in Path(a.base).iterdir():
    if f.suffix in (".json", ".jinja", ".txt") and f.name != "ORIGEN.txt" and not f.name.startswith(("config", "model.safetensors")):
        shutil.copy2(f, out / f.name)
print("fusionado en", out)
