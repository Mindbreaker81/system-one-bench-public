"""El GT adjudicado conserva estados/preguntas y la revisión humana parcial."""
import json
import os
import unittest
from unittest.mock import patch

from jevbench import battery


class GroundTruthV5(unittest.TestCase):
    def phases(self, version):
        with patch.dict(os.environ, {"JEVBENCH_GT": version}):
            return {ph: battery.load_phase(ph) for ph in
                    battery.PHASES + battery.EXTRA_PHASES + ['adv4', 'adv5']}

    def test_solo_cambian_etiquetas(self):
        old, new = self.phases('v4'), self.phases('current')
        changes = 0
        total = 0
        for ph, (qs, cases) in new.items():
            oqs, previous = old[ph]
            self.assertEqual(battery.questions_hash(qs), battery.questions_hash(oqs))
            self.assertEqual([(c.id, c.state) for c in cases],
                             [(c.id, c.state) for c in previous])
            total += len(cases)
            changes += sum(a.gt[k] != b.gt[k]
                           for a, b in zip(previous, cases) for k in qs)
        self.assertEqual(total, 194)
        self.assertEqual(changes, 23)

    def test_procedencia_humana_coincide_con_gt_vigente(self):
        p = json.loads((battery.DATA / 'gt_v5_procedencia.json').read_text())
        gt = {c.id: c.gt for _, cases in self.phases('current').values() for c in cases}
        self.assertEqual(sum(len(v) for v in p['fields'].values()), 88)
        self.assertEqual(p['initial_agreements'] + p['adjudications'], 88)
        self.assertEqual(p['changed_labels'] + p['retained_labels'], 37)
        for cid, fields in p['fields'].items():
            for name, evidence in fields.items():
                self.assertEqual(evidence['source'], 'usuario')
                self.assertEqual(evidence['value'], gt[cid][name])

    def test_v3_no_hereda_cambios_v5(self):
        previous, v4 = self.phases('v3'), self.phases('v4')
        self.assertEqual(sum(len(cases) for _, cases in previous.values()), 195)
        for ph in ('adv1', 'adv3'):
            self.assertEqual([(c.id, c.gt) for c in previous[ph][1]],
                             [(c.id, c.gt) for c in v4[ph][1]])

    def test_urgencias_y_hoy_adjudicados(self):
        phases = self.phases('current')
        adv1 = {c.id: c.gt for c in phases['adv1'][1]}
        self.assertEqual(adv1['A04_buried_redflag']['department'], 'urgencias')
        self.assertEqual(tuple(adv1['A04_buried_redflag'][k]
                               for k in ('urgency', 'same_day', 'clinical')), (2, 1, 1))
        self.assertEqual(adv1['A10_polite_lawyer']['same_day'], 0)
