"""Tests offline del `choice_order` genérico (JEV-103): la opción vive en la
clase base Adapter y llega a cualquier adaptador por **opts (CLI --opt).
Sin la opción, `decide` recibe `questions` intacto y `meta()` no lleva campos
de orden (byte a byte como antes). Con ella: reordena solo las claves de
`criteria` de las preguntas choice nombradas y meta registra `choice_order`
resuelto + `perm_sha256` del orden realmente aplicado — igual que el adaptador
`jev` (JEV-82). Incluye un extremo a extremo con `systemone_http` (HTTP local)
y la comprobación de que `jevbench.jev82` acepta runs de otros adaptadores."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from jevbench import jev82, run, score, store
from jevbench.adapters import Adapter
from jevbench.adapters.systemone_http import SystemOneHTTP
from jevbench.battery import TRIAGE_QS, load_phase, questions_hash
from jevbench.rotation import (NAMED_ORDERS, order_manifest, reorder_choice,
                               resolve_choice_order)


class TestBaseAdapter(unittest.TestCase):
    def test_opcion_llega_por_opts(self):
        """Una opción que el adaptador no declara en su firma llega a la base
        por **opts (el camino del CLI --opt choice_order=...)."""
        a = Adapter(**{"choice_order": "department:d1"})
        self.assertEqual(a.choice_order,
                         {"department": NAMED_ORDERS["department"]["d1"]})

    def test_sin_opcion_no_toca_nada(self):
        """Sin la opción: questions intacto (mismo objeto) y meta sin campos
        de orden — el comportamiento por defecto es idéntico."""
        a = Adapter()
        self.assertIsNone(a.choice_order)
        self.assertIsNone(a._perm_sha256)
        self.assertIs(a._apply_choice_order(TRIAGE_QS), TRIAGE_QS)
        self.assertEqual(a._order_meta(), {})

    def test_d0_no_cambia_el_wire(self):
        """d0 = orden canónico: el questions resultante serializa idéntico."""
        a = Adapter(choice_order="department:d0")
        out = a._apply_choice_order(TRIAGE_QS)
        self.assertEqual(json.dumps(out, ensure_ascii=False),
                         json.dumps(TRIAGE_QS, ensure_ascii=False))
        # canónico congelado de JEV-82 §1 (triaje/adv)
        self.assertEqual(a._order_meta()["perm_sha256"], "c656cec9e1d1")

    def test_d1_rota_solo_la_pregunta_nombrada(self):
        a = Adapter(choice_order="department:d1")
        out = a._apply_choice_order(TRIAGE_QS)
        self.assertEqual(list(out["department"]["criteria"]),
                         NAMED_ORDERS["department"]["d1"])
        self.assertEqual(out["department"]["criteria"],
                         {k: TRIAGE_QS["department"]["criteria"][k]
                          for k in NAMED_ORDERS["department"]["d1"]})
        for qid, q in TRIAGE_QS.items():
            if qid != "department":
                self.assertIs(out[qid], q)
        m = a._order_meta()
        self.assertEqual(m["choice_order"],
                         {"department": NAMED_ORDERS["department"]["d1"]})
        # congelado de JEV-82 §1: rotación d1 aplicada a las preguntas vigentes
        self.assertEqual(m["perm_sha256"], "15f6174736a0")

    def test_perm_sha256_es_el_del_orden_aplicado(self):
        """El hash registrado coincide con order_manifest sobre las preguntas
        ya reordenadas (mismo cálculo que hace jev82._expected_perm)."""
        a = Adapter(choice_order="department:d1")
        a._apply_choice_order(TRIAGE_QS)
        orders = resolve_choice_order("department:d1")
        self.assertEqual(
            a._perm_sha256,
            order_manifest(reorder_choice(TRIAGE_QS, orders),
                           orders)["perm_sha256"])

    def test_fase_sin_la_pregunta_es_noop(self):
        """En fases sin `department` (papers32, ood) el reorden no cambia nada
        y el manifiesto registra el orden canónico de esa fase."""
        a = Adapter(choice_order="department:d1")
        for ph, perm in (("papers32", "c68c21f92897"), ("ood", "e54d4e3d2038")):
            with self.subTest(phase=ph):
                qs, _ = load_phase(ph)
                out = a._apply_choice_order(qs)
                self.assertEqual(json.dumps(out, ensure_ascii=False),
                                 json.dumps(qs, ensure_ascii=False))
                self.assertEqual(a._perm_sha256, perm)

    def test_especificaciones_invalidas_rechazadas(self):
        """Misma convención que el adaptador jev: forma inválida o nombre de
        orden inexistente fallan en el constructor; una lista que no es
        permutación de las etiquetas falla al aplicar (primer decide)."""
        for bad in ("d1", "department:", "department:d9", "urgency:d1"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Adapter(choice_order=bad)

    def test_no_permutacion_falla_al_aplicar(self):
        a = Adapter(choice_order="department:admin,admin,admin,admin")
        with self.assertRaises(ValueError):
            a._apply_choice_order(TRIAGE_QS)

    def test_pregunta_no_choice_rechazada(self):
        """choice_order solo aplica a preguntas choice."""
        a = Adapter(choice_order="urgency:0,1,2")
        with self.assertRaises(ValueError):
            a._apply_choice_order(TRIAGE_QS)


class _Handler(BaseHTTPRequestHandler):
    """Servidor SystemOne mínimo: graba el cuerpo y responde argmax."""
    bodies = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.bodies.append(body)
        answers = {}
        for qid, q in body["questions"].items():
            if q["type"] == "choice":
                labels = list(q["criteria"])
                answers[qid] = {"type": "choice", "choice": labels[0],
                                "probabilities": {k: (1.0 if k == labels[0] else 0.0)
                                                  for k in labels}}
            elif q["type"] == "score":
                answers[qid] = {"type": "score", "score": 0.0,
                                "probabilities": {str(i): 1.0 / len(q["criteria"])
                                                  for i in range(len(q["criteria"]))}}
            else:
                answers[qid] = {"type": "noul", "noul": 0.25}
        data = json.dumps({"model": "fake-systemone", "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestSystemOneHTTP(unittest.TestCase):
    """Extremo a extremo del adaptador `systemone_http` (HTTP local) — el caso
    de uso de JEV-103 para drex/clm/strands: el orden viaja en el cuerpo y la
    procedencia queda en meta del run."""

    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.run_name = "test_choice_order_tmp"
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)
        _Handler.bodies = []

    def tearDown(self):
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)

    def _main(self, *opts, phase="triage_es"):
        argv = ["jevbench.run", "systemone_http", "--run", self.run_name,
                "--phases", phase, "--limit", "1", "--opt", f"url={self.url}",
                *sum((["--opt", o] for o in opts), [])]
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            old, sys.argv = sys.argv, argv
            try:
                run.main()
            finally:
                sys.argv = old
        return json.loads((store.ROOT / self.run_name / f"{phase}.json")
                          .read_text())

    def test_d1_reordena_el_cuerpo_y_registra_meta(self):
        doc = self._main("model=fake", "choice_order=department:d1")
        sent = _Handler.bodies[0]["questions"]
        self.assertEqual(list(sent["department"]["criteria"]),
                         NAMED_ORDERS["department"]["d1"])
        meta = doc["meta"]
        self.assertEqual(meta["opts"]["choice_order"], "department:d1")
        self.assertEqual(meta["choice_order"],
                         {"department": NAMED_ORDERS["department"]["d1"]})
        self.assertEqual(meta["perm_sha256"], "15f6174736a0")

    def test_sin_opcion_meta_y_cuerpo_intactos(self):
        doc = self._main("model=fake")
        sent = _Handler.bodies[0]["questions"]
        self.assertEqual(list(sent["department"]["criteria"]),
                         NAMED_ORDERS["department"]["d0"])
        self.assertNotIn("choice_order", doc["meta"])
        self.assertNotIn("perm_sha256", doc["meta"])

    def test_d0_cuerpo_byte_a_byte(self):
        self._main("model=fake")
        self._main("model=fake", "choice_order=department:d0",
                   phase="triage_es")
        b0, b1 = _Handler.bodies
        self.assertEqual(json.dumps(b0["questions"], ensure_ascii=False),
                         json.dumps(b1["questions"], ensure_ascii=False))

    def test_choice_order_y_rotate_choice_excluyentes(self):
        with self.assertRaises(ValueError):
            SystemOneHTTP(rotate_choice=1, choice_order="department:d1")


class TestJev82OtroAdaptador(unittest.TestCase):
    """`jevbench.jev82 analyze` acepta runs de cualquier adaptador: la
    procedencia del orden solo lee meta.opts.choice_order / meta.choice_order
    / meta.perm_sha256 / meta.cost_guard — ninguna comprobación ata al
    adaptador `jev`. Runs sintéticos con adapter="systemone_http"."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="j103_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def _write_run(self, run, phase, spec="d0"):
        qs, cases = load_phase(phase)
        orders = resolve_choice_order(f"department:{spec}")
        perm = order_manifest(reorder_choice(qs, orders),
                              orders)["perm_sha256"]
        meta = {"adapter": "systemone_http", "phase": phase,
                "questions_hash": questions_hash(qs),
                "opts": {"url": "http://127.0.0.1:9", "model": "m",
                         "choice_order": f"department:{spec}"},
                "choice_order": orders, "perm_sha256": perm}
        if spec != "d0":
            meta["cost_guard"] = dict(jev82.COST_GUARD_SPEC)
        doc = {"meta": meta, "cases": {}}
        for c in cases:
            answers = {}
            for qid, q in qs.items():
                v = c.gt.get(qid)
                if q["type"] == "choice":
                    labels = list(q["criteria"])
                    answers[qid] = {"type": "choice", "choice": v,
                                    "probabilities": {o: (0.9 if o == v else 0.0)
                                                      for o in labels}}
                elif q["type"] == "score":
                    answers[qid] = {"type": "score", "score": float(v or 0),
                                    "probabilities": {str(i): 0.5 for i in
                                                      range(len(q["criteria"]))}}
                else:
                    answers[qid] = {"type": "noul", "noul": float(bool(v))}
            doc["cases"][c.id] = {"answers": answers, "ms": 1,
                                  "cost": None, "model": "m-1"}
        store.save(run, phase, doc)

    def test_analyze_acepta_otro_adaptador(self):
        for ph in score.ADJ_PHASES:
            self._write_run("otro_d0", ph, spec="d0")
            self._write_run("otro_d1", ph, spec="d1")
        rep = jev82.rotation_report("otro_d0", "otro_d1",
                                    printer=lambda *a: None)
        self.assertEqual(rep["run_d0"], "otro_d0")
        self.assertTrue(rep["versions"]["same_model"])
        self.assertEqual(rep["agreement"]["n"], rep["agreement"]["k"])


if __name__ == "__main__":
    unittest.main()
