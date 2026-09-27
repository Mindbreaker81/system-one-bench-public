"""Minimal .env loader (no python-dotenv dependency). Never prints values."""
import os
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def load_env(path=ENV):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if "HF_API_KEY" in os.environ:
        os.environ.setdefault("HF_TOKEN", os.environ["HF_API_KEY"])
