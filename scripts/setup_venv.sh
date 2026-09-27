#!/bin/bash
# Create .venv-<name> on a DGX Spark with uv-managed Python (ships Python.h, which
# Triton needs to build its CUDA launcher; the system python3.12 lacks it) and
# PyTorch cu130 for aarch64. Usage: scripts/setup_venv.sh <name> <pip packages...>
set -euo pipefail
name=$1; shift
cd "$(dirname "$0")/.."
export PATH=$HOME/.local/bin:$PATH UV_HTTP_TIMEOUT=300
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
rm -rf ".venv-$name"
uv venv -q --managed-python -p 3.12 ".venv-$name"
uv pip install -q -p ".venv-$name/bin/python" torch --index-url https://download.pytorch.org/whl/cu130
uv pip install -q -p ".venv-$name/bin/python" "$@"
".venv-$name/bin/python" -c "import torch; assert torch.cuda.is_available(); print('$name', torch.__version__, torch.cuda.get_device_name(0))"
