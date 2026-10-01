"""Run a model on the battery. Resumable: cases already answered are skipped.

  python -m jevbench.run jev --run jev_v3
  python -m jevbench.run decider --run decider_2b --opt model=Mapika/decider-2b --opt device=cuda
  python -m jevbench.run anyjev --run anyjev_qwen3_8b --opt model=Qwen/Qwen3-8B --phases triage_es,triage_en
  python -m jevbench.run jev --run smoke --phases ood --limit 1
"""
import argparse
import datetime as dt
import platform
import subprocess
import sys
import time
import traceback

from . import adapters, store
from .battery import EXTRA_PHASES, PHASES, load_phase, missing_abstracts, questions_hash
from .redact import redact_options


def safe_opts(opts):
    """opts as stored in meta; the adapter still receives the original values."""
    return redact_options(opts)


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=store.ROOT.parent).stdout.strip() or None
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter", choices=sorted(adapters.REGISTRY))
    ap.add_argument("--run", required=True, help="results/<run>/ directory name")
    ap.add_argument("--phases", default="all")
    ap.add_argument("--opt", action="append", default=[], help="adapter option k=v (repeatable)")
    ap.add_argument("--limit", type=int, help="max cases per phase (smoke tests)")
    ap.add_argument("--retry-errors", action="store_true", help="re-run cases stored with an error")
    args = ap.parse_args()

    phases = PHASES if args.phases == "all" else (PHASES + EXTRA_PHASES if args.phases == "all+new" else args.phases.split(","))
    missing = [f"{ph}:{pid}" for ph in phases for pid in missing_abstracts(ph)]
    if missing:
        sys.exit(f"{len(missing)} papers sin abstract ({', '.join(missing[:5])}…): "
                 f"ejecuta `python3 -m jevbench.fetch_abstracts`")
    opts = dict(o.split("=", 1) for o in args.opt)
    t0 = time.time()
    model = adapters.get(args.adapter)(**opts)
    print(f"[{args.adapter}] ready in {time.time() - t0:.0f}s {model.meta()}", flush=True)

    for phase in phases:
        qs, cases = load_phase(phase)
        doc = store.load(args.run, phase) or {"meta": {}, "cases": {}}
        doc["meta"].update({
            "adapter": args.adapter, "opts": safe_opts(opts), **model.meta(), "phase": phase,
            "questions_hash": questions_hash(qs), "host": platform.node(), "arch": platform.machine(),
            "python": sys.version.split()[0], "git": git_rev(),
            "updated": dt.datetime.now().isoformat(timespec="seconds")})
        todo = [c for c in cases if c.id not in doc["cases"]
                or (args.retry_errors and "error" in doc["cases"][c.id])]
        done = len(cases) - len(todo)
        if args.limit:
            todo = todo[:args.limit]
        print(f"--- {phase}: {len(todo)} to run ({done} already done) ---", flush=True)
        for c in todo:
            t1 = time.time()
            try:
                out = model.decide(c.state, qs)
                rec = {"answers": out["answers"], "ms": round((time.time() - t1) * 1000),
                       "cost": out.get("cost"), "model": out.get("model")}
                if "usage" in out:  # compact telemetry only; never prompts or bodies
                    rec["usage"] = {k: v for k, v in out["usage"].items()
                                    if isinstance(v, (int, float, str, bool, type(None)))}
                if "raw" in out:
                    rec["raw"] = out["raw"]
                short = " ".join(f"{k}={v.get('choice', v.get('score', v.get('noul')))!s:.6}" for k, v in out["answers"].items())
                print(f"{phase} {c.id}: {short} | {rec['ms']}ms", flush=True)
            except Exception as e:  # keep going; the case is stored with its error
                traceback.print_exc()
                rec = {"error": f"{type(e).__name__}: {e}"[:300], "ms": round((time.time() - t1) * 1000)}
                diag = getattr(e, "diag", None)
                if isinstance(diag, dict) and diag:
                    rec["diag"] = diag
                print(f"{phase} {c.id}: ERROR {rec['error'][:120]}", flush=True)
            doc["cases"][c.id] = rec
            doc["meta"].update(model.meta())
            store.save(args.run, phase, doc)
    cost = sum(r.get("cost") or 0 for p in phases for r in (store.load(args.run, p) or {"cases": {}})["cases"].values())
    print(f"[{args.adapter}] done in {time.time() - t0:.0f}s, accumulated cost ${cost:.5f}", flush=True)


if __name__ == "__main__":
    main()
