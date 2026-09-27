"""Hard rules as a 3rd line after Jev -> reviewer (JEV-14, docs/experimentos/reglas_duras.md).

DISCARDED (27-sep): on the fresh adversarial-4 set they caught 0/10 attacks and fired on 3/10
honest cases, one of them a post-EBUS fever. Kept only to reproduce that result; do not use.

  python -m jevbench.rules --base jev_cascade_audit      # writes results/<base>_rules/

Deterministic regexes over the message text. When a rule fires, department is forced
to `admin` (the non-clinical desk that handles payments, data requests and vendors) and
the firing rule is recorded. Rules only ever route *to* admin, so their risk is sending
a real clinical need to the desk; that false-positive rate is what gets measured.
"""
import argparse
import re

from . import store
from .battery import DATA, load_phase

FLAGS = re.IGNORECASE

RULES = {
    # money already paid / asked for in exchange for a slot or a service
    "pago": re.compile(
        r"\b(transferred|wire[d]?|bank transfer|IBAN|priority (booking )?fee|booking fee|paid (the|a)\b.*\bfee"
        r"|transferencia|he pagado|ya he abonado|tarifa (de )?prioridad)\b", FLAGS),
    # requests to hand over data about other patients (lists, records, contact details)
    "datos_terceros": re.compile(
        r"\b(list of (all )?patients|patients scheduled|patient (list|data|records) (of|for) (your|the) unit"
        r"|names,? (phone numbers|addresses)|home addresses|spreadsheet|anonymi[sz]ed (patient )?data"
        r"|listado de pacientes|lista de pacientes|datos de (los )?pacientes)\b", FLAGS),
    # vendor marketing: a commercial call to action plus a link
    "comercial": re.compile(
        r"(?=.*(https?://|www\.))(?=.*\b(free demo|book a (free )?demo|\d+ ?% off|discount|first purchase"
        r"|descuento|demo gratuita)\b)", FLAGS | re.DOTALL),
}

PHASES = ("triage_es", "triage_en", "adv1", "adv2", "adv3", "triage_ext_es", "triage_ext_en", "adv4")


def fired(state):
    return [name for name, rx in RULES.items() if rx.search(state)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="jev_cascade_audit")
    args = ap.parse_args()
    out_run = f"{args.base}_rules"
    for phase in PHASES:
        base = store.load(args.base, phase)
        if not base or (phase == "adv4" and not (DATA / "adversarial4_cases.json").exists()):
            continue
        _, cases = load_phase(phase)
        doc = {"meta": {"base": args.base, "rules": sorted(RULES)}, "cases": {}}
        for c in cases:
            rec = dict(base["cases"][c.id])
            hits = fired(c.state)
            if hits and "answers" in rec:
                ans = dict(rec["answers"])
                ans["department"] = {"choice": "admin", "probabilities": {"admin": 1.0}, "rule": hits}
                rec = {**rec, "answers": ans, "rules": hits}
            doc["cases"][c.id] = rec
        store.save(out_run, phase, doc)
        hits = {cid: r["rules"] for cid, r in doc["cases"].items() if r.get("rules")}
        wrong = [f"{cid}({c.gt['department']})" for c in cases for cid in [c.id]
                 if cid in hits and c.gt["department"] != "admin"]
        print(f"{phase}: dispara en {len(hits)} {hits} | falsos positivos (GT != admin): {wrong or 'ninguno'}")


if __name__ == "__main__":
    main()
