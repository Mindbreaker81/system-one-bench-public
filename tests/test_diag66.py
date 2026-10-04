"""JEV-66 matrix structure: cell registry, pre-registered order, run naming and
the report's slug/summary on synthetic result dirs. No network or GPU."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jevbench.diag63 import DIAG_CASES
from jevbench.diag66 import CELLS, CELL_ORDER, CONFIG_KEYS
from jevbench.diag65 import _check_resume
from jevbench.diag66_report import _slug, collect, summarize


class Matrix(unittest.TestCase):
    def test_cells_are_the_preregistered_pair(self):
        self.assertEqual(sorted(CELLS),
                         ["typesafe_struct", "typesafe_struct_schema_in_prompt"])
        # control sin inyección, experimental con inyección
        self.assertFalse(CELLS["typesafe_struct"])
        self.assertTrue(CELLS["typesafe_struct_schema_in_prompt"])

    def test_order_alternates_and_covers_both_cells(self):
        self.assertEqual(sorted(CELL_ORDER), [1, 2, 3])
        for order in CELL_ORDER.values():
            self.assertEqual(sorted(order), sorted(CELLS))
        self.assertNotEqual(CELL_ORDER[1], CELL_ORDER[2])

    def test_inject_flag_in_config_keys(self):
        """La opción que define la celda experimental forma parte de la
        configuración efectiva que vigila la reanudación."""
        self.assertIn("inject_schema_in_prompt", CONFIG_KEYS)

    def test_resume_rejects_inject_mismatch(self):
        """Reanudar un run de una celda con la configuración de la otra aborta
        aunque el resto de la configuración coincida."""
        cfg = {"opts": {"model": "m"}, "meta": {"model": "m"},
               "expected": {}}
        stored = {"meta": {"diag": {"cell": "typesafe_struct", "rep": 1},
                           "opts": cfg["opts"], "model": "m",
                           "inject_schema_in_prompt": False},
                  "cases": {"C1": {"answers": {}}}}
        bad = {"opts": cfg["opts"],
               "meta": {"model": "m", "inject_schema_in_prompt": True},
               "expected": {}}
        with self.assertRaises(SystemExit):
            _check_resume("r", "ph", stored,
                          {"cell": "typesafe_struct", "rep": 1}, bad,
                          config_keys=CONFIG_KEYS)
        # la misma celda con la misma configuración reanuda sin problema
        _check_resume("r", "ph", stored,
                      {"cell": "typesafe_struct", "rep": 1},
                      {"opts": cfg["opts"],
                       "meta": {"model": "m", "inject_schema_in_prompt": False},
                       "expected": {}},
                      config_keys=CONFIG_KEYS)


class Report(unittest.TestCase):
    def _tmp_store(self):
        from jevbench import store
        tmp = Path(tempfile.mkdtemp())
        old = store.ROOT
        store.ROOT = tmp
        self.addCleanup(setattr, store, "ROOT", old)
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def test_slug(self):
        self.assertEqual(
            _slug("diag_qwen38_jev66_nvfp4_typesafe_struct_r2", "nvfp4"),
            ("typesafe_struct", 2))
        self.assertEqual(
            _slug("diag_qwen38_jev66_fp8_typesafe_struct_schema_in_prompt_r1",
                  "fp8"),
            ("typesafe_struct_schema_in_prompt", 1))

    def test_collect_counts_missing(self):
        tmp = self._tmp_store()
        run = "diag_qwen38_jev66_tcfg_typesafe_struct_r1"
        (tmp / run).mkdir()
        doc = {"meta": {"diag": {"mode": "probabilities",
                                 "cases": DIAG_CASES["triage_es"]}},
               "cases": {}}
        (tmp / run / "triage_es.json").write_text(json.dumps(doc))
        cells, decs, missing, phase_case = collect("tcfg")
        total = sum(len(v) for v in DIAG_CASES.values())
        self.assertEqual(len(missing[run]), total)
        summary, baselines = summarize("tcfg", cells, decs, missing, phase_case)
        self.assertIn("typesafe_struct", summary)
        self.assertEqual(summary["typesafe_struct"]["reps"][0]["cases"], 0)
        for rep in (1, 2, 3):
            self.assertIn(rep, summary["typesafe_struct"]["missing"])


if __name__ == "__main__":
    unittest.main()
