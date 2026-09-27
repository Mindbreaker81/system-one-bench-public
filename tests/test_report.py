"""jevbench.report only rewrites the AUTO sections and --check detects stale docs."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import report

DOC = """# Título

texto a mano

<!-- AUTO:comando -->
viejo
<!-- /AUTO:comando -->

## Marcador

<!-- AUTO:marcador -->
tabla vieja
<!-- /AUTO:marcador -->

Lectura escrita a mano.
"""
GEN = {"comando": "cmd nuevo", "marcador": "| tabla | nueva |"}


class Report(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.doc = Path(self.tmp.name) / "r.md"
        self.runs = Path(self.tmp.name) / "runs.txt"
        self.doc.write_text(DOC)
        self.runs.write_text("# comentario\njev_v3  # inline\n\n")
        self.patch = mock.patch.object(report, "sections", lambda runs: GEN)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def run_report(self, *extra):
        return report.main(["--doc", str(self.doc), "--runs", str(self.runs), *extra])

    def test_read_runs(self):
        self.assertEqual(report.read_runs(self.runs), ["jev_v3"])

    def test_only_auto_sections_change_and_idempotent(self):
        self.run_report()
        once = self.doc.read_text()
        self.assertIn("cmd nuevo", once)
        self.assertIn("| tabla | nueva |", once)
        self.assertNotIn("tabla vieja", once)
        for manual in ("# Título", "texto a mano", "Lectura escrita a mano."):
            self.assertIn(manual, once)
        self.run_report()
        self.assertEqual(self.doc.read_text(), once)

    def test_check(self):
        self.assertEqual(self.run_report("--check"), 1)
        self.assertEqual(self.doc.read_text(), DOC)  # --check never writes
        self.run_report()
        self.assertEqual(self.run_report("--check"), 0)


if __name__ == "__main__":
    unittest.main()
