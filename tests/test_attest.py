"""JEV-87: atestaciones congeladas de los análisis confirmatorios (se exporta al espejo)."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import attest

OUTPUT = "A: CONFIRMADA\nB: REFUTADA\n"


class Attest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "docs" / "auditorias"
        self.out.mkdir(parents=True)
        self.dep = "results/runx/triage_es.json"
        (self.tmp / "results" / "runx").mkdir(parents=True)
        (self.tmp / self.dep).write_text(json.dumps({"meta": {}, "cases": {"T01": {"answers": {}}}}))
        self._p = [mock.patch.object(attest, "ROOT", self.tmp),
                   mock.patch.object(attest, "OUT", self.out),
                   mock.patch.object(attest, "EXPERIMENTS", {"x": (["-c", "pass"], True)}),
                   mock.patch.object(attest, "_dep_hash",
                                     lambda rel: (hashlib.sha256((self.tmp / rel).read_bytes())
                                                  .hexdigest(), True))]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()

    def _doc(self, **over):
        h = hashlib.sha256((self.tmp / self.dep).read_bytes()).hexdigest()
        doc = {"experiment": "x", "command": "python3 -c pass", "needs_raw": True, "returncode": 0,
               "output": OUTPUT, "runs": ["runx"], "files": {self.dep: {"sha256": h, "exported": True}}}
        doc.update(over)
        (self.out / "x.json").write_text(json.dumps(doc))

    def _verify_public(self, names=None):
        msgs = []
        with mock.patch.object(attest, "in_public_export", lambda: True):
            n = attest.verify(names, printer=msgs.append)
        return n, msgs

    def test_ligadura_correcta_y_veredictos_de_la_salida(self):
        self._doc(verdicts=["A: FABRICADO"])  # un campo ajeno no se imprime: se deriva de output
        n, msgs = self._verify_public()
        self.assertEqual(n, 0)
        self.assertIn("    A: CONFIRMADA", msgs)
        self.assertFalse(any("FABRICADO" in m for m in msgs))

    def test_dependencia_alterada_se_detecta(self):
        self._doc()
        (self.tmp / self.dep).write_text("{}")
        n, msgs = self._verify_public()
        self.assertGreater(n, 0)
        self.assertTrue(any("hash distinto" in m for m in msgs))

    def test_dependencia_privada_no_se_exige_en_el_espejo(self):
        self._doc(files={"results/logs/ref.json": {"sha256": "0" * 64, "exported": False},
                         self.dep: {"sha256": hashlib.sha256((self.tmp / self.dep).read_bytes())
                                    .hexdigest(), "exported": True}})
        self.assertEqual(self._verify_public()[0], 0)

    def test_analisis_fallido_no_vale(self):
        self._doc(returncode=1)
        self.assertGreater(self._verify_public()[0], 0)

    def test_registro_distinto_no_vale(self):
        self._doc(needs_raw=False)
        self.assertGreater(self._verify_public()[0], 0)

    def test_falta_atestacion_obligatoria(self):
        n, msgs = self._verify_public()
        self.assertEqual(n, 1)
        self.assertTrue(any("falta docs/auditorias/x.json" in m for m in msgs))

    def test_nombre_desconocido(self):
        self._doc()
        self.assertGreater(self._verify_public(["no_existe"])[0], 0)

    def test_freeze_aborta_si_el_analizador_falla(self):
        with mock.patch.object(attest, "_run", lambda cmd, trace=False: (1, "fallo", [])), \
                mock.patch.object(attest, "in_public_export", lambda: False):
            with self.assertRaises(SystemExit):
                attest.freeze(["x"])
        self.assertFalse((self.out / "x.json").exists())

    def test_freeze_aborta_sin_resultados(self):
        with mock.patch.object(attest, "_run", lambda cmd, trace=False: (0, OUTPUT, ["jevbench/x.py"])), \
                mock.patch.object(attest, "in_public_export", lambda: False):
            with self.assertRaises(SystemExit):
                attest.freeze(["x"])

    def test_analizador_no_ligado_se_detecta(self):
        # R84: el fichero del propio analizador debe estar entre las dependencias ligadas
        with mock.patch.object(attest, "EXPERIMENTS", {"x": (["-m", "jevbench.attest"], True)}):
            self._doc(command="python3 -m jevbench.attest")
            n, msgs = self._verify_public()
        self.assertGreater(n, 0)
        self.assertTrue(any("analizador no está ligado" in m for m in msgs))

    def test_public_exit_en_privado(self):
        with mock.patch.object(attest, "in_public_export", lambda: False):
            self.assertEqual(attest.public_exit(printer=lambda *a: None), 0)
        with mock.patch.object(attest, "in_public_export", lambda: True):
            self.assertEqual(attest.public_exit(printer=lambda *a: None), attest.PUBLIC_EXIT)


class AttestReal(unittest.TestCase):
    """Las atestaciones del repo verifican contra los ficheros versionados (las rápidas)."""

    def test_cada_atestacion_liga_su_analizador(self):
        for name, (cmd, _) in attest.EXPERIMENTS.items():
            f = attest.OUT / f"{name}.json"
            if not f.exists():
                self.skipTest("sin auditorías congeladas")
            files = json.loads(f.read_text())["files"]
            self.assertIn(attest._entry_file(cmd), files, name)

    def test_reproducidas(self):
        if not (attest.OUT / "jev82.json").exists():
            self.skipTest("sin auditorías congeladas")
        self.assertEqual(attest.verify(["jev78", "jev82"], printer=lambda *a: None), 0)
