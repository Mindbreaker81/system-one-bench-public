"""Tests offline de jevbench.jev90 (JEV-90: puerta de snapshot, Holm
confirmatorio sin IDs expuestos, discordancias department, negativas
por pregunta). No toca el comportamiento por defecto de jev81/jev82/score."""
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from jevbench import jev81, jev82, jev90, run, score, store
from jevbench.adapters import Adapter
from jevbench.battery import load_phase, questions_hash
from jevbench.rotation import order_manifest, reorder_choice, resolve_choice_order


class TmpStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="j90_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)


def _answers(qs, gt, bad=False, refuse=()):
    out = {}
    for qid, q in qs.items():
        if qid in refuse:
            out[qid] = {"type": "refusal"}
            continue
        v = gt.get(qid)
        if q["type"] == "choice":
            labels = list(q["criteria"])
            pick = (v if not bad else
                    next(l for l in labels if l != v))
            out[qid] = {"type": "choice", "choice": pick,
                        "probabilities": {o: (0.9 if o == pick else 0.0)
                                          for o in labels}}
        elif q["type"] == "score":
            out[qid] = {"type": "score", "score": float(v or 0),
                        "probabilities": {str(i): 0.5
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"type": "noul", "noul": float(bool(v))}
    return out


def _write_phase(run, phase, model=jev90.EXPECTED_SNAPSHOT, cost=0.0001,
                 wrong_ids=(), refuse_ids=None, refuse_q=(),
                 ledger=None, skip_ids=()):
    qs, cases = load_phase(phase)
    meta = {"adapter": "jev", "phase": phase,
            "questions_hash": questions_hash(qs),
            "opts": {"provider": "openrouter",
                     "model": "microsoft/microsoft-decision-1"},
            "resolved": model}
    if ledger is not None:
        meta["cost_ledger"] = ledger
    doc = {"meta": meta, "cases": {}}
    refuse_ids = set(refuse_ids or ())
    wrong = set(wrong_ids)
    skip = set(skip_ids)
    for c in cases:
        if c.id in skip:
            continue
        if c.id in refuse_ids:
            # negativa parcial: refusal en refuse_q (default department)
            rq = refuse_q or ("department",)
            doc["cases"][c.id] = {
                "answers": _answers(qs, c.gt, refuse=rq),
                "ms": 100, "cost": cost, "model": model,
                "refusals": list(rq)}
        else:
            doc["cases"][c.id] = {
                "answers": _answers(qs, c.gt, bad=(c.id in wrong)),
                "ms": 100, "cost": cost, "model": model}
    store.save(run, phase, doc)
    return doc


def _write_all(run, model=jev90.EXPECTED_SNAPSHOT, **kw):
    for ph in score.ADJ_PHASES:
        _write_phase(run, ph, model=model, **kw)


def _stamp_provenance(run, spec="d0"):
    """Declara choice_order/perm_sha256 (+ cost_guard en d1) por fase."""
    orders = resolve_choice_order(f"department:{spec}")
    for ph in score.ADJ_PHASES:
        qs, _ = load_phase(ph)
        doc = store.load(run, ph)
        if doc is None:
            continue
        meta = doc.setdefault("meta", {})
        opts = meta.setdefault("opts", {})
        opts["choice_order"] = f"department:{spec}"
        meta["choice_order"] = orders
        meta["perm_sha256"] = order_manifest(
            reorder_choice(qs, orders), orders)["perm_sha256"]
        if spec != "d0":
            meta["cost_guard"] = dict(jev82.COST_GUARD_SPEC)
        store.save(run, ph, doc)


def _one_change_d1(cid="T12_autorizacion_seguro"):
    _write_all("d0")
    _write_all("d1")
    qs, cases = load_phase("triage_es")
    case = next(c for c in cases if c.id == cid)
    doc = store.load("d1", "triage_es")
    doc["cases"][case.id]["answers"] = _answers(qs, case.gt, bad=True)
    store.save("d1", "triage_es", doc)


class TestExposedInventory(unittest.TestCase):
    def test_exposed_tags_congelados(self):
        tags = jev90.exposed_tags()
        self.assertEqual(tags, [
            "ood/contrato", "ood/receta",
            "triage_es/T01_ebus_alergia", "triage_es/T02_factura_duplicada",
        ])
        self.assertTrue(jev90.is_exposed("ood", "receta"))
        self.assertFalse(jev90.is_exposed("ood", "codigo"))

    def test_sondas_sinteticas_inventariadas(self):
        probes = jev90.EXPOSED_SYNTHETIC_PROBES
        self.assertTrue(any("Roast the chicken" in p["state_prefix"]
                            for p in probes))
        # no son ids del banco
        for ph in score.ADJ_PHASES:
            _, cases = load_phase(ph)
            ids = {c.id for c in cases}
            for p in probes:
                self.assertNotIn(p["id"], ids)


class TestHolmConfirm(TmpStore):
    def test_53_filas_y_exclusion(self):
        _write_all("a")
        _write_all("b")
        rows = jev90.holm_cells_confirm("a", "b")
        self.assertEqual(len(rows), 53)
        # ood tiene 3 casos; excluye 2 → n≤1 por celda ood
        ood = [r for r in rows if r["cell"].startswith("ood.")]
        self.assertTrue(ood)
        for r in ood:
            self.assertLessEqual(r["n"], 1)
            self.assertIn("receta", r["excluded"])

    def test_celda_vacia_p1(self):
        # run sin ood/codigo → tras exclusión ood queda n=0
        _write_all("a", skip_ids={"codigo"})
        _write_all("b", skip_ids={"codigo"})
        rows = jev90.holm_cells_confirm("a", "b")
        ood = [r for r in rows if r["cell"].startswith("ood.")]
        self.assertTrue(all(r["n"] == 0 and r["p"] == 1.0 for r in ood))
        # siguen entrando en Holm (p_holm presente)
        self.assertTrue(all("p_holm" in r for r in ood))


class TestSnapshotGate(TmpStore):
    def test_ok_con_snapshot_unico(self):
        _write_all("d0")
        gate = jev90.snapshot_gate("d0")
        self.assertTrue(gate["evaluable"])
        self.assertEqual(gate["versions_seen"], [jev90.EXPECTED_SNAPSHOT])

    def test_drift_no_evaluable(self):
        _write_all("d0")
        _write_phase("d0", "ood", model="microsoft/microsoft-decision-1-20990101")
        gate = jev90.snapshot_gate("d0")
        self.assertFalse(gate["evaluable"])
        self.assertTrue(gate["drift"])

    def test_par_exige_al_menos_un_par(self):
        _write_all("d0")
        # r2 vacío de éxitos: solo errores
        for ph in score.ADJ_PHASES:
            qs, cases = load_phase(ph)
            doc = {"meta": {"questions_hash": questions_hash(qs)},
                   "cases": {c.id: {"error": "HTTP Error 502: refused to answer question"}
                             for c in cases}}
            store.save("r2", ph, doc)
        gate = jev90.snapshot_gate_pair("d0", "r2")
        self.assertEqual(gate["n_valid_pairs"], 0)
        self.assertFalse(gate["evaluable"])

    def test_mixed_snapshots_pair_false(self):
        # A/A en unos y B/B en otros: jev81 same_model podría ser true,
        # pero la puerta de snapshot único exige EXPECTED en todos.
        _write_all("d0", model="microsoft/microsoft-decision-1-20261009")
        _write_all("d1", model="microsoft/microsoft-decision-1-20990101")
        gate = jev90.snapshot_gate_pair("d0", "d1")
        self.assertFalse(gate["evaluable"])


class TestDepartmentDiscords(TmpStore):
    def test_contador_y_lista(self):
        _write_all("d0")
        _write_all("d1")
        # fuerza un cambio en un caso no expuesto
        ph, cid = "triage_es", "T12_autorizacion_seguro"
        qs, cases = load_phase(ph)
        case = next(c for c in cases if c.id == cid)
        doc = store.load("d1", ph)
        doc["cases"][cid]["answers"] = _answers(qs, case.gt, bad=True)
        store.save("d1", ph, doc)
        dep = jev90.department_discords("d0", "d1")
        self.assertGreaterEqual(dep["n_changes"], 1)
        self.assertTrue(any(d["case"] == f"{ph}/{cid}" for d in dep["discords"]))

    def test_expuestos_fuera_del_conteo_confirmatorio(self):
        _write_all("d0")
        _write_all("d1")
        qs, cases = load_phase("ood")
        case = next(c for c in cases if c.id == "receta")
        doc = store.load("d1", "ood")
        # domain es la pregunta ood; department no está en ood — usar triage
        qs, cases = load_phase("triage_es")
        case = next(c for c in cases if c.id == "T01_ebus_alergia")
        doc = store.load("d1", "triage_es")
        doc["cases"][case.id]["answers"] = _answers(qs, case.gt, bad=True)
        store.save("d1", "triage_es", doc)
        conf = jev90.department_discords("d0", "d1", exclude_exposed=True)
        desc = jev90.department_discords("d0", "d1", exclude_exposed=False)
        self.assertEqual(conf["n_changes"], 0)
        self.assertGreaterEqual(desc["n_changes"], 1)

    def test_veredicto_no_evaluable_si_replica_cambia(self):
        _write_all("d0")
        _write_all("d1")
        _stamp_provenance("d1", "d1")
        _write_all("r2")
        qs, cases = load_phase("triage_es")
        case = next(c for c in cases if c.id == "T12_autorizacion_seguro")
        for rname in ("d1", "r2"):
            doc = store.load(rname, "triage_es")
            doc["cases"][case.id]["answers"] = _answers(qs, case.gt, bad=True)
            store.save(rname, "triage_es", doc)
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIn("réplica", rep["reason"])


class TestRefusals(TmpStore):
    def test_formats_documentados(self):
        fm = jev90.analysis_formats()
        self.assertIn("question_refusal", fm)
        self.assertIn("NO EVALUABLE", fm["question_refusal"]["jev81_repeat"])

    def test_refusal_detectado_y_veredicto(self):
        _write_all("d0")
        _write_all("d1", refuse_ids={"T12_autorizacion_seguro"})
        self.assertTrue(jev90.has_question_refusals("d1"))
        # jev81 aborta ante refusal
        with self.assertRaises(SystemExit):
            jev81._check_paired_vectors("d0", "d1", printer=lambda *a: None)
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")


class TestCostsAndPreflight(TmpStore):
    def test_costs_separa_suma_y_ledger(self):
        # ledger > suma vigente (retries reemplazados en el durable)
        _write_all("d0", cost=0.0001, ledger=0.05)
        doc = store.load("d0", "ood")
        doc["cases"]["codigo"].pop("cost", None)
        store.save("d0", "ood", doc)
        c = jev90.costs_report("d0")
        self.assertAlmostEqual(c["ledger_max"], 0.05)
        self.assertIn("ood/codigo", c["unknown"])
        self.assertLess(c["recorded_sum"], c["ledger_max"])
        self.assertNotEqual(c["recorded_sum"], c["ledger_max"])

    def test_preflight_lista_expuestos(self):
        _write_all("d0")
        _write_all(jev90.REF)
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = jev90.preflight("d0", ref=jev90.REF,
                                  printer=lambda *a: print(*a, file=buf))
        self.assertEqual(out["exposed_bank"], jev90.exposed_tags())
        self.assertEqual(out["n_phases"], 11)
        self.assertIn("Roast the chicken",
                      out["exposed_synthetic"][0]["state_prefix"])

    def test_cli_holm53_imprime_53(self):
        _write_all(jev90.D0)
        _write_all(jev90.REF)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["holm53", jev90.D0, jev90.REF])
        self.assertEqual(rc, 0)
        # 53 líneas de celda + cabecera
        lines = [ln for ln in buf.getvalue().splitlines()
                 if ln.strip().startswith("triage_") or
                 ln.strip().startswith("papers") or
                 ln.strip().startswith("adv") or
                 ln.strip().startswith("ood")]
        self.assertEqual(len(lines), 53)

    def test_defaults_jev81_intactos(self):
        # smoke: repeatability_report sigue sin exigir EXPECTED_SNAPSHOT
        _write_all(jev81.LUNA, model="otra-version-A")
        _write_all(jev81.R2_RUN, model="otra-version-A")
        rep = jev81.repeatability_report(jev81.LUNA, jev81.R2_RUN)
        self.assertTrue(rep["versions"]["repeatable_model"])


class TestConstants(unittest.TestCase):
    def test_presupuesto_global_y_fases(self):
        self.assertEqual(jev90.GLOBAL_EXPERIMENT_BUDGET, 0.15)
        self.assertEqual(len(jev90.PHASES_11), 11)
        self.assertIn("adv5", jev90.PHASES_11_CSV)
        self.assertAlmostEqual(1004 / 2704, 0.37130, places=5)


# --- R96 / T31c: escenarios adversos de Codex (deben fallar antes del fix) ---

class TestPrimacyConfirmExcludesExposed(TmpStore):
    """P1: la familia Holm {todos, primacía} no puede incluir IDs expuestos."""

    def test_todos_sin_expuestos_aunque_fallen(self):
        _write_all("d0")
        _write_all("d1")
        # errores solo en los dos IDs expuestos de triage_es → no deben
        # entrar en el contraste «todos» de la familia confirmatoria
        qs, cases = load_phase("triage_es")
        for cid in ("T01_ebus_alergia", "T02_factura_duplicada"):
            case = next(c for c in cases if c.id == cid)
            doc = store.load("d1", "triage_es")
            doc["cases"][cid]["answers"] = _answers(qs, case.gt, bad=True)
            store.save("d1", "triage_es", doc)
        # descriptivo jev82/qwen_session SÍ los ve (reproducción Codex)
        from jevbench import qwen_session as qs_
        desc = qs_.primacy_analysis({"d0": "d0", "d1": "d1"}, iters=10)
        labels = [lab for lab, _, _ in desc["holm"]]
        self.assertIn("d0vsd1 todos", labels)
        # confirmatorio jev90: «todos» no debe contar esos discordantes
        conf = jev90.primacy_analysis_confirm("d0", "d1", iters=10)
        self.assertEqual(conf["subset_sha"], "4e7e2877f27d")
        todos = next(x for x in conf["holm"] if x[0] == "d0vsd1 todos")
        # con solo errores en expuestos, b=c=0 → p=1 (sin observaciones
        # discordantes de no-expuestos); n_todos no incluye expuestos
        self.assertNotIn("triage_es/T01_ebus_alergia",
                         conf.get("todos_ids", []))
        self.assertTrue(conf["exclude_exposed"])
        # p de «todos» no se alimenta de los dos expuestos
        self.assertEqual(todos[1], 1.0)  # p nominal sin discordantes


class TestReplicaGateNoRefutada(TmpStore):
    """P2: réplica ausente / drift / negativas parciales → NO EVALUABLE."""

    def _one_change_d1_rotated(self):
        _one_change_d1()
        _stamp_provenance("d1", "d1")

    def test_r_valida_identica_refutada(self):
        self._one_change_d1_rotated()
        _write_all("r2")  # idéntica a d0
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "REFUTADA")

    def test_r_inexistente_no_evaluable(self):
        self._one_change_d1_rotated()
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2_missing")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIsNone(rep.get("replica_department_changes"))

    def test_r_otro_snapshot_no_evaluable(self):
        self._one_change_d1_rotated()
        _write_all("r2", model="microsoft/microsoft-decision-1-20990101")
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIsNone(rep.get("replica_department_changes"))

    def test_r_refusal_department_en_caso_cambiado_no_evaluable(self):
        self._one_change_d1_rotated()
        _write_all("r2", refuse_ids={"T12_autorizacion_seguro"})
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        reason = (rep.get("reason") or "").lower()
        self.assertTrue(
            "réplica" in reason or "negativ" in reason
            or "refusal" in reason or "snapshot" in reason
            or "parcial" in reason)

    def test_r_valida_que_cambia_t12_no_evaluable(self):
        self._one_change_d1_rotated()
        _write_all("r2")
        qs, cases = load_phase("triage_es")
        case = next(c for c in cases if c.id == "T12_autorizacion_seguro")
        doc = store.load("r2", "triage_es")
        doc["cases"][case.id]["answers"] = _answers(qs, case.gt, bad=True)
        store.save("r2", "triage_es", doc)
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIn("réplica", rep["reason"])


class TestHolm53Gates(TmpStore):
    """P2: Holm53 confirmatorio exige preflight + snapshot; aborta si falla."""

    def test_holm53_hash_errado_no_confirmatorio(self):
        _write_all("a")
        _write_all("b")
        doc = store.load("a", "triage_es")
        doc["meta"]["questions_hash"] = "wrong"
        store.save("a", "triage_es", doc)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["holm53", "a", "b"])
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Holm53 confirmatorio n=53", buf.getvalue())

    def test_holm53_snapshot_errado_no_evaluable(self):
        _write_all("d0", model="wrong-snapshot")
        _write_all(jev90.REF)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["holm53", "d0", jev90.REF])
        self.assertNotEqual(rc, 0)
        out = buf.getvalue()
        self.assertTrue("NO EVALUABLE" in out or "snapshot" in out.lower())

    def test_preflight_drift_exit_no_cero(self):
        _write_all("d0", model="wrong-snapshot")
        _write_all(jev90.REF)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["preflight", "d0", "--ref", jev90.REF])
        self.assertNotEqual(rc, 0)

    def test_preflight_ref_ausente_falla(self):
        _write_all("d0")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["preflight", "d0", "--ref", "ref_missing"])
        self.assertNotEqual(rc, 0)

    def test_holm53_runs_inexistentes_no_familia_falsa(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["holm53", "missing-a", "missing-b"])
        self.assertNotEqual(rc, 0)
        # no debe imprimir 53 filas confirmatorias
        lines = [ln for ln in buf.getvalue().splitlines()
                 if ln.strip().startswith("triage_") or
                 ln.strip().startswith("papers") or
                 ln.strip().startswith("adv") or
                 ln.strip().startswith("ood")]
        self.assertEqual(len(lines), 0)


class TestGlobalBudgetLedger(TmpStore):
    """P2 (T31e): cupo global ≤ $0,15 por construcción (3×$0,05)."""

    def test_tope_por_construccion_tres_por_run_cap(self):
        self.assertAlmostEqual(
            3 * jev90.RUN_COST_CAP, jev90.GLOBAL_EXPERIMENT_BUDGET)
        self.assertAlmostEqual(jev90.CASE_COST_CAP, 0.01)
        self.assertAlmostEqual(jev90.RUN_COST_CAP, 0.05)

    def test_procedimiento_no_usa_cupo_dinamico(self):
        """El borrador publicado no invoca effective_max_cost / budget --before."""
        text = Path("docs/infra_runs/ms_decision1_jev90.md").read_text(
            encoding="utf-8")
        # Solo el registro histórico T31c/d puede citarlos; el cuerpo del
        # procedimiento (§1–§5) no debe exigirlos.
        body = text.split("## Registro de cambios")[0]
        self.assertNotIn("effective_max_cost", body)
        self.assertNotIn("budget --before", body)
        self.assertIn("por construcción", body.lower())
        self.assertIn("--max-cost 0.05", body)
        self.assertIn("sin reanudación", body.lower())
        # Helper legado existe pero declara que el procedimiento no lo usa.
        ok, st = jev90.check_global_budget_before(jev90.D0)
        self.assertIn("NO usa", (st.get("procedure_note") or ""))
        self.assertTrue(ok)  # sin gasto: el helper sigue respondiendo


class TestUnknownCostsPreserveReplaced(TmpStore):
    """P3: inventario distingue capturados vs reemplazos comprobados."""

    def test_reemplazo_comprobado_sigue_en_inventario(self):
        _write_all("d0", cost=0.0001, ledger=0.05)
        # intento con error sin coste, luego sustituido (vigente con coste)
        doc = store.load("d0", "ood")
        old = {"error": "boom", "usage": {"input_tokens": 1}}  # sin cost
        self.assertTrue(jev90.note_unknown_replacement(
            doc["meta"], "ood", "codigo", old))
        store.save("d0", "ood", doc)
        c = jev90.costs_report("d0")
        self.assertIn("ood/codigo", c["unknown_replaced"])
        self.assertNotIn("ood/codigo", c.get("unknown_captured", []))
        self.assertNotIn("ood/codigo", c.get("unknown_current", c["unknown"]))
        note = c["note"].lower()
        self.assertTrue("vigente" in note or "reemplaz" in note)
        self.assertIn("capture-unknowns", note)
        self.assertIn("acreditado", note)


# --- R98 / T31d: escenarios adversos de Codex (deben fallar antes del fix) ---

class TestManufacturerRequiresD1Rotation(TmpStore):
    """P2: el contador acredita que D1 es rotación (perm/choice_order)."""

    def test_d1_canonico_no_evaluable(self):
        # Reproducción Codex: tres runs canónicos; cambio en T12 → antes
        # REFUTADA; ahora NO EVALUABLE (D1 no declara rotación).
        _one_change_d1()
        _write_all("r2")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(
                ["department-discords", "d0", "d1", "--r2", "r2"])
        self.assertNotEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("NO EVALUABLE", out)
        self.assertNotIn("REFUTADA", out)
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertTrue(rep.get("department_descriptive"))

    def test_d1_orden_incorrecto_no_evaluable(self):
        _one_change_d1()
        _stamp_provenance("d1", "d0")  # declara d0 en el run d1
        _write_all("r2")
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        reason = (rep.get("reason") or "").lower()
        self.assertTrue("procedencia" in reason or "orden" in reason
                        or "rotación" in reason or "choice_order" in reason
                        or "incompatible" in reason)

    def test_d1_perm_ausente_no_evaluable(self):
        _one_change_d1()
        _stamp_provenance("d1", "d1")
        doc = store.load("d1", "triage_es")
        del doc["meta"]["perm_sha256"]
        store.save("d1", "triage_es", doc)
        _write_all("r2")
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")

    def test_d1_perm_incorrecto_no_evaluable(self):
        _one_change_d1()
        _stamp_provenance("d1", "d1")
        doc = store.load("d1", "adv3")
        doc["meta"]["perm_sha256"] = "000000000000"
        store.save("d1", "adv3", doc)
        _write_all("r2")
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")


class TestPairedVectorsRequired(TmpStore):
    """P2: contrastes validan vectores completos (no solo IDs/hashes)."""

    def test_r_sin_probabilities_no_evaluable(self):
        _one_change_d1()
        _stamp_provenance("d1", "d1")
        _write_all("r2")
        doc = store.load("r2", "triage_es")
        ans = doc["cases"]["T12_autorizacion_seguro"]["answers"]["department"]
        ans.pop("probabilities", None)
        store.save("r2", "triage_es", doc)
        with self.assertRaises(SystemExit):
            jev81._check_paired_vectors(
                "d0", "r2", printer=lambda *a: None)
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIn("vector", (rep.get("reason") or "").lower())

    def test_primacy_pregunta_ausente_en_d1_no_evaluable(self):
        _write_all("d0")
        _write_all("d1")
        _stamp_provenance("d1", "d1")
        doc = store.load("d1", "triage_es")
        doc["cases"]["T12_autorizacion_seguro"]["answers"].pop(
            "department", None)
        store.save("d1", "triage_es", doc)
        with self.assertRaises(SystemExit):
            jev81._check_paired_vectors(
                "d0", "d1", printer=lambda *a: None)
        # El hash del subconjunto sigue intacto, pero sin contrato →
        # NO EVALUABLE (no REFUTADA con n_paired=36).
        rep = jev90.primacy_confirm_verdict("d0", "d1", iters=10)
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertIsNone(rep.get("primacy"))


class TestNoCausalWithoutReplica(TmpStore):
    """P2: sin réplica válida no se imprime veredicto causal."""

    def test_sin_r2_no_evaluable_no_refutada(self):
        _one_change_d1()
        _stamp_provenance("d1", "d1")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jev90.main(["department-discords", "d0", "d1"])
        self.assertNotEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("NO EVALUABLE", out)
        self.assertNotIn(": REFUTADA", out)
        self.assertNotIn("REFUTADA\n", out)
        rep = jev90.manufacturer_zero_change_verdict("d0", "d1")
        self.assertEqual(rep["verdict"], "NO EVALUABLE")
        self.assertTrue(rep.get("department_descriptive"))
        self.assertGreaterEqual(rep["department"]["n_changes"], 1)


class TestGlobalBudgetFixedGuards(TmpStore):
    """P2 (T31e): guarda fija 0,05 coincide con jev82 y acota el agregado."""

    def test_guarda_declarada_permite_analisis_rotacion(self):
        """Con --max-cost 0.05 (publicado), primacía/contador no son NO EVALUABLE
        por guarda; con 0,04 sí lo serían (incompatibilidad R99 eliminada)."""
        _one_change_d1()
        _stamp_provenance("d1", "d1")
        _write_all("r2")
        # guarda congelada 0,05 (como los comandos publicados)
        for ph in score.ADJ_PHASES:
            doc = store.load("d1", ph)
            if doc is None:
                continue
            doc["meta"]["cost_guard"] = {
                "max_case_cost": 0.01, "max_cost": 0.05}
            store.save("d1", ph, doc)
        rep = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep["verdict"], "REFUTADA")
        # la misma rotación con tope 0,04 (cupo dinámico R98) → NO EVALUABLE
        for ph in score.ADJ_PHASES:
            doc = store.load("d1", ph)
            if doc is None:
                continue
            doc["meta"]["cost_guard"] = {
                "max_case_cost": 0.01, "max_cost": 0.04}
            store.save("d1", ph, doc)
        rep2 = jev90.manufacturer_zero_change_verdict(
            "d0", "d1", run_r2="r2")
        self.assertEqual(rep2["verdict"], "NO EVALUABLE")

    def test_runner_guarda_fija_no_excede_run_cap_mas_margen(self):
        """Un run con --max-cost 0.05 y $0,01/caso para en el tope (+≤1 caso)."""
        qs, cases = load_phase("triage_es")
        meta = {"adapter": "fake", "phase": "triage_es",
                "questions_hash": questions_hash(qs),
                "opts": {}, "cost_ledger": 0.0,
                "cost_guard": {"max_case_cost": 0.01, "max_cost": 0.05}}
        store.save("cell", "triage_es", {"meta": meta, "cases": {}})

        class Fake(Adapter):
            def __init__(self, **opts):
                super().__init__(**opts)
                self.calls = 0

            def meta(self):
                return {"model": "fake"}

            def decide(self, state, questions):
                self.calls += 1
                answers = {}
                for qid, q in questions.items():
                    if q["type"] == "choice":
                        lab = next(iter(q["criteria"]))
                        answers[qid] = {"type": "choice", "choice": lab,
                                        "probabilities": {lab: 1.0}}
                    elif q["type"] == "score":
                        answers[qid] = {"type": "score", "score": 0.0,
                                        "probabilities": {"0": 1.0}}
                    else:
                        answers[qid] = {"type": "noul", "noul": 0.0}
                return {"answers": answers, "cost": 0.01, "model": "fake-1"}

        a = Fake()
        argv = ["run.py", "fake", "--run", "cell", "--phases", "triage_es",
                "--max-case-cost", "0.01", "--max-cost", "0.05"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(run.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(run.adapters, "get",
                               return_value=lambda **o: a):
            run.main()
        from jevbench import cost_guard as cg
        phase_docs = cg.load_phase_docs(store, "cell")
        spent = cg.prior_cost(phase_docs)
        self.assertLessEqual(spent, 0.05 + 0.01)
        doc = store.load("cell", "triage_es")
        self.assertEqual(doc["meta"]["cost_guard"]["max_cost"], 0.05)


class TestCaptureUnknownsBeforeRetry(TmpStore):
    """P3: captura pre-retry; reemplazo solo si se comprueba."""

    def _fake_cls(self):
        class Fake(Adapter):
            def __init__(self, cost=None, fail=False, **opts):
                super().__init__(**opts)
                self.cost = cost
                self.fail = fail
                self.calls = 0

            def meta(self):
                return {"model": "fake"}

            def decide(self, state, questions):
                self.calls += 1
                if self.fail:
                    raise RuntimeError("boom sin coste")
                answers = {}
                for qid, q in questions.items():
                    if q["type"] == "choice":
                        lab = next(iter(q["criteria"]))
                        answers[qid] = {"type": "choice", "choice": lab,
                                        "probabilities": {lab: 1.0}}
                    elif q["type"] == "score":
                        answers[qid] = {"type": "score", "score": 0.0,
                                        "probabilities": {"0": 1.0}}
                    else:
                        answers[qid] = {"type": "noul", "noul": 0.0}
                out = {"answers": answers, "model": "fake-1"}
                if self.cost is not None:
                    out["cost"] = self.cost
                return out
        return Fake

    def _invoke(self, Fake, *extra, cost=None, fail=False, run_name="r1"):
        a = Fake(cost=cost, fail=fail)
        argv = ["run.py", "fake", "--run", run_name, "--phases", "triage_es",
                "--limit", "1", *extra]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(run.adapters.REGISTRY, {"fake": "x:y"}), \
             mock.patch.object(run.adapters, "get",
                               return_value=lambda **o: a):
            run.main()
        return a

    def test_flujo_publicado_conserva_reemplazados(self):
        Fake = self._fake_cls()
        self._invoke(Fake, "--max-case-cost", "0.01", "--max-cost", "0.05",
                     fail=True)
        c0 = jev90.costs_report("r1")
        self.assertTrue(c0["unknown_current"])
        tag = c0["unknown_current"][0]
        out = jev90.capture_unknowns("r1")
        self.assertGreaterEqual(out["captured"], 1)
        self.assertIn(tag, out["tags"])
        # tras captura, aún no acreditado
        c_mid = jev90.costs_report("r1")
        self.assertIn(tag, c_mid["unknown_captured"])
        self.assertNotIn(tag, c_mid["unknown_replaced"])
        self._invoke(Fake, "--max-case-cost", "0.01", "--max-cost", "0.05",
                     "--retry-errors", cost=0.0001, fail=False)
        c1 = jev90.costs_report("r1")
        self.assertEqual(c1["unknown_current"], [])
        self.assertIn(tag, c1["unknown_replaced"])
        self.assertNotIn(tag, c1["unknown_captured"])

    def test_exito_sin_coste_no_es_reemplazado(self):
        """Éxito sin coste capturado: unknown_captured, no unknown_replaced."""
        _write_all("d0", cost=None)
        # _write_all con cost=None deja answers sin cost
        out = jev90.capture_unknowns("d0")
        self.assertGreater(out["captured"], 0)
        c = jev90.costs_report("d0")
        self.assertTrue(c["unknown_current"])
        self.assertTrue(c["unknown_captured"])
        self.assertEqual(c["unknown_replaced"], [])
        self.assertEqual(set(c["unknown_captured"]),
                         set(c["unknown_current"]))

    def test_retry_bloqueado_no_acredita_reemplazo(self):
        """Error capturado sin retry: sigue en captured, no en replaced."""
        Fake = self._fake_cls()
        self._invoke(Fake, "--max-case-cost", "0.01", "--max-cost", "0.05",
                     fail=True)
        tag = jev90.costs_report("r1")["unknown_current"][0]
        jev90.capture_unknowns("r1")
        # no se ejecuta --retry-errors (retry «bloqueado»)
        c = jev90.costs_report("r1")
        self.assertIn(tag, c["unknown_current"])
        self.assertIn(tag, c["unknown_captured"])
        self.assertNotIn(tag, c["unknown_replaced"])


if __name__ == "__main__":
    unittest.main()
