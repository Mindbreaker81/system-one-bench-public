"""Cobertura / NO EVALUABLE de scripts/jev84_analyze.py (JEV-84 R69 F1)."""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import cost_guard, store
from jevbench.battery import load_phase
from jevbench.score import ADJ_PHASES

_CFG_SHA = cost_guard.config_sha256({
    "provider": "fake", "model": "same-alias", "resolved": "snapshot-A",
    "thinking": "adaptive", "effort": "medium", "max_tokens": 8192,
})

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "jev84_analyze.py"
_spec = importlib.util.spec_from_file_location("jev84_analyze", _SCRIPT)
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)


def _empty_answers(qs):
    answers = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            lab = next(iter(q["criteria"]))
            answers[qid] = {"type": "choice", "choice": lab,
                            "probabilities": {lab: 1.0}}
        elif q["type"] == "score":
            answers[qid] = {"type": "score", "score": 0.0,
                            "probabilities": {"0": 1.0}}
        else:
            answers[qid] = {"type": "noul", "noul": 0.0}
    return answers


def _seed_complete(run, phases=None, meta=None, stamp=False):
    for ph in (phases or ADJ_PHASES):
        qs, cases = load_phase(ph)
        doc = {"meta": dict(meta or {}), "cases": {}}
        for c in cases:
            rec = {"answers": _empty_answers(qs), "cost": 0.0}
            if stamp:
                rec["config_sha256"] = (meta or {}).get(
                    "config_sha256", _CFG_SHA)
                if (meta or {}).get("resolved"):
                    rec["resolved"] = meta["resolved"]
                if (meta or {}).get("model"):
                    rec["model"] = meta.get("resolved") or meta["model"]
            doc["cases"][c.id] = rec
        store.save(run, ph, doc)


def _seed_empty(run, phases=None, meta=None):
    for ph in (phases or ADJ_PHASES):
        store.save(run, ph, {"meta": dict(meta or {}), "cases": {}})


class Jev84AnalyzeCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jev84an_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def test_familia_r_incompleta_no_interpreta_faltantes(self):
        """R69 F1: cascada vacía vs D1/ref completos → 212 incompletas, 0 sig."""
        for d1, casc, ref in an.R_PAIRS:
            _seed_empty(casc)
            _seed_complete(d1)
            _seed_complete(ref)
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        self.assertTrue(all(c["incomplete"] for c in cells))
        self.assertEqual(sum(1 for c in cells if c.get("sig_holm")), 0)
        self.assertTrue(all(c["p"] is None for c in cells))

    def test_familia_r_parcial_fase_incompleta(self):
        """Una fase a medias marca sus celdas incompletas; el resto puede evaluar."""
        for d1, casc, ref in an.R_PAIRS:
            _seed_complete(d1)
            _seed_complete(ref)
            _seed_complete(casc, meta={"d1": d1})
            raw = casc.replace("_audit", "_raw")
            _seed_complete(raw, meta={
                "d1": d1, "reviewer": "fake",
                "prefix": casc.replace("_audit", ""),
                "reviewer_resolved": "snap-A"}, stamp=True)
            for ph in ("adv3", "adv4", "adv5"):
                doc = store.load(raw, ph)
                for rec in doc["cases"].values():
                    rec["answers"]["manipulation"] = {"noul": 0.1}
                store.save(raw, ph, doc)
            # vaciar ood en cascada
            store.save(casc, "ood", {"meta": {"d1": d1}, "cases": {}})
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        ood = [c for c in cells if c["phase"] == "ood"]
        self.assertTrue(ood and all(c["incomplete"] for c in ood))
        other = [c for c in cells if c["phase"] != "ood"]
        self.assertTrue(other and all(not c["incomplete"] for c in other))

    def test_run_status_cost_stop_no_evaluable(self):
        status, detail = an.run_acquisition_status(
            "x_audit", raw_run="x_raw",
            check_alert_raw=True)
        self.assertEqual(status, "NO_EVALUABLE")  # missing
        _seed_complete("x_audit")
        _seed_complete("x_raw", phases=("adv3", "adv4", "adv5"),
                       meta={"cost_stop": {"reason": "accumulated_cost"}})
        # completar raw de alerta en adv* con answers
        for ph in ("adv3", "adv4", "adv5"):
            qs, cases = load_phase(ph)
            # manipulation only for raw alert path — use full answers ok
            doc = store.load("x_raw", ph)
            doc["meta"]["cost_stop"] = {"reason": "case_cost"}
            store.save("x_raw", ph, doc)
        status, detail = an.run_acquisition_status(
            "x_audit", raw_run="x_raw", check_alert_raw=True)
        self.assertEqual(status, "NO_EVALUABLE")
        self.assertIn("cost_stop", str(detail))

    def test_alert_raw_incompleto_con_audit_completo(self):
        _seed_complete("casc_audit")
        # raw ausente → no evaluable
        status, _ = an.run_acquisition_status(
            "casc_audit", raw_run="casc_raw", check_alert_raw=True)
        self.assertEqual(status, "NO_EVALUABLE")
        # raw parcial (falta un caso)
        for ph in ("adv3", "adv4", "adv5"):
            qs, cases = load_phase(ph)
            doc = {"meta": {}, "cases": {}}
            for c in cases[:-1]:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}}}
            store.save("casc_raw", ph, doc)
        status, detail = an.run_acquisition_status(
            "casc_audit", raw_run="casc_raw", check_alert_raw=True)
        self.assertEqual(status, "NO_EVALUABLE")

    def test_a_documentos_vacios_no_evaluable(self):
        for ph in ("adv3", "adv4", "adv5"):
            store.save(an.ALERT_RUN, ph, {"meta": {}, "cases": {}})
        ok, detail = an.alert_onepass_coverage(an.ALERT_RUN)
        self.assertFalse(ok)
        self.assertIn("missing", str(detail).lower() + str(detail))

    def test_a_error_residual_no_evaluable(self):
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {}, "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.9}}}
            # un error residual
            doc["cases"][cases[0].id] = {"error": "Timeout"}
            store.save(an.ALERT_RUN, ph, doc)
        ok, detail = an.alert_onepass_coverage(an.ALERT_RUN)
        self.assertFalse(ok)

    def test_a_completo_ok(self):
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {"resolved": "snapshot-A"}, "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                    "config_sha256": _CFG_SHA, "resolved": "snapshot-A"}
            store.save(an.ALERT_RUN, ph, doc)
        ok, detail = an.alert_onepass_coverage(an.ALERT_RUN)
        self.assertTrue(ok)
        self.assertEqual(detail.get("n_ok"), 60)

    def test_a_sin_config_sha_no_evaluable(self):
        """R72: cobertura A sin huella por caso → NO EVALUABLE."""
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {"resolved": "A"}, "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}}}
            store.save(an.ALERT_RUN, ph, doc)
        ok, detail = an.alert_onepass_coverage(an.ALERT_RUN)
        self.assertFalse(ok)
        self.assertIn("config_provenance", detail)

    def test_main_a_vacio_no_keyerror(self):
        """Documentos presentes con cases={} → NO EVALUABLE, no KeyError."""
        for ph in ("adv3", "adv4", "adv5"):
            store.save(an.ALERT_RUN, ph, {"meta": {}, "cases": {}})
        with mock.patch.object(an, "R_PAIRS", ()), \
             mock.patch.object(an, "S_RUNS", ("s1", "s2")), \
             mock.patch("sys.argv", ["jev84_analyze.py"]):
            # no debe lanzar
            an.main()

    def test_pregunta_ausente_no_keyerror_no_evaluable(self):
        """R70-2: falta una pregunta → None, sin KeyError."""
        _seed_complete("missing_q")
        doc = store.load("missing_q", "ood")
        first = next(iter(doc["cases"]))
        qid = next(iter(doc["cases"][first]["answers"]))
        del doc["cases"][first]["answers"][qid]
        store.save("missing_q", "ood", doc)
        self.assertIsNone(an.phase_score_complete("missing_q", "ood"))

    def test_answers_ausente_no_keyerror(self):
        """R70-2: caso sin answers → None, sin crash."""
        _seed_complete("no_ans")
        doc = store.load("no_ans", "ood")
        first = next(iter(doc["cases"]))
        doc["cases"][first] = {"cost": 0.0}
        store.save("no_ans", "ood", doc)
        self.assertIsNone(an.phase_score_complete("no_ans", "ood"))

    def test_alerta_manipulation_malformada_no_evaluable(self):
        """R70-2: manipulation vacía / None / texto / NaN → cobertura False."""
        import math
        for label, noul in (
            ("empty", None),  # answers manipulation = {}
            ("none", None),
            ("text", "nope"),
            ("nan", float("nan")),
            ("neg", -0.1),
            ("gt1", 1.5),
        ):
            run = f"bad_{label}"
            for ph in ("adv3", "adv4", "adv5"):
                _, cases = load_phase(ph)
                doc = {"meta": {}, "cases": {}}
                for c in cases:
                    if label == "empty":
                        ans = {"manipulation": {}}
                    elif label == "none":
                        ans = {"manipulation": {"type": "noul", "noul": None}}
                    else:
                        ans = {"manipulation": {"type": "noul", "noul": noul}}
                    doc["cases"][c.id] = {"answers": ans}
                store.save(run, ph, doc)
            ok, _ = an.alert_onepass_coverage(run)
            self.assertFalse(ok, label)
            # hits no debe crashear
            ids, hits = an.onepass_alert_hits(run)
            self.assertEqual(len(ids), 60)
            self.assertTrue(all(h is None for h in hits), label)

    def test_raw_ood_cost_stop_no_evaluable(self):
        """R70-3: cost_stop en raw/ood (fuera de adv*) → NO EVALUABLE."""
        _seed_complete("r_audit")
        _seed_complete("r_raw")
        doc = store.load("r_raw", "ood")
        doc["meta"]["cost_stop"] = {"reason": "case_cost"}
        store.save("r_raw", "ood", doc)
        # completar manipulation en adv* del raw
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            d = store.load("r_raw", ph)
            for c in cases:
                d["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}}}
            store.save("r_raw", ph, d)
        status, detail = an.run_acquisition_status(
            "r_audit", raw_run="r_raw", check_alert_raw=True)
        self.assertEqual(status, "NO_EVALUABLE")
        self.assertIn("ood", str(detail))

    def test_version_drift_alerta_no_evaluable(self):
        """R70-3: meta.version_drift → cobertura alerta False."""
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {"version_drift": {"frozen": "A", "observed": "B"}},
                   "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}}}
            store.save(an.ALERT_RUN, ph, doc)
        ok, detail = an.alert_onepass_coverage(an.ALERT_RUN)
        self.assertFalse(ok)
        self.assertIn("drift", str(detail).lower() + str(detail))

    def test_replica_cost_stop_no_evaluable_ni_estable(self):
        """R70-3: cost_stop en réplica → evaluable=False, stable_ge_95=False."""
        _seed_complete("s1")
        _seed_complete("s2")
        doc = store.load("s2", "ood")
        doc["meta"]["cost_stop"] = {"reason": "case_cost"}
        store.save("s2", "ood", doc)
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement("s1", "s2")
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_replica_version_modelo_mezclado_no_evaluable(self):
        """R71 P1-1: meta.resolved / model por caso mezclados → no estable."""
        meta = {"model": "alias", "resolved": "A", "thinking": "adaptive",
                "config_sha256": _CFG_SHA}
        _seed_complete("s1", meta=meta, stamp=True)
        _seed_complete("s2", meta=meta, stamp=True)
        doc = store.load("s2", "ood")
        doc["meta"]["resolved"] = "B"
        for rec in doc["cases"].values():
            rec["model"] = "B"
            rec["resolved"] = "B"
        store.save("s2", "ood", doc)
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement("s1", "s2")
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])
        self.assertFalse(s["identity_ok"])
        self.assertTrue(
            "resolved_conflict" in s["provenance_b"]
            or len(s["provenance_b"].get("versions", [])) > 1
            or s["provenance_b"].get("model_conflict"))

    def test_replica_max_tokens_distintos_no_evaluable(self):
        """R72-P1-2a: config_sha256 distinta entre réplicas → no estable."""
        sha_a = cost_guard.config_sha256({"max_tokens": 8192, "effort": "medium"})
        sha_b = cost_guard.config_sha256({"max_tokens": 4096, "effort": "medium"})
        self.assertNotEqual(sha_a, sha_b)
        meta_a = {"model": "same-alias", "resolved": "snapshot-A",
                  "config_sha256": sha_a}
        meta_b = {"model": "same-alias", "resolved": "snapshot-A",
                  "config_sha256": sha_b}
        _seed_complete("s_tok_a", meta=meta_a, stamp=True)
        _seed_complete("s_tok_b", meta=meta_b, stamp=True)
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement("s_tok_a", "s_tok_b")
        self.assertFalse(s["identity_ok"])
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_replica_sin_huella_sin_identidad_no_evaluable(self):
        """Sin huella y sin identidad de meta usable → NO_EVALUABLE."""
        _seed_complete("s_nohash_a", meta={})
        _seed_complete("s_nohash_b", meta={})
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement("s_nohash_a", "s_nohash_b")
        self.assertFalse(s["identity_ok"])
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_familia_r_raw_ood_cost_stop_incompleta(self):
        """R71 P1-2: raw/ood.cost_stop con audit completo → Holm no evaluable."""
        for d1, casc, ref in an.R_PAIRS:
            for r in (d1, casc, ref):
                _seed_complete(r, meta={"d1": d1} if r == casc else None)
            raw = casc.replace("_audit", "_raw")
            _seed_complete(raw, meta={
                "d1": d1, "reviewer": "fake",
                "prefix": casc.replace("_audit", ""),
                "reviewer_resolved": "snap-A"}, stamp=True)
            for ph in ("adv3", "adv4", "adv5"):
                doc = store.load(raw, ph)
                for rec in doc["cases"].values():
                    rec["answers"]["manipulation"] = {"noul": 0.1}
                store.save(raw, ph, doc)
            doc = store.load(raw, "ood")
            doc["meta"]["cost_stop"] = {"reason": "case_cost"}
            store.save(raw, "ood", doc)
        status, _ = an.run_acquisition_status(
            an.R_PAIRS[0][1],
            raw_run=an.R_PAIRS[0][1].replace("_audit", "_raw"),
            check_alert_raw=True, expected_d1=an.R_PAIRS[0][0])
        self.assertEqual(status, "NO_EVALUABLE")
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        self.assertTrue(all(c["incomplete"] for c in cells))
        self.assertTrue(all(c["p"] is None for c in cells))
        self.assertEqual(sum(1 for c in cells if c.get("sig_holm")), 0)
        self.assertTrue(all(c.get("raw_blocked") for c in cells))

    def test_familia_r_conflicto_huella_raw_incompleta(self):
        """R73-P1-1: conflicto config_sha256 en raw → Holm incompleta (misma puerta)."""
        for d1, casc, ref in an.R_PAIRS:
            for r in (d1, casc, ref):
                _seed_complete(r, meta={"d1": d1} if r == casc else None)
            raw = casc.replace("_audit", "_raw")
            _seed_complete(raw, meta={
                "d1": d1, "reviewer": "fake",
                "prefix": casc.replace("_audit", ""),
                "reviewer_resolved": "snap-A"}, stamp=True)
            for ph in ("adv3", "adv4", "adv5"):
                doc = store.load(raw, ph)
                for rec in doc["cases"].values():
                    rec["answers"]["manipulation"] = {"noul": 0.1}
                store.save(raw, ph, doc)
            doc = store.load(raw, "ood")
            next(iter(doc["cases"].values()))["config_sha256"] = "different-config"
            store.save(raw, "ood", doc)
        status, _ = an.run_acquisition_status(
            an.R_PAIRS[0][1],
            raw_run=an.R_PAIRS[0][1].replace("_audit", "_raw"),
            check_alert_raw=True, expected_d1=an.R_PAIRS[0][0])
        self.assertEqual(status, "NO_EVALUABLE")
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        self.assertTrue(all(c["incomplete"] for c in cells))
        self.assertEqual(sum(1 for c in cells if c.get("sig_holm")), 0)
        self.assertTrue(all(c.get("raw_blocked") for c in cells))

    def test_familia_r_sin_huella_raw_incompleta(self):
        """R73-P1-1: raw sin config_sha256 → Holm incompleta."""
        for d1, casc, ref in an.R_PAIRS:
            for r in (d1, casc, ref):
                _seed_complete(r, meta={"d1": d1} if r == casc else None)
            raw = casc.replace("_audit", "_raw")
            _seed_complete(raw, meta={
                "d1": d1, "reviewer": "fake",
                "prefix": casc.replace("_audit", ""),
                "reviewer_resolved": "snap-A"})
            for ph in ("adv3", "adv4", "adv5"):
                doc = store.load(raw, ph)
                for rec in doc["cases"].values():
                    rec["answers"]["manipulation"] = {"noul": 0.1}
                store.save(raw, ph, doc)
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        self.assertTrue(all(c["incomplete"] for c in cells))
        self.assertEqual(sum(1 for c in cells if c.get("sig_holm")), 0)

    def test_familia_r_d1_mezclado_incompleta(self):
        """R73-P1-2: raw con d1 distinto al esperado por R_PAIRS → incompleta."""
        for d1, casc, ref in an.R_PAIRS:
            for r in (d1, casc, ref):
                _seed_complete(r, meta={"d1": d1} if r == casc else None)
            raw = casc.replace("_audit", "_raw")
            wrong = "jev_v3" if d1 == "decider_4b" else "decider_4b"
            _seed_complete(raw, meta={
                "d1": wrong, "reviewer": "fake",
                "prefix": casc.replace("_audit", ""),
                "reviewer_resolved": "snap-A"}, stamp=True)
            for ph in ("adv3", "adv4", "adv5"):
                doc = store.load(raw, ph)
                for rec in doc["cases"].values():
                    rec["answers"]["manipulation"] = {"noul": 0.1}
                store.save(raw, ph, doc)
        cells = an.family_r_mcnemar()
        self.assertEqual(len(cells), 212)
        self.assertTrue(all(c["incomplete"] for c in cells))
        self.assertEqual(sum(1 for c in cells if c.get("sig_holm")), 0)

    def test_replica_answers_none_no_typeerror(self):
        """R71 P2-2: answers=None → NO_EVALUABLE, sin TypeError."""
        _seed_complete("invalid_s1")
        _seed_complete("invalid_s2")
        doc = store.load("invalid_s2", "ood")
        first = next(iter(doc["cases"]))
        doc["cases"][first]["answers"] = None
        store.save("invalid_s2", "ood", doc)
        s = an.replica_agreement("invalid_s1", "invalid_s2")
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_replica_r2_sin_huella_no_evaluable(self):
        """R74-P1-1: r2 nueva sin huella no admite bypass histórico → NO_EVALUABLE."""
        meta = {"model": "claude-haiku-5-5", "resolved": "claude-haiku-5-5",
                "thinking": "adaptive", "effort": "medium", "max_tokens": 8192,
                "structured": True, "mode": "probabilities",
                "questions_hash": "qh-test"}
        r1, r2 = an.S_RUNS
        self.assertIn(r1, an.HISTORICAL_REFERENCE_RUNS)
        self.assertNotIn(r2, an.HISTORICAL_REFERENCE_RUNS)
        _seed_complete(r1, meta=meta)
        _seed_complete(r2, meta=meta)  # sin stamp: falta huella
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement(r1, r2)
        self.assertEqual(s["provenance_a"].get("kind"),
                         "procedencia histórica (meta de fase)")
        self.assertNotEqual(s["provenance_b"].get("kind"),
                            "procedencia histórica (meta de fase)")
        self.assertFalse(s["identity_ok"])
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_replica_historica_r1_con_r2_sellada_evaluable(self):
        """R74-P1-1 positivo: r1 histórica + r2 sellada misma config → evaluable."""
        meta = {"model": "claude-haiku-5-5", "resolved": "claude-haiku-5-5",
                "thinking": "adaptive", "effort": "medium", "max_tokens": 8192,
                "structured": True, "mode": "probabilities",
                "questions_hash": "qh-test"}
        r1, r2 = an.S_RUNS
        _seed_complete(r1, meta=meta)
        _seed_complete(r2, meta=meta, stamp=True)
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement(r1, r2)
        self.assertEqual(s["provenance_a"].get("kind"),
                         "procedencia histórica (meta de fase)")
        self.assertEqual(s["provenance_b"].get("kind"),
                         "huella por registro")
        self.assertTrue(s["identity_ok"])
        self.assertTrue(s["evaluable"])
        self.assertTrue(s["stable_ge_95"])

    def test_replica_historica_meta_conflicto_no_evaluable(self):
        """R74: r1 histórica vs r2 sellada con effort distinto → no evaluable."""
        meta_a = {"model": "claude-haiku-5-5", "resolved": "A",
                  "thinking": "adaptive", "effort": "medium", "max_tokens": 8192,
                  "structured": True, "mode": "probabilities",
                  "questions_hash": "qh-test"}
        meta_b = dict(meta_a, effort="high")
        r1, r2 = an.S_RUNS
        _seed_complete(r1, meta=meta_a)
        _seed_complete(r2, meta=meta_b, stamp=True)
        with mock.patch.object(an, "_paired_adjusted_delta",
                               return_value=(0, 0, 0)):
            s = an.replica_agreement(r1, r2)
        self.assertFalse(s["identity_ok"])
        self.assertFalse(s["evaluable"])
        self.assertFalse(s["stable_ge_95"])

    def test_a_ref_historica_sin_huella_ok(self):
        """R73/R74: ref A en lista blanca sin huella pero meta estable → OK."""
        ref = an.ALERT_REFS[0]
        self.assertIn(ref, an.HISTORICAL_REFERENCE_RUNS)
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {"model": "Cloudflare/clef", "adapter": "clef"},
                   "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                    "model": "Cloudflare/clef"}
            store.save(ref, ph, doc)
        ok, detail = an.alert_onepass_coverage(
            ref, allow_historical=an.historical_allowed_for(ref))
        self.assertTrue(ok)
        self.assertEqual(
            (detail.get("config_provenance") or {}).get("kind"),
            "procedencia histórica (meta de fase)")
        self.assertEqual(detail.get("n_ok"), 60)

    def test_a_nuevo_sin_huella_no_evaluable(self):
        """R74-P1-1: adquisición A nueva sin huella → NO_EVALUABLE (no histórico)."""
        run = "llm_haiku55_adapt_alert_raw_nuevo"
        self.assertNotIn(run, an.HISTORICAL_REFERENCE_RUNS)
        for ph in ("adv3", "adv4", "adv5"):
            _, cases = load_phase(ph)
            doc = {"meta": {"model": "claude-haiku-5-5", "adapter": "llm"},
                   "cases": {}}
            for c in cases:
                doc["cases"][c.id] = {
                    "answers": {"manipulation": {"type": "noul", "noul": 0.1}},
                    "model": "claude-haiku-5-5"}
            store.save(run, ph, doc)
        ok, detail = an.alert_onepass_coverage(run, allow_historical=True)
        self.assertFalse(ok)
        self.assertFalse(detail.get("config_provenance_ok", True))


if __name__ == "__main__":
    unittest.main()
