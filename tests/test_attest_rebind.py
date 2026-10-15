"""Una subida de versión sin re-ligar las auditorías rompe `attest verify` (y la publicación)."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from jevbench import attest  # noqa: E402


@unittest.skipIf(attest.in_public_export(), "solo en el repo privado")
class AttestRebind(unittest.TestCase):
    def test_version_hash_bound(self):
        import attest_rebind
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = attest_rebind.main(["--check", "jevbench/__init__.py"])
        self.assertEqual(rc, 0, "auditorías desfasadas tras cambiar jevbench/__init__.py: "
                         "python3 scripts/attest_rebind.py jevbench/__init__.py\n" + out.getvalue())


if __name__ == "__main__":
    unittest.main()
