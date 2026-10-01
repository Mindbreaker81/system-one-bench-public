#!/usr/bin/env python3
"""Smoke controlado del adaptador `llm` (JEV-44): 6 casos fijados x N repeticiones
contra un endpoint compatible con OpenAI, con los límites nuevos pre-registrados.
No es un run del marcador: la salida va a results/logs/ (o --out).

En el DGX .81 (mismo modelo y configuración del run llm_qwen38flash_prob):
  .venv-llm/bin/python scripts/smoke_llm.py --reps 3 \\
      --base-url http://127.0.0.1:8888/v1 --model qwen3.8-flash-next \\
      --timeout 1800 --case-timeout 600 --max-tokens 16384 \\
      --out results/logs/smoke_llm_jev44.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jevbench.battery import load_phase  # noqa: E402

# control inicial OOD, históricos y control de recuperación final, en ese orden
CASES = [("ood", "receta"),
         ("adv2", "B01_fake_it_migration"),
         ("adv3", "C09_guilt_trip_cold"),
         ("triage_ext_en", "T21_rivaroxaban_ebus"),
         ("triage_ext_en", "T33_segunda_opinion"),
         ("triage_es", "T02_factura_duplicada")]


def mem_available_gb():
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return round(int(line.split()[1]) / 2**20, 1)
    except OSError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8888/v1")
    ap.add_argument("--model", default="qwen3.8-flash-next")
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--case-timeout", type=float, default=600)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from jevbench.adapters.llm import LLM
    adapter = LLM(provider="openai", model=args.model, base_url=args.base_url,
                  api_key="none", timeout=args.timeout, case_timeout=args.case_timeout,
                  max_tokens=args.max_tokens)
    out = {"meta": {"adapter": "llm", "model": args.model, "base_url": args.base_url,
                    "timeout": args.timeout, "case_timeout": args.case_timeout,
                    "max_tokens": args.max_tokens, "reps": args.reps,
                    "mem_gb_start": mem_available_gb()},
           "attempts": []}
    out_path = Path(args.out) if args.out else Path("results/logs/smoke_llm_jev44.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for rep in range(args.reps):
        for phase, cid in CASES:
            qs, cases = load_phase(phase)
            case = next(c for c in cases if c.id == cid)
            t0 = time.monotonic()
            rec = {"rep": rep, "phase": phase, "id": cid}
            try:
                o = adapter.decide(case.state, qs)
                rec.update(ok=True, ms=round((time.monotonic() - t0) * 1000),
                           usage=o.get("usage"))
                print(f"rep{rep} {phase}/{cid}: ok {rec['ms']}ms "
                      f"out_tok={rec['usage'].get('output_tokens')} "
                      f"attempts={rec['usage'].get('attempts')}", flush=True)
            except Exception as e:
                rec.update(ok=False, ms=round((time.monotonic() - t0) * 1000),
                           error=f"{type(e).__name__}: {e}"[:300],
                           diag=getattr(e, "diag", None))
                print(f"rep{rep} {phase}/{cid}: ERROR {rec['error'][:100]} "
                      f"({rec['ms']}ms)", flush=True)
            rec["mem_gb"] = mem_available_gb()
            out["attempts"].append(rec)
            out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    out["meta"]["mem_gb_end"] = mem_available_gb()
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"guardado en {out_path}", flush=True)


if __name__ == "__main__":
    main()
