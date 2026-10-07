"""GT v4 (JEV-73): impedir duplicados en los datos actuales de la batería."""
import json
import unittest
from collections import defaultdict
from unittest import mock

from jevbench import battery


def duplicate_states(cases):
    groups = defaultdict(list)
    for case in cases:
        groups[case.state].append(case.id)
    return [ids for ids in groups.values() if len(ids) > 1]


class BatteryIntegrity(unittest.TestCase):
    def test_current_phases_have_unique_states(self):
        # Las traducciones entre fases son intencionadas; dentro de una fase no.
        phases = (battery.PHASES + battery.EXTRA_PHASES
                  + battery.RULES_PHASES + battery.ALERT_PHASES)
        with mock.patch.dict('os.environ', {'JEVBENCH_GT': 'current'}):
            for phase in phases:
                with self.subTest(phase=phase):
                    self.assertEqual(duplicate_states(battery.load_phase(phase)[1]), [])

    def test_current_papers_have_unique_pmids(self):
        papers = json.loads((battery.DATA / 'papers32.json').read_text())
        groups = defaultdict(list)
        for paper in papers:
            groups[paper['pmid']].append(paper['pid'])
        self.assertEqual([ids for ids in groups.values() if len(ids) > 1], [])

    def test_historical_papers_and_gt_remain_available(self):
        # GT v4 (JEV-73) no debe cambiar las cuentas históricas de Lyra.
        for version in ('v1', 'v2', 'v3'):
            with self.subTest(version=version), mock.patch.dict(
                    'os.environ', {'JEVBENCH_GT': version}):
                cases = battery.load_phase('papers32')[1]
                self.assertEqual(len(cases), 32)
                self.assertEqual(duplicate_states(cases), [['P02', 'P03']])
        with mock.patch.dict('os.environ', {'JEVBENCH_GT': 'current'}):
            cases = battery.load_phase('papers32')[1]
            self.assertEqual(len(cases), 31)
            self.assertNotIn('P02', {case.id for case in cases})
            self.assertEqual(next(c.gt['practice'] for c in cases if c.id == 'P03'), 0)
