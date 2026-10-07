"""The unified scorer must reproduce the numbers published in the legacy reports
(jev_vs_laya.md, anyjev_vs_jev.md). Run: python -m unittest discover tests"""
import unittest
from unittest import mock

from jevbench import legacy_import, metrics
from jevbench.score import baseline, score_run


class LegacyRescore(unittest.TestCase):
    def setUp(self):
        # GT v4 (JEV-73): v1 solo en estas regresiones; no contaminar los tests
        # del sitio ni las comprobaciones de la batería actual al importar el módulo.
        patch = mock.patch.dict('os.environ', {'JEVBENCH_GT': 'v1'})
        patch.start()
        self.addCleanup(patch.stop)

    @classmethod
    def setUpClass(cls):
        legacy_import.main()

    def check(self, run, phase, pct=None, dept=None, **extra):
        r = score_run(run, phase)
        if pct is not None:
            self.assertAlmostEqual(r["pct"], pct, places=1, msg=f"{run} {phase}")
        if dept is not None:
            self.assertEqual(r["per_q"]["department"], dept, msg=f"{run} {phase}")
        return r

    def test_jev_v2(self):
        self.check("legacy_jev_v2", "triage_es", 86.4, 12)
        self.check("legacy_jev_v2", "triage_en", 88.6, 12)
        r = self.check("legacy_jev_v2", "papers32", 66.2)
        self.assertAlmostEqual(r["spearman"], 0.866, places=3)
        self.assertEqual(r["cascade"]["skip_recall_cv2"], 6)
        self.check("legacy_jev_v2", "adv1", 79.0, 8)
        self.check("legacy_jev_v2", "adv2", dept=7)

    def test_jev_v1(self):
        self.check("legacy_jev_v1", "triage_es", 87.1)
        self.check("legacy_jev_v1", "triage_en", 85.0)
        self.check("legacy_jev_v1", "adv1", 81.0)

    def test_anyjev(self):
        self.check("legacy_anyjev_qwen3_1.7b", "triage_es", 80.0, 11)
        self.check("legacy_anyjev_qwen3_1.7b", "triage_en", 70.0, 12)
        r = self.check("legacy_anyjev_qwen3_1.7b", "papers32", 62.2)
        self.assertAlmostEqual(r["spearman"], 0.501, places=3)
        self.assertEqual(r["cascade"]["cv2"], 13)  # 40.6 %
        self.assertEqual(r["cascade"]["skip_recall_cv2"], 4)
        self.check("legacy_anyjev_qwen3_1.7b", "adv1", dept=8)
        self.check("legacy_anyjev_qwen3_1.7b", "adv2", dept=6)

    def test_gliner(self):
        self.check("legacy_gliner_decide", "triage_es", 79.3, 8)
        self.check("legacy_gliner_decide", "triage_en", 71.4, 8)
        # the 24-sep report printed 45.6 %, but its own per-dimension counts add up to 78.5/160
        self.check("legacy_gliner_decide", "papers32", 49.1)
        self.check("legacy_gliner_decide", "adv1", dept=2)
        self.check("legacy_gliner_decide", "adv2", dept=1)

    def test_laya(self):
        self.check("legacy_laya_v2", "papers32", 48.1)
        self.check("legacy_laya_v2", "adv2", dept=3)

    def test_gt_version(self):
        from jevbench import battery
        self.assertEqual(battery.gt_problems("papers32"), [("P04", "domain", "ild")])

    def test_baseline_adversarial(self):
        self.assertEqual(baseline("adv1")["per_q"]["department"] + baseline("adv2")["per_q"]["department"], 17)


class Metrics(unittest.TestCase):
    def test_mcnemar(self):
        self.assertEqual(metrics.mcnemar([1, 1, 0], [1, 1, 0]), (0, 0, 1.0))
        b, c, p = metrics.mcnemar([1] * 6 + [0] * 4, [0] * 6 + [0] * 4)
        self.assertEqual((b, c), (6, 0))
        self.assertAlmostEqual(p, 0.03125)

    def test_kappa_nominal_ignores_label_order(self):
        from jevbench.annotation2 import cohen_kappa
        base = [("urgencias", "urgencias")] * 4 + [("bronchoscopia", "bronchoscopia")] * 4 + [("admin", "admin")] * 4
        a = [("admin", "urgencias")] * 6 + base
        b = [("admin", "bronchoscopia")] * 6 + base
        self.assertAlmostEqual(cohen_kappa(a), cohen_kappa(b), places=3)
        self.assertAlmostEqual(cohen_kappa([("0", "0"), ("1", "1"), ("0", "1"), ("1", "1")]), 0.5)

    def test_score_point(self):
        q = {"type": "score", "criteria": ["a", "b", "c"]}
        self.assertEqual(metrics.point(q, {"value": 1.4}, 2), 0.5)
        self.assertEqual(metrics.point(q, {"value": 2.6}, 2), 1.0)


if __name__ == "__main__":
    unittest.main()
