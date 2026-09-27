#!/bin/bash
# Serve Mapika/decider-35b-a3b-nvfp4 with vLLM on a DGX Spark (GB10) at 127.0.0.1:8000.
# Needs .venv-vllm (scripts/setup_venv.sh vllm vllm==0.29.0 nvidia-modelopt==0.46.1 fastapi "uvicorn[standard]"
# jinja2 huggingface_hub ninja; then uv pip install --no-deps decider-ai) and HF_TOKEN in the environment.
# GB10 memory is unified: keep vLLM at <=45% so the first-start FlashInfer JIT (cicc, ~9 GB per job)
# does not OOM the box; MAX_JOBS=2 caps that compile (~25 min the first time, cached afterwards).
# Query it with: python3 -m jevbench.run systemone_http --run <run> --opt model=Mapika/decider-35b-a3b-nvfp4
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv-vllm/bin:/usr/local/cuda/bin:$PATH" MAX_JOBS=2
export DECIDER_MODEL=Mapika/decider-35b-a3b-nvfp4 DECIDER_VLLM_GPU_MEMORY_UTILIZATION=0.45 \
       DECIDER_VLLM_MAX_MODEL_LEN=16384 DECIDER_MAX_STATE_TOKENS=12288
exec .venv-vllm/bin/python -m uvicorn decider.serve_vllm:app --host 127.0.0.1 --port 8000
