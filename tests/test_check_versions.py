"""Offline tests for jevbench.check_versions (Jev + gpt-6-luna-decisions)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import check_versions as cv


class CheckVersions(unittest.TestCase):
    def test_families_have_separate_known_sets(self):
        fams = {f["id"]: f for f in cv.active_families()}
        self.assertIn("jev", fams)
        self.assertIn("luna_decisions", fams)
        self.assertEqual(fams["luna_decisions"]["probes"],
                         [("openrouter", "openai/gpt-6-luna-decisions")])
        self.assertIn("openai/gpt-6-luna-decisions-20261006",
                      fams["luna_decisions"]["known"])
        self.assertTrue(fams["jev"]["known"].isdisjoint(fams["luna_decisions"]["known"]))
        self.assertIn("JEV-80", fams["luna_decisions"]["on_new"])
        self.assertIn("JEV-82", fams["luna_decisions"]["on_new"])
        self.assertIn("luna_decisions_jev81.md", fams["luna_decisions"]["on_new"])
        self.assertIn("luna_decisions_jev82.md", fams["luna_decisions"]["on_new"])

    def test_openai_decisions_extension_point_reserved(self):
        self.assertIsNone(cv.OPENAI_DECISIONS_FAMILY)
        self.assertEqual([f["id"] for f in cv.active_families()],
                         ["jev", "luna_decisions"])

    def _fake(self, mapping, errors=None):
        errors = errors or {}

        def probe_fn(provider, model):
            key = f"{provider}:{model}"
            if key in errors:
                raise RuntimeError(errors[key])
            return mapping[key]
        return probe_fn

    def test_known_versions_report_no_change(self):
        probe = self._fake({
            "openrouter:~typesafe/jev-latest": "typesafe/jev-1.13-20260917",
            "typesafe:jev-latest": "jev-1.13.0",
            "typesafe:jev-preview": "jev-1.13.0",
            "openrouter:openai/gpt-6-luna-decisions":
                "openai/gpt-6-luna-decisions-20261006",
        })
        resolved, new = cv.check_families(probe_fn=probe)
        self.assertEqual(new["jev"], [])
        self.assertEqual(new["luna_decisions"], [])
        lines = "\n".join(cv.format_lines(resolved, new))
        self.assertIn("sin cambios (todas las familias)", lines)
        self.assertNotIn("NUEVA VERSIÓN (familias)", lines)

    def test_new_luna_version_names_family_and_reruns(self):
        probe = self._fake({
            "openrouter:~typesafe/jev-latest": "typesafe/jev-1.13-20260917",
            "typesafe:jev-latest": "jev-1.13.0",
            "typesafe:jev-preview": "jev-1.13.0",
            "openrouter:openai/gpt-6-luna-decisions":
                "openai/gpt-6-luna-decisions-20991231",
        })
        resolved, new = cv.check_families(probe_fn=probe)
        self.assertEqual(new["jev"], [])
        self.assertEqual(new["luna_decisions"],
                         ["openai/gpt-6-luna-decisions-20991231"])
        lines = "\n".join(cv.format_lines(resolved, new))
        self.assertIn("NUEVA VERSIÓN (gpt-6-luna-decisions)", lines)
        self.assertIn("familia gpt-6-luna-decisions", lines)
        self.assertIn("JEV-80", lines)
        self.assertIn("JEV-82", lines)
        self.assertIn("jev_luna_decisions", lines)
        self.assertIn("jev_luna_decisions_d1", lines)
        self.assertIn("NUEVA VERSIÓN (familias): gpt-6-luna-decisions", lines)
        # Jev still reports sin cambios in its block
        self.assertIn("sin cambios (Jev;", lines)

    def test_new_jev_version_does_not_confuse_luna(self):
        probe = self._fake({
            "openrouter:~typesafe/jev-latest": "typesafe/jev-1.14-20990101",
            "typesafe:jev-latest": "jev-1.14.0",
            "typesafe:jev-preview": "jev-1.14.0",
            "openrouter:openai/gpt-6-luna-decisions":
                "openai/gpt-6-luna-decisions-20261006",
        })
        resolved, new = cv.check_families(probe_fn=probe)
        self.assertEqual(new["luna_decisions"], [])
        self.assertIn("typesafe/jev-1.14-20990101", new["jev"])
        lines = "\n".join(cv.format_lines(resolved, new))
        self.assertIn("familia Jev:", lines)
        self.assertIn("jev_v3", lines)
        self.assertNotIn("NUEVA VERSIÓN (gpt-6-luna-decisions)", lines)

    def test_probe_error_is_recorded_not_as_new(self):
        probe = self._fake({
            "openrouter:~typesafe/jev-latest": "typesafe/jev-1.13-20260917",
            "typesafe:jev-latest": "jev-1.13.0",
            "typesafe:jev-preview": "jev-1.13.0",
        }, errors={"openrouter:openai/gpt-6-luna-decisions": "HTTP 502 refused"})
        resolved, new = cv.check_families(probe_fn=probe)
        self.assertTrue(resolved["luna_decisions"][
            "openrouter:openai/gpt-6-luna-decisions"].startswith("ERROR"))
        self.assertEqual(new["luna_decisions"], [])
        self.assertEqual(new["jev"], [])

    def test_log_appends_under_each_section(self):
        probe = self._fake({
            "openrouter:~typesafe/jev-latest": "typesafe/jev-1.13-20260917",
            "typesafe:jev-latest": "jev-1.13.0",
            "typesafe:jev-preview": "jev-1.13.0",
            "openrouter:openai/gpt-6-luna-decisions":
                "openai/gpt-6-luna-decisions-20261006",
        })
        resolved, new = cv.check_families(probe_fn=probe)
        base = (
            "# Versiones\n\n## Jev\n\n"
            "| fecha | alias → versión resuelta | resultado |\n"
            "|---|---|---|\n"
            "| 2026-09-27 | `old` → `v` | sin cambios |\n\n"
            "## gpt-6-luna-decisions (OpenRouter)\n\n"
            "| fecha | alias → versión resuelta | resultado |\n"
            "|---|---|---|\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "versiones_jev.md"
            log.write_text(base)
            with mock.patch.object(cv, "LOG", log):
                cv.append_log(resolved, new)
            text = log.read_text()
            self.assertIn("`openrouter:openai/gpt-6-luna-decisions`", text)
            self.assertIn("`openrouter:~typesafe/jev-latest`", text)
            # historical row preserved
            self.assertIn("| 2026-09-27 | `old` → `v` | sin cambios |", text)
            # jev section still before luna
            self.assertLess(text.index("## Jev"),
                            text.index("## gpt-6-luna-decisions"))


if __name__ == "__main__":
    unittest.main()
