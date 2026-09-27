"""Convert Lyra's legacy result JSONs into results/legacy_<run>/<phase>.json so the
new scorer can re-score them (the harness is validated when the numbers match the
reports).  python -m jevbench.legacy_import"""
import json
from pathlib import Path

from . import store
from .battery import load_phase

LEG = Path(__file__).resolve().parent.parent / "legacy" / "lyra_laya_vs_jev"

# run -> phase -> (file, optional key into the file)
SOURCES = {
    "legacy_jev_v1": {  # 20-sep; adv1 used an admin description with "catering, logistics"
        "triage_es": ("jev_results.json", "jev_es"), "triage_en": ("jev_results.json", "jev_en"),
        "papers32": ("papers32_jev.json", None), "adv1": ("adversarial_results.json", "jev")},
    "legacy_jev_v2": {  # 23-sep rerun, jev-1.13-20260917
        "triage_es": ("rerun/jev_triage_v2.json", "jev_es"), "triage_en": ("rerun/jev_triage_v2.json", "jev_en"),
        "papers32": ("rerun/papers32_jev_v2.json", None), "adv1": ("rerun/adversarial_jev_v2.json", None),
        "adv2": ("rerun/adversarial2_results.json", "jev"), "ood": ("rerun/ood_jev_v2.json", None)},
    "legacy_laya_v1": {
        "triage_es": ("laya_results.json", "laya_ml_es"), "triage_en": ("laya_results.json", "laya_en_en"),
        "papers32": ("papers32_laya.json", None), "adv1": ("adversarial_results.json", "laya")},
    "legacy_laya_v2": {
        "triage_es": ("rerun/laya_triage_v2.json", "laya_ml_es"), "triage_en": ("rerun/laya_triage_v2.json", "laya_en_en"),
        "papers32": ("rerun/papers32_laya_v2.json", None), "adv1": ("rerun/adversarial_laya_v2.json", None),
        "adv2": ("rerun/adversarial2_results.json", "laya")},
    "legacy_gliner_decide": {
        "triage_es": ("gliner_decide/gliner_triage.json", "gliner_es"),
        "triage_en": ("gliner_decide/gliner_triage.json", "gliner_en"),
        "papers32": ("gliner_decide/gliner_papers32.json", None),
        "adv1": ("gliner_decide/gliner_adversarial1.json", None), "adv2": ("gliner_decide/gliner_adversarial2.json", None)},
    "legacy_anyjev_qwen3_1.7b": {
        "triage_es": ("anyjev_results/anyjev_triage_qwen3_1.7b.json", "anyjev_es"),
        "triage_en": ("anyjev_results/anyjev_triage_qwen3_1.7b.json", "anyjev_en"),
        "papers32": ("anyjev_results/anyjev_papers32_qwen3_1.7b.json", None),
        "adv1": ("anyjev_results/anyjev_adv1_qwen3_1.7b.json", None),
        "adv2": ("anyjev_results/anyjev_adv2_qwen3_1.7b.json", None),
        "ood": ("anyjev_results/anyjev_ood_qwen3_1.7b.json", None)},
}


def to_wire(pred, qs):
    ans = {}
    for name, q in qs.items():
        v = pred[name]
        if q["type"] == "choice":
            ans[name] = {"choice": v, "probabilities": pred.get(f"{name}_probs")}
        elif q["type"] == "score":
            ans[name] = {"score": float(v), "probabilities": pred.get(f"{name}_probs")}
        else:
            ans[name] = {"noul": {"yes": 1.0, "no": 0.0}[v] if isinstance(v, str) else float(v)}
    return ans


def main():
    for run, phases in SOURCES.items():
        for phase, (fname, key) in phases.items():
            data = json.loads((LEG / fname).read_text())
            rows = data[key] if key else data
            qs, _ = load_phase(phase)
            cases = {}
            for r in rows:
                cid = r.get("case") or r.get("pid")
                if "error" in r or "pred" not in r:
                    cases[cid] = {"error": r.get("error", "missing pred")}
                    continue
                cases[cid] = {"answers": to_wire(r["pred"], qs), "ms": r.get("ms"), "model": r.get("model")}
            meta = {"source": f"legacy/lyra_laya_vs_jev/{fname}" + (f"[{key}]" if key else ""), "imported": True}
            store.save(run, phase, {"meta": meta, "cases": cases})
        print(f"{run}: {', '.join(phases)}")


if __name__ == "__main__":
    main()
