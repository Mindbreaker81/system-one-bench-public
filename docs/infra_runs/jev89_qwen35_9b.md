# Manifiesto — JEV-89: LoRA sobre Qwen3.5-9B y su control

## Runs

| Run | Modelo | Host | Fecha |
|---|---|---|---|
| `qwen35_9b_base_tev1fmt` | `Qwen/Qwen3.5-9B` @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a` (copia de ai-models), sin entrenar | DGX Spark <host> (GB10) | 17-oct-2026 |
| `jev89_qwen35_9b_lora` | la misma base + LoRA época 2, fusionado | DGX Spark <host> (GB10) | 18-oct-2026 |

Ambos: adaptador `tev1` sin cambios, `--phases all+new` y `--phases adv4,adv5`, venv `.venv-tev1`
(torch 2.14.1+cu130, transformers 5.17.0, sin `fla`), bf16, `enable_thinking=false`. `jevbench/adapters/tev1.py`,
`battery.py` y `run.py` en <host> idénticos a los del repo (sha256 comprobado antes de lanzar).

## Entrenamiento

- `scripts/jev89/train_lora.py --base <ruta-local> --data <ruta-local>
  --out <ruta-local> --epochs 3 --backend unsloth --save-every 200 --resume`.
- Unsloth 2026.10.6 (+ unsloth_zoo 2026.10.6), peft 0.21.2, transformers 5.17.0, torch 2.14.1+cu130;
  `causal_conv1d` sin compilar (vía PyTorch de referencia).
- LoRA r=16, α=32, dropout 0,05; módulos de la enmienda E1; 0 en visión; 40,1 M parámetros entrenables.
- 21.843 muestras de entrenamiento y 2.441 de validación; ~13 s/paso; 18-oct 00:34 → 16:10.
- Conjunto `run-20261017-192634`, índice de exclusión `23a21a1f…642d`; sha256 de los cuatro JSONL en
  `docs/experimentos/jev89_entrenamiento/entrenamiento.json`.
- Elegida: época 2 (val log-loss 0,0694). Adaptador `epoch2/adapter_model.safetensors`
  sha256 `90814b2741463cf25493bb0bcbe8b88522b33168f56758e8816ce2094b0a2de6`; fusionado
  `model.safetensors` sha256 `29589114e13a78a7af87316786667225d4bb8be271a2f76f67b3534b54766ecb`
  (`scripts/jev89/merge_lora.py`, venv `.venv-jev89`).

## Incidencias

- **Primer intento perdido** (17-oct 20:04 → 18-oct 00:10, paso 1.050/4.098): la tarjeta de red r8127 de
  <host> se colgó a las 22:10 (*transmit timeout*) y a las 00:09:59 la GPU dio un **Xid 120** (GSP task
  exception, iniciado por Xorg), probablemente al conectar un monitor. El proceso murió con
  `CUDA error: unspecified launch failure`, sin checkpoint. Log: `<host>:<ruta-local>`.
- Recuperación: acceso por el enlace QSFP directo desde <host>; apagado forzado y
  arranque. Se añadió el guardado de reanudación (commit `e4cb999`, probado con 2B) y se relanzó
  desde cero, sin usar nada del primer intento.
