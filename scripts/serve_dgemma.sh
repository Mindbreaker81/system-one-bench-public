#!/bin/bash
# JEV-70: DiffusionGemma-26B-A4B NVFP4 en un DGX Spark — motor vLLM (commit fijado
# 1b3b88ec, venv propio) + interposer structured_server.py del mismo commit.
# Uso (en el Spark):  scripts/serve_dgemma.sh <CANVAS> <MAXLEN> [ENGINE_PORT] [SRV_PORT]
# Arranca dos sesiones tmux (dgemma-vllm, dgemma-srv) que escuchan solo en 127.0.0.1;
# logs en ~/dgemma/{vllm,srv}.log. Consumir con túnel SSH.
# VLLM_CACHE_ROOT (opcional, en el entorno): raíz de caché propia; en .80 hace falta porque
# ~/.cache/vllm/flashinfer_autotune_cache es de root (contenedor ajeno) y el autotune no puede escribir.
# VLLM_LOGGING_LEVEL=DEBUG: en esta build `--enable-log-requests` solo registra el prompt
# (repr + prompt_token_ids) en DEBUG; la puerta §6.4 lo necesita. Sin --max-log-len = sin truncar.
# EXTRA_SERVE_ARGS (opcional, vacío por defecto): flags extra de `vllm serve`; solo la sesión L″
# de JEV-70 lo usa (EXTRA_SERVE_ARGS="--reasoning-parser gemma4").
# Reglas GB10: gpu_memory_utilization 0.45 y MAX_JOBS=2 (JIT sin OOM del kernel).
set -euo pipefail
CANVAS=${1:?canvas}; MAXLEN=${2:?max-model-len}; EP=${3:-8010}; SP=${4:-8011}
V=$HOME/proyectos/jev-tests/.venv-vllm-dgemma
M=$HOME/modelos/diffusiongemma-26B-A4B-it-NVFP4
SRV=$HOME/dgemma/vllm/examples/features/structured_diffusion/structured_server.py
D=$HOME/dgemma
# $V/bin en el PATH: el JIT de los kernels NVFP4 (modelopt) invoca `ninja` por nombre
export PATH=$V/bin:/usr/local/cuda/bin:$PATH
for p in $EP $SP; do
  if ss -ltn | grep -q ":$p\b"; then echo "puerto $p ocupado" >&2; exit 1; fi
done
CACHE_ENV=${VLLM_CACHE_ROOT:+VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT}
tmux new -d -s dgemma-vllm "$CACHE_ENV VLLM_LOGGING_LEVEL=DEBUG MAX_JOBS=2 $V/bin/vllm serve $M \
  --served-model-name dgemma --diffusion-config '{\"canvas_length\": $CANVAS}' \
  --max-logprobs 32 --enable-prefix-caching --async-scheduling --attention-backend TRITON_ATTN \
  --max-num-seqs 32 --max-model-len $MAXLEN --gpu-memory-utilization 0.45 \
  --host 127.0.0.1 --port $EP --enable-log-requests ${EXTRA_SERVE_ARGS:-} 2>&1 | tee -a $D/vllm.log"
echo "motor en tmux dgemma-vllm; esperando /health…"
until curl -sf http://127.0.0.1:$EP/health >/dev/null; do
  tmux has-session -t dgemma-vllm 2>/dev/null || { echo "el motor murió; ver $D/vllm.log" >&2; exit 1; }
  sleep 10
done
tmux new -d -s dgemma-srv "$V/bin/python $SRV \
  --upstream http://127.0.0.1:$EP --model dgemma --tokenizer $M --canvas $CANVAS \
  --canvas-step 16 --host 127.0.0.1 --port $SP 2>&1 | tee -a $D/srv.log"
echo "listo: motor :$EP, interposer :$SP"
