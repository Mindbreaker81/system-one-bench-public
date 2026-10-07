"""JEV-70: systemone_http extras (extra, timeout, capture_raw, diag on HTTP errors,
rotate_choice), checked end to end HTTP → adapter → JSON in results/."""
import contextlib
import io
import json
import shutil
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jevbench import run, store
from jevbench.adapters.systemone_http import SystemOneHTTP
from jevbench.battery import load_phase


class Handler(BaseHTTPRequestHandler):
    status = 200
    bodies = []
    payload = None  # cuerpo de error opcional (bytes), p. ej. UTF-8 multibyte

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.bodies.append(body)
        if Handler.status != 200:
            msg = Handler.payload if Handler.payload is not None else \
                json.dumps({"detail": "schema rejected: " + "x" * 5000}).encode()
            self.send_response(Handler.status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(msg)
            return
        answers = {}
        for qid, q in body["questions"].items():
            if q["type"] == "choice":
                first = next(iter(q["criteria"]))
                answers[qid] = {"choice": first, "probabilities": {k: (1.0 if k == first else 0.0)
                                                                   for k in q["criteria"]}}
            elif q["type"] == "score":
                answers[qid] = {"score": 0.0, "legend": q["criteria"]}
            else:
                answers[qid] = {"noul": 0.25}
        out = {"model": "dgemma", "answers": answers,
               "usage": {"input_tokens": 123, "output_tokens": 7},
               "diagnostics": {"groups": 1, "prompt_tokens_source": "engine"}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


class SystemOneHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.run_name = "test_systemone_http_tmp"
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)
        Handler.status, Handler.bodies, Handler.payload = 200, [], None

    def tearDown(self):
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)

    def _main(self, *opts, phase="ood"):
        argv = ["jevbench.run", "systemone_http", "--run", self.run_name, "--phases", phase,
                "--limit", "1", "--opt", f"url={self.url}", *sum((["--opt", o] for o in opts), [])]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            old, sys.argv = sys.argv, argv
            try:
                run.main()
            finally:
                sys.argv = old
        return json.loads((store.ROOT / self.run_name / f"{phase}.json").read_text())

    def test_defaults_unchanged(self):
        doc = self._main("model=dgemma")
        rec = next(iter(doc["cases"].values()))
        self.assertEqual(set(Handler.bodies[0]), {"state", "questions", "model"})
        self.assertNotIn("raw", rec)
        self.assertEqual(rec["usage"], {"input_tokens": 123, "output_tokens": 7})
        self.assertEqual(SystemOneHTTP().timeout, 600.0)

    def test_extra_and_capture_raw_persisted(self):
        extra = {"seed": 42, "samples": "auto", "auto_threshold": 0.1}
        doc = self._main("model=dgemma", "extra=" + json.dumps(extra), "capture_raw=true",
                         "timeout=120")
        body = Handler.bodies[0]
        for k, v in extra.items():
            self.assertEqual(body[k], v)
        rec = next(iter(doc["cases"].values()))
        self.assertEqual(rec["raw"]["request"]["seed"], 42)
        self.assertEqual(rec["raw"]["response"]["diagnostics"]["groups"], 1)
        self.assertEqual(json.loads(doc["meta"]["opts"]["extra"]), extra)

    def test_extra_cannot_override_reserved(self):
        for k in ("state", "questions", "model"):
            with self.assertRaises(ValueError):
                SystemOneHTTP(extra=json.dumps({k: 1}))

    def test_http_error_keeps_status_and_body(self):
        Handler.status = 422
        doc = self._main("model=dgemma")
        rec = next(iter(doc["cases"].values()))
        self.assertIn("HTTP 422", rec["error"])
        self.assertEqual(rec["diag"]["http_status"], 422)
        self.assertIn("schema rejected", rec["diag"]["body"])
        self.assertEqual(len(rec["diag"]["body"]), 2048)

    def test_diag_body_limite_en_bytes(self):
        # el límite es de 2048 bytes, no caracteres (revisión R1, hallazgo 6)
        Handler.status = 422
        Handler.payload = ("á" * 2048).encode()  # 4096 bytes UTF-8
        rec = next(iter(self._main("model=dgemma")["cases"].values()))
        body = rec["diag"]["body"]
        self.assertEqual(len(body), 1024)  # 2048 bytes = 1024 'á'
        self.assertLessEqual(len(body.encode("utf-8")), 2048)
        # corte a mitad de un carácter multibyte: se descarta sin pasarse
        shutil.rmtree(store.ROOT / self.run_name)  # el caso ya quedó con error
        Handler.payload = ("x" + "á" * 1500).encode()  # 3001 bytes
        rec = next(iter(self._main("model=dgemma")["cases"].values()))
        body = rec["diag"]["body"]
        self.assertEqual(body, "x" + "á" * 1023)
        self.assertEqual(len(body.encode("utf-8")), 2047)

    def test_rotate_choice(self):
        qs, _ = load_phase("triage_es")
        doc = self._main("rotate_choice=1", phase="triage_es")
        sent = Handler.bodies[0]["questions"]
        for qid, q in qs.items():
            if q["type"] == "choice":
                keys = list(q["criteria"])
                self.assertEqual(list(sent[qid]["criteria"]), keys[1:] + keys[:1])
                self.assertEqual(sent[qid]["criteria"], q["criteria"])  # same texts
            else:
                self.assertEqual(sent[qid], q)
        self.assertEqual(doc["meta"]["rotate_choice"], 1)
        self.assertTrue(doc["meta"]["perm_sha256"])


if __name__ == "__main__":
    unittest.main()
