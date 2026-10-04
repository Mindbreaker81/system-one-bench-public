"""Runner checks that need no optional dependency: option redaction in meta, usage
persisted on success, ms + safe diag on error, and a sentinel secret that must never
reach the stored JSON or the console output."""
import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

from jevbench import adapters, run, store
from jevbench.adapters import Adapter

SENTINEL = "sk-CENTINELA-JEV44-no-versionar"


class FakeAdapter(Adapter):
    fail = False

    def __init__(self, **opts):
        super().__init__(**opts)
        # the adapter must still receive the real secret value
        FakeAdapter.received_api_key = opts.get("api_key")

    def meta(self):
        return {"fake": True}

    def decide(self, state, questions):
        if self.fail:
            e = RuntimeError("boom")
            e.diag = {"attempts": 1, "provider_error": "TypeSafeError"}
            raise e
        return {"answers": {}, "cost": None, "model": "fake",
                "usage": {"input_tokens": 10, "output_tokens": 5, "attempts": 1,
                          "latency": 0.01, "debug_blob": {"ignored": "x"}}}


class Runner(unittest.TestCase):
    def setUp(self):
        self.run_name = "test_run_tmp"
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)
        # __name__ resolves to this very module under both `unittest discover`
        # (test_run) and `python -m unittest tests.test_run`.
        adapters.REGISTRY["fake_test"] = f"{__name__}:FakeAdapter"
        FakeAdapter.fail = False

    def tearDown(self):
        shutil.rmtree(store.ROOT / self.run_name, ignore_errors=True)
        adapters.REGISTRY.pop("fake_test", None)

    def _main(self, *extra):
        argv = ["jevbench.run", "fake_test", "--run", self.run_name,
                "--phases", "ood", "--limit", "1", *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            old = sys.argv
            try:
                sys.argv = argv
                run.main()
            finally:
                sys.argv = old
        return out.getvalue(), err.getvalue()

    def _doc(self):
        return json.loads((store.ROOT / self.run_name / "ood.json").read_text())

    def test_safe_opts(self):
        opts = {"api_key": SENTINEL, "hf_token": "t", "client_secret": "s",
                "db_password": "p", "model": "m", "timeout": "5", "max_tokens": "8192"}
        safe = run.safe_opts(opts)
        for k in ("api_key", "hf_token", "client_secret", "db_password"):
            self.assertEqual(safe[k], "<redacted>", k)
        self.assertEqual(safe["model"], "m")
        self.assertEqual(safe["timeout"], "5")
        self.assertEqual(safe["max_tokens"], "8192")  # es un tope de salida, no una credencial

    def test_safe_opts_redacts_nested_json(self):
        opts = {"extra_body": json.dumps({
            "headers": {"Authorization": f"Bearer {SENTINEL}"},
            "nested": [{"access_token": SENTINEL}], "temperature": 0.7})}
        safe = run.safe_opts(opts)
        self.assertNotIn(SENTINEL, json.dumps(safe))
        parsed = json.loads(safe["extra_body"])
        self.assertEqual(parsed["headers"]["Authorization"], "<redacted>")
        self.assertEqual(parsed["nested"][0]["access_token"], "<redacted>")
        self.assertEqual(parsed["temperature"], 0.7)

    def test_usage_and_ms_persisted(self):
        self._main("--opt", f"api_key={SENTINEL}", "--opt", "model=m")
        rec = next(iter(self._doc()["cases"].values()))
        self.assertEqual(rec["usage"]["input_tokens"], 10)
        self.assertEqual(rec["usage"]["attempts"], 1)
        self.assertNotIn("debug_blob", rec["usage"])
        self.assertIsNotNone(rec["ms"])

    def test_error_saves_ms_and_diag(self):
        FakeAdapter.fail = True
        self._main()
        rec = next(iter(self._doc()["cases"].values()))
        self.assertIn("boom", rec["error"])
        self.assertIsNotNone(rec["ms"])
        self.assertEqual(rec["diag"]["attempts"], 1)

    def test_secret_never_serialized(self):
        out, err = self._main("--opt", f"api_key={SENTINEL}", "--opt", "model=m")
        raw = (store.ROOT / self.run_name / "ood.json").read_text()
        self.assertNotIn(SENTINEL, raw)
        self.assertNotIn(SENTINEL, out + err)
        self.assertEqual(self._doc()["meta"]["opts"]["api_key"], "<redacted>")
        self.assertEqual(FakeAdapter.received_api_key, SENTINEL)


if __name__ == "__main__":
    unittest.main()
