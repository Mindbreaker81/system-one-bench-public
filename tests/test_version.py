"""One semantic version for the whole repo: jevbench.__version__ must match the newest
CHANGELOG entry and the version line in README."""
import re
import unittest
from pathlib import Path

import jevbench

ROOT = Path(__file__).resolve().parent.parent


class Version(unittest.TestCase):
    def test_changelog_matches(self):
        m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(), re.M)
        self.assertIsNotNone(m, "CHANGELOG.md: no hay ninguna sección ## [X.Y.Z]")
        self.assertEqual(m.group(1), jevbench.__version__,
                         "la versión más reciente del CHANGELOG no es jevbench.__version__")

    def test_readme_matches(self):
        m = re.search(r"\*\*Versión (\d+\.\d+\.\d+)\*\*", (ROOT / "README.md").read_text())
        self.assertIsNotNone(m, "README.md: falta la línea **Versión X.Y.Z**")
        self.assertEqual(m.group(1), jevbench.__version__)


if __name__ == "__main__":
    unittest.main()
