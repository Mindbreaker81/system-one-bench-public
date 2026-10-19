"""JEV-89 paso 3: LoRA de Qwen3.5 con el contrato de Tev1 (una letra por pregunta).

Pre-registro: docs/experimentos/jev89_preregistro.md (+ enmienda E1). El formato del prompt sale de
jevbench/adapters/tev1.py (SYSTEM y _options) y las preguntas de jevbench.battery, importados sin
editar, para que la evaluación use el adaptador `tev1` tal cual. Pérdida solo sobre el token de la
letra; selección del checkpoint por log-loss de la letra correcta (softmax restringida a las letras
permitidas, como el adaptador) en val + val_nc.

    python3 scripts/jev89/train_lora.py --base /mnt/ai-models/hf/Qwen/Qwen3.5-9B \
        --data /ruta/final --out ~/modelos/jev89_qwen35_9b --epochs 3
"""
import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jevbench.adapters.tev1 import LETTERS, SYSTEM, _options  # noqa: E402
from jevbench.battery import PAPERS_QS, TRIAGE_QS  # noqa: E402

QS = {"triage": TRIAGE_QS, "papers": PAPERS_QS}
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj",
           "gate_proj", "up_proj", "down_proj"]


def answer_key(q, value):
    """Valor del GT → clave de opción de _options (choice: etiqueta; score: índice; noul: yes/no)."""
    if q["type"] == "noul":
        return "yes" if value == 1 else "no"
    if q["type"] == "score":
        return str(int(value))
    return value


def build_samples(records, rng, shuffle_choice=True):
    """Una muestra por pregunta etiquetada: (mensajes, letra correcta, letras permitidas)."""
    out = []
    for r in records:
        qs = QS[r["task"]]
        for name, value in r["gt"].items():
            q = qs[name]
            options, keys = _options(name, q)
            pairs = list(zip([dict(o) for o in options], keys))
            if q["type"] == "choice" and shuffle_choice:
                rng.shuffle(pairs)
            opts = []
            for letter, (o, _) in zip(LETTERS, pairs):
                o["label"] = letter
                opts.append(o)
            keys = [k for _, k in pairs]
            gold = LETTERS[keys.index(answer_key(q, value))]
            msg = [{"role": "system", "content": SYSTEM},
                   {"role": "user", "content": json.dumps(
                       {"state": r["state"], "question": q["instructions"], "options": opts},
                       ensure_ascii=False)}]
            out.append({"messages": msg, "gold": gold, "letters": LETTERS[:len(opts)],
                        "id": r["id"], "q": name})
    return out


def load(path):
    return [json.loads(line) for line in Path(path).open()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--data", required=True, help="directorio final/ del ensamblado")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--max-steps", type=int, default=0, help="solo prueba de la cadena")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--micro", type=int, default=4)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=89)
    ap.add_argument("--val-limit", type=int, default=0)
    ap.add_argument("--backend", choices=["unsloth", "peft"], default="unsloth",
                    help="pre-registro: Unsloth si funciona en el DGX; si no, transformers + peft")
    ap.add_argument("--save-every", type=int, default=200,
                    help="pasos entre guardados de reanudación (<out>/reanudar.pt); 0 = nunca")
    ap.add_argument("--resume", action="store_true", help="continúa desde <out>/reanudar.pt si existe")
    a = ap.parse_args()

    if a.backend == "unsloth":
        import unsloth  # noqa: F401  (antes que transformers y peft, para que aplique sus parches)
    import torch
    import peft
    import transformers
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    data = Path(a.data)
    train_recs = load(data / "train.jsonl") + load(data / "train_nc.jsonl")
    val_recs = load(data / "val.jsonl") + load(data / "val_nc.jsonl")
    train = build_samples(train_recs, rng)
    val = build_samples(val_recs, random.Random(a.seed + 1))
    if a.val_limit:
        val = val[:a.val_limit]

    tok = AutoTokenizer.from_pretrained(a.base)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def encode(s):
        prompt = tok.apply_chat_template(s["messages"], tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
        ids = tok.encode(prompt, add_special_tokens=False)
        cand = []
        for letter in s["letters"]:
            comb = tok.encode(prompt + letter, add_special_tokens=False)
            assert comb[:len(ids)] == ids and len(comb) == len(ids) + 1, "letra no es token único"
            cand.append(comb[-1])
        return ids[-a.max_len:], cand, s["letters"].index(s["gold"])

    t0 = time.time()
    train_enc = [encode(s) for s in train]
    val_enc = [encode(s) for s in val]
    lens = sorted(len(e[0]) for e in train_enc)
    print(f"muestras train {len(train_enc)} val {len(val_enc)}; tokens mediana {lens[len(lens)//2]} "
          f"p99 {lens[int(len(lens)*.99)]} máx {lens[-1]}; codificado en {time.time()-t0:.0f}s", flush=True)

    if a.backend == "unsloth":
        from unsloth import FastModel
        model, _ = FastModel.from_pretrained(a.base, dtype=torch.bfloat16, load_in_4bit=False,
                                             full_finetuning=False, max_seq_length=a.max_len)
        model = FastModel.get_peft_model(model, r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                                         target_modules=TARGETS, finetune_vision_layers=False,
                                         finetune_language_layers=True,
                                         use_gradient_checkpointing="unsloth", random_state=a.seed)
    else:
        model = Qwen3_5ForConditionalGeneration.from_pretrained(a.base, dtype=torch.bfloat16,
                                                                attn_implementation="sdpa").to("cuda")
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                         target_modules=r".*language_model.*\.(" + "|".join(TARGETS) + r")$")
        model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    lora_mods = sorted({n.rsplit(".lora_A", 1)[0].split(".")[-1] for n, _ in model.named_parameters() if ".lora_A" in n})
    vis = sum(1 for n, _ in model.named_parameters() if ".lora_A" in n and ".visual." in n)
    print("módulos LoRA:", lora_mods, "| en visión:", vis, flush=True)

    def batch_logits(chunk):
        maxlen = max(len(e[0]) for e in chunk)
        ids = torch.full((len(chunk), maxlen), tok.pad_token_id, dtype=torch.long)
        att = torch.zeros_like(ids)
        for i, e in enumerate(chunk):
            ids[i, maxlen - len(e[0]):] = torch.tensor(e[0])
            att[i, maxlen - len(e[0]):] = 1
        res = model(input_ids=ids.cuda(), attention_mask=att.cuda(), logits_to_keep=1)
        return res.logits[:, -1, :].float()

    def evaluate():
        model.eval()
        nll, hits = 0.0, 0
        with torch.inference_mode():
            for i in range(0, len(val_enc), 8):
                chunk = val_enc[i:i + 8]
                lg = batch_logits(chunk)
                for j, (_, cand, gi) in enumerate(chunk):
                    p = lg[j, torch.tensor(cand, device=lg.device)].log_softmax(-1)
                    nll -= p[gi].item()
                    hits += int(p.argmax().item() == gi)
        model.train()
        return nll / len(val_enc), hits / len(val_enc)

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    steps_per_epoch = math.ceil(len(train_enc) / (a.micro * a.accum))
    total = a.max_steps or steps_per_epoch * a.epochs
    warm = max(1, int(0.03 * total))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))
    trainable = {n: p for n, p in model.named_parameters() if p.requires_grad}
    state_path = out / "reanudar.pt"

    def save_state(ep, bi):
        """Estado completo para reanudar sin cambiar el resultado: pesos LoRA, gradientes acumulados,
        optimizador, scheduler, RNG y posición (época, micro-lote) en el orden fijo por semilla."""
        tmp = state_path.with_suffix(".tmp")
        torch.save({"ep": ep, "bi": bi, "step": step, "log": log,
                    "params": {n: p.detach().cpu() for n, p in trainable.items()},
                    "grads": {n: p.grad.detach().cpu() for n, p in trainable.items() if p.grad is not None},
                    "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state()}, tmp)
        tmp.replace(state_path)

    start_ep, start_bi, step = 1, 0, 0
    if a.resume and state_path.exists():
        st = torch.load(state_path, map_location="cpu", weights_only=False)
        with torch.no_grad():
            for n, p in trainable.items():
                p.copy_(st["params"][n])
                if n in st["grads"]:
                    p.grad = st["grads"][n].to(p.device)
        opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"])
        torch.set_rng_state(st["rng"])
        torch.cuda.set_rng_state(st["cuda_rng"])
        start_ep, start_bi, step, log = st["ep"], st["bi"], st["step"], st["log"]
        print(f"reanudado: época {start_ep}, micro-lote {start_bi}, paso {step}", flush=True)
    else:
        log = []
        v0 = evaluate()
        print(f"val antes de entrenar: logloss {v0[0]:.4f} acc {v0[1]:.3f}", flush=True)
        log.append({"epoch": 0, "val_logloss": v0[0], "val_acc": v0[1]})
    model.train()
    for ep in range(start_ep, a.epochs + 1):
        order = list(range(len(train_enc)))
        random.Random(a.seed * 100 + ep).shuffle(order)
        run_loss, t1, step_t1 = 0.0, time.time(), step
        for bi in range(start_bi if ep == start_ep else 0, len(order), a.micro):
            chunk = [train_enc[k] for k in order[bi:bi + a.micro]]
            lg = batch_logits(chunk)
            gold = torch.tensor([e[1][e[2]] for e in chunk], device=lg.device)
            loss = torch.nn.functional.cross_entropy(lg, gold) / a.accum
            loss.backward()
            run_loss += loss.item()
            if (bi // a.micro + 1) % a.accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 25 == 0:
                    el = time.time() - t1
                    print(f"ep {ep} paso {step}/{total} loss {run_loss/25:.4f} lr {sched.get_last_lr()[0]:.2e} "
                          f"{el / max(1, step - step_t1):.2f}s/paso", flush=True)
                    run_loss = 0.0
                if a.save_every and step % a.save_every == 0:
                    save_state(ep, bi + a.micro)
                if a.max_steps and step >= a.max_steps:
                    break
        v = evaluate()
        ck = out / f"epoch{ep}"
        model.save_pretrained(ck)
        print(f"época {ep}: val logloss {v[0]:.4f} acc {v[1]:.3f} → {ck}", flush=True)
        log.append({"epoch": ep, "val_logloss": v[0], "val_acc": v[1], "steps": step, "path": str(ck)})
        if a.save_every and not (a.max_steps and step >= a.max_steps):
            save_state(ep + 1, 0)
        if a.max_steps and step >= a.max_steps:
            break
    best = min((e for e in log if e["epoch"] > 0), key=lambda e: (round(e["val_logloss"], 6), e["epoch"]))
    meta = {"base": a.base, "data": str(data), "args": vars(a), "log": log, "elegido": best,
            "modulos_lora": lora_mods, "lora_en_vision": vis,
            "torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__,
            "data_sha256": {f: hashlib.sha256((data / f).read_bytes()).hexdigest()
                            for f in ("train.jsonl", "train_nc.jsonl", "val.jsonl", "val_nc.jsonl")}}
    (out / "entrenamiento.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print("elegido:", best, flush=True)


if __name__ == "__main__":
    main()
