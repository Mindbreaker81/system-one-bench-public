"""Tests offline del adaptador `jev` (JEV-82: opción choice_order) — un HTTP
local graba el cuerpo enviado y responde una respuesta fija. Sin red externa
ni claves reales (OPENROUTER_API_KEY se fija a un valor de prueba)."""
import http.server
import json
import os
import threading
import unittest

from jevbench.battery import TRIAGE_QS
from jevbench.rotation import (NAMED_ORDERS, order_manifest, reorder_choice,
                               resolve_choice_order)

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

CANNED = {"answers": {"department": {"type": "choice", "choice": "admin",
                                     "probabilities": {"admin": 0.9}},
                      "urgency": {"type": "score", "score": 0.5,
                                  "probabilities": {"0": 0.3, "1": 0.5,
                                                    "2": 0.2}},
                      "clinical": {"type": "noul", "noul": 0.1},
                      "hostile": {"type": "noul", "noul": 0.0},
                      "same_day": {"type": "noul", "noul": 0.0}},
          "model": "fake-decisions-20990101",
          "usage": {"input_tokens": 100, "output_tokens": 0, "cost": 0.0001}}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.bodies.append(body)
        payload = json.dumps(CANNED).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class FakeDecisionsServer:
    def __enter__(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.bodies = []
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/api/alpha/decisions"
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def _adapter(srv, **opts):
    from jevbench.adapters.jev import Jev
    a = Jev(provider="openrouter", model="fake-decisions", pause=0,
            retries=1, **opts)
    a.url = srv.url
    return a


class TestChoiceOrder(unittest.TestCase):
    def test_d0_cuerpo_byte_a_byte(self):
        """Sin opción y con department:d0 el cuerpo de la petición es
        exactamente el mismo (d0 = comportamiento histórico)."""
        with FakeDecisionsServer() as srv:
            _adapter(srv).decide("Factura duplicada.", TRIAGE_QS)
            _adapter(srv, choice_order="department:d0").decide(
                "Factura duplicada.", TRIAGE_QS)
        self.assertEqual(len(srv.httpd.bodies), 2)
        self.assertEqual(srv.httpd.bodies[0], srv.httpd.bodies[1])
        sent = json.loads(srv.httpd.bodies[0])
        self.assertEqual(list(sent["questions"]["department"]["criteria"]),
                         NAMED_ORDERS["department"]["d0"])

    def test_d1_rota_solo_department(self):
        """Con department:d1 el orden de criteria del wire es el d1 congelado;
        textos, etiquetas y el resto de preguntas quedan intactos."""
        with FakeDecisionsServer() as srv:
            _adapter(srv, choice_order="department:d1").decide(
                "Factura duplicada.", TRIAGE_QS)
        sent = json.loads(srv.httpd.bodies[0])["questions"]
        dept = sent["department"]
        self.assertEqual(list(dept["criteria"]),
                         NAMED_ORDERS["department"]["d1"])
        self.assertEqual(dept["criteria"],
                         {k: TRIAGE_QS["department"]["criteria"][k]
                          for k in NAMED_ORDERS["department"]["d1"]})
        for qid, q in TRIAGE_QS.items():
            if qid != "department":
                self.assertEqual(sent[qid], q)
        self.assertEqual(dept["type"], TRIAGE_QS["department"]["type"])
        self.assertEqual(dept["instructions"],
                         TRIAGE_QS["department"]["instructions"])

    def test_perm_sha256_registrado_en_meta(self):
        """Tras decide, meta() lleva choice_order resuelto y el perm_sha256
        del orden realmente aplicado (mismo valor que en los runs JEV-76)."""
        with FakeDecisionsServer() as srv:
            a = _adapter(srv, choice_order="department:d1")
            a.decide("Factura duplicada.", TRIAGE_QS)
        meta = a.meta()
        d1 = resolve_choice_order("department:d1")
        expected = order_manifest(reorder_choice(TRIAGE_QS, d1), d1)
        self.assertEqual(meta["perm_sha256"], expected["perm_sha256"])
        self.assertEqual(meta["perm_sha256"], "15f6174736a0")
        self.assertEqual(meta["choice_order"], d1)

    def test_sin_opcion_meta_sin_orden(self):
        """Sin choice_order: meta declara ausencia y nada cambia."""
        with FakeDecisionsServer() as srv:
            a = _adapter(srv)
            a.decide("Factura duplicada.", TRIAGE_QS)
        self.assertIsNone(a.meta()["choice_order"])
        self.assertIsNone(a.meta()["perm_sha256"])

    def test_orden_explicito_por_etiquetas(self):
        """También acepta una lista explícita de etiquetas."""
        order = "admin,urgencias,consulta_externa,bronchoscopia"
        with FakeDecisionsServer() as srv:
            _adapter(srv, choice_order="department:" + order).decide(
                "Factura duplicada.", TRIAGE_QS)
        sent = json.loads(srv.httpd.bodies[0])["questions"]
        self.assertEqual(list(sent["department"]["criteria"]),
                         order.split(","))

    def test_especificacion_invalida_rechazada(self):
        """Órdenes mal formados fallan en el constructor; una lista que no es
        permutación de las etiquetas falla en el primer decide (misma
        convención que el adaptador llm)."""
        with FakeDecisionsServer() as srv:
            for bad in ("d1", "department:", "department:d9", "urgency:d1"):
                with self.subTest(bad=bad):
                    with self.assertRaises((ValueError, SystemExit)):
                        _adapter(srv, choice_order=bad)
            a = _adapter(srv, choice_order="department:admin,admin,admin,admin")
            with self.assertRaises(ValueError):
                a.decide("Factura duplicada.", TRIAGE_QS)
            self.assertEqual(srv.httpd.bodies, [])  # nada salió por el cable

    def test_respuesta_y_coste_intactos(self):
        """La respuesta, el modelo resuelto y el coste no dependen del orden."""
        with FakeDecisionsServer() as srv:
            out = _adapter(srv, choice_order="department:d1").decide(
                "Factura duplicada.", TRIAGE_QS)
        self.assertEqual(out["answers"]["department"]["choice"], "admin")
        self.assertEqual(out["model"], "fake-decisions-20990101")
        self.assertEqual(out["cost"], 0.0001)


if __name__ == "__main__":
    unittest.main()
