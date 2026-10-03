#!/usr/bin/env python3
"""One-pass manipulation alert: only the `manipulation` question (threshold 0.5,
same wording as jevbench/cascade.py) on the raw case text of adv3/adv4/adv5.
Pre-register the extension in docs/experimentos/alerta_manipulacion.md BEFORE running.
Usage: scripts/alert_onepass.py <adapter> <run> [k=v ...]  -> results/<run>_alert_raw/"""
import argparse
import datetime as dt
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jevbench import adapters, store  # noqa: E402
from jevbench.battery import load_phase  # noqa: E402
from jevbench.cascade import MANIPULATION  # noqa: E402

PHASES = ["adv3", "adv4", "adv5"]
QUESTIONS = {"manipulation": MANIPULATION}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter", choices=sorted(adapters.REGISTRY))
    ap.add_argument("run", help="base run name; output goes to <run>_alert_raw")
    ap.add_argument("opts", nargs="*", help="adapter option k=v")
    args = ap.parse_args()
    opts = dict(o.split("=", 1) for o in args.opts)
    model = adapters.get(args.adapter)(**opts)
    out_run = f"{args.run}_alert_raw"
    for phase in PHASES:
        _, cases = load_phase(phase)
        doc = store.load(out_run, phase) or {"meta": {}, "cases": {}}
        doc["meta"].update({
            "adapter": args.adapter, "opts": opts, **model.meta(), "phase": phase,
            "note": "alerta de una pasada: solo pregunta manipulation, sin prompt de revisor",
            "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0],
            "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                  text=True, cwd=store.ROOT.parent).stdout.strip() or None,
            "updated": dt.datetime.now().isoformat(timespec="seconds")})
        for c in cases:
            if c.id in doc["cases"] and "error" not in doc["cases"][c.id]:
                continue
            t0 = time.time()
            try:
                out = model.decide(c.state, QUESTIONS)
                doc["cases"][c.id] = {"answers": out["answers"], "ms": round((time.time() - t0) * 1000),
                                      "cost": out.get("cost"), "model": out.get("model")}
            except Exception as e:  # keep going; the case is stored with its error
                doc["cases"][c.id] = {"error": f"{type(e).__name__}: {e}"[:300],
                                      "ms": round((time.time() - t0) * 1000)}
                print(f"{phase} {c.id}: ERROR {e}", flush=True)
            store.save(out_run, phase, doc)
            p = doc["cases"][c.id].get("answers", {}).get("manipulation", {}).get("noul")
            print(f"{phase} {c.id}: manipulation={p}", flush=True)
        n = sum("answers" in x for x in doc["cases"].values())
        print(f"--- {phase}: {n}/{len(cases)} done ---", flush=True)


if __name__ == "__main__":
    main()
